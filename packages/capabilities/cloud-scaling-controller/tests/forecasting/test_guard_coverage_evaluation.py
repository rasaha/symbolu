"""Isolating tests for the guard sweep — `forecasting/evaluation.py`.

Written for phase 2 of the shared-engine adoption. Evaluation is the shadow scoreboard:
it decides whether a forecast may be *scored* against a later actual observation, and a
scored record is what an operator would read to judge whether the forecaster is any good.
A validation gate that nothing proves is a gate that could silently stop refusing — a
record could then claim `EVALUATED` while its errors, its interval coverage, or its
subject binding disagree with the canonical state it embeds. The phase-2 sweep measured
26 of this module's guards surviving: deletable with all 646 tests still green.

Each test isolates one gate by building a record valid in every respect except the one
field that gate reads, so exactly one refusal can fire. The typed half asserted is
`EvaluationError` — the contract this module publishes — never a message substring; where
neutralising a gate leaves the record structurally impossible rather than merely
unrefused, the discriminating outcome is a *different* exception type (`AttributeError`,
`TypeError`), which `pytest.raises(EvaluationError)` still separates.

`__post_init__` is a four-arm status dispatch (EVALUATED / SUBJECT_MISMATCH / ABSTAINED /
else). Several tests below therefore probe an arm's *dispatch condition* rather than a
field: the probe is an input the arm rejects but the fall-through arm accepts, so the
condition itself is what fails.
"""

from __future__ import annotations

import dataclasses

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    EvaluationStatus,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    evaluate_forecast,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.evaluation import (
    EvaluationError,
    ForecastEvaluationRecord,
    unscored_record,
)

H1 = ForecastHorizon(60.0)
NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)
BAND_UC = UncertaintyConfig(requested_coverage=0.8, min_calibration_samples=5,
                           match_tolerance_seconds=5.0)
_BAND_VALUES = (0.0, 10.0, 5.0, 20.0, 15.0, 30.0)  # yields the interval [25, 45]
TOL = 5.0


def _evidence(values=(10.0, 20.0, 30.0), *, uncertainty=None, npol=...):
    s = CanonicalCapacitySeries.build(fx.cpu_series_states(list(values), cadence_seconds=60.0))
    if npol is ...:
        npol = fx.cpu_norm_policy()
    return forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, H1, PersistenceForecaster(),
        normalization_policy=npol,
        uncertainty_config=uncertainty or NONE_UC,
    )


def _evaluated(actual_cpu=25.0, *, uncertainty=None):
    """A genuine EVALUATED record, produced by the supported factory."""
    values = _BAND_VALUES if uncertainty is not None else (10.0, 20.0, 30.0)
    ev = _evidence(values, uncertainty=uncertainty)
    actual = fx.cpu_state(ev.forecast.forecast_for, actual_cpu)
    rec = evaluate_forecast(ev, actual, match_tolerance_seconds=TOL)
    assert rec.status is EvaluationStatus.EVALUATED
    return rec


def _unmatched():
    """A genuine UNMATCHED record: no candidate actual, so nothing is embedded."""
    rec = evaluate_forecast(_evidence(), None, match_tolerance_seconds=TOL)
    assert rec.status is EvaluationStatus.UNMATCHED
    return rec


def _subject_mismatch():
    ev = _evidence()
    other = fx.cpu_state(ev.forecast.forecast_for, 25.0, subj=fx.subject("wl-OTHER"))
    rec = evaluate_forecast(ev, other, match_tolerance_seconds=TOL)
    assert rec.status is EvaluationStatus.SUBJECT_MISMATCH
    return rec


def _abstained():
    ev = _evidence(npol=None)  # no normalization policy -> the forecast abstains
    assert ev.forecast.is_abstained
    rec = evaluate_forecast(ev, None, match_tolerance_seconds=TOL)
    assert rec.status is EvaluationStatus.ABSTAINED
    return rec


# ===================================================================================== #
# type gates on the record's own identity fields
# ===================================================================================== #


def test_a_status_that_is_not_an_evaluation_status_is_refused():
    """`EvaluationStatus` is a `str` enum, so the bare string compares equal to the member
    everywhere except the `is` dispatch this module uses. Probed on an UNMATCHED record:
    without the gate the string falls through to the catch-all arm, whose checks it
    passes, and a record ships carrying a status no reader can dispatch on."""

    rec = _unmatched()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, status="unmatched")


