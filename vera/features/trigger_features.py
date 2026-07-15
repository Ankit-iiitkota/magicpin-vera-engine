"""
vera.features.trigger_features — TriggerContext -> TriggerFeatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import TriggerFeatures, freeze_mapping
from vera.utils.time_utils import parse_iso8601_safe

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.trigger import TriggerContext

__all__ = ["extract_trigger_features"]

FESTIVAL_KIND = "festival_upcoming"


def extract_trigger_features(
    trigger: TriggerContext, now: datetime, *, festival_window_days: int
) -> TriggerFeatures:
    expires_dt = parse_iso8601_safe(trigger.expires_at)
    if expires_dt is not None:
        days_until_expiry = (expires_dt - now).days
        is_expired = expires_dt < now
    else:
        days_until_expiry = None
        is_expired = False

    festival_window = False
    if trigger.kind == FESTIVAL_KIND:
        days_until = trigger.payload.get("days_until")
        if isinstance(days_until, int | float) and 0 <= days_until <= festival_window_days:
            festival_window = True

    return TriggerFeatures(
        id=trigger.id,
        scope=trigger.scope,
        kind=trigger.kind,
        source=trigger.source,
        urgency=trigger.urgency,
        suppression_key=trigger.suppression_key,
        expires_at=trigger.expires_at,
        days_until_expiry=days_until_expiry,
        is_expired=is_expired,
        festival_window=festival_window,
        payload=freeze_mapping(trigger.payload),
    )
