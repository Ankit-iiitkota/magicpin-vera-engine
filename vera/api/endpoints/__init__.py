"""
FastAPI endpoint handlers.

Phase 1: healthz + metadata. Phase 2: context (POST /v1/context).
Phase 8: tick (POST /v1/tick) + reply (POST /v1/reply) — all 5
endpoints challenge-testing-brief.md §2 requires are now wired.
"""

from __future__ import annotations

from vera.api.endpoints import context, healthz, metadata, reply, tick

routers = [healthz.router, metadata.router, context.router, tick.router, reply.router]

__all__ = ["routers"]
