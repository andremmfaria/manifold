from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.exceptions import NotFoundError
from manifold.models.account import Account
from manifold.models.event import Event


class EventService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, event_id: str, user_ids: set[str]) -> Event:
        result = await self._session.execute(
            select(Event).where(Event.id == event_id, Event.user_id.in_(user_ids))
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise NotFoundError("Event", event_id)
        return event

    async def list_for_scope(self, user_ids: set[str]) -> list[Event]:
        result = await self._session.execute(
            select(Event)
            .where(Event.user_id.in_(user_ids))
            .order_by(Event.recorded_at.desc(), Event.occurred_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_account(self, account_id: str, user_ids: set[str]) -> list[Event]:
        result = await self._session.execute(
            select(Event)
            .join(Account, Event.account_id == Account.id)
            .where(Event.account_id == account_id, Account.user_id.in_(user_ids))
            .order_by(Event.recorded_at.desc(), Event.occurred_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["EventService"]
