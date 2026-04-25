from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.alarm import AlarmDefinition, AlarmNotifierAssignment
from manifold.models.notification_delivery import NotificationDelivery
from manifold.models.notifier import NotifierConfig
from manifold.models.user import User
from manifold.notifiers.dispatcher import NotifierDispatcher
from manifold.notifiers.registry import registry
from manifold.schemas.notifiers import NotifierCreateRequest, NotifierUpdateRequest

router = APIRouter()
delivery_router = APIRouter()


def _forbid_superadmin(current_user: User) -> None:
    if current_user.role == "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _serialize_notifier(notifier: NotifierConfig) -> dict:
    return {
        "id": str(notifier.id),
        "user_id": str(notifier.user_id),
        "name": notifier.name,
        "type": notifier.type,
        "is_enabled": notifier.is_enabled,
        "config": notifier.config,
        "created_at": notifier.created_at.isoformat(),
        "updated_at": notifier.updated_at.isoformat(),
    }


def _serialize_delivery(item: NotificationDelivery) -> dict:
    return {
        "id": str(item.id),
        "alarm_firing_event_id": (
            str(item.alarm_firing_event_id) if item.alarm_firing_event_id else None
        ),
        "notifier_id": str(item.notifier_id) if item.notifier_id else None,
        "user_id": str(item.user_id) if item.user_id else None,
        "notification_type": item.notification_type,
        "status": item.status,
        "attempt_count": item.attempt_count,
        "rendered_subject": item.rendered_subject,
        "rendered_body": item.rendered_body,
        "request_payload": item.request_payload,
        "response_detail": item.response_detail,
        "error_message": item.error_message,
        "created_at": item.created_at.isoformat(),
        "first_attempted_at": (
            item.first_attempted_at.isoformat() if item.first_attempted_at else None
        ),
        "last_attempted_at": item.last_attempted_at.isoformat() if item.last_attempted_at else None,
        "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
    }


async def _notifier_owner_or_404(session: AsyncSession, notifier_id: str) -> str:
    result = await session.execute(
        select(NotifierConfig.__table__.c.user_id).where(
            NotifierConfig.__table__.c.id == parse_uuid(notifier_id)
        )
    )
    owner_user_id = result.scalar_one_or_none()
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return str(owner_user_id)


async def _check_scope(current_user: User, session: AsyncSession, owner_user_id: str) -> None:
    scope = await get_accessible_scope(current_user, session)
    if owner_user_id not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})


def _require_owner(current_user: User, owner_user_id: str) -> None:
    if str(current_user.id) != owner_user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _get_notifier_impl(notifier_type: str):
    try:
        return registry.get(notifier_type)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_notifier_type"}) from exc


