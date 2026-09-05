"""Canonical bytes, domain-separated digests, and the instant rules.

Copied in shape from the sibling integration packages and from storygraph's
``canonical.py``; imported from neither. Sorted-key JSON with no whitespace, so
two equal entries digest equally regardless of how a caller built the dict.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .errors import ContractViolation

__all__ = ["canonical_bytes", "domain_digest", "iso", "require_nonempty",
           "require_tzaware"]


def require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ContractViolation(f"{name} must be a string (got {type(value).__name__})")
    text = value.strip()
    if not text:
        raise ContractViolation(f"{name} must be a non-empty string")
    return text


def require_tzaware(value: object, name: str) -> datetime:
    """A naive datetime names no instant, so it is refused rather than assumed UTC."""

    if not isinstance(value, datetime):
        raise ContractViolation(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ContractViolation(f"{name} must be timezone-aware")
    return value


def iso(value: datetime, name: str) -> str:
    """UTC-normalized ISO 8601, so two equal instants at different offsets agree."""

    return require_tzaware(value, name).astimezone(timezone.utc).isoformat()


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def domain_digest(domain: str, payload: dict) -> str:
    """Domain-separated SHA-256, so an entry digest can never collide with a
    chain digest computed over the same bytes."""

    hasher = hashlib.sha256()
    hasher.update(domain.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(canonical_bytes(payload))
    return hasher.hexdigest()
