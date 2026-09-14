"""Redis: rate-limit buckets, access-token blacklist, last_active debounce, settings cache.

ARCHITECTURE.md §8.4 — losing Redis degrades rather than stops the platform:
rate limiting falls open with a logged warning, the token blacklist check fails
closed (a 401 rather than an unchecked token), and the app stays up.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from backend.config.settings_env import get_env_settings

log = logging.getLogger(__name__)

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        env = get_env_settings()
        _client = aioredis.from_url(
            env.REDIS_URL, encoding="utf-8", decode_responses=True, socket_timeout=2
        )
    return _client


def override_redis(client: aioredis.Redis) -> None:
    """Used by the test suite."""
    global _client
    _client = client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


class RedisUnavailable(Exception):
    """Raised inside this module only; callers decide how to degrade."""


async def incr_with_expiry(key: str, window_seconds: int) -> int:
    """Increment a counter and set its expiry on first use. Returns the count."""
    client = get_redis()
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds, nx=True)
    count, _ = await pipe.execute()
    return int(count)


async def ttl(key: str) -> int:
    return int(await get_redis().ttl(key))


async def set_if_absent(key: str, value: str, ttl_seconds: int) -> bool:
    return bool(await get_redis().set(key, value, ex=ttl_seconds, nx=True))


async def blacklist_jti(jti: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    await get_redis().set(f"jti:blacklist:{jti}", "1", ex=ttl_seconds)


async def is_jti_blacklisted(jti: str) -> bool:
    """Fails closed: if Redis cannot answer, the token is treated as revoked."""
    try:
        return bool(await get_redis().exists(f"jti:blacklist:{jti}"))
    except Exception:
        log.warning("redis_unavailable_blacklist_fails_closed", exc_info=True)
        return True


async def cache_get(key: str) -> str | None:
    try:
        return await get_redis().get(key)
    except Exception:
        log.warning("redis_unavailable_cache_miss", extra={"key": key})
        return None


async def cache_set(key: str, value: str, ttl_seconds: int) -> None:
    try:
        await get_redis().set(key, value, ex=ttl_seconds)
    except Exception:
        log.warning("redis_unavailable_cache_not_written", extra={"key": key})


async def cache_delete_prefix(prefix: str) -> None:
    try:
        client = get_redis()
        async for key in client.scan_iter(match=f"{prefix}*"):
            await client.delete(key)
    except Exception:
        log.warning("redis_unavailable_cache_not_cleared", extra={"prefix": prefix})
