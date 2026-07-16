"""
vera.conversation.customer_reply — CustomerReplyHandler.

Replies where from_role == "customer" are the merchant's OWN customer
answering a merchant_on_behalf send (a recall with slot options, a
refill reminder, ...). Routing them through the merchant state machine
was actively wrong: a customer picking a slot ("1" / "Wed works") tripped
the merchant commit path and got back "Badhiya, aage badh rahi hoon —
2 minute mein update kar deti hoon" — Vera talking shop to the wrong
person. This handler speaks AS the merchant TO the customer:

  1. stop/hostile        -> end (opt-out honoured immediately)
  2. slot pick           -> confirm the EXACT slot label from the trigger
  3. decline/reschedule  -> re-offer the real slots or ask for a time
  4. price question      -> quote the merchant's live offer
  5. anything else       -> ask for their preferred time (stay useful)

All slot labels and prices come from the same trigger/merchant contexts
the opening message used — nothing invented.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vera.conversation.state_machine import ReplyDecision

if TYPE_CHECKING:
    from vera.conversation.reply_facts import ReplyFacts

__all__ = ["CustomerReplyHandler"]

_MAX_BODY = 320

_STOP_RE = re.compile(
    r"\b(stop|unsubscribe|not interested|leave me alone|don'?t message|mat bhejo|nahi chahiye|band karo|spam)\b",
    re.IGNORECASE,
)
_DECLINE_RE = re.compile(
    r"\b(can'?t|cannot|busy|reschedule|another time|different time|not (that|this)|nahi (ho|aa)|some other)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"\b(price|cost|charge|fee|how much|kitna|kitne)\b", re.IGNORECASE)
_YES_RE = re.compile(r"\b(yes|ok(ay)?|sure|confirm|book|done|haan|theek hai|chalega|pakka)\b", re.IGNORECASE)

_DAY_TOKENS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _hi(language: str) -> bool:
    return language in ("hi", "hi-en")


def _cap(body: str) -> str:
    return body if len(body) <= _MAX_BODY else body[: _MAX_BODY - 1].rstrip() + "…"


class CustomerReplyHandler:
    def decide(self, message: str, language: str, facts: ReplyFacts | None) -> ReplyDecision:
        name = (facts.customer_first_name if facts else None) or ""
        name_part = f" {name}" if name else ""
        hi = _hi(language)
        slots = facts.slot_labels if facts else []

        if _STOP_RE.search(message):
            return ReplyDecision(
                action="end",
                body=None,
                cta=None,
                wait_seconds=None,
                rationale="customer opted out — ending immediately, no further sends",
                engagement_tag=None,
            )

        picked = self._pick_slot(message, slots)
        if picked is not None:
            body = (
                f"Perfect{name_part}! {picked} confirm ho gaya hai ✅ Hum ek din pehle reminder bhej denge. "
                "Reschedule karna ho toh yahin bata dijiye."
                if hi
                else f"Perfect{name_part}! You're booked for {picked} ✅ We'll send a reminder the day before. "
                "Just reply here if you need to reschedule."
            )
            return ReplyDecision(
                action="send",
                body=_cap(body),
                cta="none",
                wait_seconds=None,
                rationale=f"customer picked a slot — confirmed the exact option from the trigger ({picked})",
                engagement_tag="slot_confirmed",
            )

        if _DECLINE_RE.search(message):
            if slots:
                options = " ya ".join(slots[:2]) if hi else " or ".join(slots[:2])
                body = (
                    f"Koi baat nahi{name_part}! {options} — inme se koi chalega? Ya apna time bata dijiye, hum adjust kar lenge."
                    if hi
                    else f"No problem{name_part}! Would {options} work instead? Or tell us a time and we'll fit you in."
                )
            else:
                body = (
                    f"Koi baat nahi{name_part}! Jo time aapko suit kare bata dijiye, hum slot arrange kar denge."
                    if hi
                    else f"No problem{name_part}! Tell us a time that suits you and we'll arrange the slot."
                )
            return ReplyDecision(
                action="send",
                body=_cap(body),
                cta="open_ended",
                wait_seconds=None,
                rationale="customer declined the offered slot — re-offering the real alternatives",
                engagement_tag="reschedule_offered",
            )

        if _PRICE_RE.search(message):
            offers = facts.active_offers if facts else []
            if offers:
                body = (
                    f"Hi{name_part}! Abhi '{offers[0]}' chal raha hai — wahi rate aapke liye apply hoga. Slot book kar doon?"
                    if hi
                    else f"Hi{name_part}! Our current offer is '{offers[0]}' — that's the rate for you. Shall I book your slot?"
                )
            else:
                clinic = (facts.merchant_name if facts else None) or ("hum" if hi else "we")
                body = (
                    f"Hi{name_part}! Pricing visit ke time confirm ho jayegi — {clinic} aapko exact estimate dega. Slot book kar doon?"
                    if hi
                    else f"Hi{name_part}! Pricing is confirmed at your visit — {clinic} will give you an exact estimate. Shall I book your slot?"
                )
            return ReplyDecision(
                action="send",
                body=_cap(body),
                cta="binary",
                wait_seconds=None,
                rationale="customer asked about price — quoted the merchant's live offer",
                engagement_tag="price_answered",
            )

        if _YES_RE.search(message):
            if len(slots) == 1:
                return self.decide(slots[0], language, facts)  # only one option — confirm it
            if len(slots) >= 2:
                body = (
                    f"Badhiya{name_part}! Kaunsa slot rakhein — {slots[0]} (1) ya {slots[1]} (2)? Reply 1 ya 2."
                    if hi
                    else f"Great{name_part}! Which slot should we lock — {slots[0]} (1) or {slots[1]} (2)? Reply 1 or 2."
                )
                return ReplyDecision(
                    action="send",
                    body=_cap(body),
                    cta="binary",
                    wait_seconds=None,
                    rationale="customer said yes without picking — asking to choose between the two real slots",
                    engagement_tag="slot_choice_asked",
                )

        body = (
            f"Hi{name_part}! Jo time aapko theek lage bata dijiye — hum slot book kar denge."
            if hi
            else f"Hi{name_part}! Tell us a time that works for you and we'll book the slot."
        )
        return ReplyDecision(
            action="send",
            body=_cap(body),
            cta="open_ended",
            wait_seconds=None,
            rationale="customer reply without a clear pick — asking for their preferred time",
            engagement_tag="time_asked",
        )

    @staticmethod
    def _pick_slot(message: str, slots: list[str]) -> str | None:
        """Match '1'/'2', a day name, or any distinctive part of a slot label."""
        if not slots:
            return None
        msg = message.lower()

        for slot in slots:
            if slot.lower() in msg:
                return slot

        # Day-name match before bare digits: "I'll come at 1pm on Thu" must
        # resolve by "thu", not by the incidental "1".
        for slot in slots:
            day = slot.split()[0].lower()[:3]
            if day in _DAY_TOKENS and re.search(rf"\b{day}", msg):
                return slot

        for idx, slot in enumerate(slots[:2], start=1):
            if re.search(rf"(?<!\d){idx}(?!\d)(?!\s*(am|pm))", msg):
                return slot
        return None
