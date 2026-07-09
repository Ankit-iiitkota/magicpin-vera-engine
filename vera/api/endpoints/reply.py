"""
vera.api.endpoints.reply — POST /v1/reply.

challenge-testing-brief.md §2.3. Delegates entirely to
ConversationManager (Phase 8's conversation engine) for the actual
decision; this endpoint's job is just DI wiring and shaping whichever
of the three response variants (send/wait/end) the decision maps to.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from vera.api.deps import get_context_repository, get_store
from vera.api.models.reply import (
    ReplyEndResponse,
    ReplyRequest,
    ReplySendResponse,
    ReplyWaitResponse,
)
from vera.engine.conversation_manager import ConversationManager
from vera.store.base_store import BaseContextStore
from vera.store.context_repository import ContextRepository
from vera.store.conversation_store import ConversationStore

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["reply"])


@router.post("/v1/reply")
async def reply(
    body: ReplyRequest,
    repo: ContextRepository = Depends(get_context_repository),
    store: BaseContextStore = Depends(get_store),
) -> JSONResponse:
    conversation_store = ConversationStore(store)
    manager = ConversationManager(conversation_store, repo)

    decision = await manager.handle_reply(
        conversation_id=body.conversation_id,
        merchant_id=body.merchant_id,
        customer_id=body.customer_id,
        message=body.message,
        turn_number=body.turn_number,
    )

    logger.info(
        "reply_decision",
        conversation_id=body.conversation_id,
        action=decision.action,
        engagement_tag=decision.engagement_tag,
    )

    if decision.action == "send":
        payload = ReplySendResponse(
            body=decision.body, cta=decision.cta, rationale=decision.rationale
        )
    elif decision.action == "wait":
        payload = ReplyWaitResponse(
            wait_seconds=decision.wait_seconds, rationale=decision.rationale
        )
    else:
        payload = ReplyEndResponse(rationale=decision.rationale)

    return JSONResponse(status_code=200, content=payload.model_dump())
