"""Canonicalization and digests — the Policy Authority's scheme, reached only through its API.

Phase 5B-0B introduces **no new canonicalization scheme**. Every byte this package digests
flows through ``ugence_policy_authority.api.canonical_bytes`` and ``sha256_hex``. There is
no local JSON encoder, no ``sort_keys=True`` call, no ``hashlib`` use and no second digest
path in this distribution.

Why the Policy Authority's encoder and not Risk Authority's
------------------------------------------------------------
Phase 5B-0A digests its artifacts under Risk Authority's scheme, because the facts it binds
come from the Phase 5A candidate, which is canonicalized that way. The facts this package
binds come from a Policy Authority resolution: a coordinate, a framed body digest, an
issuing authority and a key. Digesting them under a *different* encoder than the authority
that produced them would mean this package and the authority disagree about what "the
canonical bytes" of a coordinate are — and the Policy Authority's encoder is additionally
the stricter of the two, since it *rejects* non-NFC input where Risk Authority's accepts it.

The cost is stated rather than hidden: this package therefore carries digests from **two
namespaces**, and the two are never mixed.

Two digest namespaces, and the predicate for each
--------------------------------------------------
* **Policy Authority digests** — bare lowercase 64-hex, deliberately without a prefix.
  ``policy_body_digest``, ``coordinate.content_digest``, and every digest this package
  computes. Validated by :func:`require_policy_digest`.
* **Phase 5A digests** — ``sha256:`` followed by 64 lowercase hex. The candidate digest, and
  nothing else here. Validated by :func:`require_phase5a_digest`.

D-5B0B-2 measured that a Policy Authority digest cannot be placed in Phase 5A's
``policy_artifact_digest`` field at all, because that field requires the prefix. This module
makes that incompatibility executable in both directions: :func:`is_policy_digest` is
``False`` for a prefixed digest and :func:`is_phase5a_digest` is ``False`` for a bare one.
Neither function converts, and there is deliberately no function that does — a re-prefixed
digest is a digest nobody signed, over a frame nobody hashed.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Final

from ugence_policy_authority.api import (
    CANONICALIZATION_VERSION,
    canonical_bytes as _pa_canonical_bytes,
    sha256_hex as _pa_sha256_hex,
)

from .errors import PolicyAuthenticityExactTypeError as _ExactTypeError
from .errors import PolicyAuthenticityFieldError as _FieldError

__all__ = [
    "CANONICALIZATION_VERSION",
    "canonical_bytes",
    "framed_digest",
    "is_policy_digest",
    "require_policy_digest",
    "is_phase5a_digest",
    "require_phase5a_digest",
    "require_nfc_text",
    "require_canonical_identifier",
    "require_aware_utc",
    "require_exact_type",
]

#: Exactly 64 lowercase hexadecimal characters, with no prefix. The Policy Authority shape.
_POLICY_DIGEST_RE: Final[re.Pattern] = re.compile(r"^[0-9a-f]{64}$")

#: ``sha256:`` followed by exactly 64 lowercase hexadecimal characters. The Phase 5A shape.
_PHASE_5A_DIGEST_RE: Final[re.Pattern] = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    """The canonical UTF-8 byte stream for ``value``, under the Policy Authority's scheme."""

    return _pa_canonical_bytes(value)


def framed_digest(*, domain: str, body: Any) -> str:
    """Digest ``body`` inside an explicit, versioned frame. Returns bare 64-hex.

    The frame binds the canonicalization version and a domain tag as ordinary canonical
    fields, mirroring the Policy Authority's own ``framed_body_digest``. Two different
    domains can therefore never produce identical bytes for identical bodies, so this
    package's artifact digests can never be read as policy-body digests.
    """

    if type(domain) is not str or not domain:
        raise _FieldError("framed_digest(domain) must be a non-empty str")
    return _pa_sha256_hex(
        canonical_bytes(
            {
                "canonicalization": CANONICALIZATION_VERSION,
                "domain": domain,
                "body": body,
            }
        )
    )


def is_policy_digest(value: Any) -> bool:
    """True only for a bare lowercase 64-hex digest — the Policy Authority's shape."""

    return type(value) is str and _POLICY_DIGEST_RE.match(value) is not None


def require_policy_digest(name: str, value: Any) -> str:
    """Return ``value`` if it is a bare lowercase 64-hex digest; otherwise refuse."""

    if not is_policy_digest(value):
        raise _FieldError(
            f"{name} must be a bare lowercase 64-hex Policy Authority digest (got "
            f"{value!r}); a 'sha256:'-prefixed or uppercase spelling is refused rather "
            "than converted, because two spellings of one digest defeat equality and a "
            "re-prefixed digest is a digest nobody hashed"
        )
    return value


def is_phase5a_digest(value: Any) -> bool:
    """True only for ``sha256:<64 lowercase hex>`` — the Phase 5A shape."""

    return type(value) is str and _PHASE_5A_DIGEST_RE.match(value) is not None


def require_phase5a_digest(name: str, value: Any) -> str:
    """Return ``value`` if it is a canonical Phase 5A digest; otherwise refuse."""

    if not is_phase5a_digest(value):
        raise _FieldError(
            f"{name} must be a canonical Phase 5A 'sha256:<64 lowercase hex>' digest "
            f"(got {value!r})"
        )
    return value


def require_nfc_text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    """Return ``value`` if it is NFC-normalized text; otherwise refuse.

    Non-NFC text is **rejected, never normalized** — the same posture the Policy Authority
    holds at its own boundary. Normalizing would silently accept two distinct byte sequences
    as one identity.
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
            f"{name} must be NFC-normalized; a non-NFC identifier is rejected rather than "
            "normalized"
        )
    return value


def require_canonical_identifier(name: str, value: Any, *, allow_empty: bool = False) -> str:
    """An NFC identifier with no surrounding or control whitespace.

    ``allow_empty`` exists for exactly one field: the tenant component of a ``GLOBAL``-scope
    coordinate is the canonical empty string, not a missing value.
    """

    text = require_nfc_text(name, value, allow_empty=allow_empty)
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
        raise _FieldError(f"{name} must be exactly a datetime (got {type(value).__name__})")
    if value.tzinfo is None or value.utcoffset() is None:
        raise _FieldError(
            f"{name} must be timezone-aware; a naive datetime is refused rather than "
            "assumed UTC"
        )
    return value.astimezone(timezone.utc)


def require_exact_type(name: str, value: Any, expected: type) -> Any:
    """Return ``value`` only when ``type(value) is expected``.

    ``isinstance`` is deliberately not used. A subclass can override ``__eq__``, ``__hash__``
    and any property this package reads, so an ``isinstance`` admission is an admission of
    arbitrary behaviour wearing a trusted name.
    """

    if type(value) is not expected:
        raise _ExactTypeError(
            f"{name} must be exactly {expected.__name__} (got {type(value).__name__}); "
            "subclasses, duck-typed look-alikes and fabricated instances are refused, not "
            "adapted"
        )
    return value
