"""Contracts (ports) for integrating existing governance components.

``risk_authority`` integrates ActionGate, TAP and PWC through these ports and
never imports their application-specific policy logic directly (user brief §1).
"""

from __future__ import annotations

from .actiongate import ActionGatePort, ReferenceActionGate, RuntimeIdentity
from .authority_lifecycle import (
    AuthorityLifecycleWriter,
    AuthorityReassessmentSignalPort,
    AuthorityStatusReader,
    LifecycleOutcome,
    LifecycleWriteResult,
    SignalAck,
    SignalDisposition,
    WriterPrincipal,
)
from .control_assurance import (
    ControlAssuranceError,
    ControlAssurancePort,
    ControlAssuranceRequest,
    ControlAssuranceResult,
    ReferenceControlAssurance,
    bind_control_result,
)
from .ingress import TrustedEvidenceIngressPort
from .pwc import InMemoryWorkflowIRSource, WorkflowIRSource
from .tap import EvidenceAdmissionPort, ReferenceEvidenceAdmission
from .evaluation_contracts import (
    EVALUATION_REQUEST_SCHEMA_VERSION,
    EVALUATION_RESULT_SCHEMA_VERSION,
    SUPPORTED_REQUEST_SCHEMA_VERSIONS,
    PolicyResolverPort,
    ReferenceControlEvidenceResolver,
    ReferencePolicyResolver,
    SeamContractError,
    SubjectRiskDecision,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskNonDecisionReason,
    TrustedControlEvidenceResolverPort,
)

__all__ = [
    "ActionGatePort",
    "ReferenceActionGate",
    "RuntimeIdentity",
    "AuthorityStatusReader",
    "AuthorityLifecycleWriter",
    "AuthorityReassessmentSignalPort",
    "WriterPrincipal",
    "LifecycleOutcome",
    "LifecycleWriteResult",
    "SignalAck",
    "SignalDisposition",
    "EvidenceAdmissionPort",
    "ReferenceEvidenceAdmission",
    "TrustedEvidenceIngressPort",
    "ControlAssurancePort",
    "ControlAssuranceRequest",
    "ControlAssuranceResult",
    "ControlAssuranceError",
    "ReferenceControlAssurance",
    "bind_control_result",
    "WorkflowIRSource",
    "InMemoryWorkflowIRSource",
    "EVALUATION_REQUEST_SCHEMA_VERSION",
    "EVALUATION_RESULT_SCHEMA_VERSION",
    "SUPPORTED_REQUEST_SCHEMA_VERSIONS",
    "PolicyResolverPort",
    "TrustedControlEvidenceResolverPort",
    "ReferencePolicyResolver",
    "ReferenceControlEvidenceResolver",
    "SubjectRiskEvaluationRequest",
    "SubjectRiskDecision",
    "SubjectRiskDisposition",
    "SubjectRiskNonDecisionReason",
    "SeamContractError",
]
