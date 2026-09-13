"""The thirteen record types, frozen and digest-bound.

Every one validates its own shape and **computes nothing across records**. Digests
are supplied by the caller; no type here resolves, dereferences or verifies another
record, recomputes a projection, re-applies a routing rule, or drives a state
machine. The graph they form is a DAG whose edges are pins: each record carries the
digests of records that already existed when it was sealed, and never a
back-reference to one that did not.

Canonical order of the graph, for the reader rather than for any code here:
classification, confirmation amendment, investigation openings with their optional
extensions and single closures, final resolution, authorization, admission
reservation, claim, completion and where needed resolution, with revocation and its
impact hanging off the resolution.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._canon import require_digest, require_nonempty, require_ordinal
from .vocabulary import (
    AdmissionState,
    ClaimKind,
    ClosureOutcome,
    CompletionAbsence,
    EffectClass,
    EvaluationStatus,
    JurisdictionalRoute,
    ObligationKind,
    PrimitiveEffectKind,
    RemediationRequirement,
    RevocationOrdering,
)
from .errors import ContractViolation


def _digests(values, name: str) -> tuple[str, ...]:
    return tuple(require_digest(v, name) for v in values)


# --------------------------------------------------------------------------- parts
@dataclass(frozen=True)
class RegistryEffectResult:
    """One protected registry's result. ``effect_class`` only when ``MEASURED``."""

    registry: str
    evaluation_status: EvaluationStatus
    effect_class: EffectClass | None = None
    blocking_obligation_id: str | None = None

    def __post_init__(self) -> None:
        require_nonempty(self.registry, "registry")
        measured = self.evaluation_status is EvaluationStatus.MEASURED
        if measured and self.effect_class is None:
            raise ContractViolation("a MEASURED registry must carry an effect class")
        if not measured and self.effect_class is not None:
            raise ContractViolation("an effect class is set only when MEASURED")
        if self.evaluation_status is EvaluationStatus.UNEVALUATED:
            if self.blocking_obligation_id is None:
                raise ContractViolation(
                    "an UNEVALUATED registry must name the obligation recording why"
                )
            require_digest(self.blocking_obligation_id, "blocking_obligation_id")


@dataclass(frozen=True)
class BlockingObligation:
    """An obligation as the introducing record carries it."""

    obligation_id: str
    obligation_kind: ObligationKind
    coordinate: str
    ordinal: int

    def __post_init__(self) -> None:
        require_digest(self.obligation_id, "obligation_id")
        require_nonempty(self.coordinate, "coordinate")
        require_ordinal(self.ordinal, "ordinal")


@dataclass(frozen=True)
class PrimitiveEffect:
    """One primitive write. Never a derived value."""

    kind: PrimitiveEffectKind
    target: str
    value_digest: str

    def __post_init__(self) -> None:
        require_nonempty(self.target, "target")
        require_digest(self.value_digest, "value_digest")


@dataclass(frozen=True)
class ClosureEffectBundle:
    """What a COMPLETED closure carries — **derived by the mapping, never composed.**

    The evaluator signs a raw evaluation result; the versioned, policy-governance-owned
    ClosureBundleMapping produces this bundle, and the Stage 3 verifier recomputes and
    compares it for completeness as well as correctness. This type holds the bundle. It
    derives nothing and verifies nothing.
    """

    obligation_id: str
    mapping_version: str
    evaluation_result_digest: str
    effects: tuple[PrimitiveEffect, ...]
    declared_write_set: tuple[str, ...]

    def __post_init__(self) -> None:
        require_digest(self.obligation_id, "obligation_id")
        require_nonempty(self.mapping_version, "mapping_version")
        require_digest(self.evaluation_result_digest, "evaluation_result_digest")
        if not self.effects:
            raise ContractViolation("a bundle carries at least one primitive effect")
        if len(set(self.declared_write_set)) != len(self.declared_write_set):
            raise ContractViolation("declared_write_set must not repeat a target")


