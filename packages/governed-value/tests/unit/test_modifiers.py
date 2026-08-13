"""GV-1: geography and domain are descriptive context and touch no money.

The prior kernel let geography/domain multipliers (residency, regulatory load,
locale, severity floor) move the result — caller-controlled policy. Those levers
are removed; here we prove the profiles are inert with respect to the monetary
figures.
"""

from governed_value.domain.enums import DomainKind, ValueSource
from governed_value.domain.modifiers import DomainProfile, GeographyProfile
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case


def test_changing_geography_label_does_not_change_money():
    base = score_case(scorable_support_case())
    other = score_case(
        scorable_support_case(geography=GeographyProfile(label="DE", currency="USD"))
    )
    assert other.realized_net_governed_value == base.realized_net_governed_value
    assert other.cost_to_serve == base.cost_to_serve
    assert other.realized_roi == base.realized_roi


def test_changing_domain_profile_does_not_change_money():
    base = score_case(scorable_support_case())
    regulated = DomainProfile(
        kind=DomainKind.REGULATED,
        natural_unit="decision_reviewed",
        dominant_source=ValueSource.LOSS_AVOIDED,
    )
    other = score_case(scorable_support_case(domain=regulated))
    assert other.realized_net_governed_value == base.realized_net_governed_value
    assert other.risk_adjusted_net_governed_value == base.risk_adjusted_net_governed_value


def test_geography_currency_still_enforced_for_consistency():
    import pytest

    from governed_value.domain.errors import CurrencyMismatchError

    with pytest.raises(CurrencyMismatchError):
        scorable_support_case(geography=GeographyProfile(label="DE", currency="EUR"))
