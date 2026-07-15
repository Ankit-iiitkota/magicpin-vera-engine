"""
Time utilities and expiry helpers.

ISO-8601 helpers used by POST /v1/context (validating the caller-supplied
`delivered_at`, stamping `stored_at`) and by the feature extraction layer
(vera.features), which needs a raw `datetime` "now" and tolerant parsing
of the various date/datetime strings scattered through merchant/customer
context data (offer `started`/`ended`, conversation turn `ts`, customer
`last_visit`, ...).
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["parse_iso8601", "parse_iso8601_safe", "utcnow", "utcnow_iso"]


def utcnow() -> datetime:
    """Return the current, timezone-aware (UTC) time."""
    return datetime.now(UTC)


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a 'Z' suffix."""
    return utcnow().isoformat().replace("+00:00", "Z")


def parse_iso8601(value: str) -> datetime:
    """
    Parse an ISO-8601 timestamp string, tolerating a trailing 'Z'.

    Raises ValueError if `value` is not a valid ISO-8601 timestamp.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"expected a non-empty ISO-8601 string, got {value!r}")
    normalised = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalised)
    if parsed.tzinfo is None:
        # Date-only strings ("2026-03-01") and other naive timestamps in the
        # dataset are treated as UTC — every timezone-aware string in this
        # system already carries a 'Z'/offset, so naive == UTC by convention.
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_iso8601_safe(value: str | None) -> datetime | None:
    """
    Parse an ISO-8601 timestamp, never raising.

    Returns None for None/empty/unparseable input. Used throughout
    feature extraction, which must degrade gracefully on missing or
    malformed source data rather than crash — see vera.features.
    """
    if not value:
        return None
    try:
        return parse_iso8601(value)
    except ValueError:
        return None
