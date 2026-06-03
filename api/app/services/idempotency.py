import json
import hashlib
from typing import Any

from app.db.connection import db_conn, redis_client


def request_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def acquire_idempotency_lock(idem_key: str) -> bool:
    lock_key = f"idem_lock:{idem_key}"
    return bool(redis_client.set(lock_key, "LOCKED", nx=True, ex=30))


def release_idempotency_lock(idem_key: str):
    lock_key = f"idem_lock:{idem_key}"
    redis_client.delete(lock_key)


def get_idempotent_response(idem_key: str):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT response_json, status_code FROM idempotency_keys WHERE idem_key = %s",
                (idem_key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return row[0], row[1]


def store_idempotent_response(idem_key: str, endpoint: str, req_hash: str, response_json: dict[str, Any], status_code: int):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO idempotency_keys (idem_key, endpoint, request_hash, response_json, status_code)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (idem_key) DO NOTHING
                """,
                (idem_key, endpoint, req_hash, json.dumps(response_json), status_code),
            )
        conn.commit()
    release_idempotency_lock(idem_key)