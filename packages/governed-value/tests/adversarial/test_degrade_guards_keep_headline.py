"""Degrading guards keep the headline but attach an auditable caveat."""

from governed_value.domain.attribution import AttributionEvidence
from governed_value.domain.cost import CostToServe
from governed_value.domain.enums import Scorability
from governed_value.domain.expected_loss import ExpectedLoss
from governed_value.domain.investment import TotalInvestment
from governed_value.services.scorer import score_case

from ..scenario import money, scorable_support_case


def test_incomplete_cost_is_flagged():
    thin = CostToServe(currency="USD", inference=money(200_00))  # 1 of 7 accounted
    r = score_case(scorable_support_case(cost=thin))
    assert r.scorability is Scorability.DEGRADED
    assert r.realized_roi is not None  # headline kept
    assert any("cost-to-serve incomplete" in a for a in r.advisories)


def test_incomplete_investment_is_flagged():
    thin_inv = TotalInvestment(currency="USD", one_time_build=money(300_00))  # 1 of 4
    r = score_case(scorable_support_case(investment=thin_inv))
    assert r.scorability is Scorability.DEGRADED
    assert any("investment incomplete" in a for a in r.advisories)


def test_empty_residual_expected_loss_is_flagged():
    r = score_case(scorable_support_case(residual_expected_loss=ExpectedLoss.none("USD")))
    assert r.scorability is Scorability.DEGRADED
    assert any("forward risk is unpriced" in a for a in r.advisories)
    # With no forward loss, the risk-adjusted view equals the realized view.
    assert (
        r.risk_adjusted_net_governed_value.minor_units
        == r.realized_net_governed_value.minor_units
    )


def test_concurrent_changes_without_holdout_is_flagged():
    r = score_case(
        scorable_support_case(
            attribution=AttributionEvidence(
                baseline_captured=True, concurrent_changes=3, holdout_or_staged=False
            )
        )
    )
    assert r.scorability is Scorability.DEGRADED
    assert any("concurrent change" in a for a in r.advisories)
    assert r.realized_roi is not None
