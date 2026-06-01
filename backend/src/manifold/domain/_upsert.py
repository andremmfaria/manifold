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
    update_values: dict[str, Any] | None = None,
):
    """Insert-or-update *model* and return the live row.

    *update_values* — if given, only these key/value pairs are written on
    conflict (instead of the full *values* dict).  Use to exclude immutable
    columns like ``created_at`` from the UPDATE path (§13.1 guard).
    """
    stmt = _backend.upsert(model.__table__, values, conflict_columns, update_values)
    await session.execute(stmt)
    await session.flush()
    criteria = lookup or {column: values[column] for column in conflict_columns}
    result = await session.execute(select(model).filter_by(**criteria))
    return result.scalar_one()


async def insert_row(session: AsyncSession, model: Any, values: dict[str, Any]):
    await session.execute(insert(model).values(**values))
    await session.flush()
