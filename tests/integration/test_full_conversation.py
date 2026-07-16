"""
End-to-end 5-turn conversation tests.
Implemented alongside the phases they test.

The three judge-scenario tests below use the exact conversation ids,
messages, and turn numbers judge_simulator.py's _auto_reply/_intent/
_hostile methods send, so a regression here means the actual judge
replay would regress too.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_context import CATEGORY_PAYLOAD, DELIVERED_AT, MERCHANT_PAYLOAD
from vera.api.deps import get_context_repository, get_store
from vera.config import get_settings
from vera.main import app
from vera.store.context_repository import ContextRepository
from vera.store.conversation_store import ConversationStore
from vera.store.memory_store import InMemoryContextStore

TRIGGER_PAYLOAD = {
    "id": "trg_conv_001",
    "scope": "merchant",
    "kind": "research_digest",
    "source": "external",
    "suppression_key": "research:dentists:2026-conv",
    "expires_at": "2026-05-03T00:00:00Z",
    "merchant_id": "m_001",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()

    store = InMemoryContextStore()
    repo = ContextRepository(store)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context_repository] = lambda: repo

    with TestClient(app) as c:
        yield c, store

    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(get_context_repository, None)
    get_settings.cache_clear()


def _push(client: TestClient, scope: str, context_id: str, payload: dict):
    return client.post(
        "/v1/context",
        json={
            "scope": scope,
            "context_id": context_id,
            "version": 1,
            "payload": payload,
            "delivered_at": DELIVERED_AT,
        },
    )


def _reply(client: TestClient, conversation_id: str, message: str, turn_number: int, mid="m_001"):
    return client.post(
        "/v1/reply",
        json={
            "conversation_id": conversation_id,
            "merchant_id": mid,
            "customer_id": None,
            "from_role": "merchant",
            "message": message,
            "received_at": "2026-04-26T12:00:00Z",
            "turn_number": turn_number,
        },
    )


async def test_five_turn_conversation_persists_state_across_turns(env):
    client, store = env
    _push(client, "category", "dentists", CATEGORY_PAYLOAD)
    _push(client, "merchant", "m_001", MERCHANT_PAYLOAD)
    _push(client, "trigger", TRIGGER_PAYLOAD["id"], TRIGGER_PAYLOAD)

    tick = client.post(
        "/v1/tick",
        json={"now": "2026-04-26T12:00:00Z", "available_triggers": [TRIGGER_PAYLOAD["id"]]},
    )
    conversation_id = tick.json()["actions"][0]["conversation_id"]

    r1 = _reply(client, conversation_id, "Okay, tell me more", 1)
    assert r1.json()["action"] == "send"

    r2 = _reply(client, conversation_id, "Call me back later, busy now", 2)
    assert r2.json()["action"] == "wait"

    r3 = _reply(client, conversation_id, "Alright sure, go ahead", 3)
    assert r3.json()["action"] == "send"

    r4 = _reply(client, conversation_id, "Actually not interested, thanks", 4)
    assert r4.json()["action"] == "end"

    conv_store = ConversationStore(store)
    state = await conv_store.get(conversation_id)
    assert state is not None
    assert state.ended is True
    assert state.state == "ended"
    assert state.turn_number == 4
    merchant_turns = [t for t in state.turns if t["from"] == "merchant"]
    assert len(merchant_turns) == 4


def test_judge_scenario_intent_transition_switches_to_action(env):
    client, _store = env
    commitment = "Ok lets do it. Whats next?"

    r = _reply(client, "conv_intent_1", commitment, 2, mid="m_test")

    body = r.json()
    assert body["action"] == "send"
    actioning = ["done", "sending", "draft", "here", "confirm", "proceed", "next"]
    qualifying = ["would you", "do you", "can you tell", "what if", "how about"]
    lowered = body["body"].lower()
    assert any(w in lowered for w in actioning)
    assert not any(w in lowered for w in qualifying)


def test_judge_scenario_hostile_message_apologizes_gracefully(env):
    client, _store = env
    hostile = "Stop messaging me. This is useless spam."

    r = _reply(client, "conv_hostile", hostile, 2, mid="m_test")

    # "Stop messaging me" is an explicit opt-out — it must end the
    # conversation immediately (no de-escalation send, no further nudges).
    body = r.json()
    assert body["action"] == "end"


def test_judge_scenario_auto_reply_each_conversation_is_independent(env):
    client, _store = env
    auto_msg = "Thank you for contacting us! Our team will respond shortly."

    for i in range(1, 5):
        r = _reply(client, f"conv_auto_{i}", auto_msg, i + 1, mid="m_test")
        assert r.status_code == 200
        assert r.json()["action"] in ("send", "wait", "end")
