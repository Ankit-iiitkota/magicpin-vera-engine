"""
Unit tests for vera.store.resilient_store.ResilientContextStore.

Proves the runtime Redis-failure requirement directly: when the
primary store raises, calls transparently succeed against the
fallback instead of propagating the exception, and the store stays
degraded for the rest of its life (no flapping back to a
still-possibly-unhealthy primary on every call).
"""

from __future__ import annotations

import time

from tests.conftest import AlwaysFailsStore, HangingStore
from vera.store.memory_store import InMemoryContextStore
from vera.store.resilient_store import ResilientContextStore


async def test_healthy_primary_is_used_and_fallback_untouched() -> None:
    primary = InMemoryContextStore()
    fallback = InMemoryContextStore()
    store = ResilientContextStore(primary=primary, fallback=fallback)

    await store.set("merchant", "m_001", 1, {"name": "x"})

    assert store.degraded is False
    assert await primary.get("merchant", "m_001") is not None
    assert await fallback.get("merchant", "m_001") is None


async def test_primary_failure_falls_back_without_raising() -> None:
    store = ResilientContextStore(primary=AlwaysFailsStore(), fallback=InMemoryContextStore())

    # Must not raise — this is the whole point of the fix.
    await store.set("merchant", "m_001", 1, {"name": "x"})
    result = await store.get("merchant", "m_001")

    assert result is not None
    assert result["payload"] == {"name": "x"}
    assert store.degraded is True


async def test_stays_degraded_for_subsequent_calls() -> None:
    fallback = InMemoryContextStore()
    store = ResilientContextStore(primary=AlwaysFailsStore(), fallback=fallback)

    await store.set("merchant", "m_001", 1, {"name": "x"})  # triggers degrade
    assert store.degraded is True

    # A second, independent call must go straight to the fallback and
    # succeed too — no repeated attempt against the dead primary.
    await store.set("merchant", "m_002", 1, {"name": "y"})
    assert await store.get("merchant", "m_002") is not None
    assert await fallback.get("merchant", "m_002") is not None


async def test_backend_name_reflects_degraded_state() -> None:
    store = ResilientContextStore(primary=AlwaysFailsStore(), fallback=InMemoryContextStore())

    assert store.backend_name == "always_fails"
    await store.get("merchant", "m_001")
    assert store.backend_name == "memory"


async def test_count_all_and_healthz_style_calls_survive_outage() -> None:
    store = ResilientContextStore(primary=AlwaysFailsStore(), fallback=InMemoryContextStore())

    counts = await store.count_all()

    assert counts == {}
    assert store.degraded is True


async def test_close_never_raises_even_if_primary_close_fails() -> None:
    class _FailsOnClose(AlwaysFailsStore):
        async def close(self) -> None:
            raise ConnectionError("already gone")

    store = ResilientContextStore(primary=_FailsOnClose(), fallback=InMemoryContextStore())

    await store.close()  # must not raise


# ── Timeout bound — a stalled primary must degrade, not hang the request ────
#
# This is the fix for a production-only 502: a managed Redis that accepts a
# connection/PING but stalls on a specific command (a blocked write path)
# doesn't raise — it just never returns. Without an explicit bound, that
# hangs the request until the platform's edge proxy times out and returns a
# 502, instead of the documented store failure surfacing as a clean 200
# (degraded) or 500. AlwaysFailsStore can't exercise this; only a primary
# that truly never completes can.


async def test_hanging_primary_degrades_to_fallback_within_the_timeout() -> None:
    store = ResilientContextStore(
        primary=HangingStore(), fallback=InMemoryContextStore(), primary_timeout_seconds=0.05
    )

    started = time.monotonic()
    await store.set("merchant", "m_001", 1, {"name": "x"})  # must not hang
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert store.degraded is True
    result = await store.get("merchant", "m_001")
    assert result is not None
    assert result["payload"] == {"name": "x"}


async def test_hanging_primary_stays_degraded_for_subsequent_calls() -> None:
    store = ResilientContextStore(
        primary=HangingStore(), fallback=InMemoryContextStore(), primary_timeout_seconds=0.05
    )

    await store.set("merchant", "m_001", 1, {"name": "x"})  # triggers degrade via timeout
    assert store.degraded is True

    started = time.monotonic()
    await store.set("merchant", "m_002", 1, {"name": "y"})
    elapsed = time.monotonic() - started

    assert elapsed < 0.5  # goes straight to fallback, no second timeout wait
    assert await store.get("merchant", "m_002") is not None


async def test_default_primary_timeout_is_five_seconds() -> None:
    store = ResilientContextStore(primary=InMemoryContextStore(), fallback=InMemoryContextStore())
    assert store._primary_timeout_seconds == 5.0
