from __future__ import annotations

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_master_dek
from manifold.api.deps import get_session
from manifold.email.factory import get_transport
from manifold.models.email_settings import InstanceEmailSettings
from manifold.models.email_suppression import EmailSuppression
from manifold.models.email_webhook_event import EmailWebhookEvent
from manifold.security.encryption import EncryptionService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/webhooks/{provider}", operation_id="ingestEmailWebhook", include_in_schema=True)
async def ingest_email_webhook(
    request: Request,
    provider: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    raw_body = await request.body()

    # Load provider config under master DEK so EncryptedJSON columns decrypt correctly.
    async def _load_config() -> dict:
        row = await session.get(InstanceEmailSettings, "default")
        return dict(row.config or {}) if row is not None else {}

    config: dict = await with_master_dek(_load_config)

    try:
        transport = get_transport(provider, config)
    except ValueError:
        return Response(status_code=404)

    # Signature verification is sync per the Protocol definition.
    ok = transport.verify_webhook(dict(request.headers), raw_body)
    if not ok:
        return Response(status_code=401)

    try:
        payload: dict = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return Response(status_code=400)

    events = transport.parse_webhook(payload)

    async def _persist() -> None:
        master_key = EncryptionService().dek_master_key

        for event in events:
            addr = event.address.strip().lower()
            digest = hmac.new(master_key, addr.encode(), hashlib.sha256).digest()

            existing = await session.execute(
                select(EmailSuppression).where(EmailSuppression.address_hmac == digest)
            )
            if existing.scalar_one_or_none() is None:
                session.add(
                    EmailSuppression(
                        address_hmac=digest,
                        reason=event.reason,
                        source=provider,
                    )
                )
                logger.info(
                    "email.suppression_added",
                    reason=event.reason,
                    source=provider,
                )

        event_type: str = (
            payload.get("Type") or payload.get("event") or payload.get("type") or "unknown"
        )
        session.add(
            EmailWebhookEvent(
                provider=provider,
                event_type=str(event_type),
                raw=payload,
            )
        )

        await session.commit()

    await with_master_dek(_persist)

    return Response(status_code=200)


__all__ = ["router"]
