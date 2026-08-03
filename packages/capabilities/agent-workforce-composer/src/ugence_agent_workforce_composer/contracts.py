"""Neutral, data-only mirrors of the upstream compiler workflow-IR vocabulary.

The Agent Workforce Composer is a **leaf capability**: it must build, install and
import outside the monorepo without importing ``ugence_policy_workflow_compiler``.
The compiler seam is therefore *data-only* — the adapter consumes a serialized
``workflow_ir.v1`` document (a dict / JSON), and these enums reproduce the
upstream vocabulary by **value** so that serialized IR parses losslessly. The
string values are frozen against the live compiler contract
(``workflow_ir.py`` :class:`NodeKind` / :class:`EdgeKind`,
``models/common.py`` :class:`AuthorityDisposition` / :class:`CapabilityId`).

Nothing here makes a governance decision; these are declarative labels only.
"""
from __future__ import annotations

from enum import Enum


class NodeKind(str, Enum):
    """The 14 governed-workflow node kinds (mirror of compiler ``workflow_ir.v1``)."""

    EVIDENCE_REQUIREMENT = "EVIDENCE_REQUIREMENT"
    EVIDENCE_ADMISSIBILITY = "EVIDENCE_ADMISSIBILITY"
    DECISION_RULE = "DECISION_RULE"
    AUTHORITY_CHECK = "AUTHORITY_CHECK"
    APPROVAL_GATE = "APPROVAL_GATE"
    SEGREGATION_OF_DUTIES_GATE = "SEGREGATION_OF_DUTIES_GATE"
    PROHIBITED_CONDITION = "PROHIBITED_CONDITION"
    EXCEPTION_BRANCH = "EXCEPTION_BRANCH"
    OVERRIDE_GATE = "OVERRIDE_GATE"
    ACTION_CONSTRAINT = "ACTION_CONSTRAINT"
    SEQUENCE_RISK_CHECK = "SEQUENCE_RISK_CHECK"
    ACTION_CLEARANCE_REQUIREMENT = "ACTION_CLEARANCE_REQUIREMENT"
    AUDIT_EMISSION = "AUDIT_EMISSION"
    TERMINAL_OUTCOME = "TERMINAL_OUTCOME"


class EdgeKind(str, Enum):
    """The 9 typed edge kinds (mirror of compiler ``workflow_ir.v1``)."""

    NEXT = "NEXT"
    ON_PASS = "ON_PASS"
    ON_FAIL = "ON_FAIL"
    ON_MISSING = "ON_MISSING"
    ON_EXCEPTION = "ON_EXCEPTION"
    ON_OVERRIDE = "ON_OVERRIDE"
    ON_ESCALATE = "ON_ESCALATE"
    ON_DENY = "ON_DENY"
    ON_INDETERMINATE = "ON_INDETERMINATE"


class AuthorityDisposition(str, Enum):
    """Whether a node is advisory (produces evidence/recommendation) or
    authoritative (owns a binding gate). Mirror of the compiler enum."""

    ADVISORY = "ADVISORY"
    AUTHORITATIVE = "AUTHORITATIVE"


class CapabilityOwner(str, Enum):
    """The governance capability that owns a workflow node.

    Values mirror the compiler ``CapabilityId``. ``COMPILER`` marks the compiler's
    own *structural* nodes — the only advisory nodes that may become agent work.
    """

    TAP = "TAP"
    DECISION_AUTHORITY = "DECISION_AUTHORITY"
    ACTION_GATE = "ACTION_GATE"
    ACTION_CLEARANCE = "ACTION_CLEARANCE"
    STORYGRAPH = "STORYGRAPH"
    MODEL_SELECTION = "MODEL_SELECTION"
    OPTIONAL_ORCHESTRATOR = "OPTIONAL_ORCHESTRATOR"
    COMPILER = "COMPILER"


#: Authoritative governance capabilities whose nodes may never become agent work.
AUTHORITATIVE_GOVERNANCE_OWNERS = frozenset(
    {
        CapabilityOwner.DECISION_AUTHORITY,
        CapabilityOwner.ACTION_GATE,
        CapabilityOwner.ACTION_CLEARANCE,
    }
)

