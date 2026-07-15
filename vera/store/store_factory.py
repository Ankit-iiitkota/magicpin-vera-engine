"""
vera.store.store_factory — Store creation and auto-fallback.

Attempts to connect to Redis using the configured URL.
If Redis is unreachable (and fallback_to_memory is True), silently
falls back to the in-memory store so the engine always starts.

Usage (called once in vera.main lifespan):

    store = await create_store(settings)
    app.state.store = store
    ...
    await store.close()  # on shutdown
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vera.store.memory_store import InMemoryContextStore
from vera.store.redis_store import RedisContextStore
from vera.store.resilient_store import ResilientContextStore

if TYPE_CHECKING:
    from vera.config import Settings
    from vera.store.base_store import BaseContextStore

logger = structlog.get_logger(__name__)


async def create_store(settings: Settings) -> BaseContextStore:
    """
    Create and return the appropriate context store.

    Tries Redis first. If the connection fails and
    settings.redis_fallback_to_memory is True, returns an InMemoryContextStore.
    Otherwise re-raises the connection error.

    A Redis store that connects successfully here can still fail later —
    mid-test outages, container restarts, network blips. When
    redis_fallback_to_memory is True, the Redis store is wrapped in
    ResilientContextStore so a later failure degrades to an in-memory
    backend transparently instead of raising through every subsequent
    request for the rest of the process's life.
    """
    try:
        store = await _connect_redis(settings)
        logger.info(
            "store_connected",
            backend="redis",
            url=_mask_url(settings.computed_redis_url),
        )
        if settings.redis_fallback_to_memory:
            return ResilientContextStore(
                primary=store,
                fallback=InMemoryContextStore(),
                primary_timeout_seconds=float(settings.redis_connect_timeout),
            )
        return store

    except Exception as exc:
        if settings.redis_fallback_to_memory:
            logger.warning(
                "store_redis_unavailable_falling_back",
                error=str(exc),
                backend="memory",
            )
            return InMemoryContextStore()
        logger.error("store_redis_connection_failed", error=str(exc))
        raise


async def _connect_redis(settings: Settings) -> RedisContextStore:
    """
    Create a redis.asyncio client, verify connectivity with PING,
    and wrap it in RedisContextStore.
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url(
        settings.computed_redis_url,
        socket_connect_timeout=settings.redis_connect_timeout,
        socket_timeout=settings.redis_connect_timeout,
        decode_responses=False,  # We handle decoding ourselves
    )
    # Eagerly verify the connection
    await client.ping()
    return RedisContextStore(client)


def _mask_url(url: str) -> str:
    """Redact the password component from a Redis URL for safe logging."""
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return url
