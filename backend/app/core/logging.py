"""Structured logging setup (SPEC §6.3).

Call `configure_logging()` at process startup (web app + worker).
`pretty` format colors output for dev; `json` emits one JSON object per
line so log shippers can ingest stdout directly.
"""
from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog

from app.core.config import settings

LogFormat = Literal["pretty", "json"]


def configure_logging() -> None:
    fmt: LogFormat = "json" if settings.LOG_FORMAT.lower() == "json" else "pretty"
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Stdlib root: just deliver to stderr at the chosen level. Structlog wraps
    # this so library logs (uvicorn, sqlalchemy.engine) flow through too.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if fmt == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
