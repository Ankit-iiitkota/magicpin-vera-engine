"""
vera.features.extractor — FeatureExtractor, the Layer-1 entry point.

FeatureExtractor.extract(category, merchant, trigger, customer=None) is
the ONLY function in this codebase allowed to read CategoryContext /
MerchantContext / TriggerContext / CustomerContext fields directly.
Every layer built in later phases (signals, goals, candidates, ranking,
templates, scoring, the composer itself) must take a FeatureSet as
input and never import vera.contexts.* — see vera/contexts/__init__.py
consumers should never appear outside vera/features/ and vera/api/.

Determinism: the only non-deterministic input this extractor could use
is the wall clock, so `now` is an explicit, optional keyword argument
(defaulting to the real current time in production) rather than an
internal `datetime.now()` call. Given the same four contexts and the
same `now`, extract() always returns a byte-identical FeatureSet — no
randomness, no network I/O, no hidden state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.config import load_yaml
from vera.features.builder import FeatureBuilder
from vera.features.category_features import extract_category_features
from vera.features.cross_features import extract_business_health, extract_temporal
from vera.features.customer_features import extract_customer_relationship
from vera.features.merchant_features import (
    extract_campaign_history,
    extract_conversation_summary,
    extract_identity,
    extract_merchant_profile,
    extract_offers,
    extract_performance,
)
from vera.features.trigger_features import extract_trigger_features
from vera.features.validator import FeatureValidator
from vera.utils.time_utils import utcnow

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.category import CategoryContext
    from vera.contexts.customer import CustomerContext
    from vera.contexts.merchant import MerchantContext
    from vera.contexts.trigger import TriggerContext
    from vera.features.feature_set import FeatureSet

__all__ = ["FeatureExtractor"]

#: Mirrors config/settings.yaml's `feature_extraction` block — see
#: FeatureExtractor.from_config(). Duplicated here as literal defaults
#: so the extractor is fully usable (and deterministic) with zero file
#: I/O, e.g. in unit tests or if the YAML file is ever unavailable.
_DEFAULT_DORMANCY_THRESHOLD_DAYS = 14
_DEFAULT_CTR_DIP_THRESHOLD = -0.15
_DEFAULT_CTR_SPIKE_THRESHOLD = 0.20
_DEFAULT_FESTIVAL_WINDOW_DAYS = 14


class FeatureExtractor:
    """Turns the four raw context objects into one immutable FeatureSet."""

    def __init__(
        self,
        *,
        dormancy_threshold_days: int = _DEFAULT_DORMANCY_THRESHOLD_DAYS,
        ctr_dip_threshold: float = _DEFAULT_CTR_DIP_THRESHOLD,
        ctr_spike_threshold: float = _DEFAULT_CTR_SPIKE_THRESHOLD,
        festival_window_days: int = _DEFAULT_FESTIVAL_WINDOW_DAYS,
    ) -> None:
        self._dormancy_threshold_days = dormancy_threshold_days
        self._ctr_dip_threshold = ctr_dip_threshold
        self._ctr_spike_threshold = ctr_spike_threshold
        self._festival_window_days = festival_window_days
        self._validator = FeatureValidator()

    @classmethod
    def from_config(cls, path: str = "config/settings.yaml") -> FeatureExtractor:
        """Build an extractor from config/settings.yaml's `feature_extraction` block."""
        cfg = load_yaml(path).get("feature_extraction", {})
        return cls(
            dormancy_threshold_days=cfg.get(
                "dormancy_threshold_days", _DEFAULT_DORMANCY_THRESHOLD_DAYS
            ),
            ctr_dip_threshold=cfg.get("ctr_dip_threshold", _DEFAULT_CTR_DIP_THRESHOLD),
            ctr_spike_threshold=cfg.get("ctr_spike_threshold", _DEFAULT_CTR_SPIKE_THRESHOLD),
        )

    def extract(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: CustomerContext | None = None,
        *,
        now: datetime | None = None,
    ) -> FeatureSet:
        """
        Extract a FeatureSet. `category`, `merchant`, and `trigger` are
        required (mirrors challenge-brief.md §5's compose() signature);
        `customer` is optional and only present for customer-facing
        composition.
        """
        if category is None or merchant is None or trigger is None:
            raise TypeError("category, merchant, and trigger are required; customer is optional")

        moment = now if now is not None else utcnow()

        features = (
            FeatureBuilder()
            .with_identity(extract_identity(merchant))
            .with_merchant_profile(extract_merchant_profile(merchant))
            .with_performance(extract_performance(merchant))
            .with_offers(extract_offers(merchant))
            .with_campaign_history(extract_campaign_history(merchant, moment))
            .with_business_health(
                extract_business_health(
                    merchant,
                    category,
                    ctr_dip_threshold=self._ctr_dip_threshold,
                    ctr_spike_threshold=self._ctr_spike_threshold,
                )
            )
            .with_conversation(
                extract_conversation_summary(merchant, moment, self._dormancy_threshold_days)
            )
            .with_customer_relationship(extract_customer_relationship(merchant, customer, moment))
            .with_trigger(
                extract_trigger_features(
                    trigger, moment, festival_window_days=self._festival_window_days
                )
            )
            .with_category(extract_category_features(category))
            .with_temporal(extract_temporal(moment, category))
            .build()
        )

        self._validator.validate(features)
        return features
