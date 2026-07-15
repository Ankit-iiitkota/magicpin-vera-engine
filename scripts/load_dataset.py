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
import time
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

#: Free-tier hosts (Render, Railway, ...) can drop or 502/504 a request
#: transiently under a rapid back-to-back sequence like this script's 55
#: pushes, or return an HTML edge-error page instead of JSON. A couple of
#: short retries smooths that over without masking a genuine, repeated
#: failure (schema mismatch, wrong URL, ...), which still fails loudly
#: after the retries are exhausted.
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2.0


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _decode_json(raw: bytes) -> Any:
    """Best-effort JSON decode — returns the raw text if the body isn't JSON
    (e.g. a platform edge-proxy HTML error page) instead of raising."""
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"non_json_response": text[:500]}


def _request(base_url: str, path: str, method: str, body: dict[str, Any] | None) -> tuple[int, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers, method=method)

    last_status, last_data = 0, {"error": "never attempted"}
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, _decode_json(resp.read())
        except urllib.error.HTTPError as exc:
            last_status, last_data = exc.code, _decode_json(exc.read())
        except urllib.error.URLError as exc:
            last_status, last_data = 0, {"error": str(exc.reason)}

        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SECONDS)

    return last_status, last_data


def _post(base_url: str, path: str, body: dict[str, Any]) -> tuple[int, Any]:
    return _request(base_url, path, "POST", body)


def _get(base_url: str, path: str) -> tuple[int, Any]:
    return _request(base_url, path, "GET", None)


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
    ok = status == 200 and isinstance(data, dict) and data.get("accepted") is True
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
