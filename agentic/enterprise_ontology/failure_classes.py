"""
Generic cross-vertical failure taxonomy + Finding.

The generic class groups structurally-equivalent failures across verticals; the
original vertical/domain reason code is preserved alongside it so nothing is
lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from agentic.enterprise_ontology.layers import OntologyLayer
from agentic.enterprise_ontology.verticals import EnterpriseVertical


class FailureClass(str, Enum):
    IDENTITY_AUTHORITY_VIOLATION = "IDENTITY_AUTHORITY_VIOLATION"
    PURPOSE_POLICY_VIOLATION = "PURPOSE_POLICY_VIOLATION"
    FORM_EXECUTION_MISMATCH = "FORM_EXECUTION_MISMATCH"
    CROSS_VERTICAL_DEPENDENCY_FAILURE = "CROSS_VERTICAL_DEPENDENCY_FAILURE"
    CORE_INVARIANT_BREACH = "CORE_INVARIANT_BREACH"
    UNIVERSAL_CONSTRAINT_BREACH = "UNIVERSAL_CONSTRAINT_BREACH"
    EXECUTION_OBSERVATION_MISMATCH = "EXECUTION_OBSERVATION_MISMATCH"
    STATE_RECONCILIATION_FAILURE = "STATE_RECONCILIATION_FAILURE"
    ADVISORY_AUTHORITY_ESCALATION = "ADVISORY_AUTHORITY_ESCALATION"
    MISSING_VERIFIED_PURPOSE = "MISSING_VERIFIED_PURPOSE"
    MISSING_AUTHORITY_BASIS = "MISSING_AUTHORITY_BASIS"
    STALE_OR_CONFLICTING_EVIDENCE = "STALE_OR_CONFLICTING_EVIDENCE"


@dataclass(frozen=True)
class Finding:
    failure_class: FailureClass
    invariant: str
    detail: str
    verticals: Tuple[EnterpriseVertical, ...] = ()
    layers: Tuple[OntologyLayer, ...] = ()
    vertical_reason_code: Optional[str] = None  # original, preserved
    record_refs: Tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "failure_class": self.failure_class.value,
            "invariant": self.invariant,
            "detail": self.detail,
            "verticals": [v.value for v in self.verticals],
            "layers": [l.value for l in self.layers],
            "vertical_reason_code": self.vertical_reason_code,
            "record_refs": list(self.record_refs),
        }
