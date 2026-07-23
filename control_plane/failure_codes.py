"""Namespaced control-plane failure codes (Phase 7).

Existing component reason codes are NOT merged; they are wrapped under namespaces:
EXEC.* MODEL.* ASSERT.* ACTION.* RUNTIME.* AUDIT.* POLICY.*
"""
from __future__ import annotations

from enum import Enum


class Failure(str, Enum):
    # integration-level
    UPSTREAM_EXCLUSION_BYPASSED = "RUNTIME.UPSTREAM_EXCLUSION_BYPASSED"
    NO_ELIGIBLE_MODEL = "EXEC.NO_ELIGIBLE_MODEL"
    POLICY_VERSION_MISMATCH = "POLICY.POLICY_VERSION_MISMATCH"
    REGISTRY_VERSION_MISMATCH = "POLICY.REGISTRY_VERSION_MISMATCH"
    CONTRACT_VERSION_UNSUPPORTED = "POLICY.CONTRACT_VERSION_UNSUPPORTED"
    STALE_ELIGIBILITY_EVIDENCE = "EXEC.STALE_ELIGIBILITY_EVIDENCE"
    INVALID_SELECTION_INPUT = "MODEL.INVALID_SELECTION_INPUT"
    SELECTED_MODEL_NOT_ELIGIBLE = "MODEL.SELECTED_MODEL_NOT_ELIGIBLE"
    PROVIDER_EXECUTION_FAILED = "RUNTIME.PROVIDER_EXECUTION_FAILED"
    ASSERTION_REJECTED = "ASSERT.ASSERTION_REJECTED"
    ASSERTION_CONSTRAINED = "ASSERT.ASSERTION_CONSTRAINED"
    ASSERTION_ESCALATED = "ASSERT.ASSERTION_ESCALATED"
    ACTION_PROPOSAL_INVALID = "ACTION.ACTION_PROPOSAL_INVALID"
    ACTION_DENIED = "ACTION.ACTION_DENIED"
    ACTION_CONSTRAINED = "ACTION.ACTION_CONSTRAINED"
    ACTION_APPROVAL_REQUIRED = "ACTION.ACTION_APPROVAL_REQUIRED"
    ACTION_EXECUTION_FAILED = "RUNTIME.ACTION_EXECUTION_FAILED"
    TELEMETRY_WRITE_FAILED = "AUDIT.TELEMETRY_WRITE_FAILED"
    AUDIT_CHAIN_BROKEN = "AUDIT.AUDIT_CHAIN_BROKEN"
    HUMAN_AUTHORITY_UNRESOLVED = "ACTION.HUMAN_AUTHORITY_UNRESOLVED"
    POLICY_CONFLICT = "POLICY.POLICY_CONFLICT"
    GOVERNANCE_COMPONENT_UNAVAILABLE = "RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE"
    UNAUTHORIZED_OVERRIDE = "AUDIT.UNAUTHORIZED_OVERRIDE"
    RAW_PROVIDER_ERROR_LEAKED = "AUDIT.RAW_PROVIDER_ERROR_LEAKED"
    DATA_FLOW_NOT_APPROVED = "POLICY.DATA_FLOW_NOT_APPROVED"
    REPLAY_VERSION_MISMATCH = "POLICY.REPLAY_VERSION_MISMATCH"
    TRACE_INCOMPLETE = "AUDIT.TRACE_INCOMPLETE"
    CIRCULAR_DEPENDENCY_DETECTED = "RUNTIME.CIRCULAR_DEPENDENCY_DETECTED"


