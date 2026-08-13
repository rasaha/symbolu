"""GV-1: already-realized benefit must not be realization-discounted again.

The realized kernel takes benefit that is already realized and already
attributable and passes it through with no realization / attribution / decay /
locale multiplier. Feeding a benefit of X (with zero losses and zero cost) must
yield exactly X in realized NGV.
"""

from governed_value.domain.value import RealizedValue
from governed_value.services.scorer import score_case

from ..scenario import money, scorable_support_case


def test_benefit_passes_through_undiscounted():
    r = score_case(scorable_support_case())
    # total_benefit equals the raw sum of the three sources — no hidden factor.
    assert r.total_benefit.minor_units == 100_000


def test_zero_cost_zero_loss_yields_benefit_exactly():
    from governed_value.domain.cost import CostToServe
    from governed_value.domain.investment import TotalInvestment

    zero_cost = CostToServe(
        currency="USD",
        inference=money(0),
        retries=money(0),
        evals=money(0),
        monitoring=money(0),
        human_in_loop_review=money(0),
        incident_remediation=money(0),
        model_migration=money(0),
    )
    inv = TotalInvestment(currency="USD", one_time_build=money(10_000))
    from governed_value.domain.expected_loss import ExpectedLoss

    r = score_case(
        scorable_support_case(
            benefit=RealizedValue(money(777_00), money(0), money(0)),
            actual_losses=money(0),
            residual_expected_loss=ExpectedLoss.none("USD"),
            cost=zero_cost,
            investment=inv,
        )
    )
    assert r.total_benefit.minor_units == 77_700
    assert r.realized_net_governed_value.minor_units == 77_700  # undiscounted
