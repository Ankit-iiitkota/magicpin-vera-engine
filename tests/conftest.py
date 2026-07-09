"""Shared pytest fixtures, test doubles, and context factories."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from vera.contexts import CategoryContext, CustomerContext, MerchantContext, TriggerContext
from vera.features import FeatureExtractor
from vera.store.base_store import BaseContextStore

#: A fixed "now" for every test that needs determinism — Sunday, so
#: `temporal.weekend` is True by default unless a test overrides `now`.
NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


# ── Minimal context factories — only the Pydantic-required fields, so
#    tests can build "the smallest legal context" and override just what
#    they care about. Shared across features/signals/goals/candidates/
#    ranking/composer tests. ──────────────────────────────────────────────


def make_category(**overrides: Any) -> CategoryContext:
    data: dict[str, Any] = {"slug": "dentists", "voice": {"tone": "peer_clinical"}}
    data.update(overrides)
    return CategoryContext.model_validate(data)


def make_merchant(**overrides: Any) -> MerchantContext:
    data: dict[str, Any] = {
        "merchant_id": "m_001",
        "category_slug": "dentists",
        "identity": {
            "name": "Dr. Meera's Dental Clinic",
            "verified": True,
            "city": "Delhi",
            "locality": "Lajpat Nagar",
        },
        "subscription": {"status": "active"},
        "performance": {},
    }
    data.update(overrides)
    return MerchantContext.model_validate(data)


def make_trigger(**overrides: Any) -> TriggerContext:
    data: dict[str, Any] = {
        "id": "trg_001",
        "scope": "merchant",
        "kind": "research_digest",
        "source": "external",
        "suppression_key": "research:dentists:2026-W17",
        "expires_at": "2026-05-03T00:00:00Z",
    }
    data.update(overrides)
    return TriggerContext.model_validate(data)


def make_customer(**overrides: Any) -> CustomerContext:
    data: dict[str, Any] = {
        "customer_id": "c_001",
        "merchant_id": "m_001",
        "identity": {"name": "Priya"},
        "relationship": {},
        "state": "active",
        "preferences": {},
        "consent": {},
    }
    data.update(overrides)
    return CustomerContext.model_validate(data)


def extract_features(
    *,
    category: CategoryContext | None = None,
    merchant: MerchantContext | None = None,
    trigger: TriggerContext | None = None,
    customer: CustomerContext | None = None,
    now: datetime = NOW,
):
    """Build a FeatureSet from factory defaults, overridable per-arg."""
    return FeatureExtractor().extract(
        category or make_category(),
        merchant or make_merchant(),
        trigger or make_trigger(),
        customer=customer,
        now=now,
    )


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


class HangingStore(BaseContextStore):
    """
    Test double whose every operation awaits forever, simulating a
    Redis that accepts a connection but stalls on a command (a blocked
    write path, a half-open socket) rather than raising outright.

    Used to prove ResilientContextStore's primary_timeout_seconds bound
    actually kicks in — AlwaysFailsStore only exercises the "primary
    raises quickly" path, not "primary never returns at all".
    """

    async def _hang(self) -> None:
        await asyncio.Event().wait()

    async def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        await self._hang()
        return None

    async def set(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        await self._hang()

    async def delete(self, scope: str, context_id: str) -> None:
        await self._hang()

    async def count_by_scope(self, scope: str) -> int:
        await self._hang()
        return 0

    async def count_all(self) -> dict[str, int]:
        await self._hang()
        return {}

    async def flush_all(self) -> None:
        await self._hang()

    async def check_suppression(self, suppression_key: str) -> bool:
        await self._hang()
        return False

    async def set_suppression(self, suppression_key: str, ttl_seconds: int) -> None:
        await self._hang()

    async def check_seen(self, conversation_id: str, body_hash: str) -> bool:
        await self._hang()
        return False

    async def set_seen(
        self, conversation_id: str, body_hash: str, ttl_seconds: int = 172800
    ) -> None:
        await self._hang()

    async def ping(self) -> bool:
        await self._hang()
        return False

    async def close(self) -> None:
        pass  # closing a hung store must never itself raise

    @property
    def backend_name(self) -> str:
        return "hanging"