@dataclass(frozen=True)
class SampleBinding:
    """What a supplemental sample binds so a reviewer can redraw it.

    Disjointness is recomputable from these, not asserted by them: the prior history
    is the full ordered list, and the seed authority is recorded because a party that
    can choose the seed can choose the result.
    """

    seed_digest: str
    seed_authority: str
    archive_snapshot_digest: str
    sampling_algorithm: str
    sampling_algorithm_version: str
    population_digest: str
    sample_digest: str
    prior_sample_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "seed_digest", "archive_snapshot_digest", "population_digest", "sample_digest",
        ):
            require_digest(getattr(self, name), name)
        for name in ("seed_authority", "sampling_algorithm", "sampling_algorithm_version"):
            require_nonempty(getattr(self, name), name)
        _digests(self.prior_sample_digests, "prior_sample_digests")


# ---------------------------------------------------------------------- 1. the chain
@dataclass(frozen=True)
class ClassificationRecord:
    """Frozen at step 6. Introduces the obligation identifiers; carries no confirmation.

    The confirmation seed, sample digest and result are produced after the freeze and
    live in the ConfirmationAmendment. This record references nothing that comes after it.
    """

    chain_id: str
    tenant: str
    candidate_digest: str
    anomaly_family: str
    chain_instance_id: str
    family_seed_digest: str
    family_sample_digest: str
    anchor_snapshot_digest: str
    current_snapshot_digest: str
    proposed_snapshot_digest: str
    evaluator_version: str
    replay_environment_digest: str
    model_code_digest: str
    policy_versions: tuple[str, ...]
    delegation_table_version: str
    registry_list_version: str
    mapping_version: str
    results: tuple[RegistryEffectResult, ...]
    jurisdictional_route: JurisdictionalRoute
    provisional: str = "false"
    blocking_obligations: tuple[BlockingObligation, ...] = ()
    signer: str = ""

    def __post_init__(self) -> None:
        for name in (
            "chain_id", "candidate_digest", "family_seed_digest", "family_sample_digest",
            "anchor_snapshot_digest", "current_snapshot_digest", "proposed_snapshot_digest",
            "replay_environment_digest", "model_code_digest",
        ):
            require_digest(getattr(self, name), name)
        for name in (
            "tenant", "anomaly_family", "chain_instance_id", "evaluator_version",
            "delegation_table_version", "registry_list_version", "mapping_version", "signer",
        ):
            require_nonempty(getattr(self, name), name)
        if self.provisional not in ("true", "false"):
            raise ContractViolation("provisional is the enumerated string 'true' or 'false'")
        if not self.results:
            raise ContractViolation("a classification carries a result per protected registry")
        seen = {o.obligation_id for o in self.blocking_obligations}
        if len(seen) != len(self.blocking_obligations):
            raise ContractViolation("an obligation identifier appears at most once")


@dataclass(frozen=True)
class ConfirmationAmendment:
    """The post-freeze amendment. Closes CONFIRMATION_PENDING and nothing else."""

    chain_id: str
    classification_digest: str
    confirmation_seed_digest: str
    confirmation_sample_digest: str
    confirmation_result_digest: str
    closes_obligation_ids: tuple[str, ...] = ()
    introduces: tuple[BlockingObligation, ...] = ()
    signer: str = ""

    def __post_init__(self) -> None:
        for name in (
            "chain_id", "classification_digest", "confirmation_seed_digest",
            "confirmation_sample_digest", "confirmation_result_digest",
        ):
            require_digest(getattr(self, name), name)
        require_nonempty(self.signer, "signer")
        _digests(self.closes_obligation_ids, "closes_obligation_ids")


@dataclass(frozen=True)
class InvestigationRecord:
    """The immutable opening only. It acquires no state and no closing disposition.

    It pins the obligation it answers and **exactly one** introducing record — the
    classification or the amendment, never both — carried as a role constant and a
    digest, not as a source of the identifier.
    """

    chain_id: str
    obligation_id: str
    introducing_role: str
    introducing_digest: str
    candidate_digest: str
    anomaly_family: str
    named_evaluation: str
    owner_identity: str
    deadline: str

    def __post_init__(self) -> None:
        for name in ("chain_id", "obligation_id", "introducing_digest", "candidate_digest"):
            require_digest(getattr(self, name), name)
        for name in ("anomaly_family", "named_evaluation", "owner_identity", "deadline"):
            require_nonempty(getattr(self, name), name)
        if self.introducing_role not in ("CLASSIFICATION", "CONFIRMATION_AMENDMENT"):
            raise ContractViolation(
                "introducing_role must be CLASSIFICATION or CONFIRMATION_AMENDMENT"
            )


