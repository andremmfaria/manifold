from manifold.config import settings
from manifold.tasks.broker import broker


@broker.task(
    queue="sync",
    retry_on_error=True,
    schedule=[{"cron": settings.alarm_eval_cron}],
)
async def evaluate_all_alarms() -> None:
    from manifold.database import db_session
    from manifold.domain.alarm_evaluator import AlarmEvaluatorService

    async with db_session() as session:
        evaluator = AlarmEvaluatorService(session)
        await evaluator.evaluate_all_active()
