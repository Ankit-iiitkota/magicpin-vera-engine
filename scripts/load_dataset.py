"""
Script: Warm the store with all seed data. Phase 9.

Root cause of "healthz shows merchant=0, customer=0 while category/trigger
loaded": there was no implemented loader — this file and
vera/dataset/loader.py were both `raise NotImplementedError` stubs, and
nothing else in the codebase ever POSTs to /v1/context. Whatever pushed
category + trigger data onto a deployment did so by hand and simply never
covered merchant/customer, so /v1/tick's per-trigger merchant lookup
(vera/api/endpoints/tick.py::_resolve_inputs) always missed and every
action was silently dropped — not a bug in tick, context_repository, or
the merchant/customer schemas themselves (all four scopes validate and
store identically once actually pushed; verified against the real
dataset — see AGENT_NOTES in the project history).

Pushes every category/merchant/customer/trigger record in
magicpin-ai-challenge/dataset/ to a running Vera server's POST /v1/context,
in that order (categories and merchants before the triggers/customers that
reference them, though push order has no bearing on correctness — only
tick-time lookups do). Prints one line per push and a final summary so a
partial failure (e.g. a schema mismatch on one record) is visible instead
of silently producing an empty contexts_loaded count.

Usage:
    python scripts/load_dataset.py [--base-url http://localhost:8080]

The base URL also comes from the VERA_BASE_URL env var if --base-url is
omitted, so a Railway deployment can be seeded with e.g.:

    VERA_BASE_URL=https://your-app.up.railway.app python scripts/load_dataset.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATASET_DIR = _REPO_ROOT / "magicpin-ai-challenge" / "dataset"
_DEFAULT_BASE_URL = "http://localhost:8080"

_CATEGORY_FILES = (
    "dentists.json",
    "salons.json",
    "restaurants.json",
    "gyms.json",
    "pharmacies.json",
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _post(base_url: str, path: str, body: dict[str, Any]) -> tuple[int, Any]:
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get(base_url: str, path: str) -> tuple[int, Any]:
    req = urllib.request.Request(f"{base_url}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _push_context(base_url: str, scope: str, context_id: str, payload: dict[str, Any]) -> bool:
    status, data = _post(
        base_url,
        "/v1/context",
        {
            "scope": scope,
            "context_id": context_id,
            "version": 1,
            "payload": payload,
            "delivered_at": _now_iso(),
        },
    )
    ok = status == 200 and data.get("accepted") is True
    marker = "OK" if ok else "FAIL"
    print(f"  [{marker}] {scope}/{context_id} -> {status} {data}")
    return ok


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_dataset(base_url: str, dataset_dir: Path) -> int:
    pushed = 0
    failed = 0

    print(f"Loading dataset from {dataset_dir} into {base_url}\n")

    print("Categories:")
    for filename in _CATEGORY_FILES:
        path = dataset_dir / "categories" / filename
        if not path.exists():
            print(f"  [SKIP] {path} not found")
            continue
        payload = _load_json(path)
        ok = _push_context(base_url, "category", payload["slug"], payload)
        pushed += ok
        failed += not ok

    merchants_path = dataset_dir / "merchants_seed.json"
    print("\nMerchants:")
    if merchants_path.exists():
        merchants = _load_json(merchants_path)["merchants"]
        for merchant in merchants:
            ok = _push_context(base_url, "merchant", merchant["merchant_id"], merchant)
            pushed += ok
            failed += not ok
    else:
        print(f"  [SKIP] {merchants_path} not found")

    customers_path = dataset_dir / "customers_seed.json"
    print("\nCustomers:")
    if customers_path.exists():
        customers = _load_json(customers_path).get("customers", [])
        for customer in customers:
            ok = _push_context(base_url, "customer", customer["customer_id"], customer)
            pushed += ok
            failed += not ok
    else:
        print(f"  [SKIP] {customers_path} not found")

    triggers_path = dataset_dir / "triggers_seed.json"
    print("\nTriggers:")
    if triggers_path.exists():
        triggers = _load_json(triggers_path)["triggers"]
        for trigger in triggers:
            ok = _push_context(base_url, "trigger", trigger["id"], trigger)
            pushed += ok
            failed += not ok
    else:
        print(f"  [SKIP] {triggers_path} not found")

    print(f"\nPushed {pushed} record(s), {failed} failure(s).")

    status, health = _get(base_url, "/v1/healthz")
    print(f"\nGET /v1/healthz -> {status} {health}")

    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VERA_BASE_URL", _DEFAULT_BASE_URL),
        help="Base URL of a running Vera server (default: %(default)s, or $VERA_BASE_URL)",
    )
    parser.add_argument(
        "--dataset-dir",
        default=str(_DATASET_DIR),
        help="Path to the magicpin-ai-challenge dataset directory (default: %(default)s)",
    )
    args = parser.parse_args()

    failed = load_dataset(args.base_url.rstrip("/"), Path(args.dataset_dir))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
