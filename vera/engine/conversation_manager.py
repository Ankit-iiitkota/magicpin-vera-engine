"""
vera.engine.conversation_manager — ConversationManager.

The async orchestrator behind POST /v1/reply: loads (or lazily opens)
the ConversationState, looks up the merchant's language from whatever
MerchantContext was already pushed via POST /v1/context, asks
ConversationStateMachine what to do, persists the updated turn history,
and returns the decision for the endpoint to serialise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    ) -> None:
        self._conversation_store = conversation_store
        self._context_repository = context_repository
        self._state_machine = state_machine or ConversationStateMachine()

    async def handle_reply(
        self,
        conversation_id: str,
        merchant_id: str | None,
        customer_id: str | None,
        message: str,
        turn_number: int,
    ) -> ReplyDecision:
        state = await self._conversation_store.get(conversation_id)
        if state is None:
            state = await self._open_conversation(conversation_id, merchant_id, customer_id)

        language = await self._resolve_language(state)
        decision = self._state_machine.decide(state, message, turn_number, language)

        self._record_turns(state, message, decision, turn_number)
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

    async def _resolve_language(self, state: ConversationState) -> str:
        record = await self._context_repository.get_context("merchant", state.merchant_id)
        if record is None:
            return _DEFAULT_LANGUAGE
        languages = tuple(record.payload.get("identity", {}).get("languages", ()))
        return pick_language(languages, None)

    @staticmethod
    def _record_turns(
        state: ConversationState, message: str, decision: ReplyDecision, turn_number: int
    ) -> None:
        now = utcnow_iso()
        state.turns.append({"from": "merchant", "body": message, "ts": now, "engagement": None})
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
