"""
Suppression key logic tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

from vera.engine.anti_repetition import AntiRepetitionGuard
from vera.engine.suppression import SuppressionGuard
from vera.rules.suppression_rules import resolve_suppression_key
from vera.store.memory_store import InMemoryContextStore

# ── resolve_suppression_key (pure) ───────────────────────────────────────────


def test_merchant_scoped_key_is_passed_through_unchanged():
    assert (
        resolve_suppression_key("offer_expiry:m_001:trg_001", None) == "offer_expiry:m_001:trg_001"
    )


def test_customer_scoped_key_already_containing_customer_id_is_unchanged():
    key = "recall:c_001_priya_for_m001:6mo"
    assert resolve_suppression_key(key, "c_001_priya_for_m001") == key


def test_customer_scoped_key_missing_customer_id_gets_it_appended():
    key = "recall:m_001:6mo"
    assert resolve_suppression_key(key, "c_001") == "recall:m_001:6mo:c_001"


def test_no_customer_id_leaves_key_unchanged():
    assert resolve_suppression_key("some_key", None) == "some_key"


# ── SuppressionGuard (async, store-backed) ───────────────────────────────────


async def test_suppression_guard_reports_not_suppressed_when_unseen():
    guard = SuppressionGuard(InMemoryContextStore())
    assert await guard.is_suppressed("key_1") is False


async def test_suppression_guard_reports_suppressed_after_mark_sent():
    guard = SuppressionGuard(InMemoryContextStore())
    await guard.mark_sent("key_1")
    assert await guard.is_suppressed("key_1") is True


async def test_suppression_guard_keys_are_independent():
    guard = SuppressionGuard(InMemoryContextStore())
    await guard.mark_sent("key_1")
    assert await guard.is_suppressed("key_2") is False


# ── AntiRepetitionGuard (async, store-backed) ────────────────────────────────


async def test_anti_repetition_guard_reports_not_repeat_when_unseen():
    guard = AntiRepetitionGuard(InMemoryContextStore())
    assert await guard.is_repeat("conv_1", "hello there") is False


async def test_anti_repetition_guard_reports_repeat_after_mark_sent():
    guard = AntiRepetitionGuard(InMemoryContextStore())
    await guard.mark_sent("conv_1", "hello there")
    assert await guard.is_repeat("conv_1", "hello there") is True


async def test_anti_repetition_guard_normalises_whitespace_and_case():
    guard = AntiRepetitionGuard(InMemoryContextStore())
    await guard.mark_sent("conv_1", "Hello   There")
    assert await guard.is_repeat("conv_1", "hello there") is True


async def test_anti_repetition_guard_is_scoped_per_conversation():
    guard = AntiRepetitionGuard(InMemoryContextStore())
    await guard.mark_sent("conv_1", "hello there")
    assert await guard.is_repeat("conv_2", "hello there") is False


async def test_anti_repetition_guard_distinguishes_different_bodies():
    guard = AntiRepetitionGuard(InMemoryContextStore())
    await guard.mark_sent("conv_1", "hello there")
    assert await guard.is_repeat("conv_1", "a completely different message") is False
