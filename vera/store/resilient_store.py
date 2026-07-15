"""
vera.store.resilient_store — runtime Redis-failure fallback.

store_factory.create_store() already falls back to InMemoryContextStore
if Redis is unreachable at startup. That check runs exactly once — if
Redis is healthy at boot but drops mid-test (container restart, network
blip), every store call after that would raise unhandled and the
endpoint would 500, with no documented response shape.

ResilientContextStore closes that gap: it wraps a primary store and a
fallback store behind the same BaseContextStore interface. Every call
tries the primary first; the moment the primary raises OR fails to
return within `primary_timeout_seconds`, it logs once, flips to
"degraded", and both that call and every call after it go straight to
the fallback for the rest of the process's lifetime.

The explicit timeout matters beyond the connection-level timeouts
redis.asyncio is already given (see store_factory._connect_redis): a
managed Redis that accepts a connection/PING but then stalls on a
specific command (a blocked write path, a half-open connection) can
hang a coroutine well past those — and an unhandled hang on a request
path degrades into an upstream 502 at the platform's edge, not a clean
error response. Bounding every primary call here guarantees this store
always resolves (primary or fallback) within a bounded time.

No auto-recovery. Once degraded, this store does not retry the primary
— reconciling data written to the fallback during an outage with
whatever state the primary comes back with is a hard problem this
challenge's bounded 60-minute test window doesn't need solved, and
retrying a still-unhealthy primary on every call would just add
latency without benefit.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from vera.store.base_store import BaseContextStore

logger = structlog.get_logger(__name__)

_DEFAULT_PRIMARY_TIMEOUT_SECONDS = 5.0


class ResilientContextStore(BaseContextStore):
    """Drop-in BaseContextStore that degrades to `fallback` on primary failure."""

    def __init__(
        self,
        primary: BaseContextStore,
        fallback: BaseContextStore,
        primary_timeout_seconds: float = _DEFAULT_PRIMARY_TIMEOUT_SECONDS,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._degraded = False
        self._primary_timeout_seconds = primary_timeout_seconds

    async def _run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if not self._degraded:
            try:
                return await asyncio.wait_for(
                    getattr(self._primary, method)(*args, **kwargs),
                    timeout=self._primary_timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "store_primary_failed_degrading_to_fallback",
                    primary_backend=self._primary.backend_name,
                    fallback_backend=self._fallback.backend_name,
                    method=method,
                    error=str(exc),
                )
                self._degraded = True
        return await getattr(self._fallback, method)(*args, **kwargs)

    # ── Context CRUD ──────────────────────────────────────────────────────────

    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        return await self._run("get", scope, context_id)

    async def set(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        await self._run("set", scope, context_id, version, payload, ttl_seconds)

    async def delete(self, scope: str, context_id: str) -> None:
        await self._run("delete", scope, context_id)

    async def count_by_scope(self, scope: str) -> int:
        return await self._run("count_by_scope", scope)

    async def count_all(self) -> dict[str, int]:
        return await self._run("count_all")

    async def flush_all(self) -> None:
        await self._run("flush_all")

    # ── Suppression ───────────────────────────────────────────────────────────

    async def check_suppression(self, suppression_key: str) -> bool:
        return await self._run("check_suppression", suppression_key)

    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        await self._run("set_suppression", suppression_key, ttl_seconds)

    # ── Seen-body dedup ───────────────────────────────────────────────────────

    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        return await self._run("check_seen", conversation_id, body_hash)

    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        await self._run("set_seen", conversation_id, body_hash, ttl_seconds)

    # ── Health / lifecycle ────────────────────────────────────────────────────

    async def ping(self) -> bool:
        return await self._run("ping")

    async def close(self) -> None:
        for store in (self._primary, self._fallback):
            try:
                await store.close()
            except Exception as exc:
                logger.warning("store_close_failed", backend=store.backend_name, error=str(exc))

    @property
    def backend_name(self) -> str:
        return self._fallback.backend_name if self._degraded else self._primary.backend_name

    @property
    def degraded(self) -> bool:
        """True once the primary has failed at least once and been bypassed."""
        return self._degraded
