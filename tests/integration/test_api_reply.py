"""
POST /v1/reply state machine tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vera.api.deps import get_context_repository, get_store
from vera.config import get_settings
from vera.main import app
from vera.store.context_repository import ContextRepository
from vera.store.memory_store import InMemoryContextStore


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()

    store = InMemoryContextStore()
    repo = ContextRepository(store)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context_repository] = lambda: repo

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(get_context_repository, None)
    get_settings.cache_clear()


def _reply(client: TestClient, conversation_id: str, message: str, turn_number: int, **overrides):
    payload = {
        "conversation_id": conversation_id,
        "merchant_id": "m_001",
        "customer_id": None,
        "from_role": "merchant",
        "message": message,
        "received_at": "2026-04-26T12:00:00Z",
        "turn_number": turn_number,
    }
    payload.update(overrides)
    return client.post("/v1/reply", json=payload)


def test_reply_with_unknown_conversation_opens_it_defensively(client):
    r = _reply(client, "conv_unseen", "Okay, thanks for letting me know", 1)

    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "send"
    assert body["body"]
    assert set(body.keys()) == {"action", "body", "cta", "rationale"}


def test_reply_commit_message_returns_send_with_confirmation(client):
    r = _reply(client, "conv_commit", "Yes, let's do it", 1)

    body = r.json()
    assert body["action"] == "send"
    assert "update" in body["body"].lower() or "confirm" in body["body"].lower()


def test_reply_decline_message_returns_end_with_no_body_field(client):
    r = _reply(client, "conv_decline", "Not interested, thanks", 1)

    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "end"
    assert set(body.keys()) == {"action", "rationale"}


def test_reply_wait_message_returns_wait_with_seconds(client):
    r = _reply(client, "conv_wait", "Call me later, I'm busy", 1)

    body = r.json()
    assert body["action"] == "wait"
    assert body["wait_seconds"] > 0
    assert set(body.keys()) == {"action", "wait_seconds", "rationale"}


def test_reply_hostile_message_deescalates_once_then_ends_on_repeat(client):
    conversation_id = "conv_hostile"

    first = _reply(client, conversation_id, "This is spam, stop bothering me", 1)
    assert first.json()["action"] == "send"

    second = _reply(client, conversation_id, "You people are useless, this is spam", 2)
    assert second.json()["action"] == "end"


def test_reply_auto_reply_pattern_nudges_once_then_ends(client):
    conversation_id = "conv_autoreply"
    canned = "We are currently unavailable. We will get back to you soon."

    r1 = _reply(client, conversation_id, canned, 1)
    r2 = _reply(client, conversation_id, canned, 2)
    r3 = _reply(client, conversation_id, canned, 3)

    assert r1.json()["action"] == "send"
    assert r2.json()["action"] == "send"
    assert r3.json()["action"] == "send"

    r4 = _reply(client, conversation_id, canned, 4)
    assert r4.json()["action"] == "end"


def test_reply_max_turns_reached_returns_end(client):
    # Distinct message text per turn avoids tripping the auto-reply
    # detector, so this exercises the max_turns exit path specifically.
    conversation_id = "conv_maxturns"
    for turn in range(1, 6):
        r = _reply(client, conversation_id, f"Sounds good, checking now #{turn}", turn)

    assert r.json()["action"] == "end"


def test_reply_off_topic_question_stays_on_mission(client):
    r = _reply(client, "conv_offtopic", "What's the weather like today?", 1)

    body = r.json()
    assert body["action"] == "send"
    assert body["cta"] == "none"
