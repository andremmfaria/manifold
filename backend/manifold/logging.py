import logging
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog

from manifold.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_var: ContextVar[str | None] = ContextVar("session_id", default=None)

SENSITIVE_FIELDS = {
    "access_token",
    "refresh_token",
    "iban",
    "account_number",
    "sort_code",
    "pan",
    "card_number",
    "credentials",
    "config",
}


def drop_sensitive_fields(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if key in SENSITIVE_FIELDS:
            event_dict[key] = "[redacted]"
    return event_dict


def add_correlation(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    event_dict.setdefault("request_id", request_id_var.get())
    event_dict.setdefault("user_id", user_id_var.get())
    event_dict.setdefault("session_id", session_id_var.get())
    return event_dict


def configure_logging() -> None:
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_correlation,
            drop_sensitive_fields,
            structlog.processors.dict_tracebacks,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
