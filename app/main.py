from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.ai.graph import build_graph
from app.core.config import settings
from app.routers import auth, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The checkpointer uses psycopg, not asyncpg, so it needs the plain postgresql:// URL.
    conn_string = settings.database_url.replace("+asyncpg", "")
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="SupportDesk AI", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tickets.router)
