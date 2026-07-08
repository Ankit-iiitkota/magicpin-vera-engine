"""
Unit tests for vera.store.context_repository.ContextRepository.

Exercises version semantics (create / duplicate / replace / stale),
reads (get_context / context_exists / get_version), deletion, and
concurrency, against InMemoryContextStore — no Redis required.
"""

from __future__ import annotations

import asyncio

import pytest

from vera.store.context_repository import ContextRepository, SaveStatus
from vera.store.conversation_store import ConversationStore
from vera.store.memory_store import InMemoryContextStore


@pytest.fixture
def repo() -> ContextRepository:
    return ContextRepository(InMemoryContextStore())


async def test_create_new_context(repo: ContextRepository) -> None:
    result = await repo.save_context("merchant", "m_001", 1, {"name": "Dr. Meera"})

    assert result.status is SaveStatus.CREATED
    assert result.version == 1
    assert result.current_version == 1

    record = await repo.get_context("merchant", "m_001")
    assert record is not None
    assert record.payload == {"name": "Dr. Meera"}
    assert record.version == 1


async def test_duplicate_version_is_noop(repo: ContextRepository) -> None:
    first = await repo.save_context("customer", "c_001", 1, {"name": "Priya"})
    second = await repo.save_context("customer", "c_001", 1, {"name": "SOMEONE ELSE"})

    assert second.status is SaveStatus.DUPLICATE
    assert second.current_version == 1
    # The no-op must not have overwritten the original payload.
    record = await repo.get_context("customer", "c_001")
    assert record is not None
    assert record.payload == {"name": "Priya"}
    # stored_at is unchanged from the original write.
    assert second.stored_at == first.stored_at


async def test_higher_version_atomic_replace(repo: ContextRepository) -> None:
    await repo.save_context("conversation", "conv_001", 1, {"turn": 1})
    result = await repo.save_context("conversation", "conv_001", 2, {"turn": 2})

    assert result.status is SaveStatus.REPLACED
    assert result.version == 2
    assert result.current_version == 2

    record = await repo.get_context("conversation", "conv_001")
    assert record is not None
    assert record.version == 2
    assert record.payload == {"turn": 2}


async def test_lower_version_rejected(repo: ContextRepository) -> None:
    await repo.save_context("merchant", "m_002", 5, {"name": "v5"})
    result = await repo.save_context("merchant", "m_002", 3, {"name": "v3"})

    assert result.status is SaveStatus.STALE
    assert result.version == 3
    assert result.current_version == 5

    # The original (higher) version must be untouched.
    record = await repo.get_context("merchant", "m_002")
    assert record is not None
    assert record.version == 5
    assert record.payload == {"name": "v5"}


async def test_delete_context(repo: ContextRepository) -> None:
    await repo.save_context("trigger", "trg_001", 1, {"kind": "research_digest"})
    assert await repo.context_exists("trigger", "trg_001") is True

    await repo.delete_context("trigger", "trg_001")

    assert await repo.context_exists("trigger", "trg_001") is False
    assert await repo.get_context("trigger", "trg_001") is None
    assert await repo.get_version("trigger", "trg_001") is None


async def test_context_exists_and_get_version_absent(repo: ContextRepository) -> None:
    assert await repo.context_exists("category", "unknown") is False
    assert await repo.get_version("category", "unknown") is None
    assert await repo.get_context("category", "unknown") is None


@pytest.mark.parametrize("scope", ["merchant", "customer", "conversation"])
async def test_supports_merchant_customer_conversation_scopes(
    repo: ContextRepository, scope: str
) -> None:
    result = await repo.save_context(scope, "id_1", 1, {"scope_under_test": scope})
    assert result.status is SaveStatus.CREATED

    record = await repo.get_context(scope, "id_1")
    assert record is not None
    assert record.scope == scope
    assert record.payload == {"scope_under_test": scope}
    assert await repo.get_version(scope, "id_1") == 1


async def test_delivered_at_and_stored_at_round_trip(repo: ContextRepository) -> None:
    await repo.save_context(
        "trigger", "trg_002", 1, {"kind": "recall_due"}, delivered_at="2026-04-26T10:00:00Z"
    )
    record = await repo.get_context("trigger", "trg_002")

    assert record is not None
    assert record.delivered_at == "2026-04-26T10:00:00Z"
    assert record.stored_at is not None


async def test_rejects_scope_reserved_by_conversation_store(repo: ContextRepository) -> None:
    """
    ConversationStore owns ConversationStore.SCOPE exclusively and writes
    a raw, incompatible envelope there. ContextRepository must refuse to
    touch it rather than risk corrupting or misdeserialising those
    records.
    """
    with pytest.raises(ValueError):
        await repo.save_context(ConversationStore.SCOPE, "conv_001", 1, {"turn": 1})
    with pytest.raises(ValueError):
        await repo.get_context(ConversationStore.SCOPE, "conv_001")
    with pytest.raises(ValueError):
        await repo.context_exists(ConversationStore.SCOPE, "conv_001")
    with pytest.raises(ValueError):
        await repo.get_version(ConversationStore.SCOPE, "conv_001")
    with pytest.raises(ValueError):
        await repo.delete_context(ConversationStore.SCOPE, "conv_001")


async def test_concurrent_saves_same_key_are_serialised(repo: ContextRepository) -> None:
    """Two concurrent pushes for the same key must not race each other."""
    results = await asyncio.gather(
        repo.save_context("merchant", "m_race", 1, {"v": 1}),
        repo.save_context("merchant", "m_race", 2, {"v": 2}),
    )

    # Regardless of which call the lock let through first, version 2
    # must win: either it wrote CREATED and the v1 call lost as STALE,
    # or v1 wrote CREATED first and v2 then won as REPLACED.
    final = await repo.get_context("merchant", "m_race")
    assert final is not None
    assert final.version == 2
    assert final.payload == {"v": 2}
    statuses = {r.status for r in results}
    assert statuses in (
        {SaveStatus.CREATED, SaveStatus.REPLACED},
        {SaveStatus.CREATED, SaveStatus.STALE},
    )
