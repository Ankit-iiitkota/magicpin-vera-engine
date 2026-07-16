"""
vera.engine.composer — the composition entry point, Phase 8.

`compose()` is the function signature defined by challenge-brief.md §5:

    compose(category, merchant, trigger, customer=None) -> ComposedMessage

Orchestrates the full deterministic pipeline:

    FeatureExtractor -> SignalDetector -> GoalInferenceEngine ->
    CandidateGenerator -> CandidateRanker -> FallbackChain -> RuleEngine
    -> ComposedMessage

Pure and synchronous, on purpose: every input is already-validated data
(the four context objects) and every step is deterministic given those
inputs plus `now`. Suppression and anti-repetition are NOT part of this
function — they're async, store-backed concerns the API layer (POST
/v1/tick) applies before deciding to call compose() at all, and after
deciding whether to actually send what it returns. See
vera.engine.suppression / vera.engine.anti_repetition.

NOTE on field naming: the return type's message-text field is `body`,
matching challenge-brief.md §5 and §7.1 and every JSON example in
challenge-testing-brief.md (§2.2's ActionItem.body, §2.3's
ReplySendResponse.body) verbatim — that's the actual contract the judge
harness parses. Kept as `body` rather than `message` for that reason.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from vera.candidates.candidate_generator import CandidateGenerator
from vera.contexts.composed_message import ComposedMessage
from vera.fallback.fallback_chain import FallbackChain
from vera.features.extractor import FeatureExtractor
from vera.goals.goal_inferrer import GoalInferenceEngine
from vera.ranking.candidate_ranker import CandidateRanker
from vera.rules.rule_engine import RuleEngine
from vera.engine.trigger_grounding import ground
from vera.scoring.compulsion_checker import CompulsionChecker
from vera.signals.signal_detector import SignalDetector
from vera.tracing.trace_builder import TraceBuilder, build_rationale

if TYPE_CHECKING:
    from datetime import datetime

    from vera.contexts.category import CategoryContext
    from vera.contexts.customer import CustomerContext
    from vera.contexts.merchant import MerchantContext
    from vera.contexts.trigger import TriggerContext

__all__ = ["Composer", "compose"]

logger = structlog.get_logger(__name__)


class Composer:
    """Owns one instance of every pipeline stage — construct once, reuse across calls."""

    def __init__(
        self,
        feature_extractor: FeatureExtractor | None = None,
        signal_detector: SignalDetector | None = None,
        goal_inference_engine: GoalInferenceEngine | None = None,
        candidate_generator: CandidateGenerator | None = None,
        candidate_ranker: CandidateRanker | None = None,
        fallback_chain: FallbackChain | None = None,
        rule_engine: RuleEngine | None = None,
        compulsion_checker: CompulsionChecker | None = None,
    ) -> None:
        self._feature_extractor = feature_extractor or FeatureExtractor.from_config()
        self._signal_detector = signal_detector or SignalDetector.from_config()
        self._goal_inference_engine = goal_inference_engine or GoalInferenceEngine.from_config()
        self._candidate_generator = candidate_generator or CandidateGenerator.from_config()
        self._candidate_ranker = candidate_ranker or CandidateRanker.from_config()
        self._fallback_chain = fallback_chain or FallbackChain.from_config()
        self._rule_engine = rule_engine or RuleEngine()
        self._compulsion_checker = compulsion_checker or CompulsionChecker()
        self._trace_builder = TraceBuilder()

    def compose(
        self,
        category: CategoryContext,
        merchant: MerchantContext,
        trigger: TriggerContext,
        customer: CustomerContext | None = None,
        *,
        now: datetime | None = None,
    ) -> ComposedMessage:
        # Trigger-payload-grounded kinds compose directly from the trigger's
        # own facts (deadline, quote, festival date, dip %) — the generic
        # pipeline below infers goals from merchant state only and would
        # never mention them. See vera.engine.trigger_grounding.
        grounded = ground(category, merchant, trigger, customer)
        if grounded is not None:
            logger.info(
                "compose_decision",
                trigger_id=trigger.id,
                merchant_id=merchant.merchant_id,
                trigger_kind=trigger.kind,
                grounded=True,
            )
            return grounded

        features = self._feature_extractor.extract(category, merchant, trigger, customer, now=now)
        signals = self._signal_detector.detect(features)
        goal_context = self._goal_inference_engine.infer(signals)
        candidates = self._candidate_generator.generate(features, signals, goal_context)
        ranked = self._candidate_ranker.rank(candidates, features, goal_context)
        rendered, fallback_level = self._fallback_chain.resolve(ranked, features)

        message_rules = self._rule_engine.resolve(rendered, features)
        lever_verified = self._compulsion_checker.check(
            rendered.body, rendered.candidate.compulsion_lever
        )

        winner_score = None
        if fallback_level == "L0":
            winner_score = next(
                (
                    sc.total
                    for sc in ranked
                    if sc.rendered.candidate.candidate_id == rendered.candidate.candidate_id
                ),
                None,
            )

        trace = self._trace_builder.build(
            trigger_id=trigger.id,
            merchant_id=merchant.merchant_id,
            signal_set=signals,
            goal_context=goal_context,
            candidate_count=len(candidates),
            rendered=rendered,
            winner_score=winner_score,
            fallback_level=fallback_level,
            compulsion_lever_verified=lever_verified,
        )
        logger.info(
            "compose_decision",
            trigger_id=trace.trigger_id,
            merchant_id=trace.merchant_id,
            trigger_kind=trigger.kind,
            primary_goal=trace.primary_goal,
            winner_candidate_id=trace.winner_candidate_id,
            winner_score=trace.winner_score,
            fallback_level=trace.fallback_level,
            compulsion_lever_verified=trace.compulsion_lever_verified,
        )

        return ComposedMessage(
            body=rendered.body,
            cta=message_rules.cta,
            send_as=message_rules.send_as,
            suppression_key=message_rules.suppression_key,
            rationale=build_rationale(trace),
        )


_default_composer: Composer | None = None


def _get_default_composer() -> Composer:
    global _default_composer
    if _default_composer is None:
        _default_composer = Composer()
    return _default_composer


def compose(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None = None,
) -> ComposedMessage:
    """Compose the next outbound message from the four context layers."""
    return _get_default_composer().compose(category, merchant, trigger, customer)
