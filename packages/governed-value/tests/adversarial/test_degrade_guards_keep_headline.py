"""Degrading guards keep the headline but attach an auditable caveat.

Unlike the fatal guards, these do not suppress the figure — they mark it
DEGRADED so a consumer can see the figure *and* why to trust it less.
"""

from decimal import Decimal

from governed_value.domain.attribution import AttributionContext
from governed_value.domain.cost import CostToServe
from governed_value.domain.enums import Scorability
from governed_value.domain.money import Money
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_realization_assumed_100_percent_is_flagged_not_fatal():
    case = scorable_support_case(
        attribution=AttributionContext(
            baseline_captured=True,
            realization_rate=Decimal("1.0"),
            headcount_or_scope_changed=False,  # 100% with no org change
        )
    )
    result = score_case(case)
    assert result.scorability is Scorability.DEGRADED
    assert result.ngva_per_action is not None  # headline kept
    assert any("notional" in a for a in result.advisories)


def test_incomplete_tco_is_flagged():
    thin = CostToServe(currency="USD", inference=Money(200_00, "USD"))  # only 1 of 7
    result = score_case(scorable_support_case(cost=thin))
    assert result.scorability is Scorability.DEGRADED
    assert any("TCO incomplete" in a for a in result.advisories)


def test_concurrent_changes_without_holdout_is_flagged():
    case = scorable_support_case(
        attribution=AttributionContext(
            baseline_captured=True,
            realization_rate=Decimal("0.9"),
            headcount_or_scope_changed=True,
            concurrent_changes=3,
            holdout_or_staged=False,
        )
    )
    result = score_case(case)
    assert result.scorability is Scorability.DEGRADED
    assert any("concurrent change" in a for a in result.advisories)
    assert result.ngva_per_action is not None
