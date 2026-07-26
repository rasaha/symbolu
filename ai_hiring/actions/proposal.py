"""Immutable, versioned hiring-action proposal (H4).

A proposed hiring action derived from an eligible governed human decision. It is a
*proposal* — never self-executing. Authorization (ActionGate) and execution
(external port) are separate, later stages. Immutable; state changes create new
versions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError, IllegalActionTransitionError
from .action_types import HiringActionType
from .status import ActionProposalStatus, action_transition_allowed


class HiringActionProposal(DomainModel):
    action_proposal_id: str
    tenant_id: str
    application_id: str
    candidate_subject_ref: str
    decision_case_id: str
    human_decision_id: str
    recommendation_id: str
    recommendation_version: int
    action_type: HiringActionType
    target_system: str
    normalized_parameters: tuple[tuple[str, str], ...] = ()
    requested_effects: tuple[str, ...] = ()
    prohibited_effects: tuple[str, ...] = ()
    proposing_actor: str
    accountable_authority: str          # the human decision authority id
    policy_refs: tuple[str, ...] = ()
    correlation_id: str = ""
    causation_id: str = ""              # the human_decision_id that caused this proposal
    idempotency_key: str
    created_at: datetime = Field(default_factory=utc_now)
    status: ActionProposalStatus = ActionProposalStatus.DRAFT
    supersedes: str = ""
    compensation_for: str = ""          # set when this proposal compensates another
    version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> "HiringActionProposal":
        for req in ("action_proposal_id", "tenant_id", "application_id", "candidate_subject_ref",
                    "decision_case_id", "human_decision_id", "recommendation_id",
                    "target_system", "proposing_actor", "accountable_authority", "idempotency_key"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"HiringActionProposal.{req} is required")
        keys = [k for k, _ in self.normalized_parameters]
        if len(set(keys)) != len(keys):
            raise DomainValidationError("duplicate normalized parameter key")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    def params(self) -> dict[str, str]:
        return {k: v for k, v in self.normalized_parameters}

    def with_status(self, new_status: ActionProposalStatus) -> "HiringActionProposal":
        if new_status == self.status:
            raise IllegalActionTransitionError(
                f"action '{self.action_proposal_id}' is already {self.status.value}")
        if not action_transition_allowed(self.status, new_status):
            raise IllegalActionTransitionError(
                f"illegal action transition {self.status.value} -> {new_status.value}")
        data = self.model_dump()
        data["status"] = new_status
        data["version"] = self.version + 1
        return type(self)(**data)
