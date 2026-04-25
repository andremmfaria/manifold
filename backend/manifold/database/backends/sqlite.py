from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, StaticPool

from manifold.database.base import DatabaseBackend


class SQLiteBackend(DatabaseBackend):
    @property
    def dialect_name(self) -> str:
        return "sqlite"

    def create_engine(self, url: str) -> AsyncEngine:
        poolclass = StaticPool if ":memory:" in url else NullPool
        engine = create_async_engine(
            url,
            poolclass=poolclass,
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine.sync_engine, "connect")
        def _on_connect(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA synchronous=NORMAL")
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine

    def upsert(self, table, values: dict, conflict_columns: list[str]):
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(table).values(**values)
        return stmt.on_conflict_do_update(index_elements=conflict_columns, set_=values)
