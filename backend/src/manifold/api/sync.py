from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import scope_to_uuids
from manifold.api.deps import get_current_user, get_session
from manifold.domain.ownership import get_accessible_scope
from manifold.models.provider_connection import ProviderConnection
from manifold.models.sync_run import SyncRun
from manifold.models.user import User
from manifold.schemas.sync_runs import SyncRunResponse

router = APIRouter()


def _serialize_sync_run(run: SyncRun) -> dict:
    return {
        "id": str(run.id),
        "provider_connection_id": str(run.provider_connection_id),
        "account_id": str(run.account_id) if run.account_id else None,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "accounts_synced": run.accounts_synced,
        "transactions_synced": run.transactions_synced,
        "new_transactions": run.new_transactions,
        "error_code": run.error_code,
        "error_detail": run.error_detail,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/sync-runs", operation_id="listSyncRuns", response_model=list[SyncRunResponse])
async def list_sync_runs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SyncRunResponse]:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(SyncRun)
        .join(ProviderConnection, SyncRun.provider_connection_id == ProviderConnection.id)
        .where(ProviderConnection.user_id.in_(scope_to_uuids(scope)))
        .order_by(SyncRun.created_at.desc())
    )
    return [_serialize_sync_run(run) for run in result.scalars().all()]


@router.get(
    "/sync-runs/{sync_run_id}",
    operation_id="getSyncRun",
    response_model=SyncRunResponse,
)
async def get_sync_run(
    sync_run_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SyncRunResponse:
    scope = await get_accessible_scope(current_user, session)
    result = await session.execute(
        select(SyncRun)
        .join(ProviderConnection, SyncRun.provider_connection_id == ProviderConnection.id)
        .where(SyncRun.id == sync_run_id, ProviderConnection.user_id.in_(scope_to_uuids(scope)))
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return _serialize_sync_run(run)


__all__ = ["router"]