@dataclass(frozen=True)
class InvestigationExtensionRecord:
    """At most one per investigation, and never behind its closure."""

    chain_id: str
    opening_digest: str
    extended_deadline: str
    owner_identity: str

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.opening_digest, "opening_digest")
        require_nonempty(self.extended_deadline, "extended_deadline")
        require_nonempty(self.owner_identity, "owner_identity")


@dataclass(frozen=True)
class InvestigationClosureRecord:
    """Exactly one per investigation, pinning the opening and any extension.

    A COMPLETED closure carries a bundle and resolves inside the existing chain. EXPIRED
    and CLOSED_INSUFFICIENT_EVIDENCE are terminating: the candidate ends with no
    resolution and no authorization, and the chain seals on the closure.
    """

    chain_id: str
    obligation_id: str
    opening_digest: str
    outcome: ClosureOutcome
    extension_digest: str | None = None
    bundle: ClosureEffectBundle | None = None
    sample_binding: SampleBinding | None = None
    reason: str = ""
    signer: str = ""

    def __post_init__(self) -> None:
        for name in ("chain_id", "obligation_id", "opening_digest"):
            require_digest(getattr(self, name), name)
        if self.extension_digest is not None:
            require_digest(self.extension_digest, "extension_digest")
        completed = self.outcome is ClosureOutcome.COMPLETED
        if completed and self.bundle is None:
            raise ContractViolation("a COMPLETED closure carries a ClosureEffectBundle")
        if not completed and self.bundle is not None:
            raise ContractViolation("a terminating closure carries no bundle")
        if completed and self.bundle.obligation_id != self.obligation_id:
            raise ContractViolation("the bundle answers a different obligation")
        require_nonempty(self.signer, "signer")


@dataclass(frozen=True)
class FinalResolutionRecord:
    """Terminal and unique for its chain; the only record an authorization pins.

    It binds the classification, the amendment and every COMPLETED closure, states the
    re-applied disposition, and asserts the effective obligation set is empty. The
    assertion is evidence of what the producer believed; the Stage 3 verifier recomputes
    the projection rather than accepting it, and nothing here recomputes anything.
    """

    chain_id: str
    classification_digest: str
    amendment_digest: str
    closure_digests: tuple[str, ...]
    jurisdictional_route: JurisdictionalRoute
    routing_rule: str
    effective_set_empty: str = "true"
    signer: str = ""

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.classification_digest, "classification_digest")
        require_digest(self.amendment_digest, "amendment_digest")
        _digests(self.closure_digests, "closure_digests")
        if self.effective_set_empty != "true":
            raise ContractViolation(
                "a final resolution exists only where the effective obligation set is empty"
            )
        require_nonempty(self.routing_rule, "routing_rule")
        require_nonempty(self.signer, "signer")


@dataclass(frozen=True)
class AuthorizationBinding:
    """The shape by which an M6 authorization pins a **FinalResolutionRecord**.

    Not the classification digest alone: an authorization pinned to the classification
    would identify neither the final route nor the evidence that emptied the effective
    obligation set. A binding contract only; issuance stays in M6.
    """

    chain_id: str
    final_resolution_digest: str
    authorization_digest: str
    issuing_authority: str
    validity_window: str

    def __post_init__(self) -> None:
        for name in ("chain_id", "final_resolution_digest", "authorization_digest"):
            require_digest(getattr(self, name), name)
        require_nonempty(self.issuing_authority, "issuing_authority")
        require_nonempty(self.validity_window, "validity_window")


