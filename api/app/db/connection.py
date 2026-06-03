import os
from contextlib import contextmanager

import psycopg
from redis import Redis

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://demo:demo@localhost:5432/ticket_demo")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

@contextmanager
def db_conn():
    conn = psycopg.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()