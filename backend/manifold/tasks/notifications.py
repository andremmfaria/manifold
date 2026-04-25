from manifold.tasks.broker import broker


@broker.task(task_name="dispatch_alarm_notifications", labels={"queue": "notifications"})
async def dispatch_alarm_notifications() -> dict[str, str]:
    return {"status": "stub"}


@broker.task(task_name="dispatch_system_notification", labels={"queue": "notifications"})
async def dispatch_system_notification() -> dict[str, str]:
    return {"status": "stub"}
