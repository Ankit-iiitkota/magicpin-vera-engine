"""
vera.store.redis_store — Redis-backed context store.

Uses redis-py 5.x async client (redis.asyncio).
Falls back gracefully if the connection is lost mid-flight
(callers receive the same errors they would from memory_store).

Key layout matches BaseContextStore conventions:
    ctx:{scope}:{context_id}   → JSON envelope {version, payload}
    sup:{suppression_key}      → "1"
    seen:{conv_id}:{body_hash} → "1"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vera.store.base_store import BaseContextStore

if TYPE_CHECKING:
    import redis.asyncio as aioredis


class RedisContextStore(BaseContextStore):
    """
    Redis-backed implementation of BaseContextStore.

    Accepts an already-connected redis.asyncio.Redis client so that
    connection management lives in store_factory.py.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._r = client

    # ── Context CRUD ──────────────────────────────────────────────────────────

    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        raw: bytes | None = await self._r.get(self.context_key(scope, context_id))
        if raw is None:
            return None
        return self._deserialise(raw)

    async def set(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.ttl_for_scope(scope)
        await self._r.setex(
            self.context_key(scope, context_id),
            ttl,
            self._serialise(version, payload),
        )

    async def delete(self, scope: str, context_id: str) -> None:
        await self._r.delete(self.context_key(scope, context_id))

    async def count_by_scope(self, scope: str) -> int:
        """
        Count keys matching ctx:{scope}:*.

        Uses SCAN rather than KEYS to avoid blocking the Redis event loop.
        """
        pattern = f"ctx:{scope}:*"
        count = 0
        async for _ in self._r.scan_iter(match=pattern, count=200):
            count += 1
        return count

    async def count_all(self) -> dict[str, int]:
        """Scan all ctx:* keys and aggregate by scope."""
        scopes: dict[str, int] = {}
        async for key in self._r.scan_iter(match="ctx:*", count=200):
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            parts = key_str.split(":", 2)
            if len(parts) >= 2:
                scope = parts[1]
                scopes[scope] = scopes.get(scope, 0) + 1
        return scopes

    async def flush_all(self) -> None:
        """
        Delete all Vera-managed keys.

        Scans for ctx:*, sup:*, seen:* and deletes in batches.
        Does NOT call FLUSHDB to avoid nuking unrelated Redis data.
        """
        patterns = ["ctx:*", "sup:*", "seen:*", "conv:*"]
        pipeline = self._r.pipeline(transaction=False)
        for pattern in patterns:
            async for key in self._r.scan_iter(match=pattern, count=500):
                pipeline.delete(key)
        await pipeline.execute()

    # ── Suppression ───────────────────────────────────────────────────────────

    async def check_suppression(self, suppression_key: str) -> bool:
        return bool(await self._r.exists(self.suppression_key(suppression_key)))

    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        await self._r.setex(self.suppression_key(suppression_key), ttl_seconds, "1")

    # ── Seen-body dedup ───────────────────────────────────────────────────────

    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        return bool(await self._r.exists(self.seen_key(conversation_id, body_hash)))

    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        await self._r.setex(self.seen_key(conversation_id, body_hash), ttl_seconds, "1")

    # ── Health / lifecycle ────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._r.aclose()

    @property
    def backend_name(self) -> str:
        return "redis"
