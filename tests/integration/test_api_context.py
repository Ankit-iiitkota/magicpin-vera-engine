"""
POST /v1/context contract tests — challenge-testing-brief.md §2.1.

Exercises the endpoint end-to-end through a real TestClient/lifespan,
but with the store dependencies explicitly overridden to a fresh
InMemoryContextStore per test (see the `client` fixture) — this suite
must pass identically whether or not a real Redis happens to be
running locally, so it never relies on the ambient environment.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AlwaysFailsStore
from vera.api.deps import get_context_repository, get_store
from vera.config import get_settings
from vera.main import app
from vera.store.context_repository import ContextRepository
from vera.store.memory_store import InMemoryContextStore
from vera.store.resilient_store import ResilientContextStore

CATEGORY_PAYLOAD = {"slug": "dentists", "voice": {"tone": "peer_clinical"}}
MERCHANT_PAYLOAD = {
    "merchant_id": "m_001",
    "category_slug": "dentists",
    "identity": {"name": "Dr. Meera's Dental Clinic"},
    "subscription": {"status": "active"},
    "performance": {},
}
CUSTOMER_PAYLOAD = {
    "customer_id": "c_001",
    "merchant_id": "m_001",
    "identity": {"name": "Priya"},
    "relationship": {},
    "state": "active",
    "preferences": {},
    "consent": {},
}
TRIGGER_PAYLOAD = {
    "id": "trg_001",
    "scope": "merchant",
    "kind": "research_digest",
    "source": "external",
    "suppression_key": "research:dentists:2026-W17",
    "expires_at": "2026-05-03T00:00:00Z",
}

DELIVERED_AT = "2026-04-26T10:00:00Z"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """
    A TestClient wired to a fresh, isolated InMemoryContextStore.

    Two layers of isolation, deliberately redundant:
      1. `dependency_overrides` on get_store/get_context_repository is
         the load-bearing fix — whatever the real lifespan creates,
         every request in this test goes through the store object
         created right here, fresh, every test.
      2. Forcing REDIS_URL to a closed local port (and clearing the
         Settings cache so that takes effect) makes the *real* lifespan's
         own incidental store-creation attempt fail the same way every
         run (connection refused) instead of whatever a possibly-
         reachable ambient Redis would do — belt and suspenders on top
         of (1), which is what actually makes this suite hermetic.
    """
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


@pytest.fixture
def degraded_client(monkeypatch: pytest.MonkeyPatch):
    """A client whose store's primary is already dead — every op degrades."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()

    store = ResilientContextStore(primary=AlwaysFailsStore(), fallback=InMemoryContextStore())
    repo = ContextRepository(store)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context_repository] = lambda: repo

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(get_context_repository, None)
    get_settings.cache_clear()


def _push(client: TestClient, scope: str, context_id: str, version: int, payload: dict):
    return client.post(
        "/v1/context",
        json={
            "scope": scope,
            "context_id": context_id,
            "version": version,
            "payload": payload,
            "delivered_at": DELIVERED_AT,
        },
    )


@pytest.mark.parametrize(
    ("scope", "context_id", "payload"),
    [
        ("category", "dentists", CATEGORY_PAYLOAD),
        ("merchant", "m_001", MERCHANT_PAYLOAD),
        ("customer", "c_001", CUSTOMER_PAYLOAD),
        ("trigger", "trg_001", TRIGGER_PAYLOAD),
    ],
)
def test_push_each_scope_is_accepted(client, scope, context_id, payload):
    r = _push(client, scope, context_id, 1, payload)

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["ack_id"] == f"ack_{context_id}_v1"
    assert body["stored_at"]


def test_duplicate_version_is_noop_and_returns_200(client):
    first = _push(client, "category", "dentists", 1, CATEGORY_PAYLOAD)
    second = _push(client, "category", "dentists", 1, CATEGORY_PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["stored_at"] == first.json()["stored_at"]


def test_higher_version_replaces_lower(client):
    r1 = _push(client, "merchant", "m_001", 1, MERCHANT_PAYLOAD)
    r2 = _push(client, "merchant", "m_001", 2, MERCHANT_PAYLOAD)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["ack_id"] == "ack_m_001_v1"
    assert r2.json()["ack_id"] == "ack_m_001_v2"

    # Proven indirectly: re-pushing v1 now must be rejected as stale
    # against the replaced current_version=2.
    stale = _push(client, "merchant", "m_001", 1, MERCHANT_PAYLOAD)
    assert stale.status_code == 409
    assert stale.json()["current_version"] == 2


def test_lower_version_rejected_409_stale(client):
    _push(client, "trigger", "trg_001", 5, TRIGGER_PAYLOAD)
    r = _push(client, "trigger", "trg_001", 3, TRIGGER_PAYLOAD)

    assert r.status_code == 409
    body = r.json()
    assert body["accepted"] is False
    assert body["reason"] == "stale_version"
    assert body["current_version"] == 5


def test_invalid_scope_returns_400(client):
    r = _push(client, "bogus_scope", "x", 1, {})

    assert r.status_code == 400
    body = r.json()
    assert body["accepted"] is False
    assert body["reason"] == "invalid_scope"


def test_invalid_payload_returns_400(client):
    # Missing required fields (identity, subscription, performance).
    r = _push(client, "merchant", "m_broken", 1, {"merchant_id": "m_broken"})

    assert r.status_code == 400
    body = r.json()
    assert body["accepted"] is False
    assert body["reason"] == "invalid_payload"
    assert body["details"]


def test_invalid_delivered_at_returns_400(client):
    r = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": CATEGORY_PAYLOAD,
            "delivered_at": "not-a-timestamp",
        },
    )

    assert r.status_code == 400
    assert r.json()["reason"] == "invalid_delivered_at"


