"""Inert ports and an inert consistency descriptor. **No implementation ships.**

Four :class:`typing.Protocol` declarations name the seams a registry will need,
and **nothing in this package satisfies any of them**:

* :class:`BenchmarkRegistryStorePort` — the durable-store seam (D-14).
* :class:`BenchmarkPublisherTrustDirectoryPort` — role-scoped anchor resolution
  (D-25, D-26). Formerly a Boolean entitlement predicate.
* :class:`BenchmarkApprovalVerifierPort` — the three verification seams
  (D-24, D-26), each returning a distinct exact verified result. Formerly two
  methods returning ``bool``.
* :class:`BenchmarkClockPort` — the one injected authoritative clock (D-11).

What is deliberately absent
---------------------------
No port implementation. **No deny-all implementation** — not even that one: a
deny-all verifier is BR-2C's, where an injected verifier and a test proving
nothing can reach ``ADMITTED`` belong together. BR-2B has no verifier to default,
because it performs no authoritative act for one to gate. No in-memory store, no adapter
registry, no identity allow-list executing adapter admission, and no production
composition root.

``tests/contract/test_confusable_and_ports.py`` asserts that **no concrete class in
this package satisfies any port** — structurally, by method-name coverage, so a
class cannot satisfy a port by accident either.

A Protocol is a shape, not a capability. Declaring the shape a clock must have
does not read a clock, and BR-2A reads none: a source-tree scan asserts it.

Why there is no ``is_production_grade`` flag
---------------------------------------------
Revision 1 proposed one. **D-15 retires it.** An unavailable consistency
guarantee must not be represented as a Boolean capability that can be flipped,
because a settable flag is one assignment away from a production deployment on an
in-memory store.

:class:`BenchmarkRegistryStoreConsistencyDescriptor` replaces it. It carries a
single field — a :class:`~.enums.BenchmarkRegistryConsistencyScope` with exactly
one ratified member — and derives all seven guarantee answers from it as
read-only properties. **There is no flag to set, because there is no flag**, and
an over-claiming descriptor is not merely refused but unconstructible: there is
no ``DURABLE`` scope member to pass.

The ratified enforcement mechanism is documented here and implemented nowhere
here: the production composition root admits only an allow-listed set of adapter
classes **checked by interpreter identity** — BR-1's sealed-registry ``is``
pattern, which no subclass, same-named lookalike or metaclass can defeat — and
raises :class:`~.errors.BenchmarkRegistryCompositionError` for anything else.
§17 permits this package to *state* that requirement and forbids it to
*implement or simulate* it, so the allow-list, the composition root and the
adapter admission path are all absent. Documenting a deferred capability is
permitted; shipping an executable placeholder for it is not.

The consistency claim, disclaimed in the contract
--------------------------------------------------
BR-2 claims **process-local atomicity and read-after-write behaviour, and
nothing more**. The five things it explicitly disclaims — durability,
multi-process coordination, distributed strong consistency, eventual-consistency
safety, and cross-process atomic revocation — are disclaimed **in the contract**,
as typed properties a consumer can read, not merely in prose a consumer might not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ._validation import require_enum_member
from .chain import (
    BenchmarkRegistrationEventPayload,
    BenchmarkRevocationEventPayload,
    BenchmarkSubmissionRecordPayload,
)
from .enums import (
    BenchmarkRegistryConsistencyClaim,
    BenchmarkRegistryConsistencyScope,
)
from .envelopes import (
    BenchmarkApprovalEnvelope,
    BenchmarkPublisherSubmissionEnvelope,
)
from .envelopes import BenchmarkRevocationEnvelope
from .enums import BenchmarkTrustRole
from .read_payloads import BenchmarkHistoricalRecordPayload
from .requests import BenchmarkHistoricalInspectionRequest
from .trust import (
    BenchmarkApprovalVerifiedResult,
    BenchmarkPublisherVerifiedResult,
    BenchmarkRevocationVerifiedResult,
    BenchmarkTrustAnchorRecord,
)

__all__ = [
    "BenchmarkRegistryStorePort",
    "BenchmarkPublisherTrustDirectoryPort",
    "BenchmarkApprovalVerifierPort",
    "BenchmarkClockPort",
    "BenchmarkRegistryStoreConsistencyDescriptor",
    "BENCHMARK_REGISTRY_DECLARED_CONSISTENCY",
    "BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES",
    "BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT",
]


@runtime_checkable
class BenchmarkRegistryStorePort(Protocol):
    """The append-only registry store seam. **Declared here, implemented nowhere.**

    D-14 as amended: BR-2A defines the port; **BR-2D** ships the clearly named *process-local*
    in-memory adapter; production composition raises a typed startup error when
    handed the non-production adapter — a warning or a docstring is
    insufficient. No Postgres, no reuse of Risk Authority persistence, and no
    durable backend chosen before ADR DD-10 is ratified.

    The method signatures name the shape a store must have. They are
    ``...``-bodied Protocol members: calling one on this class does nothing,
    because there is nothing to call — a Protocol is not instantiable and this
    package defines no class that satisfies it.
    """

    def append_submission(
        self, record: BenchmarkSubmissionRecordPayload
    ) -> None:
        """Append a submission record to the append-only log."""
        ...

    def append_registration(
        self, event: BenchmarkRegistrationEventPayload
    ) -> None:
        """Claim the exact locator slot and append a registration event."""
        ...

    def append_revocation(self, event: BenchmarkRevocationEventPayload) -> None:
        """Append a revocation event. Terminal for the locator."""
        ...

    def read_historical(
        self, request: BenchmarkHistoricalInspectionRequest
    ) -> Optional[BenchmarkHistoricalRecordPayload]:
        """Read history at the request's mandatory ``as_of``."""
        ...

    def consistency(self) -> "BenchmarkRegistryStoreConsistencyDescriptor":
        """Return the adapter's frozen consistency descriptor."""
        ...


