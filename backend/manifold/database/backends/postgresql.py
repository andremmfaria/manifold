from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from manifold.config import settings as _settings
from manifold.database.base import DatabaseBackend


class PostgreSQLBackend(DatabaseBackend):
    @property
    def dialect_name(self) -> str:
        return "postgresql"

    def create_engine(self, url: str) -> AsyncEngine:
        return create_async_engine(
            url,
            pool_size=_settings.db_pool_size,
            max_overflow=_settings.db_pool_max_overflow,
            pool_timeout=_settings.db_pool_timeout,
            pool_pre_ping=True,
        )

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(table).values(**values)
        return stmt.on_conflict_do_update(index_elements=conflict_columns, set_=values)
