from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_master_dek
from manifold.email.base import SuppressionEvent
from manifold.models.email_suppression import EmailSuppression
from manifold.models.email_webhook_event import EmailWebhookEvent
from manifold.security.encryption import EncryptionService


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


async def _setup_email_settings(client, superadmin_user, provider: str, extra_config: dict):
    """PUT a minimal valid email settings row for the given provider."""
    admin, password = superadmin_user
    await _login(client, admin.username, password)
    await client.put(
        "/api/v1/email-settings",
        json={
            "provider": provider,
            "config": extra_config,
            "from_address": "no-reply@example.com",
        },
    )
    # Log out so webhook requests don't carry session cookies
    await client.post("/api/v1/auth/logout")


def _address_hmac(address: str) -> bytes:
    master_key = EncryptionService().dek_master_key
    normalized = address.strip().lower()
    return hmac.new(master_key, normalized.encode(), hashlib.sha256).digest()


# ---------------------------------------------------------------------------
# Unknown provider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_provider_returns_404(client):
    response = await client.post(
        "/api/v1/email/webhooks/unknownprovider",
        content=b'{"event": "test"}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Shared helper: test a provider with mocked verify/parse
# ---------------------------------------------------------------------------


async def _run_webhook_test(
    client,
    superadmin_user,
    db_session: AsyncSession,
    provider: str,
    settings_config: dict,
    transport_module: str,
    transport_class: str,
    bounce_address: str,
    monkeypatch,
    *,
    raw_body: bytes = b'{"event": "bounce"}',
):
    """
    Insert InstanceEmailSettings row for `provider`, monkeypatch verify_webhook → True and
    parse_webhook → [SuppressionEvent(bounce_address, 'bounce', provider)], POST the webhook,
    then assert suppression + audit rows exist.
    """
    await _setup_email_settings(client, superadmin_user, provider, settings_config)

    import importlib

    mod = importlib.import_module(transport_module)
    cls = getattr(mod, transport_class)

    monkeypatch.setattr(cls, "verify_webhook", lambda self, headers, body: True)
    monkeypatch.setattr(
        cls,
        "parse_webhook",
        lambda self, payload: [
            SuppressionEvent(address=bounce_address, reason="bounce", provider=provider)
        ],
    )

    response = await client.post(
        f"/api/v1/email/webhooks/{provider}",
        content=raw_body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200

    expected_hmac = _address_hmac(bounce_address)

    # Assert suppression row exists
    async def _check() -> tuple[bool, bool]:
        supp = await db_session.execute(
            select(EmailSuppression).where(EmailSuppression.address_hmac == expected_hmac)
        )
        audit = await db_session.execute(select(EmailWebhookEvent))
        return supp.scalar_one_or_none() is not None, audit.scalars().first() is not None

    db_session.expire_all()
    suppression_found, audit_found = await with_master_dek(_check)
    assert suppression_found, "suppression row not inserted"
    assert audit_found, "audit row not inserted"


async def _run_reject_test(
    client,
    superadmin_user,
    db_session: AsyncSession,
    provider: str,
    settings_config: dict,
    transport_module: str,
    transport_class: str,
    bounce_address: str,
    monkeypatch,
    *,
    raw_body: bytes = b'{"event": "bounce"}',
):
    """verify_webhook returns False → 401, no suppression row inserted."""
    await _setup_email_settings(client, superadmin_user, provider, settings_config)

    import importlib

    mod = importlib.import_module(transport_module)
    cls = getattr(mod, transport_class)

    monkeypatch.setattr(cls, "verify_webhook", lambda self, headers, body: False)

    response = await client.post(
        f"/api/v1/email/webhooks/{provider}",
        content=raw_body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 401

    expected_hmac = _address_hmac(bounce_address)

    async def _check() -> bool:
        supp = await db_session.execute(
            select(EmailSuppression).where(EmailSuppression.address_hmac == expected_hmac)
        )
        return supp.scalar_one_or_none() is None

    db_session.expire_all()
    no_suppression = await with_master_dek(_check)
    assert no_suppression, "suppression row must NOT be inserted when signature invalid"


# ---------------------------------------------------------------------------
# SES
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ses_webhook_valid_inserts_suppression(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_webhook_test(
        client,
        superadmin_user,
        db_session,
        provider="ses",
        settings_config={"region": "us-east-1"},
        transport_module="manifold.email.adapters.ses",
        transport_class="SESTransport",
        bounce_address="ses-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps({"Type": "Notification", "Message": "{}"}).encode(),
    )


@pytest.mark.asyncio
async def test_ses_webhook_invalid_signature_returns_401(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_reject_test(
        client,
        superadmin_user,
        db_session,
        provider="ses",
        settings_config={"region": "us-east-1"},
        transport_module="manifold.email.adapters.ses",
        transport_class="SESTransport",
        bounce_address="ses-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps({"Type": "Notification", "Message": "{}"}).encode(),
    )


@pytest.mark.asyncio
async def test_ses_subscription_confirmation_no_suppression(
    client, superadmin_user, db_session, monkeypatch
):
    """SubscriptionConfirmation: verify True + parse [] -> 200, audit row, no suppression."""
    await _setup_email_settings(client, superadmin_user, "ses", {"region": "us-east-1"})

    from manifold.email.adapters.ses import SESTransport

    monkeypatch.setattr(SESTransport, "verify_webhook", lambda self, headers, body: True)
    monkeypatch.setattr(SESTransport, "parse_webhook", lambda self, payload: [])

    raw_body = json.dumps(
        {
            "Type": "SubscriptionConfirmation",
            "SubscribeURL": "https://sns.amazonaws.com/confirm",
            "Token": "abc",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        }
    ).encode()

    response = await client.post(
        "/api/v1/email/webhooks/ses",
        content=raw_body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200

    async def _check() -> tuple[int, bool]:
        supp_count_result = await db_session.execute(select(EmailSuppression))
        supp_count = len(supp_count_result.scalars().all())
        audit_result = await db_session.execute(select(EmailWebhookEvent))
        audit_exists = audit_result.scalars().first() is not None
        return supp_count, audit_exists

    db_session.expire_all()
    supp_count, audit_exists = await with_master_dek(_check)
    assert supp_count == 0, "no suppression should be created for SubscriptionConfirmation"
    assert audit_exists, "audit row should be inserted"


# ---------------------------------------------------------------------------
# Resend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_webhook_valid_inserts_suppression(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_webhook_test(
        client,
        superadmin_user,
        db_session,
        provider="resend",
        settings_config={"api_key": "re_test_key", "webhook_secret": "whsec_test"},
        transport_module="manifold.email.adapters.resend",
        transport_class="ResendTransport",
        bounce_address="resend-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps(
            {"type": "email.bounced", "data": {"to": "resend-bounce@x.com"}}
        ).encode(),
    )


@pytest.mark.asyncio
async def test_resend_webhook_invalid_signature_returns_401(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_reject_test(
        client,
        superadmin_user,
        db_session,
        provider="resend",
        settings_config={"api_key": "re_test_key", "webhook_secret": "whsec_test"},
        transport_module="manifold.email.adapters.resend",
        transport_class="ResendTransport",
        bounce_address="resend-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps({"type": "email.bounced"}).encode(),
    )


# ---------------------------------------------------------------------------
# Postmark
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_postmark_webhook_valid_inserts_suppression(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_webhook_test(
        client,
        superadmin_user,
        db_session,
        provider="postmark",
        settings_config={"api_key": "pm_test_key", "webhook_token": "pm_token"},
        transport_module="manifold.email.adapters.postmark",
        transport_class="PostmarkTransport",
        bounce_address="postmark-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps({"RecordType": "Bounce", "Email": "postmark-bounce@x.com"}).encode(),
    )


@pytest.mark.asyncio
async def test_postmark_webhook_invalid_signature_returns_401(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_reject_test(
        client,
        superadmin_user,
        db_session,
        provider="postmark",
        settings_config={"api_key": "pm_test_key", "webhook_token": "pm_token"},
        transport_module="manifold.email.adapters.postmark",
        transport_class="PostmarkTransport",
        bounce_address="postmark-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps({"RecordType": "Bounce", "Email": "postmark-bounce@x.com"}).encode(),
    )


# ---------------------------------------------------------------------------
# Mailgun
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mailgun_webhook_valid_inserts_suppression(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_webhook_test(
        client,
        superadmin_user,
        db_session,
        provider="mailgun",
        settings_config={
            "api_key": "mg_key",
            "domain": "mg.example.com",
            "region": "us",
            "webhook_signing_key": "mg_sign_key",
        },
        transport_module="manifold.email.adapters.mailgun",
        transport_class="MailgunTransport",
        bounce_address="mailgun-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps(
            {
                "event-data": {
                    "event": "failed",
                    "severity": "permanent",
                    "recipient": "mailgun-bounce@x.com",
                }
            }
        ).encode(),
    )


@pytest.mark.asyncio
async def test_mailgun_webhook_invalid_signature_returns_401(
    client, superadmin_user, db_session, monkeypatch
):
    await _run_reject_test(
        client,
        superadmin_user,
        db_session,
        provider="mailgun",
        settings_config={
            "api_key": "mg_key",
            "domain": "mg.example.com",
            "region": "us",
            "webhook_signing_key": "mg_sign_key",
        },
        transport_module="manifold.email.adapters.mailgun",
        transport_class="MailgunTransport",
        bounce_address="mailgun-bounce@x.com",
        monkeypatch=monkeypatch,
        raw_body=json.dumps(
            {
                "event-data": {
                    "event": "failed",
                    "severity": "permanent",
                    "recipient": "mailgun-bounce@x.com",
                }
            }
        ).encode(),
    )