# ------------------------------------------------------------------ 2. revocation
@dataclass(frozen=True)
class ResolutionRevocationRecord:
    """The decision, recorded immediately. **It carries no exposure window.**

    At the instant it is sealed the window may not exist yet, because the executor may
    hold a durable APPLY claim whose completion is unwritten, and an immutable record
    must not assert a fact that is not yet available. What becomes knowable afterwards
    goes into the RevocationImpactRecord.

    Signed under owner decision 6a by the authority that issued the authorization for
    the classification's governance route, never the candidate's proposer or reviewer.
    """

    chain_id: str
    final_resolution_digest: str
    basis: str
    ordering: RevocationOrdering
    control_version_at_revocation: int
    signer: str
    signer_authority: str

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.final_resolution_digest, "final_resolution_digest")
        require_nonempty(self.basis, "basis")
        require_ordinal(self.control_version_at_revocation, "control_version_at_revocation")
        require_nonempty(self.signer, "signer")
        require_nonempty(self.signer_authority, "signer_authority")


@dataclass(frozen=True)
class RevocationImpactRecord:
    """The single successor of a revocation, carrying what is knowable only afterwards.

    Every field is **derived and verified** by the Stage 3 boundary from the ledger, the
    registers and the read-port receipts, and a divergent record is refused. This type
    carries the fields; it derives none of them.

    Under owner decision 6b a revoked applied delta always requires a state-repair or
    compensating candidate, which nothing waives. Downstream-exposure remediation is a
    separate obligation, required where at least one read was served; until archive
    custody exists and the served-read log is custody-assured, the conservative
    presumption is that exposure occurred.
    """

    chain_id: str
    revocation_digest: str
    applied: str
    ordering: RevocationOrdering
    remediation: RemediationRequirement
    exposure_presumed: str
    completion_digest: str | None = None
    completion_absence: CompletionAbsence | None = None
    post_target_versions: tuple[tuple[str, int], ...] = ()
    exposure_receipt_digests: tuple[str, ...] = ()
    signer: str = ""

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.revocation_digest, "revocation_digest")
        for name in ("applied", "exposure_presumed"):
            if getattr(self, name) not in ("true", "false"):
                raise ContractViolation(f"{name} is the enumerated string 'true' or 'false'")
        if (self.completion_digest is None) == (self.completion_absence is None):
            raise ContractViolation(
                "an impact record pins a completion or states its structural absence, never both"
            )
        if self.completion_digest is not None:
            require_digest(self.completion_digest, "completion_digest")
        if self.completion_absence is not None and self.applied != "false":
            raise ContractViolation("no APPLY claim was made, so nothing can have been applied")
        if self.applied == "true" and self.remediation is RemediationRequirement.NONE:
            raise ContractViolation(
                "owner decision 6b: a revoked applied delta always requires state repair"
            )
        if self.applied == "false" and self.remediation is not RemediationRequirement.NONE:
            raise ContractViolation("no remediation arises where nothing was applied")
        _digests(self.exposure_receipt_digests, "exposure_receipt_digests")
        require_nonempty(self.signer, "signer")


# ------------------------------------------------------------------- 3. admission
@dataclass(frozen=True)
class AdmissionReservationRecord:
    """RESERVED. Appended durably before any effect, on a transition keyed by the
    authorization, so a fresh authorization reserves on its own transition rather than
    colliding with a consumed one.

    Binds the head version it was appended under, the single-tenant target set and the
    expected version of each target. A delta never spans tenants.
    """

    chain_id: str
    final_resolution_digest: str
    authorization_digest: str
    classification_digest: str
    amendment_digest: str
    pre_state_digest: str
    delta_digest: str
    idempotency_key: str
    head_version: int
    control_version: int
    tenant: str
    expected_target_versions: tuple[tuple[str, int], ...]
    state: AdmissionState = AdmissionState.RESERVED
    signer: str = ""

    def __post_init__(self) -> None:
        for name in (
            "chain_id", "final_resolution_digest", "authorization_digest",
            "classification_digest", "amendment_digest", "pre_state_digest", "delta_digest",
        ):
            require_digest(getattr(self, name), name)
        require_nonempty(self.idempotency_key, "idempotency_key")
        require_nonempty(self.tenant, "tenant")
        require_nonempty(self.signer, "signer")
        require_ordinal(self.head_version, "head_version")
        require_ordinal(self.control_version, "control_version")
        if self.state is not AdmissionState.RESERVED:
            raise ContractViolation("a reservation is RESERVED and nothing else")
        if not self.expected_target_versions:
            raise ContractViolation("a reservation binds at least one target version")
        targets = [t for t, _ in self.expected_target_versions]
        if len(set(targets)) != len(targets):
            raise ContractViolation("a target appears at most once in the target set")
        for target, version in self.expected_target_versions:
            require_nonempty(target, "target")
            require_ordinal(version, "expected_target_version")


