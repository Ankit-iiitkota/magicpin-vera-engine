"""
vera.contexts.category — CategoryContext schema.

Mirrors challenge-brief.md §4.1 and challenge-testing-brief.md §3.1.
Slow-changing knowledge pack shared across all merchants in a vertical.

All nested models use `extra="allow"` so fields present in the dataset
but not yet consumed by the pipeline (or added later via context
injection, per testing-brief.md §4 Phase 3) are preserved rather than
silently dropped.
"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class OfferTemplate(BaseModel):
    """A canonical service+price pattern for a vertical."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    title: str
    value: str | None = None
    audience: str | None = None
    type: str | None = None


class VoiceProfile(BaseModel):
    """Tone, vocabulary, and taboos for a category's voice."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    tone: str
    register_: str | None = Field(default=None, alias="register")
    code_mix: str | None = None
    vocab_allowed: list[str] = Field(default_factory=list)
    vocab_taboo: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("vocab_taboo", "taboos"),
    )
    salutation_examples: list[str] = Field(default_factory=list)
    tone_examples: list[str] = Field(default_factory=list)


class PeerStats(BaseModel):
    """City/vertical-scoped benchmarks used to anchor comparative messages."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    scope: str | None = None
    avg_rating: float | None = None
    avg_reviews: float | None = Field(
        default=None, validation_alias=AliasChoices("avg_reviews", "avg_review_count")
    )
    avg_views_30d: float | None = None
    avg_calls_30d: float | None = None
    avg_directions_30d: float | None = None
    avg_ctr: float | None = None
    avg_photos: float | None = None
    avg_post_freq_days: float | None = None
    retention_6mo_pct: float | None = None


class DigestItem(BaseModel):
    """A single curated research / compliance / trend / CDE item, source-cited."""

    model_config = ConfigDict(extra="allow")

    id: str
    kind: str
    title: str
    source: str
    summary: str | None = None
    actionable: str | None = None
    trial_n: int | None = None
    patient_segment: str | None = None
    date: str | None = None
    credits: int | None = None


class ContentItem(BaseModel):
    """Patient/customer-reading-level content the merchant can reshare."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    channel: str | None = None
    length_seconds: int | None = None
    body: str


class SeasonalBeat(BaseModel):
    """A recurring seasonal cycle relevant to the category."""

    model_config = ConfigDict(extra="allow")

    month_range: str
    note: str


class TrendSignal(BaseModel):
    """A search/query trend signal for the category."""

    model_config = ConfigDict(extra="allow")

    query: str
    delta_yoy: float | None = None
    segment_age: str | None = None
    skew: str | None = None


class CategoryContext(BaseModel):
    """Slow-changing knowledge pack for a vertical (e.g. 'dentists')."""

    model_config = ConfigDict(extra="allow")

    slug: str
    display_name: str | None = None
    voice: VoiceProfile
    offer_catalog: list[OfferTemplate] = Field(default_factory=list)
    peer_stats: PeerStats | None = None
    digest: list[DigestItem] = Field(default_factory=list)
    patient_content_library: list[ContentItem] = Field(default_factory=list)
    seasonal_beats: list[SeasonalBeat] = Field(default_factory=list)
    trend_signals: list[TrendSignal] = Field(default_factory=list)
    regulatory_authorities: list[str] = Field(default_factory=list)
    professional_journals: list[str] = Field(default_factory=list)
