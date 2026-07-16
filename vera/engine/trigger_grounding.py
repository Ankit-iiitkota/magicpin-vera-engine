"""
vera.engine.trigger_grounding — per-trigger-kind grounded composition.

The generic pipeline (signals -> goals -> candidates -> templates) infers
WHAT to say from merchant state alone; the trigger's own kind/payload
never reaches goal inference. That's fine for merchant-state nudges, but
for triggers whose whole point IS their payload (a DCI regulation with a
deadline, a review theme with a quote, Diwali on a date, a 50% call dip),
it produced messages that never mentioned the trigger — and two triggers
for the same merchant could render byte-identical bodies, so the second
one was swallowed by the anti-repetition guard.

`ground(category, merchant, trigger, customer)` builds the body directly
from the trigger payload plus the matching category/merchant/customer
facts for the kinds it knows, and returns None for every other kind so
the generic pipeline still handles them. Every number, date, name, and
quote in these bodies comes from the provided contexts — nothing is
invented (challenge-brief.md §5 rule 8).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.contexts.composed_message import ComposedMessage
from vera.rules.language_rules import pick_language

if TYPE_CHECKING:
    from vera.contexts.category import CategoryContext, DigestItem
    from vera.contexts.customer import CustomerContext
    from vera.contexts.merchant import MerchantContext
    from vera.contexts.trigger import TriggerContext

__all__ = ["ground"]

_MAX_BODY = 320


# ── Shared fact helpers ──────────────────────────────────────────────────────


def _language(merchant: MerchantContext, customer: CustomerContext | None) -> str:
    pref = customer.identity.language_pref if customer is not None else None
    return pick_language(tuple(merchant.identity.languages), pref)


def _is_hindi_mix(language: str) -> bool:
    return language in ("hi", "hi-en")


def _salutation(merchant: MerchantContext) -> str:
    first = merchant.identity.owner_first_name
    if not first:
        return merchant.identity.name
    if merchant.category_slug == "dentists":
        return f"Dr. {first}"
    return first


def _active_offer_titles(merchant: MerchantContext) -> list[str]:
    return [o.title for o in merchant.offers if o.status == "active"]


def _digest_item(category: CategoryContext, trigger: TriggerContext, kind: str) -> DigestItem | None:
    """The digest item the trigger points at, else the first item of the wanted kind."""
    wanted_id = trigger.payload.get("top_item_id")
    if wanted_id:
        for item in category.digest:
            if item.id == wanted_id:
                return item
    for item in category.digest:
        if item.kind == kind:
            return item
    return category.digest[0] if category.digest else None


def _first_sentence(text: str | None) -> str:
    if not text:
        return ""
    return text.split(". ")[0].rstrip(".")


def _short_date(iso: str | None) -> str:
    """'2026-12-15' -> '15 Dec 2026' (grounded readability, no tz math)."""
    if not iso or len(iso) < 10:
        return iso or ""
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        y, m, d = iso[:10].split("-")
        return f"{int(d)} {months[int(m) - 1]} {y}"
    except (ValueError, IndexError):
        return iso[:10]


def _fit(opening: str, middles: list[str], ask: str) -> str:
    """opening + droppable middle sentences + ask, <= 320 chars, ask always last.

    Middle parts are dropped (last first) before anything else is cut, so the
    call-to-action never gets buried or truncated (challenge-brief.md §11).
    """
    middles = [m for m in middles if m]
    while True:
        body = " ".join(p for p in [opening, *middles, ask] if p).strip()
        if len(body) <= _MAX_BODY or not middles:
            break
        middles.pop()
    if len(body) > _MAX_BODY:
        keep = _MAX_BODY - len(ask) - 2
        body = opening[:keep].rstrip() + "… " + ask
    return body


def _message(
    trigger: TriggerContext,
    body: str,
    cta: str,
    rationale: str,
    *,
    send_as: str | None = None,
) -> ComposedMessage:
    return ComposedMessage(
        body=body,
        cta=cta,
        send_as=send_as or ("merchant_on_behalf" if trigger.scope == "customer" else "vera"),
        suppression_key=trigger.suppression_key,
        rationale=rationale,
    )


# ── Per-kind builders ────────────────────────────────────────────────────────


def _research_digest(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    item = _digest_item(category, trigger, "research")
    if item is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    n_part = f" (n={item.trial_n:,})" if item.trial_n else ""
    finding = _first_sentence(item.summary) or item.title

    cohort = ""
    agg = merchant.customer_aggregate
    if agg and agg.high_risk_adult_count and item.patient_segment == "high_risk_adults":
        cohort = (
            f"Aapke {agg.high_risk_adult_count} patients high-risk flagged hain — directly relevant."
            if hi
            else f"Directly relevant to the {agg.high_risk_adult_count} patients you have flagged high-risk."
        )

    ask = (
        "2-min abstract + patient-ed WhatsApp draft kar doon? Reply YES."
        if hi
        else "Want the 2-min abstract + a patient-ed WhatsApp draft? Reply YES."
    )
    body = _fit(f"{sal}, {item.source}{n_part}: {finding}.", [cohort], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"research_digest: cited {item.source} finding verbatim, tied to merchant's "
        "high-risk cohort; levers: specificity + reciprocity (drafted deliverable).",
    )


def _regulation_change(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    item = _digest_item(category, trigger, "compliance")
    if item is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    deadline = _short_date(trigger.payload.get("deadline_iso")) or _short_date(trigger.expires_at)
    rule = _first_sentence(item.summary) or item.title

    deadline_part = ""
    if deadline:
        deadline_part = (
            f"Deadline {deadline} — non-compliance inspection risk hai."
            if hi
            else f"Deadline is {deadline} — non-compliance is an inspection risk."
        )
    action = item.actionable or ""
    ask = (
        "Audit checklist bhej doon? Reply YES."
        if hi
        else "Want the audit checklist? Reply YES."
    )
    body = _fit(
        f"{sal}, {item.source}: {rule}.",
        [deadline_part, f"({action})" if action else ""],
        ask,
    )
    return _message(
        trigger,
        body,
        "binary",
        f"regulation_change: named the regulator via {item.source}, exact rule change and "
        "deadline from the digest/payload; framed as compliance risk, not promo.",
    )


def _recall_due(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    if customer is None:
        return None  # merchant-facing recall asks stay with the generic pipeline
    hi = _is_hindi_mix(_language(merchant, customer))
    cust_name = customer.identity.name.split()[0]
    clinic = merchant.identity.name
    service = str(trigger.payload.get("service_due", "")).replace("_", " ").strip()

    slots = trigger.payload.get("available_slots") or []
    labels = [s.get("label", "") for s in slots[:2] if isinstance(s, dict) and s.get("label")]
    if labels and len(labels) >= 2:
        slot_part = (
            f"2 slots ready hain: {labels[0]} ya {labels[1]}. Reply 1 ya 2 to confirm."
            if hi
            else f"2 slots are open: {labels[0]} or {labels[1]}. Reply 1 or 2 to confirm."
        )
        cta = "binary"
    elif labels:
        slot_part = (
            f"Slot available: {labels[0]}. Reply YES to confirm."
            if hi
            else f"Slot available: {labels[0]}. Reply YES to confirm."
        )
        cta = "binary"
    else:
        slot_part = (
            "Kaunsa time suit karega? Bata dijiye, book kar denge."
            if hi
            else "What time works for you? Tell us and we'll book it."
        )
        cta = "open_ended"

    offer_part = ""
    offers = _active_offer_titles(merchant)
    service_word = service.split()[-1] if service else ""
    matching = [t for t in offers if service_word and service_word.lower() in t.lower()]
    if matching:
        offer_part = f"({matching[0]})"

    due = service or ("follow-up" if not hi else "follow-up")
    opening = (
        f"Hi {cust_name}, {clinic} se — aapka {due} due hai."
        if hi
        else f"Hi {cust_name}, this is {clinic} — your {due} is due."
    )
    body = _fit(opening, [offer_part], slot_part)
    return _message(
        trigger,
        body,
        cta,
        f"recall_due: customer-facing recall for {cust_name} naming the due service, real "
        "slot options from the trigger payload, and the merchant's live offer price.",
        send_as="merchant_on_behalf",
    )


def _perf_dip(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    metric = str(trigger.payload.get("metric", "calls"))
    delta_pct = trigger.payload.get("delta_pct")
    if delta_pct is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    drop = abs(int(round(float(delta_pct) * 100)))
    window = str(trigger.payload.get("window", "7d")).replace("d", " din" if hi else " days")
    baseline = trigger.payload.get("vs_baseline")
    baseline_part = ""
    if baseline is not None:
        baseline_part = (
            f"(baseline ~{baseline}/hafta)" if hi else f"(baseline ~{baseline}/week)"
        )

    peer_part = ""
    peer_calls = category.peer_stats.avg_calls_30d if category.peer_stats else None
    if metric == "calls" and peer_calls:
        peer_part = (
            f"Peer average {int(peer_calls)} calls/30d hai — gap recover ho sakta hai."
            if hi
            else f"Peers average {int(peer_calls)} calls/30d — this gap is recoverable."
        )

    offers = _active_offer_titles(merchant)
    if offers:
        fix = (
            f"Aapka '{offers[0]}' offer live hai — usko GBP post + WhatsApp push se aage rakhein."
            if hi
            else f"Your live '{offers[0]}' offer is the hook — I can push it via a GBP post + WhatsApp."
        )
    else:
        catalog = category.offer_catalog[0].title if category.offer_catalog else None
        fix = (
            (
                f"Koi active offer nahi hai — '{catalog}' jaisa service+price offer sabse tez fix hai."
                if catalog
                else "Koi active offer nahi hai — ek service+price offer sabse tez fix hai."
            )
            if hi
            else (
                f"You have no active offer — a service+price offer like '{catalog}' is the fastest fix."
                if catalog
                else "You have no active offer — a service+price offer is the fastest fix."
            )
        )
    ask = "Main setup kar doon? Reply YES." if hi else "Shall I set it up? Reply YES."
    opening = (
        f"{sal}, {metric} pichhle {window} mein {drop}% neeche {baseline_part}".strip() + "."
        if hi
        else f"{sal}, your {metric} dropped {drop}% over the last {window} {baseline_part}".strip() + "."
    )
    body = _fit(opening, [peer_part, fix], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"perf_dip: exact metric ({metric} -{drop}%) and baseline from the trigger payload, "
        "peer benchmark from category stats, one concrete fix using their real offer.",
    )


def _perf_spike(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    metric = str(trigger.payload.get("metric", "views"))
    delta_pct = trigger.payload.get("delta_pct")
    if delta_pct is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    rise = abs(int(round(float(delta_pct) * 100)))
    driver = str(trigger.payload.get("likely_driver", "")).replace("_", " ")
    driver_part = (f"— lagta hai {driver} ne kaam kiya" if hi else f"— looks like {driver} worked") if driver else ""
    opening = (
        f"{sal}, {metric} is hafte {rise}% upar {driver_part}".strip() + "."
        if hi
        else f"{sal}, your {metric} are up {rise}% this week {driver_part}".strip() + "."
    )
    ask = (
        "Isko repeat karne ke liye ek aur GBP post draft kar doon? Reply YES."
        if hi
        else "Want me to draft one more GBP post to repeat this? Reply YES."
    )
    body = _fit(opening, [], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"perf_spike: celebrated the exact {metric} +{rise}% from the payload and offered a "
        "concrete replication step.",
    )


def _festival_upcoming(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    festival = trigger.payload.get("festival")
    if not festival:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    date = _short_date(trigger.payload.get("date"))
    days_until = trigger.payload.get("days_until")
    when = f"{date}" if date else (f"{days_until} din mein" if hi else f"in {days_until} days")

    offers = _active_offer_titles(merchant)
    if offers:
        hook = (
            f"Aapke live offers ('{offers[0]}'{' + ' + repr(offers[1]) if len(offers) > 1 else ''}) iske hook ban sakte hain."
            if hi
            else f"Your live offer{'s' if len(offers) > 1 else ''} ('{offers[0]}'{' + ' + repr(offers[1]) if len(offers) > 1 else ''}) can carry it."
        )
    else:
        catalog = category.offer_catalog[0].title if category.offer_catalog else None
        hook = (
            (f"'{catalog}' jaisa offer iska hook ban sakta hai." if catalog else "Ek service+price offer iska hook banega.")
            if hi
            else (f"An offer like '{catalog}' can carry it." if catalog else "A service+price offer can carry it.")
        )
    ask = (
        f"{festival} campaign post + WhatsApp abhi se draft kar doon? Reply YES."
        if hi
        else f"Shall I draft the {festival} campaign post + WhatsApp now? Reply YES."
    )
    opening = (
        f"{sal}, {festival} {when} ko hai — bookings ka sabse bada window."
        if hi
        else f"{sal}, {festival} lands {when} — the biggest booking window of the year."
    )
    body = _fit(opening, [hook], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"festival_upcoming: named {festival} and its date from the payload, tied it to the "
        "merchant's real live offers; levers: urgency + effort externalization.",
    )


def _review_theme(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    theme = str(trigger.payload.get("theme", "")).replace("_", " ").strip()
    count = trigger.payload.get("occurrences_30d")
    if not theme or count is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    quote = str(trigger.payload.get("common_quote", "")).strip()
    trend = str(trigger.payload.get("trend", "")).strip()
    quote_part = f'("{quote[:60]}")' if quote else ""
    trend_part = (
        ("— aur trend rising hai" if hi else "— and the trend is rising") if trend == "rising" else ""
    )
    opening = (
        f"{sal}, pichhle 30 din mein {count} reviews '{theme}' mention kar rahe hain {quote_part} {trend_part}".strip()
        + "."
        if hi
        else f"{sal}, {count} reviews in the last 30 days mention '{theme}' {quote_part} {trend_part}".strip() + "."
    )
    ask = (
        "Main review-response template + ops fix checklist dono draft kar doon? Reply YES."
        if hi
        else "Want me to draft a review-response template + an ops fix checklist? Reply YES."
    )
    body = _fit(opening, [], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"review_theme_emerged: exact theme '{theme}', {count} occurrences and the customers' "
        "own quote from the payload; offered a drafted deliverable.",
    )


def _renewal_due(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    days = trigger.payload.get("days_remaining", merchant.subscription.days_remaining)
    if days is None:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    plan = trigger.payload.get("plan") or merchant.subscription.plan or "plan"
    perf = merchant.performance
    lead_part = ""
    if perf.calls or perf.leads:
        leads = perf.leads or perf.calls
        lead_part = (
            f"Pichhle 30 din mein {leads} leads isi listing se aaye hain."
            if hi
            else f"Your listing brought {leads} leads in the last 30 days."
        )
    opening = (
        f"{sal}, aapka {plan} plan {days} din mein expire ho raha hai."
        if hi
        else f"{sal}, your {plan} plan expires in {days} days."
    )
    ask = (
        "Renewal 2 minute ka hai — abhi kar doon? Reply YES."
        if hi
        else "Renewal takes 2 minutes — shall I start it now? Reply YES."
    )
    body = _fit(opening, [lead_part], ask)
    return _message(
        trigger,
        body,
        "binary",
        f"renewal_due: exact days_remaining ({days}) and plan from context; framed as "
        "protecting the lead flow their own numbers show.",
    )


def _competitor_opened(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None,
) -> ComposedMessage | None:
    comp = trigger.payload.get("competitor_name")
    dist = trigger.payload.get("distance_km")
    if not comp:
        return None
    sal = _salutation(merchant)
    hi = _is_hindi_mix(_language(merchant, customer))
    their_offer = trigger.payload.get("their_offer")
    dist_part = f" {dist}km" if dist is not None else ""
    offer_part = f" '{their_offer}' ke saath" if (their_offer and hi) else (f" with '{their_offer}'" if their_offer else "")
    offers = _active_offer_titles(merchant)
    defense = (
        (f"Aapka '{offers[0]}' pehle se strong hai — usse aage rakhna hai." if offers else "Ek fresh offer + updated photos aapko aage rakhenge.")
        if hi
        else (f"Your '{offers[0]}' already holds up — we just need it in front." if offers else "A fresh offer + updated photos will keep you ahead.")
    )
    ask = "Defensive campaign draft kar doon? Reply YES." if hi else "Shall I draft a defensive campaign? Reply YES."
    opening = (
        f"{sal}, {comp}{dist_part} door khula hai{offer_part}."
        if hi
        else f"{sal}, {comp} just opened{dist_part} away{offer_part}."
    )
    body = _fit(opening, [defense], ask)
    return _message(
        trigger,
        body,
        "binary",
        "competitor_opened: named the competitor, distance and their offer from the payload; "
        "defensive frame anchored on the merchant's real offer.",
    )


_BUILDERS = {
    "research_digest": _research_digest,
    "regulation_change": _regulation_change,
    "recall_due": _recall_due,
    "perf_dip": _perf_dip,
    "perf_spike": _perf_spike,
    "festival_upcoming": _festival_upcoming,
    "review_theme_emerged": _review_theme,
    "renewal_due": _renewal_due,
    "competitor_opened": _competitor_opened,
}


def ground(
    category: CategoryContext,
    merchant: MerchantContext,
    trigger: TriggerContext,
    customer: CustomerContext | None = None,
) -> ComposedMessage | None:
    """Compose a trigger-payload-grounded message, or None if this kind isn't grounded."""
    builder = _BUILDERS.get(trigger.kind)
    if builder is None:
        return None
    return builder(category, merchant, trigger, customer)