@runtime_checkable
class BenchmarkPublisherTrustDirectoryPort(Protocol):
    """The role-scoped anchor **resolution** seam. **Implemented nowhere.**

    D-25 replaces Boolean entitlement with exact anchor resolution: the seam
    resolves an **immutable role-scoped anchor record** rather than answering
    true or false. A Boolean answered *entitled?* and nothing else, so a caller
    could not learn which key, under which role, valid over which interval, in
    which status — and a verified result had nowhere to bind the anchor revision
    §35.1's BR-2C row requires it to bind.

    D-26 makes the seam **role-scoped in its parameters**. Publisher, approver
    and revoker occupy logically separate anchor namespaces; they may share one
    physical directory implementation, but an anchor authorized for one role
    **never** authorizes another automatically, so the role is a mandatory
    argument rather than something a shared directory may infer.

    D-04: the **composition root** owns and configures benchmark trust anchors,
    under seven binding constraints — exact deny-all default; no registry-minted
    anchors; no Policy Authority ownership; no import of the trusted-evidence
    layer's trust-anchor directory; no exception to ADR §23; **no second hidden
    trust store inside the registry**; and production startup fails closed when a
    production trust resolver is absent.

    This package holds no anchors, mints none, resolves none, parses no key
    material and imports no other authority's directory. There is no second
    trust store here because there is no first one — declaring the shape a
    resolver must have does not resolve anything, and a Protocol is not
    instantiable.
    """

    def resolve_anchor(
        self,
        role: BenchmarkTrustRole,
        identity: str,
        key_id: str,
    ) -> Optional[BenchmarkTrustAnchorRecord]:
        """Resolve the anchor record for an exact (role, identity, key) triple.

        Returns the record **as it stands**, with its own status and validity
        interval intact. It deliberately takes **no trusted instant and performs
        no lifecycle evaluation**: D-27 requires revoked, disabled, not-yet-valid
        and expired to stay distinguishable, and a resolver that filtered on the
        instant would collapse all four into an indistinguishable absence. The
        evaluation belongs to the verification seam, which binds its outcome and
        its reason into the verified result where D-27 requires the distinctions
        to be preserved.

        Never called here.
        """
        ...


