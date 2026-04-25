from manifold.config import settings
from manifold.database.backends.mariadb import MariaDBBackend
from manifold.database.backends.postgresql import PostgreSQLBackend
from manifold.database.backends.sqlite import SQLiteBackend
from manifold.database.base import DatabaseBackend

_BACKENDS: dict[str, type[DatabaseBackend]] = {
    "sqlite": SQLiteBackend,
    "postgresql": PostgreSQLBackend,
    "mysql": MariaDBBackend,
}


class DatabaseBackendFactory:
    @staticmethod
    def create(database_url: str | None = None) -> DatabaseBackend:
        url = database_url or settings.database_url
        scheme = url.split("+")[0].split(":")[0]
        backend_cls = _BACKENDS.get(scheme)
        if backend_cls is None:
            supported = ", ".join(_BACKENDS)
            raise ValueError(
                f"Unsupported database scheme '{scheme}' in DATABASE_URL. Supported: {supported}"
            )
        return backend_cls()
