"""Product-owned enumerations.

These are PRODUCT_PUBLIC vocabularies. They never redefine neutral contract
enums (``ProviderKind``, ``ActionGovernanceOutcome``, ``AssertionCoverage``,
``DecisionOutcome`` remain owned upstream and are consumed through public APIs).
"""
from __future__ import annotations

from enum import Enum


class MergeMethod(str, Enum):
    """How the change would land — bound into the exact-artifact identity."""

    MERGE = "merge"
    SQUASH = "squash"
    REBASE = "rebase"
    MERGE_QUEUE = "merge_queue"


class RiskTier(str, Enum):
    """Risk scope that selects which claims a policy requires.

    Matches the merged Change Intelligence evidence-profile tiers.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ClaimType(str, Enum):
    """Claim families supported by the merged Change Intelligence design.

    Code Governance *governs* evidence produced by external validators; it does
    not itself detect. Only families named in the merged documentation appear.
    """

    BUILD = "BUILD"
    UNIT_TEST = "UNIT_TEST"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    SECURITY = "SECURITY"
    DEPENDENCY_DELTA = "DEPENDENCY_DELTA"
    ARCHITECTURE_DELTA = "ARCHITECTURE_DELTA"
    PUBLIC_API_DELTA = "PUBLIC_API_DELTA"
    ARTIFACT_SIZE_DELTA = "ARTIFACT_SIZE_DELTA"
    COMPLEXITY_DELTA = "COMPLEXITY_DELTA"
    DIFFERENTIAL_TEST = "DIFFERENTIAL_TEST"
    PROPERTY_TEST = "PROPERTY_TEST"
    MUTATION_ADEQUACY = "MUTATION_ADEQUACY"
    PERFORMANCE_BUDGET = "PERFORMANCE_BUDGET"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"


class ClaimStatus(str, Enum):
    """Per-claim state semantics (merged design).

    Deliberately NOT a single blended quality score — each claim carries its own
    admissibility verdict so mandatory gates stay non-compensatory.
    """

    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValidatorTrustLevel(str, Enum):
    """Source classification / trust level of the validator that produced evidence."""

    TRUSTED = "TRUSTED"          # pinned, provenance-bound validator
    UNVERIFIED = "UNVERIFIED"    # admissible but not yet provenance-verified
    UNTRUSTED = "UNTRUSTED"      # inadmissible as a mandatory-claim source


class WorkflowState(str, Enum):
    """Deterministic Workflow Service state machine for the MVP 1A shadow path.

    The Workflow Service owns *coordination*; it owns no governance authority.
    The machine runs to :attr:`SHADOW_COMPLETE` and stops — there is no
    authorization-issue, clearance, dispatch, or merge state in this phase.
    """

    # forward path
    RECEIVED = "RECEIVED"
    IDENTITY_BOUND = "IDENTITY_BOUND"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"
    CLAIMS_EVALUATED = "CLAIMS_EVALUATED"
    ASSERTIONS_EVALUATED = "ASSERTIONS_EVALUATED"
    DECISION_PENDING = "DECISION_PENDING"
    DECISION_RECORDED = "DECISION_RECORDED"
    CONTEXT_BOUND = "CONTEXT_BOUND"
    ACTION_PREPARED = "ACTION_PREPARED"
    ACTION_EVALUATED = "ACTION_EVALUATED"
    # MVP 1B — shadow Action Clearance stage (inserted before SHADOW_COMPLETE)
    CLEARANCE_PENDING = "CLEARANCE_PENDING"
    CLEARANCE_EVALUATED = "CLEARANCE_EVALUATED"
    INTERVENTION_ASSESSED = "INTERVENTION_ASSESSED"
    SHADOW_COMPLETE = "SHADOW_COMPLETE"

    # terminal / failure states (fail closed)
    STALE_ARTIFACT = "STALE_ARTIFACT"
    CLAIMS_INCOMPLETE = "CLAIMS_INCOMPLETE"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    CHAIN_INCOMPLETE = "CHAIN_INCOMPLETE"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    ERROR = "ERROR"
    # MVP 1B — fail-closed clearance-stage terminals
    CLEARANCE_INPUT_INCOMPLETE = "CLEARANCE_INPUT_INCOMPLETE"
    CLEARANCE_INTEGRITY_FAILURE = "CLEARANCE_INTEGRITY_FAILURE"
    CLEARANCE_EVALUATION_ERROR = "CLEARANCE_EVALUATION_ERROR"


#: States after which no further forward progress is possible in this phase.
TERMINAL_WORKFLOW_STATES = frozenset({
    WorkflowState.SHADOW_COMPLETE,
    WorkflowState.STALE_ARTIFACT,
    WorkflowState.CLAIMS_INCOMPLETE,
    WorkflowState.DECISION_REQUIRED,
    WorkflowState.CHAIN_INCOMPLETE,
    WorkflowState.BLOCKED,
    WorkflowState.ESCALATED,
    WorkflowState.ERROR,
    WorkflowState.CLEARANCE_INPUT_INCOMPLETE,
    WorkflowState.CLEARANCE_INTEGRITY_FAILURE,
    WorkflowState.CLEARANCE_EVALUATION_ERROR,
})


class WorkflowMode(str, Enum):
    """The only mode available in MVP 1A. Execution is unambiguously disabled."""

    SHADOW = "SHADOW"


class ExecutionStatus(str, Enum):
    """Execution capability of the product. Fixed to DISABLED in this phase."""

    DISABLED = "DISABLED"


class ActionEvaluationMode(str, Enum):
    """Marks an ActionGate evaluation as advisory-only, never execution clearance."""

    SHADOW_ONLY = "SHADOW_ONLY"


class ActionClearanceStatus(str, Enum):
    """Product-owned Action Clearance *stage* state recorded on the chain.

    ``NOT_EVALUATED`` is the MVP 1A default (the clearance stage did not run). MVP
    1B adds the shadow clearance stage outcomes. These are product coordination
    states, distinct from the canonical :class:`ClearanceStatus`
    (CLEAR/HOLD/BLOCK/ESCALATE), which is recorded separately on the evaluation
    record.
    """

    NOT_EVALUATED = "ACTION_CLEARANCE_NOT_EVALUATED"
    EVALUATED = "EVALUATED"
    NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED = "NOT_EVALUATED_UPSTREAM_NOT_AUTHORIZED"
    INPUT_INCOMPLETE = "INPUT_INCOMPLETE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    EVALUATION_ERROR = "EVALUATION_ERROR"


class ReconstructionState(str, Enum):
    """Outcome of a governance-chain reconstruction."""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"
    TENANT_MISMATCH = "TENANT_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"


__all__ = [
    "MergeMethod",
    "RiskTier",
    "ClaimType",
    "ClaimStatus",
    "ValidatorTrustLevel",
    "WorkflowState",
    "TERMINAL_WORKFLOW_STATES",
    "WorkflowMode",
    "ExecutionStatus",
    "ActionEvaluationMode",
    "ActionClearanceStatus",
    "ReconstructionState",
]
