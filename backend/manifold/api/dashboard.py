from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.alarm import AlarmDefinition
from manifold.models.event import Event
from manifold.models.provider_connection import ProviderConnection
from manifold.models.recurrence_profile import RecurrenceProfile
from manifold.models.sync_run import SyncRun
from manifold.models.user import User

router = APIRouter()


def _forbid_superadmin(current_user: User) -> None:
    if current_user.role == "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _serialize_recent_event(item: Event) -> dict:
    return {
        "event_type": item.event_type,
        "source_type": item.source_type,
        "account_id": str(item.account_id) if item.account_id else None,
        "occurred_at": item.occurred_at.isoformat(),
    }


def _serialize_upcoming_debit(item: RecurrenceProfile) -> dict:
    return {
        "profile_id": str(item.id),
        "label": item.label,
        "next_predicted_at": item.next_predicted_at.isoformat() if item.next_predicted_at else None,
        "amount_mean": str(item.amount_mean) if item.amount_mean is not None else None,
        "confidence": float(item.confidence) if item.confidence is not None else None,
    }


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    scoped_user_ids = scope_to_uuids(scope)

    accounts_total_result = await session.execute(
        select(func.count()).select_from(Account.__table__).where(
            Account.__table__.c.user_id.in_(scoped_user_ids)
        )
    )
    active_alarms_result = await session.execute(
        select(func.count()).select_from(AlarmDefinition.__table__).where(
            AlarmDefinition.__table__.c.user_id.in_(scoped_user_ids),
            AlarmDefinition.__table__.c.status == "active",
        )
    )
    last_sync_result = await session.execute(
        select(func.max(SyncRun.__table__.c.completed_at))
        .select_from(SyncRun.__table__)
        .join(
            ProviderConnection.__table__,
            SyncRun.__table__.c.provider_connection_id == ProviderConnection.__table__.c.id,
        )
        .where(ProviderConnection.__table__.c.user_id.in_(scoped_user_ids))
    )

    recent_events_result = await session.execute(
        select(Event.__table__.c.id, Event.__table__.c.user_id)
        .join(Account.__table__, Event.__table__.c.account_id == Account.__table__.c.id)
        .where(Account.__table__.c.user_id.in_(scoped_user_ids))
        .order_by(Event.__table__.c.occurred_at.desc(), Event.__table__.c.recorded_at.desc())
        .limit(5)
    )
    recent_events: list[dict] = []
    for event_id, owner_user_id in recent_events_result.all():
        async def _serialize(eid: str = str(event_id)) -> dict:
            item = await session.get(Event, eid)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_recent_event(item)

        recent_events.append(await with_user_dek(session, str(owner_user_id), _serialize))

    now = datetime.now(UTC)
    upcoming_cutoff = now + timedelta(days=7)
    upcoming_result = await session.execute(
        select(RecurrenceProfile.__table__.c.id, Account.__table__.c.user_id)
        .join(Account.__table__, RecurrenceProfile.__table__.c.account_id == Account.__table__.c.id)
        .where(
            Account.__table__.c.user_id.in_(scoped_user_ids),
            RecurrenceProfile.__table__.c.status == "active",
            RecurrenceProfile.__table__.c.next_predicted_at.is_not(None),
            RecurrenceProfile.__table__.c.next_predicted_at >= now,
            RecurrenceProfile.__table__.c.next_predicted_at <= upcoming_cutoff,
        )
        .order_by(RecurrenceProfile.__table__.c.next_predicted_at.asc())
    )
    upcoming_debits: list[dict] = []
    for profile_id, owner_user_id in upcoming_result.all():
        async def _serialize(pid: str = str(profile_id)) -> dict:
            item = await session.get(RecurrenceProfile, pid)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_upcoming_debit(item)

        upcoming_debits.append(await with_user_dek(session, str(owner_user_id), _serialize))

    last_sync_at = last_sync_result.scalar_one()
    return {
        "accounts_total": int(accounts_total_result.scalar_one()),
        "active_alarms_count": int(active_alarms_result.scalar_one()),
        "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
        "recent_events": recent_events,
        "upcoming_debits": upcoming_debits,
    }
