from fastapi import APIRouter, Response, HTTPException, Request

from app.schemas import ReserveRequest, PaymentInitRequest, PaymentConfirmRequest
from app.services.idempotency import request_hash, get_idempotent_response, store_idempotent_response, acquire_idempotency_lock, release_idempotency_lock
from app.services.booking import create_reservation, initiate_payment, confirm_payment, expire_pending_reservations
from app.db.connection import db_conn

router = APIRouter()


def maybe_idempotent(idem_key: str):
    existing = get_idempotent_response(idem_key)
    if existing:
        body, status_code = existing
        return body, status_code, True
    
    if not acquire_idempotency_lock(idem_key):
        raise HTTPException(status_code=409, detail="Concurrent request processing. Please retry.")

    return None, None, False


@router.post("/reservations")
def reserve_seats(req: ReserveRequest, response: Response):
    cached, status_code, hit = maybe_idempotent(req.idempotency_key)
    if hit:
        response.headers["X-Idempotency"] = "HIT"
        return cached

    try:
        payload = req.model_dump()
        result = create_reservation(payload)
        store_idempotent_response(req.idempotency_key, "/reservations", request_hash(payload), result, 200)
        response.headers["X-Idempotency"] = "MISS"
        return result
    except Exception:
        release_idempotency_lock(req.idempotency_key)
        raise


@router.post("/payments/initiate")
def payment_initiate(req: PaymentInitRequest, response: Response, request: Request):
    expire_pending_reservations()
    cached, status_code, hit = maybe_idempotent(req.idempotency_key)
    if hit:
        if request.headers.get("X-Simulate-Drop") == "true":
            raise HTTPException(status_code=504, detail="Simulated Network Drop: Gateway Timeout")
        response.headers["X-Idempotency"] = "HIT"
        return cached

    try:
        payload = req.model_dump()
        result = initiate_payment(req.reservation_id)
        store_idempotent_response(req.idempotency_key, "/payments/initiate", request_hash(payload), result, 200)
        
        if request.headers.get("X-Simulate-Drop") == "true":
            raise HTTPException(status_code=504, detail="Simulated Network Drop: Gateway Timeout")

        response.headers["X-Idempotency"] = "MISS"
        return result
    except HTTPException:
        raise
    except Exception:
        release_idempotency_lock(req.idempotency_key)
        raise


@router.post("/payments/confirm")
def payment_confirm(req: PaymentConfirmRequest, response: Response):
    cached, status_code, hit = maybe_idempotent(req.idempotency_key)
    if hit:
        response.headers["X-Idempotency"] = "HIT"
        return cached

    try:
        payload = req.model_dump()
        result = confirm_payment(req.payment_ref)
        store_idempotent_response(req.idempotency_key, "/payments/confirm", request_hash(payload), result, 200)
        response.headers["X-Idempotency"] = "MISS"
        return result
    except Exception:
        release_idempotency_lock(req.idempotency_key)
        raise


@router.get("/demo/timeline")
def timeline(reservation_id: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, details, created_at
                FROM event_log
                WHERE reservation_id = %s
                ORDER BY id ASC
                """,
                (reservation_id,),
            )
            rows = cur.fetchall()

            cur.execute("SELECT show_id, seat_ids, status, expires_at FROM reservations WHERE id = %s", (reservation_id,))
            res = cur.fetchone()

    events = [
        {"event_type": r[0], "details": r[1], "at": r[2].isoformat()} for r in rows
    ]

    reservation = None
    if res:
        reservation = {
            "show_id": res[0],
            "seat_ids": res[1],
            "status": res[2],
            "expires_at": res[3].isoformat(),
        }

    return {"reservation": reservation, "events": events}


@router.get("/seats")
def seats(show_id: str = "show-1"):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT seat_no, status FROM seats WHERE show_id = %s ORDER BY seat_no", (show_id,))
            rows = cur.fetchall()
    return {"show_id": show_id, "seats": [{"seat_no": r[0], "status": r[1]} for r in rows]}