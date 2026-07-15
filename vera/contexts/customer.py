"""
vera.contexts.customer — CustomerContext schema.

Mirrors challenge-brief.md §4.4 and challenge-testing-brief.md §3.3.
Only populated for customer-facing (merchant_on_behalf) messages.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CustomerIdentity(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    phone_redacted: str | None = None
    language_pref: str | None = None
    age_band: str | None = None


class Relationship(BaseModel):
    model_config = ConfigDict(extra="allow")

    first_visit: str | None = None
    last_visit: str | None = None
    visits_total: int | None = None
    services_received: list[str] = Field(default_factory=list)
    lifetime_value: float | None = None
    favourite_dish: str | None = None


class Preferences(BaseModel):
    model_config = ConfigDict(extra="allow")

    preferred_slots: str | None = None
    channel: str | None = None
    reminder_opt_in: bool | None = None


class Consent(BaseModel):
    model_config = ConfigDict(extra="allow")

    opted_in_at: str | None = None
    scope: list[str] = Field(default_factory=list)


class CustomerContext(BaseModel):
    """The merchant's customer, and their state with this merchant."""

    model_config = ConfigDict(extra="allow")

    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship
    state: Literal["new", "active", "lapsed_soft", "lapsed_hard", "churned"]
    preferences: Preferences
    consent: Consent
