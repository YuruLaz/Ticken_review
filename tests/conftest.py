import os

# Set before the app is imported (its load_dotenv() doesn't override): tests use a fake LLM
# and must not send traces to LangSmith.
os.environ["LANGSMITH_TRACING"] = "false"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai import nodes
from app.core.config import settings
from app.database.base import Base
from app.database.db import get_session
from app.main import app

# Same server as the dev database, so the only extra setup is creating this database once.
TEST_DATABASE_URL = make_url(settings.database_url).set(database="supportdesk_test")


@pytest.fixture
async def session_maker():
    # A new engine per test: asyncpg connections belong to one event loop, and
    # each test gets its own loop, so the app's global engine can't be reused.
    engine = create_async_engine(TEST_DATABASE_URL)
    # Dropping at the start rather than the end leaves a failed test's data
    # behind so you can inspect it.
    async with engine.begin() as conn:
        # Alembic enables this in the dev DB; create_all doesn't, and kb_articles needs it.
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

    # Every route that depends on get_session gets the test database instead.
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

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0)


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    # Patch the name nodes.py imported, not app.ai.llm.get_llm: nodes holds its own reference.
    monkeypatch.setattr(nodes, "get_llm", lambda: fake)
    return fake
