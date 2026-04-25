from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_user_dek
from manifold.api.accounts import _account_or_404, _check_access
from manifold.api.deps import get_current_user, get_session
from manifold.models.direct_debit import DirectDebit
from manifold.models.user import User
from manifold.schemas.accounts import DirectDebitResponse

router = APIRouter()


@router.get(
    "/accounts/{account_id}/direct-debits",
    operation_id="getAccountDirectDebits",
    response_model=list[DirectDebitResponse],
)
async def get_account_direct_debits(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DirectDebitResponse]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(DirectDebit)
            .where(DirectDebit.account_id == account.id)
            .order_by(DirectDebit.created_at.desc())
        )
        return [
            {
                "id": str(item.id),
                "account_id": str(item.account_id),
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
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)

__all__ = ["router"]
