"""
vera.features.validator — FeatureValidator.

A post-extraction sanity gate. Deterministic construction from
Pydantic-validated context inputs should never actually produce an
invalid FeatureSet, so this is defense-in-depth against extraction bugs
(a future edit to merchant_features.py etc. producing NaN, an
inconsistent count, or an empty required identifier) — not something
callers need to think about on the happy path.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.features.feature_set import FeatureSet

__all__ = ["FeatureValidationError", "FeatureValidator"]


class FeatureValidationError(ValueError):
    """Raised by FeatureValidator.validate() with every issue found, not just the first."""

    def __init__(self, issues: list[str]) -> None:
        super().__init__("; ".join(issues))
        self.issues = issues


class FeatureValidator:
    def validate(self, features: FeatureSet) -> None:
        issues: list[str] = []
        self._check_required_identifiers(features, issues)
        self._check_numeric_sanity(features, issues)
        self._check_count_consistency(features, issues)
        if issues:
            raise FeatureValidationError(issues)

    @staticmethod
    def _check_required_identifiers(features: FeatureSet, issues: list[str]) -> None:
        if not features.identity.merchant_id:
            issues.append("identity.merchant_id must be non-empty")
        if not features.identity.category_slug:
            issues.append("identity.category_slug must be non-empty")
        if not features.identity.name:
            issues.append("identity.name must be non-empty")
        if not features.category.slug:
            issues.append("category.slug must be non-empty")
        if not features.trigger.id:
            issues.append("trigger.id must be non-empty")
        if features.identity.category_slug != features.category.slug:
            issues.append(
                "identity.category_slug "
                f"({features.identity.category_slug!r}) does not match "
                f"category.slug ({features.category.slug!r})"
            )

    @staticmethod
    def _check_numeric_sanity(features: FeatureSet, issues: list[str]) -> None:
        numeric_fields = (
            ("performance.ctr", features.performance.ctr),
            ("category.peer_avg_ctr", features.category.peer_avg_ctr),
            ("business_health.ctr_vs_peer_delta", features.business_health.ctr_vs_peer_delta),
            (
                "customer_relationship.customer_loyalty_score",
                features.customer_relationship.customer_loyalty_score,
            ),
        )
        for name, value in numeric_fields:
            if value is not None and (math.isnan(value) or math.isinf(value)):
                issues.append(f"{name} is NaN/Inf: {value}")

        if features.performance.ctr is not None and features.performance.ctr < 0:
            issues.append(f"performance.ctr must be >= 0, got {features.performance.ctr}")
        if not 1 <= features.trigger.urgency <= 5:
            issues.append(f"trigger.urgency must be within 1..5, got {features.trigger.urgency}")

    @staticmethod
    def _check_count_consistency(features: FeatureSet, issues: list[str]) -> None:
        if features.offers.offer_count != len(features.offers.offers):
            issues.append("offers.offer_count does not match len(offers.offers)")
        if features.offers.active_offer_count > features.offers.offer_count:
            issues.append("offers.active_offer_count exceeds offers.offer_count")
        if features.conversation.turn_count != len(features.conversation.turns):
            issues.append("conversation.turn_count does not match len(conversation.turns)")
        if features.category.digest_count != len(features.category.digest):
            issues.append("category.digest_count does not match len(category.digest)")
