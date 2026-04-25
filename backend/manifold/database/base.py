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
    def upsert(self, table: Any, values: dict[str, Any], conflict_columns: list[str]) -> Any: ...
