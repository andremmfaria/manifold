from __future__ import annotations

from datetime import UTC, datetime

from passlib.context import CryptContext
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.database import db_session
from manifold.exceptions import ConflictError
from manifold.models.user import RefreshToken, User
from manifold.security.encryption import EncryptionService

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


async def create_user_record(
    username: str,
    password: str,
    role: str,
    session: AsyncSession | None = None,
    email: str | None = None,
    must_change_password: bool = False,
) -> User:
    owns_session = session is None
    service = EncryptionService()
    if owns_session:
        async with db_session() as own_session:
            return await create_user_record(
                username=username,
                password=password,
                role=role,
                session=own_session,
                email=email,
                must_change_password=must_change_password,
            )

    assert session is not None
    existing = await session.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("username already exists")

    dek = service.generate_dek()
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
        must_change_password=must_change_password,
        encrypted_dek=service.encrypt_dek(dek),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def count_active_superadmins(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == "superadmin", User.is_active.is_(True))
    )
    return int(result.scalar_one())


async def deactivate_user(session: AsyncSession, user: User) -> None:
    if (
        user.role == "superadmin"
        and user.is_active
        and await count_active_superadmins(session) <= 1
    ):
        raise ConflictError("last active superadmin")
    user.is_active = False
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.commit()
