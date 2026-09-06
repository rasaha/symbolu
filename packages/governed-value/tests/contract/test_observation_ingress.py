"""GV-2: observations bind, are recorded, and change nothing else.

The seam exists so that when an attesting authority arrives (GV-4) there is
somewhere for its output to land. Until then a bound observation is carried and
never scored: the money, the guards and — above all — the classification are
identical with and without it.
"""

from datetime import datetime, timezone

import pytest
from ugence_governance_contracts.contracts.evidence import (
    AssessmentWindow,
    MetricObservation,
)

from governed_value.api import GovernedValueApplication
from governed_value.domain.enums import AuthorityStatus, EvidenceStatus
from governed_value.domain.observation import ObservationBindingError, ObservedMetric
from governed_value.services.ingress import admit_observations
from governed_value.services.scorer import score_case

from ..scenario import scorable_support_case

UNIT = "contact_deflected_quality_adjusted"
WINDOW = AssessmentWindow(
    start=datetime(2026, 1, 1, tzinfo=timezone.utc),
    end=datetime(2026, 2, 1, tzinfo=timezone.utc),
)


def observation(**overrides) -> MetricObservation:
    base = dict(
        observation_id="obs-1",
        tenant_id="tenant-a",
        subject_id="support-manila-1",
        metric_id="contacts_deflected",
        value="1200",
        governed_unit=UNIT,
        assessment_window=WINDOW,
        evidence_refs=("evidence://ticket-export/2026-01",),
        content_digest="a" * 64,
    )
    base.update(overrides)
    return MetricObservation(**base)


# --------------------------------------------------------------------------- #
# It binds, and it records exactly what it checked.
# --------------------------------------------------------------------------- #
def test_a_matching_observation_is_admitted_and_flattened():
    (bound,) = admit_observations(scorable_support_case(), [observation()])

    assert isinstance(bound, ObservedMetric)
    assert bound.observation_id == "obs-1"
    assert bound.metric_id == "contacts_deflected"
    assert bound.governed_unit == UNIT
    assert bound.window_start == "2026-01-01T00:00:00+00:00"
    assert bound.window_end == "2026-02-01T00:00:00+00:00"
    assert bound.evidence_reference_count == 1
    assert bound.content_digest == "a" * 64


def test_no_observations_is_the_unchanged_default():
    assert admit_observations(scorable_support_case(), []) == ()
    assert GovernedValueApplication().score(scorable_support_case()).observed_metrics == ()


# --------------------------------------------------------------------------- #
# The point of the ruling: carried, never scored.
# --------------------------------------------------------------------------- #
def test_a_bound_observation_does_not_lift_the_classification():
    r = GovernedValueApplication().score(scorable_support_case(), [observation()])

    assert r.observed_metrics != ()
    assert r.evidence_status is EvidenceStatus.REPORTED
    assert r.authority_status is AuthorityStatus.UNVERIFIED
    assert r.evidence_status is not EvidenceStatus.OBSERVED


def test_observations_change_no_money_no_guard_and_no_verdict():
    case = scorable_support_case()
    without = GovernedValueApplication().score(case)
    with_obs = GovernedValueApplication().score(case, [observation()])

    for field in (
        "total_benefit", "reported_avoided_loss", "actual_losses",
        "residual_expected_loss", "cost_to_serve", "total_investment",
        "reported_net_governed_value", "risk_adjusted_net_governed_value",
        "reported_roi", "risk_adjusted_roi", "payback_periods",
        "scorability", "reasons", "advisories", "measurement_method",
    ):
        assert getattr(without, field) == getattr(with_obs, field), field


def test_score_case_carries_the_tuple_through_untouched():
    bound = admit_observations(scorable_support_case(), [observation()])
    assert score_case(scorable_support_case(), observed_metrics=bound).observed_metrics == bound


# --------------------------------------------------------------------------- #
# Fail closed: a mis-bound observation refuses the whole set.
# --------------------------------------------------------------------------- #
def test_a_foreign_tenant_refuses():
    with pytest.raises(ObservationBindingError, match="tenant"):
        admit_observations(scorable_support_case(), [observation(tenant_id="tenant-b")])


def test_a_different_governed_unit_refuses():
    with pytest.raises(ObservationBindingError, match="natural unit"):
        admit_observations(scorable_support_case(), [observation(governed_unit="tickets")])


def test_the_same_observation_twice_refuses():
    with pytest.raises(ObservationBindingError, match="twice"):
        admit_observations(scorable_support_case(), [observation(), observation()])


def test_something_that_is_not_a_metric_observation_refuses():
    with pytest.raises(ObservationBindingError, match="MetricObservation"):
        admit_observations(scorable_support_case(), [{"observation_id": "obs-1"}])


def test_a_subclass_of_the_contract_refuses():
    """Exact type: a subclass can weaken the contract's own __post_init__."""

    class Looser(MetricObservation):
        def __post_init__(self) -> None:  # pragma: no cover - never valid input
            pass

    with pytest.raises(ObservationBindingError, match="MetricObservation"):
        admit_observations(scorable_support_case(), [Looser.__new__(Looser)])


def test_one_bad_observation_refuses_the_whole_set_and_produces_no_result():
    with pytest.raises(ObservationBindingError):
        GovernedValueApplication().score(
            scorable_support_case(), [observation(), observation(observation_id="obs-2", tenant_id="tenant-b")]
        )
