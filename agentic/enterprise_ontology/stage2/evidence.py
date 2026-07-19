"""
Concept-specific evidence structures (stage-2 only; not production schemas).

Each is attached as an ``OntologyRecord.value`` so the sparse record model is
preserved. Invariants detect them by type, independent of the record's layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class PotentialEvidence:
    """Pre-action capability / plan space reachable by an agent."""
    available_capabilities: Tuple[str, ...]
    permitted_capabilities: Tuple[str, ...]
    prohibited_capabilities: Tuple[str, ...]
    reachable_plan_branches: Tuple[str, ...] = ()
    capability_source_refs: Tuple[str, ...] = ()
    revoked_capabilities: Tuple[str, ...] = ()
    approval_required_capabilities: Tuple[str, ...] = ()
    approvals_present: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CognitionEvidence:
    """One model/analytical advisory output."""
    source_model: str
    model_version: str
    advisory_decision: str        # a stance, e.g. "expand" / "do_not_expand"
    confidence: Optional[float] = None
    uncertainty: Optional[float] = None
    rationale_ref: Optional[str] = None
    approval_status: str = "approved"   # approved / unapproved / stale


@dataclass(frozen=True)
class ReasoningEvidence:
    """A vertical's derivation path for its decision."""
    vertical_reasoning_for: str            # decision id this justifies
    matched_rule_ids: Tuple[str, ...] = ()
    policy_versions: Tuple[str, ...] = ()  # "name@version" pairs
    derivation_steps: Tuple[str, ...] = () # edges "child<-parent"
    exception_refs: Tuple[str, ...] = ()
    override_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class StateAssertion:
    system: str
    key: str
    value: Any


@dataclass(frozen=True)
class StateConflict:
    key: str
    systems: Tuple[str, ...]
    values: Tuple[Any, ...]
    detail: str = ""


@dataclass(frozen=True)
class IntegrationEvidence:
    """Intended vs observed final enterprise state + closure conditions."""
    intended_final_state: Tuple[StateAssertion, ...] = ()
    observed_final_state: Tuple[StateAssertion, ...] = ()
    unresolved_conflicts: Tuple[StateConflict, ...] = ()
    required_closure_conditions: Tuple[str, ...] = ()
    satisfied_closure_conditions: Tuple[str, ...] = ()
    marked_complete: bool = False
