"""Stdlib-only structural validators shared by the benchmark contracts.

Private module — nothing here is part of the curated public API. These are the
fail-closed primitives every contract's ``__post_init__`` is built from, kept in
one place so a rule cannot drift between two contracts.

Three disciplines run through all of them:

* **Never silently normalize an invalid semantic value into an accepted one.** A
  blank identifier is rejected, not defaulted; a padded string is rejected, not
  trimmed; a naive datetime is rejected, not assumed UTC; a duplicate reference
  is rejected, not de-duplicated.
* **Reject duck-typed lookalikes where contract identity matters.** ``bool`` is
  not ``int``; a ``str`` is not a sequence of references; an object that merely
  has the right attribute names is not the contract type.
* **Make an inexact coordinate unrepresentable, not merely discouraged.** ADR
  B-8 requires exactly that of floating benchmark references, so the check lives
  at construction, in the type, rather than in a resolver that a caller could
  bypass.

Canonical strings are *not* stripped
------------------------------------
These contracts **reject padding** rather than trimming it. Stripping is a silent
normalization of a value the caller actually wrote, and ADR §22 requires the
digest to be a faithful function of the committed bytes. Rejecting also keeps a
single rule: whatever the caller supplies is exactly what is digested.

Unicode **NFC is required at construction**, not only at canonicalization. ADR
§22.4 fixes the pattern for naive datetimes: they are rejected "at the boundary
**and again** at canonicalization". A canonical string is the same kind of
coordinate and gets the same two-boundary treatment. An object that cannot be
canonicalized is not structurally valid, so it must not exist in the first place;
the encoder keeps its own NFC check as defence in depth, so a value arriving by
any other route still fails closed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime
from typing import Optional

from .errors import BenchmarkContractError
from .reasons import BenchmarkRefusalReason

__all__ = [
    "require_exact_type",
    "require_canonical_str",
    "require_identifier",
    "require_exact_coordinate_token",
    "require_exact_semantic_version",
    "require_digest",
    "require_aware_datetime",
    "require_optional_aware_datetime",
    "require_strictly_before",
    "normalize_unordered_reference_tuple",
]

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Semantic Versioning 2.0.0, anchored, in its published form.
#:
#: ADR §15 row 3 names the coordinate a **semantic version**, so an exact
#: ``MAJOR.MINOR.PATCH`` (with optional pre-release and build metadata) is what
#: the coordinate admits. Requiring the full grammar is what makes a *range*
#: structurally unrepresentable: ``^1.2``, ``1.x``, ``>=2.0``, ``1.2.3 - 1.4.0``
#: and ``1.2 || 1.3`` all fail to parse, so B-8's "a floating reference must be
#: *unrepresentable*" holds in the type rather than in prose. Leading zeroes in
#: numeric identifiers are rejected by the published grammar itself, so ``1.02.0``
#: and ``1.2.0`` cannot both name one version.
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

#: Tokens that name a *moving* target rather than an exact one.
#:
#: ADR §17.2 forbids ``latest()``, ``current()`` and newest-version fallback on
#: the trusted path and requires a floating reference to be unrepresentable;
#: B-8 forbids "floating ``latest``, implicit version selection, and
#: string-parsed successor guesses". Compared case-insensitively, because
#: ``Latest`` names the same non-existent thing as ``latest``.
_FLOATING_TOKENS = frozenset(
    {
        "latest",
        "current",
        "newest",
        "head",
        "tip",
        "any",
        "default",
        "active",
        "stable",
        "*",
        "-",
        "?",
    }
)

#: Characters that express a wildcard, a range or a boolean version expression.
#:
#: Refused anywhere in an exact coordinate token. A coordinate carrying one is
#: not a coordinate — it is a query, and §17.1 admits "exact-coordinate lookup
#: only".
_INEXACT_CHARS = ("*", "?", "%", "^", "~", ">", "<", "|", ",", "[", "]", "{", "}")


def _fail(
    message: str, reason: Optional[BenchmarkRefusalReason] = None
) -> BenchmarkContractError:
    error = BenchmarkContractError(message)
    if reason is not None:
        error.reason = reason
    return error


def require_exact_type(value: object, expected: type, name: str) -> None:
    """Reject anything that is not *exactly* ``expected``.

    Uses ``type(value) is expected``, not ``isinstance``, so a **subclass** is
    refused along with a duck-typed lookalike. That is deliberate: ADR §26
    requires that a self-consistent forged artifact still fail, and a subclass is
    the cheapest way to smuggle an overridden property past an ``isinstance``
    check. A contract that must be *this* contract accepts only this contract.
    """

    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} "
            f"(got {type(value).__name__}); subclasses and duck-typed "
            "lookalikes are refused because contract identity is load-bearing",
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )


def require_canonical_str(value: object, name: str, *, allow_empty: bool) -> str:
    """Require a canonical ``str``: exact type, unpadded, and Unicode NFC.

    ``bool``, every other non-``str``, and every ``str`` **subclass** are
    refused — a subclass could override ``__eq__``, ``__hash__`` or ``__str__``
    and thereby change what a comparison or a digest sees.

    An all-whitespace value is refused whether or not ``allow_empty`` is set:
    it is padding around nothing, not an explicit absence.

    A non-NFC value is refused here, **at construction**, and again by the
    canonical encoder. Neither boundary normalizes it.
    """

    if type(value) is not str:
        raise _fail(
            f"{name} must be a string (got {type(value).__name__}); str "
            "subclasses are refused because a subclass can change what "
            "comparison and canonicalization see",
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )
    if value != value.strip():
        raise _fail(
            f"{name} must be a canonical string with no leading or trailing "
            "whitespace; padding is refused, never trimmed, so the digest stays "
            "a faithful function of the exact value supplied",
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )
    if unicodedata.normalize("NFC", value) != value:
        raise _fail(
            f"{name} must be Unicode NFC-normalized; a non-canonical string is "
            "refused at construction and never silently normalized, so two "
            "differently-spelled coordinates can never share one digest",
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )
    if not value and not allow_empty:
        raise _fail(
            f"{name} must not be empty",
            BenchmarkRefusalReason.BENCHMARK_IDENTITY_COORDINATE_MISSING,
        )
    return value


def require_identifier(value: object, name: str) -> str:
    """Require a non-empty, unpadded canonical identifier string."""

    return require_canonical_str(value, name, allow_empty=False)


def require_exact_coordinate_token(value: object, name: str) -> str:
    """Require an identifier that names **one** thing, exactly (ADR B-8, §17.1).

    On top of :func:`require_identifier`, refuses:

    * a floating token — ``latest``, ``current``, ``newest``, ``head``, ``tip``,
      ``any``, ``default``, ``active``, ``stable``, ``*``, ``-``, ``?`` — in any
      letter case, because §17.2 requires the floating reference to be
      *unrepresentable* rather than merely discouraged;
    * any wildcard, range or boolean-expression character anywhere in the value,
      because such a value is a query rather than a coordinate.

    The raised reason is ``BENCHMARK_COORDINATE_NOT_EXACT``, which is a different
    fault from a missing coordinate: something *was* supplied, and what it names
    is a moving target.
    """

    text = require_identifier(value, name)
    if text.casefold() in _FLOATING_TOKENS:
        raise _fail(
            f"{name} must name one exact benchmark coordinate; {text!r} is a "
            "floating reference. ADR B-8 and §17.2 require latest/current/"
            "newest selection to be unrepresentable on the trusted path, not "
            "merely discouraged",
            BenchmarkRefusalReason.BENCHMARK_COORDINATE_NOT_EXACT,
        )
    for char in _INEXACT_CHARS:
        if char in text:
            raise _fail(
                f"{name} must be an exact coordinate; {text!r} contains "
                f"{char!r}, which expresses a wildcard, a range or a version "
                "expression. §17.1 admits exact-coordinate lookup only, so a "
                "query is not a representable coordinate",
                BenchmarkRefusalReason.BENCHMARK_COORDINATE_NOT_EXACT,
            )
    return text


def require_exact_semantic_version(value: object, name: str) -> str:
    """Require an exact Semantic Versioning 2.0.0 string (ADR §15 row 3).

    Runs :func:`require_exact_coordinate_token` first, so a floating token gets
    the floating-token message rather than a grammar complaint, then requires the
    published semver grammar. A range, a partial version (``1.2``), a wildcard
    (``1.2.x``), a comparator (``>=1.2.3``) and a leading-zero spelling
    (``1.02.0``) are all refused — each of them either names more than one
    version or gives one version two spellings, and B-8 admits neither.
    """

    text = require_exact_coordinate_token(value, name)
    if not _SEMVER_RE.match(text):
        raise _fail(
            f"{name} must be an exact Semantic Versioning 2.0.0 string "
            f"(got {text!r}); ADR §15 row 3 names the coordinate a semantic "
            "version, and a partial version, range or comparator names more "
            "than one version",
            BenchmarkRefusalReason.BENCHMARK_COORDINATE_NOT_EXACT,
        )
    return text


def require_digest(
    value: object,
    name: str,
    *,
    reason: BenchmarkRefusalReason = (
        BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT
    ),
) -> str:
    """Require a bare lowercase 64-char sha-256 hex digest.

    One spelling only: uppercase hex, a ``0x`` prefix, padding and any other
    length are refused rather than normalized, so one digest value has exactly
    one representation in a canonical byte sequence.
    """

    text = require_canonical_str(value, name, allow_empty=False)
    if not _SHA256_RE.match(text):
        raise _fail(
            f"{name} must be a bare lowercase 64-char sha-256 hex digest",
            reason,
        )
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
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise _fail(
            f"{name} must be timezone-aware; a value with no offset does not "
            "name an instant and UTC is never guessed for it",
            BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        )
    return value


def require_optional_aware_datetime(value: object, name: str) -> Optional[datetime]:
    """Require ``None`` (explicitly absent) or a timezone-aware ``datetime``.

    ``None`` is never conflated with a zero/epoch datetime. Where ``None`` would
    otherwise be ambiguous — the exclusive end of an effective period — the
    contract additionally requires an explicit
    :class:`~.enums.TemporalBoundDeclaration`, so absence is a recorded decision
    rather than an omission.
    """

    if value is None:
        return None
    return require_aware_datetime(value, name)


def require_strictly_before(
    earlier: datetime,
    later: datetime,
    earlier_name: str,
    later_name: str,
    rule: str,
    *,
    reason: BenchmarkRefusalReason = (
        BenchmarkRefusalReason.BENCHMARK_EFFECTIVE_PERIOD_INVALID
    ),
) -> None:
    """Require ``earlier < later``, rejecting equal and reversed orderings.

    An equal pair is refused as well as a reversed one: under the half-open
    ``[start, end)`` rule of ADR §17.9 an empty interval contains no instant, so
    it could never be effective and naming one is a mistake, not a decision.
    """

    if not earlier < later:
        raise _fail(
            f"{earlier_name} must strictly precede {later_name} ({rule}); "
            "an equal or reversed ordering is refused, never reordered",
            reason,
        )


def normalize_unordered_reference_tuple(
    value: object,
    name: str,
    *,
    reason: BenchmarkRefusalReason,
) -> tuple:
    """Normalize an **order-irrelevant** reference set into a canonical tuple.

    The entries are sorted by Unicode code point and returned as an immutable
    ``tuple``. Sorting is correct *here* because the collection this serves —
    ADR §15 row 16's source/provenance requirements — is a set of requirements
    whose order carries no meaning; ADR §22.2's "deterministic canonical bytes"
    then demands that two callers who wrote the same set in different orders
    produce one byte sequence. Normalizing happens in the contract, never in the
    encoder, so the encoder stays order-faithful for any collection whose order
    *is* meaningful.

    A caller-owned ``list`` is defensively copied, so later mutation of that list
    cannot reach the frozen contract or change its digest — the same
    defensive-copy discipline ADR §17.7 requires of trust-anchor views.

    Scalar substitutes are refused rather than silently iterated: a ``str`` or
    ``bytes`` would decompose into characters/bytes, and a ``Mapping`` would
    contribute only its keys. Blank, non-string and **duplicate** entries are
    refused, never dropped or coerced — de-duplicating would silently accept a
    document that says the same requirement twice, and B-7 admits no silent
    repair.
    """

    if isinstance(value, (str, bytes, bytearray)):
        raise _fail(
            f"{name} must be a sequence of reference strings, not a "
            f"{type(value).__name__}",
            reason,
        )
    if isinstance(value, Mapping):
        raise _fail(
            f"{name} must be a sequence, not a mapping; a benchmark coordinate "
            "is never carried in a free-form dictionary",
            reason,
        )
    if not isinstance(value, (list, tuple)):
        raise _fail(
            f"{name} must be a list or tuple of reference strings "
            f"(got {type(value).__name__}); an arbitrary iterable is refused "
            "because consuming it could depend on iteration order that is not "
            "part of the contract",
            reason,
        )
    items = tuple(value)
    if not items:
        raise _fail(
            f"{name} must not be empty",
            reason,
        )
    seen: set = set()
    normalized = []
    for index, item in enumerate(items):
        text = require_canonical_str(item, f"{name}[{index}]", allow_empty=False)
        if text in seen:
            raise _fail(
                f"{name} contains duplicate reference {text!r}; a requirement "
                "set may not name the same requirement twice, and a duplicate "
                "is refused rather than de-duplicated",
                reason,
            )
        seen.add(text)
        normalized.append(text)
    return tuple(sorted(normalized))
