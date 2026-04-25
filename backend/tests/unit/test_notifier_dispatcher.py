from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from manifold.notifiers.base import NotificationPayload, NotificationType, PreparedNotification
from manifold.notifiers.dispatcher import NotifierDispatcher


class DummyNotifier:
    def __init__(self) -> None:
        self.validate_config = MagicMock(return_value=[])
        self.prepare = MagicMock(
            side_effect=lambda payload, config: PreparedNotification(
                subject=payload.subject,
                body=payload.body,
                request_payload={
                    "metadata": dict(payload.metadata),
                    "config": dict(config),
                },
            )
        )
        self.send = AsyncMock(return_value=True)


def _make_session() -> tuple[MagicMock, list[Any]]:
    session = MagicMock()
    deliveries: list[Any] = []
    session.add = MagicMock(side_effect=lambda delivery: deliveries.append(delivery))

    async def flush() -> None:
        for index, delivery in enumerate(deliveries, start=1):
            if not getattr(delivery, "id", None):
                delivery.id = f"delivery-{index}"

    session.flush = AsyncMock(side_effect=flush)
    session.commit = AsyncMock()
    return session, deliveries


def test_notification_payload_creation() -> None:
    payload = NotificationPayload(
        type=NotificationType.TEST,
        subject="Test",
        body="Test body",
    )

    assert payload.type == NotificationType.TEST
    assert payload.subject == "Test"


def test_notifier_registry_get_unknown_type() -> None:
    from manifold.notifiers.registry import registry

    with pytest.raises(KeyError):
        registry.get("unknown_notifier_type_xyz")


def test_email_notifier_validate_config_valid() -> None:
    from manifold.notifiers.email import EmailNotifier

    notifier = EmailNotifier()
    errors = notifier.validate_config(
        {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_use_tls": True,
            "from_address": "from@example.com",
            "to_address": "to@example.com",
        }
    )

    assert errors == []


def test_email_notifier_validate_config_missing_required() -> None:
    from manifold.notifiers.email import EmailNotifier

    notifier = EmailNotifier()

    assert len(notifier.validate_config({})) > 0


def test_webhook_notifier_validate_config_valid() -> None:
    from manifold.notifiers.webhook import WebhookNotifier

    notifier = WebhookNotifier()

    assert notifier.validate_config({"url": "https://example.com/hook"}) == []


def test_webhook_notifier_validate_config_missing_url() -> None:
    from manifold.notifiers.webhook import WebhookNotifier

    notifier = WebhookNotifier()

    assert len(notifier.validate_config({})) > 0


def test_all_notifier_types_registered() -> None:
    from manifold.notifiers.registry import register_all, registry

    register_all()

    for notifier_type in ["email", "webhook", "slack", "telegram"]:
        assert registry.get(notifier_type) is not None


@pytest.mark.asyncio
async def test_dispatch_with_retry_delivers_and_records_payload() -> None:
    session, deliveries = _make_session()
    dispatcher = NotifierDispatcher(session)
    notifier = DummyNotifier()
    payload = NotificationPayload(
        type=NotificationType.TEST,
        subject="Dispatch subject",
        body="Dispatch body",
        metadata={"triggered_at": datetime.now(UTC).isoformat()},
    )

    delivered = await dispatcher._dispatch_with_retry(
        notifier,
        payload,
        {"url": "https://example.test/hook"},
        max_attempts=1,
    )

    assert delivered is True
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.status == "delivered"
    assert delivery.attempt_count == 1
    assert delivery.rendered_subject == "Dispatch subject"
    assert delivery.rendered_body == "Dispatch body"
    assert delivery.response_detail == {"delivered": True, "attempt": 1}

    send_payload = notifier.send.await_args.args[0]
    assert send_payload.metadata["delivery_id"] == "delivery-1"
    assert send_payload.metadata["triggered_at"] == payload.metadata["triggered_at"]


@pytest.mark.asyncio
async def test_dispatch_with_retry_retries_after_http_error() -> None:
    session, deliveries = _make_session()
    dispatcher = NotifierDispatcher(session)
    notifier = DummyNotifier()
    request = httpx.Request("POST", "https://example.test/hook")
    response = httpx.Response(500, request=request, text="boom")
    notifier.send = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError("server error", request=request, response=response),
            True,
        ]
    )

    with patch("manifold.notifiers.dispatcher.asyncio.sleep", new=AsyncMock()) as sleep_mock:
        delivered = await dispatcher._dispatch_with_retry(
            notifier,
            NotificationPayload(type=NotificationType.TEST, subject="Retry", body="Retry body"),
            {"url": "https://example.test/hook"},
            max_attempts=2,
        )

    assert delivered is True
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.status == "delivered"
    assert delivery.attempt_count == 2
    assert delivery.response_detail == {"delivered": True, "attempt": 2}
    sleep_mock.assert_awaited_once_with(dispatcher.BACKOFF_BASE_SECONDS)


@pytest.mark.asyncio
async def test_dispatch_with_retry_fails_fast_for_invalid_config() -> None:
    session, deliveries = _make_session()
    dispatcher = NotifierDispatcher(session)
    notifier = DummyNotifier()
    notifier.validate_config.return_value = ["missing_url"]

    delivered = await dispatcher._dispatch_with_retry(
        notifier,
        NotificationPayload(type=NotificationType.TEST, subject="Bad", body="Bad body"),
        {},
        max_attempts=3,
    )

    assert delivered is False
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.status == "failed"
    assert delivery.error_message == "missing_url"
    assert delivery.response_detail == {"validation_errors": ["missing_url"]}
    notifier.send.assert_not_awaited()
