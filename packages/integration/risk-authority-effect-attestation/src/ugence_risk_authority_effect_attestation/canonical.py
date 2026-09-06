"""Deterministic canonical bytes and digests, and the field disciplines behind them.

One encoder, one digest path. The canonical form of a value is UTF-8 JSON with
sorted keys, no insignificant whitespace, non-ASCII preserved, ``None`` as
``null``, booleans as booleans, enums by ``.value``, timezone-aware instants
rendered in UTC as ``%Y-%m-%dT%H:%M:%S.%fZ``, mappings with **string** keys and
**string** values only, and nothing else: a float, a ``bytes`` value, a set, a
naive datetime, a non-NFC string or a ``str`` subclass is refused rather than
coerced, because a coerced value is a value nobody checked that then gets
signed.

The signing frame domain-separates the payload **outside** the JSON as well as
inside it: ``uint32_be(len(domain)) || domain || canonical_json``. The domain is
also a JSON field, so a payload lifted out of its frame still names what it
was signed for.

Digests are ``sha256:`` followed by exactly 64 lowercase hex characters, the
Risk Authority spelling RA-8's records already use. A second spelling is a
refusal, never a repair.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Mapping

from .errors import EffectAttestationContractError as _Error

__all__ = [
    "DIGEST_PREFIX",
    "to_canonical_obj",
    "canonical_bytes",
    "canonical_digest",
    "framed_signing_bytes",
    "is_canonical_digest",
    "require_canonical_digest",
    "require_nfc_text",
    "require_canonical_identifier",
    "require_aware_utc",
    "require_exact_type",
    "require_string_mapping",
]

DIGEST_PREFIX: Final[str] = "sha256:"
_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP_FMT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"
_LENGTH_PREFIX_BYTES: Final[int] = 4


def require_exact_type(name: str, value: Any, expected: type) -> Any:
    """``type(value) is expected`` — never ``isinstance``.

    A subclass can override ``__eq__``, ``__hash__`` or any property this
    package reads, so admitting one is admitting arbitrary behaviour wearing a
    trusted name.
    """

    if type(value) is not expected:
        raise _Error(
            f"{name} must be exactly {expected.__name__} (got "
            f"{type(value).__name__}); subclasses, duck-typed look-alikes and "
            "fabricated instances are refused, not adapted"
        )
    return value


def require_nfc_text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    """Exact ``str``, NFC, optionally non-empty. Non-NFC text is refused, never
    normalized: normalizing would sign a spelling nobody checked."""

    if type(value) is not str:
        raise _Error(
            f"{name} must be exactly a str (got {type(value).__name__}); a str "
            "subclass may override comparison and is refused"
        )
    if not allow_empty and value == "":
        raise _Error(f"{name} is required and must not be empty")
    if unicodedata.normalize("NFC", value) != value:
        raise _Error(f"{name} must be NFC-normalized; it is rejected rather than normalized")
    return value


def require_canonical_identifier(name: str, value: Any) -> str:
    """A non-empty NFC identifier with no surrounding or control whitespace."""

    text = require_nfc_text(name, value)
    if text != text.strip():
        raise _Error(f"{name} must not carry leading or trailing whitespace")
    if any(ch.isspace() and ch != " " for ch in text):
        raise _Error(f"{name} must not contain control whitespace")
    return text


def require_aware_utc(name: str, value: Any) -> datetime:
    """A timezone-aware exact ``datetime``, normalized to UTC. A naive instant is
    refused rather than assumed UTC; this package reads no clock."""

    if type(value) is not datetime:
        raise _Error(f"{name} must be exactly a datetime (got {type(value).__name__})")
    if value.tzinfo is None or value.utcoffset() is None:
        raise _Error(f"{name} must be timezone-aware; a naive datetime is refused")
    return value.astimezone(timezone.utc)


def require_string_mapping(name: str, value: Any) -> dict:
    """A mapping with exact-``str`` NFC keys and values, copied into a plain dict.

    This is the discipline ``ExecutionObservation.observed_parameters`` is
    declared with (``Mapping[str, str]``) and never enforces. It is enforced
    here because the parameters are signed: a non-string value would have to
    be *rendered* to sign it, and a rendering is an interpretation the wrapper
    is forbidden to add (SE-3).
    """

    if not isinstance(value, Mapping):
        raise _Error(f"{name} must be a mapping (got {type(value).__name__})")
    out: dict = {}
    for key, item in value.items():
        k = require_nfc_text(f"{name} key", key)
        v = require_nfc_text(f"{name}[{k!r}]", item, allow_empty=True)
        out[k] = v
    return out


def to_canonical_obj(value: Any) -> Any:
    """Project ``value`` onto the closed canonical JSON model, or refuse."""

    if value is None or type(value) is bool or type(value) is int:
        return value
    if type(value) is str:
        return require_nfc_text("canonical string", value, allow_empty=True)
    if isinstance(value, Enum):
        return to_canonical_obj(value.value)
    if type(value) is datetime:
        return require_aware_utc("canonical datetime", value).strftime(_TIMESTAMP_FMT)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_canonical_obj(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        out = {}
        for key, item in value.items():
            k = require_nfc_text("canonical mapping key", key)
            out[k] = to_canonical_obj(item)
        return out
    if type(value) in (list, tuple):
        return [to_canonical_obj(item) for item in value]
    raise _Error(
        f"no canonical form exists for {type(value).__name__}; floats, bytes, "
        "sets, naive datetimes and arbitrary objects are refused rather than rendered"
    )


def canonical_bytes(value: Any) -> bytes:
    """The one canonical byte encoding of ``value``."""

    return json.dumps(
        to_canonical_obj(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    """``sha256:`` + hex over :func:`canonical_bytes`."""

    return DIGEST_PREFIX + hashlib.sha256(canonical_bytes(value)).hexdigest()


def framed_signing_bytes(domain: str, value: Any) -> bytes:
    """``uint32_be(len(domain)) || domain || canonical_bytes(value)``."""

    tag = require_canonical_identifier("signing domain", domain).encode("utf-8")
    return len(tag).to_bytes(_LENGTH_PREFIX_BYTES, "big") + tag + canonical_bytes(value)


def is_canonical_digest(value: Any) -> bool:
    return type(value) is str and _DIGEST_RE.match(value) is not None


def require_canonical_digest(name: str, value: Any) -> str:
    if not is_canonical_digest(value):
        raise _Error(
            f"{name} must be a canonical {DIGEST_PREFIX}<64 lowercase hex> digest "
            f"(got {value!r}); a bare-hex or uppercase spelling is refused"
        )
    return value
