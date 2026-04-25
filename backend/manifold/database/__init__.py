from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manifold.config import settings
from manifold.database.factory import DatabaseBackendFactory

_backend = DatabaseBackendFactory.create()
engine = _backend.create_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
