from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.exceptions import NotFoundError
from manifold.models.account import Account


class AccountService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, account_id: str, user_ids: set[str]) -> Account:
        result = await self._session.execute(
            select(Account).where(Account.id == account_id, Account.user_id.in_(user_ids))
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise NotFoundError("Account", account_id)
        return account

    async def list_for_scope(
        self,
        user_ids: set[str],
        include_inactive: bool = False,
    ) -> list[Account]:
        stmt = select(Account).where(Account.user_id.in_(user_ids))
        if not include_inactive:
            stmt = stmt.where(Account.is_active.is_(True))
        result = await self._session.execute(stmt.order_by(Account.created_at.desc()))
        return list(result.scalars().all())


__all__ = ["AccountService"]
