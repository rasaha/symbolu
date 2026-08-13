from decimal import Decimal

from governed_value.domain.enums import (
    AssessmentStage,
    AuthorityStatus,
    EvidenceStatus,
    MeasurementMethod,
    Scorability,
)
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_happy_path_numbers_are_exact():
    r = score_case(scorable_support_case())

    assert r.total_benefit.minor_units == 100_000
    assert r.actual_losses.minor_units == 0
    assert r.residual_expected_loss.minor_units == 200  # 20_000 x 0.01
    assert r.cost_to_serve.minor_units == 30_000
    assert r.total_investment.minor_units == 50_000
    assert r.reported_net_governed_value.minor_units == 70_000  # 100_000 - 0 - 30_000
    assert r.risk_adjusted_net_governed_value.minor_units == 69_800  # - 200

    assert r.reported_roi == Decimal("70000") / Decimal("50000")  # 1.4
    assert r.risk_adjusted_roi == Decimal("69800") / Decimal("50000")
    assert r.payback_periods is None  # no run-rate supplied


def test_happy_path_is_scorable_with_no_caveats():
    r = score_case(scorable_support_case())
    assert r.scorability is Scorability.SCORABLE
    assert r.reasons == ()
    assert r.advisories == ()


def test_classification_is_fixed_and_honest():
    r = score_case(scorable_support_case())
    assert r.stage is AssessmentStage.POST_DEPLOYMENT_VALUE
    assert r.evidence_status is EvidenceStatus.REPORTED
    assert r.authority_status is AuthorityStatus.UNVERIFIED
    assert r.measurement_method is MeasurementMethod.BEFORE_AFTER_BASELINE


def test_payback_only_with_defensible_run_rate():
    # Investment 50_000; realized net run-rate 10_000/period -> payback 5 periods.
    from ..scenario import money

    r = score_case(
        scorable_support_case(reported_net_per_period=money(10_000), period_label="month")
    )
    assert r.payback_periods == Decimal("50000") / Decimal("10000")
