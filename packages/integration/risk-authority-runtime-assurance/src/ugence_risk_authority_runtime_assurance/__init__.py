"""Ugence Risk Authority Runtime Assurance — RA-7 runtime / trajectory assurance.

RA-7 is the **missing producer** of the neutral ``AuthorityReassessmentSignal``
that the fully-built RA-6 seam already consumes. It observes the Agent Runtime
through the existing neutral event seam, risk-types the per-workflow-instance
*trajectory*, and — on a material deviation — emits a neutral signal into the
RA-6 intake. It is **not** a second authority layer.

    RA-7 OBSERVES AND ASSESSES.  RA-6 OWNS AUTHORITY CONSEQUENCES.

Ratified flow (spec §18):

    runtime event / external telemetry
        → TrustedTelemetryIngress            (trust boundary; §10/D7)
        → RuntimeAssuranceObserver           (bounded trajectory; dedupe/order; §11,§13)
        → SafeEvaluator(ReferenceTrajectoryEvaluator)  (risk-type; §6,§12)
        → TrajectoryAssessment  NORMAL / ESCALATED / UNKNOWN   (evidence, not authority)
        → if material ESCALATED →
        → AuthorityReassessmentSignal(RUNTIME_RISK_ESCALATED, ENVELOPE)
        → AuthorityReassessmentSignalPort.submit   (RA-6 intake; §15,§18)
        → RA-6 reassessor → sole authenticated writer → targeted revoke / no-op
        → StatusAwareActionGate / pre-effect recheck enforce at next commit

Dependency direction is one-way (spec §22): this package imports the RA leaf (for
the neutral signal types + intake port) and the RA-6 status-runtime (reassessor +
sole writer). The RA leaf stays a stdlib-only leaf; the Agent Runtime is observed
through a neutral duck-typed event contract and **never imports Risk Authority**.

**Maturity (no overclaim, spec §28):** event-driven, reference-grade runtime
assurance. Persistence and telemetry producer trust are *delegated* (reference
in-memory window + reference ingress authenticator, both refused in production
via the RA-5/RA-6 F-1 pattern). This is NOT continuous real-time authorization,
zero-window revocation, cryptographically-attested telemetry, ACP physical-control
safety, or RA-8 post-effect reconciliation. Revocation bites at the next
pre-effect recheck — bounded-latency, not instantaneous (spec §25).

See ``docs/architecture/RISK_AUTHORITY_RA7_SPEC.md`` (ratified) and
``docs/architecture/RA7_RUNTIME_ASSURANCE_AS_BUILT.md``.
"""

from __future__ import annotations

from .assurance import (
    AssuranceStateRecord,
    PreEffectAssuranceDecision,
    ReferenceCompositionRejectedError,
    RuntimeAssuranceOutcome,
    RuntimeAssuranceService,
)
from .contracts import (
    RUNTIME_ASSURANCE_SCHEMA_VERSION,
    SUPPORTED_OBSERVATION_SCHEMA_VERSIONS,
    AssessmentOutcome,
    ReasonCode,
    RuntimeRiskLevel,
    TrajectoryAssessment,
    TrajectoryObservation,
    TrajectoryPolicyRef,
)
from .evaluator import (
    EVALUATOR_IDENTITY,
    EVALUATOR_VERSION,
    ReferenceTrajectoryEvaluator,
    RuntimeAssuranceEvaluator,
    SafeEvaluator,
)
from .event_adapter import RuntimeBindingContext, RuntimeEventAdapter
from .handoff import (
    SIGNAL_SOURCE,
    AuthorityReassessmentSignalEmitter,
    HandoffOutcome,
    HandoffResult,
    assessment_to_signal,
)
from .ingress import (
    ExpectedBinding,
    IngressDecision,
    IngressDisposition,
    ReferenceIngressRejectedError,
    ReferenceTelemetryAuthenticator,
    TelemetryAuthenticator,
    TrustedTelemetryIngress,
)
from .observer import (
    DEFAULT_WINDOW_SIZE,
    RuntimeAssuranceObserver,
    Trajectory,
)
from .policy import (
    ReferencePolicyRejectedError,
    ReferenceTrajectoryPolicyReader,
    TrajectoryPolicy,
    TrajectoryPolicyReader,
)
from .version import __version__

__all__ = [
    "__version__",
    # contracts
    "RUNTIME_ASSURANCE_SCHEMA_VERSION",
    "SUPPORTED_OBSERVATION_SCHEMA_VERSIONS",
    "RuntimeRiskLevel",
    "ReasonCode",
    "AssessmentOutcome",
    "TrajectoryPolicyRef",
    "TrajectoryObservation",
    "TrajectoryAssessment",
    # policy
    "TrajectoryPolicy",
    "TrajectoryPolicyReader",
    "ReferenceTrajectoryPolicyReader",
    "ReferencePolicyRejectedError",
    # ingress
    "TrustedTelemetryIngress",
    "TelemetryAuthenticator",
    "ReferenceTelemetryAuthenticator",
    "ReferenceIngressRejectedError",
    "ExpectedBinding",
    "IngressDecision",
    "IngressDisposition",
    # observer
    "RuntimeAssuranceObserver",
    "Trajectory",
    "DEFAULT_WINDOW_SIZE",
    # event adapter
    "RuntimeEventAdapter",
    "RuntimeBindingContext",
    # evaluator
    "RuntimeAssuranceEvaluator",
    "ReferenceTrajectoryEvaluator",
    "SafeEvaluator",
    "EVALUATOR_IDENTITY",
    "EVALUATOR_VERSION",
    # handoff
    "AuthorityReassessmentSignalEmitter",
    "HandoffOutcome",
    "HandoffResult",
    "assessment_to_signal",
    "SIGNAL_SOURCE",
    # composition
    "RuntimeAssuranceService",
    "RuntimeAssuranceOutcome",
    "AssuranceStateRecord",
    "PreEffectAssuranceDecision",
    "ReferenceCompositionRejectedError",
]
