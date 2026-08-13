"""GV-1 core: expected loss is additive absolute money, unbounded vs benefit.

The prior model capped the wrong-action term at a fraction of realized value, so
NGV could never fall below -TCO. These tests prove the corrected model lets a
catastrophic, low-probability loss exceed total benefit and drive net governed
value deeply negative — exactly the case a high-consequence agent must surface.
"""

from decimal import Decimal

from governed_value.domain.expected_loss import ExpectedLoss, ExpectedLossItem
from governed_value.domain.enums import Scorability
from governed_value.services.scorer import score_case

from ..scenario import money, scorable_support_case


def test_expected_loss_may_exceed_total_benefit():
    # Benefit 100_000. A 10% chance of a 50_000_00 (5,000,000 minor) catastrophe
    # => expected loss 500_000 minor units, five times total benefit.
    catastrophic = ExpectedLoss(
        currency="USD",
        items=(
            ExpectedLossItem(
                label="catastrophic_wrongful_action",
                probability=Decimal("0.10"),
                loss_magnitude=money(50_000_00),
            ),
        ),
    )
    r = score_case(scorable_support_case(residual_expected_loss=catastrophic))

    assert r.total_benefit.minor_units == 100_000
    assert r.residual_expected_loss.minor_units == 500_000
    assert r.residual_expected_loss.minor_units > r.total_benefit.minor_units


def test_catastrophic_loss_makes_risk_adjusted_ngv_deeply_negative():
    catastrophic = ExpectedLoss(
        currency="USD",
        items=(
            ExpectedLossItem(
                label="catastrophic_wrongful_action",
                probability=Decimal("0.10"),
                loss_magnitude=money(50_000_00),
            ),
        ),
    )
    r = score_case(scorable_support_case(residual_expected_loss=catastrophic))

    # Realized NGV stays positive (70_000); the risk-adjusted view inverts hard.
    assert r.realized_net_governed_value.minor_units == 70_000
    assert r.risk_adjusted_net_governed_value.minor_units == 70_000 - 500_000
    assert r.risk_adjusted_net_governed_value.minor_units == -430_000
    # Risk-adjusted ROI is sharply negative on the 50_000 investment base.
    assert r.risk_adjusted_roi is not None and r.risk_adjusted_roi < Decimal("-8")
    # Still SCORABLE: the number is defensible, it is just bad. Fail-closed is for
    # missing basis, not for an unfavourable result.
    assert r.scorability is Scorability.SCORABLE


def test_actual_losses_are_separate_from_forward_expected_loss():
    # Historical incurred loss reduces realized NGV directly; forward expected
    # loss only the risk-adjusted view. They must not be conflated.
    r = score_case(
        scorable_support_case(actual_losses=money(40_000))  # historical, incurred
    )
    assert r.realized_net_governed_value.minor_units == 100_000 - 40_000 - 30_000  # 30_000
    # residual expected loss (200) applies only beyond realized NGV.
    assert r.risk_adjusted_net_governed_value.minor_units == 30_000 - 200
