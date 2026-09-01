"""Isolating tests for the guard sweep — the smaller `canonical/` modules.

Written for phase 2 of the shared-engine adoption. One file rather than eight because
each of these modules contributes a handful of gates of the same character: the
fail-closed type and range checks that keep a malformed value from becoming a canonical
one. The larger surfaces have their own files (`test_guard_coverage_state.py`).

Why these matter in one sentence each:

* `identity` — a subject is the tenant/workload scope every later decision is bound to;
  a malformed one silently widens or narrows what a recommendation applies to.
* `measurement` — the single authority on what values a unit admits. Every domain check
  elsewhere in the controller reads it, so a gate that stops refusing here stops
  refusing everywhere.
* `provenance` — where an observation came from and when; evidence, never authority.
* `normalization` — the policy that converts raw units into controller signals. A
  threshold that is zero, negative, or non-finite makes every normalized value meaningless.
* `serialization` — canonical form is what a digest is computed over; two payloads that
  should digest identically must, and two that should not, must not.
* `sources` / `projection` / `evidence` — the boundaries where states enter, become a
  controller observation, and are bound into an advisory-only record.

Each test isolates one gate and asserts the typed half of its refusal, never a message
substring.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum

import pytest

from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState,
    CapacitySubject,
    CapacityState,
    InfrastructureState,
    Measurement,
    NormalizationMethod,
    NormalizationPolicy,
    ObservationProvenance,
    ObservationSourceType,
    Unit,
    project_to_scaling_observation,
    recommend_with_evidence,
)
from ugence_cloud_scaling_controller.canonical.evidence import (
    EvidenceError,
    build_capacity_decision_evidence,
)
from ugence_cloud_scaling_controller.canonical.identity import SubjectError
from ugence_cloud_scaling_controller.canonical.measurement import (
    MeasurementError,
    unit_domain,
)
from ugence_cloud_scaling_controller.canonical.normalization import (
    NormalizationError,
    normalize_signal,
)
from ugence_cloud_scaling_controller.canonical.projection import ProjectionError
from ugence_cloud_scaling_controller.canonical.provenance import ProvenanceError
from ugence_cloud_scaling_controller.canonical.serialization import to_canonical_obj
from ugence_cloud_scaling_controller.canonical.sources import (
    FixtureObservationSource,
    ReplayObservationSource,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _policy(**over):
    fields = dict(
        policy_id="ev",
        method_by_signal={
            "cpu": NormalizationMethod.PERCENT_TO_RATIO,
            "queue_depth": NormalizationMethod.QUEUE_TO_CAPACITY,
        },
        thresholds={"queue_depth": 100.0},
    )
    fields.update(over)
    return NormalizationPolicy(**fields)


def _state(**over):
    fields = dict(
        subject=CapacitySubject(workload_id="checkout", tenant_id="acme"),
        observed_at=T0,
        infrastructure=InfrastructureState(cpu_utilization=Measurement(92.0, Unit.PERCENT)),
        capacity=CapacityState(running_replicas=4),
    )
    fields.update(over)
    return CanonicalCapacityState(**fields)


# ===================================================================================== #
# identity — the scope every decision is bound to
# ===================================================================================== #


def test_an_optional_subject_field_that_is_not_a_string_is_refused():
    """The shared optional-string helper, reached from every optional scope field. A
    non-string tenant id would ride along into the digest and compare unequal to the
    string form of the same tenant — two subjects that are the same scope."""

    with pytest.raises(SubjectError):
        CapacitySubject(workload_id="checkout", tenant_id=7)


def test_a_subject_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(SubjectError):
        CapacitySubject.from_dict(["checkout"])


def test_a_subject_payload_carrying_an_unknown_field_is_refused():
    """An unknown field is a scope dimension this package does not understand; accepting
    it silently would drop it, narrowing the scope without saying so."""

    with pytest.raises(SubjectError):
        CapacitySubject.from_dict({"workload_id": "checkout", "namespace": "prod"})


def test_a_subject_payload_without_a_workload_id_is_refused():
    with pytest.raises(SubjectError):
        CapacitySubject.from_dict({"tenant_id": "acme"})


# ===================================================================================== #
# measurement — the authority every domain check reads
# ===================================================================================== #


def test_asking_for_the_domain_of_something_that_is_not_a_unit_is_refused():
    """Without the gate the next line indexes the domain table with an unhashable or
    absent key — a KeyError naming an internal table rather than this module's contract."""

    with pytest.raises(MeasurementError):
        unit_domain("percent")


def test_a_non_finite_measurement_is_refused():
    """NaN and infinity survive every arithmetic operation downstream and poison a digest;
    this is the only place they can be stopped."""

    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(MeasurementError):
            Measurement(bad, Unit.PERCENT)


