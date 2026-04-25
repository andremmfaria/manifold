from manifold.tasks.broker import broker


@broker.task(queue="manual", retry_on_error=True)
async def dispatch_alarm_notifications(alarm_firing_event_id: str) -> None:
    from manifold.database import db_session
    from manifold.notifiers.dispatcher import NotifierDispatcher

    async with db_session() as session:
        dispatcher = NotifierDispatcher(session)
        await dispatcher.dispatch_for_firing_event(alarm_firing_event_id)


@broker.task(queue="manual", retry_on_error=True)
async def dispatch_system_notification(
    notification_type: str,
    notifier_ids: list[str],
    owner_user_id: str,
    payload_dict: dict,
) -> None:
    from manifold.database import db_session
    from manifold.notifiers.base import NotificationPayload
    from manifold.notifiers.dispatcher import NotifierDispatcher

    async with db_session() as session:
        dispatcher = NotifierDispatcher(session)
        payload = NotificationPayload(**payload_dict)
        await dispatcher.dispatch_system_notification(
            notification_type=notification_type,
            notifier_ids=notifier_ids,
            notifier_owner_user_id=owner_user_id,
            affected_user_id=owner_user_id,
            payload=payload,
        )
