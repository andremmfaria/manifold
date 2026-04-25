from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.alarm import AlarmDefinition, AlarmFiringEvent
from manifold.models.notification_delivery import NotificationDelivery
from manifold.models.user import User

router = APIRouter()


def _forbid_superadmin(current_user: User) -> None:
    if current_user.role == "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _serialize_delivery(item: NotificationDelivery) -> dict:
    return {
        "id": str(item.id),
        "alarm_firing_event_id": (
            str(item.alarm_firing_event_id) if item.alarm_firing_event_id else None
        ),
        "notifier_id": str(item.notifier_id) if item.notifier_id else None,
        "notification_type": item.notification_type,
        "status": item.status,
        "attempt_count": item.attempt_count,
        "rendered_subject": item.rendered_subject,
        "rendered_body": item.rendered_body,
        "created_at": item.created_at.isoformat(),
        "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
        "error_message": item.error_message,
    }


def _base_stmt(scoped_user_ids: list[str]):
    return (
        select(
            NotificationDelivery.__table__.c.id,
            func.coalesce(
                AlarmDefinition.__table__.c.user_id,
                NotificationDelivery.__table__.c.user_id,
            ).label("owner_user_id"),
        )
        .select_from(NotificationDelivery.__table__)
        .outerjoin(
            AlarmFiringEvent.__table__,
            (
                NotificationDelivery.__table__.c.alarm_firing_event_id
                == AlarmFiringEvent.__table__.c.id
            ),
        )
        .outerjoin(
            AlarmDefinition.__table__,
            AlarmFiringEvent.__table__.c.alarm_id == AlarmDefinition.__table__.c.id,
        )
        .where(
            or_(
                AlarmDefinition.__table__.c.user_id.in_(scoped_user_ids),
                NotificationDelivery.__table__.c.user_id.in_(scoped_user_ids),
            )
        )
    )


@router.get("")
async def list_notification_deliveries(
    alarm_id: str | None = Query(default=None),
    notifier_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    scoped_user_ids = scope_to_uuids(scope)
    stmt = _base_stmt(scoped_user_ids)
    if alarm_id is not None:
        stmt = stmt.where(AlarmDefinition.__table__.c.id == parse_uuid(alarm_id))
    if notifier_id is not None:
        stmt = stmt.where(NotificationDelivery.__table__.c.notifier_id == parse_uuid(notifier_id))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    result = await session.execute(
        stmt.order_by(NotificationDelivery.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for delivery_id, owner_user_id in result.all():
        async def _serialize(did: str = str(delivery_id)) -> dict:
            item = await session.get(NotificationDelivery, did)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_delivery(item)

        if owner_user_id is None:
            continue
        items.append(await with_user_dek(session, str(owner_user_id), _serialize))
    return {
        "items": items,
        "total": int(total_result.scalar_one()),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{delivery_id}")
async def get_notification_delivery(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    scoped_user_ids = scope_to_uuids(scope)
    result = await session.execute(
        _base_stmt(scoped_user_ids).where(
            NotificationDelivery.__table__.c.id == parse_uuid(delivery_id)
        )
    )
    row = result.one_or_none()
    if row is None or row.owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _get() -> dict:
        item = await session.get(NotificationDelivery, parse_uuid(delivery_id))
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return _serialize_delivery(item)

    return await with_user_dek(session, str(row.owner_user_id), _get)
