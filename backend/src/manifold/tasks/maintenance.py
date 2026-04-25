from manifold.config import settings
from manifold.tasks.broker import broker


@broker.task(
    queue="sync",
    schedule=[{"cron": settings.recurrence_detect_cron}],
)
async def detect_recurrence() -> None:
    from manifold.database import db_session
    from manifold.domain.recurrence import RecurrenceDetector

    async with db_session() as session:
        detector = RecurrenceDetector(session)
        await detector.detect_for_all_users()


@broker.task(
    task_name="run_data_retention_jobs",
    queue="maintenance",
    schedule=[{"cron": settings.cleanup_cron}],
)
async def run_data_retention_jobs() -> dict[str, int]:
    """Delete old records according to configured retention windows.
    Returns dict of {table_name: rows_deleted}."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from manifold.database import db_session
    from manifold.models.alarm import AlarmEvaluationResult
    from manifold.models.event import Event
    from manifold.models.notification_delivery import NotificationDelivery
    from manifold.models.sync_run import SyncRun

    results: dict[str, int] = {}
    now = datetime.now(UTC)

    async with db_session() as session:
        if settings.sync_run_retention_days > 0:
            cutoff = now - timedelta(days=settings.sync_run_retention_days)
            result = await session.execute(
                delete(SyncRun).where(
                    SyncRun.created_at < cutoff,
                    SyncRun.status != "in_progress",
                )
            )
            results["sync_runs"] = result.rowcount or 0
            await session.commit()

        if settings.notification_delivery_retention_days > 0:
            cutoff = now - timedelta(days=settings.notification_delivery_retention_days)
            result = await session.execute(
                delete(NotificationDelivery).where(NotificationDelivery.created_at < cutoff)
            )
            results["notification_deliveries"] = result.rowcount or 0
            await session.commit()

        if settings.alarm_evaluation_retention_days > 0:
            cutoff = now - timedelta(days=settings.alarm_evaluation_retention_days)
            result = await session.execute(
                delete(AlarmEvaluationResult).where(AlarmEvaluationResult.created_at < cutoff)
            )
            results["alarm_evaluation_results"] = result.rowcount or 0
            await session.commit()

        if settings.event_retention_days > 0:
            cutoff = now - timedelta(days=settings.event_retention_days)
            result = await session.execute(
                delete(Event).where(
                    Event.source_type == "predicted",
                    Event.recorded_at < cutoff,
                )
            )
            results["predicted_events"] = result.rowcount or 0
            await session.commit()

    return results
