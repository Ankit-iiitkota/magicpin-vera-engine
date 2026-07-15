"""
vera.api.deps — FastAPI dependency-injection providers.

Every dependency reads from `request.app.state`, which is populated once
in `vera.main`'s lifespan handler (settings, store, process start time).
Endpoints declare these via `Depends(...)` instead of importing globals
directly, so they stay testable with a substitute app.state in tests.
"""

from __future__ import annotations

from fastapi import Request

from vera.config import Settings
from vera.store.base_store import BaseContextStore
from vera.store.context_repository import ContextRepository


def get_app_settings(request: Request) -> Settings:
    """Return the Settings instance bound to this app at startup."""
    return request.app.state.settings


def get_store(request: Request) -> BaseContextStore:
    """Return the active context store (Redis or in-memory fallback)."""
    return request.app.state.store


def get_context_repository(request: Request) -> ContextRepository:
    """Return the app-wide ContextRepository singleton."""
    return request.app.state.context_repository


def get_started_at(request: Request) -> float:
    """Return the monotonic timestamp captured at process startup."""
    return request.app.state.started_at
