"""Stdlib-only structural validators shared by the BR-2 registry contracts.

Private module — nothing here is part of the curated public API. These are the
fail-closed primitives every contract's ``__post_init__`` is built from, kept in
one place so a rule cannot drift between two contracts.

Four disciplines run through all of them, inherited from the frozen BR-1 layer
rather than re-derived:

* **Never silently normalize an invalid value into an accepted one.** A blank
  identifier is rejected, not defaulted; a padded string is rejected, not
  trimmed; a naive datetime is rejected, not assumed UTC; an uppercase digest is
  rejected, not lowercased.
* **Reject duck-typed lookalikes where contract identity matters.** ``type(x) is
  Expected``, never ``isinstance``: a **subclass** is refused along with a duck
  type, because a subclass is the cheapest way to smuggle an overridden property
  past an ``isinstance`` check.
* **Make an impossible state unrepresentable, not merely detected.** §09 states
  the preference explicitly: *prefer making the conflicting representation
  unconstructible over detecting the conflict*. Where a value is derivable from
  an exact nested contract, no field for it exists at all.
* **Actor separation is checked where both actors are first mechanically
  reachable** — never earlier (where one of them is not present) and never later
  (where an unseparated artifact would already have been constructed).

These validators are **BR-2A's own**. They deliberately do not import BR-1's
private ``_validation`` module: a package's private surface is not an API, and
reaching into one would couple this package to a module the frozen layer is free
to reorganize. Where BR-2A needs a *BR-1* rule enforced — exact coordinate
tokens, exact SemVer, the floating-token ban — it does not re-implement the rule
at all: it requires an exact
:class:`~ugence_benchmark_registry.BenchmarkCoordinate`, which already enforced
every one of them at its own construction. That is one source of truth, not two.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import Enum
from typing import Optional

from .errors import BenchmarkRegistryContractError
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "require_exact_type",
    "require_canonical_str",
    "require_identifier",
    "require_digest",
    "require_detached_signature",
    "require_public_key_material",
    "require_aware_datetime",
    "require_enum_member",
    "require_distinct_actors",
    "require_exact_string_equality",
    "require_pinned_constant",
]

#: A bare lowercase sha-256 hex digest. One spelling only.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: Ed25519 public-key material, carried as exactly 64 lowercase hex characters
#: (32 bytes). A **separate** pattern from ``_SHA256_RE`` even though the two
#: currently accept the same language: sharing one constant would mean a future
#: change to the digest rule silently re-specified what a public key may be.
_ED25519_PUBLIC_KEY_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

#: A detached Ed25519 signature, carried as exactly 128 lowercase hex
#: characters (64 bytes). Canonicalization refuses ``bytes`` outright, so the
#: signature has to be a string — and a string coordinate must have exactly one
#: spelling, so the length, the case and the alphabet are all fixed.
_ED25519_HEX_RE = re.compile(r"^[0-9a-f]{128}$")


def _fail(
    message: str,
    reason: Optional[BenchmarkRegistryRefusalReason] = None,
) -> BenchmarkRegistryContractError:
    error = BenchmarkRegistryContractError(message)
    if reason is not None:
        error.reason = reason
    return error


def require_exact_type(value: object, expected: type, name: str) -> None:
    """Reject anything that is not *exactly* ``expected``.

    Uses ``type(value) is expected``, not ``isinstance``, so a **subclass** is
    refused along with a duck-typed lookalike. ADR §26 requires that a
    self-consistent forged artifact still fail, and a subclass is the cheapest
    forgery: it inherits every genuine method, passes every ``isinstance``
    check, and can still override the one property that matters.

    This is also the check that makes the nested chain load-bearing. A
    :class:`~.chain.BenchmarkRegistrationEventPayload` that accepted *any*
    object with a ``declared_outcome`` attribute would be accepting the
    attacker's word for its predecessor; requiring the exact admission-decision
    class means the predecessor had to pass the admission decision's own
    constructor first.
    """

    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} "
            f"(got {type(value).__name__}); subclasses and duck-typed "
            "lookalikes are refused because contract identity is load-bearing "
            "and a nested predecessor is the only evidence a payload has",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )


def require_canonical_str(value: object, name: str, *, allow_empty: bool) -> str:
    """Require a canonical ``str``: exact type, unpadded, and Unicode NFC.

    ``bool``, every other non-``str``, and every ``str`` **subclass** are
    refused — a subclass could override ``__eq__``, ``__hash__`` or ``__str__``
    and thereby change what a comparison or a digest sees, which for an actor
    identity would mean an actor-separation check comparing something other than
    what gets digested.

    An all-whitespace value is refused whether or not ``allow_empty`` is set: it
    is padding around nothing, not an explicit absence.

    A non-NFC value is refused here, **at construction**, and again by the
    canonical encoder. Neither boundary normalizes it.
    """

    if type(value) is not str:
        raise _fail(
            f"{name} must be a string (got {type(value).__name__}); str "
            "subclasses are refused because a subclass can change what "
            "comparison, actor separation and canonicalization each see",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    if value != value.strip():
        raise _fail(
            f"{name} must be a canonical string with no leading or trailing "
            "whitespace; padding is refused, never trimmed, so the digest "
            "stays a faithful function of the exact value supplied",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    if unicodedata.normalize("NFC", value) != value:
        raise _fail(
            f"{name} must be Unicode NFC-normalized; a non-canonical string is "
            "refused at construction and never silently normalized, so two "
            "differently-spelled identities can never share one digest",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    if not value and not allow_empty:
        raise _fail(
            f"{name} must not be empty",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    return value


def require_identifier(value: object, name: str) -> str:
    """Require a non-empty, unpadded, NFC canonical identifier string.

    Used for every declared actor identity and key identifier in this package.
    Note what it deliberately does **not** do: it does not check that the
    identity names a real publisher, a configured key, or an entitled anchor.
    Nothing in BR-2A can — there is no trust directory, no key parser and no
    verifier — and a validator that appeared to would be exactly the
    "caller-created verification object" ADR B-5 rules is not evidence.
    """

    return require_canonical_str(value, name, allow_empty=False)


def require_digest(
    value: object,
    name: str,
    *,
    reason: BenchmarkRegistryRefusalReason = (
        BenchmarkRegistryRefusalReason.INDETERMINATE
    ),
) -> str:
    """Require a bare lowercase 64-char sha-256 hex digest.

    One spelling only: uppercase hex, a ``0x`` prefix, padding and any other
    length are refused rather than normalized, so one digest value has exactly
    one representation in a canonical byte sequence — and so a digest-equality
    check can never be defeated by a second spelling.
    """

    text = require_canonical_str(value, name, allow_empty=False)
    if not _SHA256_RE.match(text):
        raise _fail(
            f"{name} must be a bare lowercase 64-char sha-256 hex digest "
            f"(got {text!r}); one digest value has exactly one spelling",
            reason,
        )
    return text


def require_detached_signature(value: object, name: str) -> str:
    """Require a detached Ed25519 signature as exactly 128 lowercase hex chars.

    **This validates an encoding, not a signature.** It proves the field has the
    shape a signature would have. It does not, and at BR-2A cannot, prove that
    the bytes are a signature at all, that they were produced by the declared
    key, that the declared key exists, or that anyone is entitled to use it.
    Every envelope carrying one permanently derives ``signature_verified is
    False`` for exactly this reason.
    """

    text = require_canonical_str(value, name, allow_empty=False)
    if not _ED25519_HEX_RE.match(text):
        raise _fail(
            f"{name} must be a detached signature encoded as exactly 128 "
            f"lowercase hex characters (64 bytes) (got a {len(text)}-character "
            "value); canonicalization refuses bytes outright, so the signature "
            "is carried as a string with exactly one admissible spelling. "
            "Validating this encoding is not verifying this signature",
            BenchmarkRegistryRefusalReason.SIGNATURE_INVALID,
        )
    return text


def require_public_key_material(value: object, name: str) -> str:
    """Require Ed25519 public-key material as exactly 64 lowercase hex chars.

    **This validates an encoding, not a key.** It proves the field has the shape
    Ed25519 public-key material would have — 32 bytes, one spelling, lowercase
    hex. It does not decode those bytes, does not check that they are a valid
    curve point, does not construct a key object and does not import anything to
    do so. D-04 forbids this package from parsing key material and this package
    ships no cryptographic dependency at all; a validator that decoded the point
    would be the first half of a key parser.

    Carried as a string rather than :class:`bytes` for the same reason every
    other opaque value in this package is: canonicalization refuses ``bytes``
    outright, and one value must have exactly one spelling or two differently
    encoded anchors could share one digest — which, since D-25 makes the anchor
    revision the record's canonical digest, would make two distinct anchors one
    revision.
    """

    text = require_canonical_str(value, name, allow_empty=False)
    if not _ED25519_PUBLIC_KEY_HEX_RE.match(text):
        raise _fail(
            f"{name} must be Ed25519 public-key material as exactly 64 "
            "lowercase hex characters (32 bytes); the encoding is checked and "
            "the bytes are never decoded, because this package parses no key "
            "material and links no cryptographic library",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    return text


def require_aware_datetime(value: object, name: str) -> datetime:
    """Require a timezone-aware ``datetime``.

    Rejects a naive value rather than assuming UTC for it (ADR §22.4), and
    rejects a ``datetime`` **subclass**, which could override ``utcoffset`` or
    ``astimezone`` and thereby change what instant the canonical bytes record
    while the object still compared equal to a genuine one.

    Requiring a caller to supply this value is not granting it authority. D-11
    ratifies one injected authoritative clock for recorded time, owned by the
    registry from BR-2D onward; **neither BR-2A nor BR-2B reads a clock**, so every
    timestamp in this package is a *declaration* by whoever constructed the
    object, permanently covered by ``authority_verified is False``.
    """

    if type(value) is not datetime:
        raise _fail(
            f"{name} must be exactly a datetime (got {type(value).__name__}); "
            "a datetime subclass is refused because it can override utcoffset "
            "or astimezone and change which instant is digested",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise _fail(
            f"{name} must be timezone-aware; a value with no offset does not "
            "name an instant and UTC is never guessed for it",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    return value


def require_enum_member(value: object, expected: type, name: str) -> Enum:
    """Require exactly a member of ``expected``, never a string spelling of one.

    ``str``-valued enums compare equal to their own values, so ``"ADMITTED" ==
    BenchmarkAdmissionOutcome.ADMITTED`` is :data:`True`. That convenience is a
    hazard at a contract boundary: a bare string would pass an equality check,
    canonicalize to the same bytes, and yet carry none of the closed-vocabulary
    guarantee the enum exists to provide. The exact-type check closes it.
    """

    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} member "
            f"(got {type(value).__name__}); a bare string that spells a member "
            "is not a member, even though a str-valued enum compares equal to "
            "it, and a closed vocabulary that accepts strings is not closed",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )
    return value


def require_distinct_actors(
    first: str,
    second: str,
    first_name: str,
    second_name: str,
    rule: str,
) -> None:
    """Require two declared actor identities to differ, refusing equality.

    D-02's four-party separation is what stops a single compromised party moving
    an artifact from submitted to resolvable. The check is placed in the **first
    contract where both identities are mechanically reachable** — never in a
    later one, because by then an unseparated artifact would already exist and
    the check would be advice rather than a constructor invariant.

    Separation is compared on the exact declared strings. It is *not* an
    authenticity check: two distinct identities are still two *declarations*, and
    neither is verified at BR-2A. Distinctness closes the self-approval hole; it
    does not open a trust one.
    """

    if first == second:
        raise _fail(
            f"{first_name} must differ from {second_name} ({rule}); the same "
            "party may not occupy two roles the four-party separation of D-02 "
            "keeps apart, and self-approval is not approval",
            BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION,
        )


def require_exact_string_equality(
    value: str,
    expected: str,
    value_name: str,
    expected_name: str,
    rule: str,
) -> None:
    """Require ``value == expected`` exactly, refusing any divergence.

    Used only where a value must be repeated for display or indexing and the
    single source of truth lives elsewhere. §09 prefers making the conflicting
    representation *unconstructible*; where a repetition genuinely must exist,
    this is the fallback that proves the repetition agrees with its source
    rather than competing with it.
    """

    if value != expected:
        raise _fail(
            f"{value_name} must equal {expected_name} exactly ({rule}); "
            f"got {value!r} against {expected!r}. A second spelling of one "
            "value is refused rather than reconciled — the nested contract is "
            "the single source of truth",
            BenchmarkRegistryRefusalReason.INDETERMINATE,
        )


def require_pinned_constant(
    value: object,
    expected: str,
    name: str,
    rule: str,
) -> str:
    """Require a declared framing coordinate to equal its pinned constant.

    Signing-frame domains and versions are *declared on the artifact* — a
    verifier has to know which frame to verify under, and reading that from a
    field the artifact carries is what makes an already-published contract
    interpretable by a later milestone without reinterpretation (§11). But a
    caller-chosen frame identifier would be an unconstrained algorithm string by
    another name, so the admissible set has exactly one member: the pinned
    constant this package publishes.

    The field is therefore digest-participating **and** closed. It records which
    frame was intended without letting a caller invent one.
    """

    text = require_canonical_str(value, name, allow_empty=False)
    if text != expected:
        raise _fail(
            f"{name} must be exactly {expected!r} ({rule}); got {text!r}. "
            "The signing-frame identifiers are a closed, pinned vocabulary — a "
            "caller-chosen frame is an unconstrained algorithm string under "
            "another name, and a verifier that reads its frame from an "
            "attacker-supplied field has already lost",
            BenchmarkRegistryRefusalReason.SIGNATURE_INVALID,
        )
    return text
