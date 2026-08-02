"""Canonical, deterministic serialization + data-minimization for durable records.

Records are stored as canonical JSON (sorted keys, compact separators). Only
governance-relevant data is persisted: fields whose names look like credentials or
unrelated PII are **rejected** (fail closed). This module never persists arbitrary
live Python objects — only frozen product records and explicit projection dicts.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
from enum import Enum
from typing import Any, Mapping

from .errors import ProhibitedFieldError

#: Substrings that mark a field name as PROHIBITED (credentials / secrets / PII).
PROHIBITED_KEY_SUBSTRINGS = (
    "token", "secret", "password", "passwd", "private_key", "privatekey",
    "api_key", "apikey", "oauth", "credential", "webhook",
    "salary", "ssn", "social_security", "medical", "health_record",
    "date_of_birth", "home_address",
)


class PayloadClassification(str, Enum):
    REFERENCE_ONLY = "REFERENCE_ONLY"
    NORMALIZED_METADATA = "NORMALIZED_METADATA"
    CANONICAL_PAYLOAD = "CANONICAL_PAYLOAD"
    PROHIBITED = "PROHIBITED"


def classify_key(key: str) -> PayloadClassification:
    low = key.lower()
    for banned in PROHIBITED_KEY_SUBSTRINGS:
        if banned in low:
            return PayloadClassification.PROHIBITED
    return PayloadClassification.CANONICAL_PAYLOAD


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            raise ProhibitedFieldError("naive datetime is not permitted in durable records")
        return value.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    return value


def serialize(obj: Any) -> Any:
    """Recursively serialize a product record to a canonical JSON-compatible value.

    Rejects any mapping key classified PROHIBITED (data minimization).
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (Enum, _dt.datetime)):
        return _normalize_scalar(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return serialize({f.name: getattr(obj, f.name) for f in dataclasses.fields(obj)})
    if isinstance(obj, Mapping):
        out = {}
        for k, v in obj.items():
            key = str(k)
            if classify_key(key) is PayloadClassification.PROHIBITED:
                raise ProhibitedFieldError(f"prohibited field in durable payload: {key!r}")
            out[key] = serialize(v)
        return {k: out[k] for k in sorted(out)}
    if isinstance(obj, (list, tuple)):
        return [serialize(v) for v in obj]
    # Unknown object types are not serialized (no arbitrary live objects).
    raise ProhibitedFieldError(f"non-serializable record field type: {type(obj).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(serialize(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def loads(text: str) -> Any:
    return json.loads(text)


__all__ = [
    "PROHIBITED_KEY_SUBSTRINGS", "PayloadClassification", "classify_key",
    "serialize", "canonical_json", "loads",
]
