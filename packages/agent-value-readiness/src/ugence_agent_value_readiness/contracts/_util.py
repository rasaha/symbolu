"""Stdlib-only validation helpers shared by the readiness contract shapes.

These mirror the hardened GV-2E-a / GV-2C-a discipline: sequences are coerced to
real tuples (scalar substitutes rejected) before validation, digests are
sha-256-hex, timestamps are timezone-aware, and Decimal fields reject binary
floats. Canonical serialization is sorted-key JSON + sha-256.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from .errors import ReadinessContractError

__all__ = [
    "require_nonempty",
    "validate_digest",
    "require_tzaware",
    "coerce_tuple",
    "normalize_tokens",
    "require_decimal",
    "canonical_digest",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReadinessContractError(f"{name} must be a non-empty string")


def validate_digest(value: str, name: str, *, required: bool) -> None:
    if not value:
        if required:
            raise ReadinessContractError(f"{name} is required (sha-256 hex digest)")
        return
    if not _SHA256_RE.match(value):
        raise ReadinessContractError(f"{name} must be a lowercase 64-char sha-256 hex digest")


def require_tzaware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise ReadinessContractError(f"{name} must be a datetime")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ReadinessContractError(f"{name} must be timezone-aware")


def coerce_tuple(value, name: str) -> tuple:
    """Normalize an accepted sequence into an immutable ``tuple``.

    Rejects scalar substitutes that would otherwise be iterated element-by-element
    (``str``/``bytes``/``bytearray``) and a ``Mapping`` (only its keys would be
    taken), and rejects a non-iterable. A caller ``list`` is copied into a fresh
    tuple so later mutation cannot reach the frozen contract; a tuple is preserved.
    """

    if isinstance(value, tuple):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        raise ReadinessContractError(
            f"{name} must be a sequence of items, not a {type(value).__name__}"
        )
    if isinstance(value, Mapping):
        raise ReadinessContractError(f"{name} must be a sequence, not a mapping")
    try:
        return tuple(value)
    except TypeError:
        raise ReadinessContractError(
            f"{name} must be an iterable sequence (got {type(value).__name__})"
        )


def normalize_tokens(values, name: str) -> tuple[str, ...]:
    """Coerce to a tuple, then reject blank/non-string and duplicate tokens."""

    coerced = coerce_tuple(values, name)
    seen: set[str] = set()
    for v in coerced:
        if not isinstance(v, str) or not v.strip():
            raise ReadinessContractError(f"{name} contains a blank or non-string entry")
        if v in seen:
            raise ReadinessContractError(f"{name} contains duplicate entry {v!r}")
        seen.add(v)
    return coerced


def require_decimal(value, name: str) -> Decimal:
    """Return a finite ``Decimal``; reject binary ``float``/``bool``, NaN, infinity.

    Accepts a ``Decimal``, an ``int`` (exact), or a numeric ``str`` (exact
    textual parse). A ``float`` is **rejected** — binary floating point is
    inexact and must never be used for a governed score.
    """

    if isinstance(value, bool):
        raise ReadinessContractError(f"{name} must not be a bool")
    if isinstance(value, float):
        raise ReadinessContractError(
            f"{name} must be a Decimal/int/str, not a binary float (inexact)"
        )
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, str):
        try:
            dec = Decimal(value)
        except InvalidOperation:
            raise ReadinessContractError(f"{name} is not a valid decimal string: {value!r}")
    else:
        raise ReadinessContractError(f"{name} must be a Decimal, int, or numeric str")
    if not dec.is_finite():
        raise ReadinessContractError(f"{name} must be finite (no NaN/Infinity)")
    return dec


def canonical_digest(obj) -> str:
    """Deterministic sha-256 over a canonical JSON serialization of a dataclass."""

    payload = dataclasses.asdict(obj)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(o):
    if isinstance(o, Enum):
        return o.value
    return str(o)
