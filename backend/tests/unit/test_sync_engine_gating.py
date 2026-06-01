from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from manifold.domain.sync_engine import SyncEngine
from manifold.models.sync_run import SyncRun


def _make_connection(
    connection_id: str,
    user_id: str,
    last_sync_at: datetime | None,
    sync_interval: str | None = None,
) -> MagicMock:
    """Return a minimal ProviderConnection mock with the fields SyncEngine reads."""
    conn = MagicMock()
    conn.id = connection_id
    conn.user_id = user_id
    conn.provider_type = "json"
    conn.status = "active"
    conn.auth_status = "connected"
    conn.last_sync_at = last_sync_at
    conn.credentials_encrypted = {}
    conn.config = {"sync_interval": sync_interval} if sync_interval else {}
    conn.consent_expires_at = None
    return conn


def _make_sync_run(run_id: str) -> MagicMock:
    run = MagicMock(spec=SyncRun)
    run.id = run_id
    run.status = "success"
    return run


@pytest.mark.asyncio
async def test_sync_all_active_skips_recent_connection():
    """A connection synced 2 minutes ago with sync_interval=1h must be skipped."""
    now = datetime.now(UTC)
    recent_sync = now - timedelta(minutes=2)
    conn_id = "conn-recent"
    user_id = "user-1"

    connection = _make_connection(conn_id, user_id, last_sync_at=recent_sync, sync_interval="1h")

    db_result = MagicMock()
    db_result.all.return_value = [(conn_id, user_id, recent_sync)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=db_result)

    async def fake_db_session():
        yield mock_session

    with (
        patch("manifold.domain.sync_engine.db_session") as mock_ctx,
        patch("manifold.domain.sync_engine.acquire_lock", return_value=True),
        patch("manifold.domain.sync_engine.release_lock"),
        patch.object(
            SyncEngine,
            "_load_connection_for_owner_context",
            new=AsyncMock(return_value=connection),
        ),
        patch.object(
            SyncEngine,
            "sync_connection",
            new=AsyncMock(return_value=_make_sync_run("run-1")),
        ) as mock_sync,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = SyncEngine()
        runs = await engine.sync_all_active()

    # Synced 2 min ago, interval 1h → must be skipped
    assert runs == []
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_sync_all_active_syncs_overdue_connection():
    """A connection last synced 2h ago with sync_interval=1h must be synced."""
    now = datetime.now(UTC)
    old_sync = now - timedelta(hours=2)
    conn_id = "conn-old"
    user_id = "user-2"

    connection = _make_connection(conn_id, user_id, last_sync_at=old_sync, sync_interval="1h")
    run = _make_sync_run("run-2")

    db_result = MagicMock()
    db_result.all.return_value = [(conn_id, user_id, old_sync)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=db_result)

    with (
        patch("manifold.domain.sync_engine.db_session") as mock_ctx,
        patch("manifold.domain.sync_engine.acquire_lock", return_value=True),
        patch("manifold.domain.sync_engine.release_lock"),
        patch.object(
            SyncEngine,
            "_load_connection_for_owner_context",
            new=AsyncMock(return_value=connection),
        ),
        patch.object(
            SyncEngine,
            "sync_connection",
            new=AsyncMock(return_value=run),
        ) as mock_sync,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = SyncEngine()
        runs = await engine.sync_all_active()

    assert len(runs) == 1
    mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_sync_all_active_syncs_never_synced_connection():
    """A connection with last_sync_at=None must be synced regardless of interval."""
    conn_id = "conn-new"
    user_id = "user-3"

    connection = _make_connection(conn_id, user_id, last_sync_at=None, sync_interval="1h")
    run = _make_sync_run("run-3")

    db_result = MagicMock()
    db_result.all.return_value = [(conn_id, user_id, None)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=db_result)

    with (
        patch("manifold.domain.sync_engine.db_session") as mock_ctx,
        patch("manifold.domain.sync_engine.acquire_lock", return_value=True),
        patch("manifold.domain.sync_engine.release_lock"),
        patch.object(
            SyncEngine,
            "_load_connection_for_owner_context",
            new=AsyncMock(return_value=connection),
        ),
        patch.object(
            SyncEngine,
            "sync_connection",
            new=AsyncMock(return_value=run),
        ) as mock_sync,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = SyncEngine()
        runs = await engine.sync_all_active()

    assert len(runs) == 1
    mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_sync_all_active_never_auto_syncs_manual_connection():
    """A connection with sync_interval=manual must never be auto-synced."""
    conn_id = "conn-manual"
    user_id = "user-4"

    connection = _make_connection(conn_id, user_id, last_sync_at=None, sync_interval="manual")

    db_result = MagicMock()
    db_result.all.return_value = [(conn_id, user_id, None)]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=db_result)

    with (
        patch("manifold.domain.sync_engine.db_session") as mock_ctx,
        patch("manifold.domain.sync_engine.acquire_lock", return_value=True),
        patch("manifold.domain.sync_engine.release_lock"),
        patch.object(
            SyncEngine,
            "_load_connection_for_owner_context",
            new=AsyncMock(return_value=connection),
        ),
        patch.object(
            SyncEngine,
            "sync_connection",
            new=AsyncMock(return_value=_make_sync_run("run-4")),
        ) as mock_sync,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        engine = SyncEngine()
        runs = await engine.sync_all_active()

    assert runs == []
    mock_sync.assert_not_called()
