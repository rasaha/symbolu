"""Hiring policy plane — canonical import surface.

Re-exports the Policy → Compiler (PWC) → WorkflowIR → Decision Contract layer so
consumers can depend on ``ugence_ai_hiring.hiring.policy`` alongside the other
canonical hiring-domain surfaces (``hiring.errors``, ``hiring.adapters``, …). The
implementation lives under ``ugence_ai_hiring.hiring_policy`` and object identity
is preserved.

See ``docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`` §3.
"""

from __future__ import annotations

from ugence_ai_hiring.hiring_policy import (
    ActionConstraints,
    Approver,
    ApproverAuthority,
    CompiledFrom,
    CompilerProvenance,
    ContractProjectionError,
    DeterministicHMACSigner,
    DimensionEmphasis,
    GatePredicate,
    GateStatus,
    HiringDecisionContract,
    HiringEvidenceClass,
    HiringPolicy,
    HiringPolicyCompiler,
    HiringWorkflowIR,
    IRActionConstraints,
    IRSignature,
    LifecycleStatus,
    MandatoryGate,
    MandatoryGateType,
    PolicyCompilationError,
    Requirements,
    RoleRef,
    RuntimeAssuranceCheck,
    SignatureError,
    Signer,
    compute_content_digest,
    project_contract,
)

__all__ = [
    "HiringPolicy",
    "RoleRef",
    "Requirements",
    "ActionConstraints",
    "HiringPolicyCompiler",
    "ApproverAuthority",
    "HiringWorkflowIR",
    "MandatoryGate",
    "GatePredicate",
    "IRActionConstraints",
    "Approver",
    "CompilerProvenance",
    "compute_content_digest",
    "HiringDecisionContract",
    "CompiledFrom",
    "project_contract",
    "Signer",
    "DeterministicHMACSigner",
    "IRSignature",
    "DimensionEmphasis",
    "MandatoryGateType",
    "HiringEvidenceClass",
    "RuntimeAssuranceCheck",
    "GateStatus",
    "LifecycleStatus",
    "PolicyCompilationError",
    "SignatureError",
    "ContractProjectionError",
]
