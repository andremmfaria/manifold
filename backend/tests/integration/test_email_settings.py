from __future__ import annotations

import hashlib
import hmac

import pytest

from manifold.api._crypto import with_master_dek
from manifold.models.email_settings import InstanceEmailSettings
from manifold.security.encryption import EncryptionService


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


# ---------------------------------------------------------------------------
# GET /api/v1/email-settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_email_settings_non_superadmin_is_403(client, test_user):
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.get("/api/v1/email-settings")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_email_settings_no_row_returns_smtp_bootstrap(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    response = await client.get("/api/v1/email-settings")

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "smtp"
    # Secrets must be masked or absent — never a real value
    cfg = data.get("config") or {}
    pw = cfg.get("password")
    assert pw in ("********", None), f"password not masked: {pw!r}"


# ---------------------------------------------------------------------------
# PUT /api/v1/email-settings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_email_settings_persists_and_masks_secret(client, superadmin_user, db_session):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    put_response = await client.put(
        "/api/v1/email-settings",
        json={
            "provider": "resend",
            "config": {"api_key": "realkey"},
            "from_address": "alerts@x.com",
        },
    )
    assert put_response.status_code == 200

    # GET must mask the api_key
    get_response = await client.get("/api/v1/email-settings")
    assert get_response.status_code == 200
    assert get_response.json()["config"]["api_key"] == "********"

    # Directly read the row under master DEK to assert real value stored
    async def _read_row() -> str | None:
        row = await db_session.get(InstanceEmailSettings, "default")
        if row is None:
            return None
        cfg = dict(row.config or {})
        return cfg.get("api_key")

    # Expire the session cache so it re-reads from DB
    db_session.expire_all()
    stored_key = await with_master_dek(_read_row)
    assert stored_key == "realkey"


@pytest.mark.asyncio
async def test_put_blank_secret_preserves_prior_value(client, superadmin_user, db_session):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    # Store a real value first
    await client.put(
        "/api/v1/email-settings",
        json={
            "provider": "resend",
            "config": {"api_key": "original-secret"},
            "from_address": "alerts@x.com",
        },
    )

    # Now PUT with blank sentinel — must NOT overwrite the original
    for blank_value in ("", "********"):
        response = await client.put(
            "/api/v1/email-settings",
            json={
                "provider": "resend",
                "config": {"api_key": blank_value},
                "from_address": "alerts@x.com",
            },
        )
        assert response.status_code == 200

    # Verify stored value is still the original
    async def _read_row() -> str | None:
        row = await db_session.get(InstanceEmailSettings, "default")
        if row is None:
            return None
        return dict(row.config or {}).get("api_key")

    db_session.expire_all()
    stored_key = await with_master_dek(_read_row)
    assert stored_key == "original-secret", f"secret was overwritten; got {stored_key!r}"


@pytest.mark.asyncio
async def test_put_invalid_config_returns_422(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    response = await client.put(
        "/api/v1/email-settings",
        json={
            "provider": "resend",
            "config": {},  # missing api_key — resend validator rejects
            "from_address": "alerts@x.com",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/email-settings/test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_settings_test_endpoint_ok(client, superadmin_user, monkeypatch):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    # Store a resend config so test can pick it up
    await client.put(
        "/api/v1/email-settings",
        json={
            "provider": "resend",
            "config": {"api_key": "test-api-key"},
            "from_address": "no-reply@example.com",
        },
    )

    # Monkeypatch the transport's send so no network call happens
    from manifold.email.adapters.resend import ResendTransport

    async def fake_send(self, msg):
        return "fake-message-id"

    monkeypatch.setattr(ResendTransport, "send", fake_send)

    response = await client.post(
        "/api/v1/email-settings/test",
        json={"to_address": "recipient@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


# ---------------------------------------------------------------------------
# POST/GET/DELETE /api/v1/email-settings/suppressions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_suppression_no_plaintext_address_in_response(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    response = await client.post(
        "/api/v1/email-settings/suppressions",
        json={"address": "User@Example.com", "reason": "manual"},
    )

    assert response.status_code in (200, 201)
    data = response.json()

    # HMAC must be a non-empty hex string
    hmac_hex = data["address_hmac"]
    assert len(hmac_hex) == 64, f"expected 64-char sha256 hex, got {hmac_hex!r}"
    assert all(c in "0123456789abcdef" for c in hmac_hex.lower())

    # Plaintext address must not appear anywhere in the response body
    import json

    raw = json.dumps(data)
    assert "User@Example.com" not in raw
    assert "user@example.com" not in raw


@pytest.mark.asyncio
async def test_suppression_hmac_equals_expected(client, superadmin_user):
    """HMAC in response must match hmac_sha256(dek_master_key, 'user@example.com')."""
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    response = await client.post(
        "/api/v1/email-settings/suppressions",
        json={"address": "User@Example.com", "reason": "manual"},
    )
    assert response.status_code in (200, 201)

    master_key = EncryptionService().dek_master_key
    expected_digest = hmac.new(master_key, b"user@example.com", hashlib.sha256).hexdigest()

    assert response.json()["address_hmac"] == expected_digest


@pytest.mark.asyncio
async def test_list_suppressions_contains_created_item(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    await client.post(
        "/api/v1/email-settings/suppressions",
        json={"address": "listed@example.com", "reason": "bounce"},
    )

    list_response = await client.get("/api/v1/email-settings/suppressions")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) >= 1
    # Ensure no plaintext address leaked
    import json

    raw = json.dumps(items)
    assert "listed@example.com" not in raw


@pytest.mark.asyncio
async def test_delete_suppression(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    create_resp = await client.post(
        "/api/v1/email-settings/suppressions",
        json={"address": "todelete@example.com", "reason": "manual"},
    )
    suppression_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/email-settings/suppressions/{suppression_id}")
    assert delete_resp.status_code == 204

    list_resp = await client.get("/api/v1/email-settings/suppressions")
    ids = [item["id"] for item in list_resp.json()["items"]]
    assert suppression_id not in ids


@pytest.mark.asyncio
async def test_duplicate_suppression_is_idempotent(client, superadmin_user):
    admin, password = superadmin_user
    await _login(client, admin.username, password)

    body = {"address": "duplicate@example.com", "reason": "bounce"}
    r1 = await client.post("/api/v1/email-settings/suppressions", json=body)
    r2 = await client.post("/api/v1/email-settings/suppressions", json=body)

    # Both calls must succeed without 500
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    # Both must return the same record
    assert r1.json()["address_hmac"] == r2.json()["address_hmac"]
