"""Execution receipt and reconciliation record — hiring-domain artifacts.

``HiringExecutionReceipt`` is the immutable record of an HRIS/ATS execution
attempt made only after action authorization AND runtime assurance passed.
``HiringReconciliationRecord`` compares the authorized action to the executed
action and resulting HRIS state and emits a hiring-domain status. The shared,
cross-system reconciliation *engine* stays external (``ReconciliationPort``);
this record is the hiring-domain view only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, new_id, utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .action_request import HiringActionSnapshot
from .enums import ExecutionStatus, ReconciliationStatus
from .ports import ExecutionOutcome
from .refs import ContractRef


class HiringExecutionReceipt(DomainModel):
    """Immutable record of a governed HRIS/ATS execution attempt."""

    receipt_id: str = Field(default_factory=lambda: new_id("hrcpt"))
    decision_case_id: str
    contract_ref: ContractRef
    binding_decision_id: str
    binding_authority_id: str
    action_request_id: str
    action_request_digest: str
    authorization_ref: str
    assurance_ref: str
    hris_execution_ref: str
    actor: str
    authorized_at: datetime
    assured_at: datetime
    executed_at: datetime
    execution_status: ExecutionStatus
    result_digest: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "HiringExecutionReceipt":
        for field in (
            "decision_case_id",
            "binding_decision_id",
            "action_request_id",
            "action_request_digest",
            "actor",
        ):
            if not getattr(self, field).strip():
                raise DomainValidationError(f"{field} is required on an execution receipt")
        return self


class HiringReconciliationRecord(DomainModel):
    """Hiring-domain comparison of authorized vs executed action + HRIS state."""

    record_id: str = Field(default_factory=lambda: new_id("hrec-rc"))
    decision_case_id: str
    contract_ref: ContractRef
    receipt_id: str
    authorized_action: HiringActionSnapshot
    executed_action: Optional[HiringActionSnapshot] = None
    hris_state: dict = {}
    status: ReconciliationStatus
    external_reconciliation_ref: Optional[str] = None
    reconciled_at: datetime = Field(default_factory=utc_now)


def classify_reconciliation(
    authorized_action: HiringActionSnapshot, outcome: ExecutionOutcome
) -> ReconciliationStatus:
    """Deterministic hiring-domain equivalence (authorized vs executed + state)."""
    if outcome.status is ExecutionStatus.FAILED:
        return ReconciliationStatus.FAILED
    if outcome.status is ExecutionStatus.OUTCOME_UNKNOWN or outcome.executed_action is None:
        return ReconciliationStatus.UNKNOWN
    if outcome.executed_action != authorized_action:
        return ReconciliationStatus.DEVIATION
    # actions match; HRIS state must confirm the write to be fully reconciled
    if not outcome.hris_state:
        return ReconciliationStatus.PARTIAL
    return ReconciliationStatus.RECONCILED


def build_reconciliation_record(
    *,
    decision_case_id: str,
    contract_ref: ContractRef,
    receipt_id: str,
    authorized_action: HiringActionSnapshot,
    outcome: ExecutionOutcome,
    external_reconciliation_ref: Optional[str] = None,
    now: Optional[datetime] = None,
) -> HiringReconciliationRecord:
    status = classify_reconciliation(authorized_action, outcome)
    kwargs = {
        "decision_case_id": decision_case_id,
        "contract_ref": contract_ref,
        "receipt_id": receipt_id,
        "authorized_action": authorized_action,
        "executed_action": outcome.executed_action,
        "hris_state": dict(outcome.hris_state),
        "status": status,
        "external_reconciliation_ref": external_reconciliation_ref,
    }
    if now is not None:
        kwargs["reconciled_at"] = now
    return HiringReconciliationRecord(**kwargs)
