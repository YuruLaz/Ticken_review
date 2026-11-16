from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url)

# Without expire_on_commit=False, reading an attribute after commit triggers a
# lazy reload, which fails in async code.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session
