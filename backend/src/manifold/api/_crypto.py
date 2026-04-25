from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import TypeVar, overload

from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.user import User
from manifold.security.encryption import EncryptionService

T = TypeVar("T")


def parse_uuid(value: str) -> str:
    return str(value)


async def get_user_dek(session: AsyncSession, user_id: str) -> bytes:
    user = await session.get(User, parse_uuid(user_id))
    if user is None:
        raise RuntimeError("owner missing")
    return EncryptionService().decrypt_dek(user.encrypted_dek)


@contextmanager
def dek_context(dek: bytes):
    with EncryptionService().user_dek_context(dek):
        yield


@overload
async def with_user_dek(  # noqa: UP047
    session: AsyncSession,
    user_id: str,
    fn: Callable[[], Awaitable[T]],
) -> T: ...


@overload
async def with_user_dek(  # noqa: UP047
    session: AsyncSession,
    user_id: str,
    fn: Callable[[], T],
) -> T: ...


async def with_user_dek(  # noqa: UP047
    session: AsyncSession,
    user_id: str,
    fn: Callable[[], T | Awaitable[T]],
) -> T:
    dek = await get_user_dek(session, user_id)
    with dek_context(dek):
        result = fn()
        if inspect.isawaitable(result):
            return await result
        return result


def scope_to_uuids(scope: set[str]) -> list[str]:
    return [str(item) for item in scope]
