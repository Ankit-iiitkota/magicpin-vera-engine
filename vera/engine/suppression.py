"""
vera.engine.suppression — SuppressionGuard.

Async, store-backed — deliberately NOT part of compose() (which stays a
pure, synchronous function per challenge-brief.md §5). The API layer
(/v1/tick) checks is_suppressed() BEFORE deciding to compose+send for a
trigger, and calls mark_sent() AFTER a successful send. compose() never
touches the store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.store.base_store import BaseContextStore

__all__ = ["SuppressionGuard"]

_DEFAULT_TTL_SECONDS = 86_400  # 24h — matches BaseContextStore.SCOPE_TTL's trigger default


class SuppressionGuard:
    def __init__(self, store: BaseContextStore) -> None:
        self._store = store

    async def is_suppressed(self, suppression_key: str) -> bool:
        return await self._store.check_suppression(suppression_key)

    async def mark_sent(
        self, suppression_key: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._store.set_suppression(suppression_key, ttl_seconds)
