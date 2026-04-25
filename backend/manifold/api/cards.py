from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.balance import Balance
from manifold.models.card import Card
from manifold.models.provider_connection import ProviderConnection
from manifold.models.transaction import Transaction
from manifold.models.user import User

router = APIRouter()


@router.get("")
async def list_cards(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[dict]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(Card.__table__.c.id, ProviderConnection.__table__.c.user_id)
        .select_from(
            Card.__table__.join(
                ProviderConnection.__table__,
                Card.__table__.c.provider_connection_id == ProviderConnection.__table__.c.id,
            )
        )
        .where(ProviderConnection.__table__.c.user_id.in_(scope_to_uuids(scope)))
    )
    items: list[dict] = []
    for card_id, owner_user_id in result.all():
        async def _serialize() -> dict:
            card = await session.get(Card, card_id)
            if card is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return {
                "id": str(card.id),
                "provider_card_id": card.provider_card_id,
                "display_name": card.display_name,
                "card_network": card.card_network,
                "partial_card_number": card.partial_card_number,
                "currency": card.currency,
                "credit_limit": str(card.credit_limit) if card.credit_limit is not None else None,
            }

        items.append(await with_user_dek(session, owner_user_id, _serialize))
    return items


async def _card_scope_row(session: AsyncSession, card_id: str):
    result = await session.execute(
        select(Card.__table__.c.id, ProviderConnection.__table__.c.user_id)
        .select_from(
            Card.__table__.join(
                ProviderConnection.__table__,
                Card.__table__.c.provider_connection_id == ProviderConnection.__table__.c.id,
            )
        )
        .where(Card.__table__.c.id == parse_uuid(card_id))
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _load() -> Card:
        card = await session.get(Card, parse_uuid(card_id))
        if card is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return card

    card: Card = await with_user_dek(session, row.user_id, _load)
    return card, row.user_id


@router.get("/{card_id}")
async def get_card(
    card_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    card, owner_user_id = await _card_scope_row(session, card_id)
    scope = await get_accessible_scope(current_user, session)
    if str(owner_user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    async def _get() -> dict:
        return {
            "id": str(card.id),
            "provider_card_id": card.provider_card_id,
            "display_name": card.display_name,
            "card_network": card.card_network,
            "partial_card_number": card.partial_card_number,
            "currency": card.currency,
            "credit_limit": str(card.credit_limit) if card.credit_limit is not None else None,
        }

    return await with_user_dek(session, owner_user_id, _get)


@router.get("/{card_id}/balances")
async def get_card_balances(
    card_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    card, owner_user_id = await _card_scope_row(session, card_id)
    scope = await get_accessible_scope(current_user, session)
    if str(owner_user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    async def _get() -> list[dict]:
        result = await session.execute(
            select(Balance).where(Balance.card_id == card.id).order_by(desc(Balance.recorded_at))
        )
        return [
            {
                "id": str(item.id),
                "available": str(item.available) if item.available is not None else None,
                "current": str(item.current) if item.current is not None else None,
                "currency": item.currency,
                "recorded_at": item.recorded_at.isoformat(),
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, owner_user_id, _get)


@router.get("/{card_id}/transactions")
async def get_card_transactions(
    card_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    card, owner_user_id = await _card_scope_row(session, card_id)
    scope = await get_accessible_scope(current_user, session)
    if str(owner_user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    async def _get() -> list[dict]:
        result = await session.execute(select(Transaction).where(Transaction.card_id == card.id))
        return [
            {
                "id": str(item.id),
                "provider_transaction_id": item.provider_transaction_id,
                "amount": str(item.amount) if item.amount is not None else None,
                "currency": item.currency,
                "description": item.description,
                "transaction_date": item.transaction_date,
            }
            for item in result.scalars().all()
        ]

    return await with_user_dek(session, owner_user_id, _get)