# Meta = (owning_component, originating_component, severity, recoverable,
#         retry_eligible, escalation_required, fail_mode)  — fail_mode is always "closed"
# for governance-critical failures (fail-closed is non-negotiable, Phase 8).
FAILURE_META = {
    Failure.UPSTREAM_EXCLUSION_BYPASSED:  ("Orchestrator", "any", "critical", False, False, True, "closed"),
    Failure.NO_ELIGIBLE_MODEL:            ("ExecutionGate", "ExecutionGate", "high", True, False, False, "closed"),
    Failure.POLICY_VERSION_MISMATCH:      ("PolicyContext", "any", "high", True, False, False, "closed"),
    Failure.REGISTRY_VERSION_MISMATCH:    ("PolicyContext", "any", "high", True, False, False, "closed"),
    Failure.CONTRACT_VERSION_UNSUPPORTED: ("Orchestrator", "any", "high", False, False, False, "closed"),
    Failure.STALE_ELIGIBILITY_EVIDENCE:   ("ExecutionGate", "ExecutionGate", "medium", True, True, False, "closed"),
    Failure.INVALID_SELECTION_INPUT:      ("ModelPolicy", "ExecutionGate", "high", False, False, False, "closed"),
    Failure.SELECTED_MODEL_NOT_ELIGIBLE:  ("Orchestrator", "ModelPolicy", "critical", True, False, True, "closed"),
    Failure.PROVIDER_EXECUTION_FAILED:    ("ProviderAdapter", "Provider", "medium", True, True, False, "closed"),
    Failure.ASSERTION_REJECTED:           ("Assertion", "Assertion", "high", False, False, True, "closed"),
    Failure.ASSERTION_CONSTRAINED:        ("Assertion", "Assertion", "medium", True, False, False, "closed"),
    Failure.ASSERTION_ESCALATED:          ("Assertion", "Assertion", "medium", True, False, True, "closed"),
    Failure.ACTION_PROPOSAL_INVALID:      ("ActionProposalLayer", "ActionProposalLayer", "medium", False, False, False, "closed"),
    Failure.ACTION_DENIED:                ("ActionGate", "ActionGate", "high", False, False, True, "closed"),
    Failure.ACTION_CONSTRAINED:           ("ActionGate", "ActionGate", "medium", True, False, False, "closed"),
    Failure.ACTION_APPROVAL_REQUIRED:     ("ActionGate", "ActionGate", "high", True, False, True, "closed"),
    Failure.ACTION_EXECUTION_FAILED:      ("ActionAdapter", "ActionAdapter", "high", True, True, True, "closed"),
    Failure.TELEMETRY_WRITE_FAILED:       ("Telemetry", "Telemetry", "medium", True, True, False, "closed"),
    Failure.AUDIT_CHAIN_BROKEN:           ("Audit", "Audit", "critical", False, False, True, "closed"),
    Failure.HUMAN_AUTHORITY_UNRESOLVED:   ("ActionGate", "Human", "high", True, False, True, "closed"),
    Failure.POLICY_CONFLICT:              ("PolicyContext", "any", "high", False, False, True, "closed"),
    Failure.GOVERNANCE_COMPONENT_UNAVAILABLE: ("Orchestrator", "Assertion|ActionGate", "high", True, False, True, "closed"),
    Failure.UNAUTHORIZED_OVERRIDE:        ("Audit", "any", "critical", False, False, True, "closed"),
    Failure.RAW_PROVIDER_ERROR_LEAKED:    ("Orchestrator", "ProviderAdapter", "high", False, False, True, "closed"),
    Failure.DATA_FLOW_NOT_APPROVED:       ("PolicyContext", "any", "critical", False, False, True, "closed"),
    Failure.REPLAY_VERSION_MISMATCH:      ("ReplayEngine", "ReplayEngine", "medium", False, False, False, "closed"),
    Failure.TRACE_INCOMPLETE:             ("Audit", "Orchestrator", "high", False, False, True, "closed"),
    Failure.CIRCULAR_DEPENDENCY_DETECTED: ("Orchestrator", "Telemetry", "critical", False, False, True, "closed"),
}

_FIELDS = ("owning_component", "originating_component", "severity", "recoverable",
           "retry_eligible", "escalation_required", "fail_mode")


def meta(code: "Failure") -> dict:
    return dict(zip(_FIELDS, FAILURE_META[code]))
