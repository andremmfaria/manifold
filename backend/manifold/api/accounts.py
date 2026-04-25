from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.balance import Balance
from manifold.models.direct_debit import DirectDebit
from manifold.models.pending_transaction import PendingTransaction
from manifold.models.standing_order import StandingOrder
from manifold.models.transaction import Transaction
from manifold.models.user import User

router = APIRouter()


async def _account_or_404(session: AsyncSession, account_id: str) -> Account:
    result = await session.execute(
        select(Account.__table__.c.id, Account.__table__.c.user_id).where(
            Account.__table__.c.id == parse_uuid(account_id)
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _load() -> Account:
        account = await session.get(Account, parse_uuid(account_id))
        if account is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return account

    return await with_user_dek(session, row.user_id, _load)


async def _check_access(current_user: User, session: AsyncSession, user_id: str) -> None:
    scope = await get_accessible_scope(current_user, session)
    if user_id not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})


def _serialize_account(account: Account, current_balance: Balance | None) -> dict:
    return {
        "id": str(account.id),
        "user_id": str(account.user_id),
        "provider_connection_id": str(account.provider_connection_id),
        "provider_account_id": account.provider_account_id,
        "account_type": account.account_type,
        "currency": account.currency,
        "display_name": account.display_name,
        "iban": account.iban,
        "sort_code": account.sort_code,
        "account_number": account.account_number,
        "is_active": account.is_active,
        "current_balance": str(current_balance.current)
        if current_balance and current_balance.current is not None
        else None,
        "balance_currency": current_balance.currency if current_balance else None,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }


@router.get("")
async def list_accounts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    scope = await get_accessible_scope(current_user, session)
    from sqlalchemy import func
    total_result = await session.execute(
        select(func.count()).select_from(Account.__table__).where(
            Account.__table__.c.user_id.in_(scope_to_uuids(scope))
        )
    )
    total = total_result.scalar_one()
    result = await session.execute(
        select(Account.__table__.c.id, Account.__table__.c.user_id)
        .where(Account.__table__.c.user_id.in_(scope_to_uuids(scope)))
        .order_by(Account.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for account_id, owner_user_id in result.all():
        async def _serialize(aid: str = account_id, oid: str = owner_user_id) -> dict:
            account = await session.get(Account, aid)
            if account is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            balance_result = await session.execute(
                select(Balance)
                .where(Balance.account_id == account.id)
                .order_by(desc(Balance.recorded_at))
                .limit(1)
            )
            return _serialize_account(account, balance_result.scalar_one_or_none())

        items.append(await with_user_dek(session, owner_user_id, _serialize))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{account_id}")
async def get_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> dict:
        balance_result = await session.execute(
            select(Balance)
            .where(Balance.account_id == account.id)
            .order_by(desc(Balance.recorded_at))
            .limit(1)
        )
        return _serialize_account(account, balance_result.scalar_one_or_none())

    return await with_user_dek(session, account.user_id, _get)


@router.get("/{account_id}/balances")
async def get_account_balances(
    account_id: str,
    from_ts: str | None = Query(default=None, alias="from"),
    to_ts: str | None = Query(default=None, alias="to"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        stmt = select(Balance).where(Balance.account_id == account.id)
        if from_ts:
            stmt = stmt.where(Balance.recorded_at >= from_ts)
        if to_ts:
            stmt = stmt.where(Balance.recorded_at <= to_ts)
        result = await session.execute(stmt.order_by(Balance.recorded_at.desc()))
        return [
            {
                "id": str(item.id),
                "available": str(item.available) if item.available is not None else None,
                "current": str(item.current) if item.current is not None else None,
                "currency": item.currency,
                "overdraft": str(item.overdraft) if item.overdraft is not None else None,
                "credit_limit": str(item.credit_limit) if item.credit_limit is not None else None,
                "as_of": item.as_of.isoformat() if item.as_of else None,
                "recorded_at": item.recorded_at.isoformat(),
            }
                for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)


@router.get("/{account_id}/transactions")
async def get_account_transactions(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.account_id == account.id)
            .order_by(Transaction.created_at.desc())
        )
        return [
            {
                "id": str(item.id),
                "provider_transaction_id": item.provider_transaction_id,
                "status": item.status,
                "amount": str(item.amount) if item.amount is not None else None,
                "currency": item.currency,
                "transaction_type": item.transaction_type,
                "transaction_category": item.transaction_category,
                "description": item.description,
                "merchant_name": item.merchant_name,
                "merchant_category": item.merchant_category,
                "transaction_date": item.transaction_date,
                "settled_date": item.settled_date,
                "running_balance": str(item.running_balance)
                if item.running_balance is not None
                else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)


@router.get("/{account_id}/pending")
async def get_account_pending(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(PendingTransaction).where(PendingTransaction.account_id == account.id)
        )
        return [
            {
                "id": str(item.id),
                "provider_transaction_id": item.provider_transaction_id,
                "amount": str(item.amount) if item.amount is not None else None,
                "currency": item.currency,
                "description": item.description,
                "merchant_name": item.merchant_name,
                "transaction_date": item.transaction_date,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)


@router.get("/{account_id}/direct-debits")
async def get_account_direct_debits(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(DirectDebit).where(DirectDebit.account_id == account.id)
        )
        return [
            {
                "id": str(item.id),
                "provider_mandate_id": item.provider_mandate_id,
                "name": item.name,
                "status": item.status,
                "amount": str(item.amount) if item.amount is not None else None,
                "currency": item.currency,
                "frequency": item.frequency,
                "reference": item.reference,
                "last_payment_date": item.last_payment_date,
                "next_payment_date": item.next_payment_date,
                "next_payment_amount": str(item.next_payment_amount)
                if item.next_payment_amount is not None
                else None,
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)


@router.get("/{account_id}/standing-orders")
async def get_account_standing_orders(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(StandingOrder).where(StandingOrder.account_id == account.id)
        )
        return [
            {
                "id": str(item.id),
                "provider_standing_order_id": item.provider_standing_order_id,
                "reference": item.reference,
                "status": item.status,
                "currency": item.currency,
                "frequency": item.frequency,
                "next_payment_date": item.next_payment_date,
                "next_payment_amount": str(item.next_payment_amount)
                if item.next_payment_amount is not None
                else None,
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)
