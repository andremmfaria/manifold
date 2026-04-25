from __future__ import annotations

import pytest

from manifold.models.account import Account
from manifold.models.provider_connection import ProviderConnection
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
