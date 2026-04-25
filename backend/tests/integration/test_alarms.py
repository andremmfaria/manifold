from __future__ import annotations

from datetime import UTC, datetime

import pytest

from manifold.models.account import Account
from manifold.models.alarm import AlarmEvaluationResult, AlarmFiringEvent, AlarmState
from manifold.models.provider_connection import ProviderConnection
from manifold.security.encryption import EncryptionService


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


async def _create_account(db_session, user):
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Primary connection",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.flush()
        account = Account(
            user_id=str(user.id),
            provider_connection_id=str(connection.id),
            provider_account_id="provider-account-1",
            account_type="current",
            currency="GBP",
            display_name="Main account",
            is_active=True,
            raw_payload={"source": "test"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)
        return account


async def _create_alarm(client, account_id: str):
    return await client.post(
        "/api/v1/alarms",
        json={
            "name": "Low balance",
            "condition": {"op": "LT", "field": "account.balance", "value": 100},
            "account_ids": [account_id],
            "notifier_ids": [],
            "repeat_count": 2,
            "cooldown_minutes": 15,
            "notify_on_resolve": True,
        },
    )


@pytest.mark.asyncio
async def test_list_alarms_empty(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/alarms")

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_create_get_update_delete_alarm(client, test_user, db_session):
    user, password = test_user
    account = await _create_account(db_session, user)
    await _login(client, user.username, password)

    create_response = await _create_alarm(client, str(account.id))
    assert create_response.status_code == 201
    alarm = create_response.json()
    assert alarm["name"] == "Low balance"
    assert alarm["account_ids"] == [str(account.id)]
    assert alarm["state"] == "ok"

    get_response = await client.get(f"/api/v1/alarms/{alarm['id']}")
    assert get_response.status_code == 200

    update_response = await client.patch(
        f"/api/v1/alarms/{alarm['id']}",
        json={"name": "Very low balance", "status": "paused", "account_ids": [str(account.id)]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Very low balance"
    assert update_response.json()["status"] == "paused"

    delete_response = await client.delete(f"/api/v1/alarms/{alarm['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_alarm_mute_and_unmute_flow(client, test_user, db_session):
    user, password = test_user
    account = await _create_account(db_session, user)
    await _login(client, user.username, password)
    alarm = (await _create_alarm(client, str(account.id))).json()
    mute_until = datetime(2025, 1, 2, tzinfo=UTC).isoformat()

    mute_response = await client.post(
        f"/api/v1/alarms/{alarm['id']}/mute",
        json={"mute_until": mute_until},
    )
    assert mute_response.status_code == 200
    assert mute_response.json()["state"] == "muted"
    assert mute_response.json()["mute_until"].startswith("2025-01-02T00:00:00")

    unmute_response = await client.post(f"/api/v1/alarms/{alarm['id']}/unmute")
    assert unmute_response.status_code == 200
    assert unmute_response.json()["state"] == "ok"
    assert unmute_response.json()["mute_until"] is None


@pytest.mark.asyncio
async def test_alarm_history_and_firings(client, test_user, db_session):
    user, password = test_user
    account = await _create_account(db_session, user)
    await _login(client, user.username, password)
    alarm = (await _create_alarm(client, str(account.id))).json()
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    evaluated_at = datetime(2025, 1, 1, tzinfo=UTC)

    with enc.user_dek_context(dek):
        db_session.add(
            AlarmEvaluationResult(
                alarm_id=alarm["id"],
                evaluated_at=evaluated_at,
                result=True,
                previous_state="ok",
                new_state="firing",
                condition_version=1,
                context_snapshot={"account": {"balance": 50}},
                explanation="account.balance (50) < 100",
            )
        )
        db_session.add(
            AlarmFiringEvent(
                alarm_id=alarm["id"],
                fired_at=evaluated_at,
                explanation="account.balance (50) < 100",
                condition_snapshot={"op": "LT"},
                context_snapshot={"account": {"balance": 50}},
                notifications_sent=1,
            )
        )
        state = await db_session.get(AlarmState, alarm["id"])
        if state is not None:
            state.state = "firing"
            state.last_fired_at = evaluated_at
        await db_session.commit()

    history_response = await client.get(f"/api/v1/alarms/{alarm['id']}/history")
    firings_response = await client.get(f"/api/v1/alarms/{alarm['id']}/firings")

    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["new_state"] == "firing"
    assert firings_response.status_code == 200
    assert firings_response.json()["items"][0]["notifications_sent"] == 1


@pytest.mark.asyncio
async def test_superadmin_cannot_access_alarms(client, superadmin_user):
    user, password = superadmin_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/alarms")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_alarm_requires_account_ids(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.post(
        "/api/v1/alarms",
        json={
            "name": "Broken alarm",
            "condition": {"op": "LT", "field": "account.balance", "value": 0},
            "account_ids": [],
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_superadmin_can_queue_alarm_evaluation(client, superadmin_user, monkeypatch):
    user, password = superadmin_user
    await _login(client, user.username, password)

    from manifold.tasks.alarms import evaluate_all_alarms

    async def fake_kiq():
        return None

    monkeypatch.setattr(evaluate_all_alarms, "kiq", fake_kiq)

    response = await client.post("/api/v1/alarms/evaluate")

    assert response.status_code == 202
    assert response.json() == {"status": "queued"}
