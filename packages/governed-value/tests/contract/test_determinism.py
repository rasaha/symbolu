from decimal import Decimal

from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_scoring_is_deterministic():
    case = scorable_support_case()
    a = score_case(case)
    b = score_case(case)
    assert a == b
    assert a.reported_roi == b.reported_roi


def test_no_binary_float_in_headline():
    r = score_case(scorable_support_case())
    assert isinstance(r.reported_roi, Decimal)
    assert isinstance(r.risk_adjusted_roi, Decimal)
