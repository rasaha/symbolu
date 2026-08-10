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
    expires_at: Optional[datetime] = None
    applicable_rules: tuple[str, ...] = ()
    reason: str = ""

    @property
    def grants_authority(self) -> bool:
        """Only ALLOW / ALLOW_WITH_CONDITIONS may produce an envelope."""

        return self.outcome in (RiskOutcome.ALLOW, RiskOutcome.ALLOW_WITH_CONDITIONS)