def test_a_measurement_whose_unit_is_not_a_unit_is_refused():
    """`Unit` is a `str` enum, so the bare string compares equal to the member in every
    later `in` test — and would pass the bounds checks that follow. Only the type gate
    separates a real unit from a string that happens to spell one."""

    with pytest.raises(MeasurementError):
        Measurement(50.0, "percent")


def test_a_measurement_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(MeasurementError):
        Measurement.from_dict([50.0, "percent"])


def test_a_measurement_payload_carrying_an_unknown_field_is_refused():
    with pytest.raises(MeasurementError):
        Measurement.from_dict({"value": 50.0, "unit": "percent", "precision": 2})


def test_a_measurement_payload_missing_value_or_unit_is_refused():
    with pytest.raises(MeasurementError):
        Measurement.from_dict({"value": 50.0})


# ===================================================================================== #
# provenance — evidence about an observation, never authority over it
# ===================================================================================== #


def _prov(**over):
    fields = dict(source_type=ObservationSourceType.PROMETHEUS, observed_at=T0)
    fields.update(over)
    return ObservationProvenance(**fields)


def test_a_source_type_that_is_not_a_source_type_is_refused():
    with pytest.raises(ProvenanceError):
        _prov(source_type="prometheus")


def test_a_collected_at_that_is_not_a_datetime_is_refused():
    """Probes both halves of the optional-collection-time gate: the `is not None`
    admission and the datetime check it routes into. `collected_at` is deliberately
    distinct from `observed_at`; a string there makes the two indistinguishable."""

    with pytest.raises(ProvenanceError):
        _prov(collected_at="2026-01-01")


def test_an_optional_provenance_label_that_is_not_a_string_is_refused():
    """The shared loop over `source_id` and `provider`. Both are informational, which is
    exactly why nothing downstream would object to a non-string sitting in one."""

    with pytest.raises(ProvenanceError):
        _prov(provider=7)


def test_a_metric_window_that_is_not_a_non_negative_real_number_is_refused():
    """Probes the optional-window admission and its type check together; `True` is an
    `int` and non-negative, so it would otherwise become a one-second window."""

    with pytest.raises(ProvenanceError):
        _prov(metric_window_seconds=True)


def test_a_negative_metric_window_is_refused():
    """A separate gate from the type check above: zero is admissible, negative is not."""

    with pytest.raises(ProvenanceError):
        _prov(metric_window_seconds=-1.0)


# ===================================================================================== #
# normalization — the policy that gives raw units controller meaning
# ===================================================================================== #


def test_a_policy_without_an_identifier_is_refused():
    with pytest.raises(NormalizationError):
        _policy(policy_id="")


def test_a_method_map_that_is_not_a_mapping_is_refused():
    """Without the gate the iteration one line down raises whatever the wrong type
    happens to raise when unpacked."""

    with pytest.raises(NormalizationError):
        _policy(method_by_signal=[("cpu", NormalizationMethod.PERCENT_TO_RATIO)])


def test_a_method_map_keyed_by_something_other_than_a_signal_name_is_refused():
    with pytest.raises(NormalizationError):
        _policy(method_by_signal={"": NormalizationMethod.PERCENT_TO_RATIO})


def test_a_method_that_is_not_a_normalization_method_is_refused():
    """`NormalizationMethod` is a `str` enum: the bare string reaches the dispatch chain
    in `normalize_signal`, matches no member, and falls out of the exhaustive `else`."""

    with pytest.raises(NormalizationError):
        _policy(method_by_signal={"cpu": "percent_to_ratio"})


def test_a_threshold_map_that_is_not_a_mapping_is_refused():
    with pytest.raises(NormalizationError):
        _policy(thresholds=[("queue_depth", 100.0)])


def test_a_threshold_that_is_not_a_real_number_is_refused():
    """Every threshold method divides by this value; `True` would make it a divide-by-one
    and every queue depth would normalize to its own raw magnitude."""

    with pytest.raises(NormalizationError):
        _policy(thresholds={"queue_depth": True})


def test_a_non_finite_threshold_is_refused():
    with pytest.raises(NormalizationError):
        _policy(thresholds={"queue_depth": float("inf")})


def test_a_normalized_value_that_is_not_finite_is_refused():
    """The post-arithmetic finiteness check. Reached with a threshold small enough that a
    finite queue depth divided by it overflows to infinity — every input is individually
    admissible and only the result is not, which is why the check lives after the
    arithmetic rather than before it."""

    tiny = _policy(thresholds={"queue_depth": 5e-324}, clamp=False)
    with pytest.raises(NormalizationError):
        normalize_signal("queue_depth", Measurement(70.0, Unit.COUNT), tiny)


# ===================================================================================== #
# serialization — what a digest is computed over
# ===================================================================================== #


class _PlainEnum(Enum):
    """Deliberately NOT a `str` enum: a `str` enum is caught by the string branch one
    line earlier, so only a plain one reaches the `Enum` branch this test covers."""

    ALPHA = "alpha"


