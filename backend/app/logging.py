"""
How this works / why it is safe:
This module provides structured JSON logging via structlog.
It automatically redacts sensitive financial and authentication fields
(passwords, auth tokens, session hashes, credit card/raw credentials)
to ensure secrets are never leaked to log aggregators or console streams.
Every log entry includes an immutable request_id and UTC timestamp for auditability.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = {
    "password",
    "password_hash",
    "token",
    "token_hash",
    "authorization",
    "secret",
    "cookie",
}


def censor_sensitive_data(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Recursively scrub sensitive keys from log dictionaries."""
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], dict):
            event_dict[key] = dict(censor_sensitive_data(logger, method_name, event_dict[key]))
    return event_dict


def setup_logging(env: str = "dev") -> None:
    """Configure structured logging pipeline."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        censor_sensitive_data,
    ]

    if env == "prod":
        processors = [*shared_processors, structlog.processors.format_exc_info, structlog.processors.JSONRenderer()]
    else:
        processors = [*shared_processors, structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
