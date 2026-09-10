"""Transport-neutral request/response DTOs for the RA-1..RA-4 API surface.

Plain dataclasses so the package stays stdlib-only; ``api.routes`` maps these
onto FastAPI models when FastAPI is available. The eight shapes here mirror the
eight endpoints in the MVP API (user brief §21).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..domain.enums import ActionGateDecision, RiskClass, RiskOutcome
from ..domain.scope import Scope

__all__ = [
    "CreateCaseRequest",
    "ControlResultInput",
    "EvaluateRequest",
    "DecisionRequest",
    "IssueEnvelopeRequest",
    "AuthorizeActionRequest",
    "VerifyResponse",
]


@dataclass(frozen=True)
class CreateCaseRequest:
    tenant_id: str
    case_id: Optional[str]
    subject_id: str
    model_id: str
    purpose: str
    domain: str
    jurisdictions: tuple[str, ...]
    tools: tuple[str, ...]
    autonomy_level: int
    data_classes: tuple[str, ...]
    workflow_ir_id: str
    inherent_risk: RiskClass
    residual_risk: RiskClass
    workflow_ir_version: Optional[str] = None
    correlation_id: str = ""


@dataclass(frozen=True)
class ControlResultInput:
    control_id: str
    status: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluateRequest:
    control_results: tuple[ControlResultInput, ...] = ()
    conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionRequest:
    principal_id: str
    requested_scope: Scope
    evidence_snapshot_digest: str = ""
    model_digest: str = ""
    #: The evaluator's stamp for the evaluation being bound (R-12b). Optional so an existing
    #: caller is unaffected; when absent the authority records no evaluation instant rather
    #: than substituting its own, because inventing one would be the very conflation this
    #: field exists to end.
    evaluated_at: Optional[datetime] = None
    #: The subject assertion's own upper bound, when the caller bound one. A decision may
    #: not outlive the subject assertion that authorized it, so this caps ``expires_at``
    #: alongside the grant and control-freshness bounds. Optional and defaulting to
    #: ``None`` — an existing caller is unaffected and supplies no cap, and because it can
    #: only ever *shorten* a decision, accepting it from the caller widens nothing.
    #:
    #: The subject window itself stays inclusive at both ends: a ``SubjectContext`` may be
    #: valid at exactly one instant, and that point-in-time contract is ratified. What it
    #: may not do is mint authority reaching past that instant.
    subject_valid_until: Optional[datetime] = None


@dataclass(frozen=True)
class IssueEnvelopeRequest:
    decision_id: str
    audience: str
    session_id: str
    nonce: str
    envelope_scope: Optional[Scope] = None
    human_approval_required_above_minor_units: Optional[int] = None
    required_conditions: tuple[str, ...] = ()
    context_minimization: bool = False


@dataclass(frozen=True)
class AuthorizeActionRequest:
    envelope_id: str
    tenant_id: str
    actor_id: str
    model_id: str
    session_id: str
    action_type: str
    target_id: str
    purpose: str
    data_classes: tuple[str, ...] = ()
    destination: str = ""
    amount_minor_units: Optional[int] = None
    currency: str = ""
    satisfied_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerifyResponse:
    valid: bool
    reasons: tuple[str, ...] = ()