def test_a_plain_enum_canonicalizes_to_its_value():
    """The one decision point here whose evidence is a success rather than a refusal:
    neutralised, the enum falls past every branch and canonicalization fails outright, so
    only asserting the produced value distinguishes the two."""

    assert to_canonical_obj(_PlainEnum.ALPHA) == "alpha"


# ===================================================================================== #
# sources — the read-only observation boundary
# ===================================================================================== #


def test_a_fixture_source_over_something_that_is_not_a_state_is_refused():
    """The source contract is that `observe()` returns a canonical state. Without the
    gate the wrong type is stored and surfaces at the far end of the pipeline instead."""

    with pytest.raises(TypeError):
        FixtureObservationSource({"cpu": 92.0})


def test_a_replay_source_carrying_a_non_state_item_is_refused():
    """The first item is a real state, so the failure is not visible at the head of the
    sequence — the gate materializes and checks the whole sequence up front rather than
    failing partway through a replay."""

    with pytest.raises(TypeError):
        ReplayObservationSource([_state(), {"cpu": 92.0}])


# ===================================================================================== #
# projection and the advisory-only decision record
# ===================================================================================== #


def test_projecting_something_that_is_not_a_state_is_refused():
    with pytest.raises(ProjectionError):
        project_to_scaling_observation({"cpu": 92.0}, _policy())


def test_projecting_under_something_that_is_not_a_policy_is_refused():
    with pytest.raises(ProjectionError):
        project_to_scaling_observation(_state(), {"cpu": "percent_to_ratio"})


@pytest.mark.parametrize(
    "override",
    [
        {"advisory_only": False},
        {"actuation_performed": True},
        {"authority_class": "EXECUTIVE"},
        {"execution_capability": "DIRECT"},
    ],
)
def test_decision_evidence_cannot_claim_an_authority_this_package_does_not_have(override):
    """The machine-readable half of the controller's boundary, one override per gate. A
    record that could carry any of these values is a record claiming this package
    executed something — which it has no code path to do."""

    _rec, ev = recommend_with_evidence(_state(), _policy())
    with pytest.raises(EvidenceError):
        dataclasses.replace(ev, **override)


def test_the_decision_evidence_dict_carries_the_identity_digest_by_default():
    """`include_digest` is a decision point, not a formatting flag: neutralised, the
    default serialization loses the identity a reader verifies against and still looks
    complete."""

    _rec, ev = recommend_with_evidence(_state(), _policy())
    assert ev.to_canonical_dict()["evidence_digest"] == ev.digest()
    assert "evidence_digest" not in ev.to_canonical_dict(include_digest=False)


def test_an_evidence_produced_at_that_is_not_a_datetime_is_refused():
    """A caller-supplied trusted timestamp, excluded from the identity digest — so
    nothing downstream would ever notice a string sitting in that field."""

    state, policy = _state(), _policy()
    projection = project_to_scaling_observation(state, policy)
    from ugence_cloud_scaling_controller.api import CloudScalingController

    controller = CloudScalingController()
    recommendation = controller.recommend(projection.observation)
    with pytest.raises(EvidenceError):
        build_capacity_decision_evidence(
            state, policy, projection, recommendation, controller.config,
            evidence_produced_at="2026-01-01",
        )


def test_every_normalization_method_has_a_dispatch_arm():
    """Evidence for the exhaustive `else` at the end of the method dispatch, which the
    source itself marks unreachable. The policy's own type gate refuses anything that is
    not a `NormalizationMethod`, so the only way to reach the `else` is a member the
    chain forgot — and this test is what would fail the day one is added. It measures the
    jacket: every declared member normalizes, so none falls through.

    Written as a success assertion because a refusal probe cannot reach the arm at all."""

    units = {
        NormalizationMethod.RATIO_PASSTHROUGH: Measurement(0.5, Unit.RATIO),
        NormalizationMethod.PERCENT_TO_RATIO: Measurement(50.0, Unit.PERCENT),
        NormalizationMethod.ERROR_PERCENT_TO_RATIO: Measurement(50.0, Unit.PERCENT),
        NormalizationMethod.LATENCY_MS_TO_THRESHOLD: Measurement(500.0, Unit.MILLISECONDS),
        NormalizationMethod.LATENCY_S_TO_THRESHOLD: Measurement(0.5, Unit.SECONDS),
        NormalizationMethod.QUEUE_TO_CAPACITY: Measurement(50.0, Unit.COUNT),
    }
    assert set(units) == set(NormalizationMethod), "a method was added without a dispatch arm"
    for method, measurement in units.items():
        policy = NormalizationPolicy(
            policy_id="exhaustive", method_by_signal={"s": method},
            thresholds={"s": 1000.0},
        )
        assert normalize_signal("s", measurement, policy).method == method.value
