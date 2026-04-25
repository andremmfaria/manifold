from manifold.tasks.broker import broker


@broker.task(task_name="detect_recurrence", labels={"queue": "maintenance"})
async def detect_recurrence() -> dict[str, str]:
    return {"status": "stub"}


@broker.task(task_name="run_data_retention_jobs", labels={"queue": "maintenance"})
async def run_data_retention_jobs() -> dict[str, str]:
    return {"status": "stub"}
