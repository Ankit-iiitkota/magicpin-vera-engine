"""
vera.features.category_features — CategoryContext -> CategoryFeatures.

Pure function, no cross-context computation (that's cross_features.py)
and no `now`-dependence (that's temporal, also cross_features.py since
it needs category.seasonal_beats).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import (
    CategoryFeatures,
    DigestItemRecord,
    OfferTemplateRecord,
    SeasonalBeatRecord,
    TrendSignalRecord,
)

if TYPE_CHECKING:
    from vera.contexts.category import CategoryContext

__all__ = ["extract_category_features"]


def extract_category_features(category: CategoryContext) -> CategoryFeatures:
    peer = category.peer_stats
    voice = category.voice

    offer_catalog = tuple(
        OfferTemplateRecord(id=o.id, title=o.title, value=o.value, audience=o.audience, type=o.type)
        for o in category.offer_catalog
    )
    digest = tuple(
        DigestItemRecord(
            id=d.id,
            kind=d.kind,
            title=d.title,
            source=d.source,
            summary=d.summary,
            actionable=d.actionable,
        )
        for d in category.digest
    )
    seasonal_beats = tuple(
        SeasonalBeatRecord(month_range=b.month_range, note=b.note) for b in category.seasonal_beats
    )
    trend_signals = tuple(
        TrendSignalRecord(query=t.query, delta_yoy=t.delta_yoy) for t in category.trend_signals
    )

    return CategoryFeatures(
        slug=category.slug,
        display_name=category.display_name,
        voice_tone=voice.tone,
        vocab_allowed=tuple(voice.vocab_allowed),
        vocab_taboo=tuple(voice.vocab_taboo),
        salutation_examples=tuple(voice.salutation_examples),
        peer_avg_rating=peer.avg_rating if peer else None,
        peer_avg_ctr=peer.avg_ctr if peer else None,
        peer_avg_reviews=peer.avg_reviews if peer else None,
        offer_catalog=offer_catalog,
        digest=digest,
        digest_count=len(digest),
        seasonal_beats=seasonal_beats,
        trend_signals=trend_signals,
    )
