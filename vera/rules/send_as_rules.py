"""
vera.rules.send_as_rules — "vera" vs "merchant_on_behalf".

challenge-brief.md §4.4 / §5: a customer-facing message (a
CustomerContext was supplied) is sent from the merchant's own WhatsApp
number, attributed "merchant_on_behalf"; everything else is Vera
speaking directly to the merchant.
"""

from __future__ import annotations

__all__ = ["resolve_send_as"]


def resolve_send_as(has_customer_context: bool) -> str:
    return "merchant_on_behalf" if has_customer_context else "vera"
