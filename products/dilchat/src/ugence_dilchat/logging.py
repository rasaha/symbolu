"""Structured logging configuration.

Uses structlog with a JSON renderer. A redaction processor drops keys that must
never be logged (secrets, tokens, raw sensitive birth payloads) as a defence in
depth on top of call-site discipline.
"""

from __future__ import annotations

import logging

import structlog
from structlog.typing import EventDict, WrappedLogger

# Keys that must never appear in logs (privacy/security invariant).
_REDACT_KEYS = {
    "password",
    "password_hash",
    "credential_hash",
    "refresh_token",
    "refresh_token_hash",
    "access_token",
    "authorization",
    "latitude",
    "longitude",
    "birth_time",
    "private_content",
    "content",
    "note",
    "secret",
    "private_key",
    "pem",
    # Production-readiness round PR-A additions: push/device tokens (DEC-3C
    # sensitivity), report evidence/description text (DEC-3B-5), message
    # bodies, and direct identifiers.
    "token",
    "push_token",
    "device_token",
    "expo_push_token",
    "evidence",
    "description",
    "message_body",
    "body",
    "email",
    "database_url",
}


def _redact(_logger: WrappedLogger, _name: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(debug: bool = False) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "dilchat") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
