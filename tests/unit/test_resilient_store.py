"""
Unit tests for vera.store.resilient_store.ResilientContextStore.

Proves the runtime Redis-failure requirement directly: when the
primary store raises, calls transparently succeed against the
fallback instead of propagating the exception, and the store stays
degraded for the rest of its life (no flapping back to a
still-possibly-unhealthy primary on every call).
"""

from __future__ import annotations

from tests.conftest import AlwaysFailsStore
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
