from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseBackend(ABC):
    @property
    @abstractmethod
    def dialect_name(self) -> str: ...

    @abstractmethod
    def create_engine(self, url: str) -> AsyncEngine: ...

    @abstractmethod
    def upsert(
        self,
        table: Any,
        values: dict[str, Any],
        conflict_columns: list[str],
        update_values: dict[str, Any] | None = None,
    ) -> Any:
        """Build a dialect-specific upsert statement.

        *update_values* — if provided, only these key/value pairs are written
        in the conflict UPDATE path.  When absent, the entire *values* dict is
        used (legacy behaviour).  Pass a subset that excludes ``created_at`` to
        keep that column immutable across re-syncs (§13.1 guard).
        """
        ...
