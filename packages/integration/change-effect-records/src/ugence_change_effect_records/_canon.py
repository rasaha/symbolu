"""Module-local canonicalization — the rule section 6a **profile**, stdlib only.

The same shape as the sibling integration packages' ``_canon.py``: copied, never
imported. The envelope is theirs unchanged — namespace, U+001F separator, schema
version, ``json.dumps`` with sorted keys and compact separators, SHA-256 hex. The
profile adds what the envelope does not impose and what an identifier needs:

* recursive NFC normalization of every string at every depth;
* absent fields omitted, never ``null``;
* integers only, within signed 64 bits — no floats, no exponent;
* **JSON booleans refused outright**, so a language that treats ``True`` as ``1``
  cannot admit a flag where a count was meant. A flag is an enumerated string;
* order-significant lists in the order the rule defines, sets sorted first;
* the full 64-character lowercase digest, **never truncated**.

No clock is read anywhere in this package; every instant is a caller input.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from typing import Any

from .errors import CanonicalFormRefused, ContractViolation

_NAMESPACE = "change_effect_classifier"
_US = "\x1f"
_SCHEMA = "v1"

#: Signed 64-bit range, inclusive.
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def normalize_text(value: str) -> str:
    """NFC, the profile's normal form for every string."""

    return unicodedata.normalize("NFC", value)


def normalize_tenant(value: str) -> str:
    """Tenant identity is additionally trimmed and lower-cased before hashing."""

    return normalize_text(require_nonempty(value, "tenant")).strip().lower()


def profile(value: Any, path: str = "$") -> Any:
    """Return ``value`` in profile form, or refuse it.

    Pure: it reads no clock, no environment and no state, and returns a new value
    rather than mutating the caller's.
    """

    if value is None:
        raise CanonicalFormRefused("CANONICAL_NULL_FORBIDDEN", path)
    if isinstance(value, bool):
        raise CanonicalFormRefused("CANONICAL_BOOLEAN_REFUSED", f"{path}: use an enumerated string")
    if isinstance(value, float):
        raise CanonicalFormRefused("CANONICAL_NUMBER_REFUSED", f"{path}: float")
    if isinstance(value, int):
        if not INT64_MIN <= value <= INT64_MAX:
            raise CanonicalFormRefused("CANONICAL_NUMBER_REFUSED", f"{path}: outside int64")
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, dict):
        return {profile(k, path): profile(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [profile(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise CanonicalFormRefused("CANONICAL_TYPE_REFUSED", f"{path}: {type(value).__name__}")


def canonical_json(payload: Any) -> str:
    """The sibling packages' encoding, byte for byte."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def domain_digest(domain: str, payload: Any) -> str:
    """Domain-separated SHA-256 over the profiled payload. Full 64 hex, never truncated.

    A literal U+001F inside any string is escaped by the JSON encoder as ``\\u001f``
    and cannot be mistaken for the separator, which supplies the framing that bare
    concatenation lacks.
    """

    preimage = f"{_NAMESPACE}{_US}{domain}{_US}{_SCHEMA}{_US}{canonical_json(profile(payload))}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{name} must be a non-empty string")
    return value


def require_digest(value: object, name: str) -> str:
    """A full lowercase SHA-256 hex digest. Truncation is refused, not tolerated."""

    text = require_nonempty(value, name)
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ContractViolation(
            f"{name} must be a full 64-character lowercase SHA-256 hex digest"
        )
    return text


def require_ordinal(value: object, name: str) -> int:
    """A non-negative integer, and never a boolean."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractViolation(f"{name} must be an integer and never a boolean")
    if value < 0 or value > INT64_MAX:
        raise ContractViolation(f"{name} must be a non-negative int64")
    return value


def require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ContractViolation(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ContractViolation(f"{name} must be timezone-aware")
    return value


def iso(value: datetime, name: str = "instant") -> str:
    """Canonical UTC ISO-8601 text with microseconds, as the sibling packages write it."""

    return require_tzaware(value, name).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f+00:00"
    )
