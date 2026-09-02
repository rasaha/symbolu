"""Shared validation and canonicalization helpers.

Digests are ``ugence_jcs.canonical_sha256_hex`` over a JSON-shaped payload built
from a contract's fields: enums by value, datetimes as RFC 3339 UTC strings,
integers as decimal strings (JCS rejects bare numbers), ``None`` as null,
tuples in declared order, nested dataclasses recursively. No prefix, no
envelope, ``set_paths`` and ``nfc_paths`` empty.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from ugence_jcs import canonical_sha256_hex

from ..errors import ContractError, ContractErrorCode

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def require_nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a non-blank string")
    return value


def require_digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        raise ContractError(
            ContractErrorCode.DIGEST_MALFORMED, f"{name} must be 64 lowercase hex characters"
        )
    return value


def require_tzaware(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ContractError(ContractErrorCode.DATETIME_NAIVE, f"{name} must be a timezone-aware datetime")
    return value


def require_decimal_string(value: Any, name: str) -> str:
    """A finite decimal carried as a string. Returns the input unchanged."""
    if not isinstance(value, str) or not value.strip():
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name} must be a decimal string")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name}={value!r} is not a decimal") from None
    if not d.is_finite():
        raise ContractError(ContractErrorCode.DECIMAL_UNPARSEABLE, f"{name}={value!r} is not finite")
    return value


def require_str_tuple(value: Any, name: str, *, allow_blank_items: bool = False) -> tuple:
    if not isinstance(value, tuple):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a tuple")
    for item in value:
        if not isinstance(item, str) or (not allow_blank_items and not item.strip()):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} contains a blank or non-string item")
    return value


def require_member(value: Any, enum_cls: type, name: str, code: ContractErrorCode) -> Any:
    if not isinstance(value, enum_cls):
        raise ContractError(code, f"{name} must be a {enum_cls.__name__} member, got {value!r}")
    return value


def rfc3339_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def payload(obj: Any, *, exclude: Iterable[str] = ()) -> Any:
    """Render a contract value as a JCS-safe JSON shape."""
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
        out = {}
        for f in dataclasses.fields(obj):
            if f.name in excluded:
                continue
            out[f.name] = payload(getattr(obj, f.name))
        return out
    if isinstance(obj, Mapping):
        return {str(k): payload(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [payload(v) for v in obj]
    raise TypeError(f"unsupported payload type {type(obj).__name__}")


def digest_of(obj: Any, *, exclude: Iterable[str] = (), extra: Mapping[str, Any] | None = None) -> str:
    body = payload(obj, exclude=exclude)
    if extra:
        body = dict(body)
        for k, v in extra.items():
            body[k] = payload(v)
    return canonical_sha256_hex(body)


def settle_digest(obj: Any, field_name: str, computed: str) -> None:
    """Fill or verify a self-digest field on a frozen dataclass.

    An empty string means "compute". A supplied value must equal the computed
    digest exactly; a mismatch is DIGEST_MALFORMED, because a self-digest that
    does not describe its payload is malformed by definition.
    """
    supplied = getattr(obj, field_name)
    if supplied == "":
        object.__setattr__(obj, field_name, computed)
        return
    require_digest(supplied, field_name)
    if supplied != computed:
        raise ContractError(
            ContractErrorCode.DIGEST_MALFORMED,
            f"{field_name} does not match the canonical digest of the payload",
        )


def guard_kwargs(cls: type, forbidden: Sequence[str], code: ContractErrorCode) -> None:
    """Refuse named keyword arguments at construction, after dataclass decoration."""
    original = cls.__init__
    forbidden_set = frozenset(forbidden)

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        bad = sorted(forbidden_set & set(kwargs))
        if bad:
            raise ContractError(code, f"{cls.__name__} does not accept {', '.join(bad)}")
        original(self, *args, **kwargs)

    __init__.__qualname__ = original.__qualname__
    cls.__init__ = __init__  # type: ignore[method-assign]


__all__ = [
    "require_nonblank",
    "require_digest",
    "require_tzaware",
    "require_decimal_string",
    "require_str_tuple",
    "require_member",
    "rfc3339_utc",
    "payload",
    "digest_of",
    "settle_digest",
    "guard_kwargs",
]
