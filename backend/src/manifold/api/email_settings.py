from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api._crypto import with_master_dek
from manifold.api.deps import get_session, require_superadmin
from manifold.config import settings
from manifold.email.factory import get_transport
from manifold.email.message import EmailMessage
from manifold.models.email_settings import InstanceEmailSettings
from manifold.models.email_suppression import EmailSuppression
from manifold.models.user import User
from manifold.schemas.email_settings import (
    EmailSettingsResponse,
    EmailSettingsTestRequest,
    EmailSettingsUpdateRequest,
    SuppressionCreateRequest,
    SuppressionListResponse,
    SuppressionResponse,
)
from manifold.security.encryption import EncryptionService

router = APIRouter()

# Keys whose values must be masked on read and whose blank/sentinel
# incoming values mean "keep the existing secret unchanged".
_SECRET_KEYS = frozenset(
    (
        "api_key",
        "password",
        "secret_access_key",
        "webhook_secret",
        "webhook_signing_key",
        "webhook_token",
    )
)

_MASK = "********"


def _mask_config(config: dict | None) -> dict | None:
    """Return a copy of config with secret values replaced by _MASK (or None if absent)."""
    if config is None:
        return None
    masked: dict = {}
    for k, v in config.items():
        if k in _SECRET_KEYS:
            masked[k] = _MASK if v else None
        else:
            masked[k] = v
    return masked


def _serialize_settings(row: InstanceEmailSettings) -> dict:
    return {
        "provider": row.provider,
        "config": _mask_config(dict(row.config) if row.config else None),
        "from_address": row.from_address,
        "from_name": row.from_name,
        "is_configured": row.is_configured,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _env_bootstrap_response() -> dict:
    """Synthesize a response from env vars when no DB row exists yet."""
    return {
        "provider": "smtp",
        "config": {
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "use_tls": settings.smtp_use_tls,
            "username": settings.smtp_user,
            # Mask the env password the same way we mask DB secrets.
            "password": _MASK if settings.smtp_password else None,
        },
        "from_address": settings.smtp_from_address or None,
        "from_name": None,
        "is_configured": False,
        "created_at": None,
        "updated_at": None,
    }


@router.get("", operation_id="getEmailSettings", response_model=EmailSettingsResponse)
async def get_email_settings(
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> EmailSettingsResponse:
    async def _get() -> dict:
        row = await session.get(InstanceEmailSettings, "default")
        if row is None:
            return _env_bootstrap_response()
        return _serialize_settings(row)

    return await with_master_dek(_get)


@router.put("", operation_id="updateEmailSettings", response_model=EmailSettingsResponse)
async def update_email_settings(
    payload: EmailSettingsUpdateRequest,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> EmailSettingsResponse:
    async def _update() -> dict:
        row = await session.get(InstanceEmailSettings, "default")
        existing_config: dict = dict(row.config) if (row and row.config) else {}

        # Build merged_config: for secret keys, sentinel/blank → keep existing.
        merged_config: dict = {}
        for k, v in payload.config.items():
            if k in _SECRET_KEYS and v in ("", None, _MASK):
                # Keep the previously stored secret if available, otherwise drop.
                if k in existing_config:
                    merged_config[k] = existing_config[k]
                # else: omit the key entirely (no prior value)
            else:
                merged_config[k] = v

        # Validate via the transport's own config validator.
        try:
            transport = get_transport(payload.provider, merged_config)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_config", "fields": [str(exc)]},
            ) from exc
        errors = transport.validate_config(merged_config)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_config", "fields": errors},
            )

        if row is None:
            row = InstanceEmailSettings(
                id="default",
                provider=payload.provider,
                config=merged_config,
                from_address=payload.from_address,
                from_name=payload.from_name,
                is_configured=True,
            )
        else:
            row.provider = payload.provider
            row.config = merged_config
            row.from_address = payload.from_address
            row.from_name = payload.from_name
            row.is_configured = True

        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _serialize_settings(row)

    return await with_master_dek(_update)


@router.post("/test", operation_id="testEmailSettings")
async def test_email_settings(
    payload: EmailSettingsTestRequest,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    async def _test() -> dict:
        row = await session.get(InstanceEmailSettings, "default")
        if row is not None:
            provider = row.provider
            real_config = dict(row.config) if row.config else {}
            from_addr = row.from_address or settings.smtp_from_address or None
        else:
            # Fall back to env SMTP config with real (unmasked) secrets.
            provider = "smtp"
            real_config = {
                "host": settings.smtp_host,
                "port": settings.smtp_port,
                "use_tls": settings.smtp_use_tls,
                "username": settings.smtp_user,
                "password": settings.smtp_password,
            }
            from_addr = settings.smtp_from_address or None

        try:
            transport = get_transport(provider, real_config)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        msg = EmailMessage(
            to=[payload.to_address],
            subject="Manifold test email",
            html_body="<p>Manifold test email</p>",
            text_body="Manifold test email",
            from_address=from_addr,
        )
        try:
            message_id = await transport.send(msg)
            return {"ok": True, "message_id": message_id}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    return await with_master_dek(_test)


@router.get(
    "/suppressions",
    operation_id="listEmailSuppressions",
    response_model=SuppressionListResponse,
)
async def list_suppressions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> SuppressionListResponse:
    async def _list() -> dict:
        total_result = await session.execute(
            select(func.count()).select_from(EmailSuppression.__table__)
        )
        total = total_result.scalar_one()
        result = await session.execute(
            select(EmailSuppression)
            .order_by(EmailSuppression.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            {
                "id": str(row.id),
                "address_hmac": row.address_hmac.hex(),
                "reason": row.reason,
                "source": row.source,
                "created_at": row.created_at,
            }
            for row in result.scalars().all()
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    return await with_master_dek(_list)


@router.post(
    "/suppressions",
    operation_id="createEmailSuppression",
    response_model=SuppressionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_suppression(
    payload: SuppressionCreateRequest,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> SuppressionResponse:
    async def _create() -> dict:
        # Normalise: lowercase + strip whitespace only (preserve dots/plus per R8).
        normalized = payload.address.strip().lower()
        digest = hmac.new(
            EncryptionService().dek_master_key,
            normalized.encode(),
            hashlib.sha256,
        ).digest()

        # Idempotent upsert — return existing row if present.
        existing = await session.execute(
            select(EmailSuppression).where(EmailSuppression.address_hmac == digest)
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = EmailSuppression(
                address_hmac=digest,
                reason=payload.reason or "manual",
                source="superadmin",
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return {
            "id": str(row.id),
            "address_hmac": row.address_hmac.hex(),
            "reason": row.reason,
            "source": row.source,
            "created_at": row.created_at,
        }

    return await with_master_dek(_create)


@router.delete(
    "/suppressions/{suppression_id}",
    operation_id="deleteEmailSuppression",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_suppression(
    suppression_id: str,
    current_user: User = Depends(require_superadmin),
    session: AsyncSession = Depends(get_session),
) -> None:
    async def _delete() -> None:
        row = await session.get(EmailSuppression, suppression_id)
        if row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found"})
        await session.delete(row)
        await session.commit()

    await with_master_dek(_delete)


__all__ = ["router"]
