from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.ai.graph import build_graph
from app.ai.tracing import setup_tracing
from app.core.config import settings
from app.routers import auth, review, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    # The checkpointer uses psycopg, not asyncpg, so it needs the plain postgresql:// URL.
    conn_string = settings.database_url.replace("+asyncpg", "")
    # A pool, not one shared connection: concurrent tickets save checkpoints in parallel, and
    # broken connections get replaced. The kwargs are what the checkpointer requires per connection.
    # open=False: the pool is opened by async with, not in the constructor (which can't await).
    async with AsyncConnectionPool(
        conn_string,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="SupportDesk AI", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(review.router)
