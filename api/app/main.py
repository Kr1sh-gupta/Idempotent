from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.demo import router

app = FastAPI(title="Ticket Idempotency Playground")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"ok": True, "name": "ticket-idempotency-demo"}