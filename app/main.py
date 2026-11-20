from fastapi import FastAPI

from app.routers import auth, tickets

app = FastAPI(title="SupportDesk AI")
app.include_router(auth.router)
app.include_router(tickets.router)
