"""
vera.api.endpoints.context — POST /v1/context.

Receives a context push (category | merchant | customer | trigger),
validates it against the corresponding Pydantic schema from
vera.contexts, and hands it to ContextRepository for versioned,
idempotent storage. See challenge-testing-brief.md §2.1 for the exact
request/response contract this endpoint implements.

No business logic lives here — this endpoint only validates and
persists. Feature extraction, signals, goals, templates, ranking,
composition, and suppression are later phases.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from vera.api.deps import get_context_repository
from vera.api.models.context import (
    ALLOWED_PUSH_SCOPES,
    ContextPushAccepted,
    ContextPushRejected,
    ContextPushRequest,
)
from vera.contexts.category import CategoryContext
from vera.contexts.customer import CustomerContext
from vera.contexts.merchant import MerchantContext
from vera.contexts.trigger import TriggerContext
from vera.store.context_repository import ContextRepository, SaveStatus
from vera.utils.time_utils import parse_iso8601

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["context"])

_SCOPE_MODELS: dict[str, type[BaseModel]] = {
    "category": CategoryContext,
    "merchant": MerchantContext,
    "customer": CustomerContext,
    "trigger": TriggerContext,
}
assert set(_SCOPE_MODELS) == set(ALLOWED_PUSH_SCOPES)


def _rejected(status_code: int, **fields: object) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=ContextPushRejected(**fields).model_dump())


@router.post("/v1/context")
async def push_context(
    body: ContextPushRequest,
    repo: ContextRepository = Depends(get_context_repository),
) -> JSONResponse:
    model_cls = _SCOPE_MODELS.get(body.scope)
    if model_cls is None:
        logger.warning("context_push_rejected", reason="invalid_scope", scope=body.scope)
        return _rejected(
            400,
            reason="invalid_scope",
            details=f"scope must be one of {sorted(_SCOPE_MODELS)}, got {body.scope!r}",
        )

    try:
        parse_iso8601(body.delivered_at)
    except ValueError as exc:
        logger.warning("context_push_rejected", reason="invalid_delivered_at", scope=body.scope)
        return _rejected(400, reason="invalid_delivered_at", details=str(exc))

    try:
        validated = model_cls.model_validate(body.payload)
    except ValidationError as exc:
        logger.warning(
            "context_push_rejected",
            reason="invalid_payload",
            scope=body.scope,
            context_id=body.context_id,
        )
        return _rejected(400, reason="invalid_payload", details=str(exc))

    result = await repo.save_context(
        scope=body.scope,
        context_id=body.context_id,
        version=body.version,
        payload=validated.model_dump(mode="json", by_alias=True),
        delivered_at=body.delivered_at,
    )

    if result.status is SaveStatus.STALE:
        logger.info(
            "context_push_rejected",
            reason="stale_version",
            scope=body.scope,
            context_id=body.context_id,
            submitted_version=body.version,
            current_version=result.current_version,
        )
        return _rejected(409, reason="stale_version", current_version=result.current_version)

    logger.info(
        "context_push_accepted",
        scope=body.scope,
        context_id=body.context_id,
        version=result.version,
        status=result.status.value,
    )
    accepted = ContextPushAccepted(
        ack_id=f"ack_{body.context_id}_v{result.version}",
        stored_at=result.stored_at,
    )
    return JSONResponse(status_code=200, content=accepted.model_dump())
