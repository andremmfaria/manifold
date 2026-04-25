from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.exceptions import NotFoundError
from manifold.models.account import Account
from manifold.models.direct_debit import DirectDebit


class DirectDebitService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, direct_debit_id: str, user_ids: set[str]) -> DirectDebit:
        result = await self._session.execute(
            select(DirectDebit)
            .join(Account, DirectDebit.account_id == Account.id)
            .where(DirectDebit.id == direct_debit_id, Account.user_id.in_(user_ids))
        )
        direct_debit = result.scalar_one_or_none()
        if direct_debit is None:
            raise NotFoundError("DirectDebit", direct_debit_id)
        return direct_debit

    async def list_for_account(self, account_id: str, user_ids: set[str]) -> list[DirectDebit]:
        result = await self._session.execute(
            select(DirectDebit)
            .join(Account, DirectDebit.account_id == Account.id)
            .where(DirectDebit.account_id == account_id, Account.user_id.in_(user_ids))
            .order_by(DirectDebit.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_scope(self, user_ids: set[str]) -> list[DirectDebit]:
        result = await self._session.execute(
            select(DirectDebit)
            .join(Account, DirectDebit.account_id == Account.id)
            .where(Account.user_id.in_(user_ids))
            .order_by(DirectDebit.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["DirectDebitService"]