def test_a_subject_that_is_not_a_capacity_subject_is_refused():
    """On an UNMATCHED record nothing downstream in `__post_init__` reads the subject, so
    this gate is the only thing standing between a bare workload id and a record that
    claims to be bound to a tenant-scoped subject."""

    rec = _unmatched()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, subject="wl-1")


def test_an_actual_state_that_is_not_a_canonical_state_is_refused():
    """Without the type gate the very next line calls `.digest()` on whatever was handed
    in — an `AttributeError` naming an internal call, not this module's contract."""

    rec = _evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_state="a canonical state, honest")


# ===================================================================================== #
# the actual-state binding
# ===================================================================================== #


def test_an_actual_event_time_that_disagrees_with_the_embedded_state_is_refused():
    """The record would then claim the actual was observed at a time the embedded state
    does not record — the matching evidence and the matched state disagreeing."""

    rec = _evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_event_time=fx.at(9999.0))


def test_a_digest_without_an_embedded_state_is_refused():
    """An UNMATCHED record embeds nothing, so a digest on it points at a state the record
    does not carry: unverifiable by construction."""

    rec = _unmatched()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_state_digest="sha256:" + "0" * 64)


# ===================================================================================== #
# the EVALUATED arm
# ===================================================================================== #


def test_an_evaluated_record_without_an_embedded_state_is_refused():
    """Scored, but against nothing. Without the gate the next line dereferences `None`."""

    rec = _evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_state=None, actual_state_digest=None,
                            actual_event_time=None)


def test_an_evaluated_record_without_a_point_forecast_is_refused():
    """Errors are recomputed from the point forecast; with the gate gone the subtraction
    is `None - actual`, a `TypeError` from arithmetic rather than a refusal."""

    rec = _evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, point_forecast=None)


def test_an_evaluated_record_matched_outside_its_own_tolerance_is_refused():
    """The record states the tolerance it was matched under; a delta beyond it means the
    actual is not the observation the forecast was made for."""

    rec = _evaluated()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, match_delta_seconds=TOL * 100)


def test_a_half_present_interval_is_refused():
    """`interval_upper` is dropped, not `interval_lower`: dropping the lower bound routes
    into the no-bounds arm, which refuses the leftover coverage fields anyway and so
    cannot attribute. Dropping the upper keeps the has-bounds arm, where this gate is the
    only thing preventing a `None < float` comparison."""

    rec = _evaluated(uncertainty=BAND_UC)
    assert rec.interval_lower is not None and rec.interval_upper is not None
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, interval_upper=None)


def test_an_inverted_interval_is_refused():
    """Coverage and width are set consistently with the inverted bounds, so every later
    check in the arm passes and only the ordering gate can fire."""

    rec = _evaluated(actual_cpu=40.0, uncertainty=BAND_UC)
    lower, upper = rec.interval_lower, rec.interval_upper
    inverted_upper = lower - 10.0
    covered = (lower - 1e-9) <= rec.actual_value <= (inverted_upper + 1e-9)
    assert upper is not None
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, interval_upper=inverted_upper, interval_covered=covered,
                            interval_width=inverted_upper - lower)


def test_coverage_reported_without_any_interval_is_refused():
    """A forecast with no uncertainty band cannot have covered anything; without the gate
    the record advertises a coverage figure derived from bounds it never had."""

    rec = _evaluated()
    assert rec.interval_lower is None and rec.interval_covered is None
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, interval_covered=True)


# ===================================================================================== #
# the SUBJECT_MISMATCH arm
# ===================================================================================== #


def test_the_subject_mismatch_arm_is_reached_for_subject_mismatch_records():
    """Probes the arm's dispatch condition, not a field. The record's embedded subject is
    made to *equal* the forecast subject — which the catch-all arm happily accepts. Only
    reaching the SUBJECT_MISMATCH arm rejects it, so neutralising the dispatch admits a
    record labelled `subject_mismatch` whose subjects in fact match."""

    ev = _evidence()
    matching = fx.cpu_state(ev.forecast.forecast_for, 25.0)
    with pytest.raises(EvaluationError):
        unscored_record(ev, status=EvaluationStatus.SUBJECT_MISMATCH,
                        reason="actual_subject_differs", match_tolerance_seconds=TOL,
                        actual_state=matching)


def test_a_subject_mismatch_record_without_an_embedded_state_is_refused():
    """The mismatch claim is only checkable against the state it is claimed about."""

    rec = _subject_mismatch()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_state=None, actual_state_digest=None,
                            actual_event_time=None)


