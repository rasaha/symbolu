"""Portfolio normalization must be commensurable and fail closed on bad inputs.

The point of NGVA is that a support agent in Manila and an underwriting agent in
Frankfurt line up on one axis — but only scorable, same-currency agents may
enter the ranking.
"""

from dataclasses import replace
from decimal import Decimal

from governed_value.domain.attribution import AttributionContext
from governed_value.domain.enums import OutcomeClass
from governed_value.domain.error_profile import ErrorProfile
from governed_value.domain.modifiers import GeographyProfile
from governed_value.services.portfolio import normalize_portfolio
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_ranks_scorable_agents_and_excludes_not_scorable():
    good = score_case(scorable_support_case(agent_id="manila"))
    # A not-scorable agent (no baseline) must be excluded, not ranked.
    bad = score_case(
        scorable_support_case(
            agent_id="frankfurt",
            attribution=AttributionContext(baseline_captured=False),
        )
    )
    summary = normalize_portfolio([good, bad], base_currency="USD")
    ranked_ids = [e.agent_id for e in summary.ranked]
    assert ranked_ids == ["manila"]
    assert any(a == "frankfurt" for a, _ in summary.excluded)


def test_mixed_currency_excluded_needs_fx():
    from governed_value.domain.cost import CostToServe
    from governed_value.domain.money import Money
    from governed_value.domain.value import RealizedValue

    usd = score_case(scorable_support_case(agent_id="usd-agent"))
    eur = score_case(
        scorable_support_case(
            agent_id="eur-agent",
            geography=GeographyProfile(label="DE", currency="EUR"),
            realized=RealizedValue(
                labor_displaced=Money(1_000_00, "EUR"),
                throughput_gained=Money(0, "EUR"),
                loss_avoided=Money(0, "EUR"),
            ),
            cost=CostToServe(
                currency="EUR",
                inference=Money(200_00, "EUR"),
                retries=Money(0, "EUR"),
                evals=Money(0, "EUR"),
                monitoring=Money(0, "EUR"),
                human_in_loop_review=Money(0, "EUR"),
                incident_remediation=Money(0, "EUR"),
                model_migration=Money(0, "EUR"),
            ),
        )
    )
    summary = normalize_portfolio([usd, eur], base_currency="USD")
    assert [e.agent_id for e in summary.ranked] == ["usd-agent"]
    assert any("FX" in reason for _, reason in summary.excluded)


def test_ranked_by_ngva_descending():
    high = score_case(scorable_support_case(agent_id="high"))
    low_ref = replace(scorable_support_case().action, authorized_count=100000)
    low = score_case(scorable_support_case(agent_id="low", action=low_ref))
    summary = normalize_portfolio([low, high], base_currency="USD")
    # 'high' has far fewer actions over the same net value -> higher NGVA.
    assert [e.agent_id for e in summary.ranked] == ["high", "low"]
    assert summary.portfolio_ngva is not None
