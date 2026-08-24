"""JCS (RFC 8785) + Action-Profile canonicalizer.

Authority-neutral, standard-library-only canonicalization. This module is the
extracted clean-room implementation formerly resident at
``cer_v0_3/cleanroom/canon.py``: an independent reimplementation written from the
published specification (ACTION_CANONICALIZATION_AND_HASHING_SPEC.md §2, §7),
sharing no code with the reference ActionGate path. Its byte stream is unchanged
by the extraction and is pinned by this package's vector suite and by the
CER V0.3 clean-room suite that consumes it.

Action Profile (as specified):
  * UTF-8 output, no BOM, no insignificant whitespace.
  * Object member names sorted by UTF-16 code-unit order (== UTF-16-BE byte order).
  * JSON string escaping: the seven short escapes plus \\u00XX for other C0 controls;
    all other characters emitted literally (no \\uXXXX expansion of non-ASCII).
  * NO bare JSON numbers in authorization payloads -> reject. Every numeric is a
    typed string upstream.
  * Arrays keep declaration order EXCEPT schema-declared "set" paths, which are
    order-independent (canonical children sorted) and reject duplicate elements.
  * NFC is validated (never rewritten) on schema-declared paths.
  * Duplicate object keys and non-finite floats are rejected.

This module decides nothing. It carries no authority, no policy, and no domain
vocabulary; it maps a parsed JSON value to canonical bytes.

Uses only the Python standard library.
"""
from __future__ import annotations

import hashlib
import unicodedata
from typing import Any, FrozenSet, List, Tuple

from .errors import (
    BareNumberError,
    DuplicateSetElementError,
    NonFiniteNumberError,
    NonNFCError,
    UnsupportedTypeError,
)

_SHORT_ESCAPES = {
    0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r",
    0x22: '\\"', 0x5C: "\\\\",
}


def _emit_string(s: str, path: str, nfc_paths: FrozenSet[str]) -> str:
    if path in nfc_paths and not unicodedata.is_normalized("NFC", s):
        raise NonNFCError(f"string at {path!r} is not NFC-normalized", path=path)
    buf: List[str] = ['"']
    for ch in s:
        code = ord(ch)
        esc = _SHORT_ESCAPES.get(code)
        if esc is not None:
            buf.append(esc)
        elif code < 0x20:
            buf.append("\\u%04x" % code)
        else:
            buf.append(ch)
    buf.append('"')
    return "".join(buf)


def _sort_key(name: str) -> bytes:
    # UTF-16 code-unit order is the big-endian UTF-16 byte order.
    return name.encode("utf-16-be")


def _extend(path: str, key: str) -> str:
    return key if path == "" else f"{path}.{key}"


def _render(value: Any, path: str, set_paths: FrozenSet[str],
            nfc_paths: FrozenSet[str]) -> str:
    # bool must precede int (bool is an int subclass in Python).
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return _emit_string(value, path, nfc_paths)
    if isinstance(value, float):
        # A float here is always a spec violation: numerics must be typed strings.
        if value != value or value in (float("inf"), float("-inf")):
            raise NonFiniteNumberError(f"non-finite number at {path!r}", path=path)
        raise BareNumberError(f"bare float at {path!r}; numerics must be typed strings",
                              path=path)
    if isinstance(value, int):
        raise BareNumberError(f"bare integer at {path!r}; numerics must be typed strings",
                              path=path)
    if isinstance(value, dict):
        members: List[Tuple[bytes, str]] = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise UnsupportedTypeError(f"non-string key at {path!r}", path=path)
            rendered = f"{_emit_string(k, path, nfc_paths)}:" \
                       f"{_render(v, _extend(path, k), set_paths, nfc_paths)}"
            members.append((_sort_key(k), rendered))
        members.sort(key=lambda pair: pair[0])
        return "{" + ",".join(r for _, r in members) + "}"
    if isinstance(value, (list, tuple)):
        child_path = f"{path}[]"
        rendered = [_render(v, child_path, set_paths, nfc_paths) for v in value]
        if path in set_paths:
            if len(set(rendered)) != len(rendered):
                raise DuplicateSetElementError(f"duplicate element in set at {path!r}",
                                               path=path)
            rendered.sort()
        return "[" + ",".join(rendered) + "]"
    raise UnsupportedTypeError(f"unsupported type {type(value).__name__} at {path!r}",
                               path=path)


def canonical_string(value: Any, set_paths: FrozenSet[str] = frozenset(),
                     nfc_paths: FrozenSet[str] = frozenset()) -> str:
    """Canonical JCS+Action-Profile text for an already-parsed value."""
    return _render(value, "", set_paths, nfc_paths)


def canonical_bytes(value: Any, set_paths: FrozenSet[str] = frozenset(),
                    nfc_paths: FrozenSet[str] = frozenset()) -> bytes:
    """Canonical UTF-8 bytes."""
    return canonical_string(value, set_paths, nfc_paths).encode("utf-8")


def canonical_sha256_hex(value: Any, set_paths: FrozenSet[str] = frozenset(),
                         nfc_paths: FrozenSet[str] = frozenset()) -> str:
    """Lowercase 64-character SHA-256 hex digest of ``canonical_bytes(value)``.

    A bare digest of the canonical bytes: no domain tag, no length prefix, no
    envelope framing, and no ``sha256:`` prefix — callers that need one apply it.
    Canonicalization faults propagate unchanged.
    """
    return hashlib.sha256(
        canonical_bytes(value, set_paths, nfc_paths)
    ).hexdigest()