@runtime_checkable
class BenchmarkApprovalVerifierPort(Protocol):
    """The independent approval-verification seam. **Implemented nowhere.**

    D-03: a verified publisher signature is **mandatory before admission**. An
    unsigned, malformed, unknown-key, revoked-key or invalidly signed artifact
    cannot become ``ADMITTED`` or ``REGISTERED``.

    BR-2A may define this contract and **must not implement or simulate
    signature verification** — including a permissive placeholder, a
    "development" verifier, or a :class:`NotImplementedError` body pretending to
    be an implementation. **BR-2B ships no verifier at all**; BR-2C injects one
    whose default is exact deny-all and supplies the audited one, reusing neither the Policy
    Authority nor the Risk Authority Ed25519 implementation.

    **No verifier ships at this contract slice either, and none has been
    audited.** D-32 waives the distinct in-repo reviewer for BR-2C only and
    narrows "independently audited" to an *external cryptographic audit of the
    verifier*, which remains a hard precondition to any production use. The
    engineering half of §35.1's blocker is untouched by that waiver.

    Three seams, not two
    ---------------------
    D-24 replaces both Boolean returns with **distinct exact verified-result
    types**, and D-26 adds a third method for the revocation seam. Each returns
    its own type: a result about a revoker can never be handed to a caller
    expecting one about a publisher, which §17's rule 10 requires and which one
    shared return type would leave to call-site discipline.

    Every seam takes the **explicit trusted instant** as an argument. D-28
    records the consequence for D-11 so it is not discovered late: BR-2C ships
    no clock, so the trusted instant is an *input* to verification and never a
    clock read. The authoritative clock arrives at BR-2D and D-11 is unamended.
    """

    def verify_publisher_submission(
        self,
        envelope: BenchmarkPublisherSubmissionEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkPublisherVerifiedResult:
        """Verify the envelope's detached signature. Never called here.

        Returns an exact result binding the envelope digest, the signer role,
        identity and key, the profile, the anchor revision, ``trusted_instant``,
        the outcome and any refusal reason — never a ``bool``, which had nowhere
        to carry any of them and was indistinguishable from a cached copy of
        itself (D-21, D-24).
        """
        ...

    def verify_approval(
        self,
        envelope: BenchmarkApprovalEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkApprovalVerifiedResult:
        """Verify the approval's detached signature. Never called here.

        A distinct result type from the publisher seam's, because D-02 forbids a
        publisher's own signature from standing where an independent approver's
        is required.
        """
        ...

    def verify_revocation(
        self,
        envelope: BenchmarkRevocationEnvelope,
        trusted_instant: datetime,
    ) -> BenchmarkRevocationVerifiedResult:
        """Verify the revocation assertion's signature. Never called here.

        Added by D-26, which verifies revokers at BR-2C under role separation.
        **Verifying a revoker's assertion is not appending a revocation**:
        through BR-2C registry events remain unsigned and non-existent under
        D-12, and nothing in this package revokes anything.
        """
        ...


@runtime_checkable
class BenchmarkClockPort(Protocol):
    """The one injected authoritative clock. **Read by nothing in BR-2A.**

    D-11: one injected authoritative clock owns ``recorded_at``.
    Publisher-supplied time is evidence, never registry time. Caller-supplied
    ``as_of`` is permitted **only** on the historical-inspection API, never
    bypasses ``DENY_ALWAYS`` and never influences trusted exact resolution.

    **Zero clock skew.** No non-zero tolerance precedent exists anywhere in this
    repository — the only tolerance found is a policy-supplied
    ``clock_skew_tolerance_s: int = 0`` in a non-governance capability — so none
    is invented. No future-dated registration is permitted, and a revocation's
    ``effective_at`` is validated against registry-observed time and against its
    own signed record; it can never be used to reopen or reverse a revocation.

    **BR-2A reads no clock at all**, and this Protocol does not change that: it
    is a shape a later milestone's injected clock must have.
    """

    def now(self) -> datetime:
        """The authoritative present instant, timezone-aware. Never called here."""
        ...


#: The five guarantees BR-2 explicitly disclaims, pinned so the disclaimer is
#: enumerable rather than only readable.
BENCHMARK_REGISTRY_DISCLAIMED_GUARANTEES: tuple = (
    "durability",
    "multi_process_coordination",
    "distributed_strong_consistency",
    "eventual_consistency_safety",
    "cross_process_atomic_revocation",
)


@dataclass(frozen=True)
class BenchmarkRegistryStoreConsistencyDescriptor:
    """A frozen typed consistency descriptor. **Never a flippable Boolean.**

    One field: the declared :class:`~.enums.BenchmarkRegistryConsistencyScope`,
    whose enum has exactly one ratified member. Every guarantee answer is a
    **derived read-only property** computed from that scope, so:

    * there is no Boolean capability to flip;
    * an over-claiming descriptor is **unconstructible**, not merely refused —
      there is no ``DURABLE`` scope member to pass;
    * a consumer reads the disclaimers off the contract rather than out of prose.

    Deliberately **not canonicalizable**: it is a declaration *about a future
    port*, not an artifact in the registry's chain, so it mints no
    domain-separation tag. Minting one would be reserving byte space for an
    artifact that does not exist, which §05 prohibits. The published
    contract inventory marks it accordingly.
    """

    #: The declared consistency scope. One ratified member exists.
    scope: BenchmarkRegistryConsistencyScope = field(
        default=BenchmarkRegistryConsistencyScope.PROCESS_LOCAL_ONLY
    )

    def __post_init__(self) -> None:
        require_enum_member(
            self.scope, BenchmarkRegistryConsistencyScope, "scope"
        )

    @property
    def process_local_atomicity(self) -> BenchmarkRegistryConsistencyClaim:
        """Claimed within the declared scope. One of the two things BR-2 claims."""

        return BenchmarkRegistryConsistencyClaim.CLAIMED_WITHIN_DECLARED_SCOPE

    @property
    def read_after_write(self) -> BenchmarkRegistryConsistencyClaim:
        """Claimed within the declared scope. The other thing BR-2 claims."""

        return BenchmarkRegistryConsistencyClaim.CLAIMED_WITHIN_DECLARED_SCOPE

    @property
    def durability(self) -> BenchmarkRegistryConsistencyClaim:
        """**Explicitly disclaimed.** Nothing here survives process exit."""

        return BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED

    @property
    def multi_process_coordination(self) -> BenchmarkRegistryConsistencyClaim:
        """**Explicitly disclaimed.** Two processes coordinate through nothing."""

        return BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED

    @property
    def distributed_strong_consistency(
        self,
    ) -> BenchmarkRegistryConsistencyClaim:
        """**Explicitly disclaimed.** No distributed guarantee of any strength."""

        return BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED

    @property
    def eventual_consistency_safety(self) -> BenchmarkRegistryConsistencyClaim:
        """**Explicitly disclaimed.** Not even the weak guarantee is offered."""

        return BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED

    @property
    def cross_process_atomic_revocation(
        self,
    ) -> BenchmarkRegistryConsistencyClaim:
        """**Explicitly disclaimed.** A revocation is atomic in one process only.

        The most consequential disclaimer of the five: a revocation that is not
        atomic across processes means one process can still resolve a benchmark
        another has revoked. Saying so in the contract is what stops a
        deployment from assuming otherwise.
        """

        return BenchmarkRegistryConsistencyClaim.EXPLICITLY_DISCLAIMED


#: The declared consistency of any BR-2 store, at every subphase this
#: distribution currently reaches. A module-level frozen instance, not a
#: configurable one.
BENCHMARK_REGISTRY_DECLARED_CONSISTENCY = (
    BenchmarkRegistryStoreConsistencyDescriptor()
)

#: The ratified production-adapter admission requirement, **documented and not
#: implemented**. §17 permits this package to state the requirement and forbids
#: it to implement or simulate it, so there is no allow-list, no registry of
#: adapters and no composition root anywhere in this distribution.
BENCHMARK_PRODUCTION_ADAPTER_ADMISSION_REQUIREMENT = (
    "The production composition root admits only an allow-listed set of adapter "
    "classes, checked by interpreter identity (`cls is AllowedAdapter`) — the "
    "sealed-registry pattern no subclass, same-named lookalike or metaclass can "
    "defeat — and raises BenchmarkRegistryCompositionError for anything else. "
    "There is no settable flag, because D-15 retires the flag: an unavailable "
    "consistency guarantee must never be a Boolean one assignment away from a "
    "production deployment on an in-memory store. This requirement is stated "
    "here and implemented nowhere in this distribution; BR-2D owns the "
    "composition root that enforces it."
)
