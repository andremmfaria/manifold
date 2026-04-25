from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import parse_uuid, scope_to_uuids, with_user_dek
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.account import Account
from manifold.models.recurrence_profile import RecurrenceProfile
from manifold.models.user import User
from manifold.schemas.recurrence_profiles import (
    RecurrenceProfileListResponse,
    RecurrenceProfileResponse,
)

router = APIRouter()


def _forbid_superadmin(current_user: User) -> None:
    if current_user.role == "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})


def _serialize_profile(item: RecurrenceProfile) -> dict:
    return {
        "id": str(item.id),
        "account_id": str(item.account_id),
        "label": item.label,
        "merchant_pattern": item.merchant_pattern,
        "amount_mean": str(item.amount_mean) if item.amount_mean is not None else None,
        "amount_stddev": str(item.amount_stddev) if item.amount_stddev is not None else None,
        "cadence_days": item.cadence_days,
        "cadence_stddev": float(item.cadence_stddev) if item.cadence_stddev is not None else None,
        "confidence": float(item.confidence) if item.confidence is not None else None,
        "first_seen": item.first_seen.isoformat() if item.first_seen else None,
        "last_seen": item.last_seen.isoformat() if item.last_seen else None,
        "next_predicted_amount": (
            str(item.next_predicted_amount) if item.next_predicted_amount is not None else None
        ),
        "status": item.status,
        "next_predicted_at": item.next_predicted_at.isoformat() if item.next_predicted_at else None,
        "data_source": item.data_source,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


async def _profile_owner_or_404(session: AsyncSession, profile_id: str) -> str:
    result = await session.execute(
        select(Account.__table__.c.user_id)
        .select_from(RecurrenceProfile.__table__)
        .join(Account.__table__, RecurrenceProfile.__table__.c.account_id == Account.__table__.c.id)
        .where(RecurrenceProfile.__table__.c.id == parse_uuid(profile_id))
    )
    owner_user_id = result.scalar_one_or_none()
    if owner_user_id is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return str(owner_user_id)


async def _check_scope(current_user: User, session: AsyncSession, owner_user_id: str) -> None:
    scope = await get_accessible_scope(current_user, session)
    if owner_user_id not in scope:
        raise HTTPException(status_code=404, detail={"error": "not_found"})


@router.get(
    "",
    operation_id="listRecurrenceProfiles",
    response_model=RecurrenceProfileListResponse,
)
async def list_recurrence_profiles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecurrenceProfileListResponse:
    _forbid_superadmin(current_user)
    scope = await get_accessible_scope(current_user, session)
    scoped_user_ids = scope_to_uuids(scope)
    total_result = await session.execute(
        select(func.count())
        .select_from(RecurrenceProfile.__table__)
        .join(Account.__table__, RecurrenceProfile.__table__.c.account_id == Account.__table__.c.id)
        .where(Account.__table__.c.user_id.in_(scoped_user_ids))
    )
    result = await session.execute(
        select(RecurrenceProfile.__table__.c.id, Account.__table__.c.user_id)
        .join(Account.__table__, RecurrenceProfile.__table__.c.account_id == Account.__table__.c.id)
        .where(Account.__table__.c.user_id.in_(scoped_user_ids))
        .order_by(RecurrenceProfile.__table__.c.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items: list[dict] = []
    for profile_id, owner_user_id in result.all():
        async def _serialize(pid: str = str(profile_id)) -> dict:
            item = await session.get(RecurrenceProfile, pid)
            if item is None:
                raise HTTPException(status_code=404, detail={"error": "not_found"})
            return _serialize_profile(item)

        items.append(await with_user_dek(session, str(owner_user_id), _serialize))
    return {
        "items": items,
        "total": int(total_result.scalar_one()),
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{profile_id}",
    operation_id="getRecurrenceProfile",
    response_model=RecurrenceProfileResponse,
)
async def get_recurrence_profile(
    profile_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RecurrenceProfileResponse:
    _forbid_superadmin(current_user)
    owner_user_id = await _profile_owner_or_404(session, profile_id)
    await _check_scope(current_user, session, owner_user_id)

    async def _get() -> dict:
        item = await session.get(RecurrenceProfile, parse_uuid(profile_id))
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        return _serialize_profile(item)

    return await with_user_dek(session, owner_user_id, _get)
