"""Module-local canonicalization helpers (stdlib only).

The same shape as the sibling integration packages — copied, never imported:
sorted-key compact JSON, SHA-256, UTC-normalized instants, and a hard refusal of
naive datetimes. No clock is read anywhere in this package; every instant is a
caller input.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .errors import ContractViolation

_NAMESPACE = "incident_response"
_US = "\x1f"


def require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ContractViolation(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ContractViolation(f"{name} must be timezone-aware")
    return value


def to_utc(value: datetime, name: str) -> datetime:
    """Re-express an aware instant in UTC with an explicit target (pure arithmetic)."""

    return require_tzaware(value, name).astimezone(timezone.utc)


def iso(value: datetime, name: str = "instant") -> str:
    """Canonical UTC ISO-8601 text with microseconds, suitable for storage and ordering."""

    return to_utc(value, name).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def from_iso(text: str) -> datetime:
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def domain_digest(domain: str, payload: Any) -> str:
    """Domain-separated SHA-256 in the same preimage shape the sibling packages use."""

    preimage = f"{_NAMESPACE}{_US}{domain}{_US}v1{_US}{canonical_json(payload)}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{name} must be a non-empty string")
    return value.strip()


def optional_text(value: object, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContractViolation(f"{name} must be a string")
    return value.strip()
