from __future__ import annotations

from redis.asyncio import from_url

from manifold.config import settings


async def acquire_lock(key: str, ttl: int = 300) -> bool:
    client = from_url(settings.redis_url)
    try:
        return bool(await client.set(f"manifold:{key}", "1", nx=True, ex=ttl))
    finally:
        await client.aclose()


async def release_lock(key: str) -> None:
    client = from_url(settings.redis_url)
    try:
        await client.delete(f"manifold:{key}")
    finally:
        await client.aclose()
