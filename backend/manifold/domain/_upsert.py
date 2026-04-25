from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.database import _backend


async def upsert_and_fetch(
    session: AsyncSession,
    model: Any,
    values: dict[str, Any],
    conflict_columns: list[str],
    lookup: dict[str, Any] | None = None,
):
    stmt = _backend.upsert(model.__table__, values, conflict_columns)
    await session.execute(stmt)
    await session.flush()
    criteria = lookup or {column: values[column] for column in conflict_columns}
    result = await session.execute(select(model).filter_by(**criteria))
    return result.scalar_one()


async def insert_row(session: AsyncSession, model: Any, values: dict[str, Any]):
    await session.execute(insert(model).values(**values))
    await session.flush()
