from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session, require_superadmin
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.alarm import (
    AlarmAccountAssignment,
    AlarmDefinition,
    AlarmDefinitionVersion,
    AlarmEvaluationResult,
    AlarmFiringEvent,
    AlarmNotifierAssignment,
    AlarmState,
)
from manifold.models.notifier import NotifierConfig
from manifold.models.user import User
from manifold.schemas.alarms import (
    AlarmCreateRequest,
    AlarmEvaluationHistoryResponse,
    AlarmFiringEventResponse,
    AlarmListResponse,
    AlarmResponse,
    AlarmUpdateRequest,
    MuteRequest,
)
from manifold.schemas.common import StatusResponse
from manifold.tasks.alarms import evaluate_all_alarms

router = APIRouter()

VALID_ALARM_STATUSES = {"active", "paused", "archived"}


def _forbid_superadmin(current_user: User) -> None:
    if current_user.role == "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _dedupe_ids(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _serialize_alarm(
    alarm: AlarmDefinition,
    state: AlarmState | None,
    account_ids: list[str],
    notifier_ids: list[str],
) -> dict:
    return {
        "id": str(alarm.id),
        "user_id": str(alarm.user_id),
        "name": alarm.name,
        "condition": alarm.condition,
        "condition_version": alarm.condition_version,
        "status": alarm.status,
        "repeat_count": alarm.repeat_count,
        "for_duration_minutes": alarm.for_duration_minutes,
        "cooldown_minutes": alarm.cooldown_minutes,
        "notify_on_resolve": alarm.notify_on_resolve,
        "account_ids": account_ids,
        "notifier_ids": notifier_ids,
        "state": state.state if state else "ok",
        "mute_until": state.mute_until.isoformat() if state and state.mute_until else None,
        "last_evaluated_at": state.last_evaluated_at.isoformat()
        if state and state.last_evaluated_at
        else None,
        "last_fired_at": state.last_fired_at.isoformat() if state and state.last_fired_at else None,
        "created_at": alarm.created_at.isoformat(),
        "updated_at": alarm.updated_at.isoformat(),
    }


async def _alarm_or_404(session: AsyncSession, alarm_id: str) -> tuple[AlarmDefinition, str]:
    result = await session.execute(
        select(AlarmDefinition.__table__.c.id, AlarmDefinition.__table__.c.user_id).where(
            AlarmDefinition.__table__.c.id == parse_uuid(alarm_id)
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    async def _load() -> AlarmDefinition:
        alarm = await session.get(AlarmDefinition, parse_uuid(alarm_id))
        if alarm is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return alarm

    owner_user_id = str(row.user_id)
    alarm = await with_user_dek(session, owner_user_id, _load)
    return alarm, owner_user_id


async def _check_access(current_user: User, session: AsyncSession, owner_user_id: str) -> None:
    scope = await get_accessible_scope(current_user, session)
    if owner_user_id not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})


async def _load_alarm_state(session: AsyncSession, alarm_id: str) -> AlarmState | None:
    result = await session.execute(select(AlarmState).where(AlarmState.alarm_id == alarm_id))
    return result.scalar_one_or_none()


async def _load_alarm_account_ids(session: AsyncSession, alarm_id: str) -> list[str]:
    result = await session.execute(
        select(AlarmAccountAssignment.account_id)
        .where(AlarmAccountAssignment.alarm_id == alarm_id)
        .order_by(AlarmAccountAssignment.created_at.asc())
    )
    return [str(item) for item in result.scalars().all()]


async def _load_alarm_notifier_ids(session: AsyncSession, alarm_id: str) -> list[str]:
    result = await session.execute(
        select(AlarmNotifierAssignment.notifier_id)
        .where(AlarmNotifierAssignment.alarm_id == alarm_id)
        .order_by(AlarmNotifierAssignment.created_at.asc())
    )
    return [str(item) for item in result.scalars().all()]


