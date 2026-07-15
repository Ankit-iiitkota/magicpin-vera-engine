"""
vera.store.base_store — Abstract base class for all context stores.

Both RedisContextStore and InMemoryContextStore implement this interface.
All methods are async to allow the Redis implementation to use native
async I/O without re-wrapping.

Key layout
----------
Context objects:  ctx:{scope}:{context_id}
Suppression keys: sup:{suppression_key}
Conversation:     conv:{conversation_id}
Seen-body hashes: seen:{conversation_id}:{body_hash}
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class BaseContextStore(ABC):
    """Abstract interface for the context persistence layer."""

    # ── Context CRUD ──────────────────────────────────────────────────────────

    @abstractmethod
    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        """
        Retrieve a stored context.

        Returns the stored dict (including 'version' and 'payload' keys)
        or None if not found / expired.
        """

    @abstractmethod
    async def set(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Upsert a context.

        The caller is responsible for version conflict logic.
        If ttl_seconds is None a scope-specific default is used.
        """

    @abstractmethod
    async def delete(self, scope: str, context_id: str) -> None:
        """Hard-delete a context."""

    @abstractmethod
    async def count_by_scope(self, scope: str) -> int:
        """Return the number of contexts stored under the given scope."""

    @abstractmethod
    async def count_all(self) -> dict[str, int]:
        """Return {scope: count} for every scope that has stored contexts."""

    @abstractmethod
    async def flush_all(self) -> None:
        """Delete ALL stored data (contexts + suppression keys + conversations). Used by teardown."""

    # ── Suppression ───────────────────────────────────────────────────────────

    @abstractmethod
    async def check_suppression(self, suppression_key: str) -> bool:
        """Return True if the suppression key is currently active."""

    @abstractmethod
    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        """Record a suppression key with the given TTL."""

    # ── Seen-body dedup ───────────────────────────────────────────────────────

    @abstractmethod
    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        """Return True if this body hash has already been sent in this conversation."""

    @abstractmethod
    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        """Mark a body hash as sent. Default TTL = 48 h."""

    # ── Health / lifecycle ────────────────────────────────────────────────────

    @abstractmethod
    async def ping(self) -> bool:
        """Return True if the backing store is reachable."""

    @abstractmethod
    async def close(self) -> None:
        """Release connections / resources."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier: 'redis' | 'memory'."""

    # ── Helpers (shared by both implementations) ──────────────────────────────

    @staticmethod
    def context_key(scope: str, context_id: str) -> str:
        """Canonical key for a context object."""
        return f"ctx:{scope}:{context_id}"

    @staticmethod
    def suppression_key(key: str) -> str:
        """Canonical key for a suppression entry."""
        return f"sup:{key}"

    @staticmethod
    def seen_key(conversation_id: str, body_hash: str) -> str:
        """Canonical key for a seen-body hash entry."""
        return f"seen:{conversation_id}:{body_hash}"

    # ── Default TTLs (seconds) ────────────────────────────────────────────────

    SCOPE_TTL: dict[str, int] = {
        "category": 86_400,  # 24 h
        "merchant": 21_600,  # 6 h
        "customer": 21_600,  # 6 h
        "trigger": 86_400,  # 24 h (overridden by trigger.expires_at in Phase 2)
        "conversation_state": 172_800,  # 48 h — ConversationStore's dedicated scope
    }
    DEFAULT_TTL: int = 21_600  # 6 h fallback for unknown scopes

    def ttl_for_scope(self, scope: str) -> int:
        """Return the default TTL in seconds for a given scope."""
        return self.SCOPE_TTL.get(scope, self.DEFAULT_TTL)

    # ── Serialisation helpers ─────────────────────────────────────────────────

    @staticmethod
    def _serialise(version: int, payload: dict[str, Any]) -> str:
        """Serialise the envelope {version, payload} to a JSON string."""
        return json.dumps({"version": version, "payload": payload}, default=str)

    @staticmethod
    def _deserialise(raw: str | bytes) -> dict[str, Any]:
        """Deserialise a JSON string back to the envelope dict."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
