"""
FastAPI endpoint handlers.

Phase 1 implemented healthz + metadata. Phase 2 adds context (POST
/v1/context). tick/reply routers are added to `routers` as they're
implemented in later phases.
"""

from __future__ import annotations

from vera.api.endpoints import context, healthz, metadata

routers = [healthz.router, metadata.router, context.router]

__all__ = ["routers"]
