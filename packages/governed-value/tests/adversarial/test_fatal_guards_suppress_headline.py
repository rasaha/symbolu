"""Each fatal guard must fail closed: NOT_SCORABLE and headline suppressed.

These encode the documented ways ROI models fail. A model that returns a
flattering number under any of these conditions is exactly the failure mode the
kernel exists to prevent.
"""

from dataclasses import replace
from decimal import Decimal

from governed_value.domain.attribution import AttributionContext
from governed_value.domain.enums import DomainKind, OutcomeClass, Scorability, ValueSource
from governed_value.domain.error_profile import ErrorProfile
from governed_value.domain.modifiers import DomainProfile
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def _assert_suppressed(result, needle: str):
    assert result.scorability is Scorability.NOT_SCORABLE
    assert result.ngva_per_action is None
    assert result.roi_ratio is None
    assert any(needle in r for r in result.reasons), result.reasons


def test_no_baseline_captured():
    case = scorable_support_case(
        attribution=AttributionContext(baseline_captured=False, realization_rate=Decimal("0.9"))
    )
    _assert_suppressed(score_case(case), "baseline")


def test_unpriced_error_term():
    case = scorable_support_case(error_profile=ErrorProfile.unpriced())
    _assert_suppressed(score_case(case), "unpriced")


def test_judgment_support_without_holdout():
    case = scorable_support_case(outcome=OutcomeClass.JUDGMENT_SUPPORT)
    _assert_suppressed(score_case(case), "holdout")


def test_discovery_insight_has_no_hard_roi():
    case = scorable_support_case(outcome=OutcomeClass.DISCOVERY_INSIGHT)
    _assert_suppressed(score_case(case), "option value")


def test_zero_authorized_actions():
    ref = replace(scorable_support_case().action, authorized_count=0)
    case = scorable_support_case(action=ref)
    _assert_suppressed(score_case(case), "no authorized actions")


def test_regulated_domain_severity_floor_inverts_underpriced_error():
    # Regulated domain demands severity >= 0.5; the support-grade 0.20 is too low.
    regulated = DomainProfile(
        kind=DomainKind.REGULATED,
        natural_unit="decision_reviewed",
        dominant_source=ValueSource.LOSS_AVOIDED,
        min_severity=Decimal("0.5"),
    )
    case = scorable_support_case(
        domain=regulated,
        outcome=OutcomeClass.RISK_CONTAINMENT,
        attribution=AttributionContext(
            baseline_captured=True,
            realization_rate=Decimal("0.9"),
            headcount_or_scope_changed=True,
            holdout_or_staged=True,  # isolate the severity-floor guard
        ),
        error_profile=ErrorProfile(p_error=Decimal("0.05"), severity=Decimal("0.20")),
    )
    _assert_suppressed(score_case(case), "under-priced")
