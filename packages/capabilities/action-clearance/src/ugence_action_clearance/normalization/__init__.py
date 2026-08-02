"""Canonical, deterministic normalization (design §10, §16).

Rules (frozen):

* JSON with sorted keys, compact separators ``(",", ":")``, ``ensure_ascii=True``,
  ``allow_nan=False``;
* all strings NFC-normalized;
* datetimes → canonical RFC3339 UTC with a ``Z`` suffix (one canonical form);
* enums encoded by their string value;
* mappings recursively key-sorted; sequences preserve order (except reason codes,
  which the result orders canonically before serialization);
* ``-0.0`` normalized to ``0.0``; ``NaN``/``Inf`` rejected;
* ``None`` is emitted only where meaningful; unsupported/nondeterministic types are
  rejected (never silently stringified).
"""
from __future__ import annotations

import datetime as _dt
import math
import unicodedata
from enum import Enum
from typing import Any, Mapping, Sequence

from ..errors import ValidationError


def normalize_timestamp(value: _dt.datetime) -> str:
    """Return a canonical RFC3339 UTC timestamp string (``...Z``)."""
    if not isinstance(value, _dt.datetime):
        raise ValidationError(f"expected datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        raise ValidationError("timestamps must be timezone-aware")
    utc = value.astimezone(_dt.timezone.utc)
    # microsecond precision, always 'Z'
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def normalize_value(value: Any) -> Any:
    """Recursively normalize a JSON-compatible value to a canonical form.

    Rejects unsupported/nondeterministic types instead of stringifying them.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValidationError("NaN/Inf are not permitted in normalized values")
        return 0.0 if value == 0.0 else value
    if isinstance(value, _dt.datetime):
        return normalize_timestamp(value)
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValidationError("mapping keys must be strings")
            out[unicodedata.normalize("NFC", k)] = normalize_value(v)
        return {k: out[k] for k in sorted(out)}
    if isinstance(value, (list, tuple)):
        return [normalize_value(v) for v in value]
    raise ValidationError(f"unsupported non-deterministic value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize a normalized value to canonical JSON."""
    import json

    return json.dumps(
        normalize_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


__all__ = ["normalize_timestamp", "normalize_value", "canonical_json"]
