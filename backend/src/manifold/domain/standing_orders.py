from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.exceptions import NotFoundError
from manifold.models.account import Account
from manifold.models.standing_order import StandingOrder


class StandingOrderService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, standing_order_id: str, user_ids: set[str]) -> StandingOrder:
        result = await self._session.execute(
            select(StandingOrder)
            .join(Account, StandingOrder.account_id == Account.id)
            .where(StandingOrder.id == standing_order_id, Account.user_id.in_(user_ids))
        )
        standing_order = result.scalar_one_or_none()
        if standing_order is None:
            raise NotFoundError("StandingOrder", standing_order_id)
        return standing_order

    async def list_for_account(self, account_id: str, user_ids: set[str]) -> list[StandingOrder]:
        result = await self._session.execute(
            select(StandingOrder)
            .join(Account, StandingOrder.account_id == Account.id)
            .where(StandingOrder.account_id == account_id, Account.user_id.in_(user_ids))
            .order_by(StandingOrder.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_scope(self, user_ids: set[str]) -> list[StandingOrder]:
        result = await self._session.execute(
            select(StandingOrder)
            .join(Account, StandingOrder.account_id == Account.id)
            .where(Account.user_id.in_(user_ids))
            .order_by(StandingOrder.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["StandingOrderService"]
