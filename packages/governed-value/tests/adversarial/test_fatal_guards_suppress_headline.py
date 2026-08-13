"""Fatal guards fail closed: NOT_SCORABLE and headline (ROI/payback) suppressed.

Component money stays exposed for transparency; only the headline ratios and
payback are nulled. The classification remains honestly POST_DEPLOYMENT_VALUE /
REPORTED / UNVERIFIED.
"""

from governed_value.domain.attribution import AttributionEvidence
from governed_value.domain.enums import OutcomeClass, Scorability
from governed_value.services.scorer import score_case

from ..scenario import money, scorable_support_case


def _assert_suppressed(result, needle: str):
    assert result.scorability is Scorability.NOT_SCORABLE
    assert result.reported_roi is None
    assert result.risk_adjusted_roi is None
    assert result.payback_periods is None
    assert any(needle in r for r in result.reasons), result.reasons
    # Component money is still present.
    assert result.total_benefit.minor_units == 100_000


def test_no_baseline_captured():
    r = score_case(
        scorable_support_case(attribution=AttributionEvidence(baseline_captured=False))
    )
    _assert_suppressed(r, "baseline")


def test_judgment_support_without_holdout():
    r = score_case(scorable_support_case(outcome=OutcomeClass.JUDGMENT_SUPPORT))
    _assert_suppressed(r, "holdout")


def test_risk_containment_without_holdout():
    r = score_case(scorable_support_case(outcome=OutcomeClass.RISK_CONTAINMENT))
    _assert_suppressed(r, "holdout")


def test_discovery_insight_has_no_hard_roi():
    r = score_case(scorable_support_case(outcome=OutcomeClass.DISCOVERY_INSIGHT))
    _assert_suppressed(r, "option value")


def test_headline_suppressed_even_with_supplied_run_rate():
    # A run-rate cannot manufacture a payback when the basis is not scorable.
    r = score_case(
        scorable_support_case(
            attribution=AttributionEvidence(baseline_captured=False),
            reported_net_per_period=money(10_000),
        )
    )
    assert r.payback_periods is None
