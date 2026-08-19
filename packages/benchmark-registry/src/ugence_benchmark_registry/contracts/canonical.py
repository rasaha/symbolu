"""Versioned, domain-separated canonicalization for benchmark contracts.

**One** encoder produces the bytes behind **one** digest path. There is no
second serializer, no legacy digest, no dual-acceptance fallback, and no
alternate encoding a caller can select — ADR §22.2 requires canonical bytes to
be "a pure function of the payload", and two functions of the payload are not
one function.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` (no insignificant whitespace) and
  ``ensure_ascii=False``. The digest input is exactly those UTF-8 bytes.
* **Key ordering**: object keys sorted lexicographically by code point.
* **Field inclusion is total and deterministic**: every dataclass field is
  included, always, by declared name. Nothing is dropped when empty, and no
  field is conditionally omitted — a conditional omission would let two
  different payloads share one byte sequence. This is also what makes ADR §15's
  twenty coordinates *structurally* present in the digest rather than present by
  convention.
* **``None`` is represented explicitly** as JSON ``null``. ``None`` and ``""``
  are therefore distinct byte sequences and distinct digests.
* **Datetimes** must be timezone-aware; they are normalized to UTC with
  ``astimezone(timezone.utc)`` — pure arithmetic against the value's own
  offset — and rendered ``%Y-%m-%dT%H:%M:%S.%fZ``, which **preserves
  microseconds**. Two spellings of one instant therefore render identically
  (ADR §22.3). **A naive datetime is rejected**, here and at every construction
  boundary (ADR §22.4): a value with no offset does not name an instant, and
  guessing UTC would silently invent one.
* **Strings** must already be Unicode **NFC**; non-canonical input is rejected,
  never silently normalized (see the posture note below).
* **``bool`` before ``int``** — ``bool`` subclasses ``int`` in Python, so it is
  dispatched first and serialized as a JSON boolean, never as ``0``/``1``.
* **``float`` is rejected outright.** This subsumes the rejection of non-finite
  values (``nan``, ``inf``, ``-inf``), which have no canonical JSON form at all;
  exact values in these contracts are integers or strings. It matches the merged
  ``ugence_policy_authority`` and trusted-evidence canonicalization ``v1``
  posture.
* **Ordered collections** (``list``/``tuple``) preserve order. Where a BR-1
  collection's order is *semantically irrelevant* — as it is for ADR §15 row
  16's source/provenance requirements — the contract normalizes it into a
  ratified canonical order **before** it reaches the encoder, so two callers who
  wrote the same set in different orders share one digest. The encoder itself
  never reorders: normalizing inside it would silently erase order wherever
  order *is* meaningful.
* **Mappings and ``bytes`` are rejected.** No contract in this package carries
  either. Rejecting mappings structurally enforces ADR §15's rule that a
  required benchmark coordinate can never disappear into a free-form metadata
  dictionary or an extension bag: there is no type in which one could be
  written. Rejecting ``bytes`` keeps every digest and reference a canonical
  lowercase hex **string** with exactly one spelling.
* **Unknown types fail closed** (ADR §22.8). There is **no** ``default=`` hook,
  no ``str()`` fallback, and no ``repr()`` anywhere in this module: an
  unrecognized type raises. A permissive fallback would make the digest a
  function of a Python object's textual rendering — including its ``id()`` for
  any default ``__repr__`` — which is neither deterministic across processes nor
  a function of the payload.

Determinism inputs
------------------
The encoder consults **no** wall clock, locale, timezone database, environment
variable, filesystem or network (ADR §22.9). ``astimezone`` is always called
with an explicit ``timezone.utc`` target, never the zero-argument form that
would infer the local zone. Package tests assert this structurally over the
whole source tree, not merely for one code path.

Unicode posture — reject, do not normalize
------------------------------------------
Silent NFC normalization would map two *structurally different* artifacts onto
one digest: an NFD-spelled and an NFC-spelled coordinate would become
indistinguishable, so a digest over one would attest a value nobody wrote.
Rejecting keeps the digest a faithful function of the exact bytes the author
committed to. The posture is bound to the canonicalization version, so changing
it requires a new version. This is the merged ``ugence_policy_authority`` §12
posture (a), adopted rather than re-litigated.

Domain separation and versioning
--------------------------------
ADR §22.1 requires every digest to bind a canonicalization version and a
domain-separation tag, and **DD-9 explicitly leaves the exact byte constants to
TEV-1/TEV-2 and BR-1/BR-2**. This module is where BR-1 resolves them.

**BR-1 mints exactly one domain**, because BR-1 introduces exactly one artifact
class: the benchmark-definition identity and the coordinates that make it up.
:data:`BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN` covers
:class:`~.identity.CanonicalBenchmarkDefinitionIdentity` and every contract
nested inside it. They are not separate artifact classes — they are the parts of
one definition's identity, exactly as the trusted-evidence identity family is
one class.

**No other domain is minted.** DD-9's licence is to settle byte constants for
artifacts a milestone actually ships, not to reserve byte space for a later one.
BR-2's registration record, resolution result, signed publication, revocation
record, trust anchor and audit record do not exist, so their tags do not exist
either: a tag without an artifact is an unused constant a later milestone would
have to either honour or break. The **successor/supersession** domain is
likewise unminted — DD-4 defers the structured successor reference itself.

Minting a domain grants nothing; it separates byte spaces. Because the domain is
framed into the bytes, a benchmark-identity digest can never be read as a
digest in any other capability's domain, and vice versa — in particular it is a
different byte space from the merged trusted-evidence domains, so an evidence
digest and a benchmark digest can never collide.

Every canonical byte sequence is framed as::

    {"body": {...}, "canonicalization": <version>, "domain": <tag>, "type": <name>}

so the same body under two contract types can never produce the same bytes. The
``type`` element is what keeps the nested coordinate contracts distinct inside
the one domain.

Only the exact registered BR-1 contract classes are canonicalizable
---------------------------------------------------------------------
Framing alone is not the security boundary — a `type` string is only trustworthy
once the object producing it is known to be genuine. **Membership in the
contract-type registry is decided by class *identity* (``cls is
SomeExactClass``, checked with the interpreter's ``is`` primitive, which has no
dunder method for any class or metaclass to override), never by ``__name__``,
``__module__``, or the class object's own ``__eq__``/``__hash__``.** A
subclass, a same-named foreign dataclass defined anywhere else, a same-named
class whose ``__module__`` was forged to match this package, an arbitrary
dataclass or duck type, and a foreign class whose **metaclass** forges the
class object's own equality or hash to collide with a genuine registered class
are all refused outright — none of them reaches the encoder, and none of them
produces bytes or a digest, "borrowed" or otherwise.

The registry mapping contract classes to their domain is populated exactly
once, by :mod:`.identity` at import time, and is then sealed. It is built and
held entirely inside a closure (:func:`_build_exact_type_boundary`): the only
module-level names are the functions the closure returns, never the mapping
itself. This matters because a :class:`~types.MappingProxyType` alone stops a
mapping from being *mutated* but does nothing to stop a module attribute that
*holds* one from being **rebound outright** — ``canonical._REGISTERED_X =
{Evil: domain}`` is always legal Python for any code that imported the module,
regardless of a leading underscore, and every subsequent call into an
*unmodified* :func:`canonical_bytes` would then trust it, because the encoder
reads a module global by name at call time. With no such name exposed, no
caller — including code inside this package — can widen or replace the
registry by any means short of reaching into the closure's cells directly
(``func.__closure__``), which is possible in CPython but is a fundamentally
different, much deeper capability than mapping mutation or attribute
replacement — equivalent to being able to rebind ``canonical_bytes`` itself,
or any other name in this process, and is not defended against here or
anywhere else in the standard library.

Before producing bytes, :func:`canonical_bytes` also **revalidates the complete
exact contract graph**: every dataclass node reachable from the root re-runs its
own ``__post_init__`` invariants. This is what catches a frozen instance
corrupted after construction via ``object.__setattr__`` — a swapped nested
object of the wrong exact type, an invalid semantic version, an inexact
coordinate token, a malformed applicability or supersession value, a duplicate
reference — anything whose state could not have come from the public
constructors is refused here, before a single byte is produced. A revalidation
failure never repairs the object; it refuses it.

The content digest is not this digest
-------------------------------------
ADR §15 row 4's **content digest** is a coordinate the definition *declares*: the
digest of the benchmark content itself, which lives outside this package and
which the Benchmark Registry never authors (§7.2 row 1). The digest this module
computes is the digest **of the identity**. They are different values with
different owners, and §16.2 stage 2's "declared digest equals the computed
canonical digest" check — over the benchmark *content* — is BR-2's, because it
needs content this package never holds.

Independent verification
------------------------
:func:`canonical_bytes` and :func:`canonical_digest` are public and pure. A
third party holding a contract and this module can recompute any digest without
package internals; the package tests and the distribution verifier both
reconstruct pinned digests from hand-written literal bytes and ``hashlib``
alone.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from .errors import BenchmarkCanonicalizationError, BenchmarkContractError

__all__ = [
    "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
    "BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN",
    "canonical_bytes",
    "canonical_digest",
]

#: The canonicalization rule-set version bound into every digest (ADR §22.1).
#: Changing any rule in this module's docstring requires a new version string.
BENCHMARK_REGISTRY_CANONICALIZATION_VERSION = (
    "ugence.benchmark-registry/canonicalization/v1"
)

#: The domain-separation tag bound into every benchmark-definition-identity
#: digest — the single domain BR-1 mints (DD-9).
#:
#: Covers :class:`~.identity.CanonicalBenchmarkDefinitionIdentity` and every
#: contract nested inside it: the coordinate, the scope, the two applicability
#: coordinates, the measurement semantics, the effective period, the source
#: requirements, the approval reference and the supersession declaration. All
#: describe one artifact class — the identity of one benchmark definition.
BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN = (
    "ugence.benchmark-registry/benchmark-definition-identity/v1"
)

#: The closed contract-type registry, built once below by
#: :func:`_build_exact_type_boundary` and exposed only through the four
#: closures it returns. There is deliberately **no module-level name bound to
#: the registry's backing dict or to a `MappingProxyType` wrapping it** — a
#: `MappingProxyType` stops the mapping from being *mutated* (no
#: ``__setitem__``), but it does nothing to stop a module attribute that
#: *holds* one from being **rebound** wholesale (``some_module.NAME = ...`` is
#: always legal from any code that imported the module; leading underscores
#: are a convention, not an access-control mechanism). A registry exposed as
#: ``canonical._REGISTERED_CONTRACT_TYPES`` could be replaced outright by any
#: caller — ``canonical._REGISTERED_CONTRACT_TYPES = {Evil: domain}`` — and
#: every subsequent call to the *unmodified* ``canonical_bytes`` would trust
#: it, because the encoder reads the module global by name at call time.
#: Closing over the dict instead means there is no such name to rebind: the
#: only module-level surface is the four functions themselves, and rebinding
#: one of *those* replaces a function wholesale (indistinguishable from
#: replacing ``canonical_bytes`` itself) rather than quietly widening which
#: types are trusted while the rest of the module keeps behaving normally.
#:
#: Lookup is by class **identity**, checked with ``is`` — never ``in``/``[]``
#: on the backing dict, which would dispatch to ``__hash__``/``__eq__`` on
#: whichever operand's type defines them. A class object's default
#: ``__eq__``/``__hash__`` (inherited from :class:`type`) already is
#: identity-based, but a **custom metaclass** can override the *type object's*
#: ``__eq__``/``__hash__`` (the metaclass's dunders govern comparisons of the
#: class itself, not of its instances) to make an unrelated class object
#: compare equal to, and hash the same as, a genuine registered class — which
#: would defeat a dict-membership check while never touching the registry's
#: contents. ``is`` has no dunder to override; it is the interpreter's own
#: object-identity primitive.
def _build_exact_type_boundary():
    types_: dict = {}
    sealed = False

    def record(cls: type, domain: str) -> None:
        """Register ``cls`` as an exact, canonicalizable BR-1 contract type.

        Private to this package's own module-initialization path. Refuses to
        run once :func:`seal` has been called, and refuses anything that is
        not itself a dataclass, so the registry can never be grown by a
        caller — including one holding a reference to this "private"
        function — after package import completes.
        """

        if sealed:
            raise RuntimeError(
                "the BR-1 contract-type registry is sealed; no type may be "
                "registered after package initialization"
            )
        if not (isinstance(cls, type) and is_dataclass(cls)):
            raise TypeError(
                f"only a dataclass type may be registered as a BR-1 "
                f"contract type (got {cls!r})"
            )
        types_[cls] = domain

    def seal() -> None:
        """Close the registry. Called exactly once, by :mod:`.identity`
        after registering all nine BR-1 contract classes."""

        nonlocal sealed, types_
        types_ = MappingProxyType(dict(types_))
        sealed = True

    def domain_for(cls: type) -> Any:
        """Return the registered domain for ``cls`` by identity, or ``None``.

        Iterates the registered classes and compares each with ``cls is
        registered_cls``. Dict iteration itself never consults ``__eq__`` or
        ``__hash__`` (those only matter for ``in``/``[]``/insertion), so this
        is immune to a metaclass forging either on a foreign class's type
        object.
        """

        for registered_cls, domain in types_.items():
            if cls is registered_cls:
                return domain
        return None

    def snapshot() -> Any:
        """A read-only **copy** for introspection only (tests, probes).

        Never consulted by :func:`canonical_bytes`, :func:`canonical_digest`,
        or the encoder — those call :func:`domain_for` against the closure's
        own ``registry``, which this snapshot cannot reach or influence in
        either direction: mutating, replacing, or discarding the returned
        mapping has no effect on what the encoder trusts.
        """

        return MappingProxyType(dict(types_))

    return record, seal, domain_for, snapshot


(
    _register_contract_type,
    _seal_contract_types,
    _domain_for_contract_type,
    _contract_type_registry_snapshot,
) = _build_exact_type_boundary()

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _require_nfc(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise BenchmarkCanonicalizationError(
            f"{path}: string is not Unicode NFC-normalized; benchmark "
            "contracts reject non-canonical input rather than silently "
            f"normalizing it ({BENCHMARK_REGISTRY_CANONICALIZATION_VERSION})"
        )
    return value


def _format_datetime(value: datetime, path: str) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise BenchmarkCanonicalizationError(
            f"{path}: a naive datetime is not a well-defined instant and must "
            "not enter a canonical byte sequence, an effective period, or a digest"
        )
    return value.astimezone(timezone.utc).strftime(_TIMESTAMP_FMT)


def _to_canonical_obj(value: Any, path: str) -> Any:
    """Recursively convert ``value`` into a JSON-canonical structure.

    The result contains only ``dict`` (string keys), ``list``, ``str``, ``int``,
    ``bool`` and ``None``. Every rejection carries the offending path.
    """

    if value is None:
        return None
    # ``bool`` before ``int`` — ``bool`` subclasses ``int``.
    if isinstance(value, bool):
        return value
    # ``float`` before any numeric handling: rejected outright, which covers
    # nan/inf/-inf as well as every finite float.
    if isinstance(value, float):
        raise BenchmarkCanonicalizationError(
            f"{path}: float is not canonicalizable — a governed coordinate must "
            "be an exact integer or a string (this also rejects nan/inf/-inf, "
            "which have no canonical JSON form)"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return _require_nfc(value, path)
    if isinstance(value, Enum):
        return _to_canonical_obj(value.value, path)
    if isinstance(value, datetime):
        return _format_datetime(value, path)
    if is_dataclass(value) and not isinstance(value, type):
        if _domain_for_contract_type(type(value)) is None:
            raise BenchmarkCanonicalizationError(
                f"{path}: type {type(value).__name__!r} "
                f"(module {type(value).__module__!r}) is not a registered "
                "BR-1 contract type; only the exact classes this package "
                "defines can be canonicalized, and neither the name nor the "
                "module of a foreign, subclassed or duck-typed object is "
                "ever treated as authority"
            )
        return {
            _require_nfc(f.name, f"{path}.{f.name}"): _to_canonical_obj(
                getattr(value, f.name), f"{path}.{f.name}"
            )
            for f in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise BenchmarkCanonicalizationError(
        f"{path}: type {type(value).__name__!r} is not canonicalizable; the "
        "encoder has no permissive fallback and never renders an unknown object"
    )


def _require_registered_exact_type(contract: Any, path: str) -> type:
    """Return ``type(contract)`` iff it is an exact registered BR-1 contract.

    The only check that matters here is class **identity** against the sealed
    registry — never ``__name__``, never ``__module__``. A subclass fails this
    (subclassing produces a different class object even when it inherits every
    method), a foreign dataclass of the same name fails this, and a foreign
    class whose ``__module__`` was forged to look like this package's still
    fails this, because none of them *is* the exact object this package
    registered.
    """

    if not is_dataclass(contract) or isinstance(contract, type):
        raise BenchmarkCanonicalizationError(
            f"{path}: canonical_bytes expects a benchmark contract instance "
            f"(got {type(contract).__name__})"
        )
    cls = type(contract)
    if _domain_for_contract_type(cls) is None:
        raise BenchmarkCanonicalizationError(
            f"{path}: type {cls.__name__!r} (module {cls.__module__!r}) is "
            "not a registered BR-1 contract type; only the exact classes "
            "this package defines can be canonicalized. Subclasses, "
            "same-named foreign dataclasses (including ones with a forged "
            "matching module or a metaclass forging the class object's own "
            "equality/hash), duck types and arbitrary dataclasses are all "
            "refused — class-name matching and class-object equality are "
            "never used as authority, only interpreter-level identity"
        )
    return cls


def _revalidate_exact_contract_graph(contract: Any, path: str) -> None:
    """Re-run every reachable node's own structural invariants.

    Defends against a frozen instance corrupted after construction via
    ``object.__setattr__``: each dataclass node in the graph must
    independently pass the same ``__post_init__`` checks its public
    constructor would have enforced — including the exact-type checks it runs
    on its own nested fields, which is what catches a wrong-typed or
    same-named-lookalike object substituted at any depth. A node whose state
    could not have come from the public constructors is refused here, before
    a single byte is produced; nothing is silently repaired.
    """

    cls = _require_registered_exact_type(contract, path)
    try:
        cls.__post_init__(contract)
    except BenchmarkContractError as exc:
        raise BenchmarkCanonicalizationError(
            f"{path}: {cls.__name__} failed structural revalidation before "
            f"canonicalization ({exc}); an object whose state could not "
            "have passed its own public constructor is refused rather than "
            "canonicalized"
        ) from exc
    for f in fields(contract):
        _revalidate_value(getattr(contract, f.name), f"{path}.{f.name}")


def _revalidate_value(value: Any, path: str) -> None:
    if is_dataclass(value) and not isinstance(value, type):
        _revalidate_exact_contract_graph(value, path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _revalidate_value(item, f"{path}[{index}]")


def canonical_bytes(contract: Any) -> bytes:
    """Return the exact UTF-8 bytes :func:`canonical_digest` is computed over.

    ``contract`` must be an exact instance of one of the nine registered BR-1
    contract classes — never a subclass, a same-named foreign dataclass, a
    duck type, or any other dataclass. Membership is decided by class
    identity against the sealed contract-type registry, never by name. The
    returned bytes are the framed, domain-separated, version-labelled
    encoding described in the module docstring.

    Before any byte is produced, the complete contract graph reachable from
    ``contract`` is revalidated (see :func:`_revalidate_exact_contract_graph`),
    so an instance corrupted after construction via ``object.__setattr__``
    into a state its public constructor would have refused is refused here
    too.

    Two contracts that compare equal always produce byte-identical output,
    including when their instants were written with different UTC offsets::

        if a == b:
            assert canonical_bytes(a) == canonical_bytes(b)

    Two contracts differing in **any** load-bearing coordinate always produce
    different output — which for ADR §15's twenty coordinates is asserted
    coordinate by coordinate by the package tests.
    """

    cls = _require_registered_exact_type(contract, "$")
    domain = _domain_for_contract_type(cls)
    _revalidate_exact_contract_graph(contract, "$")
    type_name = cls.__name__
    framed = {
        "canonicalization": BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
        "domain": domain,
        "type": type_name,
        "body": _to_canonical_obj(contract, "$"),
    }
    return json.dumps(
        framed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_digest(contract: Any) -> str:
    """Return the bare lowercase 64-char sha-256 hex digest of the canonical bytes.

    The digest is computed **solely** from :func:`canonical_bytes` — no other
    input, no salt, no clock, no side channel. It is an identity fingerprint. It
    is **not** approval evidence, not a publisher signature, not a registration,
    and not a resolution: ADR B-5 rules that approval binds a content digest
    rather than being one, and B-9 that "possession is not validity; retrieval is
    not resolution". Computing or matching this digest establishes only that two
    identities are the same identity.
    """

    return hashlib.sha256(canonical_bytes(contract)).hexdigest()
