"""Pydantic schemas for the four context objects (+ ComposedMessage)."""

from __future__ import annotations

from vera.contexts.category import (
    CategoryContext,
    ContentItem,
    DigestItem,
    OfferTemplate,
    PeerStats,
    SeasonalBeat,
    TrendSignal,
    VoiceProfile,
)
from vera.contexts.composed_message import ComposedMessage
from vera.contexts.customer import (
    Consent,
    CustomerContext,
    CustomerIdentity,
    Preferences,
    Relationship,
)
from vera.contexts.merchant import (
    ConversationTurn,
    CustomerAggregate,
    DeltaSnapshot,
    Identity,
    MerchantContext,
    MerchantOffer,
    PerformanceSnapshot,
    ReviewTheme,
    Subscription,
)
from vera.contexts.trigger import TriggerContext

__all__ = [
    "CategoryContext",
    "ContentItem",
    "DigestItem",
    "OfferTemplate",
    "PeerStats",
    "SeasonalBeat",
    "TrendSignal",
    "VoiceProfile",
    "ComposedMessage",
    "Consent",
    "CustomerContext",
    "CustomerIdentity",
    "Preferences",
    "Relationship",
    "ConversationTurn",
    "CustomerAggregate",
    "DeltaSnapshot",
    "Identity",
    "MerchantContext",
    "MerchantOffer",
    "PerformanceSnapshot",
    "ReviewTheme",
    "Subscription",
    "TriggerContext",
]