async def _validate_account_ids(
    session: AsyncSession, owner_user_id: str, account_ids: list[str]
) -> list[str]:
    normalized_ids = _dedupe_ids(account_ids)
    if len(normalized_ids) == 0:
        raise HTTPException(status_code=422, detail={"error": "account_ids_required"})

    result = await session.execute(
        select(Account.__table__.c.id).where(
            Account.__table__.c.id.in_([parse_uuid(item) for item in normalized_ids]),
            Account.__table__.c.user_id == parse_uuid(owner_user_id),
        )
    )
    found = {str(item) for item in result.scalars().all()}
    if found != set(normalized_ids):
        raise HTTPException(status_code=422, detail={"error": "invalid_account_ids"})
    return normalized_ids


async def _validate_notifier_ids(
    session: AsyncSession, owner_user_id: str, notifier_ids: list[str]
) -> list[str]:
    normalized_ids = _dedupe_ids(notifier_ids)
    if len(normalized_ids) == 0:
        return []

    result = await session.execute(
        select(NotifierConfig.__table__.c.id).where(
            NotifierConfig.__table__.c.id.in_([parse_uuid(item) for item in normalized_ids]),
            NotifierConfig.__table__.c.user_id == parse_uuid(owner_user_id),
        )
    )
    found = {str(item) for item in result.scalars().all()}
    if found != set(normalized_ids):
        raise HTTPException(status_code=422, detail={"error": "invalid_notifier_ids"})
    return normalized_ids


async def _replace_account_assignments(
    session: AsyncSession, alarm_id: str, account_ids: list[str]
) -> None:
    await session.execute(
        delete(AlarmAccountAssignment).where(AlarmAccountAssignment.alarm_id == alarm_id)
    )
    session.add_all(
        [
            AlarmAccountAssignment(alarm_id=alarm_id, account_id=parse_uuid(account_id))
            for account_id in account_ids
        ]
    )


async def _replace_notifier_assignments(
    session: AsyncSession, alarm_id: str, notifier_ids: list[str]
) -> None:
    await session.execute(
        delete(AlarmNotifierAssignment).where(AlarmNotifierAssignment.alarm_id == alarm_id)
    )
    session.add_all(
        [
            AlarmNotifierAssignment(alarm_id=alarm_id, notifier_id=parse_uuid(notifier_id))
            for notifier_id in notifier_ids
        ]
    )


def _parse_mute_until(value: str) -> datetime:
    try:
        mute_until = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_mute_until"}) from exc
    if mute_until.tzinfo is None:
        raise HTTPException(status_code=422, detail={"error": "invalid_mute_until"})
    return mute_until.astimezone(UTC)


