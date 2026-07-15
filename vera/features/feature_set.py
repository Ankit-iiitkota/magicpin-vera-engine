"""
vera.features.feature_set — the FeatureSet contract.

FeatureSet is the ONLY thing any layer past feature extraction is
allowed to consume. It is deliberately split into two kinds of field:

  1. Passthrough reference data (offers, digest items, conversation
     turns, trigger payload, ...) — later phases (templates, candidate
     generation) need this content verbatim to compose real messages,
     so it's carried through as small immutable record types rather
     than flattened away.
  2. Computed signals (ctr_vs_peer_delta, campaign_fatigue, season,
     ...) — derived, deterministic values computed once here so no
     downstream layer has to re-derive them from raw context data.

Every dataclass here is frozen + slotted: a FeatureSet, once built, can
never be mutated. Collections are `tuple`, not `list`, for the same
reason. `Mapping` (not `dict`) + `MappingProxyType` for the one
genuinely-opaque passthrough (trigger.payload, whose shape depends on
`trigger.kind` and isn't modelled per-kind until Phase 8's strategies).

Immutable, but deliberately not hashable: trigger.payload's dict-backed
Mapping can't be hashed without deep-freezing arbitrary nested JSON, and
nothing in this system needs a FeatureSet as a dict/set key — only
equality (for determinism checks) and read access. `first == second` is
the tool for "did I get the same output"; `hash(first)` will raise.

Missing-value convention (applies uniformly across every field below):
  - scalars: `None` means "not present in the source data" — never a
    magic number, empty string, or exception.
  - collections: absent/empty source data means an empty tuple `()`,
    never `None`.
This is the one and only representation for "missing" — see
FeatureValidator and the extractor's docstring for how that's enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


# ── Small immutable passthrough records ─────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OfferRecord:
    id: str | None
    title: str
    status: str
    started: str | None
    ended: str | None


@dataclass(frozen=True, slots=True)
class OfferTemplateRecord:
    id: str | None
    title: str
    value: str | None
    audience: str | None
    type: str | None


@dataclass(frozen=True, slots=True)
class DigestItemRecord:
    id: str
    kind: str
    title: str
    source: str
    summary: str | None
    actionable: str | None


@dataclass(frozen=True, slots=True)
class SeasonalBeatRecord:
    month_range: str
    note: str


@dataclass(frozen=True, slots=True)
class TrendSignalRecord:
    query: str
    delta_yoy: float | None


@dataclass(frozen=True, slots=True)
class ConversationTurnRecord:
    ts: str
    from_role: str
    body: str
    engagement: str | None


@dataclass(frozen=True, slots=True)
class ReviewThemeRecord:
    theme: str
    sentiment: str | None
    occurrences_30d: int | None


# ── Section dataclasses ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdentityFeatures:
    merchant_id: str
    category_slug: str
    name: str
    city: str | None
    locality: str | None
    place_id: str | None
    verified: bool | None
    languages: tuple[str, ...]
    owner_first_name: str | None
    established_year: int | None


@dataclass(frozen=True, slots=True)
class MerchantProfileFeatures:
    subscription_status: str | None
    plan: str | None
    days_remaining: int | None
    days_since_expiry: int | None
    is_subscription_active: bool
    renewal_due_soon: bool


@dataclass(frozen=True, slots=True)
class PerformanceFeatures:
    window_days: int
    views: int | None
    calls: int | None
    directions: int | None
    ctr: float | None
    leads: int | None
    views_delta_pct: float | None
    calls_delta_pct: float | None
    ctr_delta_pct: float | None


@dataclass(frozen=True, slots=True)
class OfferFeatures:
    offers: tuple[OfferRecord, ...]
    offer_count: int
    active_offer_count: int
    has_live_offer: bool
    inventory_health: str  # "healthy" | "stale" | "empty"


@dataclass(frozen=True, slots=True)
class CampaignHistoryFeatures:
    """
    "Campaign" == a deployed offer (MerchantOffer). This schema has no
    dedicated campaign entity, and each offer's `started` date is the
    closest thing to a campaign-launch timestamp it carries.
    """

    last_campaign_title: str | None
    last_campaign_started_at: str | None
    days_since_last_campaign: int | None
    campaign_count: int
    campaign_fatigue: int  # consecutive unanswered Vera touches, most-recent-first


@dataclass(frozen=True, slots=True)
class BusinessHealthFeatures:
    signals: tuple[str, ...]
    ctr_vs_peer_delta: float | None
    #: Always None: MerchantContext carries no numeric merchant-rating
    #: field in this dataset's schema (only CategoryContext.peer_stats.
    #: avg_rating exists, which is a peer *benchmark*, not this
    #: merchant's own rating) — computing a delta would mean inventing
    #: a number, which "no hallucination" rules out.
    rating_delta: float | None
    review_velocity: int | None  # sum of review_themes[].occurrences_30d
    review_trend: str | None  # "positive" | "mixed" | "negative"
    review_themes: tuple[ReviewThemeRecord, ...]
    merchant_growth_trend: str  # "growing" | "declining" | "stable" | "unknown"


@dataclass(frozen=True, slots=True)
class ConversationSummaryFeatures:
    turns: tuple[ConversationTurnRecord, ...]
    turn_count: int
    last_from: str | None
    last_engagement: str | None
    last_message_at: str | None
    days_since_last_touch: int | None
    days_since_last_reply: int | None
    conversation_recency: str  # "active" | "recent" | "dormant" | "none"


@dataclass(frozen=True, slots=True)
class CustomerRelationshipFeatures:
    # Merchant-level aggregate — always available (from MerchantContext).
    total_unique_ytd: int | None
    lapsed_count: int | None
    retention_pct: float | None
    high_risk_adult_count: int | None
    # Per-customer detail — only when a CustomerContext was supplied.
    has_customer_context: bool
    customer_id: str | None
    customer_name: str | None
    customer_state: str | None
    customer_language_pref: str | None
    customer_visits_total: int | None
    customer_lifetime_value: float | None
    customer_last_visit: str | None
    customer_days_since_last_visit: int | None
    customer_preferred_slots: str | None
    customer_loyalty_score: float | None


@dataclass(frozen=True, slots=True)
class TriggerFeatures:
    id: str
    scope: str
    kind: str
    source: str
    urgency: int
    suppression_key: str
    expires_at: str | None
    days_until_expiry: int | None
    is_expired: bool
    festival_window: bool
    payload: Mapping[str, Any]  # kind-specific passthrough — see trigger.kind


@dataclass(frozen=True, slots=True)
class CategoryFeatures:
    slug: str
    display_name: str | None
    voice_tone: str | None
    vocab_allowed: tuple[str, ...]
    vocab_taboo: tuple[str, ...]
    salutation_examples: tuple[str, ...]
    peer_avg_rating: float | None
    peer_avg_ctr: float | None
    peer_avg_reviews: float | None
    offer_catalog: tuple[OfferTemplateRecord, ...]
    digest: tuple[DigestItemRecord, ...]
    digest_count: int
    seasonal_beats: tuple[SeasonalBeatRecord, ...]
    trend_signals: tuple[TrendSignalRecord, ...]


@dataclass(frozen=True, slots=True)
class TemporalFeatures:
    extracted_at: str  # ISO snapshot of the `now` used for this extraction
    season: tuple[str, ...]  # every category.seasonal_beats note whose month_range matches `now`
    weekend: bool
    #: Always None: no business-hours field exists anywhere in the
    #: context schemas — see rating_delta's docstring for the same
    #: "don't invent data" rationale.
    business_open_now: bool | None


@dataclass(frozen=True, slots=True)
class FeatureSet:
    """The complete, immutable, self-sufficient feature representation
    of one (category, merchant, trigger, customer?) composition input.
    """

    identity: IdentityFeatures
    merchant_profile: MerchantProfileFeatures
    performance: PerformanceFeatures
    offers: OfferFeatures
    campaign_history: CampaignHistoryFeatures
    business_health: BusinessHealthFeatures
    conversation: ConversationSummaryFeatures
    customer_relationship: CustomerRelationshipFeatures
    trigger: TriggerFeatures
    category: CategoryFeatures
    temporal: TemporalFeatures


def freeze_mapping(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Wrap a dict as a read-only mapping; None becomes an empty mapping."""
    return MappingProxyType(dict(payload) if payload else {})
