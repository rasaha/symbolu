from decimal import Decimal

from governed_value.domain.enums import MeasurementMethod, Scorability
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_happy_path_numbers_are_exact():
    result = score_case(scorable_support_case())

    # gross 100000; realization 0.90; error 0.05*0.20=0.01
    assert result.gross_value.minor_units == 100_000
    assert result.effective_value.minor_units == 90_000
    assert result.expected_error_cost.minor_units == 900
    assert result.cost_to_serve.minor_units == 30_000
    assert result.net_governed_value.minor_units == 59_100

    # 59_100 / 500 authorized actions
    assert result.ngva_per_action == Decimal("118.2")
    # (89_100 - 30_000) / 30_000
    assert result.roi_ratio == Decimal("59100") / Decimal("30000")


def test_happy_path_is_scorable_with_no_caveats():
    result = score_case(scorable_support_case())
    assert result.scorability is Scorability.SCORABLE
    assert result.reasons == ()
    assert result.advisories == ()


def test_measurement_method_follows_outcome():
    result = score_case(scorable_support_case())
    assert result.measurement_method is MeasurementMethod.BEFORE_AFTER_BASELINE
