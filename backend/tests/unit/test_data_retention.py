from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from manifold.models.account import Account
from manifold.models.alarm import AlarmDefinition, AlarmEvaluationResult
from manifold.models.event import Event
from manifold.models.notification_delivery import NotificationDelivery
from manifold.models.provider_connection import ProviderConnection
from manifold.models.sync_run import SyncRun
from manifold.security.encryption import EncryptionService


@pytest.mark.asyncio
async def test_retention_task_importable() -> None:
    from manifold.tasks.maintenance import detect_recurrence, run_data_retention_jobs

    assert callable(run_data_retention_jobs)
    assert callable(detect_recurrence)


def test_retention_settings_have_defaults() -> None:
    from manifold.config import settings

    assert settings.sync_run_retention_days > 0
    assert settings.notification_delivery_retention_days > 0
    assert settings.alarm_evaluation_retention_days > 0
    assert settings.event_retention_days > 0


async def _create_account_graph(
    db_session: AsyncSession, user
) -> tuple[ProviderConnection, Account]:
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Retention connection",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.flush()
        account = Account(
            user_id=str(user.id),
            provider_connection_id=str(connection.id),
            provider_account_id="retention-provider-account",
            account_type="current",
            currency="GBP",
            display_name="Retention account",
            is_active=True,
            raw_payload={"source": "retention-test"},
        )
        db_session.add(account)
        await db_session.flush()
    return connection, account


async def _event_kinds(db_session: AsyncSession, dek: bytes) -> list[tuple[str, str]]:
    enc = EncryptionService()
    with enc.user_dek_context(dek):
        events = (
            await db_session.execute(select(Event).order_by(Event.recorded_at.asc()))
        ).scalars().all()
        return [(item.source_type, item.payload["kind"]) for item in events]


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_run_data_retention_jobs_deletes_only_expired_rows(
    db_engine,
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from manifold import database
    from manifold.tasks import maintenance

    user, _ = test_user
    connection, account = await _create_account_graph(db_session, user)
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    now = datetime.now(UTC)
    old = now - timedelta(days=120)
    fresh = now - timedelta(days=5)

    with enc.user_dek_context(dek):
        alarm = AlarmDefinition(
            user_id=str(user.id),
            name="Retention alarm",
            condition={"op": "LT", "field": "account.balance", "value": 10},
        )
        db_session.add(alarm)
        await db_session.flush()

        db_session.add_all(
            [
                NotificationDelivery(
                    user_id=str(user.id),
                    notification_type="test",
                    status="delivered",
                    attempt_count=1,
                    created_at=old,
                ),
                NotificationDelivery(
                    user_id=str(user.id),
                    notification_type="test",
                    status="delivered",
                    attempt_count=1,
                    created_at=fresh,
                ),
                AlarmEvaluationResult(
                    alarm_id=str(alarm.id),
                    evaluated_at=old,
                    result=True,
                    created_at=old,
                ),
                AlarmEvaluationResult(
                    alarm_id=str(alarm.id),
                    evaluated_at=fresh,
                    result=False,
                    created_at=fresh,
                ),
                Event(
                    event_type="debit_predicted",
                    source_type="predicted",
                    user_id=str(user.id),
                    account_id=str(account.id),
                    occurred_at=old,
                    recorded_at=old,
                    payload={"kind": "old-predicted"},
                    explanation="old predicted",
                ),
                Event(
                    event_type="debit_predicted",
                    source_type="predicted",
                    user_id=str(user.id),
                    account_id=str(account.id),
                    occurred_at=fresh,
                    recorded_at=fresh,
                    payload={"kind": "fresh-predicted"},
                    explanation="fresh predicted",
                ),
                Event(
                    event_type="debit_observed",
                    source_type="observed",
                    user_id=str(user.id),
                    account_id=str(account.id),
                    occurred_at=old,
                    recorded_at=old,
                    payload={"kind": "old-observed"},
                    explanation="old observed",
                ),
            ]
        )
        await db_session.commit()

    db_session.add_all(
        [
            SyncRun(
                provider_connection_id=str(connection.id),
                account_id=str(account.id),
                status="completed",
                created_at=old,
            ),
            SyncRun(
                provider_connection_id=str(connection.id),
                account_id=str(account.id),
                status="completed",
                created_at=fresh,
            ),
            SyncRun(
                provider_connection_id=str(connection.id),
                account_id=str(account.id),
                status="in_progress",
                created_at=old,
            ),
        ]
    )
    await db_session.commit()

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    @asynccontextmanager
    async def override_db_session():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(database, "db_session", override_db_session)
    monkeypatch.setattr(maintenance.settings, "sync_run_retention_days", 90)
    monkeypatch.setattr(maintenance.settings, "notification_delivery_retention_days", 90)
    monkeypatch.setattr(maintenance.settings, "alarm_evaluation_retention_days", 30)
    monkeypatch.setattr(maintenance.settings, "event_retention_days", 90)

    results = await maintenance.run_data_retention_jobs()

    assert results == {
        "sync_runs": 1,
        "notification_deliveries": 1,
        "alarm_evaluation_results": 1,
        "predicted_events": 1,
    }

    sync_runs = (
        await db_session.execute(select(SyncRun).order_by(SyncRun.created_at.asc()))
    ).scalars().all()
    assert [item.status for item in sync_runs] == ["in_progress", "completed"]

    deliveries = (
        await db_session.execute(
            select(NotificationDelivery).order_by(NotificationDelivery.created_at.asc())
        )
    ).scalars().all()
    assert len(deliveries) == 1
    assert deliveries[0].created_at == _naive(fresh)

    evaluations = (
        await db_session.execute(
            select(AlarmEvaluationResult).order_by(AlarmEvaluationResult.created_at.asc())
        )
    ).scalars().all()
    assert len(evaluations) == 1
    assert evaluations[0].created_at == _naive(fresh)

    assert await _event_kinds(db_session, dek) == [
        ("observed", "old-observed"),
        ("predicted", "fresh-predicted"),
    ]
