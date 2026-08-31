"""Hiring policy plane — Policy → Compiler (PWC) → WorkflowIR → Decision Contract.

The governance-first authoring surface for the Hiring Decision Authority. HR
authors a declarative :class:`HiringPolicy`; the :class:`HiringPolicyCompiler`
(PWC) compiles it into a signed, content-addressed :class:`HiringWorkflowIR`
(``hiring_workflow_ir.v1``); a :class:`HiringDecisionContract` is projected from
one IR digest. This mirrors the platform Policy Workflow Compiler / WorkflowIR /
Decision Contract pattern and composes on the domain-neutral governance kernel.

See ``docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`` §3 and the normative
schemas under ``docs/schemas/``.

Scope of this layer (spec §21 step 1): it **authors, compiles, signs, and
projects policy**. It does not evaluate gates, score candidates, generate
recommendations, gate actions, run runtime assurance, write to any HRIS/ATS, or
make/authorize a decision — those are later spine stages.
"""

from __future__ import annotations

from .authority import ApproverAuthority, parse_level
from .compiler import HiringPolicyCompiler, PWC_VERSION
from .contract import CompiledFrom, HiringDecisionContract, project_contract
from .enums import (
    DimensionEmphasis,
    GateStatus,
    HiringEvidenceClass,
    LifecycleStatus,
    MandatoryGateType,
    RuntimeAssuranceCheck,
)
from .errors import ContractProjectionError, PolicyCompilationError, SignatureError
from .policy import ActionConstraints, HiringPolicy, Requirements, RoleRef
from .signing import DeterministicHMACSigner, IRSignature, Signer
from .workflow_ir import (
    IR_KIND,
    IR_VERSION,
    Approver,
    CompilerProvenance,
    GatePredicate,
    HiringWorkflowIR,
    IRActionConstraints,
    MandatoryGate,
    compute_content_digest,
)

__all__ = [
    # policy source
    "HiringPolicy",
    "RoleRef",
    "Requirements",
    "ActionConstraints",
    # compiler
    "HiringPolicyCompiler",
    "PWC_VERSION",
    "ApproverAuthority",
    "parse_level",
    # IR
    "HiringWorkflowIR",
    "MandatoryGate",
    "GatePredicate",
    "IRActionConstraints",
    "Approver",
    "CompilerProvenance",
    "compute_content_digest",
    "IR_VERSION",
    "IR_KIND",
    # contract
    "HiringDecisionContract",
    "CompiledFrom",
    "project_contract",
    # signing
    "Signer",
    "DeterministicHMACSigner",
    "IRSignature",
    # enums
    "DimensionEmphasis",
    "MandatoryGateType",
    "HiringEvidenceClass",
    "RuntimeAssuranceCheck",
    "GateStatus",
    "LifecycleStatus",
    # errors
    "PolicyCompilationError",
    "SignatureError",
    "ContractProjectionError",
]
