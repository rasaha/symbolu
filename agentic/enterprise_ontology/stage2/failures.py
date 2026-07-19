"""Stage-2 failure taxonomy + finding (kept separate from stage-1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class Concept(str, Enum):
    POTENTIAL = "potential"
    COGNITION = "cognition"
    REASONING = "reasoning"
    INTEGRATION = "integration"


class Stage2FailureClass(str, Enum):
    # Potential
    PROHIBITED_CAPABILITY_EXPOSURE = "PROHIBITED_CAPABILITY_EXPOSURE"
    POTENTIAL_AUTHORITY_MISMATCH = "POTENTIAL_AUTHORITY_MISMATCH"
    UNAUTHORIZED_PLAN_BRANCH = "UNAUTHORIZED_PLAN_BRANCH"
    STALE_CAPABILITY_STATE = "STALE_CAPABILITY_STATE"
    # Cognition
    ADVISORY_CONFLICT = "ADVISORY_CONFLICT"
    UNAPPROVED_MODEL_RELIANCE = "UNAPPROVED_MODEL_RELIANCE"
    COGNITIVE_SOURCE_MISMATCH = "COGNITIVE_SOURCE_MISMATCH"
    CONFIDENCE_PROVENANCE_GAP = "CONFIDENCE_PROVENANCE_GAP"
    ADVISORY_AUTHORITY_ESCALATION = "ADVISORY_AUTHORITY_ESCALATION"
    # Reasoning
    POLICY_VERSION_CONFLICT = "POLICY_VERSION_CONFLICT"
    REASONING_PROVENANCE_GAP = "REASONING_PROVENANCE_GAP"
    INCOMPATIBLE_RULE_BASIS = "INCOMPATIBLE_RULE_BASIS"
    UNJUSTIFIED_OVERRIDE = "UNJUSTIFIED_OVERRIDE"
    DERIVATION_CHAIN_FAILURE = "DERIVATION_CHAIN_FAILURE"
    # Integration
    STATE_RECONCILIATION_FAILURE = "STATE_RECONCILIATION_FAILURE"
    INCOMPLETE_ENTERPRISE_TRANSITION = "INCOMPLETE_ENTERPRISE_TRANSITION"
    CROSS_SYSTEM_STATE_CONFLICT = "CROSS_SYSTEM_STATE_CONFLICT"
    PREMATURE_EVENT_CLOSURE = "PREMATURE_EVENT_CLOSURE"
    UNRESOLVED_INTEGRATION_DEPENDENCY = "UNRESOLVED_INTEGRATION_DEPENDENCY"


@dataclass(frozen=True)
class Stage2Finding:
    concept: Concept
    failure_class: Stage2FailureClass
    invariant: str
    detail: str
    refs: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "concept": self.concept.value,
            "failure_class": self.failure_class.value,
            "invariant": self.invariant,
            "detail": self.detail,
            "refs": list(self.refs),
        }
