"""The scoring aggregate for a POST_DEPLOYMENT_VALUE assessment.

Everything needed to compute a reported (post-deployment) governed-value figure
for one agent over one window, on **caller-reported** inputs. The kernel makes no
claim that these are observed, attributed or verified — see the classification on
the result (``POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED``). Field names such
as ``benefit``/``actual_losses`` describe what the caller asserts for the supplied
accounting period, not anything the kernel determined.

Loss is modelled as three *distinct* concepts, never conflated:

- ``benefit.loss_avoided`` — value from losses the agent *prevented* (a benefit).
- ``actual_losses``        — losses the agent *caused* that were actually incurred
                              per the caller (historical, absolute money,
                              subtracted directly).
- ``residual_expected_loss`` — *forward* expected loss (Σ p×magnitude), used only
                              in the explicit risk-adjusted view.

The case is immutable and single-currency: benefit, actual losses, cost,
investment, every expected-loss magnitude and the geography label must agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .attribution import AttributionEvidence
from .cost import CostToServe
from .enums import ConfidenceClass, OutcomeClass
from .errors import CurrencyMismatchError, GovernedValueError
from .expected_loss import ExpectedLoss
from .investment import TotalInvestment
from .modifiers import DomainProfile, GeographyProfile
from .money import Money
from .value import ReportedValue

__all__ = ["AgentValueCase"]


@dataclass(frozen=True)
class AgentValueCase:
    tenant_id: str
    agent_id: str
    domain: DomainProfile
    geography: GeographyProfile
    outcome: OutcomeClass
    benefit: ReportedValue
    actual_losses: Money  # required — explicit zero is a claim, not an omission
    residual_expected_loss: ExpectedLoss
    cost: CostToServe
    investment: TotalInvestment
    attribution: AttributionEvidence
    # A qualitative, CALLER-REPORTED, UNVERIFIED confidence label. It is separate
    # from EvidenceStatus and is never used in any monetary calculation.
    reported_confidence: ConfidenceClass = ConfidenceClass.UNCLASSIFIED
    # A defensible, caller-stated reported net run-rate per period. Only when this
    # is supplied (and positive) is a payback period computed; otherwise payback is
    # None (a proper time basis is GV-5, deferred).
    reported_net_per_period: Optional[Money] = None
    period_label: str = ""

    def __post_init__(self) -> None:
        # RF-3: a required Money field must be exactly that — fail closed with a
        # typed domain error, never an incidental AttributeError downstream.
        if not isinstance(self.actual_losses, Money):
            raise GovernedValueError(
                "actual_losses is required and must be a Money "
                "(explicit Money.zero(currency) states a nil loss); "
                f"got {type(self.actual_losses).__name__}"
            )
        currency = self.benefit.currency
        for label, other in (
            ("actual_losses", self.actual_losses.currency),
            ("cost", self.cost.currency),
            ("investment", self.investment.currency),
            ("residual_expected_loss", self.residual_expected_loss.currency),
            ("geography", self.geography.currency),
        ):
            if other != currency:
                raise CurrencyMismatchError(
                    f"{label} currency {other} != value currency {currency}"
                )
        if self.reported_net_per_period is not None:
            if not isinstance(self.reported_net_per_period, Money):
                raise GovernedValueError(
                    "reported_net_per_period must be a Money or None; "
                    f"got {type(self.reported_net_per_period).__name__}"
                )
            if self.reported_net_per_period.currency != currency:
                raise CurrencyMismatchError(
                    f"reported_net_per_period currency "
                    f"{self.reported_net_per_period.currency} != value currency {currency}"
                )
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")

    @property
    def currency(self) -> str:
        return self.benefit.currency
