"""Governance events — auditability from day one, not bolted on later.

Every scoring produces a :class:`GovernedValueEvent` so that a downstream audit
store, metrics sink, or GRC export can reconstruct *why* an agent's ROI figure
was reported (or suppressed) without the scorer knowing its consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .enums import MeasurementMethod, Scorability

__all__ = ["GovernedValueEvent"]


@dataclass(frozen=True)
class GovernedValueEvent:
    event_type: str
    tenant_id: str
    agent_id: str
    scorability: Scorability
    measurement_method: MeasurementMethod
    net_governed_value_minor_units: int
    authorized_actions: int
    ngva_per_action: Optional[Decimal]
    reasons: tuple[str, ...] = field(default_factory=tuple)
    advisories: tuple[str, ...] = field(default_factory=tuple)