@dataclass(frozen=True)
class AdmissionClaimRecord:
    """The single legal successor of RESERVED. APPLY commits execution; CANCEL documents.

    An APPLY is a compare-and-advance on the resolution's control register carrying the
    expected version and requiring ACTIVE; a revocation is the same operation on the same
    register, which is what makes a write after a committed revocation unreachable. A
    CANCEL claim records a revocation-first outcome where one is appended, and
    correctness never depends on it.
    """

    chain_id: str
    reservation_digest: str
    claim_kind: ClaimKind
    expected_control_version: int
    expected_target_versions: tuple[tuple[str, int], ...] = ()
    signer: str = ""

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.reservation_digest, "reservation_digest")
        require_ordinal(self.expected_control_version, "expected_control_version")
        require_nonempty(self.signer, "signer")
        if self.claim_kind is ClaimKind.APPLY and not self.expected_target_versions:
            raise ContractViolation("an APPLY claim restates the reserved target versions")


@dataclass(frozen=True)
class AdmissionCompletionRecord:
    """Pins the APPLY claim. It — not the claim — says whether the mutation happened."""

    chain_id: str
    claim_digest: str
    state: AdmissionState
    prior_state: AdmissionState = AdmissionState.RESERVED
    post_state_digest: str | None = None
    post_target_versions: tuple[tuple[str, int], ...] = ()
    reason: str = ""
    signer: str = ""

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.claim_digest, "claim_digest")
        if self.state is AdmissionState.RESERVED:
            raise ContractViolation("a completion is APPLIED, FAILED or OUTCOME_UNKNOWN")
        if self.state is AdmissionState.APPLIED:
            if self.post_state_digest is None:
                raise ContractViolation("an APPLIED completion carries the post-state digest")
            require_digest(self.post_state_digest, "post_state_digest")
        if self.state is AdmissionState.FAILED and not self.reason:
            raise ContractViolation("a FAILED completion carries its refusal reason")
        require_nonempty(self.signer, "signer")


@dataclass(frozen=True)
class AdmissionResolutionRecord:
    """A human resolution of OUTCOME_UNKNOWN. It never overwrites the unknown record."""

    chain_id: str
    completion_digest: str
    resolved_state: AdmissionState
    evidence: str
    resolving_authority: str

    def __post_init__(self) -> None:
        require_digest(self.chain_id, "chain_id")
        require_digest(self.completion_digest, "completion_digest")
        if self.resolved_state not in (AdmissionState.APPLIED, AdmissionState.FAILED):
            raise ContractViolation("a human resolution resolves to APPLIED or FAILED")
        require_nonempty(self.evidence, "evidence")
        require_nonempty(self.resolving_authority, "resolving_authority")


#: The thirteen record types, in canonical graph order. Data, not a registry.
RECORD_TYPES: tuple[type, ...] = (
    ClassificationRecord,
    ConfirmationAmendment,
    InvestigationRecord,
    InvestigationExtensionRecord,
    InvestigationClosureRecord,
    FinalResolutionRecord,
    AuthorizationBinding,
    ResolutionRevocationRecord,
    RevocationImpactRecord,
    AdmissionReservationRecord,
    AdmissionClaimRecord,
    AdmissionCompletionRecord,
    AdmissionResolutionRecord,
)
