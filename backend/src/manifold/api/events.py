from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.event import Event
from manifold.models.user import User
from manifold.schemas.events import EventResponse

router = APIRouter()


@router.get("/events", operation_id="listEvents", response_model=list[EventResponse])
async def list_events(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[EventResponse]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(Event.__table__.c.id, Event.__table__.c.user_id)
        .where(Event.__table__.c.user_id.in_(scope_to_uuids(scope)))
        .order_by(Event.__table__.c.recorded_at.desc())
    )
    items: list[dict] = []
    for event_id, owner_user_id in result.all():
        async def _serialize() -> dict:
            item = await session.get(Event, event_id)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return {
                "id": str(item.id),
                "event_type": item.event_type,
                "source_type": item.source_type,
                "confidence": float(item.confidence) if item.confidence is not None else None,
                "account_id": str(item.account_id) if item.account_id else None,
                "user_id": str(item.user_id),
                "payload": item.payload,
                "occurred_at": item.occurred_at.isoformat(),
                "recorded_at": item.recorded_at.isoformat(),
                "explanation": item.explanation,
            }

        items.append(await with_user_dek(session, owner_user_id, _serialize))
    return items


@router.get("/events/{event_id}", operation_id="getEvent", response_model=EventResponse)
async def get_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventResponse:
    result = await session.execute(
        select(Event.__table__.c.user_id).where(Event.__table__.c.id == parse_uuid(event_id))
    )
    owner_user_id = result.scalar_one_or_none()
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    scope = await get_accessible_scope(current_user, session)
    if str(owner_user_id) not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _get() -> dict:
        item = await session.get(Event, parse_uuid(event_id))
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return {
            "id": str(item.id),
            "event_type": item.event_type,
            "source_type": item.source_type,
            "confidence": float(item.confidence) if item.confidence is not None else None,
            "account_id": str(item.account_id) if item.account_id else None,
            "user_id": str(item.user_id),
            "payload": item.payload,
            "occurred_at": item.occurred_at.isoformat(),
            "recorded_at": item.recorded_at.isoformat(),
            "explanation": item.explanation,
        }

    return await with_user_dek(session, owner_user_id, _get)
