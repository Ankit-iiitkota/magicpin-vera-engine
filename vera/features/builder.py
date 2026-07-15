"""
vera.features.builder — FeatureBuilder.

A fluent, completeness-checked assembler for FeatureSet. Each section
is computed independently (see category_features.py, merchant_features
.py, customer_features.py, trigger_features.py, cross_features.py) and
handed to the builder; `build()` fails loudly if any section was never
set, instead of silently constructing a partially-populated FeatureSet.

Existing mainly so FeatureExtractor's orchestration reads as a
straight-line list of "compute this, feed it in" calls, and so tests
can assemble a FeatureSet by hand from small hand-built sections
without needing full CategoryContext/MerchantContext fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.features.feature_set import FeatureSet

if TYPE_CHECKING:
    from vera.features.feature_set import (
        BusinessHealthFeatures,
        CampaignHistoryFeatures,
        CategoryFeatures,
        ConversationSummaryFeatures,
        CustomerRelationshipFeatures,
        IdentityFeatures,
        MerchantProfileFeatures,
        OfferFeatures,
        PerformanceFeatures,
        TemporalFeatures,
        TriggerFeatures,
    )

__all__ = ["FeatureBuilder"]

_SECTION_NAMES = (
    "identity",
    "merchant_profile",
    "performance",
    "offers",
    "campaign_history",
    "business_health",
    "conversation",
    "customer_relationship",
    "trigger",
    "category",
    "temporal",
)


class FeatureBuilder:
    """Accumulates FeatureSet sections, then assembles them into one."""

    def __init__(self) -> None:
        self._sections: dict[str, object] = dict.fromkeys(_SECTION_NAMES)

    def with_identity(self, value: IdentityFeatures) -> FeatureBuilder:
        self._sections["identity"] = value
        return self

    def with_merchant_profile(self, value: MerchantProfileFeatures) -> FeatureBuilder:
        self._sections["merchant_profile"] = value
        return self

    def with_performance(self, value: PerformanceFeatures) -> FeatureBuilder:
        self._sections["performance"] = value
        return self

    def with_offers(self, value: OfferFeatures) -> FeatureBuilder:
        self._sections["offers"] = value
        return self

    def with_campaign_history(self, value: CampaignHistoryFeatures) -> FeatureBuilder:
        self._sections["campaign_history"] = value
        return self

    def with_business_health(self, value: BusinessHealthFeatures) -> FeatureBuilder:
        self._sections["business_health"] = value
        return self

    def with_conversation(self, value: ConversationSummaryFeatures) -> FeatureBuilder:
        self._sections["conversation"] = value
        return self

    def with_customer_relationship(self, value: CustomerRelationshipFeatures) -> FeatureBuilder:
        self._sections["customer_relationship"] = value
        return self

    def with_trigger(self, value: TriggerFeatures) -> FeatureBuilder:
        self._sections["trigger"] = value
        return self

    def with_category(self, value: CategoryFeatures) -> FeatureBuilder:
        self._sections["category"] = value
        return self

    def with_temporal(self, value: TemporalFeatures) -> FeatureBuilder:
        self._sections["temporal"] = value
        return self

    def build(self) -> FeatureSet:
        missing = [name for name in _SECTION_NAMES if self._sections[name] is None]
        if missing:
            raise ValueError(f"FeatureBuilder.build() missing required section(s): {missing}")
        return FeatureSet(**self._sections)
