"""
vera.store.conversation_store — Conversation state wrapper.

Provides typed helpers on top of BaseContextStore for managing
multi-turn conversation state, separate from the four context objects.

Conversation data is stored under the 'conversation' scope:
    key: ctx:conversation:{conversation_id}

This module is a thin wrapper — the underlying store handles TTL and
serialisation. Conversation logic (state machine, intent) lives in
vera.conversation.* and is implemented in Phase 5.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from vera.store.base_store import BaseContextStore


@dataclass
class ConversationState:
    """
    Persisted state for a single conversation (merchant ↔ Vera).

    Populated incrementally as turns are processed.
    Stored as a plain JSON-serialisable dict.
    """

    conversation_id: str
    merchant_id: str
    trigger_id: str
    scope: str  # "merchant" | "customer"
    customer_id: str | None = None

    # Turn tracking
    turn_number: int = 0
    turns: list[dict[str, Any]] = field(default_factory=list)

    # State machine (Phase 5)
    state: str = "open"  # open | waiting | ended
    last_merchant_message_at: str | None = None  # ISO-8601
    wait_until: str | None = None  # ISO-8601

    # Suppression
    suppression_key: str | None = None
    ended: bool = False

    # Audit
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ConversationStore:
    """
    Typed wrapper around BaseContextStore for conversation state.

    All conversations are stored under scope='conversation'.
    TTL: 48 h (172_800 s) — defined in BaseContextStore.SCOPE_TTL.
    """

    SCOPE = "conversation"

    def __init__(self, store: BaseContextStore) -> None:
        self._store = store

    async def get(self, conversation_id: str) -> ConversationState | None:
        """Return the current ConversationState, or None if not found."""
        envelope = await self._store.get(self.SCOPE, conversation_id)
        if envelope is None:
            return None
        return ConversationState.from_dict(envelope["payload"])

    async def save(self, state: ConversationState) -> None:
        """Persist (upsert) a ConversationState."""
        state.updated_at = datetime.now(timezone.utc).isoformat()
        await self._store.set(
            scope=self.SCOPE,
            context_id=state.conversation_id,
            version=state.turn_number,
            payload=state.to_dict(),
        )

    async def open_conversation(
        self,
        conversation_id: str,
        merchant_id: str,
        trigger_id: str,
        scope: str,
        customer_id: str | None = None,
        suppression_key: str | None = None,
    ) -> ConversationState:
        """
        Create a new conversation record.

        If a conversation with the same ID already exists, it is returned
        unchanged (idempotent open).
        """
        existing = await self.get(conversation_id)
        if existing is not None:
            return existing

        state = ConversationState(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            trigger_id=trigger_id,
            scope=scope,
            customer_id=customer_id,
            suppression_key=suppression_key,
        )
        await self.save(state)
        return state

    async def end_conversation(self, conversation_id: str) -> None:
        """Mark a conversation as ended."""
        state = await self.get(conversation_id)
        if state is None:
            return
        state.ended = True
        state.state = "ended"
        await self.save(state)
