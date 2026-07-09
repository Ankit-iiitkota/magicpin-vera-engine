"""
vera.engine.anti_repetition — AntiRepetitionGuard.

challenge-testing-brief.md §10: "Bot returns the same body verbatim it
sent before in the same conversation" is explicitly penalised (-2 per
repeat). Async, store-backed — same reasoning as SuppressionGuard for
why this lives outside compose(): the API layer checks is_repeat()
against the rendered body before including it in a response, and calls
mark_sent() after actually sending it.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.store.base_store import BaseContextStore

__all__ = ["AntiRepetitionGuard"]

_DEFAULT_TTL_SECONDS = 172_800  # 48h — matches BaseContextStore.SCOPE_TTL's conversation default


class AntiRepetitionGuard:
    def __init__(self, store: BaseContextStore) -> None:
        self._store = store

    async def is_repeat(self, conversation_id: str, body: str) -> bool:
        return await self._store.check_seen(conversation_id, self._hash(body))

    async def mark_sent(
        self, conversation_id: str, body: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS
    ) -> None:
        await self._store.set_seen(conversation_id, self._hash(body), ttl_seconds)

    @staticmethod
    def _hash(body: str) -> str:
        normalised = " ".join(body.strip().lower().split())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
