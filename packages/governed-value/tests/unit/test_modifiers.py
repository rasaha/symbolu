from decimal import Decimal

from governed_value.domain.modifiers import GeographyProfile
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_residency_multiplier_scales_inference_line_only():
    base = score_case(scorable_support_case())
    # Double inference cost via data-residency multiplier; inference line is 20_000.
    geo = GeographyProfile(
        label="EU",
        currency="USD",
        residency_inference_multiplier=Decimal("2.0"),
    )
    hosted = score_case(scorable_support_case(geography=geo))
    assert hosted.cost_to_serve.minor_units == base.cost_to_serve.minor_units + 20_000


def test_regulatory_load_adds_to_tco_and_emits_dual_count_advisory():
    geo = GeographyProfile(
        label="EU",
        currency="USD",
        regulatory_load_minor_units=7_000,
    )
    result = score_case(scorable_support_case(geography=geo))
    assert result.cost_to_serve.minor_units == 37_000
    assert any("count both, do not net" in a for a in result.advisories)


def test_locale_realization_scales_numerator_not_denominator():
    base = score_case(scorable_support_case())
    geo = GeographyProfile(
        label="XX",
        currency="USD",
        locale_realization_rate=Decimal("0.5"),
    )
    degraded = score_case(scorable_support_case(geography=geo))
    # Effective value halves; cost-to-serve is untouched.
    assert degraded.effective_value.minor_units == base.effective_value.minor_units // 2
    assert degraded.cost_to_serve.minor_units == base.cost_to_serve.minor_units
