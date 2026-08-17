"""Canonical evidence identity and coordinates (ADR §9, §12, §14, §15).

The question these contracts answer is *which exact evidence item is this* — and
nothing else. They answer it precisely enough that a favourable evidence item
for one tenant, context, subject, assessed system, purpose or usage scope is
**mechanically detectable when replayed under another**, because every one of
those coordinates participates in :meth:`CanonicalEvidenceIdentity.canonical_digest`
(ADR §26.5).

What a canonical evidence identity proves
-----------------------------------------
Exactly one thing: **internal consistency and digest-bound identity.** That is
ADR §12 stage 1, ``STRUCTURALLY_CONSTRUCTIBLE``, and it "establishes nothing
about authenticity".

What it does **not** prove
--------------------------
Stages 2-6 of §12, every one of them:

* that any signature verifies, or that any key is trusted (stage 2);
* that the chain of custody is intact or the producer authorized (stage 3);
* that the tenant/context/subject/system coordinates it *declares* are the ones
  it truly describes (stage 4) — declaring a tenant is not being bound to it;
* that it is unrevoked or fresh at any instant (stage 5);
* that it is sufficient for any policy requirement (stage 6), which §12 rules
  requirement-relative and therefore never a property of evidence at all.

:attr:`CanonicalEvidenceIdentity.structural_status` is accordingly a permanently
``STRUCTURAL_UNVERIFIED`` **property**, not a field: there is no constructor
argument, assignment or subclass hook that can raise it. Raising it requires a
verifier, trust anchors and signature verification — **TEV-2** (ADR §30).

Why the verification-side coordinates are absent
------------------------------------------------
ADR §9 lists seventeen coordinates a *verification result* binds. Rows 14-16 —
**verifier authority identity and key identifier**, **verification protocol and
version**, **verification status and reason codes** — and row 6, the **explicit
verification instant**, describe an act TAP performs. No TEV-1 object performs
it. Carrying those fields on a caller-constructible contract would produce
precisely the artifact ADR §10 forbids consumers from trusting: a structurally
valid object naming an authority, a protocol and a status that nobody issued.
They belong to the signed receipt of §13, which ships with the signing that
makes it meaningful (E-11, TEV-2). ADR §13.3 is explicit that there is no
"trusted but unsigned" state.

Rows 1-5 and 7-13 and 17 — the evidence-side coordinates — are here.

Why geography / domain / intended outcome are here, and how
-----------------------------------------------------------
UVI ADR D-13 makes these load-bearing rather than cosmetic wherever
applicability depends on them, and ADR §15 rows 6-8 ratify the representation:
"required where applicability depends on it; explicitly ``NOT_APPLICABLE``
otherwise — **never omitted**", because "an explicit ``NOT_APPLICABLE`` is a
decision on the record; an omitted field is not". They are therefore carried as
mandatory :class:`ApplicabilityCoordinate` values, which make omission
unrepresentable.

Why purpose and usage scope are opaque tokens
---------------------------------------------
ADR §7.1 row 5 gives TAP "scope verification — tenant, assessment context,
subject, assessed system", and §7 does not enumerate an evidence-side purpose or
usage-scope vocabulary. No such enumeration is ratified anywhere in the ADR, so
none is invented: they are carried as **opaque required tokens**, exactly the
discipline the merged ``AssessedSystemBinding`` applies to
``deployment_environment_ref`` ("no environment enumeration is ratified anywhere
in the repository, so none is invented"). Once one is ratified, the token points
at it with no shape change here.

Why the assessed-system binding is a reference and a digest
-----------------------------------------------------------
ADR §14 is unambiguous: **Governance Contracts owns ``AssessedSystemBinding``**,
defined exactly once, and this ADR "does not move it, redefine it, or extend
it". TAP "may verify evidence against the binding's exact reference and digest"
without becoming the owner of assessed-system identity. This package therefore
carries the reference and digest **by value**, imports nothing, and defines no
competing binding type. ADR §23 also requires TAP to depend on
``governance-contracts`` *at most* — and DD-2, which decides what lands in that
leaf, is explicitly blocked on "the concrete contract shapes from TEV-1/BR-1",
so TEV-1 takes the zero-dependency option and leaves DD-2 open rather than
pre-empting it.

No ``SystemManifest`` is defined, named as owned, or placed here. Its home
remains the open decision at DD-11.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ._validation import (
    normalize_reference_tuple,
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_exact_type,
    require_identifier,
    require_optional_aware_datetime,
    require_optional_digest,
    require_strictly_before,
)
from .canonical import canonical_bytes, canonical_digest
from .enums import (
    EVIDENCE_TRUST_STAGE_ORDER,
    ApplicabilityDeclaration,
    EvidenceLifecycleState,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
)
from .errors import TrustedEvidenceContractError
from .reasons import TrustedEvidenceRefusalReason

__all__ = [
    "ApplicabilityCoordinate",
    "EvidenceSchemaRef",
    "EvidenceObservation",
    "EvidenceScopeBinding",
    "EvidenceProvenanceChain",
    "CanonicalEvidenceIdentity",
]


@dataclass(frozen=True)
class ApplicabilityCoordinate:
    """A coordinate that is either applicable with a value, or explicitly not.

    ADR §15's ruling made structural: there is no way to *omit* the coordinate,
    only to declare it inapplicable on the record. The declaration and the value
    are cross-checked, so ``APPLICABLE`` with no value and ``NOT_APPLICABLE``
    with a value are both refused — neither is silently repaired into the other.

    ``NOT_APPLICABLE`` and ``APPLICABLE`` produce different canonical bytes, so
    a decision to declare a coordinate inapplicable is itself digest-bound.
    """

    declaration: ApplicabilityDeclaration
    value: str = ""

    def __post_init__(self) -> None:
        require_exact_type(
            self.declaration,
            ApplicabilityDeclaration,
            "ApplicabilityCoordinate.declaration",
        )
        text = require_canonical_str(
            self.value, "ApplicabilityCoordinate.value", allow_empty=True
        )
        if self.declaration is ApplicabilityDeclaration.APPLICABLE and not text:
            raise TrustedEvidenceContractError(
                "ApplicabilityCoordinate declared APPLICABLE must carry a "
                "non-empty value; declaring applicability without naming the "
                "value it applies to records no decision"
            )
        if self.declaration is ApplicabilityDeclaration.NOT_APPLICABLE and text:
            raise TrustedEvidenceContractError(
                "ApplicabilityCoordinate declared NOT_APPLICABLE must carry an "
                f"empty value (got {text!r}); a value under NOT_APPLICABLE is "
                "an ambiguous coordinate, not a recorded decision"
            )

    @classmethod
    def applicable(cls, value: str) -> "ApplicabilityCoordinate":
        """Declare the coordinate applicable, with ``value``."""

        return cls(declaration=ApplicabilityDeclaration.APPLICABLE, value=value)

    @classmethod
    def not_applicable(cls) -> "ApplicabilityCoordinate":
        """Declare the coordinate inapplicable — a decision, not an omission."""

        return cls(declaration=ApplicabilityDeclaration.NOT_APPLICABLE, value="")


@dataclass(frozen=True)
class EvidenceSchemaRef:
    """Evidence schema identity and version (ADR §9 row 2).

    Both halves are required. A schema id without a version does not name a
    shape, and ADR §11 row 12 makes an unsupported schema a fail-closed refusal
    — which is undecidable if the version was never stated.
    """

    schema_id: str
    schema_version: str

    def __post_init__(self) -> None:
        require_identifier(self.schema_id, "EvidenceSchemaRef.schema_id")
        require_identifier(self.schema_version, "EvidenceSchemaRef.schema_version")


@dataclass(frozen=True)
class EvidenceObservation:
    """Observation and source metadata (ADR §9 rows 4-5).

    ``observed_from`` alone names an observation **instant**; ``observed_from``
    with ``observed_to`` names a half-open observation **window**
    ``[observed_from, observed_to)`` (ADR §17.9). ``None`` for ``observed_to``
    is therefore a meaningful, distinct value — "this is an instant" — never a
    stand-in for a missing bound.

    ``collected_at`` is distinct from the observation and is required. ADR §9
    keeps collection and observation apart for the same reason it keeps
    observation and verification apart: collapsing them destroys the ability to
    reason about how stale a value was when it was picked up.

    ``issuer_id`` is the ADR §9 "issuer identity when distinct" coordinate. It
    defaults to ``""`` meaning *not distinct from the producer*, and an
    ``issuer_id`` equal to ``producer_id`` is **refused** — that would be two
    byte sequences for one fact, and the digest must not depend on which
    spelling a caller chose.

    Naming a producer establishes nothing about it. ADR §10.3: "a string naming
    a verifier is not that verifier's signature", and the same holds for a
    producer or an issuer. Producer authorization is a trust-anchor question
    (E-5) and is TEV-2's.
    """

    producer_id: str
    collected_at: datetime
    observed_from: datetime
    observed_to: Optional[datetime] = None
    issuer_id: str = ""

    def __post_init__(self) -> None:
        require_identifier(self.producer_id, "EvidenceObservation.producer_id")
        issuer = require_canonical_str(
            self.issuer_id, "EvidenceObservation.issuer_id", allow_empty=True
        )
        if issuer and issuer == self.producer_id:
            raise TrustedEvidenceContractError(
                "EvidenceObservation.issuer_id is the 'issuer when distinct' "
                "coordinate (ADR §9); an issuer equal to the producer is not "
                "distinct and must be left empty, so one fact has one encoding"
            )
        require_aware_datetime(self.collected_at, "EvidenceObservation.collected_at")
        require_aware_datetime(self.observed_from, "EvidenceObservation.observed_from")
        require_optional_aware_datetime(
            self.observed_to, "EvidenceObservation.observed_to"
        )
        if self.observed_to is not None:
            require_strictly_before(
                self.observed_from,
                self.observed_to,
                "EvidenceObservation.observed_from",
                "EvidenceObservation.observed_to",
                "the observation window is half-open [observed_from, observed_to)",
            )
        if self.collected_at < self.observed_from:
            raise TrustedEvidenceContractError(
                "EvidenceObservation.collected_at precedes .observed_from; "
                "collection cannot occur before the observation it collects"
            )

    @property
    def is_observation_window(self) -> bool:
        """Whether this names a window rather than a single instant."""

        return self.observed_to is not None


@dataclass(frozen=True)
class EvidenceScopeBinding:
    """The scope coordinates TAP verifies against (ADR §7.1 row 5, §9 rows 7-10).

    Tenant, assessment context, subject, assessed system, declared purpose and
    declared usage scope. Every one participates in the enclosing identity's
    digest, so replaying an evidence item across any of them is mechanically
    detectable (ADR §26.5).

    ``tenant_id`` is mandatory and is never inferred or defaulted (ADR §27.1).

    ``subject_ref`` is the ADR §9 row 9 "subject, **or** an opaque
    subject-context reference" coordinate. It stays opaque here: §14.6 keeps
    ``canonical_subject_context_ref`` "an opaque, digest-bound bridge" and
    §27.4 requires that no subject payload cross this seam.

    The assessed-system binding is **explicitly present or explicitly absent**.
    ADR §9 row 10 admits absence only "where the evidence is system-independent,
    and its absence is explicit, never defaulted", so
    ``assessed_system_applicability`` has no default and must be stated. Under
    ``APPLICABLE`` both the reference and its digest are required — a reference
    without its digest is a floating reference, and a digest without a reference
    names nothing (the co-required rule the merged ``AssessedSystemBinding``
    already applies to its manifest pair). Under ``NOT_APPLICABLE`` both must be
    empty.
    """

    tenant_id: str
    assessment_context_ref: str
    assessment_context_digest: str
    subject_ref: str
    assessment_purpose_ref: str
    usage_scope_ref: str
    assessed_system_applicability: ApplicabilityDeclaration
    assessed_system_binding_ref: str = ""
    assessed_system_binding_digest: str = ""

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "assessment_context_ref",
            "subject_ref",
            "assessment_purpose_ref",
            "usage_scope_ref",
        ):
            require_identifier(getattr(self, name), f"EvidenceScopeBinding.{name}")
        require_digest(
            self.assessment_context_digest,
            "EvidenceScopeBinding.assessment_context_digest",
        )
        require_exact_type(
            self.assessed_system_applicability,
            ApplicabilityDeclaration,
            "EvidenceScopeBinding.assessed_system_applicability",
        )
        ref = require_canonical_str(
            self.assessed_system_binding_ref,
            "EvidenceScopeBinding.assessed_system_binding_ref",
            allow_empty=True,
        )
        digest = require_optional_digest(
            self.assessed_system_binding_digest,
            "EvidenceScopeBinding.assessed_system_binding_digest",
        )
        applicable = (
            self.assessed_system_applicability is ApplicabilityDeclaration.APPLICABLE
        )
        if applicable and not (ref and digest):
            raise TrustedEvidenceContractError(
                "EvidenceScopeBinding declares the assessed-system binding "
                "APPLICABLE, so assessed_system_binding_ref and "
                "assessed_system_binding_digest are both required: a reference "
                "must be digest-bound, and a digest must name the artifact it "
                "was computed over (ADR §9 row 10, §14.2)"
            )
        if not applicable and (ref or digest):
            raise TrustedEvidenceContractError(
                "EvidenceScopeBinding declares the assessed-system binding "
                "NOT_APPLICABLE, so assessed_system_binding_ref and "
                "assessed_system_binding_digest must both be empty; system "
                "independence is a recorded decision, not a half-filled binding"
            )

    @property
    def scope_identity(self) -> tuple:
        """The coordinate tuple that must not be reused across scopes.

        Two evidence items differing in any element of this tuple are different
        evidence items, and their canonical digests differ accordingly.
        """

        return (
            self.tenant_id,
            self.assessment_context_ref,
            self.assessment_context_digest,
            self.subject_ref,
            self.assessment_purpose_ref,
            self.usage_scope_ref,
            self.assessed_system_binding_ref,
            self.assessed_system_binding_digest,
        )


@dataclass(frozen=True)
class EvidenceProvenanceChain:
    """Provenance / chain-of-custody references (ADR §9 row 13, §7.1 row 7).

    ``chain_ref`` names the chain; ``custody_refs`` are its links **in order**,
    because a chain of custody in a different order is a different chain. The
    tuple is therefore order-sensitive in the digest, and duplicate links are
    refused — a chain may not name the same link twice.

    A caller-supplied ``list`` is defensively copied into a ``tuple`` before it
    reaches the frozen contract, so later mutation of the caller's list cannot
    alter the contract or its digest (ADR §17.7's defensive-copy discipline).

    Carrying a chain is not verifying one. ADR §11 row 11 makes broken
    provenance a fail-closed refusal, and performing that check requires an
    authorized-producer trust boundary — TEV-2 (E-5). ADR §27.7 also records
    that the disclosure scope of these references is an open deployment concern
    (DD-7), which is why they are references and never payloads.
    """

    chain_ref: str
    custody_refs: tuple = field(default=())

    def __post_init__(self) -> None:
        require_identifier(self.chain_ref, "EvidenceProvenanceChain.chain_ref")
        normalized = normalize_reference_tuple(
            self.custody_refs, "EvidenceProvenanceChain.custody_refs"
        )
        object.__setattr__(self, "custody_refs", normalized)


@dataclass(frozen=True)
class CanonicalEvidenceIdentity:
    """The exact identity of one evidence item — and nothing more.

    Every field participates in :meth:`canonical_digest`, so the *complete*
    identity distinguishes one evidence item from another, not merely its id.
    The dataclass is frozen and every nested contract is frozen, so no
    post-construction mutation can alter the content or the digest.

    Construction is a **structural** act. It records what a caller says about an
    evidence item and makes swapping any coordinate detectable. It establishes
    no authenticity, confers no admission, and authorizes nothing — not
    deployment, not runtime action, not policy approval, not benchmark
    acceptance, not monetary value, not causal attribution.
    """

    evidence_id: str
    evidence_type: str
    schema: EvidenceSchemaRef
    content_digest: str
    observation: EvidenceObservation
    scope: EvidenceScopeBinding
    provenance: EvidenceProvenanceChain
    lifecycle_state: EvidenceLifecycleState
    geography: ApplicabilityCoordinate
    domain: ApplicabilityCoordinate
    intended_outcome: ApplicabilityCoordinate
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_identifier(self.evidence_id, "CanonicalEvidenceIdentity.evidence_id")
        require_identifier(
            self.evidence_type, "CanonicalEvidenceIdentity.evidence_type"
        )
        require_digest(
            self.content_digest, "CanonicalEvidenceIdentity.content_digest"
        )
        require_exact_type(
            self.schema, EvidenceSchemaRef, "CanonicalEvidenceIdentity.schema"
        )
        require_exact_type(
            self.observation,
            EvidenceObservation,
            "CanonicalEvidenceIdentity.observation",
        )
        require_exact_type(
            self.scope, EvidenceScopeBinding, "CanonicalEvidenceIdentity.scope"
        )
        require_exact_type(
            self.provenance,
            EvidenceProvenanceChain,
            "CanonicalEvidenceIdentity.provenance",
        )
        require_exact_type(
            self.lifecycle_state,
            EvidenceLifecycleState,
            "CanonicalEvidenceIdentity.lifecycle_state",
        )
        for name in ("geography", "domain", "intended_outcome"):
            require_exact_type(
                getattr(self, name),
                ApplicabilityCoordinate,
                f"CanonicalEvidenceIdentity.{name}",
            )
        require_optional_aware_datetime(
            self.valid_from, "CanonicalEvidenceIdentity.valid_from"
        )
        require_optional_aware_datetime(
            self.valid_to, "CanonicalEvidenceIdentity.valid_to"
        )
        if self.valid_from is not None and self.valid_to is not None:
            require_strictly_before(
                self.valid_from,
                self.valid_to,
                "CanonicalEvidenceIdentity.valid_from",
                "CanonicalEvidenceIdentity.valid_to",
                "the validity interval is half-open [valid_from, valid_to) "
                "per ADR §17.9",
            )

    # ------------------------------------------------------------------ #
    # Honest, non-settable status (ADR §14.5's discipline)
    # ------------------------------------------------------------------ #
    @property
    def structural_status(self) -> EvidenceStructuralStatus:
        """Always ``STRUCTURAL_UNVERIFIED``.

        A read-only property, not a field: there is no assignment, constructor
        argument or subclass hook that can raise it. Raising it requires a
        verifier, trust anchors and signature verification — TEV-2.
        """

        return EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED

    @property
    def authenticity_verified(self) -> bool:
        """Always ``False`` — constructing an identity attests nothing."""

        return False

    @property
    def established_trust_stages(self) -> tuple:
        """The ADR §12 stages this object actually establishes.

        Exactly ``(STRUCTURALLY_CONSTRUCTIBLE,)``: it parsed, its schema is
        named, and every structural invariant held. Nothing more.
        """

        return (EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,)

    @property
    def unestablished_trust_stages(self) -> tuple:
        """The ADR §12 stages that remain **unestablished**, in ratified order.

        Stages 2-5 are unestablished because no verifier exists at TEV-1. Stage
        6 is unestablished *and* unestablishable here: §12 rules policy
        sufficiency requirement-relative, so it is never a property of evidence
        and never TAP's to assert.

        Reading this property is the honest answer to "what does this object
        prove?" — and it is a non-empty tuple for every object this package can
        build.
        """

        established = set(self.established_trust_stages)
        return tuple(s for s in EVIDENCE_TRUST_STAGE_ORDER if s not in established)

    # ------------------------------------------------------------------ #
    # Structural coordinates
    # ------------------------------------------------------------------ #
    @property
    def coordinate_identity(self) -> tuple:
        """The load-bearing coordinate tuple, for structural comparison.

        Mutating any element produces a different tuple **and** a different
        :meth:`canonical_digest`.
        """

        return (
            self.evidence_id,
            self.evidence_type,
            self.schema.schema_id,
            self.schema.schema_version,
            self.content_digest,
            self.observation.producer_id,
            self.observation.issuer_id,
        ) + self.scope.scope_identity

    def is_valid_at(self, instant: datetime) -> bool:
        """Half-open ``[valid_from, valid_to)`` membership (ADR §17.9).

        An absent bound is open on that side, so an identity declaring no
        validity interval is within it at every instant. ``instant`` is always
        an explicit caller input — **the system clock is never read** (ADR
        §22.9, §22.10).

        This answers a *temporal* question about a *declared* interval. It is
        not a validity decision: ADR §12 stage 5 additionally requires the item
        to be unrevoked and fresh under a verifier, which TEV-1 has none of.
        """

        require_aware_datetime(instant, "CanonicalEvidenceIdentity.is_valid_at.instant")
        if self.valid_from is not None and instant < self.valid_from:
            return False
        if self.valid_to is not None and instant >= self.valid_to:
            return False
        return True

    def temporal_refusal_at(self, instant: datetime):
        """The typed temporal refusal at ``instant``, or ``None`` if within.

        Returns ``TRUSTED_EVIDENCE_NOT_YET_VALID`` before ``valid_from`` and
        ``TRUSTED_EVIDENCE_STALE`` at or after ``valid_to`` — the half-open
        boundary, so ``valid_to`` itself is already stale.

        ``None`` means "no *temporal* refusal applies". It is emphatically not a
        pass: stages 2-6 remain unestablished, and ADR §12 stage 5 also requires
        revocation and freshness checks this package cannot perform.
        """

        require_aware_datetime(
            instant, "CanonicalEvidenceIdentity.temporal_refusal_at.instant"
        )
        if self.valid_from is not None and instant < self.valid_from:
            return TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_NOT_YET_VALID
        if self.valid_to is not None and instant >= self.valid_to:
            return TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_STALE
        return None

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over.

        See :mod:`..contracts.canonical` for the complete rule set. Two
        identities that are ``==`` — including ones whose instants were written
        with different UTC offsets — produce byte-identical output.
        """

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the **complete** evidence identity.

        Two identities differing in any coordinate — the tenant, the context,
        the subject, the assessed-system binding, the declared purpose, the
        usage scope, the content digest, an observation instant, a custody link
        — produce different digests. It is an identity fingerprint, not
        evidence, not a signature, and not an authenticity proof (ADR §8.1.3).
        """

        return canonical_digest(self)
