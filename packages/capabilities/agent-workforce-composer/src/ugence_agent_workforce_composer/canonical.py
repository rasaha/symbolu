"""Canonical serialization, content-addressing, and the frozen base model.

Deterministic serialization is the backbone of every AWC digest and fingerprint.
Canonical form: pydantic models dumped with enums-as-values, sorted keys, compact
separators, UTF-8, tuples as lists, sets sorted. Volatile values (wall-clock
timestamps) are never embedded in a *logical* digest — logical time is always
injected by the caller, never read from the system clock.

``AwcModel`` is the frozen, ``extra='forbid'`` base for every canonical planning
object, mirroring the compiler's ``CompilerModel`` discipline so unknown fields
are rejected and objects are immutable and hashable.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

#: Prefix marking a logical (timestamp-free) digest.
DIGEST_PREFIX = "sha256:"


def to_canonical_obj(value: Any) -> Any:
    """Recursively convert ``value`` into JSON-native, deterministically ordered
    Python objects.

    * pydantic models -> dict (enums serialized by value)
    * enums -> their ``.value``
    * mappings -> dict with sorted keys
    * tuples/lists -> lists; sets/frozensets -> sorted lists
    """
    if isinstance(value, BaseModel):
        return to_canonical_obj(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): to_canonical_obj(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [to_canonical_obj(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [to_canonical_obj(v) for v in sorted(value, key=repr)]
    return value


def canonical_json(value: Any) -> str:
    """Serialize ``value`` to a canonical JSON string (sorted keys, compact)."""
    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest(value: Any) -> str:
    """Return ``sha256:<hex>`` over the canonical JSON encoding of ``value``."""
    encoded = canonical_json(value).encode("utf-8")
    return DIGEST_PREFIX + hashlib.sha256(encoded).hexdigest()


class AwcModel(BaseModel):
    """Frozen, extra-forbidding base for every canonical AWC object.

    ``frozen=True`` makes objects hashable and immutable; ``extra='forbid'``
    rejects unknown fields (no silent, undeclared data). Enums serialize by value,
    keeping canonical JSON stable across processes and Python builds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)

    def canonical_dict(self) -> dict:
        """The deterministically ordered, JSON-native view of this object."""
        return to_canonical_obj(self)

    def content_digest(self) -> str:
        """Content digest over this object's canonical form."""
        return digest(self)


__all__ = [
    "DIGEST_PREFIX",
    "AwcModel",
    "to_canonical_obj",
    "canonical_json",
    "digest",
]
