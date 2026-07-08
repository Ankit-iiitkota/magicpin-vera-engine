"""
vera.contexts.merchant — MerchantContext schema.

Mirrors challenge-brief.md §4.2 and challenge-testing-brief.md §3.2.
Per-merchant state: identity, subscription, performance, offers,
conversation history, customer aggregate, and derived signals.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Identity(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    city: str | None = None
    locality: str | None = None
    place_id: str | None = None
    verified: bool | None = None
    languages: list[str] = Field(default_factory=list)
    owner_first_name: str | None = None
    established_year: int | None = None


class Subscription(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    plan: str | None = None
    days_remaining: int | None = None
    days_since_expiry: int | None = None
    renewed_at: str | None = None


class DeltaSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    views_pct: float | None = None
    calls_pct: float | None = None
    ctr_pct: float | None = None


class PerformanceSnapshot(BaseModel):
    model_config = ConfigDict(extra="allow")

    window_days: int = 30
    views: int | None = None
    calls: int | None = None
    directions: int | None = None
    ctr: float | None = None
    leads: int | None = None
    delta_7d: DeltaSnapshot | None = None


class MerchantOffer(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    title: str
    status: str
    started: str | None = None
    ended: str | None = None


class ConversationTurn(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    ts: str
    from_: str = Field(alias="from")
    body: str
    engagement: str | None = None


class CustomerAggregate(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_unique_ytd: int | None = None
    lapsed_180d_plus: int | None = None
    lapsed_90d_plus: int | None = None
    retention_6mo_pct: float | None = None
    retention_3mo_pct: float | None = None
    high_risk_adult_count: int | None = None


class ReviewTheme(BaseModel):
    model_config = ConfigDict(extra="allow")

    theme: str
    sentiment: str | None = None
    occurrences_30d: int | None = None
    common_quote: str | None = None
    trend: str | None = None


class MerchantContext(BaseModel):
    """A specific business's current state with Vera."""

    model_config = ConfigDict(extra="allow")

    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Subscription
    performance: PerformanceSnapshot
    offers: list[MerchantOffer] = Field(default_factory=list)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    customer_aggregate: CustomerAggregate | None = None
    signals: list[str] = Field(default_factory=list)
    review_themes: list[ReviewTheme] = Field(default_factory=list)
