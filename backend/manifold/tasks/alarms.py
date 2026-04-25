from manifold.tasks.broker import broker


@broker.task(task_name="evaluate_all_alarms", labels={"queue": "alarms"})
async def evaluate_all_alarms() -> dict[str, str]:
    return {"status": "stub"}
