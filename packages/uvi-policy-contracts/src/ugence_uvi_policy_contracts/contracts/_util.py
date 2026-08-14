"""Small stdlib-only validation helpers shared by the contract shapes.

These mirror the established fingerprint/validation discipline of the neutral
``ugence_governance_contracts`` evidence contracts (sorted-key canonical JSON +
sha-256; timezone-aware datetimes; digest-bound references) so the two families
hash and validate consistently.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from enum import Enum

from .errors import PolicyContractError

__all__ = [
    "require_nonempty",
    "validate_digest",
    "require_tzaware",
    "coerce_tuple",
    "normalize_tokens",
    "canonical_digest",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PolicyContractError(f"{name} must be a non-empty string")


def validate_digest(value: str, name: str, *, required: bool) -> None:
    if not value:
        if required:
            raise PolicyContractError(f"{name} is required (sha-256 hex digest)")
        return
    if not _SHA256_RE.match(value):
        raise PolicyContractError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )


def require_tzaware(dt: datetime, name: str) -> None:
    if not isinstance(dt, datetime):
        raise PolicyContractError(f"{name} must be a datetime")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise PolicyContractError(f"{name} must be timezone-aware")


def coerce_tuple(value, name: str) -> tuple:
    """Normalize an accepted sequence into an immutable ``tuple``.

    Rejects scalar substitutes that would otherwise be silently iterated
    element-by-element — a ``str``/``bytes``/``bytearray`` (each character/byte
    would become a bogus element) and a ``Mapping`` (only its keys would be
    taken) — and rejects any non-iterable. A caller-owned ``list`` is copied
    into a fresh tuple so later mutation of that list cannot reach the (frozen)
    contract. A tuple input is preserved with identical contents.
    """

    if isinstance(value, tuple):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        raise PolicyContractError(
            f"{name} must be a sequence of items, not a {type(value).__name__}"
        )
    if isinstance(value, Mapping):
        raise PolicyContractError(f"{name} must be a sequence, not a mapping")
    try:
        return tuple(value)
    except TypeError:
        raise PolicyContractError(
            f"{name} must be an iterable sequence (got {type(value).__name__})"
        )


def normalize_tokens(values, name: str) -> tuple[str, ...]:
    """Coerce to a tuple, then reject blank and duplicate string tokens.

    Preserves caller order. Never converts an invalid element into a valid one:
    a non-string or blank element is rejected, not silently dropped or coerced.
    """

    coerced = coerce_tuple(values, name)
    seen: set[str] = set()
    for v in coerced:
        if not isinstance(v, str) or not v.strip():
            raise PolicyContractError(f"{name} contains a blank or non-string entry")
        if v in seen:
            raise PolicyContractError(f"{name} contains duplicate entry {v!r}")
        seen.add(v)
    return coerced


def canonical_digest(obj) -> str:
    """Deterministic sha-256 over a canonical JSON serialization of a dataclass.

    Sorted keys, tight separators, ``default=str`` — identical inputs (including
    nested frozen dataclasses and enums, which serialize by value) yield an
    identical digest.
    """

    payload = dataclasses.asdict(obj)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=_json_default
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(o):
    if isinstance(o, Enum):
        return o.value
    return str(o)
