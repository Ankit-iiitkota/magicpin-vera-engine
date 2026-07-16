"""
vera.conversation.reply_facts — ReplyFacts, the grounding bundle for replies.

A mid-conversation reply previously had only the merchant's language
available, so every reply body was a canned one-liner ("Samajh gayi —
bataiye, aage kya karna chahenge?"). But the conversation record keeps
trigger_id, merchant_id and customer_id — everything needed to re-load
the same four context layers the opening message was composed from.
ReplyFacts carries those raw payload dicts (exactly as pushed via POST
/v1/context) so reply composition can cite the same real numbers, dates,
and quotes the opener did — still zero fabrication, because every field
here came from the judge's own context pushes.

Kept as raw dicts, not re-validated models: replies must never fail on a
context that tick already accepted, and the accessors below are all
defensive `.get()` chains that degrade to None.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["ReplyFacts"]


@dataclass(frozen=True)
class ReplyFacts:
    merchant: dict[str, Any] | None = None
    category: dict[str, Any] | None = None
    trigger: dict[str, Any] | None = None
    customer: dict[str, Any] | None = None

    # ── Merchant accessors ───────────────────────────────────────────────────

    @property
    def salutation(self) -> str | None:
        if not self.merchant:
            return None
        identity = self.merchant.get("identity", {})
        first = identity.get("owner_first_name")
        if not first:
            return identity.get("name")
        if self.merchant.get("category_slug") == "dentists":
            return f"Dr. {first}"
        return first

    @property
    def merchant_name(self) -> str | None:
        if not self.merchant:
            return None
        return self.merchant.get("identity", {}).get("name")

    @property
    def active_offers(self) -> list[str]:
        if not self.merchant:
            return []
        return [
            o.get("title", "")
            for o in self.merchant.get("offers", [])
            if o.get("status") == "active" and o.get("title")
        ]

    @property
    def high_risk_count(self) -> int | None:
        if not self.merchant:
            return None
        return (self.merchant.get("customer_aggregate") or {}).get("high_risk_adult_count")

    # ── Trigger accessors ────────────────────────────────────────────────────

    @property
    def trigger_kind(self) -> str | None:
        return self.trigger.get("kind") if self.trigger else None

    @property
    def payload(self) -> dict[str, Any]:
        return (self.trigger or {}).get("payload", {}) or {}

    @property
    def slot_labels(self) -> list[str]:
        slots = self.payload.get("available_slots") or []
        return [s.get("label", "") for s in slots if isinstance(s, dict) and s.get("label")]

    @property
    def digest_item(self) -> dict[str, Any] | None:
        """The digest item this conversation's trigger points at, if any."""
        if not self.category:
            return None
        digest = self.category.get("digest") or []
        wanted = self.payload.get("top_item_id")
        if wanted:
            for item in digest:
                if item.get("id") == wanted:
                    return item
        return digest[0] if digest else None

    @property
    def topic_text(self) -> str:
        """Lowercased corpus of everything this conversation is about.

        Used to recognise that a question like "which film speed do I
        need?" is ON topic for a regulation_change conversation (the DCI
        digest summary mentions film speeds) even though it contains none
        of the generic on-topic keywords.
        """
        parts: list[str] = []
        item = self.digest_item
        if item:
            parts.extend(str(item.get(k, "")) for k in ("title", "summary", "actionable", "source"))
        for value in self.payload.values():
            parts.append(str(value))
        parts.extend(self.active_offers)
        return " ".join(parts).lower()

    # ── Customer accessors ───────────────────────────────────────────────────

    @property
    def customer_first_name(self) -> str | None:
        if not self.customer:
            return None
        name = self.customer.get("identity", {}).get("name")
        return name.split()[0] if name else None

    @property
    def customer_language_pref(self) -> str | None:
        if not self.customer:
            return None
        return self.customer.get("identity", {}).get("language_pref")
