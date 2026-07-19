"""
Enterprise event envelope: sparse ontology records across verticals, plus the
cross-vertical dependency / decision / execution graph and reconciliation state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agentic.enterprise_ontology.layers import OntologyLayer
from agentic.enterprise_ontology.records import OntologyRecord
from agentic.enterprise_ontology.verticals import EnterpriseVertical


class DecisionEffect(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_CONSTRAINTS = "allow_with_constraints"
    WIDEN = "widen"                # relaxes/expands a prior constraint
    DEFER = "defer"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


PERMISSIVE_EFFECTS = frozenset({
    DecisionEffect.ALLOW, DecisionEffect.ALLOW_WITH_CONSTRAINTS, DecisionEffect.WIDEN,
})


class DependencyStatus(str, Enum):
    SATISFIED = "satisfied"
    ABSENT = "absent"
    STALE = "stale"
    DENIED = "denied"
    PENDING = "pending"


@dataclass(frozen=True)
class VerticalDependency:
    """`from_vertical` requires an upstream fact/approval from `to_vertical`."""
    from_vertical: EnterpriseVertical
    to_vertical: EnterpriseVertical
    requires_record_id: Optional[str]     # the upstream record this depends on
    status: DependencyStatus
    description: str = ""


@dataclass(frozen=True)
class VerticalDecision:
    decision_id: str
    vertical: EnterpriseVertical
    effect: DecisionEffect
    description: str
    supporting_record_ids: Tuple[str, ...] = ()
    reason_code: Optional[str] = None
    overrides_core_record_id: Optional[str] = None  # set only if it overrides a Core invariant


@dataclass(frozen=True)
class ExecutionRecord:
    execution_id: str
    vertical: EnterpriseVertical
    system: str                            # CRM / ERP / IAM / payroll / ...
    subject_key: str                       # what state this touches (e.g. "quote:Q1")
    authorized_form: Optional[str]         # form the authorization permitted
    executed_form: Optional[str]           # form actually executed
    resulting_state: Any                   # system's post-execution view of subject_key
    observation_ref: Optional[str] = None  # OntologyRecord id in OBSERVATION layer


@dataclass(frozen=True)
class EnterpriseEventEnvelope:
    event_id: str
    event_type: str
    records: Tuple[OntologyRecord, ...]
    dependencies: Tuple[VerticalDependency, ...] = ()
    decisions: Tuple[VerticalDecision, ...] = ()
    executions: Tuple[ExecutionRecord, ...] = ()
    reconciliation_status: str = "pending"

    # ---- lookups -----------------------------------------------------------

    def record_by_id(self, rid: Optional[str]) -> Optional[OntologyRecord]:
        if rid is None:
            return None
        for r in self.records:
            if r.record_id == rid:
                return r
        return None

    def records_in_layer(self, layer: OntologyLayer) -> List[OntologyRecord]:
        return [r for r in self.records if r.layer == layer]

    def records_for_vertical(self, v: EnterpriseVertical) -> List[OntologyRecord]:
        return [r for r in self.records if r.vertical == v]

    def layers_present(self) -> set:
        return {r.layer for r in self.records}

    def verticals_present(self) -> set:
        return {r.vertical for r in self.records}
