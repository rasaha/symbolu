"""The reported governed-value scorer (POST_DEPLOYMENT_VALUE stage).

One deterministic pass over caller-**reported** inputs. Two net figures are
produced, never conflated:

    ReportedNGV     = total benefit − actual losses − cost to serve
    RiskAdjustedNGV = ReportedNGV − residual expected loss      (Σ p × magnitude)

    ReportedROI     = ReportedNGV / Total Investment
    RiskAdjustedROI = RiskAdjustedNGV / Total Investment

"Reported" names carry a deliberate meaning: the benefit/loss figures are caller
assertions about the supplied accounting period, **not** determinations by this
kernel. Invariants:

* **No realization discount** is applied to already-reported benefit (GV-1).
* **Expected loss is additive absolute money** and may exceed total benefit,
  driving RiskAdjustedNGV deeply negative.
* **Total Investment is the ROI denominator**, distinct from cost-to-serve.
* The result is **always** classified ``POST_DEPLOYMENT_VALUE / REPORTED /
  UNVERIFIED`` — this kernel has no evidence, attribution or authority binding,
  so it can never claim OBSERVED / ATTRIBUTED / VERIFIED, whatever the caller
  named an input.
* **Fail closed**: without a defensible basis the headline ROI / payback is
  suppressed (``None``) while component money stays exposed for transparency.
* ``reported_confidence`` is carried, never entered into the arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from ..domain.case import AgentValueCase
from ..domain.enums import (
    OUTCOME_MEASUREMENT,
    AssessmentStage,
    AuthorityStatus,
    ConfidenceClass,
    EvidenceStatus,
    MeasurementMethod,
    OutcomeClass,
    Scorability,
)
from ..domain.money import Money

__all__ = ["GovernedValueResult", "score_case"]

# This kernel's fixed, honest classification. Raising above these requires the
# evidence (GV-2), attribution (GV-3) and authority (GV-4) layers, which do not
# exist yet.
_STAGE = AssessmentStage.POST_DEPLOYMENT_VALUE
_EVIDENCE = EvidenceStatus.REPORTED
_AUTHORITY = AuthorityStatus.UNVERIFIED


@dataclass(frozen=True)
class GovernedValueResult:
    """A reported governed-value result.

    All money figures are computed from caller-reported inputs. ``reported_*``
    names mean "as asserted by the caller for the accounting period", never
    "observed / attributed / verified by this kernel" — see ``evidence_status``
    (always ``REPORTED``) and ``authority_status`` (always ``UNVERIFIED``).
    ``reported_confidence`` is a caller-supplied, unverified label, separate from
    ``evidence_status`` and never used in the arithmetic.
    """

    tenant_id: str
    agent_id: str
    currency: str
    # -- classification (four orthogonal axes) -------------------------------
    stage: AssessmentStage
    evidence_status: EvidenceStatus
    authority_status: AuthorityStatus
    scorability: Scorability
    reported_confidence: ConfidenceClass
    measurement_method: MeasurementMethod
    # -- component money (window totals) — always populated ------------------
    total_benefit: Money
    reported_avoided_loss: Money
    actual_losses: Money
    residual_expected_loss: Money
    cost_to_serve: Money
    total_investment: Money
    reported_net_governed_value: Money
    risk_adjusted_net_governed_value: Money
    # -- headline ratios — suppressed (None) when NOT_SCORABLE ---------------
    reported_roi: Optional[Decimal]
    risk_adjusted_roi: Optional[Decimal]
    payback_periods: Optional[Decimal]
    reasons: tuple[str, ...] = field(default_factory=tuple)
    advisories: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_scorable(self) -> bool:
        return self.scorability is not Scorability.NOT_SCORABLE


def _measurement_method(outcome: OutcomeClass) -> MeasurementMethod:
    return OUTCOME_MEASUREMENT[outcome]


def score_case(case: AgentValueCase) -> GovernedValueResult:
    """Score one agent for one reported window. Pure and deterministic."""

    currency = case.currency
    attribution = case.attribution
    method = _measurement_method(case.outcome)

    reasons: list[str] = []
    advisories: list[str] = []

    # -- money (absolute, no realization discount) ---------------------------
    total_benefit = case.benefit.gross()
    reported_avoided_loss = case.benefit.reported_avoided_loss()
    actual_losses = case.actual_losses
    residual_expected_loss = case.residual_expected_loss.total()
    cost_to_serve = case.cost.total()
    total_investment = case.investment.total()

    reported_ngv = total_benefit - actual_losses - cost_to_serve
    risk_adjusted_ngv = reported_ngv - residual_expected_loss

    # -- fatal guards (fail closed -> suppress headline) ---------------------
    if not attribution.baseline_captured:
        reasons.append(
            "no pre-deployment baseline captured; before/after value is unrecoverable"
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

    # -- degrading guards (keep headline, attach caveats) --------------------
    missing_cost = case.cost.missing_components()
    if missing_cost:
        advisories.append(
            "cost-to-serve incomplete: " + ", ".join(missing_cost) + " not accounted"
        )
    missing_inv = case.investment.missing_components()
    if missing_inv:
        advisories.append(
            "investment incomplete: " + ", ".join(missing_inv) + " not accounted"
        )
    if case.residual_expected_loss.is_empty():
        advisories.append(
            "no residual/forward expected loss modelled; risk-adjusted view equals "
            "the reported view — forward risk is unpriced"
        )
    if attribution.concurrent_changes > 0 and not attribution.holdout_or_staged:
        advisories.append(
            f"value credited amid {attribution.concurrent_changes} concurrent change(s) "
            "without isolation; attribution may be over-credited"
        )

    # -- verdict + headline --------------------------------------------------
    if reasons:
        scorability = Scorability.NOT_SCORABLE
        reported_roi: Optional[Decimal] = None
        risk_adjusted_roi: Optional[Decimal] = None
        payback: Optional[Decimal] = None
    else:
        inv_minor = total_investment.minor_units
        if inv_minor != 0:
            reported_roi = Decimal(reported_ngv.minor_units) / Decimal(inv_minor)
            risk_adjusted_roi = Decimal(risk_adjusted_ngv.minor_units) / Decimal(inv_minor)
        else:
            reported_roi = None
            risk_adjusted_roi = None
            advisories.append("no investment basis; ROI ratio is undefined")

        # Payback only with a defensible, caller-stated per-period run-rate.
        payback = None
        run_rate = case.reported_net_per_period
        if run_rate is not None and run_rate.minor_units > 0:
            payback = Decimal(inv_minor) / Decimal(run_rate.minor_units)
        elif run_rate is not None:
            advisories.append(
                "reported_net_per_period is non-positive; payback never occurs (None)"
            )

        scorability = Scorability.DEGRADED if advisories else Scorability.SCORABLE

    return GovernedValueResult(
        tenant_id=case.tenant_id,
        agent_id=case.agent_id,
        currency=currency,
        stage=_STAGE,
        evidence_status=_EVIDENCE,
        authority_status=_AUTHORITY,
        scorability=scorability,
        reported_confidence=case.reported_confidence,
        measurement_method=method,
        total_benefit=total_benefit,
        reported_avoided_loss=reported_avoided_loss,
        actual_losses=actual_losses,
        residual_expected_loss=residual_expected_loss,
        cost_to_serve=cost_to_serve,
        total_investment=total_investment,
        reported_net_governed_value=reported_ngv,
        risk_adjusted_net_governed_value=risk_adjusted_ngv,
        reported_roi=reported_roi,
        risk_adjusted_roi=risk_adjusted_roi,
        payback_periods=payback,
        reasons=tuple(reasons),
        advisories=tuple(advisories),
    )
