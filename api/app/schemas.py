from pydantic import BaseModel
from typing import Any

class ReserveRequest(BaseModel):
    movie_id: str
    show_id: str
    seat_ids: list[str]
    user_ref: str
    idempotency_key: str

class PaymentInitRequest(BaseModel):
    reservation_id: str
    idempotency_key: str

class PaymentConfirmRequest(BaseModel):
    payment_ref: str
    idempotency_key: str

class GenericResponse(BaseModel):
    data: Any