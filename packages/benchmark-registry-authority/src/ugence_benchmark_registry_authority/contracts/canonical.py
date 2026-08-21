"""Versioned, domain-separated canonicalization for BR-2 registry contracts.

**One** encoder produces the bytes behind **one** digest path. There is no
second serializer, no legacy digest, no dual-acceptance fallback, and no
alternate encoding a caller can select — ADR §22.2 requires canonical bytes to
be "a pure function of the payload", and two functions of the payload are not
one function. This is the same posture the frozen BR-1 layer ships;
**reproduced, not re-derived**, so the two layers cannot drift into two
disciplines.

Exact encoding rules (canonicalization ``v1``)
----------------------------------------------
* **Serialization**: UTF-8 JSON via ``json.dumps`` with ``sort_keys=True``,
  ``separators=(",", ":")`` (no insignificant whitespace) and
  ``ensure_ascii=False``. The digest input is exactly those UTF-8 bytes.
* **Key ordering**: object keys sorted lexicographically by code point.
* **Field inclusion is total and deterministic**: every dataclass field is
  included, always, by declared name. Nothing is dropped when empty, and no
  field is conditionally omitted — a conditional omission would let two
  different payloads share one byte sequence.
* **``None`` is represented explicitly** as JSON ``null``. ``None`` and ``""``
  are therefore distinct byte sequences and distinct digests.
* **Datetimes** must be timezone-aware; they are normalized to UTC with
  ``astimezone(timezone.utc)`` — pure arithmetic against the value's own
  offset — and rendered ``%Y-%m-%dT%H:%M:%S.%fZ``, which **preserves
  microseconds**. A naive datetime is rejected here and at every construction
  boundary.
* **Strings** must already be Unicode **NFC**; non-canonical input is rejected,
  never silently normalized.
* **``bool`` before ``int``** — ``bool`` subclasses ``int``, so it is dispatched
  first and serialized as a JSON boolean, never as ``0``/``1``.
* **``float`` is rejected outright**, which subsumes ``nan``/``inf``/``-inf``.
* **Mappings and ``bytes`` are rejected.** No contract in this package carries
  either. Rejecting mappings structurally enforces that a required coordinate
  can never disappear into a free-form metadata dictionary or an extension bag:
  there is no type in which one could be written. Rejecting ``bytes`` keeps
  every digest, reference and **detached signature** a canonical lowercase hex
  string with exactly one spelling.
* **Unknown types fail closed** (ADR §22.8). There is **no** ``default=`` hook,
  no ``str()`` fallback, and **no ``repr()`` anywhere in this module**: an
  unrecognized type raises. A permissive fallback would make the digest a
  function of a Python object's textual rendering — including its ``id()`` for
  any default ``__repr__`` — which is neither deterministic across processes nor
  a function of the payload.

Determinism inputs
------------------
The encoder consults **no** wall clock, locale, timezone database, environment
variable, filesystem or network. ``astimezone`` is always called with an
explicit ``timezone.utc`` target, never the zero-argument form that would infer
the local zone. ``tests/contract/test_timestamps.py`` asserts this
structurally over the whole source tree, not merely for one code path —
**neither BR-2A nor BR-2B reads a clock anywhere**, which is D-11 as amended.

Derived digests never enter the body
------------------------------------
Every upstream digest a payload exposes — ``prev_event_digest``,
``submission_record_digest``, ``registration_event_digest`` and the rest — is a
**derived read-only property**, computed by calling :func:`canonical_digest` on
the exact nested object. None of them is a dataclass field, so none of them
enters the encoded body, and no recursion is possible.

That is not a gap: the nested object *is* in the body, so substituting it
changes the parent's bytes and every downstream digest by construction. A
caller-supplied ``prev_event_digest`` field would be a second, independent
spelling of a value the nested object already fixes — which §09 prohibits, and
§14 forbids outright: *no caller-supplied upstream digest field exists anywhere*.

Domain separation and versioning
--------------------------------
ADR §22.1 requires every digest to bind a canonicalization version and a
domain-separation tag. BR-1 minted exactly one domain because it introduced
exactly one artifact class. **BR-2A introduced fifteen distinct
artifact classes and minted exactly fifteen domains; BR-2B appends three more**
— one per class each subphase actually ships, and **no tag for an artifact that
does not exist**. The
authority-issued result types reserved for BR-2D
(``BenchmarkAdmissionDecision``, ``BenchmarkRegistrationEvent``,
``BenchmarkResolution``) have no domain here, because they have no definition
here: a tag without an artifact is an unused constant a later milestone would
have to either honour or break.

Minting a domain grants nothing; it separates byte spaces. Because the domain is
framed into the bytes, a BR-2 registration-event digest can never be read as a
BR-1 benchmark-identity digest, as a BR-2 revocation-event digest, or as a digest
in any other capability's domain.

Every canonical byte sequence is framed as::

    {"body": {...}, "canonicalization": <version>, "domain": <tag>, "type": <name>}

so the same body under two contract types can never produce the same bytes.

Only exact registered classes are canonicalizable
-------------------------------------------------
Framing alone is not the security boundary — a ``type`` string is only
trustworthy once the object producing it is known to be genuine. **Membership in
the contract-type registry is decided by class identity (``cls is
SomeExactClass``, checked with the interpreter's ``is`` primitive, which has no
dunder method for any class or metaclass to override), never by ``__name__``,
``__module__``, ``in``, ``[]``, a class's own ``__eq__``/``__hash__``, or a
metaclass path.**

The registry is populated exactly once, at package import time, and then sealed.
It is built and held entirely inside a closure
(:func:`_build_exact_type_boundary`): the only module-level names are the
functions the closure returns, never the mapping itself. A
:class:`~types.MappingProxyType` alone stops a mapping from being *mutated* but
does nothing to stop a module attribute that *holds* one from being **rebound
outright** — ``canonical._REGISTERED_X = {Evil: domain}`` is always legal Python
for any code that imported the module, regardless of a leading underscore, and
every subsequent call into an *unmodified* :func:`canonical_bytes` would then
trust it, because the encoder reads a module global by name at call time. With no
such name exposed, no caller — including code inside this package — can widen or
replace the registry by any means short of reaching into the closure's cells
directly, which is a fundamentally different and much deeper capability, and is
not defended against here or anywhere else in the standard library.

Two kinds of registered class
-----------------------------
BR-2A payloads nest **frozen BR-1 contracts** — the exact
:class:`~ugence_benchmark_registry.BenchmarkCoordinate` and the
:class:`~ugence_benchmark_registry.BenchmarkScope` and
:class:`~ugence_benchmark_registry.BenchmarkApplicabilityCoordinate` inside it.
The registry therefore records two capabilities per class:

* **root-canonicalizable** — the class owns a domain minted here and may be
  handed to :func:`canonical_bytes` directly. Eighteen contract classes: BR-2A's
  fifteen and BR-2B's three.
* **nested-admissible only** — the class may appear *inside* a BR-2A graph and
  is encoded and revalidated there, but owns no BR-2A domain and is refused as a
  root. The three BR-1 classes that actually nest.

Handing a BR-1 contract to this encoder raises. That is deliberate: BR-1 owns
its own digest path, and a BR-1 identity must keep exactly one digest — the one
BR-1 computes — or every reference already issued against it breaks. BR-2 never
re-digests a BR-1 artifact under a BR-2 domain, and **never mutates the stored
BR-1 canonical artifact or its identity digest**.

Only what actually nests is admitted. The other six BR-1 classes are not in the
allow-list, because no BR-2A contract nests them; an allow-list entry for a
class nothing nests would be exactly the reserved-byte-space §05 prohibits.

Graph revalidation runs before any byte, and invokes no attacker code
--------------------------------------------------------------------
Before producing bytes, :func:`canonical_bytes` **revalidates the complete exact
contract graph at full depth**. For every reachable node, in this order:

1. identify the expected registered class from the sealed registry using
   identity comparison with ``is``;
2. prove ``type(node) is expected_class``;
3. **only then** invoke the trusted exact class's validation method —
   ``expected_class.__post_init__(node)``, never ``node.__post_init__()`` and
   never any method resolved through the instance.

The walk itself is **post-order**: steps 1 and 2 run for a node, then the whole
nested graph beneath it is revalidated, and only then does step 3 run for that
node. A node's own validator reaches through its nested predecessors — an
actor-separation check, a predecessor-``declared_outcome`` gate and a digest
binding all read fields of nested objects — so running it before those objects
were proved genuine would read attacker-supplied state through an unproved node.
Bottom-up closes that window: when any validator runs, every descendant has
already passed exact-type validation and its own invariants.

Step 3's spelling is the whole point. ``node.__post_init__()`` resolves through
the *instance's* type, so a hostile object would run **its own** validator —
which could do anything, including recording that it ran, mutating state, or
simply returning. Because step 2 has already proved the object *is* the exact
registered class, ``expected_class.__post_init__`` is guaranteed to be this
package's own code, and the hostile object never executes. This is the ordering
BR-1's ``_revalidate_exact_contract_graph`` implements; it is reproduced here
rather than re-derived, and ``tests/contract/test_hostile_objects.py`` asserts
on a **side-effect recorder** at every depth of the chain — proving the hostile
method was never called, not merely that an error was raised.

Revalidation catches a frozen instance corrupted after construction via
``object.__setattr__``: a swapped nested object of the wrong exact type, a
corrupted predecessor ``declared_outcome``, a corrupted actor identity, an
invalid timestamp — anything whose state could not have come from the public
constructors is refused here, **before a single byte is produced**, and before
any derived property reads any field. A revalidation failure never repairs the
object; it refuses it.

Independent verification
------------------------
:func:`canonical_bytes` and :func:`canonical_digest` are public and pure. A third
party holding a contract and this module can recompute any digest without package
internals; the package tests, the probe harness and the distribution verifier all
reconstruct the pinned digests from hand-written literal bytes and ``hashlib``
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
from typing import Any, Optional

from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate,
    BenchmarkContractError as _BR1BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkScope,
)

from .errors import (
    BenchmarkRegistryCanonicalizationError,
    BenchmarkRegistryContractError,
)

__all__ = [
    "BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION",
    "BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN",
    "BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN",
    "BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN",
    "BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN",
    "BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN",
    "BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN",
    "BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN",
    "BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS",
    "canonical_bytes",
    "canonical_digest",
    "canonical_domain_inventory",
]

#: The canonicalization rule-set version bound into every BR-2 digest.
#: Changing any rule in this module's docstring requires a new version string.
#: Deliberately **not** BR-1's version constant: two packages, two rule sets,
#: two version strings, even though the rules are currently identical — sharing
#: one string would mean a future BR-2 rule change silently re-versioned BR-1.
BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION = (
    "ugence.benchmark-registry-authority/canonicalization/v1"
)

_DOMAIN_PREFIX = "ugence.benchmark-registry-authority/"

# --------------------------------------------------------------------------- #
# One domain per artifact class this subphase actually ships. Eighteen classes
# and eighteen domains — BR-2A's fifteen and BR-2B's three — and no tag for
# an artifact that does not exist.
# --------------------------------------------------------------------------- #

#: Domain for :class:`~.envelopes.BenchmarkPublisherSubmissionEnvelope` — the
#: sole source of publisher identity in the entire chain.
BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "publisher-submission-envelope/v1"
)

#: Domain for :class:`~.envelopes.BenchmarkApprovalEnvelope` — the independent
#: approval assertion, which a BR-1 ``lifecycle_state=APPROVED`` can never
#: substitute for.
BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN = _DOMAIN_PREFIX + "approval-envelope/v1"

#: Domain for :class:`~.envelopes.BenchmarkRevocationEnvelope` — a revoker's
#: declared assertion, never a registry event and never a receipt.
BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "revocation-envelope/v1"
)

#: Domain for :class:`~.chain.BenchmarkSubmissionRecordPayload` — the initial
#: ``— → SUBMITTED`` payload, and the only one whose ``prev_event_digest`` is
#: ``None``.
BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "submission-record-payload/v1"
)

#: Domain for :class:`~.chain.BenchmarkAdmissionDecisionPayload` —
#: ``SUBMITTED → ADMITTED`` and ``SUBMITTED → REJECTED``, and nothing else.
BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "admission-decision-payload/v1"
)

#: Domain for :class:`~.chain.BenchmarkPostAdmissionRejectionEventPayload` —
#: ``ADMITTED → REJECTED``, a distinct transition with a distinct predecessor,
#: and therefore a distinct artifact class with its own byte space.
BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "post-admission-rejection-event-payload/v1"
)

#: Domain for :class:`~.chain.BenchmarkRegistrationEventPayload` —
#: ``ADMITTED → REGISTERED``.
BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "registration-event-payload/v1"
)

#: Domain for :class:`~.chain.BenchmarkRevocationEventPayload` —
#: ``REGISTERED → REVOKED``, terminal.
BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "revocation-event-payload/v1"
)

#: Domain for :class:`~.chain.BenchmarkConflictRecordPayload` — a refused
#: attempt, recorded outside the linear chain, appending no successor.
BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "conflict-record-payload/v1"
)

#: Domain for :class:`~.read_payloads.BenchmarkResolutionRecordPayload`.
BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "resolution-record-payload/v1"
)

#: Domain for :class:`~.read_payloads.BenchmarkHistoricalRecordPayload` — a
#: **different byte space** from the resolution payload, so a historical answer
#: can never be mistaken for a current one even at the digest level.
BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "historical-record-payload/v1"
)

#: Domain for :class:`~.requests.BenchmarkExactResolutionRequest`.
BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "exact-resolution-request/v1"
)

#: Domain for :class:`~.requests.BenchmarkHistoricalInspectionRequest` — the
#: only request type that carries an ``as_of``.
BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "historical-inspection-request/v1"
)

#: Domain for :class:`~.requests.PlatformRegistryScopeExpectation`.
BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "platform-registry-scope-expectation/v1"
)

#: Domain for :class:`~.requests.TenantRegistryScopeExpectation`.
BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "tenant-registry-scope-expectation/v1"
)

#: Domain for :class:`~.kernel.BenchmarkRegistrySnapshotAssertion`. BR-2B.
BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "registry-snapshot-assertion/v1"
)

#: Domain for :class:`~.kernel.BenchmarkTransitionPlan`. BR-2B.
BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "transition-plan/v1"
)

#: Domain for :class:`~.kernel.BenchmarkTransitionRefusal`. BR-2B.
BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN = (
    _DOMAIN_PREFIX + "transition-refusal/v1"
)

#: Every domain this distribution mints, pinned as an immutable tuple in
#: declaration order — BR-2A's fifteen, then BR-2B's three. Used by the
#: canonical-domain inventory and by the uniqueness assertion below. Append-only:
#: a later subphase adds at the end and never inserts or re-orders, because a
#: moved domain re-digests an artifact that was already addressed under the old
#: one.
BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS: tuple = (
    BENCHMARK_PUBLISHER_SUBMISSION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_APPROVAL_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_ENVELOPE_DIGEST_DOMAIN,
    BENCHMARK_SUBMISSION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_ADMISSION_DECISION_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_POST_ADMISSION_REJECTION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REGISTRATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_REVOCATION_EVENT_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_CONFLICT_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_RESOLUTION_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_RECORD_PAYLOAD_DIGEST_DOMAIN,
    BENCHMARK_EXACT_RESOLUTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_HISTORICAL_INSPECTION_REQUEST_DIGEST_DOMAIN,
    BENCHMARK_PLATFORM_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_TENANT_REGISTRY_SCOPE_EXPECTATION_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_SNAPSHOT_ASSERTION_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_PLAN_DIGEST_DOMAIN,
    BENCHMARK_TRANSITION_REFUSAL_DIGEST_DOMAIN,
)

# Two artifact classes sharing a domain would collapse two byte spaces into one.
# Asserted at import so it can never regress silently.
if len(set(BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS)) != len(
    BENCHMARK_REGISTRY_AUTHORITY_DIGEST_DOMAINS
):  # pragma: no cover - structural invariant
    raise BenchmarkRegistryContractError(
        "two BR-2A artifact classes were minted the same domain-separation tag; "
        "one domain per artifact class is what keeps their byte spaces distinct"
    )


def _build_exact_type_boundary():
    """Build the sealed contract-type registry and return its four closures.

    There is deliberately **no module-level name bound to the registry's backing
    dict or to a proxy wrapping it**. See the module docstring for why a
    ``MappingProxyType`` module global would not be a boundary at all.

    Lookup is by class **identity**, checked with ``is`` — never ``in``/``[]``
    on the backing dict, which would dispatch to ``__hash__``/``__eq__`` on
    whichever operand's type defines them. A class object's default
    ``__eq__``/``__hash__`` (inherited from :class:`type`) is already
    identity-based, but a **custom metaclass** can override the *type object's*
    ``__eq__``/``__hash__`` to make an unrelated class object compare equal to,
    and hash the same as, a genuine registered class — defeating a
    dict-membership check while never touching the registry's contents. ``is``
    has no dunder to override; it is the interpreter's own object-identity
    primitive.
    """

    types_: dict = {}
    sealed = False

    def record(
        cls: type, domain: Optional[str], *, root_canonicalizable: bool
    ) -> None:
        """Register ``cls`` as an exact BR-2A-admissible contract type.

        Private to this package's own module-initialization path. Refuses to run
        once :func:`seal` has been called, and refuses anything that is not
        itself a dataclass, so the registry can never be grown by a caller —
        including one holding a reference to this "private" function — after
        package import completes.
        """

        if sealed:
            raise BenchmarkRegistryContractError(
                "the BR-2A contract-type registry is sealed; no type may be "
                "registered after package initialization"
            )
        if not (isinstance(cls, type) and is_dataclass(cls)):
            raise BenchmarkRegistryContractError(
                "only a dataclass type may be registered as a BR-2A contract "
                f"type (got a {type(cls).__name__})"
            )
        if root_canonicalizable and domain is None:
            raise BenchmarkRegistryContractError(
                "a root-canonicalizable contract type must carry a domain"
            )
        if not root_canonicalizable and domain is not None:
            raise BenchmarkRegistryContractError(
                "a nested-admissible-only contract type must carry no BR-2A "
                "domain; BR-2 never re-digests a frozen BR-1 artifact under a "
                "BR-2 domain"
            )
        types_[cls] = (domain, root_canonicalizable)

    def seal() -> None:
        """Close the registry. Called exactly once, by :mod:`._seal`."""

        nonlocal sealed, types_
        types_ = MappingProxyType(dict(types_))
        sealed = True

    def entry_for(cls: type):
        """Return ``(domain, root_canonicalizable)`` for ``cls``, or ``None``.

        Iterates the registered classes and compares each with ``cls is
        registered_cls``. Dict iteration itself never consults ``__eq__`` or
        ``__hash__`` (those only matter for ``in``/``[]``/insertion), so this is
        immune to a metaclass forging either on a foreign class's type object.
        """

        for registered_cls, entry in types_.items():
            if cls is registered_cls:
                return entry
        return None

    def snapshot():
        """A read-only **copy** for introspection only (tests, probes, the
        published inventory).

        Never consulted by :func:`canonical_bytes` or :func:`canonical_digest`,
        which call :func:`entry_for` against the closure's own mapping. Mutating,
        replacing or discarding the returned mapping has no effect on what the
        encoder trusts, in either direction.
        """

        return MappingProxyType(dict(types_))

    return record, seal, entry_for, snapshot


(
    _register_contract_type,
    _seal_contract_types,
    _entry_for_contract_type,
    _contract_type_registry_snapshot,
) = _build_exact_type_boundary()

#: The exact frozen BR-1 classes that may appear **nested** inside a BR-2A
#: graph. Exactly the three that actually nest: the exact locator, and the scope
#: and applicability coordinates inside it. The other six BR-1 classes are
#: absent because no BR-2A contract nests them, and an allow-list entry for a
#: class nothing nests would be reserved byte space for an artifact that does
#: not exist.
_NESTED_BR1_CONTRACT_TYPES: tuple = (
    BenchmarkCoordinate,
    BenchmarkScope,
    BenchmarkApplicabilityCoordinate,
)

for _br1_cls in _NESTED_BR1_CONTRACT_TYPES:
    _register_contract_type(_br1_cls, None, root_canonicalizable=False)
del _br1_cls

_TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _require_nfc(value: str, path: str) -> str:
    if unicodedata.normalize("NFC", value) != value:
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: string is not Unicode NFC-normalized; BR-2 registry "
            "contracts reject non-canonical input rather than silently "
            f"normalizing it "
            f"({BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION})"
        )
    return value


def _format_datetime(value: datetime, path: str) -> str:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: a naive datetime is not a well-defined instant and must "
            "not enter a canonical byte sequence or a digest"
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
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: float is not canonicalizable — a governed coordinate "
            "must be an exact integer or a string (this also rejects "
            "nan/inf/-inf, which have no canonical JSON form)"
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
        if _entry_for_contract_type(type(value)) is None:
            raise BenchmarkRegistryCanonicalizationError(
                f"{path}: type {type(value).__name__!r} "
                f"(module {type(value).__module__!r}) is not a registered "
                "BR-2A contract type; only the exact classes this package "
                "defines, and the exact frozen BR-1 classes it nests, can be "
                "canonicalized — and neither the name nor the module of a "
                "foreign, subclassed or duck-typed object is ever treated as "
                "authority"
            )
        return {
            _require_nfc(f.name, f"{path}.{f.name}"): _to_canonical_obj(
                getattr(value, f.name), f"{path}.{f.name}"
            )
            for f in fields(value)
        }
    if isinstance(value, (list, tuple)):
        return [_to_canonical_obj(v, f"{path}[{i}]") for i, v in enumerate(value)]
    raise BenchmarkRegistryCanonicalizationError(
        f"{path}: type {type(value).__name__!r} is not canonicalizable; the "
        "encoder has no permissive fallback and never renders an unknown object"
    )


def _registered_entry(contract: Any, path: str):
    """Return ``(cls, domain, root_ok)`` iff ``contract`` is an exact registered
    contract instance.

    The only check that matters here is class **identity** against the sealed
    registry — never ``__name__``, never ``__module__``. A subclass fails this
    (subclassing produces a different class object even when it inherits every
    method), a foreign dataclass of the same name fails this, a same-named class
    whose ``__module__`` was forged to look like this package's still fails this,
    and a foreign class whose *metaclass* forges the class object's own equality
    or hash fails this too — because none of them **is** the exact object this
    package registered.
    """

    if not is_dataclass(contract) or isinstance(contract, type):
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: canonical_bytes expects a BR-2 registry contract "
            f"instance (got a {type(contract).__name__})"
        )
    cls = type(contract)
    entry = _entry_for_contract_type(cls)
    if entry is None:
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: type {cls.__name__!r} (module {cls.__module__!r}) is "
            "not a registered BR-2A contract type; only the exact classes this "
            "package defines, and the exact frozen BR-1 classes it nests, are "
            "admissible. Subclasses, same-named foreign dataclasses (including "
            "ones with a forged matching module or a metaclass forging the "
            "class object's own equality/hash), duck types and arbitrary "
            "dataclasses are all refused — class-name matching and class-object "
            "equality are never used as authority, only interpreter-level "
            "identity"
        )
    domain, root_ok = entry
    return cls, domain, root_ok


def _revalidate_exact_contract_graph(contract: Any, path: str) -> None:
    """Re-run every reachable node's own structural invariants, at full depth.

    The ordering is load-bearing and is spelled out in the module docstring:
    identify the expected class by identity, prove ``type(node) is
    expected_class``, and only then invoke ``expected_class.__post_init__(node)``
    — the *trusted exact class's* method, never one resolved through the
    instance. No attacker-controlled code is ever invoked, at any depth.

    Every nested contract passes exact-type validation **before any of its
    fields are read**, including by a derived property, which is what makes a
    corrupted predecessor ``declared_outcome`` or a corrupted actor identity a
    refusal rather than an input to a digest.

    Nested frozen BR-1 contracts are revalidated the same way, against BR-1's own
    ``__post_init__`` — which raises BR-1's error type, caught here and re-raised
    as a BR-2 canonicalization refusal carrying the path. BR-1's rules stay
    BR-1's; BR-2 neither re-implements nor relaxes them.
    """

    cls, _domain, _root_ok = _registered_entry(contract, path)
    # Post-order, and that ordering is load-bearing. Every nested node is proved
    # to be an exact registered class and revalidated **before** this node's own
    # validator runs, because this node's ``__post_init__`` — and any derived
    # property that validator reads — may reach straight through the nested
    # graph. Validating this node first would mean its actor-separation checks,
    # its predecessor-outcome gate and its digest bindings all read fields of
    # objects nobody had yet proved were genuine contracts, which is precisely
    # the "before any of its fields are read, including by a derived property"
    # requirement. Bottom-up removes the window entirely.
    for f in fields(contract):
        _revalidate_value(getattr(contract, f.name), f"{path}.{f.name}")
    try:
        cls.__post_init__(contract)
    except (
        BenchmarkRegistryContractError,
        _BR1BenchmarkContractError,
    ) as exc:
        raise BenchmarkRegistryCanonicalizationError(
            f"{path}: {cls.__name__} failed structural revalidation before "
            f"canonicalization ({exc}); an object whose state could not have "
            "passed its own public constructor is refused rather than "
            "canonicalized"
        ) from exc


def _revalidate_value(value: Any, path: str) -> None:
    if is_dataclass(value) and not isinstance(value, type):
        _revalidate_exact_contract_graph(value, path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _revalidate_value(item, f"{path}[{index}]")


def canonical_bytes(contract: Any) -> bytes:
    """Return the exact UTF-8 bytes :func:`canonical_digest` is computed over.

    ``contract`` must be an exact instance of one of the eighteen registered
    **root-canonicalizable** contract classes — BR-2A's fifteen and BR-2B's
    three — never a subclass, never a same-named foreign dataclass, never a
    duck type, and never a frozen BR-1 contract, which owns its own digest
    path and must keep exactly one digest.
    Membership is decided by class identity against the sealed registry, never
    by name.

    Before any byte is produced the complete contract graph reachable from
    ``contract`` is revalidated at full depth, so an instance corrupted after
    construction via ``object.__setattr__`` into a state its public constructor
    would have refused is refused here too.

    Two contracts that compare equal always produce byte-identical output,
    including when their instants were written with different UTC offsets::

        if a == b:
            assert canonical_bytes(a) == canonical_bytes(b)

    Two contracts differing in **any** load-bearing coordinate always produce
    different output — which for the whole administrative chain is asserted
    substitution by substitution by
    ``tests/contract/test_chain_substitution.py``.
    """

    cls, domain, root_ok = _registered_entry(contract, "$")
    if not root_ok:
        raise BenchmarkRegistryCanonicalizationError(
            f"$: {cls.__name__} is a frozen BR-1 contract, admissible only "
            "**nested** inside a BR-2A graph. BR-2 never re-digests a BR-1 "
            "artifact under a BR-2 domain: a BR-1 identity must keep exactly "
            "one digest — the one BR-1 computes — or every reference already "
            "issued against it breaks. Use the BR-1 package's own "
            "canonical_bytes for a BR-1 contract"
        )
    _revalidate_exact_contract_graph(contract, "$")
    framed = {
        "canonicalization": BENCHMARK_REGISTRY_AUTHORITY_CANONICALIZATION_VERSION,
        "domain": domain,
        "type": cls.__name__,
        "body": _to_canonical_obj(contract, "$"),
    }
    return json.dumps(
        framed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_digest(contract: Any) -> str:
    """Return the bare lowercase 64-char sha-256 hex digest of the canonical bytes.

    The digest is computed **solely** from :func:`canonical_bytes` — no other
    input, no salt, no clock, no side channel. It is a structural fingerprint.

    It is **not** approval evidence, not a publisher signature, not a
    registration, not an admission and not a resolution. ADR B-5 rules that
    approval binds a content digest rather than being one, and B-9 that
    "possession is not validity; retrieval is not resolution". Computing or
    matching this digest establishes only that two structures are the same
    structure.
    """

    return hashlib.sha256(canonical_bytes(contract)).hexdigest()


def canonical_domain_inventory() -> MappingProxyType:
    """Return the live class-name → domain inventory, read-only.

    Built from the sealed registry itself rather than from a hand-maintained
    list, so the published ``canonical_domain_inventory.json`` is asserted
    against the *actual* boundary the encoder enforces and cannot drift from it.

    Nested-admissible-only classes — the frozen BR-1 contracts — appear with a
    domain of ``None``, which is what "this class owns no BR-2A byte space"
    looks like in the inventory.
    """

    return MappingProxyType(
        {
            cls.__name__: domain
            for cls, (domain, _root_ok) in (
                _contract_type_registry_snapshot().items()
            )
        }
    )
