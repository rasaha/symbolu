from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_scoring_is_deterministic():
    case = scorable_support_case()
    a = score_case(case)
    b = score_case(case)
    # Frozen dataclasses with exact Decimal arithmetic: bit-for-bit identical.
    assert a == b
    assert a.ngva_per_action == b.ngva_per_action


def test_no_binary_float_in_headline():
    # NGVA is a Decimal, not a float — an audited figure must not carry drift.
    from decimal import Decimal

    result = score_case(scorable_support_case())
    assert isinstance(result.ngva_per_action, Decimal)
    assert isinstance(result.roi_ratio, Decimal)
