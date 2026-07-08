"""
Time utilities and expiry helpers.

Minimal ISO-8601 helpers needed by POST /v1/context: validating the
caller-supplied `delivered_at` and stamping a canonical `stored_at` on
every context write.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["parse_iso8601", "utcnow_iso"]


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a 'Z' suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_iso8601(value: str) -> datetime:
    """
    Parse an ISO-8601 timestamp string, tolerating a trailing 'Z'.

    Raises ValueError if `value` is not a valid ISO-8601 timestamp.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"expected a non-empty ISO-8601 string, got {value!r}")
    normalised = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalised)
