"""Stdlib-only structural validators shared by the trusted-evidence contracts.

Private module — nothing here is part of the curated public API. These are the
fail-closed primitives every contract's ``__post_init__`` is built from, kept in
one place so a rule cannot drift between two contracts.

Two disciplines run through all of them:

* **Never silently normalize an invalid semantic value into an accepted one.** A
  blank identifier is rejected, not defaulted; a padded string is rejected, not
  trimmed; a naive datetime is rejected, not assumed UTC; a duplicate reference
  is rejected, not de-duplicated.
* **Reject duck-typed lookalikes where contract identity matters.** ``bool`` is
  not ``int``; a ``str`` is not a sequence of references; an object that merely
  has the right attribute names is not the contract type.

Canonical strings are *not* stripped
------------------------------------
The merged ``AssessedSystemBinding`` strips and stores the stripped form, so
``" sys-a "`` and ``"sys-a"`` share a digest. These contracts **reject padding
instead**. Stripping is a silent normalization of a value the caller actually
wrote, and ADR §22 requires the digest to be a faithful function of the
committed bytes. Rejecting also keeps a single rule: whatever the caller
supplies is exactly what is digested.

Unicode **NFC is required at construction**, not only at canonicalization. ADR
§22.4 fixes the pattern for naive datetimes: they are rejected "at the boundary
**and again** at canonicalization". A canonical string is the same kind of
coordinate and gets the same two-boundary treatment. Enforcing NFC only in the
encoder would let a non-NFC identifier construct successfully with every
structural invariant apparently satisfied, failing much later when something
finally asked for its bytes — and an object that cannot be canonicalized is not
structurally valid, so it must not exist in the first place. The encoder keeps
its own NFC check as defense in depth, so a value arriving by any other route
still fails closed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from typing import Optional

from .errors import TrustedEvidenceContractError
from .reasons import TrustedEvidenceRefusalReason

__all__ = [
    "require_exact_type",
    "require_canonical_str",
    "require_identifier",
    "require_digest",
    "require_optional_digest",
    "require_aware_datetime",
    "require_optional_aware_datetime",
    "require_strictly_before",
    "normalize_reference_tuple",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _fail(
    message: str, reason: Optional[TrustedEvidenceRefusalReason] = None
) -> TrustedEvidenceContractError:
    error = TrustedEvidenceContractError(message)
    if reason is not None:
        error.reason = reason
    return error


def require_exact_type(value: object, expected: type, name: str) -> None:
    """Reject anything that is not *exactly* ``expected``.

    Uses ``type(value) is expected``, not ``isinstance``, so a **subclass** is
    refused along with a duck-typed lookalike. That is deliberate: ADR §8.1 and
    §26.12 require that a self-consistent forged artifact still fail, and a
    subclass is the cheapest way to smuggle an overridden property past an
    ``isinstance`` check. A contract that must be *this* contract accepts only
    this contract.
    """

    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} "
            f"(got {type(value).__name__}); subclasses and duck-typed "
            "lookalikes are refused because contract identity is load-bearing",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )


def require_canonical_str(value: object, name: str, *, allow_empty: bool) -> str:
    """Require a canonical ``str``: exact type, unpadded, and Unicode NFC.

    ``bool``, every other non-``str``, and every ``str`` **subclass** are
    refused — a subclass could override ``__eq__``, ``__hash__`` or
    ``__str__`` and thereby change what a comparison or a digest sees.

    An all-whitespace value is refused whether or not ``allow_empty`` is set:
    it is padding around nothing, not an explicit absence.

    A non-NFC value is refused here, **at construction**, and again by the
    canonical encoder. Neither boundary normalizes it. Silently folding NFD onto
    NFC would map two structurally different coordinates onto one digest, so a
    digest over one would attest a value nobody wrote; rejecting keeps the digest
    a faithful function of the exact bytes the caller committed to.
    """

    if type(value) is not str:
        raise _fail(
            f"{name} must be a string (got {type(value).__name__}); str "
            "subclasses are refused because a subclass can change what "
            "comparison and canonicalization see",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if value != value.strip():
        raise _fail(
            f"{name} must be a canonical string with no leading or trailing "
            "whitespace; padding is refused, never trimmed, so the digest stays "
            "a faithful function of the exact value supplied",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if unicodedata.normalize("NFC", value) != value:
        raise _fail(
            f"{name} must be Unicode NFC-normalized; a non-canonical string is "
            "refused at construction and never silently normalized, so two "
            "differently-spelled coordinates can never share one digest",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if not value and not allow_empty:
        raise _fail(
            f"{name} must not be empty",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING,
        )
    return value


def require_identifier(value: object, name: str) -> str:
    """Require a non-empty, unpadded canonical identifier string."""

    return require_canonical_str(value, name, allow_empty=False)


def require_digest(value: object, name: str) -> str:
    """Require a bare lowercase 64-char sha-256 hex digest."""

    text = require_canonical_str(value, name, allow_empty=False)
    if not _SHA256_RE.match(text):
        raise _fail(
            f"{name} must be a bare lowercase 64-char sha-256 hex digest",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    return text


def require_optional_digest(value: object, name: str) -> str:
    """Require ``""`` (explicitly absent) or a valid sha-256 hex digest."""

    text = require_canonical_str(value, name, allow_empty=True)
    if text:
        return require_digest(text, name)
    return text


def require_aware_datetime(value: object, name: str) -> datetime:
    """Require a timezone-aware ``datetime``.

    Rejects a naive value rather than assuming UTC for it (ADR §22.4), and
    rejects a ``datetime`` subclass, which could override ``utcoffset`` or
    ``astimezone`` and thereby change what instant the canonical bytes record.
    """

    if type(value) is not datetime:
        raise _fail(
            f"{name} must be exactly a datetime (got {type(value).__name__})",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise _fail(
            f"{name} must be timezone-aware; a value with no offset does not "
            "name an instant and UTC is never guessed for it",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    return value


def require_optional_aware_datetime(value: object, name: str) -> Optional[datetime]:
    """Require ``None`` (explicitly absent) or a timezone-aware ``datetime``.

    ``None`` is a distinct, meaningful value here — an open interval bound, or
    an observation instant rather than a window — and is never conflated with a
    zero/epoch datetime.
    """

    if value is None:
        return None
    return require_aware_datetime(value, name)


def require_strictly_before(
    earlier: datetime, later: datetime, earlier_name: str, later_name: str, rule: str
) -> None:
    """Require ``earlier < later``, rejecting equal and reversed orderings."""

    if not earlier < later:
        raise _fail(
            f"{earlier_name} must strictly precede {later_name} ({rule}); "
            f"an equal or reversed ordering is refused, never reordered"
        )


def normalize_reference_tuple(
    value: object, name: str, *, allow_empty: bool = True
) -> tuple:
    """Normalize an ordered reference sequence into an immutable ``tuple``.

    Order is **preserved**, because order is semantic wherever these contracts
    carry a sequence. A caller-owned ``list`` is defensively copied into a fresh
    tuple, so later mutation of that list cannot reach the frozen contract or
    change its digest — the same defensive-copy discipline ADR §17.7 requires of
    trust-anchor views.

    Scalar substitutes are refused rather than silently iterated: a ``str`` or
    ``bytes`` would decompose into characters/bytes, and a ``Mapping`` would
    contribute only its keys. Blank, non-string and duplicate entries are
    refused, never dropped or coerced.
    """

    if isinstance(value, (str, bytes, bytearray)):
        raise _fail(
            f"{name} must be a sequence of reference strings, not a "
            f"{type(value).__name__}",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if isinstance(value, Mapping):
        raise _fail(
            f"{name} must be an ordered sequence, not a mapping",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    if not isinstance(value, (list, tuple)):
        raise _fail(
            f"{name} must be a list or tuple of reference strings "
            f"(got {type(value).__name__}); an arbitrary iterable is refused "
            "because consuming it could depend on iteration order that is not "
            "part of the contract",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        )
    items = tuple(value)
    if not items and not allow_empty:
        raise _fail(
            f"{name} must not be empty",
            TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING,
        )
    seen: set = set()
    for index, item in enumerate(items):
        text = require_canonical_str(item, f"{name}[{index}]", allow_empty=False)
        if text in seen:
            raise _fail(
                f"{name} contains duplicate reference {text!r}; a chain of "
                "custody may not name the same link twice",
                TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_PROVENANCE_MISMATCH,
            )
        seen.add(text)
    return items
