"""Shared pytest fixtures and test doubles."""

from __future__ import annotations

from typing import Any

from vera.store.base_store import BaseContextStore


class AlwaysFailsStore(BaseContextStore):
    """
    Test double whose every operation raises, simulating a dead Redis.

    Used to deterministically exercise ResilientContextStore's fallback
    behaviour without needing a real Redis instance to kill.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error or ConnectionError("simulated Redis outage")

    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        raise self._error

    async def set(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        raise self._error

    async def delete(self, scope: str, context_id: str) -> None:
        raise self._error

    async def count_by_scope(self, scope: str) -> int:
        raise self._error

    async def count_all(self) -> dict[str, int]:
        raise self._error

    async def flush_all(self) -> None:
        raise self._error

    async def check_suppression(self, suppression_key: str) -> bool:
        raise self._error

    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        raise self._error

    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        raise self._error

    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        raise self._error

    async def ping(self) -> bool:
        raise self._error

    async def close(self) -> None:
        pass  # closing a dead store must never itself raise

    @property
    def backend_name(self) -> str:
        return "always_fails"
