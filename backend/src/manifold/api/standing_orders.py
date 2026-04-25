from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_user_dek
from manifold.api.accounts import _account_or_404, _check_access
from manifold.api.deps import get_current_user, get_session
from manifold.models.standing_order import StandingOrder
from manifold.models.user import User
from manifold.schemas.accounts import StandingOrderResponse

router = APIRouter()


@router.get(
    "/accounts/{account_id}/standing-orders",
    operation_id="getAccountStandingOrders",
    response_model=list[StandingOrderResponse],
)
async def get_account_standing_orders(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[StandingOrderResponse]:
    account = await _account_or_404(session, account_id)
    await _check_access(current_user, session, str(account.user_id))

    async def _get() -> list[dict]:
        result = await session.execute(
            select(StandingOrder)
            .where(StandingOrder.account_id == account.id)
            .order_by(StandingOrder.created_at.desc())
        )
        return [
            {
                "id": str(item.id),
                "account_id": str(item.account_id),
                "provider_standing_order_id": item.provider_standing_order_id,
                "reference": item.reference,
                "status": item.status,
                "currency": item.currency,
                "frequency": item.frequency,
                "first_payment_date": item.first_payment_date,
                "first_payment_amount": str(item.first_payment_amount)
                if item.first_payment_amount is not None
                else None,
                "next_payment_date": item.next_payment_date,
                "next_payment_amount": str(item.next_payment_amount)
                if item.next_payment_amount is not None
                else None,
                "final_payment_date": item.final_payment_date,
                "final_payment_amount": str(item.final_payment_amount)
                if item.final_payment_amount is not None
                else None,
                "previous_payment_date": item.previous_payment_date,
                "previous_payment_amount": str(item.previous_payment_amount)
                if item.previous_payment_amount is not None
                else None,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, account.user_id, _get)

__all__ = ["router"]
