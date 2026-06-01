from __future__ import annotations

import hashlib
import hmac

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_master_dek, with_user_dek
from manifold.models.account import Account
from manifold.models.email_settings import InstanceEmailSettings
from manifold.models.email_suppression import EmailSuppression
from manifold.models.notifier import NotifierConfig
from manifold.models.provider_connection import ProviderConnection
from manifold.notifiers.base import NotificationPayload, NotificationType
from manifold.notifiers.email import EmailNotifier
from manifold.notifiers.webhook import WebhookNotifier
from manifold.security.encryption import EncryptionService


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


async def _create_account(db_session, user):
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Notifier connection",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.flush()
        account = Account(
            user_id=str(user.id),
            provider_connection_id=str(connection.id),
            provider_account_id="provider-account-2",
            account_type="current",
            currency="GBP",
            display_name="Notifier account",
            is_active=True,
            raw_payload={"source": "test"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)
        return account


@pytest.mark.asyncio
async def test_create_list_get_update_delete_notifier(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    create_response = await client.post(
        "/api/v1/notifiers",
        json={
            "name": "Webhook notifier",
            "type": "webhook",
            "config": {"url": "https://example.test/webhook"},
            "is_enabled": True,
        },
    )
    assert create_response.status_code == 201
    notifier = create_response.json()

    list_response = await client.get("/api/v1/notifiers")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["id"] == notifier["id"]

    get_response = await client.get(f"/api/v1/notifiers/{notifier['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Webhook notifier"

    update_response = await client.patch(
        f"/api/v1/notifiers/{notifier['id']}",
        json={"name": "Updated notifier", "is_enabled": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated notifier"
    assert update_response.json()["is_enabled"] is False

    delete_response = await client.delete(f"/api/v1/notifiers/{notifier['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}


@pytest.mark.asyncio
async def test_invalid_notifier_config_returns_422(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.post(
        "/api/v1/notifiers",
        json={"name": "Broken", "type": "webhook", "config": {}, "is_enabled": True},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_test_notifier_creates_delivery(client, test_user, monkeypatch):
    user, password = test_user
    await _login(client, user.username, password)
    create_response = await client.post(
        "/api/v1/notifiers",
        json={
            "name": "Webhook notifier",
            "type": "webhook",
            "config": {"url": "https://example.test/webhook"},
            "is_enabled": True,
        },
    )
    notifier_id = create_response.json()["id"]

    async def fake_send(self, payload, config):
        return True

    monkeypatch.setattr(WebhookNotifier, "send", fake_send)

    response = await client.post(f"/api/v1/notifiers/{notifier_id}/test")

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    deliveries_response = await client.get(f"/api/v1/notifiers/{notifier_id}/deliveries")
    assert deliveries_response.status_code == 200
    assert deliveries_response.json()["items"][0]["status"] == "delivered"


@pytest.mark.asyncio
async def test_delete_notifier_blocked_when_linked_to_active_alarm(client, test_user, db_session):
    user, password = test_user
    account = await _create_account(db_session, user)
    await _login(client, user.username, password)
    notifier = (
        await client.post(
            "/api/v1/notifiers",
            json={
                "name": "Webhook notifier",
                "type": "webhook",
                "config": {"url": "https://example.test/webhook"},
                "is_enabled": True,
            },
        )
    ).json()
    await client.post(
        "/api/v1/alarms",
        json={
            "name": "Linked alarm",
            "condition": {"op": "LT", "field": "account.balance", "value": 0},
            "account_ids": [str(account.id)],
            "notifier_ids": [notifier["id"]],
        },
    )

    response = await client.delete(f"/api/v1/notifiers/{notifier['id']}")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_regular_user_cannot_read_other_users_notifier(
    client, test_user, another_user, db_session
):
    owner, owner_password = test_user
    other, other_password = another_user
    await _login(client, owner.username, owner_password)
    notifier = (
        await client.post(
            "/api/v1/notifiers",
            json={
                "name": "Private notifier",
                "type": "webhook",
                "config": {"url": "https://example.test/private"},
                "is_enabled": True,
            },
        )
    ).json()
    await client.post("/api/v1/auth/logout")
    await _login(client, other.username, other_password)

    response = await client.get(f"/api/v1/notifiers/{notifier['id']}")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Email notifier integration tests (Phase 10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_notifier_config_stores_only_routing_keys(client, test_user, db_session):
    """Creating an email notifier stores config with routing keys only — no transport secrets."""
    user, password = test_user
    await _login(client, user.username, password)

    create_response = await client.post(
        "/api/v1/notifiers",
        json={
            "name": "Email notifier",
            "type": "email",
            "config": {"to_address": "t@example.com"},
            "is_enabled": True,
        },
    )
    assert create_response.status_code == 201
    notifier_id = create_response.json()["id"]

    # Read the stored NotifierConfig blob under the user DEK
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)

    async def _read_config() -> dict:
        row = await db_session.get(NotifierConfig, notifier_id)
        return dict(row.config or {}) if row else {}

    with enc.user_dek_context(dek):
        stored_config = await _read_config()

    assert stored_config.get("to_address") == "t@example.com"
    # Transport secrets must NOT be in the per-notifier config blob
    transport_secret_keys = {"smtp_host", "smtp_port", "smtp_password", "password", "api_key"}
    leaked = transport_secret_keys.intersection(stored_config.keys())
    assert not leaked, f"Transport secrets leaked into notifier config: {leaked}"


@pytest.mark.asyncio
async def test_email_notifier_dispatch_attempts_send(
    client, test_user, db_session: AsyncSession, monkeypatch
):
    """Dispatch to email notifier calls transport.send; payload has routing keys only."""
    user, password = test_user
    await _login(client, user.username, password)

    # Create email notifier via API
    create_response = await client.post(
        "/api/v1/notifiers",
        json={
            "name": "Email notifier",
            "type": "email",
            "config": {"to_address": "t@example.com"},
            "is_enabled": True,
        },
    )
    assert create_response.status_code == 201
    notifier_id = create_response.json()["id"]

    # Insert InstanceEmailSettings so the dispatcher can load transport config
    async def _insert_settings() -> None:
        row = InstanceEmailSettings(
            id="default",
            provider="smtp",
            config={"host": "localhost", "port": 1025, "use_tls": False},
            from_address="no-reply@example.com",
            is_configured=True,
        )
        db_session.add(row)
        await db_session.commit()

    await with_master_dek(_insert_settings)

    # Track what send was called with
    sent_messages: list = []

    from manifold.email.adapters.smtp import SMTPTransport

    async def fake_send(self, msg):
        sent_messages.append(msg)
        return "fake-msg-id"

    monkeypatch.setattr(SMTPTransport, "send", fake_send)

    # Dispatch via the test endpoint
    test_response = await client.post(f"/api/v1/notifiers/{notifier_id}/test")
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True

    assert len(sent_messages) == 1, "transport.send must have been called once"

    # The message sent must target the correct recipient
    sent_msg = sent_messages[0]
    assert "t@example.com" in sent_msg.to

    # Verify the EmailNotifier.build_request_payload produces routing-only keys by
    # checking the notifier directly — no HTTP round-trip needed here.
    notifier_instance = EmailNotifier()
    test_config = {"to_address": "t@example.com"}

    sample_payload = NotificationPayload(
        type=NotificationType.TEST,
        subject="Test",
        body="Test body",
    )
    req_payload = notifier_instance.build_request_payload(
        sample_payload, test_config, "Test", "Test body"
    )
    assert req_payload.get("to_address") == "t@example.com"
    transport_secret_keys = {"smtp_host", "smtp_port", "smtp_password", "password", "api_key"}
    leaked = transport_secret_keys.intersection(req_payload.keys())
    assert not leaked, f"Transport secrets leaked into delivery payload: {leaked}"


@pytest.mark.asyncio
async def test_email_dispatch_suppressed_address_returns_false(
    client, test_user, db_session: AsyncSession, monkeypatch
):
    """Dispatching to a suppressed address causes EmailNotifier.send to return False."""
    user, password = test_user
    await _login(client, user.username, password)

    to_address = "t@example.com"

    # Create email notifier
    create_response = await client.post(
        "/api/v1/notifiers",
        json={
            "name": "Email suppression notifier",
            "type": "email",
            "config": {"to_address": to_address},
            "is_enabled": True,
        },
    )
    assert create_response.status_code == 201
    notifier_id = create_response.json()["id"]

    # Insert InstanceEmailSettings
    async def _insert_settings() -> None:
        row = InstanceEmailSettings(
            id="default",
            provider="smtp",
            config={"host": "localhost", "port": 1025, "use_tls": False},
            from_address="no-reply@example.com",
            is_configured=True,
        )
        db_session.add(row)
        await db_session.commit()

    await with_master_dek(_insert_settings)

    # Insert EmailSuppression for to_address under master DEK
    async def _insert_suppression() -> None:
        master_key = EncryptionService().dek_master_key
        normalized = to_address.strip().lower()
        digest = hmac.new(master_key, normalized.encode(), hashlib.sha256).digest()
        db_session.add(
            EmailSuppression(
                address_hmac=digest,
                reason="bounce",
                source="test",
            )
        )
        await db_session.commit()

    await with_master_dek(_insert_suppression)

    # Monkeypatch transport.send to ensure it is NOT called
    send_called = []

    from manifold.email.adapters.smtp import SMTPTransport

    async def fake_send(self, msg):
        send_called.append(msg)
        return "should-not-reach"

    monkeypatch.setattr(SMTPTransport, "send", fake_send)

    # Dispatch via test endpoint — should fail delivery due to suppression
    test_response = await client.post(f"/api/v1/notifiers/{notifier_id}/test")
    # The /test endpoint returns {"ok": delivered_bool}
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is False

    # transport.send must NOT have been called
    assert send_called == [], "send must not be called for suppressed address"


@pytest.mark.asyncio
async def test_with_master_dek_nested_inside_user_dek_restores_context(
    test_user, db_session: AsyncSession
):
    """
    with_master_dek nested inside with_user_dek must complete successfully and
    the outer user DEK context must be restored afterwards.
    """
    user, _password = test_user

    enc = EncryptionService()
    master_key = enc.dek_master_key
    user_dek = enc.decrypt_dek(user.encrypted_dek)

    results: dict = {}

    async def _outer():
        # Inside user DEK context — record what's active
        from manifold.security.encryption import _current_dek

        results["outer_before"] = _current_dek.get()

        # Call with_master_dek nested inside
        async def _inner():
            results["inner"] = _current_dek.get()
            return "inner_done"

        rv = await with_master_dek(_inner)
        results["inner_return"] = rv
        # After with_master_dek the outer context must be restored
        results["outer_after"] = _current_dek.get()

    await with_user_dek(db_session, str(user.id), _outer)

    # Inside outer user DEK context both before and after the inner call must be user_dek
    assert results["outer_before"] == user_dek
    assert results["outer_after"] == user_dek
    # Inner must have seen master_key
    assert results["inner"] == master_key
    assert results["inner_return"] == "inner_done"
