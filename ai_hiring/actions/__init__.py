"""H4 hiring action authorization, execution, and reconciliation."""
from __future__ import annotations

from .action_types import (
    ACTION_CONSEQUENCE, DECISION_ALLOWED_ACTIONS, ActionConsequence, HiringActionType,
    action_allowed_for_decision)
from .actiongate_integration import ActionAuthorizationIntegration
from .execution_port import DeterministicHiringExecutionAdapter
from .proposal import HiringActionProposal
from .records import (
    ActionAuthorizationRecord, CompensationRequirement, CompensationStatus, ExecutionAttempt,
    ExecutionErrorClass, ExecutionReceipt, ReconciliationOutcome, ReconciliationRecord)
from .status import (
    ACTION_TERMINAL_STATUSES, ActionProposalStatus, action_transition_allowed)

__all__ = [
    "HiringActionType", "ActionConsequence", "ACTION_CONSEQUENCE", "DECISION_ALLOWED_ACTIONS",
    "action_allowed_for_decision", "HiringActionProposal", "ActionProposalStatus",
    "ACTION_TERMINAL_STATUSES", "action_transition_allowed",
    "ActionAuthorizationIntegration", "ActionAuthorizationRecord",
    "DeterministicHiringExecutionAdapter", "ExecutionAttempt", "ExecutionReceipt",
    "ExecutionErrorClass", "ReconciliationRecord", "ReconciliationOutcome",
    "CompensationRequirement", "CompensationStatus",
]