#: Advisory governance capabilities that own their step (never ordinary agent work).
ADVISORY_GOVERNANCE_OWNERS = frozenset(
    {
        CapabilityOwner.TAP,
        CapabilityOwner.STORYGRAPH,
        CapabilityOwner.MODEL_SELECTION,
    }
)

#: Human-authority labels (from the compiler ``AuthorityType`` vocabulary) that,
#: when named on a node, force a human-authority disposition.
HUMAN_AUTHORITY_TYPES = frozenset(
    {"HUMAN_REVIEWER", "HUMAN_APPROVER", "COMMITTEE", "EXTERNAL_AUTHORITY"}
)


class NodeDisposition(str, Enum):
    """Canonical disposition of a workflow node under P1 offline adaptation.

    Exactly one is assigned to every workflow node. ``AI_AGENT_ELIGIBLE`` yields a
    :class:`WorkflowRoleRequirement`; every other value yields a
    :class:`NonAgentDisposition`.
    """

    AI_AGENT_ELIGIBLE = "AI_AGENT_ELIGIBLE"
    NO_AI_AGENT_REQUIRED = "NO_AI_AGENT_REQUIRED"
    DETERMINISTIC_SERVICE_PREFERRED = "DETERMINISTIC_SERVICE_PREFERRED"
    HUMAN_AUTHORITY_REQUIRED = "HUMAN_AUTHORITY_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP = "EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP"
    UNSUPPORTED_NODE = "UNSUPPORTED_NODE"
    INVALID_NODE = "INVALID_NODE"


#: The seven non-agent dispositions (everything except AI_AGENT_ELIGIBLE).
NON_AGENT_DISPOSITIONS = frozenset(d for d in NodeDisposition if d is not NodeDisposition.AI_AGENT_ELIGIBLE)


class EvidenceClass(str, Enum):
    """Provenance class of a capability-evidence item.

    Trust precedence is ``OBSERVED > MEASURED > DECLARED`` (see
    :data:`EVIDENCE_PRECEDENCE`). A declared claim is never sufficient for a hard
    requirement that mandates measured or observed evidence.
    """

    DECLARED = "DECLARED"
    MEASURED = "MEASURED"
    OBSERVED = "OBSERVED"


#: Fixed trust precedence (higher wins). Verified against Model Selection's
#: ``SOURCE_PRECEDENCE`` (live_probe/telemetry > cache/config > provider_declared)
#: and the AWC Phase 0 design (DESIGN_SPEC §9): observed > measured > declared.
EVIDENCE_PRECEDENCE = {
    EvidenceClass.OBSERVED: 3,
    EvidenceClass.MEASURED: 2,
    EvidenceClass.DECLARED: 1,
}


class EligibilityState(str, Enum):
    """The terminal state of a role × agent eligibility evaluation."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INDETERMINATE = "INDETERMINATE"
    INVALID_INPUT = "INVALID_INPUT"


class Verdict(str, Enum):
    """The outcome of a single hard-constraint condition."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Criticality(str, Enum):
    """Constraint criticality class — governs fail-closed behaviour."""

    CRITICAL_GOV = "CRITICAL_GOV"   # governance / authority / residency -> always fail-closed
    CRITICAL_OP = "CRITICAL_OP"     # correctness / spend safety -> fail-closed by default
    OPERATIONAL = "OPERATIONAL"     # transient / QoS -> configurable


#: The typed marker on the empty-eligible-set outcome (I12: no empty-success ambiguity).
NO_ELIGIBLE_AGENT = "NO_ELIGIBLE_AGENT"


__all__ = [
    "NodeKind",
    "EdgeKind",
    "AuthorityDisposition",
    "CapabilityOwner",
    "AUTHORITATIVE_GOVERNANCE_OWNERS",
    "ADVISORY_GOVERNANCE_OWNERS",
    "HUMAN_AUTHORITY_TYPES",
    "NodeDisposition",
    "NON_AGENT_DISPOSITIONS",
    "EvidenceClass",
    "EVIDENCE_PRECEDENCE",
    "EligibilityState",
    "Verdict",
    "Criticality",
    "NO_ELIGIBLE_AGENT",
]