def test_a_subject_mismatch_record_carrying_a_scored_value_is_refused():
    """`SUBJECT_MISMATCH` means *not scored*; an actual value on it is a score smuggled
    across a subject boundary."""

    rec = _subject_mismatch()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_value=25.0)


def test_a_subject_mismatch_record_without_a_reason_is_refused():
    rec = _subject_mismatch()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, reason=None)


# ===================================================================================== #
# the ABSTAINED and catch-all arms
# ===================================================================================== #


def test_an_abstained_record_without_a_reason_is_refused():
    """An abstention with no stated reason is indistinguishable from a lost result."""

    rec = _abstained()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, reason=None)


def test_an_unmatched_record_carrying_a_scored_value_is_refused():
    """The catch-all arm covers UNMATCHED and AMBIGUOUS: neither was scored, so an actual
    value on one is a figure with no matched observation behind it."""

    rec = _unmatched()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, actual_value=25.0)


def test_an_unmatched_record_without_a_reason_is_refused():
    rec = _unmatched()
    with pytest.raises(EvaluationError):
        dataclasses.replace(rec, reason=None)


# ===================================================================================== #
# serialization and the controlled factories
# ===================================================================================== #


def test_the_canonical_dict_carries_the_record_digest_by_default():
    """`include_digest` is a decision point, not a formatting flag: neutralised, every
    default serialization silently loses the content identity a reader would verify
    against, and the dict still looks complete."""

    rec = _evaluated()
    assert rec.to_canonical_dict()["evaluation_digest"] == rec.digest()
    assert "evaluation_digest" not in rec.to_canonical_dict(include_digest=False)


def test_a_record_payload_that_is_not_a_mapping_is_refused():
    with pytest.raises(EvaluationError):
        ForecastEvaluationRecord.from_dict(["schema_version"])


def test_the_unscored_factory_refuses_to_mint_a_scored_status():
    """`unscored_record` exists to build the three not-scored statuses; it refuses the
    other two. `ABSTAINED` is the probe rather than `EVALUATED` because an `EVALUATED`
    record with no embedded actual is rejected one frame deeper anyway, so that probe
    leaves the gate alive. An `ABSTAINED` record with no actual and a reason is perfectly
    well-formed — nothing downstream objects — so without this gate the replay matcher
    could mint an abstention for a forecast that never abstained, and the aggregate
    abstention rate would count it. Measured, not reasoned."""

    ev = _evidence()
    with pytest.raises(EvaluationError):
        unscored_record(ev, status=EvaluationStatus.ABSTAINED, reason="nope",
                        match_tolerance_seconds=TOL)


def test_evidence_that_is_not_forecast_evidence_is_refused():
    with pytest.raises(EvaluationError):
        evaluate_forecast("not evidence", None, match_tolerance_seconds=TOL)


def test_a_match_tolerance_that_is_not_a_real_number_is_refused():
    """`True` is an `int` in Python, so without the type half of this gate it becomes a
    one-second tolerance and every match silently narrows."""

    with pytest.raises(EvaluationError):
        evaluate_forecast(_evidence(), None, match_tolerance_seconds=True)


def test_an_actual_state_missing_the_forecast_target_is_unmatched_not_scored():
    """The state is the right subject at the right time, but carries no CPU measurement.
    Without the gate the next line reads `.unit` off `None`."""

    ev = _evidence()
    no_cpu = fx.replicas_state(ev.forecast.forecast_for, 4)
    rec = evaluate_forecast(ev, no_cpu, match_tolerance_seconds=TOL)
    assert rec.status is EvaluationStatus.UNMATCHED
    assert rec.actual_value is None


def test_abstained_and_the_catch_all_arm_enforce_the_same_two_rules():
    """Evidence for the `equivalent-mutant` exclusion of the ABSTAINED status dispatch.

    The ABSTAINED arm and the catch-all arm below it enforce an identical pair of rules:
    no scored or actual fields, and a reason is required. Neutralise the dispatch and an
    ABSTAINED record falls through to the catch-all, which accepts and rejects exactly
    what the ABSTAINED arm would — the two differ only in the message text, and this
    package's guard doctrine forbids attributing a kill to a message substring.

    Kept in the source because naming ABSTAINED explicitly is what makes the four-way
    dispatch readable as four outcomes rather than three plus a remainder. This test
    measures the jacket: both arms are driven through both rules."""

    abstained, unmatched = _abstained(), _unmatched()
    for rec in (abstained, unmatched):
        with pytest.raises(EvaluationError):
            dataclasses.replace(rec, actual_value=25.0)
        with pytest.raises(EvaluationError):
            dataclasses.replace(rec, reason=None)
