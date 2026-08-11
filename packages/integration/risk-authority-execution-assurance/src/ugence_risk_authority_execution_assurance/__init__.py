"""Ugence Risk Authority Execution Assurance — RA-8 execution / effect reconciliation.

RA-8 is the **missing producer** of a neutral ``AuthorityReassessmentSignal``
(``EXECUTION_EFFECT_MISMATCH``) that the fully-built RA-6 seam already consumes,
closing the loop from *observed external effect* back to *machine authority*. It
correlates a governed authority context, the Agent Runtime execution attempt, and a
trusted external effect observation; composes the mature Decision Authority
reconciliation kernel under a safe, non-compensatory aggregation; and — on a
*material* post-effect mismatch — emits a neutral signal into the RA-6 intake. It is
**not** a second authority layer, a second Decision Authority, or a third execution
ledger.

    RA-8 OBSERVES, CORRELATES, AGGREGATES, AND ASSESSES POST-EFFECT.
    RA-6 OWNS AUTHORITY CONSEQUENCES.

Ratified flow (spec §5–§7, §22):

    governed authority context + AR attempt
        → ExecutionCorrelation                    (bind tenant/workflow/envelope/action/attempt)
        → TrustedEffectIngress                     (trust boundary; reference refused in prod)
        → DecisionAuthorityReconciler              (reuse DA ExecutionIntent/Record/Reconcile)
        → safe_aggregate (non-compensatory)        (close M-1: favorable cannot mask unfavorable)
        → EffectAssuranceAssessment                (neutral verdict: MATCHED/MISMATCH/…/CONFLICTED)
        → EffectAssuranceSignalEmitter             (material only; EXECUTION_EFFECT_MISMATCH)
        → AuthorityReassessmentSignalPort.submit   (RA-6 intake; reused as-is)
        → RA-6 reassessor → sole authenticated writer → targeted revoke / epoch / no-op

Dependency direction is one-way (spec §8): this package imports the RA leaf (neutral
signal types + intake port), the RA-6 status-runtime (reassessor + sole writer), the
Decision Authority reconciliation kernel (reused), and the neutral governance
effect-observation contract. The RA leaf stays stdlib-only; the Agent Runtime is
observed through a neutral duck-typed event contract and **never imports Risk
Authority or Decision Authority**.

**Maturity (no overclaim, spec §32, §34):** reference-grade post-effect
reconciliation. Effect-source trust is authenticated/delegated ingress + content-hash
integrity (integrity ≠ authenticity; hash ≠ signature); persistence is delegated to
Decision Authority; the reference effect authenticator and the reference DA reconciler
are **refused in production** (RA-5/6/7 F-1 pattern). This is NOT a production
Third-Party Gateway, signed external receipts, globally-distributed effect observation,
cryptographically-attested physical-world truth, zero-window correction, ACP, or GRC.
``RiskAuthorizationEnvelope`` remains the sole signed machine-execution authority.

See ``docs/architecture/RISK_AUTHORITY_RA8_SPEC.md`` (ratified) and
``docs/architecture/RA8_EXECUTION_ASSURANCE_AS_BUILT.md``.
"""

from __future__ import annotations

from .aggregation import AggregateAssessment, UNFAVORABLE_OUTCOMES, safe_aggregate
from .assurance import (
    CompositionRejectedError,
    EffectAssuranceOutcome,
    EffectAssuranceService,
)
from .contracts import (
    DA_STATUS_TO_OUTCOME,
    EXECUTION_ASSURANCE_SCHEMA_VERSION,
    SUPPORTED_OBSERVATION_SCHEMA_VERSIONS,
    EffectAssuranceAssessment,
    EffectFinality,
    EffectObservation,
    EffectReasonCode,
    EffectReconciliationOutcome,
    ExecutionCorrelation,
    effect_finality_of,
)
from .correlation import ExecutionCorrelator, GovernedAuthorityContext
from .event_adapter import RuntimeAttemptEvidence, RuntimeEventAdapter
from .handoff import (
    SIGNAL_SOURCE,
    EffectAssuranceSignalEmitter,
    HandoffOutcome,
    HandoffResult,
    assessment_to_signal,
)
from .ingress import (
    GOVERNANCE_OUTCOME_TO_BUSINESS_OUTCOME,
    EffectSourceAuthenticator,
    IngressDecision,
    IngressDisposition,
    ReferenceEffectIngressRejectedError,
    ReferenceEffectSourceAuthenticator,
    TrustedEffectIngress,
    normalize_execution_observation,
)
from .reconciler import (
    DecisionAuthorityReconciler,
    ExpectedEffect,
    ReconciliationEvidence,
    ReferenceDecisionAuthorityReconciler,
    ReferenceReconcilerRejectedError,
)
from .version import __version__

__all__ = [
    "__version__",
    # contracts
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
    # correlation
    "GovernedAuthorityContext",
    "ExecutionCorrelator",
    # event adapter
    "RuntimeAttemptEvidence",
    "RuntimeEventAdapter",
    # ingress
    "TrustedEffectIngress",
    "EffectSourceAuthenticator",
    "ReferenceEffectSourceAuthenticator",
    "ReferenceEffectIngressRejectedError",
    "IngressDecision",
    "IngressDisposition",
    "normalize_execution_observation",
    "GOVERNANCE_OUTCOME_TO_BUSINESS_OUTCOME",
    # aggregation
    "safe_aggregate",
    "AggregateAssessment",
    "UNFAVORABLE_OUTCOMES",
    # reconciler
    "DecisionAuthorityReconciler",
    "ReferenceDecisionAuthorityReconciler",
    "ReferenceReconcilerRejectedError",
    "ExpectedEffect",
    "ReconciliationEvidence",
    # handoff
    "EffectAssuranceSignalEmitter",
    "HandoffOutcome",
    "HandoffResult",
    "assessment_to_signal",
    "SIGNAL_SOURCE",
    # composition
    "EffectAssuranceService",
    "EffectAssuranceOutcome",
    "CompositionRejectedError",
]
