"""The governed-value scorer.

One deterministic pass turns an :class:`AgentValueCase` into a
:class:`GovernedValueResult`. The headline figure is **net governed value per
authorized action (NGVA)**:

    net governed value = value - expected error cost - cost to serve
    NGVA                = net governed value / authorized actions

where ``value`` is gross realized value after realization, attribution, decay
and locale modifiers. The scorer *fails closed*: when the basis for a hard ROI
figure is not defensible it returns ``Scorability.NOT_SCORABLE`` and **suppresses
the headline** (``ngva`` / ``roi`` are ``None``) while still exposing the
component money for transparency. A number without a defensible basis is worse
than no number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from ..domain.case import AgentValueCase
from ..domain.enums import (
    OUTCOME_MEASUREMENT,
    MeasurementMethod,
    OutcomeClass,
    Scorability,
)
from ..domain.money import Money
from ..domain.rates import ONE

__all__ = ["GovernedValueResult", "score_case"]


@dataclass(frozen=True)
class GovernedValueResult:
    agent_id: str
    tenant_id: str
    currency: str
    scorability: Scorability
    measurement_method: MeasurementMethod
    # Component money (window totals) — always populated for transparency.
    gross_value: Money
    effective_value: Money  # after realization x attribution x decay x locale
    expected_error_cost: Money
    cost_to_serve: Money
    net_governed_value: Money
    authorized_actions: int
    # Headline figures — suppressed (None) when NOT_SCORABLE.
    ngva_per_action: Optional[Decimal]
    roi_ratio: Optional[Decimal]
    reasons: tuple[str, ...] = field(default_factory=tuple)  # why suppressed / degraded
    advisories: tuple[str, ...] = field(default_factory=tuple)  # non-fatal notes

    @property
    def is_scorable(self) -> bool:
        return self.scorability is not Scorability.NOT_SCORABLE


def _measurement_method(outcome: OutcomeClass) -> MeasurementMethod:
    return OUTCOME_MEASUREMENT[outcome]


def score_case(case: AgentValueCase) -> GovernedValueResult:
    """Score one agent for one accounting window. Pure and deterministic."""

    currency = case.currency
    attribution = case.attribution
    error = case.error_profile
    geo = case.geography
    domain = case.domain
    method = _measurement_method(case.outcome)

    reasons: list[str] = []
    advisories: list[str] = []

    # -- numerator: gross -> effective (realization x attribution x decay x locale)
    gross = case.realized.gross()
    realization_composite = attribution.realization_composite()
    effective = gross.scaled(realization_composite).scaled(geo.locale_realization_rate)

    # -- wrong-action term (only if priced; otherwise 0 and a fatal reason below)
    if error.is_priced():
        expected_error_cost = error.expected_error_cost(effective)
    else:
        expected_error_cost = Money.zero(currency)

    risk_adjusted = effective - expected_error_cost

    # -- denominator: TCO (+ residency inference multiplier, + regulatory load)
    cost_to_serve = case.cost.total(
        inference_multiplier=geo.residency_inference_multiplier
    )
    if geo.regulatory_load_minor_units:
        cost_to_serve = cost_to_serve + Money(geo.regulatory_load_minor_units, currency)

    net_governed_value = risk_adjusted - cost_to_serve

    # -- fatal guards (fail closed -> suppress headline) ---------------------
    if not attribution.baseline_captured:
        reasons.append(
            "no pre-deployment baseline captured; before/after value is unrecoverable"
        )
    if not error.is_priced():
        reasons.append(
            "wrong-action term unpriced (p_error / severity required); "
            "agents look strongly positive only because this term is missing"
        )
    if case.outcome in (OutcomeClass.JUDGMENT_SUPPORT, OutcomeClass.RISK_CONTAINMENT) and (
        not attribution.holdout_or_staged
    ):
        reasons.append(
            f"outcome '{case.outcome.value}' requires a holdout or staged rollout; "
            "attribution is otherwise unrecoverable"
        )
    if case.outcome is OutcomeClass.DISCOVERY_INSIGHT:
        reasons.append(
            "discovery/insight outcome: hard ROI is not recoverable by design; "
            "measure leading indicators as option value"
        )
    if case.action.authorized_count <= 0:
        reasons.append(
            "no authorized actions at the control-plane chokepoint to normalize over"
        )
    if domain.min_severity is not None and (
        error.severity is None or error.severity < domain.min_severity
    ):
        reasons.append(
            f"high-consequence domain '{domain.kind.value}' requires severity "
            f">= {domain.min_severity}; error asymmetry is under-priced"
        )

    # -- degrading guards (keep headline, attach caveats) --------------------
    if attribution.realization_rate == ONE and not attribution.headcount_or_scope_changed:
        advisories.append(
            "realization assumed at 100% without a headcount/scope change; "
            "freed capacity may be notional, not cash"
        )
    missing = case.cost.missing_components()
    if missing:
        advisories.append("TCO incomplete: " + ", ".join(missing) + " not accounted")
    if attribution.decay_per_period == 0 and attribution.periods_elapsed > 0:
        advisories.append(
            "no value-decay term while periods have elapsed; drift is not modelled"
        )
    if attribution.concurrent_changes > 0 and not attribution.holdout_or_staged:
        advisories.append(
            f"value credited amid {attribution.concurrent_changes} concurrent change(s) "
            "without isolation; attribution may be over-credited"
        )
    if geo.regulatory_load_minor_units:
        advisories.append(
            f"regulatory load ({geo.regulatory_load_minor_units} {currency} minor units) "
            "added to TCO AND raises avoided-loss value; count both, do not net silently"
        )

    # -- verdict -------------------------------------------------------------
    if reasons:
        scorability = Scorability.NOT_SCORABLE
        ngva: Optional[Decimal] = None
        roi: Optional[Decimal] = None
    else:
        scorability = Scorability.DEGRADED if advisories else Scorability.SCORABLE
        ngva = Decimal(net_governed_value.minor_units) / Decimal(
            case.action.authorized_count
        )
        tco_minor = cost_to_serve.minor_units
        roi = (
            (Decimal(risk_adjusted.minor_units) - Decimal(tco_minor)) / Decimal(tco_minor)
            if tco_minor != 0
            else None
        )
        if roi is None:
            advisories.append("TCO is zero; ROI ratio is undefined (NGVA still holds)")

    return GovernedValueResult(
        agent_id=case.agent_id,
        tenant_id=case.action.tenant_id,
        currency=currency,
        scorability=scorability,
        measurement_method=method,
        gross_value=gross,
        effective_value=effective,
        expected_error_cost=expected_error_cost,
        cost_to_serve=cost_to_serve,
        net_governed_value=net_governed_value,
        authorized_actions=case.action.authorized_count,
        ngva_per_action=ngva,
        roi_ratio=roi,
        reasons=tuple(reasons),
        advisories=tuple(advisories),
    )
