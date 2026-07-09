"""
vera.signals.signal_detector — SignalDetector, Layer 2.

Evaluates a FeatureSet (Phase 3's output) against 15 primitive signal
conditions plus 3 composite rules, producing a SignalSet. Every
detector is a pure `FeatureSet -> evidence-dict-or-None` function —
deterministic, no randomness, no re-reading of raw context (FeatureSet
is the only input type this module ever touches).

Detectors are intentionally direct Python, not a YAML rule DSL — see
signal_definitions.yaml's header comment for why. Composite rules ARE
declarative (plain AND/OR membership over the SignalSet), loaded from
that same YAML file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vera.config import load_yaml
from vera.signals.signal_set import Signal, SignalSet

if TYPE_CHECKING:
    from collections.abc import Callable

    from vera.features.feature_set import FeatureSet

__all__ = ["SignalDetector"]

_DEFINITIONS_PATH = "vera/signals/yaml/signal_definitions.yaml"

# Defaults mirror signal_definitions.yaml's intent; duplicated as literal
# constants so the detector needs zero file I/O to run deterministically
# (matches FeatureExtractor's from_config()/literal-default pattern).
_DEFAULT_REVENUE_DROP_THRESHOLD = -0.20
_DEFAULT_SEARCH_SPIKE_THRESHOLD = 0.20
_DEFAULT_CAMPAIGN_FATIGUE_THRESHOLD = 3
_DEFAULT_LOCAL_DEMAND_THRESHOLD = 0.30
_DEFAULT_SEVERITY = 3

_WEATHER_TRIGGER_PREFIX = "weather"
_COMPETITION_TRIGGER_KIND = "competitor_opened"


class SignalDetector:
    """Detects every signal that applies to a given FeatureSet."""

    def __init__(
        self,
        *,
        revenue_drop_threshold: float = _DEFAULT_REVENUE_DROP_THRESHOLD,
        search_spike_threshold: float = _DEFAULT_SEARCH_SPIKE_THRESHOLD,
        campaign_fatigue_threshold: int = _DEFAULT_CAMPAIGN_FATIGUE_THRESHOLD,
        local_demand_threshold: float = _DEFAULT_LOCAL_DEMAND_THRESHOLD,
        definitions: dict[str, Any] | None = None,
    ) -> None:
        self._revenue_drop_threshold = revenue_drop_threshold
        self._search_spike_threshold = search_spike_threshold
        self._campaign_fatigue_threshold = campaign_fatigue_threshold
        self._local_demand_threshold = local_demand_threshold
        self._definitions = definitions if definitions is not None else {}
        self._primitive_detectors: dict[str, Callable[[FeatureSet], dict[str, Any] | None]] = {
            "RevenueDrop": self._detect_revenue_drop,
            "SearchSpike": self._detect_search_spike,
            "OfferExpiry": self._detect_offer_expiry,
            "FestivalWindow": self._detect_festival_window,
            "ListingIncomplete": self._detect_listing_incomplete,
            "CampaignFatigue": self._detect_campaign_fatigue,
            "CustomerRecall": self._detect_customer_recall,
            "DormantMerchant": self._detect_dormant_merchant,
            "WeekendOpportunity": self._detect_weekend_opportunity,
            "ReviewOpportunity": self._detect_review_opportunity,
            "InventoryRisk": self._detect_inventory_risk,
            "LocalDemand": self._detect_local_demand,
            "ResearchInsight": self._detect_research_insight,
            "WeatherOpportunity": self._detect_weather_opportunity,
            "CompetitionOpportunity": self._detect_competition_opportunity,
        }

    @classmethod
    def from_config(cls, path: str = _DEFINITIONS_PATH) -> SignalDetector:
        definitions = load_yaml(path)
        return cls(definitions=definitions)

    # ── Public API ────────────────────────────────────────────────────────────

    def detect(self, features: FeatureSet) -> SignalSet:
        if features is None:
            raise TypeError("features is required")

        primitives: list[Signal] = []
        for kind, detector in self._primitive_detectors.items():
            evidence = detector(features)
            if evidence is not None:
                primitives.append(self._build_signal(kind, evidence, is_composite=False))

        fired_kinds = {s.kind for s in primitives}
        composites = self._detect_composites(fired_kinds)

        ordered = tuple(sorted(primitives + composites, key=lambda s: -s.severity))
        return SignalSet(signals=ordered)

    # ── Primitive detectors — each: FeatureSet -> evidence dict | None ─────────

    def _detect_revenue_drop(self, f: FeatureSet) -> dict[str, Any] | None:
        calls_delta = f.performance.calls_delta_pct
        views_delta = f.performance.views_delta_pct
        worst = min((d for d in (calls_delta, views_delta) if d is not None), default=None)
        if worst is None or worst > self._revenue_drop_threshold:
            return None
        return {
            "calls_delta_pct": calls_delta,
            "views_delta_pct": views_delta,
            "worst_delta": worst,
        }

    def _detect_search_spike(self, f: FeatureSet) -> dict[str, Any] | None:
        views_delta = f.performance.views_delta_pct
        if views_delta is None or views_delta < self._search_spike_threshold:
            return None
        return {"views_delta_pct": views_delta}

    def _detect_offer_expiry(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.offers.inventory_health != "stale":
            return None
        return {
            "inventory_health": f.offers.inventory_health,
            "days_since_last_campaign": f.campaign_history.days_since_last_campaign,
        }

    def _detect_festival_window(self, f: FeatureSet) -> dict[str, Any] | None:
        if not f.trigger.festival_window:
            return None
        return {"trigger_kind": f.trigger.kind, "payload": dict(f.trigger.payload)}

    def _detect_listing_incomplete(self, f: FeatureSet) -> dict[str, Any] | None:
        missing = [
            name
            for name, value in (("city", f.identity.city), ("locality", f.identity.locality))
            if value is None
        ]
        unverified = f.identity.verified is not True
        if not missing and not unverified:
            return None
        return {"missing_fields": tuple(missing), "verified": f.identity.verified}

    def _detect_campaign_fatigue(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.campaign_history.campaign_fatigue < self._campaign_fatigue_threshold:
            return None
        return {"campaign_fatigue": f.campaign_history.campaign_fatigue}

    def _detect_customer_recall(self, f: FeatureSet) -> dict[str, Any] | None:
        cr = f.customer_relationship
        if not cr.has_customer_context or cr.customer_state not in ("lapsed_soft", "lapsed_hard"):
            return None
        return {
            "customer_id": cr.customer_id,
            "customer_state": cr.customer_state,
            "days_since_last_visit": cr.customer_days_since_last_visit,
        }

    def _detect_dormant_merchant(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.conversation.conversation_recency != "dormant":
            return None
        return {"days_since_last_touch": f.conversation.days_since_last_touch}

    def _detect_weekend_opportunity(self, f: FeatureSet) -> dict[str, Any] | None:
        if not f.temporal.weekend:
            return None
        return {"extracted_at": f.temporal.extracted_at}

    def _detect_review_opportunity(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.business_health.review_trend != "positive":
            return None
        return {
            "review_velocity": f.business_health.review_velocity,
            "review_trend": f.business_health.review_trend,
        }

    def _detect_inventory_risk(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.offers.inventory_health != "empty":
            return None
        return {"offer_count": f.offers.offer_count}

    def _detect_local_demand(self, f: FeatureSet) -> dict[str, Any] | None:
        hot = [
            t
            for t in f.category.trend_signals
            if (t.delta_yoy or 0) >= self._local_demand_threshold
        ]
        if not hot:
            return None
        top = max(hot, key=lambda t: t.delta_yoy or 0)
        return {"query": top.query, "delta_yoy": top.delta_yoy}

    def _detect_research_insight(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.category.digest_count == 0:
            return None
        top = f.category.digest[0]
        return {
            "digest_count": f.category.digest_count,
            "top_item_id": top.id,
            "top_item_title": top.title,
        }

    def _detect_weather_opportunity(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.trigger.is_expired or not f.trigger.kind.startswith(_WEATHER_TRIGGER_PREFIX):
            return None
        return {"trigger_kind": f.trigger.kind, "payload": dict(f.trigger.payload)}

    def _detect_competition_opportunity(self, f: FeatureSet) -> dict[str, Any] | None:
        if f.trigger.is_expired or f.trigger.kind != _COMPETITION_TRIGGER_KIND:
            return None
        return {"trigger_kind": f.trigger.kind, "payload": dict(f.trigger.payload)}

    # ── Composite signals ────────────────────────────────────────────────────

    def _detect_composites(self, fired_kinds: set[str]) -> list[Signal]:
        rules = self._definitions.get("composite_signals") or _FALLBACK_COMPOSITE_RULES
        composites: list[Signal] = []
        for name, rule in rules.items():
            requires_all = set(rule.get("requires_all", ()))
            requires_any = set(rule.get("requires_any", ()))
            if requires_all and not requires_all.issubset(fired_kinds):
                continue
            if requires_any and not (requires_any & fired_kinds):
                continue
            if not requires_all and not requires_any:
                continue
            severity = rule.get("severity", _DEFAULT_SEVERITY)
            description = rule.get("description", name)
            composites.append(
                Signal(
                    kind=name,
                    severity=severity,
                    is_composite=True,
                    rationale_hint=description,
                    evidence={
                        "requires_all": tuple(requires_all),
                        "requires_any": tuple(requires_any),
                    },
                )
            )
        return composites

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _build_signal(self, kind: str, evidence: dict[str, Any], *, is_composite: bool) -> Signal:
        meta = (self._definitions.get("signals") or {}).get(kind, {})
        severity = meta.get("severity", _FALLBACK_SIGNAL_SEVERITIES.get(kind, _DEFAULT_SEVERITY))
        description = meta.get("description", kind)
        return Signal(
            kind=kind,
            severity=severity,
            is_composite=is_composite,
            rationale_hint=description,
            evidence=evidence,
        )


# Fallback severities/composite rules, used only if signal_definitions.yaml
# can't be loaded (e.g. a bare `SignalDetector()` with no from_config()
# call) — keeps the detector fully usable with zero file I/O and correct
# severity ordering, same rationale as FeatureExtractor's literal defaults.
_FALLBACK_SIGNAL_SEVERITIES: dict[str, int] = {
    "RevenueDrop": 5,
    "SearchSpike": 3,
    "OfferExpiry": 3,
    "FestivalWindow": 2,
    "ListingIncomplete": 4,
    "CampaignFatigue": 3,
    "CustomerRecall": 4,
    "DormantMerchant": 4,
    "WeekendOpportunity": 1,
    "ReviewOpportunity": 2,
    "InventoryRisk": 4,
    "LocalDemand": 3,
    "ResearchInsight": 2,
    "WeatherOpportunity": 2,
    "CompetitionOpportunity": 3,
}
_FALLBACK_COMPOSITE_RULES: dict[str, dict[str, Any]] = {
    "UrgentWinback": {"requires_all": ["DormantMerchant", "CustomerRecall"], "severity": 5},
    "GrowthMomentum": {"requires_all": ["SearchSpike", "ReviewOpportunity"], "severity": 4},
    "StaleAndFatigued": {
        "requires_all": ["CampaignFatigue"],
        "requires_any": ["OfferExpiry", "InventoryRisk"],
        "severity": 5,
    },
}
