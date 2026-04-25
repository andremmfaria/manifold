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


@broker.task(task_name="run_data_retention_jobs", labels={"queue": "maintenance"})
async def run_data_retention_jobs() -> dict[str, str]:
    return {"status": "stub"}
