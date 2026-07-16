"""
vera.engine.conversation_manager — ConversationManager.

The async orchestrator behind POST /v1/reply: loads (or lazily opens)
the ConversationState, re-loads the same four context layers the
opening message was composed from (as ReplyFacts, for grounded reply
bodies), routes by who is actually talking — the merchant owner goes
through ConversationStateMachine, the merchant's customer through
CustomerReplyHandler — persists the updated turn history, and returns
the decision for the endpoint to serialise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vera.conversation.customer_reply import CustomerReplyHandler
from vera.conversation.reply_facts import ReplyFacts
from vera.conversation.state_machine import ConversationStateMachine
from vera.rules.language_rules import pick_language
from vera.utils.time_utils import utcnow_iso

if TYPE_CHECKING:
    from vera.conversation.state_machine import ReplyDecision
    from vera.store.context_repository import ContextRepository
    from vera.store.conversation_store import ConversationState, ConversationStore

__all__ = ["ConversationManager"]

_DEFAULT_LANGUAGE = "en"


class ConversationManager:
    def __init__(
        self,
        conversation_store: ConversationStore,
        context_repository: ContextRepository,
        state_machine: ConversationStateMachine | None = None,
        customer_handler: CustomerReplyHandler | None = None,
    ) -> None:
        self._conversation_store = conversation_store
        self._context_repository = context_repository
        self._state_machine = state_machine or ConversationStateMachine()
        self._customer_handler = customer_handler or CustomerReplyHandler()

    async def handle_reply(
        self,
        conversation_id: str,
        merchant_id: str | None,
        customer_id: str | None,
        message: str,
        turn_number: int,
        from_role: str = "merchant",
    ) -> ReplyDecision:
        state = await self._conversation_store.get(conversation_id)
        if state is None:
            state = await self._open_conversation(conversation_id, merchant_id, customer_id)

        facts = await self._load_facts(state, customer_id)
        language = self._resolve_language(facts)

        if from_role == "customer":
            # The merchant's own customer answering a merchant_on_behalf
            # send — never route through the merchant state machine (a slot
            # pick is not a merchant "commit").
            customer_language = pick_language((), facts.customer_language_pref) if (
                facts.customer_language_pref
            ) else language
            decision = self._customer_handler.decide(message, customer_language, facts)
        else:
            decision = self._state_machine.decide(state, message, turn_number, language, facts)

        self._record_turns(state, message, decision, turn_number, from_role)
        await self._conversation_store.save(state)

        return decision

    async def _open_conversation(
        self, conversation_id: str, merchant_id: str | None, customer_id: str | None
    ) -> ConversationState:
        # Defensive path — normally /v1/tick already opened this conversation
        # via ConversationStore.open_conversation when it generated the
        # action. If a /v1/reply somehow arrives first, start a bare record
        # rather than failing the turn.
        return await self._conversation_store.open_conversation(
            conversation_id=conversation_id,
            merchant_id=merchant_id or "unknown",
            trigger_id="unknown",
            scope="customer" if customer_id else "merchant",
            customer_id=customer_id,
        )

    async def _load_facts(self, state: ConversationState, customer_id: str | None) -> ReplyFacts:
        """Re-load the four context layers this conversation was opened from."""
        merchant = await self._get_payload("merchant", state.merchant_id)
        category = None
        if merchant:
            category = await self._get_payload("category", merchant.get("category_slug"))
        trigger = await self._get_payload("trigger", state.trigger_id)
        customer = await self._get_payload("customer", customer_id or state.customer_id)
        return ReplyFacts(
            merchant=merchant, category=category, trigger=trigger, customer=customer
        )

    async def _get_payload(self, scope: str, context_id: str | None) -> dict | None:
        if not context_id or context_id == "unknown":
            return None
        record = await self._context_repository.get_context(scope, context_id)
        return record.payload if record is not None else None

    @staticmethod
    def _resolve_language(facts: ReplyFacts) -> str:
        if facts.merchant is None:
            return _DEFAULT_LANGUAGE
        languages = tuple(facts.merchant.get("identity", {}).get("languages", ()))
        return pick_language(languages, None)

    @staticmethod
    def _record_turns(
        state: ConversationState,
        message: str,
        decision: ReplyDecision,
        turn_number: int,
        from_role: str,
    ) -> None:
        now = utcnow_iso()
        state.turns.append({"from": from_role, "body": message, "ts": now, "engagement": None})
        if decision.body is not None:
            state.turns.append(
                {
                    "from": "vera",
                    "body": decision.body,
                    "ts": now,
                    "engagement": decision.engagement_tag,
                }
            )

        state.turn_number = turn_number
        state.last_merchant_message_at = now

        if decision.action == "end":
            state.ended = True
            state.state = "ended"
        elif decision.action == "wait":
            state.state = "waiting"
        else:
            state.state = "open"
