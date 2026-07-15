"""
vera.rules.rule_engine — RuleEngine, ties cta/send_as/suppression rules
together into one MessageRules result.

A thin orchestrator, not a generic rule-condition DSL — each of the
three concerns (CTA shape, send_as attribution, suppression key) has
its own small, direct, testable module (cta_rules / send_as_rules /
suppression_rules); this class just calls all three with the right
FeatureSet fields so vera.engine.composer.compose() has one call site
instead of three.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vera.rules.cta_rules import resolve_cta
from vera.rules.send_as_rules import resolve_send_as
from vera.rules.suppression_rules import resolve_suppression_key

if TYPE_CHECKING:
    from vera.features.feature_set import FeatureSet
    from vera.ranking.scored_candidate import RenderedCandidate

__all__ = ["MessageRules", "RuleEngine"]


@dataclass(frozen=True, slots=True)
class MessageRules:
    cta: str
    send_as: str
    suppression_key: str


class RuleEngine:
    def resolve(self, rendered: RenderedCandidate, features: FeatureSet) -> MessageRules:
        if rendered is None or features is None:
            raise TypeError("rendered and features are both required")

        cr = features.customer_relationship
        return MessageRules(
            cta=resolve_cta(rendered.template.cta_type, features.trigger.urgency),
            send_as=resolve_send_as(cr.has_customer_context),
            suppression_key=resolve_suppression_key(
                features.trigger.suppression_key, cr.customer_id
            ),
        )
