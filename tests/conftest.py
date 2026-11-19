import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
