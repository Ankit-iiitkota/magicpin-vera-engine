"""
vera.utils.logging — Structured logging configuration.

Uses structlog for machine-readable JSON logs in production and
human-friendly coloured output in development / console mode.

Call configure_logging(log_level, log_format) once at application startup
(from vera.main lifespan). All other modules import and use structlog directly:

    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("event_name", key=value, ...)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure structlog and stdlib logging.

    Parameters
    ----------
    log_level:
        One of DEBUG | INFO | WARNING | ERROR | CRITICAL.
    log_format:
        'json'    → JSON lines, suitable for log aggregators (Datadog, CloudWatch).
        'console' → Human-friendly coloured output for local development.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── Shared processors (applied in order) ─────────────────────────────────
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        # JSON output — each log line is a valid JSON object
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Console output — coloured, human-friendly
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── stdlib handler ────────────────────────────────────────────────────────
    # `shared_processors` already ran once above for structlog-native log
    # calls (structlog.get_logger(...).info(...)), where a real bound logger
    # is available throughout the chain.
    #
    # Records that reach this formatter via plain stdlib `logging` calls —
    # e.g. everything Uvicorn itself logs (startup banner, access log,
    # error log) — never went through that chain, so they need
    # `shared_processors` applied here instead. `foreign_pre_chain` is the
    # correct place for that: it runs while `_record` (and therefore
    # `record.name`) is still attached to the event dict. `processors` runs
    # on *every* record afterwards and must stay minimal — putting
    # `add_logger_name` there instead (as before) ran it *after*
    # `remove_processors_meta` had already stripped `_record`, and foreign
    # records have no bound logger to fall back on, which is exactly what
    # raised `AttributeError: 'NoneType' object has no attribute 'name'`.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    # ── Silence noisy third-party loggers ────────────────────────────────────
    for name in ("uvicorn.access", "uvicorn.error", "uvicorn"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
