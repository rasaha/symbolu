"""Deterministic canonical serialization.

One serialization function shared throughout the entire stack. Every digest
and every signature in the package is computed over the output of
:func:`canonical_bytes`, so the rules here are load-bearing invariants, not
formatting preferences.

Canonicalization rules (spec §8, §27):

* deterministic field ordering (object keys sorted lexicographically);
* explicit ``null`` handling (``None`` -> JSON ``null``, never dropped);
* stable timestamps (``datetime`` -> RFC 3339 UTC ``Z`` with microseconds);
* normalized Unicode (NFC) for every string;
* integers for monetary/exact values; ``float`` is rejected outright;
* stable enum serialization (``Enum`` -> its ``.value``);
* canonical collection ordering where semantic order is irrelevant
  (``set``/``frozenset`` are sorted; ``list``/``tuple`` preserve order);
* ``bytes`` are base64url-encoded without padding.

The output is compact UTF-8 JSON (no insignificant whitespace) so that the
byte stream is identical across processes, platforms and Python builds.
"""

from __future__ import annotations

import base64
import json
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping

__all__ = ["to_canonical_obj", "canonical_dumps", "canonical_bytes"]

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _normalize_str(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _format_datetime(value: datetime) -> str:
    # All timestamps are normalized to UTC before formatting so that two
    # instants that are equal compare byte-equal regardless of source tzinfo.
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return aware.strftime(_TIMESTAMP_FMT)


def to_canonical_obj(value: Any) -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (with sorted string keys), ``list``,
    ``str``, ``int``, ``bool`` and ``None`` — the primitives ``json.dumps``
    can render deterministically.
    """

    # NB: ``bool`` before ``int`` (``bool`` is a subclass of ``int``) and the
    # explicit ``float`` rejection must both precede any numeric handling.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise TypeError(
            "float is not canonicalizable — use integer minor units or a string "
            "for exact values"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _normalize_str(value)
    if isinstance(value, bytes):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    if isinstance(value, Enum):
        return to_canonical_obj(value.value)
    if isinstance(value, datetime):
        return _format_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        out: dict[str, Any] = {}
        for f in fields(value):
            # Fields flagged as non-canonical (e.g. an attached signature) are
            # excluded so the signing payload is stable.
            if f.metadata.get("canonical") is False:
                continue
            out[_normalize_str(f.name)] = to_canonical_obj(getattr(value, f.name))
        return out
    if isinstance(value, Mapping):
        return {_normalize_str(str(k)): to_canonical_obj(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        # Semantic order is irrelevant for a set: sort by canonical rendering.
        rendered = [to_canonical_obj(v) for v in value]
        return sorted(rendered, key=lambda x: json.dumps(x, sort_keys=True))
    if isinstance(value, (list, tuple)):
        # Ordered collections preserve order (order is semantic).
        return [to_canonical_obj(v) for v in value]
    raise TypeError(f"type {type(value)!r} is not canonicalizable")


def canonical_dumps(value: Any) -> str:
    """Return the canonical compact JSON string for ``value``."""

    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_bytes(value: Any) -> bytes:
    """Return the canonical UTF-8 byte stream for ``value``."""

    return canonical_dumps(value).encode("utf-8")
