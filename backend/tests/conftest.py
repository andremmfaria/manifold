# ruff: noqa: E402, I001

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from taskiq import InMemoryBroker

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
TEST_SECRET_KEY = "test-secret-key-for-unit-tests-only-32chars"

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("ADMIN_USERNAME", "bootstrap-admin")
os.environ.setdefault("ADMIN_PASSWORD", "bootstrap-password")
os.environ.setdefault("SECRET_KEY", TEST_SECRET_KEY)
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("MANIFOLD_SECRET_KEY", TEST_SECRET_KEY)
os.environ.setdefault("MANIFOLD_DATABASE_URL", TEST_DATABASE_URL)

import manifold.models  # noqa: F401
from manifold.config import settings
from manifold.database import get_session
from manifold.domain.users import create_user_record
from manifold.main import create_app
from manifold.models import Base
from manifold.notifiers.registry import register_all
from manifold.tasks.broker import broker


@pytest.fixture(scope="session", autouse=True)
def set_test_env() -> None:
    settings.app_env = "development"
    settings.secret_key = TEST_SECRET_KEY
    settings.database_url = TEST_DATABASE_URL
    settings.admin_username = "bootstrap-admin"
    settings.admin_password = "bootstrap-password"


@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    app = create_app()
    register_all()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"user-agent": "pytest-httpx"},
    ) as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    user = await create_user_record(
        username="testuser",
        password="testpass123",
        role="regular",
        session=db_session,
        email="testuser@example.com",
    )
    return user, "testpass123"


@pytest_asyncio.fixture
async def superadmin_user(db_session: AsyncSession):
    user = await create_user_record(
        username="admin",
        password="adminpass123",
        role="superadmin",
        session=db_session,
        email="admin@example.com",
    )
    return user, "adminpass123"


@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession):
    user = await create_user_record(
        username="seconduser",
        password="secondpass123",
        role="regular",
        session=db_session,
        email="seconduser@example.com",
    )
    return user, "secondpass123"


@pytest.fixture(autouse=True)
def use_in_memory_broker() -> None:
    broker._broker = InMemoryBroker()
    broker.is_worker_process = True
    yield
    broker.is_worker_process = False
