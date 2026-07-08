"""
FastAPI endpoint handlers.

Phase 1 implements healthz + metadata only. context/tick/reply routers
are added to `routers` as they're implemented in later phases.
"""

from __future__ import annotations

from vera.api.endpoints import healthz, metadata

routers = [healthz.router, metadata.router]

__all__ = ["routers"]
