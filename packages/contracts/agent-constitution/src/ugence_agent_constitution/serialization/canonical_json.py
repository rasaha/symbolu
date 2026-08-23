"""Canonical JSON serialization.

Deterministic, reproducible serialization is the backbone of content addressing.
Canonical form: sorted keys, no insignificant whitespace, UTF-8, and a stable
representation of pydantic models and enums. Volatile values (timestamps,
filesystem paths) are excluded from *logical* digests by the callers that build
them — this module only guarantees a stable encoding of whatever it is given.

DELIBERATE DUPLICATION. The semantics here are identical **by value** to
``ugence_policy_workflow_compiler.serialization.canonical_json``: same recursion,
same key ordering, same separators, same enum-by-value rule, same set ordering by
``repr``. It is duplicated rather than imported because this package is a leaf —
importing the compiler would invert the dependency direction and drag a tooling
distribution into a contract distribution. The equivalence is not left to
inspection: ``tests/serialization/test_canonical_json_equivalence.py`` loads the
compiler's module directly off disk and asserts byte-identical output over a
shared corpus, so a future divergence in either copy fails a gate.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel


def to_canonical_obj(value: Any) -> Any:
    """Recursively convert ``value`` into JSON-native, deterministically ordered
    Python objects.

    * pydantic models -> dict (via ``model_dump`` with enums as values)
    * enums -> their ``.value``
    * mappings -> dict with sorted keys
    * tuples/sets -> lists (sets sorted for determinism)
    """
    if isinstance(value, BaseModel):
        return to_canonical_obj(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): to_canonical_obj(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [to_canonical_obj(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [to_canonical_obj(v) for v in sorted(value, key=repr)]
    return value


def dumps(value: Any) -> str:
    """Serialize ``value`` to a canonical JSON string (sorted keys, compact)."""
    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def dumps_pretty(value: Any) -> str:
    """Serialize ``value`` to canonical-but-readable JSON (sorted keys, indented).

    Used for on-disk package files. Key ordering is still canonical, so the file
    content is reproducible; indentation does not affect logical digests, which are
    computed from :func:`dumps`.
    """
    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    ) + "\n"


def loads(text: str) -> Any:
    """Parse a JSON string back to Python objects."""
    return json.loads(text)


__all__ = ["to_canonical_obj", "dumps", "dumps_pretty", "loads"]
