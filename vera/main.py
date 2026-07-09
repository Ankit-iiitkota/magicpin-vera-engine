"""
vera.main — FastAPI application entrypoint.

Wires together settings, structured logging, and the context store
(Redis with automatic in-memory fallback — see vera.store.store_factory)
behind FastAPI's lifespan hook, then mounts the API routers.

Run directly with uvicorn:

    uvicorn vera.main:app --host 0.0.0.0 --port 8080 --reload

Or via Docker (see Dockerfile / docker-compose.yml).
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from vera.api.endpoints import routers
from vera.api.error_handlers import context_validation_exception_handler
from vera.config import get_settings
from vera.store.context_repository import ContextRepository
from vera.store.store_factory import create_store
from vera.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        settings = get_settings()
        configure_logging(settings.log_level, settings.log_format)

        app.state.settings = settings
        app.state.started_at = time.monotonic()
        app.state.store = await create_store(settings)
        app.state.context_repository = ContextRepository(app.state.store)

        logger.info(
            "vera_startup",
            env=settings.env,
            store_backend=app.state.store.backend_name,
            app_version=settings.app_version,
        )
    except Exception as exc:
        print(f"LIFESPAN ERROR: {exc}")
        # fallback to prevent crash
        from vera.store.memory_store import InMemoryContextStore
        app.state.store = InMemoryContextStore()
        app.state.context_repository = ContextRepository(app.state.store)
    
    yield

    try:
        await app.state.store.close()
        logger.info("vera_shutdown")
    except Exception:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    for router in routers:
        app.include_router(router)
    app.add_exception_handler(RequestValidationError, context_validation_exception_handler)
    return app


try:
    app = create_app()
except Exception as exc:
    import traceback
    err_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"CRITICAL STARTUP ERROR:\n{err_str}")
    
    app = FastAPI()
    
    @app.get("/v1/healthz")
    def dummy_healthz():
        return {"status": "error", "message": err_str}
        
    @app.post("/v1/context")
    def dummy_context():
        return {"status": "error", "message": err_str}
