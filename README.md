# Ticket Idempotency Playground

This playground demonstrates idempotency + seat locking in a movie-ticket flow.

## Stack
- FastAPI API (`http://localhost:8000/docs`)
- Frontend mockup (`http://localhost:3000`)
- Postgres
- Redis (TTL seat locks)
- pgAdmin (`http://localhost:5050`)

## Start
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

## Stop (safe cleanup only for this project)
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop.ps1
```

## Auto cleanup on close
Runs stack in foreground and auto-cleans this project when you Ctrl+C.
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-with-autocleanup.ps1
```

## Demo steps
1. Open frontend and select seats.
2. Click `Reserve Seats`.
3. Click `Proceed to Payment` once (UI sends 3 concurrent clicks with same idempotency key).
4. Observe `HIT/MISS` behavior and timeline panel.
5. Click `Confirm Payment` and verify seats become SOLD.
6. Inspect tables in pgAdmin if needed (`demo/demo`, db `ticket_demo`, host `postgres` from pgAdmin container context).