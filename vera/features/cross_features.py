"""
vera.features.cross_features — features needing more than one context.

category_features.py only sees CategoryContext; merchant_features.py
only sees MerchantContext. A few features are inherently comparisons or
combinations across contexts (merchant CTR vs. category peer CTR,
which seasonal beat matches "now") — those live here instead of being
forced into a single-context module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import BusinessHealthFeatures, ReviewThemeRecord, TemporalFeatures

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.category import CategoryContext
    from vera.contexts.merchant import MerchantContext

__all__ = ["extract_business_health", "extract_temporal"]

_MONTH_ABBR = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_WEEKEND_ISOWEEKDAYS = (6, 7)  # Saturday, Sunday


def extract_business_health(
    merchant: MerchantContext,
    category: CategoryContext,
    *,
    ctr_dip_threshold: float,
    ctr_spike_threshold: float,
) -> BusinessHealthFeatures:
    ctr = merchant.performance.ctr
    peer_ctr = category.peer_stats.avg_ctr if category.peer_stats else None
    ctr_vs_peer_delta = ctr - peer_ctr if (ctr is not None and peer_ctr is not None) else None

    themes = tuple(
        ReviewThemeRecord(theme=t.theme, sentiment=t.sentiment, occurrences_30d=t.occurrences_30d)
        for t in merchant.review_themes
    )
    if not themes:
        review_velocity = None
        review_trend = None
    else:
        # `or 0`: a theme present with occurrences_30d unset still counts
        # towards velocity as zero, not as "no data" (that's `not themes`).
        review_velocity = sum(t.occurrences_30d or 0 for t in themes)
        positive = sum(1 for t in themes if t.sentiment == "pos")
        negative = sum(1 for t in themes if t.sentiment == "neg")
        if positive > negative:
            review_trend = "positive"
        elif negative > positive:
            review_trend = "negative"
        else:
            review_trend = "mixed"

    delta_7d = merchant.performance.delta_7d
    ctr_delta = delta_7d.ctr_pct if delta_7d else None
    if ctr_delta is None:
        growth_trend = "unknown"
    elif ctr_delta >= ctr_spike_threshold:
        growth_trend = "growing"
    elif ctr_delta <= ctr_dip_threshold:
        growth_trend = "declining"
    else:
        growth_trend = "stable"

    return BusinessHealthFeatures(
        signals=tuple(merchant.signals),
        ctr_vs_peer_delta=ctr_vs_peer_delta,
        rating_delta=None,
        review_velocity=review_velocity,
        review_trend=review_trend,
        review_themes=themes,
        merchant_growth_trend=growth_trend,
    )


def extract_temporal(now: datetime, category: CategoryContext) -> TemporalFeatures:
    season = tuple(
        beat.note
        for beat in category.seasonal_beats
        if _month_in_range(now.month, beat.month_range)
    )
    return TemporalFeatures(
        extracted_at=now.isoformat(),
        season=season,
        weekend=now.isoweekday() in _WEEKEND_ISOWEEKDAYS,
        business_open_now=None,
    )


def _month_in_range(month: int, month_range: str) -> bool:
    """
    Match a month (1-12) against a "Nov-Feb"/"Oct-Dec"/"Jan"-style range,
    handling year-boundary wraparound (Nov-Feb spans Nov,Dec,Jan,Feb).
    Malformed ranges never match (no crash on bad category data).
    """
    parts = [p.strip() for p in month_range.split("-")]
    start = _MONTH_ABBR.get(parts[0])
    end = _MONTH_ABBR.get(parts[-1])
    if start is None or end is None:
        return False
    if start <= end:
        return start <= month <= end
    return month >= start or month <= end
