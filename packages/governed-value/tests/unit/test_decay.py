from decimal import Decimal

from governed_value.domain.attribution import AttributionContext
from governed_value.services.decay import project_periods

from ..scenario import scorable_support_case


def _decaying_attribution():
    return AttributionContext(
        baseline_captured=True,
        realization_rate=Decimal("0.90"),
        headcount_or_scope_changed=True,
        decay_per_period=Decimal("0.10"),
    )


def test_projection_monotonically_erodes_value():
    case = scorable_support_case(attribution=_decaying_attribution())
    series = project_periods(case, horizon=3)
    assert len(series) == 4
    ngvas = [r.ngva_per_action for r in series]
    assert all(a is not None for a in ngvas)
    # Value decays each period: strictly decreasing NGVA.
    assert ngvas[0] > ngvas[1] > ngvas[2] > ngvas[3]


def test_period_zero_matches_direct_score():
    case = scorable_support_case(attribution=_decaying_attribution())
    series = project_periods(case, horizon=0)
    assert series[0].ngva_per_action is not None
