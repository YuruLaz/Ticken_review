import os

os.environ["LANGSMITH_TRACING"] = "false"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.pipeline import nodes
from app.core.config import settings
from app.database.base import Base
from app.database.db import get_session
from app.main import app

TEST_DATABASE_URL = make_url(settings.database_url).set(database="supportdesk_test")


@pytest.fixture
async def session_maker():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(session_maker):
    async def get_test_session():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


class FakeLLM:
    """Stands in for Gemini: returns the queued answers in order and remembers the prompts."""

    def __init__(self):
        self.answers = []
        self.prompts = []

    def with_structured_output(self, schema):
        return self

    def with_retry(self, **kwargs):
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(nodes, "get_llm", lambda: fake)
    return fake
