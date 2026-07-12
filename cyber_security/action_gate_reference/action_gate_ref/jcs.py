"""RFC 8785 (JCS) canonicalization + the frozen Action Profile.

Action Profile (ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §2):
  * UTF-8, no BOM; object keys sorted by UTF-16 code unit; arrays ordered
    (except schema-declared set paths); no whitespace; JCS string escaping.
  * NO bare JSON numbers in authorization payloads -> E_BARE_NUMBER. All
    numerics are typed strings.
  * NO Unicode normalization at hash time; NFC is validated (not rewritten)
    for schema-declared nfc paths -> E_NON_NFC.
  * Duplicate keys, NaN/Infinity, invalid UTF-8 -> hard errors.

Fail closed on ambiguity. Cryptography is not implemented here.
"""

from __future__ import annotations

import json
import unicodedata
from typing import Any, FrozenSet

from .errors import (
    BareNumberError,
    DuplicateKeyError,
    InvalidUTF8Error,
    NanInfError,
    NonNFCError,
)


def _reject_constant(_c: str):
    raise NanInfError(f"non-finite constant {_c!r}")


def _pairs_hook(pairs):
    d: dict = {}
    for k, v in pairs:
        if k in d:
            raise DuplicateKeyError(f"duplicate key {k!r}")
        d[k] = v
    return d


def load_strict(data) -> Any:
    """Parse JSON rejecting duplicate keys, NaN/Infinity, invalid UTF-8.

    Numbers are parsed (int/float) but rejected later at canonicalization
    (E_BARE_NUMBER) wherever they occur.
    """
    if isinstance(data, (bytes, bytearray)):
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidUTF8Error(str(exc)) from exc
    else:
        text = data
    return json.loads(text, object_pairs_hook=_pairs_hook, parse_constant=_reject_constant)


def _escape_string(s: str) -> str:
    out = ['"']
    for ch in s:
        cp = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif cp == 0x08:
            out.append("\\b")
        elif cp == 0x09:
            out.append("\\t")
        elif cp == 0x0A:
            out.append("\\n")
        elif cp == 0x0C:
            out.append("\\f")
        elif cp == 0x0D:
            out.append("\\r")
        elif cp < 0x20:
            out.append("\\u%04x" % cp)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _utf16_key(k: str) -> bytes:
    # UTF-16-BE byte order == UTF-16 code-unit ordering (JCS key sort).
    return k.encode("utf-16-be")


def _child_path(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _canon(value: Any, path: str, set_paths: FrozenSet[str], nfc_paths: FrozenSet[str]) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        if path in nfc_paths and not unicodedata.is_normalized("NFC", value):
            raise NonNFCError(f"string at {path!r} is not NFC-normalized", field=path)
        return _escape_string(value)
    if isinstance(value, (int, float)):
        # Action Profile: no bare JSON numbers in canonicalized payloads.
        raise BareNumberError(f"bare numeric value at {path!r}; numerics must be typed strings",
                              field=path)
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: _utf16_key(kv[0]))
        parts = [f"{_escape_string(k)}:{_canon(v, _child_path(path, k), set_paths, nfc_paths)}"
                 for k, v in items]
        return "{" + ",".join(parts) + "}"
    if isinstance(value, (list, tuple)):
        rendered = [_canon(v, f"{path}[]", set_paths, nfc_paths) for v in value]
        if path in set_paths:
            # schema-declared set: order-independent, duplicates rejected
            if len(set(rendered)) != len(rendered):
                raise DuplicateKeyError(f"duplicate element in set at {path!r}", field=path)
            rendered = sorted(rendered)
        return "[" + ",".join(rendered) + "]"
    raise BareNumberError(f"unsupported value type {type(value).__name__} at {path!r}", field=path)


def canonicalize_str(
    value: Any,
    set_paths: FrozenSet[str] = frozenset(),
    nfc_paths: FrozenSet[str] = frozenset(),
) -> str:
    """Return the canonical JCS+Profile string for an already-parsed value."""
    return _canon(value, "", set_paths, nfc_paths)


def canonicalize(
    value: Any,
    set_paths: FrozenSet[str] = frozenset(),
    nfc_paths: FrozenSet[str] = frozenset(),
) -> bytes:
    """Return canonical UTF-8 bytes."""
    return canonicalize_str(value, set_paths, nfc_paths).encode("utf-8")
