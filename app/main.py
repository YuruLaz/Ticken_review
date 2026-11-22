import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.ai.graph import build_graph
from app.ai.triage import fail_interrupted_runs
from app.ai.tracing import setup_tracing
from app.core.config import settings
from app.routers import analytics, auth, kb, review, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    # psycopg needs the plain postgresql:// URL.
    conn_string = settings.database_url.replace("+asyncpg", "")
    # Pool: parallel checkpoints, replaces broken connections.
    # open=False: opened by async with.
    async with AsyncConnectionPool(
        conn_string,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)
        # Background runs die with the process.
        if count := await fail_interrupted_runs():
            logging.getLogger(__name__).warning("Marked %s interrupted tickets as failed", count)
        yield


app = FastAPI(title="SupportDesk AI", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(review.router)
app.include_router(analytics.router)
app.include_router(kb.router)
