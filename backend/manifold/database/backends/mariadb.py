from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from manifold.config import settings as _settings
from manifold.database.base import DatabaseBackend


class MariaDBBackend(DatabaseBackend):
    @property
    def dialect_name(self) -> str:
        return "mariadb"

    def create_engine(self, url: str) -> AsyncEngine:
        return create_async_engine(
            url,
            pool_size=_settings.db_pool_size,
            max_overflow=_settings.db_pool_max_overflow,
            pool_timeout=_settings.db_pool_timeout,
            pool_pre_ping=True,
        )

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        stmt = mysql_insert(table).values(**values)
        update_cols = {k: stmt.inserted[k] for k in values.keys() if k not in conflict_columns}
        return stmt.on_duplicate_key_update(**update_cols)
