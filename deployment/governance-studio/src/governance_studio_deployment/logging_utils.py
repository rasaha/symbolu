"""Structured, redacting logs (P3E §17).

Emits one JSON object per event to stdout. Only an allowlisted set of fields is ever
written; credentials, Authorization headers, bodies, query strings and scenario
payloads are never logged. Correlation IDs are generated when absent and always
sanitised.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from typing import Any, Dict

from . import DEPLOYMENT_VERSION

_ALLOWED_FIELDS = {
    "timestamp", "level", "event", "method", "route", "status", "duration_ms",
    "correlation_id", "deployment_version", "integrity_result",
}
_ID_RE = re.compile(r"[^A-Za-z0-9_.-]")


def sanitize_correlation_id(raw: str | None) -> str:
    if not raw:
        return uuid.uuid4().hex
    cleaned = _ID_RE.sub("", raw)[:64]
    return cleaned or uuid.uuid4().hex


def log_event(event: str, *, level: str = "info", timestamp: str = "", **fields: Any) -> None:
    record: Dict[str, Any] = {"event": event, "level": level, "deployment_version": DEPLOYMENT_VERSION}
    if timestamp:
        record["timestamp"] = timestamp
    for key, value in fields.items():
        if key in _ALLOWED_FIELDS:
            record[key] = value
    # hard drop of anything that could carry a secret, defensively
    for banned in ("authorization", "password", "password_hash", "body", "query", "cookie",
                   "proof", "x-ugence-approver-proof", "review_service_url"):
        record.pop(banned, None)
    sys.stdout.write(json.dumps(record, sort_keys=True) + "\n")
    sys.stdout.flush()
