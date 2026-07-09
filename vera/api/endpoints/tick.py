"""
vera.api.endpoints.tick — POST /v1/tick.

challenge-testing-brief.md §2.2. For each trigger_id the judge says is
currently active, resolves the full (category, merchant, trigger,
customer?) input from whatever's already been pushed via POST
/v1/context, checks suppression, calls compose(), checks
anti-repetition, and — if everything clears — opens the conversation
and returns it as an ActionItem.

No business logic lives here beyond that orchestration: compose() owns
the actual composition pipeline (Phase 3-8); this endpoint's job is
purely "resolve inputs, gate on suppression/anti-repetition, persist
conversation state, shape the response."
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from vera.api.deps import get_context_repository, get_store
from vera.api.models.tick import ActionItem, TickRequest, TickResponse
from vera.contexts.category import CategoryContext
from vera.contexts.customer import CustomerContext
from vera.contexts.merchant import MerchantContext
from vera.contexts.trigger import TriggerContext
from vera.engine.anti_repetition import AntiRepetitionGuard
from vera.engine.composer import compose
from vera.engine.suppression import SuppressionGuard
from vera.store.base_store import BaseContextStore
from vera.store.context_repository import ContextRepository
from vera.store.conversation_store import ConversationStore

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["tick"])

_MAX_ACTIONS_PER_TICK = 20


@router.post("/v1/tick", response_model=TickResponse)
async def tick(
    body: TickRequest,
    repo: ContextRepository = Depends(get_context_repository),
    store: BaseContextStore = Depends(get_store),
) -> TickResponse:
    suppression_guard = SuppressionGuard(store)
    anti_repetition_guard = AntiRepetitionGuard(store)
    conversation_store = ConversationStore(store)

    actions: list[ActionItem] = []
    for trigger_id in body.available_triggers:
        if len(actions) >= _MAX_ACTIONS_PER_TICK:
            break

        action = await _try_build_action(
            trigger_id, repo, suppression_guard, anti_repetition_guard, conversation_store
        )
        if action is not None:
            actions.append(action)

    return TickResponse(actions=actions)


async def _try_build_action(
    trigger_id: str,
    repo: ContextRepository,
    suppression_guard: SuppressionGuard,
    anti_repetition_guard: AntiRepetitionGuard,
    conversation_store: ConversationStore,
) -> ActionItem | None:
    resolved = await _resolve_inputs(trigger_id, repo)
    if resolved is None:
        return None
    category, merchant, trigger, customer = resolved

    if await suppression_guard.is_suppressed(trigger.suppression_key):
        logger.info("tick_skipped_suppressed", trigger_id=trigger_id)
        return None

    try:
        composed = compose(category, merchant, trigger, customer)
    except (
        Exception
    ) as exc:  # compose() is deterministic; a failure here is a real bug, not user error
        logger.warning("tick_compose_failed", trigger_id=trigger_id, error=str(exc))
        return None

    conversation_id = f"conv_{merchant.merchant_id}_{trigger.id}"
    if await anti_repetition_guard.is_repeat(conversation_id, composed.body):
        logger.info(
            "tick_skipped_repeat_body", trigger_id=trigger_id, conversation_id=conversation_id
        )
        return None

    await conversation_store.open_conversation(
        conversation_id=conversation_id,
        merchant_id=merchant.merchant_id,
        trigger_id=trigger.id,
        scope=trigger.scope,
        customer_id=customer.customer_id if customer else None,
        suppression_key=composed.suppression_key,
    )
    await suppression_guard.mark_sent(composed.suppression_key)
    await anti_repetition_guard.mark_sent(conversation_id, composed.body)

    return ActionItem(
        conversation_id=conversation_id,
        merchant_id=merchant.merchant_id,
        customer_id=customer.customer_id if customer else None,
        send_as=composed.send_as,
        trigger_id=trigger.id,
        template_name=f"vera_{trigger.kind}_v1",
        template_params=[merchant.identity.name, category.slug],
        body=composed.body,
        cta=composed.cta,
        suppression_key=composed.suppression_key,
        rationale=composed.rationale,
    )


async def _resolve_inputs(
    trigger_id: str, repo: ContextRepository
) -> tuple[CategoryContext, MerchantContext, TriggerContext, CustomerContext | None] | None:
    trigger_record = await repo.get_context("trigger", trigger_id)
    if trigger_record is None:
        return None
    trigger = TriggerContext.model_validate(trigger_record.payload)

    if not trigger.merchant_id:
        return None
    merchant_record = await repo.get_context("merchant", trigger.merchant_id)
    if merchant_record is None:
        return None
    merchant = MerchantContext.model_validate(merchant_record.payload)

    category_record = await repo.get_context("category", merchant.category_slug)
    if category_record is None:
        return None
    category = CategoryContext.model_validate(category_record.payload)

    customer: CustomerContext | None = None
    if trigger.scope == "customer" and trigger.customer_id:
        customer_record = await repo.get_context("customer", trigger.customer_id)
        if customer_record is not None:
            customer = CustomerContext.model_validate(customer_record.payload)

    return category, merchant, trigger, customer
