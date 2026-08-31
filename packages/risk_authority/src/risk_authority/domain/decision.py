"""RiskDecision — the binding outcome issued by Decision Authority (spec §11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import RiskClass, RiskOutcome
from .scope import Scope

__all__ = ["RiskDecision"]


@dataclass(frozen=True)
class RiskDecision:
    """A binding decision that authorizes (or refuses) a bounded scope.

    The decision carries the exact policy/evidence bindings it was made against
    so every downstream envelope and action can reconstruct lineage
    (spec §29 policy immutability, AC-12).
    """

    decision_id: str
    tenant_id: str
    case_id: str
    outcome: RiskOutcome
    authority_principal_id: str
    risk_class: RiskClass
    domain: str
    scope: Scope
    conditions: tuple[str, ...] = ()
    workflow_ir_digest: str = ""
    evidence_snapshot_digest: str = ""
    model_digest: str = ""
    issued_at: Optional[datetime] = None
    #: When the *evaluator* stamped the evaluation this decision binds, as distinct from
    #: ``issued_at``, which is when the *authority* bound it. The two are separate facts and
    #: are not required to be equal — an authority may bind an evaluation stamped earlier.
    #:
    #: It lives on the decision, and therefore inside the digest-bound decision snapshot,
    #: because downstream admission depends on it: Phase 5B's occurrence gate refuses a
    #: determination about a moment before the evidence it rests on existed. A timestamp that
    #: affects admission must come from an authenticated artifact, and until R-12b this one
    #: travelled only on ``SubjectRiskDecision``'s outer field, which no digest covered.
    evaluated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    applicable_rules: tuple[str, ...] = ()
    reason: str = ""

    @property
    def grants_authority(self) -> bool:
        """Only ALLOW / ALLOW_WITH_CONDITIONS may produce an envelope."""

        return self.outcome in (RiskOutcome.ALLOW, RiskOutcome.ALLOW_WITH_CONDITIONS)
