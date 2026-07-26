"""Immutable H4 records: authorization, execution attempt/receipt, reconciliation,
compensation.

These pin the *exact* facts of each stage so the full decision→outcome chain is
reconstructable and tamper-evident. Transport (dispatch) is kept distinct from the
observed business outcome (the receipt), so a successful API response never implies
a successful business result or reconciliation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field, model_validator

from decision_governance.api.common import canonical_hash

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError


def params_hash(params: tuple[tuple[str, str], ...]) -> str:
    return canonical_hash({k: v for k, v in params})


# --- authorization ----------------------------------------------------------
class ActionAuthorizationRecord(DomainModel):
    authorization_id: str
    tenant_id: str
    action_proposal_id: str
    action_type: str
    outcome: str                       # ActionGovernanceOutcome value
    authorized: bool
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    expiry: Optional[datetime] = None
    authority_basis: str = ""
    reason_codes: tuple[str, ...] = ()
    provider_id: str = ""
    provider_trace_id: str = ""
    fingerprint: str = ""
    # exact binding — a change to any material field requires a new authorization
    bound_actor: str = ""
    bound_target: str = ""
    bound_parameter_hash: str = ""
    idempotency_key: str = ""
    correlation_id: str = ""
    causation_id: str = ""             # the action_proposal_id
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "ActionAuthorizationRecord":
        for req in ("authorization_id", "tenant_id", "action_proposal_id", "action_type"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"ActionAuthorizationRecord.{req} is required")
        return self


# --- execution receipt (observed business outcome) --------------------------
class ExecutionReceipt(DomainModel):
    receipt_id: str
    business_outcome: str              # ExecutionBusinessOutcome value
    observed_parameters: tuple[tuple[str, str], ...] = ()
    final: bool = True
    reason: str = ""
    target_system: str = ""
    provider_trace_id: str = ""
    fingerprint: str = ""
    raw_receipt_ref: str = ""


class ExecutionErrorClass(str, Enum):
    NONE = "NONE"
    RETRYABLE = "RETRYABLE"
    TERMINAL = "TERMINAL"
    INDETERMINATE = "INDETERMINATE"


# --- execution attempt (immutable) ------------------------------------------
class ExecutionAttempt(DomainModel):
    attempt_id: str
    tenant_id: str
    action_proposal_id: str
    authorization_id: str
    target_system: str
    action_type: str
    request_parameter_hash: str
    attempt_number: int
    idempotency_key: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    adapter_id: str = ""
    transport_accepted: bool = False
    transport_error: str = ""
    external_request_id: str = ""
    execution_status: str = "UNKNOWN"  # ExecutionBusinessOutcome value
    receipt: Optional[ExecutionReceipt] = None
    error_classification: ExecutionErrorClass = ExecutionErrorClass.NONE
    correlation_id: str = ""
    causation_id: str = ""             # the authorization_id

    @model_validator(mode="after")
    def _validate(self) -> "ExecutionAttempt":
        for req in ("attempt_id", "tenant_id", "action_proposal_id", "authorization_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"ExecutionAttempt.{req} is required")
        if self.attempt_number < 1:
            raise DomainValidationError("attempt_number must be >= 1")
        return self


# --- reconciliation ---------------------------------------------------------
class ReconciliationOutcome(str, Enum):
    MATCHED = "MATCHED"
    PARTIALLY_MATCHED = "PARTIALLY_MATCHED"
    MISMATCHED = "MISMATCHED"
    NOT_EXECUTED = "NOT_EXECUTED"
    DUPLICATE_EXECUTION = "DUPLICATE_EXECUTION"
    UNVERIFIABLE = "UNVERIFIABLE"
    COMPENSATION_REQUIRED = "COMPENSATION_REQUIRED"


class ReconciliationRecord(DomainModel):
    reconciliation_id: str
    tenant_id: str
    action_proposal_id: str
    human_decision_id: str = ""
    authorization_id: str = ""
    attempt_id: str = ""
    outcome: ReconciliationOutcome
    matched_fields: tuple[str, ...] = ()
    mismatched_fields: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    compensation_required: bool = False
    correlation_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)


# --- compensation -----------------------------------------------------------
class CompensationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    HUMAN_REMEDIATION_REQUIRED = "HUMAN_REMEDIATION_REQUIRED"
    RESOLVED = "RESOLVED"


class CompensationRequirement(DomainModel):
    compensation_id: str
    tenant_id: str
    action_proposal_id: str            # the original action needing compensation
    reason: str
    reversible: bool
    requires_human_remediation: bool = False
    proposed_compensation_action_id: str = ""   # a new proposed action (separately authorized)
    status: CompensationStatus = CompensationStatus.PROPOSED
    correlation_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "CompensationRequirement":
        for req in ("compensation_id", "tenant_id", "action_proposal_id", "reason"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"CompensationRequirement.{req} is required")
        return self
