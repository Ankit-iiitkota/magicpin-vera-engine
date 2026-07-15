"""
vera.store.context_repository — ContextRepository (Repository Pattern).

Sits above BaseContextStore, which only knows how to persist an opaque
{version, payload} envelope under a scope+id key — its own docstring
says so explicitly: "The caller is responsible for version conflict
logic." ContextRepository is that caller. It owns the version-
comparison semantics POST /v1/context needs
(challenge-testing-brief.md §2.1):

    - no existing record            -> create
    - version == stored version     -> no-op (idempotent)
    - version >  stored version     -> atomic replace
    - version <  stored version     -> reject (stale_version)

It is deliberately domain-agnostic: it stores whatever payload dict the
caller gives it under whatever scope string the caller gives it
("category" | "merchant" | "customer" | "trigger" for context pushes,
plus e.g. "conversation" for other engine-internal uses in later
phases). Domain-shape validation (does this payload look like a
MerchantContext?) is the API layer's job, not the repository's — see
vera.api.endpoints.context.

Reserved scopes: vera.store.conversation_store.ConversationStore writes
directly to the same underlying BaseContextStore, under its own
dedicated "conversation_state" scope, using a raw dataclass dict — not
this repository's {payload, delivered_at, stored_at} envelope. The two
formats are incompatible, so ContextRepository refuses to read or write
any scope ConversationStore owns (see _RESERVED_SCOPES below); doing so
would either corrupt ConversationStore's records or blow up trying to
unwrap them as if they were ours.

Concurrency: a per-(scope, context_id) asyncio.Lock guards the
read-compare-write sequence in save_context(), so two concurrent
pushes for the same context can never race each other within this
process. The project runs as a single worker (see Dockerfile:
--workers 1), so process-local locking is sufficient — no distributed
locking is needed.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

from vera.store.conversation_store import ConversationStore
from vera.utils.time_utils import utcnow_iso

if TYPE_CHECKING:
    from vera.store.base_store import BaseContextStore

logger = structlog.get_logger(__name__)

#: Scopes owned exclusively by other storage contracts. ContextRepository
#: must never read or write these — see the module docstring.
_RESERVED_SCOPES = frozenset({ConversationStore.SCOPE})


class SaveStatus(StrEnum):
    """What save_context() actually did."""

    CREATED = "created"  # no prior record existed for this (scope, context_id)
    REPLACED = "replaced"  # version was higher than the stored one — atomic replace
    DUPLICATE = "duplicate"  # version matched the stored one — idempotent no-op
    STALE = "stale"  # version was lower than the stored one — rejected


@dataclass(frozen=True)
class SaveResult:
    """Outcome of a save_context() call."""

    status: SaveStatus
    version: int  # the version that was submitted
    current_version: int  # the version now stored (== `version` unless STALE)
    stored_at: str  # ISO-8601 timestamp of this ack


@dataclass(frozen=True)
class ContextRecord:
    """A stored context, unpacked from its envelope."""

    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str | None
    stored_at: str | None


class ContextRepository:
    """Versioned, idempotent persistence for the four context objects."""

    def __init__(self, store: BaseContextStore) -> None:
        self._store = store
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _lock_for(self, scope: str, context_id: str) -> asyncio.Lock:
        key = (scope, context_id)
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    @staticmethod
    def _assert_not_reserved(scope: str) -> None:
        if scope in _RESERVED_SCOPES:
            raise ValueError(
                f"scope={scope!r} is reserved for another storage contract "
                "(see ContextRepository's module docstring) — ContextRepository "
                "must not read or write it."
            )

    # ── Writes ────────────────────────────────────────────────────────────────

    async def save_context(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str | None = None,
    ) -> SaveResult:
        """
        Upsert a context, honouring version semantics.

        Atomic with respect to other save_context() calls for the same
        (scope, context_id) within this process.
        """
        self._assert_not_reserved(scope)
        lock = await self._lock_for(scope, context_id)
        async with lock:
            stored = await self._store.get(scope, context_id)
            stored_at = utcnow_iso()

            if stored is None:
                await self._write(scope, context_id, version, payload, delivered_at, stored_at)
                logger.info(
                    "context_saved",
                    scope=scope,
                    context_id=context_id,
                    version=version,
                    status=SaveStatus.CREATED.value,
                )
                return SaveResult(SaveStatus.CREATED, version, version, stored_at)

            current_version: int = stored["version"]

            if version == current_version:
                prior_stored_at = stored["payload"].get("stored_at", stored_at)
                logger.info(
                    "context_push_duplicate",
                    scope=scope,
                    context_id=context_id,
                    version=version,
                )
                return SaveResult(SaveStatus.DUPLICATE, version, current_version, prior_stored_at)

            if version < current_version:
                logger.warning(
                    "context_push_stale",
                    scope=scope,
                    context_id=context_id,
                    submitted_version=version,
                    current_version=current_version,
                )
                return SaveResult(SaveStatus.STALE, version, current_version, stored_at)

            await self._write(scope, context_id, version, payload, delivered_at, stored_at)
            logger.info(
                "context_saved",
                scope=scope,
                context_id=context_id,
                version=version,
                status=SaveStatus.REPLACED.value,
                previous_version=current_version,
            )
            return SaveResult(SaveStatus.REPLACED, version, version, stored_at)

    async def _write(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: str | None,
        stored_at: str,
    ) -> None:
        """Serialise payload + metadata into the envelope and persist it atomically."""
        wrapped = {"payload": payload, "delivered_at": delivered_at, "stored_at": stored_at}
        await self._store.set(scope, context_id, version, wrapped)

    async def delete_context(self, scope: str, context_id: str) -> None:
        self._assert_not_reserved(scope)
        await self._store.delete(scope, context_id)
        logger.info("context_deleted", scope=scope, context_id=context_id)

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_context(self, scope: str, context_id: str) -> ContextRecord | None:
        """Return the stored context, deserialised, or None if absent/expired."""
        self._assert_not_reserved(scope)
        stored = await self._store.get(scope, context_id)
        if stored is None:
            return None
        wrapped = stored["payload"]
        return ContextRecord(
            scope=scope,
            context_id=context_id,
            version=stored["version"],
            payload=wrapped["payload"],
            delivered_at=wrapped.get("delivered_at"),
            stored_at=wrapped.get("stored_at"),
        )

    async def context_exists(self, scope: str, context_id: str) -> bool:
        self._assert_not_reserved(scope)
        return await self._store.get(scope, context_id) is not None

    async def get_version(self, scope: str, context_id: str) -> int | None:
        self._assert_not_reserved(scope)
        stored = await self._store.get(scope, context_id)
        return stored["version"] if stored else None
