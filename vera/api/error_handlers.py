"""
vera.api.error_handlers — spec-compliant 400s for malformed requests.

FastAPI's default behaviour for a request body that fails Pydantic
validation (a missing required field, `version` as a non-numeric
string, `payload` that isn't an object, or one of our own added
constraints like `version > 0`) is a 422 with its own
`{"detail": [...]}` envelope — not the `{"accepted": false, "reason":
..., "details": ...}` shape challenge-testing-brief.md §2.1 documents
for malformed /v1/context requests.

context_validation_exception_handler intercepts exactly that case for
the /v1/context route and re-shapes it into the documented 400.
Every other route (including ones added in later phases that don't
opt into this contract) keeps FastAPI's default 422 behaviour.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exception_handlers import (
    request_validation_exception_handler as _default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from vera.api.models.context import ContextPushRejected

CONTEXT_PUSH_PATH = "/v1/context"


def _format_errors(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "body")
        msg = err.get("msg", "invalid")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) or str(exc)


async def context_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Route /v1/context body-validation failures to the documented 400 shape."""
    if request.url.path == CONTEXT_PUSH_PATH:
        return JSONResponse(
            status_code=400,
            content=ContextPushRejected(
                reason="malformed_request", details=_format_errors(exc)
            ).model_dump(),
        )
    return await _default_validation_handler(request, exc)
