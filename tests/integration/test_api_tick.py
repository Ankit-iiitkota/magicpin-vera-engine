"""
POST /v1/tick response tests.
Implemented alongside the phases they test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_context import (
    CATEGORY_PAYLOAD,
    CUSTOMER_PAYLOAD,
    DELIVERED_AT,
    MERCHANT_PAYLOAD,
)
from vera.api.deps import get_context_repository, get_store
from vera.config import get_settings
from vera.main import app
from vera.store.context_repository import ContextRepository
from vera.store.memory_store import InMemoryContextStore

TRIGGER_PAYLOAD = {
    "id": "trg_tick_001",
    "scope": "merchant",
    "kind": "research_digest",
    "source": "external",
    "suppression_key": "research:dentists:2026-W17",
    "expires_at": "2026-05-03T00:00:00Z",
    "merchant_id": "m_001",
}

CUSTOMER_TRIGGER_PAYLOAD = {
    "id": "trg_tick_002",
    "scope": "customer",
    "kind": "customer_recall",
    "source": "internal",
    "suppression_key": "recall:c_001:6mo",
    "expires_at": "2026-05-03T00:00:00Z",
    "merchant_id": "m_001",
    "customer_id": "c_001",
}


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


def _seed_merchant_scope(client: TestClient, trigger_payload: dict = TRIGGER_PAYLOAD):
    _push(client, "category", "dentists", CATEGORY_PAYLOAD)
    _push(client, "merchant", "m_001", MERCHANT_PAYLOAD)
    r = _push(client, "trigger", trigger_payload["id"], trigger_payload)
    assert r.status_code == 200


def _tick(client: TestClient, *trigger_ids: str):
    return client.post(
        "/v1/tick",
        json={"now": "2026-04-26T12:00:00Z", "available_triggers": list(trigger_ids)},
    )


def test_tick_composes_an_action_for_a_known_merchant_trigger(client):
    _seed_merchant_scope(client)

    r = _tick(client, TRIGGER_PAYLOAD["id"])

    assert r.status_code == 200
    body = r.json()
    assert len(body["actions"]) == 1
    action = body["actions"][0]
    assert action["merchant_id"] == "m_001"
    assert action["trigger_id"] == TRIGGER_PAYLOAD["id"]
    assert action["send_as"] == "vera"
    assert action["cta"] in ("binary", "open_ended", "none")
    assert action["body"]
    assert action["suppression_key"]
    assert action["rationale"]
    assert action["conversation_id"]


def test_tick_with_unknown_trigger_id_returns_no_actions(client):
    r = _tick(client, "trg_does_not_exist")

    assert r.status_code == 200
    assert r.json()["actions"] == []


def test_tick_with_empty_available_triggers_returns_no_actions(client):
    r = client.post("/v1/tick", json={"now": "2026-04-26T12:00:00Z", "available_triggers": []})

    assert r.status_code == 200
    assert r.json()["actions"] == []


def test_tick_second_call_for_same_trigger_is_suppressed(client):
    _seed_merchant_scope(client)

    first = _tick(client, TRIGGER_PAYLOAD["id"])
    second = _tick(client, TRIGGER_PAYLOAD["id"])

    assert len(first.json()["actions"]) == 1
    assert len(second.json()["actions"]) == 0


def test_tick_skips_a_second_trigger_that_renders_the_identical_body(client):
    """
    Goal inference consumes only SignalSet (never the trigger's own kind
    or payload), so two different triggers for the same merchant can
    legitimately produce the exact same body — a real LLM judge run
    penalised this heavily (message correctly written, but doesn't
    address the second trigger's own reason). Anti-repetition is keyed
    by merchant_id specifically so this second, redundant send is
    skipped rather than delivered twice in one tick.
    """
    _seed_merchant_scope(client)
    second_trigger = dict(TRIGGER_PAYLOAD)
    second_trigger["id"] = "trg_tick_001_duplicate"
    second_trigger["suppression_key"] = "research:dentists:2026-W18"
    _push(client, "trigger", second_trigger["id"], second_trigger)

    r = _tick(client, TRIGGER_PAYLOAD["id"], second_trigger["id"])

    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["trigger_id"] == TRIGGER_PAYLOAD["id"]


def test_tick_customer_scoped_trigger_sends_as_merchant_on_behalf(client):
    _push(client, "category", "dentists", CATEGORY_PAYLOAD)
    _push(client, "merchant", "m_001", MERCHANT_PAYLOAD)
    _push(client, "customer", "c_001", CUSTOMER_PAYLOAD)
    _push(client, "trigger", CUSTOMER_TRIGGER_PAYLOAD["id"], CUSTOMER_TRIGGER_PAYLOAD)

    r = _tick(client, CUSTOMER_TRIGGER_PAYLOAD["id"])

    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["send_as"] == "merchant_on_behalf"
    assert actions[0]["customer_id"] == "c_001"


def test_tick_missing_merchant_for_trigger_is_skipped_not_500(client):
    _push(client, "category", "dentists", CATEGORY_PAYLOAD)
    orphan_trigger = dict(TRIGGER_PAYLOAD)
    orphan_trigger["id"] = "trg_orphan"
    orphan_trigger["merchant_id"] = "m_does_not_exist"
    _push(client, "trigger", orphan_trigger["id"], orphan_trigger)

    r = _tick(client, orphan_trigger["id"])

    assert r.status_code == 200
    assert r.json()["actions"] == []


def test_tick_response_action_matches_action_item_schema(client):
    _seed_merchant_scope(client)

    r = _tick(client, TRIGGER_PAYLOAD["id"])

    action = r.json()["actions"][0]
    assert set(action.keys()) == {
        "conversation_id",
        "merchant_id",
        "customer_id",
        "send_as",
        "trigger_id",
        "template_name",
        "template_params",
        "body",
        "cta",
        "suppression_key",
        "rationale",
    }