@router.post(
    "/evaluate",
    operation_id="evaluateAlarmsNow",
    response_model=StatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def evaluate_alarms_now(_: User = Depends(require_superadmin)) -> StatusResponse:
    await evaluate_all_alarms.kiq()
    return {"status": "queued"}


@router.get("", operation_id="listAlarms", response_model=AlarmListResponse)
async def list_alarms(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmListResponse:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    total_result = await session.execute(
        select(func.count()).select_from(AlarmDefinition.__table__).where(
            AlarmDefinition.__table__.c.user_id.in_(scope_to_uuids(scope))
        )
    )
    total = total_result.scalar_one()
    result = await session.execute(
        select(AlarmDefinition.__table__.c.id, AlarmDefinition.__table__.c.user_id)
        .where(AlarmDefinition.__table__.c.user_id.in_(scope_to_uuids(scope)))
        .order_by(AlarmDefinition.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for alarm_id, owner_user_id in result.all():
        async def _serialize(aid: str = str(alarm_id)) -> dict:
            alarm = await session.get(AlarmDefinition, parse_uuid(aid))
            if alarm is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            state = await _load_alarm_state(session, str(alarm.id))
            account_ids = await _load_alarm_account_ids(session, str(alarm.id))
            notifier_ids = await _load_alarm_notifier_ids(session, str(alarm.id))
            return _serialize_alarm(alarm, state, account_ids, notifier_ids)

        items.append(await with_user_dek(session, str(owner_user_id), _serialize))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post(
    "",
    operation_id="createAlarm",
    response_model=AlarmResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alarm(
    payload: AlarmCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    owner_user_id = str(current_user.id)
    account_ids = await _validate_account_ids(session, owner_user_id, payload.account_ids)
    notifier_ids = await _validate_notifier_ids(session, owner_user_id, payload.notifier_ids)

    async def _create() -> dict:
        alarm = AlarmDefinition(
            user_id=owner_user_id,
            name=payload.name,
            condition=payload.condition,
            repeat_count=payload.repeat_count,
            for_duration_minutes=payload.for_duration_minutes,
            cooldown_minutes=payload.cooldown_minutes,
            notify_on_resolve=payload.notify_on_resolve,
        )
        session.add(alarm)
        await session.flush()
        session.add(AlarmState(alarm_id=str(alarm.id), state="ok"))
        await _replace_account_assignments(session, str(alarm.id), account_ids)
        await _replace_notifier_assignments(session, str(alarm.id), notifier_ids)
        await session.commit()
        await session.refresh(alarm)
        state = await _load_alarm_state(session, str(alarm.id))
        return _serialize_alarm(alarm, state, account_ids, notifier_ids)

    return await with_user_dek(session, owner_user_id, _create)


@router.get("/{alarm_id}", operation_id="getAlarm", response_model=AlarmResponse)
async def get_alarm(
    alarm_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)

    async def _get() -> dict:
        state = await _load_alarm_state(session, str(alarm.id))
        account_ids = await _load_alarm_account_ids(session, str(alarm.id))
        notifier_ids = await _load_alarm_notifier_ids(session, str(alarm.id))
        return _serialize_alarm(alarm, state, account_ids, notifier_ids)

    return await with_user_dek(session, owner_user_id, _get)


@router.patch("/{alarm_id}", operation_id="updateAlarm", response_model=AlarmResponse)
async def update_alarm(
    alarm_id: str,
    payload: AlarmUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)
    account_ids = (
        await _validate_account_ids(session, owner_user_id, payload.account_ids)
        if payload.account_ids is not None
        else None
    )
    notifier_ids = (
        await _validate_notifier_ids(session, owner_user_id, payload.notifier_ids)
        if payload.notifier_ids is not None
        else None
    )
    if payload.status is not None and payload.status not in VALID_ALARM_STATUSES:
        raise HTTPException(status_code=422, detail={"error": "invalid_status"})

    async def _update() -> dict:
        if payload.name is not None:
            alarm.name = payload.name
        if payload.condition is not None:
            if payload.condition != alarm.condition:
                session.add(
                    AlarmDefinitionVersion(
                        alarm_definition_id=str(alarm.id),
                        version=alarm.condition_version,
                        condition=alarm.condition,
                    )
                )
                alarm.condition = payload.condition
                alarm.condition_version += 1
            else:
                alarm.condition = payload.condition
        if payload.repeat_count is not None:
            alarm.repeat_count = payload.repeat_count
        if payload.for_duration_minutes is not None:
            alarm.for_duration_minutes = payload.for_duration_minutes
        if payload.cooldown_minutes is not None:
            alarm.cooldown_minutes = payload.cooldown_minutes
        if payload.notify_on_resolve is not None:
            alarm.notify_on_resolve = payload.notify_on_resolve
        if payload.status is not None:
            alarm.status = payload.status
        if account_ids is not None:
            await _replace_account_assignments(session, str(alarm.id), account_ids)
        if notifier_ids is not None:
            await _replace_notifier_assignments(session, str(alarm.id), notifier_ids)
        await session.commit()
        await session.refresh(alarm)
        state = await _load_alarm_state(session, str(alarm.id))
        resolved_account_ids = (
            account_ids or await _load_alarm_account_ids(session, str(alarm.id))
        )
        resolved_notifier_ids = (
            notifier_ids or await _load_alarm_notifier_ids(session, str(alarm.id))
        )
        return _serialize_alarm(alarm, state, resolved_account_ids, resolved_notifier_ids)

    return await with_user_dek(session, owner_user_id, _update)


@router.delete("/{alarm_id}", operation_id="deleteAlarm", response_model=AlarmResponse)
async def delete_alarm(
    alarm_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)

    async def _delete() -> dict:
        alarm.status = "archived"
        await session.commit()
        await session.refresh(alarm)
        state = await _load_alarm_state(session, str(alarm.id))
        account_ids = await _load_alarm_account_ids(session, str(alarm.id))
        notifier_ids = await _load_alarm_notifier_ids(session, str(alarm.id))
        return _serialize_alarm(alarm, state, account_ids, notifier_ids)

    return await with_user_dek(session, owner_user_id, _delete)


@router.post("/{alarm_id}/mute", operation_id="muteAlarm", response_model=AlarmResponse)
async def mute_alarm(
    alarm_id: str,
    payload: MuteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)
    mute_until = _parse_mute_until(payload.mute_until)

    async def _mute() -> dict:
        state = await _load_alarm_state(session, str(alarm.id))
        if state is None:
            state = AlarmState(alarm_id=str(alarm.id), state="ok")
            session.add(state)
            await session.flush()
        state.state = "muted"
        state.mute_until = mute_until
        await session.commit()
        await session.refresh(alarm)
        await session.refresh(state)
        account_ids = await _load_alarm_account_ids(session, str(alarm.id))
        notifier_ids = await _load_alarm_notifier_ids(session, str(alarm.id))
        return _serialize_alarm(alarm, state, account_ids, notifier_ids)

    return await with_user_dek(session, owner_user_id, _mute)


@router.post(
    "/{alarm_id}/unmute",
    operation_id="unmuteAlarm",
    response_model=AlarmResponse,
)
async def unmute_alarm(
    alarm_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmResponse:
    _forbid_superadmin(current_user)
    alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)

    async def _unmute() -> dict:
        state = await _load_alarm_state(session, str(alarm.id))
        if state is None:
            state = AlarmState(alarm_id=str(alarm.id), state="ok")
            session.add(state)
            await session.flush()
        state.state = "ok"
        state.mute_until = None
        await session.commit()
        await session.refresh(alarm)
        await session.refresh(state)
        account_ids = await _load_alarm_account_ids(session, str(alarm.id))
        notifier_ids = await _load_alarm_notifier_ids(session, str(alarm.id))
        return _serialize_alarm(alarm, state, account_ids, notifier_ids)

    return await with_user_dek(session, owner_user_id, _unmute)


@router.get(
    "/{alarm_id}/history",
    operation_id="getAlarmHistory",
    response_model=AlarmEvaluationHistoryResponse,
)
async def get_alarm_history(
    alarm_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmEvaluationHistoryResponse:
    _forbid_superadmin(current_user)
    _alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)

    async def _history() -> dict:
        total_result = await session.execute(
            select(func.count()).select_from(AlarmEvaluationResult.__table__).where(
                AlarmEvaluationResult.__table__.c.alarm_id == parse_uuid(alarm_id)
            )
        )
        total = total_result.scalar_one()
        result = await session.execute(
            select(AlarmEvaluationResult)
            .where(AlarmEvaluationResult.alarm_id == parse_uuid(alarm_id))
            .order_by(
                AlarmEvaluationResult.evaluated_at.desc(),
                AlarmEvaluationResult.created_at.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            {
                "id": str(item.id),
                "evaluated_at": item.evaluated_at.isoformat(),
                "result": item.result,
                "previous_state": item.previous_state,
                "new_state": item.new_state,
                "explanation": item.explanation,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.scalars().all()
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await with_user_dek(session, owner_user_id, _history)


@router.get(
    "/{alarm_id}/firings",
    operation_id="getAlarmFirings",
    response_model=AlarmFiringEventResponse,
)
async def get_alarm_firings(
    alarm_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AlarmFiringEventResponse:
    _forbid_superadmin(current_user)
    _alarm, owner_user_id = await _alarm_or_404(session, alarm_id)
    await _check_access(current_user, session, owner_user_id)

    async def _firings() -> dict:
        total_result = await session.execute(
            select(func.count()).select_from(AlarmFiringEvent.__table__).where(
                AlarmFiringEvent.__table__.c.alarm_id == parse_uuid(alarm_id)
            )
        )
        total = total_result.scalar_one()
        result = await session.execute(
            select(AlarmFiringEvent)
            .where(AlarmFiringEvent.alarm_id == parse_uuid(alarm_id))
            .order_by(AlarmFiringEvent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            {
                "id": str(item.id),
                "alarm_id": str(item.alarm_id),
                "fired_at": item.fired_at.isoformat() if item.fired_at else None,
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
                "explanation": item.explanation,
                "notifications_sent": item.notifications_sent,
                "created_at": item.created_at.isoformat(),
            }
            for item in result.scalars().all()
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await with_user_dek(session, owner_user_id, _firings)
