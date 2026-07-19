"""
Baseline representation + Scenario container + comparison scaffolding.

The BASELINE models ordinary per-vertical workflow/audit records: each vertical
logs its own step with its own fields and (optionally) its own local flag. It has
no shared epistemic/authority vocabulary and no cross-vertical linkage — which is
exactly what we are testing the ontology against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Mapping, Tuple

from agentic.enterprise_ontology.events import EnterpriseEventEnvelope
from agentic.enterprise_ontology.failure_classes import FailureClass
from agentic.enterprise_ontology.verticals import EnterpriseVertical


@dataclass(frozen=True)
class BaselineWorkflowRecord:
    """One ordinary vertical-local workflow/audit entry."""
    vertical: EnterpriseVertical
    step: str
    status: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    # A local flag the vertical's own system could raise WITHOUT cross-vertical
    # context. Cross-vertical failure classes are, by construction, absent here.
    local_flag: FailureClass | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    envelope: EnterpriseEventEnvelope
    baseline: Tuple[BaselineWorkflowRecord, ...]
    expected_failure_classes: FrozenSet[FailureClass]
    notes: str = ""


def baseline_detectable(scenario: Scenario) -> FrozenSet[FailureClass]:
    """Failure classes a naive per-vertical baseline could surface on its own."""
    return frozenset(
        b.local_flag for b in scenario.baseline if b.local_flag is not None)
