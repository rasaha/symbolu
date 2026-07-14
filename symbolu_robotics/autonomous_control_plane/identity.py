"""Deterministic canonical identity for ACP envelopes.

A narrowly-scoped, standard-library-only canonicalizer + SHA-256 identity. It is
NOT a copy of the ActionGate reference hasher; it implements only what ACP needs
and documents its rules explicitly (see ``ACP_CANONICAL_IDENTITY.md``).

Rules
-----
* **Included fields:** every dataclass field is included unless it is tagged
  ``field(metadata={"identity": False})`` (used for advisory/provenance fields
  that must not change identity).
* **Excluded fields:** identity-tagged-false fields, and nothing else implicitly.
* **Domain separation:** every identity is prefixed with a ``domain`` label and a
  schema ``version`` and unit-separator bytes, so a world-state hash can never
  collide with an action hash even for identical payloads.
* **Float handling:** non-finite floats (NaN / +Inf / -Inf) raise
  ``NonFiniteValueError``; ``-0.0`` is normalized to ``0.0`` so numerically equal
  values share an identity.
* **Array / sequence ordering:** list/tuple order is significant and preserved
  (a trajectory is order-bearing).
* **Mapping key ordering:** mapping keys are sorted, so dict insertion order does
  not change identity. Keys must be strings.
* **Versioning:** the ``version`` argument is part of the hashed prefix; bumping a
  schema version deliberately invalidates prior identities.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from enum import Enum
from typing import Any, Mapping, Sequence

from .errors import IdentityError, NonFiniteValueError

_UNIT_SEP = "\x1f"


def normalize_float(x: float, *, field: str = "<float>") -> float:
    """Reject non-finite floats loudly; normalize -0.0 to 0.0."""
    if not math.isfinite(x):
        raise NonFiniteValueError(
            f"field {field!r} must be finite, got {x!r}"
        )
    return 0.0 if x == 0.0 else float(x)


def canonicalize(value: Any, *, field: str = "<root>") -> Any:
    """Recursively project a value into a canonical JSON-serializable form.

    Deterministic and total: anything it cannot represent unambiguously raises
    ``IdentityError`` rather than guessing.
    """
    # Order matters: bool is a subclass of int, handle it first.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return normalize_float(value, field=field)
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, Enum):
        return {"__enum__": f"{type(value).__name__}.{value.name}"}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        out = {}
        for f in dataclasses.fields(value):
            if not f.metadata.get("identity", True):
                continue
            out[f.name] = canonicalize(getattr(value, f.name),
                                       field=f"{field}.{f.name}")
        return out
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise IdentityError(
                    f"mapping keys must be str for a deterministic identity; "
                    f"field {field!r} has key {k!r}"
                )
            out[k] = canonicalize(v, field=f"{field}[{k}]")
        return out
    if isinstance(value, Sequence):  # list / tuple — order preserved
        return [canonicalize(v, field=f"{field}[{i}]")
                for i, v in enumerate(value)]
    raise IdentityError(
        f"field {field!r} has non-canonicalizable type {type(value).__name__}; "
        f"ACP identity accepts only None/bool/int/float/str/bytes/Enum/"
        f"dataclass/Mapping/Sequence"
    )


def canonical_json(value: Any) -> str:
    """Canonical JSON string: sorted keys, no whitespace, no NaN/Inf."""
    return json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def identity(value: Any, *, domain: str, version: int = 1) -> str:
    """Domain-separated SHA-256 hex identity of a canonical value."""
    prefix = f"acp{_UNIT_SEP}{domain}{_UNIT_SEP}v{version}{_UNIT_SEP}"
    payload = prefix + canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
