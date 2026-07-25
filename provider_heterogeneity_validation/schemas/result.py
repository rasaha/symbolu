"""Neutral heterogeneity result — one per (scenario, configuration) run."""
from __future__ import annotations

from dataclasses import dataclass, field

NOT_APPLICABLE = "NOT_APPLICABLE"
NOT_PERFORMED = "NOT_PERFORMED"


@dataclass
class HeteroResult:
    scenario_id: str
    configuration_id: str

    # assertion resolution + outcome
    assertion_selection: object = None            # SelectionRecord
    assertion_provider_id: str = ""
    assertion_outcome: str = NOT_PERFORMED        # SUPPORTED/UNSUPPORTED/CONSTRAINED/INDETERMINATE
    assertion_fallback_used: bool = False
    no_valid_assertion_provider: bool = False

    # action resolution + outcome
    action_selection: object = None
    action_provider_id: str = ""
    authorization_outcome: str = NOT_PERFORMED
    action_fallback_used: bool = False
    no_valid_action_provider: bool = False
    constraints: tuple = ()
    obligations: tuple = ()

    # execution / reconciliation
    dispatched: bool = False
    execution_outcome: str = NOT_PERFORMED
    reconciliation_outcome: str = NOT_PERFORMED
    final_governance_compliance: str = NOT_APPLICABLE

    human_review_requested: bool = False
    human_authority: str = ""

    audit_events: int = 0
    trace_links: int = 0
    cost: dict = field(default_factory=dict)
    trace: dict = field(default_factory=dict)
    error: object = None
