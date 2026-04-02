"""
Shared pytest fixtures.
Uses an in-memory SQLite database so tests are isolated and fast.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models.db import Base
from app.models.database import get_db
from app.services.auth import _hash_key
from app.models.db import ApiKey
from main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_KEY = "test-api-key-12345"


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        # Seed an API key
        session.add(ApiKey(key_hash=_hash_key(TEST_KEY), label="test"))
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """HTTP test client with DB overridden to use the in-memory session."""
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def auth_headers():
    return {"X-API-Key": TEST_KEY}
