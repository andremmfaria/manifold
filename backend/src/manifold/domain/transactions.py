from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.exceptions import NotFoundError
from manifold.models.account import Account
from manifold.models.transaction import Transaction


class TransactionService:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, transaction_id: str, user_ids: set[str]) -> Transaction:
        result = await self._session.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Transaction.id == transaction_id, Account.user_id.in_(user_ids))
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            raise NotFoundError("Transaction", transaction_id)
        return transaction

    async def list_for_account(self, account_id: str, user_ids: set[str]) -> list[Transaction]:
        result = await self._session.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Transaction.account_id == account_id, Account.user_id.in_(user_ids))
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_scope(self, user_ids: set[str]) -> list[Transaction]:
        result = await self._session.execute(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id.in_(user_ids))
            .order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all())


__all__ = ["TransactionService"]
