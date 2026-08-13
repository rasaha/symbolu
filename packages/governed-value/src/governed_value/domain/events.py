"""Governance events — auditability from day one, not bolted on later.

Every scoring produces a :class:`GovernedValueEvent` carrying the full
classification (stage / evidence / authority / scorability) so a downstream
audit store or GRC export can reconstruct *what class of figure* was reported
(or suppressed) and why, without the scorer knowing its consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .enums import (
    AssessmentStage,
    AuthorityStatus,
    EvidenceStatus,
    MeasurementMethod,
    Scorability,
)

__all__ = ["GovernedValueEvent"]


@dataclass(frozen=True)
class GovernedValueEvent:
    event_type: str
    tenant_id: str
    agent_id: str
    stage: AssessmentStage
    evidence_status: EvidenceStatus
    authority_status: AuthorityStatus
    scorability: Scorability
    measurement_method: MeasurementMethod
    realized_net_governed_value_minor_units: int
    risk_adjusted_net_governed_value_minor_units: int
    realized_roi: Optional[Decimal]
    reasons: tuple[str, ...] = field(default_factory=tuple)
    advisories: tuple[str, ...] = field(default_factory=tuple)
