"""Package-local validation and canonicalization (no reliance on any
underscore-prefixed helper of another distribution).

Digest discipline is the slice 1 payload rule, restated here and verified
against canonicalization vectors in ``tests/test_canonicalization.py``:
enums by value, datetimes as RFC 3339 UTC strings with microseconds and a
``Z`` suffix, booleans and integers as strings (JCS admits no bare number),
``None`` as null, tuples in declared order, nested dataclasses recursively,
floats refused. The digest is ``ugence_jcs.canonical_sha256_hex`` over that
shape, with no prefix and no envelope.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping

from ugence_jcs import canonical_sha256_hex
from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a non-blank string")
    return value


def require_digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, f"{name} must be 64 lowercase hex characters")
    return value


def require_tzaware(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ContractError(ContractErrorCode.DATETIME_NAIVE, f"{name} must be a timezone-aware datetime")
    return value


def require_str_tuple(value: Any, name: str) -> tuple:
    if not isinstance(value, tuple):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a tuple")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} contains a blank or non-string item")
    return value


def require_member(value: Any, enum_cls: type, name: str, code: ContractErrorCode) -> Any:
    if not isinstance(value, enum_cls):
        raise ContractError(code, f"{name} must be a {enum_cls.__name__} member, got {value!r}")
    return value


def rfc3339_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def payload(obj: Any, *, exclude: Iterable[str] = ()) -> Any:
    """Render a contract value as a JCS-safe JSON shape (top-level field exclusion only)."""
    excluded = set(exclude)
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, float):
        raise TypeError("floats are not admitted into a canonical payload; carry decimals as strings")
    if isinstance(obj, Enum):
        return obj.value if isinstance(obj.value, str) else str(obj.value)
    if isinstance(obj, datetime):
        return rfc3339_utc(obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: payload(getattr(obj, f.name)) for f in dataclasses.fields(obj) if f.name not in excluded}
    if isinstance(obj, Mapping):
        return {str(k): payload(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [payload(v) for v in obj]
    raise TypeError(f"unsupported payload type {type(obj).__name__}")


def digest_of(obj: Any, *, exclude: Iterable[str] = ()) -> str:
    return canonical_sha256_hex(payload(obj, exclude=exclude))


def settle_digest(obj: Any, field_name: str, computed: str) -> None:
    """Fill an empty self-digest field, or verify a supplied one exactly (DIGEST_MALFORMED otherwise)."""
    supplied = getattr(obj, field_name)
    if supplied == "":
        object.__setattr__(obj, field_name, computed)
        return
    require_digest(supplied, field_name)
    if supplied != computed:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, f"{field_name} does not match the canonical digest of the payload")


__all__ = ["require_nonblank", "require_digest", "require_tzaware", "require_str_tuple", "require_member", "rfc3339_utc", "payload", "digest_of", "settle_digest"]
