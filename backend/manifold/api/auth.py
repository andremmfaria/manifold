from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.api.deps import (
    get_current_session,
    get_current_user,
    get_current_user_allow_password_change,
    get_session,
    revoke_session_tokens,
)
from manifold.config import settings
from manifold.domain.users import hash_password, verify_password
from manifold.models.user import RefreshToken, User, UserSession
from manifold.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    SessionResponse,
    TokenResponse,
)
from manifold.security.encryption import EncryptionService

router = APIRouter()

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
DEVICE_COOKIE_NAME = "device_binding"


def _cookie_params(max_age: int) -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.secure_cookies,
        "max_age": max_age,
        "path": "/",
    }


def _serialize_me(user: User) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        username=user.username,
        role=user.role,
        mustChangePassword=user.must_change_password,
    )


def _issue_access_token(user: User) -> tuple[str, int]:
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    token = jwt.encode(payload, EncryptionService().jwt_signing_key, algorithm="HS256")
    return token, expires_in


async def _create_refresh_token(
    session: AsyncSession,
    user: User,
    user_session: UserSession,
) -> str:
    raw_token = secrets.token_urlsafe(48)
    token_hash = EncryptionService().hash_token(raw_token)
    refresh = RefreshToken(
        user_id=user.id,
        session_id=user_session.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(refresh)
    await session.flush()
    return raw_token


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})

    device_cookie = secrets.token_urlsafe(32)
    user_session = UserSession(
        user_id=user.id,
        device_cookie_hash=EncryptionService().hash_token(device_cookie),
        device_label=request.headers.get("x-device-label"),
        user_agent=request.headers.get("user-agent"),
        ip_first=request.client.host if request.client else None,
        ip_last=request.client.host if request.client else None,
    )
    session.add(user_session)
    await session.flush()
    refresh_token = await _create_refresh_token(session, user, user_session)
    access_token, expires_in = _issue_access_token(user)
    await session.commit()

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        **_cookie_params(expires_in),
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        **_cookie_params(settings.refresh_token_expire_days * 86400),
    )
    response.set_cookie(DEVICE_COOKIE_NAME, device_cookie, **_cookie_params(90 * 86400))
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None),
) -> Response:
    if refresh_token:
        token_hash = EncryptionService().hash_token(refresh_token)
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_row = result.scalar_one_or_none()
        if token_row is not None:
            await revoke_session_tokens(session, str(token_row.session_id), reason="logout")
            await session.commit()
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    response.delete_cookie(DEVICE_COOKIE_NAME, path="/")
    return response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None),
    device_binding: str | None = Cookie(default=None),
) -> TokenResponse:
    if not refresh_token or not device_binding:
        raise HTTPException(status_code=401, detail={"error": "refresh_failed"})
    token_hash = EncryptionService().hash_token(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_row = result.scalar_one_or_none()
    if (
        token_row is None
        or token_row.revoked_at is not None
        or token_row.expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(status_code=401, detail={"error": "refresh_failed"})
    user_session = await session.get(UserSession, token_row.session_id)
    if user_session is None or user_session.revoked_at is not None:
        raise HTTPException(status_code=401, detail={"error": "refresh_failed"})
    if user_session.device_cookie_hash != EncryptionService().hash_token(device_binding):
        await revoke_session_tokens(session, str(user_session.id), reason="device_mismatch")
        await session.commit()
        raise HTTPException(status_code=401, detail={"error": "refresh_failed"})

    user = await session.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": "refresh_failed"})

    token_row.revoked_at = datetime.now(UTC)
    user_session.last_seen_at = datetime.now(UTC)
    refresh_raw = await _create_refresh_token(session, user, user_session)
    access_token, expires_in = _issue_access_token(user)
    await session.commit()

    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        **_cookie_params(expires_in),
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_raw,
        **_cookie_params(settings.refresh_token_expire_days * 86400),
    )
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    return _serialize_me(current_user)


@router.patch("/me/password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user_allow_password_change),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})
    current_user.password_hash = hash_password(payload.new_password)
    current_user.must_change_password = False
    await session.commit()
    return Response(status_code=204)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SessionResponse]:
    result = await session.execute(
        select(UserSession).where(UserSession.user_id == current_user.id)
    )
    sessions = result.scalars().all()
    return [
        SessionResponse(
            id=str(item.id),
            device_label=item.device_label,
            user_agent=item.user_agent,
            ip_first=item.ip_first,
            ip_last=item.ip_last,
            last_seen_at=item.last_seen_at.isoformat(),
            created_at=item.created_at.isoformat(),
            revoked_at=item.revoked_at.isoformat() if item.revoked_at else None,
        )
        for item in sessions
        if item.revoked_at is None
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    item = await session.get(UserSession, session_id)
    if item is None or str(item.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    await revoke_session_tokens(session, session_id, reason="user_revoked")
    await session.commit()
    return Response(status_code=204)


@router.post("/sessions/revoke-others", status_code=204)
async def revoke_other_sessions(
    current_user: User = Depends(get_current_user),
    current_session: UserSession | None = Depends(get_current_session),
    session: AsyncSession = Depends(get_session),
) -> Response:
    result = await session.execute(
        select(UserSession).where(UserSession.user_id == current_user.id)
    )
    for item in result.scalars().all():
        if current_session and str(item.id) == str(current_session.id):
            continue
        await revoke_session_tokens(session, str(item.id), reason="revoke_others")
    await session.commit()
    return Response(status_code=204)
