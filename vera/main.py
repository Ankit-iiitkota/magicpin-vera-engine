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

import asyncio
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
from vera.store.memory_store import InMemoryContextStore
from vera.store.store_factory import create_store
from vera.utils.logging import configure_logging

logger = structlog.get_logger(__name__)

_STORE_CONNECT_TIMEOUT = 5.0  # seconds — must complete before healthcheck window closes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Initialise defaults so the yield is always reached even on total failure.
    app.state.started_at = time.monotonic()
    app.state.store = InMemoryContextStore()
    app.state.context_repository = ContextRepository(app.state.store)

    try:
        settings = get_settings()
        configure_logging(settings.log_level, settings.log_format)
        app.state.settings = settings

        logger.info("vera_startup_begin", env=settings.env, app_version=settings.app_version)

        try:
            store = await asyncio.wait_for(
                create_store(settings),
                timeout=_STORE_CONNECT_TIMEOUT,
            )
            app.state.store = store
            app.state.context_repository = ContextRepository(store)
            logger.info(
                "vera_startup_complete",
                env=settings.env,
                store_backend=store.backend_name,
                app_version=settings.app_version,
            )
        except asyncio.TimeoutError:
            logger.error(
                "vera_store_connect_timeout",
                timeout_seconds=_STORE_CONNECT_TIMEOUT,
                fallback="memory",
                message="create_store() did not complete within the timeout window; "
                        "falling back to in-memory store so the app can serve requests",
            )
        except Exception as exc:
            logger.error(
                "vera_store_connect_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                fallback="memory",
                message="create_store() raised an unexpected error; "
                        "falling back to in-memory store",
            )

    except Exception as exc:
        # Settings or logging init failed — still safe to continue with defaults.
        logger.error(
            "vera_startup_settings_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )

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
