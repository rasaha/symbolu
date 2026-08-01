"""Action governance contract (future implementation: ActionGate).

An action-governance provider authorizes a *prepared action* under runtime
controls. It adapts onto the frozen kernel ``ActionControlPlanePort``. The
vocabulary is provider-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping, Optional, Protocol, runtime_checkable

from .base import Provider


class ActionGovernanceOutcome(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ActionGovernanceRequest:
    """A neutral request to authorize a prepared action."""

    action_type: str
    requested_parameters: Mapping[str, str] = field(default_factory=dict)
    actor: str = ""
    authority_context: str = ""
    target_resource: str = ""
    policy_refs: tuple[str, ...] = ()
    risk_context: Mapping[str, str] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    decision_refs: tuple[str, ...] = ()
    idempotency_key: str = ""
    correlation_id: str = ""
    authorization_expired: bool = False


@dataclass(frozen=True)
class ActionGovernanceResult:
    """A neutral authorization outcome."""

    outcome: ActionGovernanceOutcome
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    expiry: Optional[datetime] = None
    authority_basis: str = ""
    reason_codes: tuple[str, ...] = ()
    provider_trace_id: str = ""
    fingerprint: str = ""


@runtime_checkable
class ActionGovernanceProvider(Provider, Protocol):
    """Authorize a prepared action under runtime controls."""

    def authorize(self, request: ActionGovernanceRequest) -> ActionGovernanceResult: ...
