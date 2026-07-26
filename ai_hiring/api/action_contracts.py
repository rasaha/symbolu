"""API-facing contracts for H4 action authorization/execution/reconciliation.

Request DTOs and read-model responses. No provider or vendor internals are exposed.
"""

from __future__ import annotations

from ..actions.action_types import HiringActionType
from ..domain.base import DomainModel


class ProposeActionRequest(DomainModel):
    recommendation_id: str
    action_type: HiringActionType
    target_system: str
    parameters: tuple[tuple[str, str], ...] = ()
    requested_effects: tuple[str, ...] = ()
    prohibited_effects: tuple[str, ...] = ()
    idempotency_key: str = ""


class AuthorizeActionRequest(DomainModel):
    action_proposal_id: str


class ExecuteActionRequest(DomainModel):
    action_proposal_id: str
    satisfied_obligations: tuple[str, ...] = ()


class ReconcileActionRequest(DomainModel):
    action_proposal_id: str


class ProposeCompensationRequest(DomainModel):
    action_proposal_id: str
    reversible: bool
    reason: str
