from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.database import get_session
from manifold.logging import session_id_var, user_id_var
from manifold.models.user import RefreshToken, User, UserSession
from manifold.security.encryption import EncryptionService


def _auth_error(detail: str = "unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": detail})


async def _decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, EncryptionService().jwt_signing_key, algorithms=["HS256"])
    except JWTError as exc:
        raise _auth_error() from exc


async def get_current_user_optional(
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
) -> User | None:
    token = access_token
    if token is None and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    if token is None:
        return None
    payload = await _decode_access_token(token)
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise _auth_error()
    user = await session.get(User, subject)
    if user is None or not user.is_active:
        raise _auth_error()
    user_id_var.set(str(user.id))
    return user


async def get_current_user(
    current_user: User | None = Depends(get_current_user_optional),
) -> User:
    if current_user is None:
        raise _auth_error()
    if current_user.must_change_password:
        raise HTTPException(status_code=403, detail={"error": "password_change_required"})
    return current_user


async def get_current_user_allow_password_change(
    current_user: User | None = Depends(get_current_user_optional),
) -> User:
    if current_user is None:
        raise _auth_error()
    return current_user


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return current_user


async def get_current_session(
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None),
) -> UserSession | None:
    if refresh_token is None:
        return None
    token_hash = EncryptionService().hash_token(refresh_token)
    stmt = (
        select(UserSession)
        .join(RefreshToken, RefreshToken.session_id == UserSession.id)
        .where(RefreshToken.token_hash == token_hash)
    )
    result = await session.execute(stmt)
    current_session = result.scalar_one_or_none()
    if current_session is not None:
        session_id_var.set(str(current_session.id))
    return current_session


async def revoke_session_tokens(
    session: AsyncSession,
    session_id: str,
    reason: str | None = None,
) -> None:
    now = datetime.now(UTC)
    current_session = await session.get(UserSession, session_id)
    if current_session is not None and current_session.revoked_at is None:
        current_session.revoked_at = now
        current_session.revoke_reason = reason
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.session_id == session_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
