"""
vera.candidates.candidate_generator — CandidateGenerator, Layer 4.

Generates 3-5 Candidates per (FeatureSet, SignalSet, GoalContext):
- the primary goal gets one candidate per lever in its top-N affinity
  list (config/weights.yaml's goal_lever_affinity — 3 levers per goal
  today, so 3 candidates), each a different persuasion angle on the
  SAME underlying facts;
- each secondary goal (if any) contributes one more candidate using its
  own top lever, capped so the total never exceeds 5.

Consumes FeatureSet + SignalSet + GoalContext only — never raw context.
Slot extraction is per-goal (not per-lever): the lever changes HOW a
candidate is framed later at template-rendering time, not WHAT facts
are available to frame — those facts come straight out of FeatureSet,
so there's no hallucination risk here regardless of which lever wins.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from vera.candidates.candidate import Candidate
from vera.config import load_yaml
from vera.rules.language_rules import pick_language

if TYPE_CHECKING:
    from collections.abc import Callable

    from vera.features.feature_set import FeatureSet
    from vera.goals.goal_context import GoalContext
    from vera.signals.signal_set import SignalSet

__all__ = ["CandidateGenerator"]

_WEIGHTS_PATH = "config/weights.yaml"
_MAX_CANDIDATES = 5
_DEFAULT_LEVERS_PER_GOAL = 3

# Mirrors config/weights.yaml's goal_lever_affinity — used when the YAML
# is unavailable, same "zero file I/O required" rationale as the rest of
# this pipeline's from_config()/literal-default pattern.
_DEFAULT_LEVER_AFFINITY: dict[str, tuple[str, ...]] = {
    "RECOVER_REVENUE": ("loss_aversion", "specificity", "reciprocity"),
    "WIN_BACK_CUSTOMERS": ("reciprocity", "curiosity", "loss_aversion"),
    "REDUCE_CHURN": ("reciprocity", "asking_merchant", "curiosity"),
    "PROMOTE_OFFERS": ("specificity", "loss_aversion", "social_proof"),
    "IMPROVE_LISTINGS": ("loss_aversion", "specificity", "reciprocity"),
    "COLLECT_REVIEWS": ("social_proof", "reciprocity", "asking_merchant"),
    "INCREASE_SALES": ("loss_aversion", "social_proof", "specificity"),
    "INCREASE_VISIBILITY": ("social_proof", "specificity", "curiosity"),
}


class CandidateGenerator:
    def __init__(
        self,
        lever_affinity: dict[str, tuple[str, ...]] | None = None,
        levers_per_goal: int = _DEFAULT_LEVERS_PER_GOAL,
    ) -> None:
        self._lever_affinity = lever_affinity or _DEFAULT_LEVER_AFFINITY
        self._levers_per_goal = levers_per_goal

    @classmethod
    def from_config(cls, path: str = _WEIGHTS_PATH) -> CandidateGenerator:
        raw = (load_yaml(path).get("goal_lever_affinity")) or {}
        affinity = {goal: tuple(levers) for goal, levers in raw.items()} if raw else None
        return cls(lever_affinity=affinity)

    def generate(
        self, features: FeatureSet, signal_set: SignalSet, goal_context: GoalContext
    ) -> tuple[Candidate, ...]:
        if features is None or signal_set is None or goal_context is None:
            raise TypeError("features, signal_set, and goal_context are all required")

        language = self._pick_language(features)
        candidates: list[Candidate] = []
        priority = 1

        primary_levers = self._levers_for(goal_context.primary_goal)[: self._levers_per_goal]
        for lever in primary_levers:
            candidates.append(
                self._build_candidate(
                    features, signal_set, goal_context.primary_goal, lever, language, priority
                )
            )
            priority += 1

        for secondary_goal in goal_context.secondary_goals:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            lever = self._levers_for(secondary_goal)[0]
            candidates.append(
                self._build_candidate(
                    features, signal_set, secondary_goal, lever, language, priority
                )
            )
            priority += 1

        return tuple(candidates)

    def _levers_for(self, goal: str) -> tuple[str, ...]:
        return self._lever_affinity.get(goal, ("specificity",))

    def _build_candidate(
        self,
        features: FeatureSet,
        signal_set: SignalSet,
        goal: str,
        lever: str,
        language: str,
        priority: int,
    ) -> Candidate:
        slot_builder = _GOAL_SLOT_BUILDERS.get(goal, _slots_fallback)
        slots = slot_builder(features, signal_set)
        candidate_id = f"cand_{features.trigger.id}_{goal.lower()}_{lever}"
        return Candidate(
            candidate_id=candidate_id,
            goal=goal,
            compulsion_lever=lever,
            language=language,
            slots=MappingProxyType(slots),
            priority=priority,
        )

    @staticmethod
    def _pick_language(features: FeatureSet) -> str:
        cr = features.customer_relationship
        customer_pref = cr.customer_language_pref if cr.has_customer_context else None
        return pick_language(features.identity.languages, customer_pref)


# ── Per-goal slot extraction — every value traces to a specific FeatureSet
#    field, so template rendering never has to invent a fact. ──────────────


def _base_slots(f: FeatureSet) -> dict[str, Any]:
    return {
        "merchant_name": f.identity.name,
        "owner_first_name": f.identity.owner_first_name,
        "category_slug": f.identity.category_slug,
        "locality": f.identity.locality,
        "city": f.identity.city,
    }


def _slots_recover_revenue(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    calls_delta = f.performance.calls_delta_pct
    views_delta = f.performance.views_delta_pct
    if calls_delta is not None and (views_delta is None or calls_delta <= views_delta):
        metric_label, metric_delta = "calls", calls_delta
    else:
        metric_label, metric_delta = "views", views_delta
    slots.update(
        {
            "metric_label": metric_label,
            "metric_delta_pct": metric_delta,
            "current_ctr": f.performance.ctr,
            "peer_avg_ctr": f.category.peer_avg_ctr,
        }
    )
    return slots


def _slots_win_back_customers(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    cr = f.customer_relationship
    active_offer = next((o.title for o in f.offers.offers if o.status == "active"), None)
    slots.update(
        {
            "customer_name": cr.customer_name,
            "customer_id": cr.customer_id,
            "customer_state": cr.customer_state,
            "days_since_last_visit": cr.customer_days_since_last_visit,
            "active_offer_title": active_offer,
        }
    )
    return slots


def _slots_reduce_churn(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    slots.update(
        {
            "campaign_fatigue": f.campaign_history.campaign_fatigue,
            "days_since_last_touch": f.conversation.days_since_last_touch,
            "conversation_recency": f.conversation.conversation_recency,
        }
    )
    return slots


def _slots_promote_offers(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    catalog_pick = f.category.offer_catalog[0] if f.category.offer_catalog else None
    slots.update(
        {
            "inventory_health": f.offers.inventory_health,
            "suggested_offer_title": catalog_pick.title if catalog_pick else None,
            "suggested_offer_value": catalog_pick.value if catalog_pick else None,
        }
    )
    return slots


def _slots_improve_listings(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    signal = ss.get("ListingIncomplete")
    missing = signal.evidence.get("missing_fields", ()) if signal else ()
    slots.update({"verified": f.identity.verified, "missing_fields": tuple(missing)})
    return slots


def _slots_collect_reviews(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    top_theme = f.business_health.review_themes[0] if f.business_health.review_themes else None
    slots.update(
        {
            "review_velocity": f.business_health.review_velocity,
            "review_trend": f.business_health.review_trend,
            "top_review_theme": top_theme.theme if top_theme else None,
        }
    )
    return slots


def _slots_increase_sales(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    demand_signal = ss.get("LocalDemand")
    festival_signal = ss.get("FestivalWindow")
    slots.update(
        {
            "weekend": f.temporal.weekend,
            "season": f.temporal.season,
            # First matched seasonal_beats note for `now`'s month (already
            # category-specific, real data) — a stronger fallback fact than
            # the generic "weekend slots fill fast" line when no trend or
            # festival signal fired.
            "season_note": f.temporal.season[0] if f.temporal.season else None,
            "trigger_kind": f.trigger.kind,
            "trend_query": demand_signal.evidence.get("query") if demand_signal else None,
            "trend_delta_yoy": demand_signal.evidence.get("delta_yoy") if demand_signal else None,
            "festival_days_until": (
                (festival_signal.evidence.get("payload") or {}).get("days_until")
                if festival_signal
                else None
            ),
            # Last-resort real fact before falling back to purely generic
            # copy: a positive views trend is still a concrete, verifiable
            # number, unlike "your weekend slots typically fill fastest".
            "views_delta_pct": f.performance.views_delta_pct,
        }
    )
    return slots


def _slots_increase_visibility(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    slots = _base_slots(f)
    top_digest = f.category.digest[0] if f.category.digest else None
    slots.update(
        {
            "views_delta_pct": f.performance.views_delta_pct,
            "digest_title": top_digest.title if top_digest else None,
            "digest_source": top_digest.source if top_digest else None,
            "competitor_trigger": f.trigger.kind == "competitor_opened",
        }
    )
    return slots


def _slots_fallback(f: FeatureSet, ss: SignalSet) -> dict[str, Any]:
    return _base_slots(f)


_GOAL_SLOT_BUILDERS: dict[str, Callable[[FeatureSet, SignalSet], dict[str, Any]]] = {
    "RECOVER_REVENUE": _slots_recover_revenue,
    "WIN_BACK_CUSTOMERS": _slots_win_back_customers,
    "REDUCE_CHURN": _slots_reduce_churn,
    "PROMOTE_OFFERS": _slots_promote_offers,
    "IMPROVE_LISTINGS": _slots_improve_listings,
    "COLLECT_REVIEWS": _slots_collect_reviews,
    "INCREASE_SALES": _slots_increase_sales,
    "INCREASE_VISIBILITY": _slots_increase_visibility,
}
