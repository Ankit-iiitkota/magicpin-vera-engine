"""
vera.store.memory_store — In-memory context store (dict-backed).

Used when Redis is unavailable or when running tests.
Provides the exact same async interface as RedisContextStore.
Data is NOT persistent across restarts.

Thread safety: uses asyncio.Lock per scope for concurrent request safety.
TTL: implemented via explicit expiry timestamps (monotonic clock).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from vera.store.base_store import BaseContextStore


class _ExpiringEntry:
    """Wraps a value with an optional absolute expiry time."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: str, ttl_seconds: int | None) -> None:
        self.value = value
        self.expires_at: float | None = (
            time.monotonic() + ttl_seconds if ttl_seconds is not None else None
        )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.monotonic() > self.expires_at


class InMemoryContextStore(BaseContextStore):
    """
    Pure in-memory implementation of BaseContextStore.

    All data lives in a single dict keyed by the canonical string key.
    A single asyncio.Lock serialises writes to avoid race conditions
    within the same event loop.
    """

    def __init__(self) -> None:
        self._data: dict[str, _ExpiringEntry] = {}
        self._lock = asyncio.Lock()

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _get_raw(self, key: str) -> str | None:
        """Return raw value or None if absent / expired."""
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._data[key]
            return None
        return entry.value

    async def _set_raw(self, key: str, value: str, ttl_seconds: int | None) -> None:
        async with self._lock:
            self._data[key] = _ExpiringEntry(value, ttl_seconds)

    async def _del_raw(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def _exists(self, key: str) -> bool:
        return await self._get_raw(key) is not None

    # ── Context CRUD ──────────────────────────────────────────────────────────

    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        raw = await self._get_raw(self.context_key(scope, context_id))
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
        await self._set_raw(
            self.context_key(scope, context_id),
            self._serialise(version, payload),
            ttl,
        )

    async def delete(self, scope: str, context_id: str) -> None:
        await self._del_raw(self.context_key(scope, context_id))

    async def count_by_scope(self, scope: str) -> int:
        prefix = f"ctx:{scope}:"
        # Purge expired entries lazily while counting
        expired = [k for k, v in self._data.items() if k.startswith(prefix) and v.is_expired()]
        for k in expired:
            self._data.pop(k, None)
        return sum(1 for k in self._data if k.startswith(prefix))

    async def count_all(self) -> dict[str, int]:
        # Purge all expired entries
        expired = [k for k, v in self._data.items() if v.is_expired()]
        for k in expired:
            self._data.pop(k, None)

        scopes: dict[str, int] = {}
        for key in self._data:
            if key.startswith("ctx:"):
                parts = key.split(":", 2)
                if len(parts) >= 2:
                    scope = parts[1]
                    scopes[scope] = scopes.get(scope, 0) + 1
        return scopes

    async def flush_all(self) -> None:
        async with self._lock:
            self._data.clear()

    # ── Suppression ───────────────────────────────────────────────────────────

    async def check_suppression(self, suppression_key: str) -> bool:
        return await self._exists(self.suppression_key(suppression_key))

    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        await self._set_raw(self.suppression_key(suppression_key), "1", ttl_seconds)

    # ── Seen-body dedup ───────────────────────────────────────────────────────

    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        return await self._exists(self.seen_key(conversation_id, body_hash))

    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        await self._set_raw(self.seen_key(conversation_id, body_hash), "1", ttl_seconds)

    # ── Health / lifecycle ────────────────────────────────────────────────────

    async def ping(self) -> bool:
        return True  # In-memory is always reachable

    async def close(self) -> None:
        pass  # No connections to release

    @property
    def backend_name(self) -> str:
        return "memory"
