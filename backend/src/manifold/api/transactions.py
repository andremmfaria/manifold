from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import dek_context, get_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.transaction import Transaction
from manifold.models.user import User
from manifold.schemas.transactions import TransactionResponse

router = APIRouter()


def _serialize(transaction: Transaction, account: Account) -> dict:
    return {
        "id": str(transaction.id),
        "account_id": str(account.id),
        "card_id": str(transaction.card_id) if transaction.card_id else None,
        "account_display_name": account.display_name,
        "provider_transaction_id": transaction.provider_transaction_id,
        "status": transaction.status,
        "amount": str(transaction.amount) if transaction.amount is not None else None,
        "currency": transaction.currency,
        "transaction_type": transaction.transaction_type,
        "transaction_category": transaction.transaction_category,
        "description": transaction.description,
        "merchant_name": transaction.merchant_name,
        "merchant_category": transaction.merchant_category,
        "transaction_date": transaction.transaction_date,
        "settled_date": transaction.settled_date,
        "running_balance": str(transaction.running_balance)
        if transaction.running_balance is not None
        else None,
        "is_recurring_candidate": transaction.is_recurring_candidate,
        "recurrence_profile_id": transaction.recurrence_profile_id,
        "created_at": transaction.created_at.isoformat(),
        "updated_at": transaction.updated_at.isoformat(),
    }


@router.get("", operation_id="listTransactions", response_model=list[TransactionResponse])
async def list_transactions(
    account_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TransactionResponse]:
    scope = await get_accessible_scope(current_user, session)
    # Encrypted columns are decrypted during result fetch, so the per-user DEK must be set
    # BEFORE execute(). Each owner has a distinct DEK, so the query is run once per owner
    # within that owner's context, then results are merged and sorted globally.
    rows: list[tuple] = []
    for owner_id in scope:
        stmt = (
            select(Transaction, Account)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == owner_id)
        )
        if account_id:
            stmt = stmt.where(Account.id == account_id)
        if status:
            stmt = stmt.where(Transaction.status == status)
        dek = await get_user_dek(session, owner_id)
        with dek_context(dek):
            result = await session.execute(stmt.order_by(Transaction.created_at.desc()))
            for transaction, account in result.all():
                rows.append((transaction.created_at, _serialize(transaction, account)))
    rows.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in rows]
