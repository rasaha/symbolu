"""Canonicalization and digests — Risk Authority's scheme, reached only through its API.

Phase 5A introduces **no fourth canonicalization scheme**. Every digest this package
emits is ``risk_authority.crypto.hashing.digest`` over
``risk_authority.crypto.canonical.to_canonical_obj``, both of which are public exports of
their modules' ``__all__``. There is no local JSON encoder, no ``sort_keys=True`` call, no
``hashlib`` use and no alternate digest path anywhere in this distribution.

This matters most for the **decision snapshot**. Risk Authority binds
``decision_digest == digest(to_canonical_obj(decision_snapshot))`` inside a private
``SubjectRiskDecision._bind``. Phase 5A does not call that private method and does not
re-implement its logic from guesswork: it recomputes the same equality from the two
*public* primitives the private method itself is built from. The check is therefore an
independent recomputation over the published canonicalization contract, not a copy of a
private internal — and if Risk Authority ever changed that contract, this package's own
frozen digests would move and its suite would fail rather than silently disagree.

Digest format is enforced, not assumed: every value that leaves this package is
``sha256:`` + 64 lowercase hex characters. A bare-hex digest is a rejection.
"""

from __future__ import annotations

import re
from typing import Any, Final, Mapping

from risk_authority.crypto.canonical import to_canonical_obj
from risk_authority.crypto.hashing import DIGEST_PREFIX
from risk_authority.crypto.hashing import digest as _ra_digest

from .errors import (
    AuthorizationCandidateRejectionReason as _Reason,
)
from .errors import (
    CanonicalFieldError,
)

__all__ = [
    "DIGEST_PREFIX",
    "canonical_digest",
    "digest_of_snapshot",
    "is_canonical_digest",
    "require_canonical_digest",
    "require_canonical_identifier",
    "require_nfc_text",
]

#: ``sha256:`` followed by exactly 64 lowercase hexadecimal characters. Uppercase hex is
#: refused rather than lowercased: two spellings of one digest would defeat equality.
_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_digest(value: Any) -> str:
    """The ``sha256:``-prefixed digest of ``value`` under Risk Authority's scheme."""

    return _ra_digest(value)


def digest_of_snapshot(snapshot: Mapping[str, Any]) -> str:
    """Recompute ``digest(to_canonical_obj(snapshot))`` from the public RA primitives.

    This is the independent revalidation of a Risk Authority snapshot/digest pair. It
    reaches no private symbol; see this module's docstring for why that is sufficient.
    """

    if not isinstance(snapshot, Mapping):
        raise CanonicalFieldError(
            "a canonical snapshot must be a mapping", _Reason.MALFORMED_CANONICAL_FIELD
        )
    return _ra_digest(to_canonical_obj(snapshot))


def is_canonical_digest(value: Any) -> bool:
    """True only for ``sha256:<64 lowercase hex>``."""

    return isinstance(value, str) and _DIGEST_RE.match(value) is not None


def require_canonical_digest(name: str, value: Any) -> str:
    """Return ``value`` if it is a canonical digest string; otherwise reject."""

    if not is_canonical_digest(value):
        raise CanonicalFieldError(
            f"{name} must be a canonical {DIGEST_PREFIX}<64 lowercase hex> digest "
            f"(got {value!r})",
            _Reason.MALFORMED_CANONICAL_FIELD,
        )
    return value


def require_nfc_text(name: str, value: Any, *, allow_empty: bool = False) -> str:
    """Return ``value`` if it is NFC-normalized text; otherwise reject.

    Non-NFC text is **rejected, never normalized**. Normalizing would silently accept two
    distinct byte sequences as one identity and freeze the substitution into a digest.
    """

    import unicodedata

    if not isinstance(value, str):
        raise CanonicalFieldError(
            f"{name} must be a string (got {type(value).__name__})",
            _Reason.MALFORMED_CANONICAL_FIELD,
        )
    if not allow_empty and value == "":
        raise CanonicalFieldError(
            f"{name} is required and must not be empty", _Reason.MALFORMED_CANONICAL_FIELD
        )
    if unicodedata.normalize("NFC", value) != value:
        raise CanonicalFieldError(
            f"{name} must be NFC-normalized; a non-NFC identifier is rejected rather "
            "than normalized",
            _Reason.NON_CANONICAL_IDENTIFIER,
        )
    return value


def require_canonical_identifier(name: str, value: Any) -> str:
    """An NFC, non-empty identifier with no leading/trailing or embedded control space."""

    text = require_nfc_text(name, value)
    if text != text.strip():
        raise CanonicalFieldError(
            f"{name} must not carry leading or trailing whitespace",
            _Reason.NON_CANONICAL_IDENTIFIER,
        )
    if any(ch.isspace() and ch != " " for ch in text):
        raise CanonicalFieldError(
            f"{name} must not contain control whitespace", _Reason.NON_CANONICAL_IDENTIFIER
        )
    return text
