import os
import time
import uuid
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.db.connection import db_conn, redis_client

LOCK_TTL_SECONDS = 120
PAYMENT_DELAY_SECONDS = int(os.getenv("PAYMENT_DELAY_SECONDS", "6"))


def log_event(reservation_id: str | None, event_type: str, details: dict):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO event_log (reservation_id, event_type, details) VALUES (%s, %s, %s::jsonb)",
                (reservation_id, event_type, json.dumps(details)),
            )
        conn.commit()


def acquire_seat_locks(show_id: str, seat_ids: list[str], reservation_id: str):
    locked = []
    for seat in seat_ids:
        key = f"seat_lock:{show_id}:{seat}"
        ok = redis_client.set(key, reservation_id, nx=True, ex=LOCK_TTL_SECONDS)
        if ok:
            locked.append(key)
        else:
            for lk in locked:
                redis_client.delete(lk)
            raise HTTPException(status_code=409, detail=f"Seat {seat} is already locked")


def create_reservation(payload: dict):
    reservation_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=LOCK_TTL_SECONDS)

    acquire_seat_locks(payload["show_id"], payload["seat_ids"], reservation_id)

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO reservations (id, user_ref, movie_id, show_id, seat_ids, status, expires_at)
                VALUES (%s, %s, %s, %s, %s, 'PENDING', %s)
                """,
                (
                    reservation_id,
                    payload["user_ref"],
                    payload["movie_id"],
                    payload["show_id"],
                    payload["seat_ids"],
                    expires_at,
                ),
            )
        conn.commit()

    log_event(reservation_id, "LOCK_ACQUIRED", {"seats": payload["seat_ids"], "expires_at": expires_at.isoformat()})
    return {"reservation_id": reservation_id, "status": "PENDING", "expires_at": expires_at.isoformat()}


def initiate_payment(reservation_id: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM reservations WHERE id = %s", (reservation_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Reservation not found")
            if row[0] != "PENDING":
                raise HTTPException(status_code=409, detail=f"Reservation is {row[0]}")

    payment_ref = str(uuid.uuid4())
    payment_id = str(uuid.uuid4())
    
    log_event(reservation_id, "PAYMENT_INITIATED", {"payment_ref": payment_ref, "intentional_delay_seconds": PAYMENT_DELAY_SECONDS})
    time.sleep(PAYMENT_DELAY_SECONDS)

    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO payments (id, reservation_id, status, external_ref) VALUES (%s, %s, 'INITIATED', %s)",
                (payment_id, reservation_id, payment_ref),
            )
        conn.commit()

    return {"payment_ref": payment_ref, "payment_url": f"/mock-payment/{payment_ref}", "status": "INITIATED"}


def confirm_payment(payment_ref: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, reservation_id, status FROM payments WHERE external_ref = %s", (payment_ref,))
            pay = cur.fetchone()
            if not pay:
                raise HTTPException(status_code=404, detail="Payment not found")

            payment_id, reservation_id, pay_status = pay
            if pay_status == "CONFIRMED":
                return {"payment_ref": payment_ref, "status": "ALREADY_CONFIRMED"}

            cur.execute("SELECT show_id, seat_ids FROM reservations WHERE id = %s", (reservation_id,))
            res = cur.fetchone()
            if not res:
                raise HTTPException(status_code=404, detail="Reservation not found")
            show_id, seats = res

            cur.execute("UPDATE payments SET status = 'CONFIRMED' WHERE id = %s", (payment_id,))
            cur.execute("UPDATE reservations SET status = 'CONFIRMED' WHERE id = %s", (reservation_id,))
            for seat in seats:
                cur.execute(
                    "UPDATE seats SET status = 'SOLD' WHERE show_id = %s AND seat_no = %s",
                    (show_id, seat),
                )
        conn.commit()

    for seat in seats:
        redis_client.delete(f"seat_lock:{show_id}:{seat}")

    log_event(reservation_id, "PAYMENT_CONFIRMED", {"payment_ref": payment_ref})
    return {"payment_ref": payment_ref, "status": "CONFIRMED"}


def expire_pending_reservations():
    now = datetime.now(timezone.utc)
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, show_id, seat_ids FROM reservations WHERE status = 'PENDING' AND expires_at < %s", (now,))
            rows = cur.fetchall()
            for rid, show_id, seats in rows:
                cur.execute("UPDATE reservations SET status = 'EXPIRED' WHERE id = %s", (rid,))
                for seat in seats:
                    redis_client.delete(f"seat_lock:{show_id}:{seat}")
                log_event(str(rid), "LOCK_EXPIRED", {"seats": seats})
        conn.commit()
