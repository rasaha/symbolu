"""Canonicalization and digests — Risk Authority's scheme, reached only through its API.

Phase 5B-0A introduces **no new canonicalization scheme**. Every byte this package signs
and every digest it emits flows through ``risk_authority.crypto.canonical`` and
``risk_authority.crypto.hashing``, both reached through their public ``__all__``. There is
no local JSON encoder, no ``sort_keys=True`` call, no ``hashlib`` use, no second digest
prefix and no alternate digest path anywhere in this distribution.

**What was deliberately not reused.** The Trusted Evidence Authority carries its signed
bytes in a length-prefixed frame with its own domain tags. Those are TEV's evidence and
receipt framings, and adopting them here would put a third framing convention into the
Cloud Scaling chain — Phase 4C, Phase 5A and this package would then disagree about what
"the canonical bytes" means. TEV's **trust primitives** are payload-neutral and are reused
in full (see :mod:`.trust`); TEV's **evidence framing** is not, and no evidence-specific
verifier is treated as if it had verified this non-evidence payload.

Domain separation is therefore carried where Phase 5A already carries it: inside the
signed bytes, as the schema tag and the dedicated signing purpose, both bound as ordinary
canonical fields. See :mod:`.identifiers`.

Digest format is enforced, not assumed: ``sha256:`` followed by exactly 64 lowercase hex
characters. A bare-hex digest, an uppercase digest and a second spelling of one digest are
all rejections, never repairs.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Final

from risk_authority.crypto.canonical import canonical_bytes as _ra_canonical_bytes
from risk_authority.crypto.canonical import to_canonical_obj as _ra_to_canonical_obj
from risk_authority.crypto.hashing import DIGEST_PREFIX
from risk_authority.crypto.hashing import digest as _ra_digest

from .errors import ProducerAttestationCanonicalFieldError as _FieldError
from .errors import ProducerAttestationExactTypeError as _ExactTypeError

__all__ = [
    "DIGEST_PREFIX",
    "canonical_bytes",
    "canonical_digest",
    "to_canonical_obj",
    "is_canonical_digest",
    "require_canonical_digest",
    "require_nfc_text",
    "require_canonical_identifier",
    "require_aware_utc",
    "require_exact_type",
]

#: ``sha256:`` followed by exactly 64 lowercase hexadecimal characters.
_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")


def to_canonical_obj(value: Any) -> Any:
    """Risk Authority's canonical projection of ``value``. No local re-implementation."""

    return _ra_to_canonical_obj(value)


def canonical_bytes(value: Any) -> bytes:
    """The exact UTF-8 byte stream a producer signs, under Risk Authority's scheme."""

    return _ra_canonical_bytes(value)


def canonical_digest(value: Any) -> str:
    """The ``sha256:``-prefixed digest of ``value``'s canonical form."""

    return _ra_digest(value)


def is_canonical_digest(value: Any) -> bool:
    """True only for ``sha256:<64 lowercase hex>``."""

    return isinstance(value, str) and _DIGEST_RE.match(value) is not None


def require_canonical_digest(name: str, value: Any) -> str:
    """Return ``value`` if it is a canonical digest string; otherwise refuse."""

    if not is_canonical_digest(value):
        raise _FieldError(
            f"{name} must be a canonical {DIGEST_PREFIX}<64 lowercase hex> digest "
            f"(got {value!r}); a bare-hex or uppercase spelling is refused rather than "
            "normalized, because two spellings of one digest defeat equality"
        )
    return value


def require_nfc_text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    """Return ``value`` if it is NFC-normalized text; otherwise refuse.

    Non-NFC text is **rejected, never normalized**. Normalizing would silently accept two
    distinct byte sequences as one identity and then freeze the substitution into signed
    bytes — the signature would cover a spelling nobody checked.
    """

    if type(value) is not str:
        raise _FieldError(
            f"{name} must be exactly a str (got {type(value).__name__}); a str subclass "
            "may override comparison and is refused"
        )
    if not allow_empty and value == "":
        raise _FieldError(f"{name} is required and must not be empty")
    if unicodedata.normalize("NFC", value) != value:
        raise _FieldError(
            f"{name} must be NFC-normalized; a non-NFC identifier is rejected rather "
            "than normalized"
        )
    return value


def require_canonical_identifier(name: str, value: Any) -> str:
    """An NFC, non-empty identifier with no surrounding or control whitespace."""

    text = require_nfc_text(name, value)
    if text != text.strip():
        raise _FieldError(f"{name} must not carry leading or trailing whitespace")
    if any(ch.isspace() and ch != " " for ch in text):
        raise _FieldError(f"{name} must not contain control whitespace")
    return text


def require_aware_utc(name: str, value: Any) -> datetime:
    """Return ``value`` normalized to UTC if it is a timezone-aware ``datetime``.

    A naive datetime is **refused, never assumed UTC**. This package reads no clock; every
    instant it handles is one a caller injected, and an instant whose offset nobody stated
    is an instant nobody can reconstruct.
    """

    if type(value) is not datetime:
        raise _FieldError(
            f"{name} must be exactly a datetime (got {type(value).__name__})"
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise _FieldError(
            f"{name} must be timezone-aware; a naive datetime is refused rather than "
            "assumed UTC"
        )
    return value.astimezone(timezone.utc)


def require_exact_type(name: str, value: Any, expected: type) -> Any:
    """Return ``value`` only when ``type(value) is expected``.

    ``isinstance`` is deliberately not used. A subclass can override ``__eq__``,
    ``__hash__`` and any property this package reads, so an ``isinstance`` admission is an
    admission of arbitrary behaviour wearing a trusted name.
    """

    if type(value) is not expected:
        raise _ExactTypeError(
            f"{name} must be exactly {expected.__name__} (got "
            f"{type(value).__name__}); subclasses, duck-typed look-alikes and "
            "fabricated instances are refused, not adapted"
        )
    return value