@router.get("")
async def list_notifiers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    total_result = await session.execute(
        select(func.count()).select_from(NotifierConfig.__table__).where(
            NotifierConfig.__table__.c.user_id.in_(scope_to_uuids(scope))
        )
    )
    total = total_result.scalar_one()
    result = await session.execute(
        select(NotifierConfig.__table__.c.id, NotifierConfig.__table__.c.user_id)
        .where(NotifierConfig.__table__.c.user_id.in_(scope_to_uuids(scope)))
        .order_by(NotifierConfig.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for notifier_id, owner_user_id in result.all():
        async def _serialize() -> dict:
            notifier = await session.get(NotifierConfig, notifier_id)
            if notifier is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_notifier(notifier)

        items.append(await with_user_dek(session, str(owner_user_id), _serialize))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_notifier(
    payload: NotifierCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    notifier_impl = _get_notifier_impl(payload.type)
    errors = notifier_impl.validate_config(dict(payload.config or {}))
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_config", "fields": errors},
        )
    owner_user_id = str(current_user.id)

    async def _create() -> dict:
        notifier = NotifierConfig(
            user_id=owner_user_id,
            name=payload.name,
            type=payload.type,
            config=dict(payload.config or {}),
            is_enabled=payload.is_enabled,
        )
        session.add(notifier)
        await session.commit()
        await session.refresh(notifier)
        return _serialize_notifier(notifier)

    return await with_user_dek(session, owner_user_id, _create)


@router.get("/{notifier_id}")
async def get_notifier(
    notifier_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    owner_user_id = await _notifier_owner_or_404(session, notifier_id)
    await _check_scope(current_user, session, owner_user_id)

    async def _get() -> dict:
        notifier = await session.get(NotifierConfig, parse_uuid(notifier_id))
        if notifier is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return _serialize_notifier(notifier)

    return await with_user_dek(session, owner_user_id, _get)


@router.patch("/{notifier_id}")
async def update_notifier(
    notifier_id: str,
    payload: NotifierUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    owner_user_id = await _notifier_owner_or_404(session, notifier_id)
    await _check_scope(current_user, session, owner_user_id)
    _require_owner(current_user, owner_user_id)

    async def _update() -> dict:
        notifier = await session.get(NotifierConfig, parse_uuid(notifier_id))
        if notifier is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        next_config = (
            dict(payload.config)
            if payload.config is not None
            else dict(notifier.config or {})
        )
        errors = _get_notifier_impl(notifier.type).validate_config(next_config)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_config", "fields": errors},
            )
        if payload.name is not None:
            notifier.name = payload.name
        if payload.config is not None:
            notifier.config = next_config
        if payload.is_enabled is not None:
            notifier.is_enabled = payload.is_enabled
        await session.commit()
        await session.refresh(notifier)
        return _serialize_notifier(notifier)

    return await with_user_dek(session, owner_user_id, _update)


@router.delete("/{notifier_id}")
async def delete_notifier(
    notifier_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    owner_user_id = await _notifier_owner_or_404(session, notifier_id)
    await _check_scope(current_user, session, owner_user_id)
    _require_owner(current_user, owner_user_id)
    active_result = await session.execute(
        select(func.count())
        .select_from(AlarmNotifierAssignment)
        .join(AlarmDefinition, AlarmDefinition.id == AlarmNotifierAssignment.alarm_id)
        .where(
            AlarmNotifierAssignment.notifier_id == parse_uuid(notifier_id),
            AlarmDefinition.status == "active",
        )
    )
    if int(active_result.scalar_one()) > 0:
        raise HTTPException(
            status_code=409,
            detail={"error": "linked_to_active_alarms"},
        )

    async def _delete() -> dict:
        notifier = await session.get(NotifierConfig, parse_uuid(notifier_id))
        if notifier is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        await session.execute(
            delete(AlarmNotifierAssignment).where(
                AlarmNotifierAssignment.notifier_id == parse_uuid(notifier_id)
            )
        )
        await session.delete(notifier)
        await session.commit()
        return {"deleted": True}

    return await with_user_dek(session, owner_user_id, _delete)


@router.post("/{notifier_id}/test")
async def test_notifier(
    notifier_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    _forbid_superadmin(current_user)
    owner_user_id = await _notifier_owner_or_404(session, notifier_id)
    await _check_scope(current_user, session, owner_user_id)
    _require_owner(current_user, owner_user_id)
    dispatcher = NotifierDispatcher(session)
    return await dispatcher.dispatch_test(notifier_id, owner_user_id)


@router.get("/{notifier_id}/deliveries")
async def list_notifier_deliveries(
    notifier_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    owner_user_id = await _notifier_owner_or_404(session, notifier_id)
    await _check_scope(current_user, session, owner_user_id)

    async def _list() -> dict:
        total_result = await session.execute(
            select(func.count()).select_from(NotificationDelivery.__table__).where(
                NotificationDelivery.__table__.c.notifier_id == parse_uuid(notifier_id)
            )
        )
        total = total_result.scalar_one()
        result = await session.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.notifier_id == parse_uuid(notifier_id))
            .order_by(NotificationDelivery.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_serialize_delivery(item) for item in result.scalars().all()]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await with_user_dek(session, owner_user_id, _list)


@delivery_router.get("/notification-deliveries")
async def list_notification_deliveries(
    alarm_firing_event_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    stmt = select(
        NotificationDelivery.__table__.c.id,
        NotificationDelivery.__table__.c.user_id,
    ).where(NotificationDelivery.__table__.c.user_id.in_(scope_to_uuids(scope)))
    count_stmt = select(func.count()).select_from(NotificationDelivery.__table__).where(
        NotificationDelivery.__table__.c.user_id.in_(scope_to_uuids(scope))
    )
    if alarm_firing_event_id is not None:
        stmt = stmt.where(
            NotificationDelivery.__table__.c.alarm_firing_event_id
            == parse_uuid(alarm_firing_event_id)
        )
        count_stmt = count_stmt.where(
            NotificationDelivery.__table__.c.alarm_firing_event_id
            == parse_uuid(alarm_firing_event_id)
        )
    total_result = await session.execute(count_stmt)
    total = total_result.scalar_one()
    result = await session.execute(
        stmt.order_by(NotificationDelivery.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for delivery_id, owner_user_id in result.all():
        async def _serialize() -> dict:
            item = await session.get(NotificationDelivery, delivery_id)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_delivery(item)

        items.append(await with_user_dek(session, str(owner_user_id), _serialize))
    return {"items": items, "total": total, "page": page, "page_size": page_size}