def test_healthz_reflects_pushed_contexts(client):
    _push(client, "category", "dentists", 1, CATEGORY_PAYLOAD)
    _push(client, "merchant", "m_001", 1, MERCHANT_PAYLOAD)
    _push(client, "customer", "c_001", 1, CUSTOMER_PAYLOAD)
    _push(client, "trigger", "trg_001", 1, TRIGGER_PAYLOAD)

    health = client.get("/v1/healthz").json()
    assert health["contexts_loaded"] == {
        "category": 1,
        "merchant": 1,
        "customer": 1,
        "trigger": 1,
    }


# ── Malformed-envelope requests now get the documented 400, not a 422 ───────


def test_missing_required_field_returns_400_not_422(client):
    r = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": CATEGORY_PAYLOAD,
            # delivered_at omitted entirely
        },
    )

    assert r.status_code == 400
    body = r.json()
    assert body["accepted"] is False
    assert body["reason"] == "malformed_request"
    assert "delivered_at" in body["details"]


def test_non_dict_payload_returns_400_not_422(client):
    r = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": 1,
            "payload": "not-an-object",
            "delivered_at": DELIVERED_AT,
        },
    )

    assert r.status_code == 400
    assert r.json()["reason"] == "malformed_request"


def test_non_integer_version_returns_400_not_422(client):
    r = client.post(
        "/v1/context",
        json={
            "scope": "category",
            "context_id": "dentists",
            "version": "not-a-number",
            "payload": CATEGORY_PAYLOAD,
            "delivered_at": DELIVERED_AT,
        },
    )

    assert r.status_code == 400
    assert r.json()["reason"] == "malformed_request"


# ── New field validation: version > 0, context_id non-empty, payload cap ────


@pytest.mark.parametrize("bad_version", [0, -1, -100])
def test_non_positive_version_returns_400(client, bad_version):
    r = _push(client, "category", "dentists", bad_version, CATEGORY_PAYLOAD)

    assert r.status_code == 400
    body = r.json()
    assert body["reason"] == "malformed_request"
    assert "version" in body["details"]


def test_empty_context_id_returns_400(client):
    r = _push(client, "category", "", 1, CATEGORY_PAYLOAD)

    assert r.status_code == 400
    body = r.json()
    assert body["reason"] == "malformed_request"
    assert "context_id" in body["details"]


def test_oversized_payload_returns_400(client):
    # challenge-testing-brief.md §5: 500 KB cap on the payload.
    huge_payload = {"slug": "dentists", "voice": {"tone": "peer_clinical"}, "blob": "x" * 600_000}
    r = _push(client, "category", "dentists", 1, huge_payload)

    assert r.status_code == 400
    body = r.json()
    assert body["reason"] == "malformed_request"
    assert "payload" in body["details"]


def test_payload_at_cap_boundary_is_accepted(client):
    # ~400KB of padding stays comfortably under the 500KB cap once the
    # rest of the envelope + JSON overhead is accounted for.
    payload = {"slug": "dentists", "voice": {"tone": "peer_clinical"}, "blob": "x" * 400_000}
    r = _push(client, "category", "dentists", 1, payload)

    assert r.status_code == 200


# ── Runtime Redis failure degrades gracefully instead of 500ing ─────────────


def test_context_push_survives_primary_store_outage(degraded_client):
    """
    The store's primary is dead from the first call. The endpoint must
    still return the documented 200-accepted shape, never a 500 — this
    is the whole point of ResilientContextStore.
    """
    r = _push(degraded_client, "category", "dentists", 1, CATEGORY_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["ack_id"] == "ack_dentists_v1"


def test_healthz_survives_primary_store_outage(degraded_client):
    r = degraded_client.get("/v1/healthz")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"
