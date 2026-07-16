"""
vera.conversation.grounded_replies — trigger-grounded reply bodies.

Builds commit-confirmation and continue-conversation bodies from the
conversation's own trigger/category/merchant facts (via ReplyFacts),
replacing the canned generics in ReplyComposer whenever the facts are
available. Returns None when it can't ground a body — the caller falls
back to ReplyComposer's safe one-liners, so behaviour with missing
context is unchanged.

Every number, date, and quote comes from the pushed contexts; the only
"knowledge" here is which payload fields each trigger kind carries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vera.conversation.reply_facts import ReplyFacts

__all__ = ["commit_reply", "continue_reply"]

_MAX_BODY = 320


def _hi(language: str) -> bool:
    return language in ("hi", "hi-en")


def _cap(body: str) -> str:
    if len(body) <= _MAX_BODY:
        return body
    return body[: _MAX_BODY - 1].rstrip() + "…"


def _first_sentence(text: str | None) -> str:
    if not text:
        return ""
    return text.split(". ")[0].rstrip(".")


# ── Commit: merchant said yes — confirm the SPECIFIC deliverable ─────────────


def commit_reply(language: str, facts: ReplyFacts | None) -> str | None:
    if facts is None:
        return None
    kind = facts.trigger_kind
    hi = _hi(language)
    offers = facts.active_offers
    offer = offers[0] if offers else None

    if kind == "research_digest":
        item = facts.digest_item or {}
        source = item.get("source", "the journal")
        cohort = facts.high_risk_count
        cohort_part = (
            (f" — aapke {cohort} high-risk patients ke liye" if hi else f" — for your {cohort} high-risk patients")
            if cohort
            else ""
        )
        return _cap(
            f"Badhiya! {source} ka 2-min abstract + patient-ed WhatsApp draft bhej rahi hoon{cohort_part}. "
            "2 minute mein yahin milega. Google post bhi bana doon?"
            if hi
            else f"Great! Sending the 2-min abstract from {source} + a patient-ed WhatsApp draft{cohort_part}. "
            "It'll be here in 2 minutes. Want a Google post version too?"
        )

    if kind == "regulation_change":
        item = facts.digest_item or {}
        action = item.get("actionable") or "audit your setup and update your SOPs"
        deadline = facts.payload.get("deadline_iso", "")[:10]
        deadline_part = f" Deadline: {deadline}." if deadline else ""
        return _cap(
            f"Badhiya — audit checklist bhej rahi hoon: {action}.{deadline_part} 2 minute mein yahin milega."
            if hi
            else f"Great — sending the audit checklist: {action}.{deadline_part} It'll be here in 2 minutes."
        )

    if kind in ("perf_dip", "perf_spike"):
        if offer:
            return _cap(
                f"Done — '{offer}' pe GBP post + WhatsApp push draft kar rahi hoon. 2 minute mein review ke liye yahin bhejti hoon."
                if hi
                else f"Done — drafting a GBP post + WhatsApp push around '{offer}'. I'll send it here for review in 2 minutes."
            )
        return _cap(
            "Done — pehle ek service+price offer set karte hain, phir GBP post + push. Draft 2 minute mein yahin milega."
            if hi
            else "Done — first we set up a service+price offer, then the GBP post + push. Draft here in 2 minutes."
        )

    if kind == "festival_upcoming":
        festival = facts.payload.get("festival", "festival")
        hook = f" '{offer}' ke saath" if (offer and hi) else (f" around '{offer}'" if offer else "")
        return _cap(
            f"Badhiya — {festival} campaign post + WhatsApp draft bana rahi hoon{hook}. 2 minute mein yahin bhejti hoon."
            if hi
            else f"Great — drafting the {festival} campaign post + WhatsApp{hook}. I'll send it here in 2 minutes."
        )

    if kind == "review_theme_emerged":
        theme = str(facts.payload.get("theme", "")).replace("_", " ")
        return _cap(
            f"Done — '{theme}' ke liye review-response template + ops fix checklist bana rahi hoon. 2 minute mein yahin milega."
            if hi
            else f"Done — building the review-response template + ops fix checklist for '{theme}'. Here in 2 minutes."
        )

    if kind == "renewal_due":
        return _cap(
            "Badhiya — renewal shuru kar rahi hoon, 2 minute ka kaam hai. Confirm hote hi yahin bata dungi."
            if hi
            else "Great — starting the renewal now, it's a 2-minute job. I'll confirm right here once it's done."
        )

    if kind == "competitor_opened":
        hook = f"'{offer}'" if offer else ("aapke best offer" if hi else "your best offer")
        return _cap(
            f"Badhiya — {hook} ke saath defensive campaign draft kar rahi hoon: GBP post + WhatsApp. 2 minute mein yahin milega."
            if hi
            else f"Great — drafting the defensive campaign around {hook}: GBP post + WhatsApp. Here in 2 minutes."
        )

    return None


# ── Continue: neutral/technical follow-up — answer with the real facts ───────


def continue_reply(language: str, facts: ReplyFacts | None) -> str | None:
    if facts is None:
        return None
    kind = facts.trigger_kind
    hi = _hi(language)

    if kind in ("regulation_change", "research_digest"):
        item = facts.digest_item or {}
        summary = item.get("summary")
        if summary:
            detail = _cap_text(summary, 200)
            ask = (
                "Aapke setup ke hisaab se exact steps chahiye toh batayiye — checklist ready hai."
                if hi
                else "Tell me your current setup and I'll match the exact steps — the checklist is ready."
            ) if kind == "regulation_change" else (
                "Aapke flagged patients ke liye recall-interval note draft kar doon? Reply YES."
                if hi
                else "Want me to draft the recall-interval note for your flagged patients? Reply YES."
            )
            return _cap(f"{detail} {ask}")

    if kind == "perf_dip":
        payload = facts.payload
        metric = payload.get("metric", "calls")
        delta = payload.get("delta_pct")
        baseline = payload.get("vs_baseline")
        if delta is not None:
            drop = abs(int(round(float(delta) * 100)))
            base_part = f" (baseline ~{baseline}/week)" if baseline is not None else ""
            offers = facts.active_offers
            fix = (
                f"'{offers[0]}' ko GBP post + WhatsApp push se aage rakhna sabse tez fix hai."
                if offers and hi
                else f"Pushing '{offers[0]}' via a GBP post + WhatsApp is the fastest fix."
                if offers
                else (
                    "Ek service+price offer set karna sabse tez fix hai."
                    if hi
                    else "Setting up a service+price offer is the fastest fix."
                )
            )
            ask = "Shuru karoon? Reply YES." if hi else "Shall I start? Reply YES."
            head = (
                f"Data yeh hai: {metric} {drop}% neeche{base_part}."
                if hi
                else f"Here's the data: {metric} down {drop}%{base_part}."
            )
            return _cap(f"{head} {fix} {ask}")

    if kind == "festival_upcoming":
        festival = facts.payload.get("festival")
        date = str(facts.payload.get("date", ""))[:10]
        if festival:
            offers = facts.active_offers
            hook = f" '{offers[0]}' hook rahega." if (offers and hi) else (f" '{offers[0]}' will be the hook." if offers else "")
            return _cap(
                f"{festival} {date} ko hai.{hook} Campaign post + WhatsApp draft ready kar sakti hoon — karoon? Reply YES."
                if hi
                else f"{festival} is on {date}.{hook} I can have the campaign post + WhatsApp drafted — shall I? Reply YES."
            )

    if kind == "review_theme_emerged":
        theme = str(facts.payload.get("theme", "")).replace("_", " ")
        count = facts.payload.get("occurrences_30d")
        quote = str(facts.payload.get("common_quote", ""))
        if theme and count is not None:
            quote_part = f' ("{quote[:60]}")' if quote else ""
            return _cap(
                f"Context: {count} reviews mein '{theme}' aaya hai{quote_part}. Response template mere paas ready hai — bhejoon? Reply YES."
                if hi
                else f"Context: '{theme}' shows up in {count} reviews{quote_part}. I have the response template ready — send it over? Reply YES."
            )

    return None


def _cap_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(". ", 1)[0]
    return cut if cut.endswith(".") else cut + "."
