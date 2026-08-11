"""RA-8 neutral execution/effect-reconciliation contracts (spec §5, §12–§14, §18).

These are the minimum ratified neutral types. Every one is **evidence /
observation / binding metadata**, NOT authority: none carries an ``ALLOW``, a
scope grant, a signature, an execution token, a replacement envelope, or any
compensation authority. The absence is structural (there is simply no such
field), not merely validated — a packaging property test asserts it (spec §28
I5/I6, §31).

    ExecutionCorrelation        the runtime↔DA↔envelope binding record (spec §5)
    EffectObservation           one normalized, admitted external-effect fact (§12)
    EffectFinality              PENDING / PARTIAL / FINAL  (state, not outcome; §11/§13)
    EffectReconciliationOutcome MATCHED / MISMATCH / PARTIAL / UNKNOWN /
                                MANUAL_REVIEW / CONFLICTED / UNVERIFIABLE  (§14)
    EffectReasonCode            structured cause for an assessment / signal
    EffectAssuranceAssessment   the neutral verdict RA-8 produces (§14, §22)

RA-8 **reuses** the Decision Authority ``BusinessOutcome`` / ``Finality`` /
``ReconciliationStatus`` vocabularies rather than forking a parallel set (§14);
this module only adds the two terms RA-8's own seams require (``CONFLICTED`` for
conflicting observers, ``UNVERIFIABLE`` for an absent effect source) and the
ratified ``PENDING/PARTIAL/FINAL`` finality model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from ugence_decision_authority.execution.status import (
    BusinessOutcome,
    Finality,
    ReconciliationStatus,
)

__all__ = [
    "EXECUTION_ASSURANCE_SCHEMA_VERSION",
    "SUPPORTED_OBSERVATION_SCHEMA_VERSIONS",
    "EffectFinality",
    "EffectReconciliationOutcome",
    "EffectReasonCode",
    "ExecutionCorrelation",
    "EffectObservation",
    "EffectAssuranceAssessment",
    "effect_finality_of",
    "DA_STATUS_TO_OUTCOME",
]

#: Current observation wire-schema version. An observation declaring an
#: unsupported version is rejected fail-closed at ingress (never reconciled).
EXECUTION_ASSURANCE_SCHEMA_VERSION = "1"
SUPPORTED_OBSERVATION_SCHEMA_VERSIONS = frozenset({EXECUTION_ASSURANCE_SCHEMA_VERSION})


class EffectFinality(str, Enum):
    """Whether an observed effect is settled (state, kept separate from outcome; §11/§13).

    ``PENDING`` — not yet observed / asynchronous / no settled state.
    ``PARTIAL`` — a legitimate partial effect that may still converge.
    ``FINAL``   — a settled effect that will not change.

    Finality is deliberately **orthogonal** to the match verdict: a ``PARTIAL``
    effect within policy is ``PARTIAL`` + acceptable, never a mismatch merely
    because it is not final yet (§13).
    """

    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FINAL = "FINAL"


class EffectReconciliationOutcome(str, Enum):
    """The neutral post-effect verdict vocabulary (spec §14).

    Reuses the DA ``ReconciliationStatus`` semantics and adds exactly the two terms
    RA-8's new seams introduce (``CONFLICTED`` for conflicting trusted observers,
    ``UNVERIFIABLE`` for an absent/unavailable effect source). **No outcome is named
    ``ALLOW``, ``GRANT``, or ``AUTHORIZED``** — an outcome is evidence/verdict, not
    authority. **Malformed / untrusted / missing input MUST NOT become ``MATCHED``.**
    """

    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    CONFLICTED = "CONFLICTED"
    UNVERIFIABLE = "UNVERIFIABLE"

    @property
    def is_material(self) -> bool:
        """Material outcomes are exactly those that warrant an RA-6 reassessment.

        ``MISMATCH`` / ``CONFLICTED`` / ``MANUAL_REVIEW`` (a duplicate/ambiguous real
        effect) are material (spec §7, §22). ``MATCHED`` / ``PARTIAL`` (within
        policy) / ``UNKNOWN`` (finality not yet settled) / ``UNVERIFIABLE`` (no
        trusted source) never emit a signal by default — a false RA-8 mismatch may
        cost availability but must never widen authority (spec §18).
        """

        return self in (
            EffectReconciliationOutcome.MISMATCH,
            EffectReconciliationOutcome.CONFLICTED,
            EffectReconciliationOutcome.MANUAL_REVIEW,
        )


#: Deterministic map from a DA ``ReconciliationStatus`` to the neutral RA-8 term
#: (spec §14). ``CONFLICTED`` / ``UNVERIFIABLE`` have no DA source status; they are
#: produced only by RA-8's own aggregation seam.
DA_STATUS_TO_OUTCOME: dict[ReconciliationStatus, EffectReconciliationOutcome] = {
    ReconciliationStatus.RECONCILED: EffectReconciliationOutcome.MATCHED,
    ReconciliationStatus.MISMATCHED: EffectReconciliationOutcome.MISMATCH,
    ReconciliationStatus.PARTIALLY_RECONCILED: EffectReconciliationOutcome.PARTIAL,
    ReconciliationStatus.INDETERMINATE: EffectReconciliationOutcome.UNKNOWN,
    ReconciliationStatus.MANUAL_REVIEW_REQUIRED: EffectReconciliationOutcome.MANUAL_REVIEW,
    ReconciliationStatus.COMPENSATION_REQUIRED: EffectReconciliationOutcome.MISMATCH,
}


class EffectReasonCode(str, Enum):
    """Structured cause codes carried on an assessment / signal (audit granularity).

    A single neutral signal category (``EXECUTION_EFFECT_MISMATCH``) plus these
    structured reasons preserves audit detail without a taxonomy-for-its-own-sake
    proliferation of top-level RA-6 categories (mirrors the RA-7 pattern).
    """

    OUTCOME_FAILED = "OUTCOME_FAILED"
    OUTCOME_REJECTED = "OUTCOME_REJECTED"
    OUTCOME_CANCELLED = "OUTCOME_CANCELLED"
    PARAMETER_MISMATCH = "PARAMETER_MISMATCH"
    DUPLICATE_EFFECT = "DUPLICATE_EFFECT"
    CONFLICTING_OBSERVERS = "CONFLICTING_OBSERVERS"
    FAVORABLE_MASK_BLOCKED = "FAVORABLE_MASK_BLOCKED"
    NON_FINAL_PENDING = "NON_FINAL_PENDING"
    FINALITY_UNKNOWN = "FINALITY_UNKNOWN"
    EFFECT_SOURCE_UNAVAILABLE = "EFFECT_SOURCE_UNAVAILABLE"
    NO_OBSERVATION = "NO_OBSERVATION"
    RECONCILIATION_ERROR = "RECONCILIATION_ERROR"


def effect_finality_of(business_outcome: BusinessOutcome, finality: Finality) -> EffectFinality:
    """Derive the RA-8 ``EffectFinality`` from the DA outcome + finality (§11/§13).

    Not-yet-final is ``PENDING``; a final partial success is ``PARTIAL``; anything
    the external system reports as settled (``FINAL``) is ``FINAL``. Unknown finality
    is ``PENDING`` — never fabricated into ``FINAL`` (spec §13, §27).
    """

    if not isinstance(finality, Finality):
        return EffectFinality.PENDING
    if finality is Finality.FINAL:
        return EffectFinality.FINAL
    # NON_FINAL or UNKNOWN: a partial success that may still converge is PARTIAL;
    # everything else is simply PENDING.
    if finality is Finality.NON_FINAL and business_outcome is BusinessOutcome.PARTIALLY_SUCCEEDED:
        return EffectFinality.PARTIAL
    return EffectFinality.PENDING


def _digest(*parts: str) -> str:
    """A stable SHA-256 **integrity** digest over the bound identity fields.

    This is a content digest (integrity), **not** a signature (authenticity): it
    proves the correlation binds these exact fields, never that a third party
    attested them (spec §10, §20 — integrity ≠ authenticity; hash ≠ signature).
    """

    h = hashlib.sha256()
    for p in parts:
        h.update(b"\x1f")
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()


@dataclass(frozen=True)
class ExecutionCorrelation:
    """The runtime↔DA↔envelope binding record RA-8 owns (spec §5, §18, §20).

    Minted at authorize-time from the governed authority context and joined to the
    Agent Runtime execution attempt. It is **binding metadata**, not authority: it
    carries no ALLOW, no scope, no token. The intrinsic binding tuple
    ``(tenant_id, workflow_instance_id, envelope_id, authorized_action_digest,
    attempt_id)`` (+ optional ``provider`` / ``external_request_id`` / effect
    identity) is what every effect observation must match; **storage partitioning
    alone is insufficient** (spec §18). Wrong tenant / workflow / envelope / action
    digest / attempt fails closed.
    """

    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    authorized_action_digest: str
    correlation_id: str
    attempt_id: str
    idempotency_key: str = ""
    provider: str = ""
    external_request_id: str = ""
    execution_intent_id: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    correlation_digest: str = ""

    def __post_init__(self) -> None:
        # Deterministic, replay-safe digest over the intrinsic binding identity.
        object.__setattr__(
            self,
            "correlation_digest",
            _digest(
                self.tenant_id,
                self.workflow_instance_id,
                self.envelope_id,
                self.authorized_action_digest,
                self.correlation_id,
                self.attempt_id,
            ),
        )

    def binding_errors(self) -> Tuple[str, ...]:
        """Return fail-closed reasons this correlation cannot be trusted/bound.

        Empty tuple == structurally acceptable. The intrinsic binding fields must
        all be present; a missing tenant / workflow / envelope / action digest /
        attempt makes the correlation unusable and can never be silently completed.
        """

        reasons: list[str] = []
        for name in (
            "tenant_id",
            "workflow_instance_id",
            "envelope_id",
            "authorized_action_digest",
            "correlation_id",
            "attempt_id",
        ):
            if not str(getattr(self, name)).strip():
                reasons.append(f"missing {name}")
        return tuple(reasons)


@dataclass(frozen=True)
class EffectObservation:
    """One normalized, admitted external-effect fact (spec §12).

    Produced by the trusted effect ingress from a raw provider/effect-source
    observation. It is transient **evidence**, bound to exactly one authority
    domain; it carries no authority. It reuses the DA ``BusinessOutcome`` /
    ``Finality`` vocabularies (spec §12/§14 — no parallel set). ``effect_digest`` is
    a content-integrity digest, never an attestation (spec §10, §20).
    """

    schema_version: str
    observation_id: str
    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    authorized_action_digest: str
    attempt_id: str
    external_request_id: str
    business_outcome: BusinessOutcome
    provider: str = ""
    external_effect_id: str = ""
    observed_parameters: Mapping[str, str] = field(default_factory=dict)
    observed_at: Optional[datetime] = None
    finality: Finality = Finality.UNKNOWN
    source: str = ""
    source_version: str = ""
    effect_digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_parameters", dict(self.observed_parameters or {}))
        if not self.effect_digest:
            object.__setattr__(
                self,
                "effect_digest",
                _digest(
                    self.tenant_id,
                    self.envelope_id,
                    self.authorized_action_digest,
                    self.attempt_id,
                    self.external_request_id,
                    self.external_effect_id,
                    getattr(self.business_outcome, "value", str(self.business_outcome)),
                ),
            )

    @property
    def effect_finality(self) -> EffectFinality:
        return effect_finality_of(self.business_outcome, self.finality)

    def binding_errors(self) -> Tuple[str, ...]:
        """Return fail-closed reasons this observation is internally malformed.

        Empty tuple == structurally acceptable *for ingress* (the trust +
        binding-domain guard still decide admission). A non-empty result means the
        observation MUST be rejected and can never become a reconciliation record.
        Uses exact type checks so a malformed producer cannot smuggle a truthy
        stand-in past the gate (spec §29).
        """

        reasons: list[str] = []
        if self.schema_version not in SUPPORTED_OBSERVATION_SCHEMA_VERSIONS:
            reasons.append(f"unsupported schema_version {self.schema_version!r}")
        for name in (
            "observation_id",
            "tenant_id",
            "workflow_instance_id",
            "envelope_id",
            "authorized_action_digest",
            "attempt_id",
            "external_request_id",
        ):
            if not str(getattr(self, name)).strip():
                reasons.append(f"missing {name}")
        if not isinstance(self.business_outcome, BusinessOutcome):
            reasons.append("business_outcome is not a BusinessOutcome")
        if not isinstance(self.finality, Finality):
            reasons.append("finality is not a Finality")
        return tuple(reasons)


@dataclass(frozen=True)
class EffectAssuranceAssessment:
    """The neutral verdict RA-8 produces (spec §14, §22).

    **Evidence / verdict, NOT machine authority.** It uses the neutral outcome
    vocabulary (never ALLOW/DENY, never a grant). Only a *material* outcome causes a
    downstream consequence, and only via the neutral RA-6 signal — the assessment
    itself can never be used as standalone execution authority (spec §28 I5/I6).
    ``compensation_recommended`` is **advisory** and requires fresh governed
    authority to enact (spec §21) — it is never itself permission.
    """

    assessment_id: str
    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    authorized_action_digest: str
    attempt_id: str
    outcome: EffectReconciliationOutcome
    finality: EffectFinality
    produced_at: datetime
    correlation_digest: str = ""
    execution_intent_id: str = ""
    reconciliation_id: str = ""
    da_status: Optional[ReconciliationStatus] = None
    reason_codes: Tuple[EffectReasonCode, ...] = ()
    reasons: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()
    compensation_recommended: bool = False

    @property
    def is_material(self) -> bool:
        """A material assessment is exactly one whose outcome warrants reassessment.

        ``MATCHED`` / ``PARTIAL`` / ``UNKNOWN`` / ``UNVERIFIABLE`` never emit a signal
        — an unknown/pending/unverifiable window is never a fabricated escalation and
        never widens authority (spec §7, §18, §27).
        """

        return self.outcome.is_material
