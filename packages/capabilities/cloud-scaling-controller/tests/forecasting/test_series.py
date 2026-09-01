"""CanonicalCapacitySeries construction-policy and invariant tests."""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    DuplicateTimestampPolicy,
    OrderingPolicy,
    SeriesConstructionPolicy,
    SeriesError,
    SeriesErrorReason,
)


def test_build_orders_and_reports_range():
    states = fx.cpu_series_states([10.0, 20.0, 30.0])
    s = CanonicalCapacitySeries.build(states)
    assert s.observation_count == 3
    assert s.start_event_time == states[0].observed_at
    assert s.end_event_time == states[-1].observed_at
    assert s.tenant_id == "tenant-1"
    assert not s.applied_sort
    assert s.collapsed_duplicate_count == 0


def test_empty_series_rejected():
    with pytest.raises(SeriesError):
        CanonicalCapacitySeries.build([])


def test_cross_subject_contamination_fails_closed():
    a = fx.cpu_state(fx.at(0), 10.0, subj=fx.subject("wl-A"))
    b = fx.cpu_state(fx.at(60), 20.0, subj=fx.subject("wl-B"))
    with pytest.raises(SeriesError) as exc:
        CanonicalCapacitySeries.build([a, b])
    assert exc.value.reason is SeriesErrorReason.CROSS_SUBJECT


def test_cross_tenant_contamination_fails_closed():
    a = fx.cpu_state(fx.at(0), 10.0, subj=fx.subject("wl-A", tenant_id="t1"))
    b = fx.cpu_state(fx.at(60), 20.0, subj=fx.subject("wl-A", tenant_id="t2"))
    with pytest.raises(SeriesError) as exc:
        CanonicalCapacitySeries.build([a, b])
    assert exc.value.reason is SeriesErrorReason.CROSS_TENANT


def test_naive_timestamp_rejected_by_default():
    from datetime import datetime
    naive = datetime(2026, 1, 1, 0, 0, 0)
    s = fx.cpu_state(naive, 10.0)
    with pytest.raises(SeriesError) as exc:
        CanonicalCapacitySeries.build([s])
    assert exc.value.reason is SeriesErrorReason.NAIVE_TIMESTAMP


def test_naive_allowed_when_policy_opts_in():
    from datetime import datetime
    naive = datetime(2026, 1, 1, 0, 0, 0)
    s = fx.cpu_state(naive, 10.0)
    series = CanonicalCapacitySeries.build(
        [s], SeriesConstructionPolicy(require_timezone_aware=False)
    )
    assert series.observation_count == 1


def test_out_of_order_rejected_by_default():
    states = fx.cpu_series_states([10.0, 20.0, 30.0])
    shuffled = [states[2], states[0], states[1]]
    with pytest.raises(SeriesError) as exc:
        CanonicalCapacitySeries.build(shuffled)
    assert exc.value.reason is SeriesErrorReason.INVALID_TIME_ORDER


def test_sort_policy_opt_in_is_disclosed():
    states = fx.cpu_series_states([10.0, 20.0, 30.0])
    shuffled = [states[2], states[0], states[1]]
    series = CanonicalCapacitySeries.build(
        shuffled, SeriesConstructionPolicy(ordering=OrderingPolicy.SORT)
    )
    assert series.applied_sort is True
    assert [s.observed_at for s in series.states] == [st.observed_at for st in states]


def test_duplicate_identical_rejected_by_default():
    s = fx.cpu_state(fx.at(0), 10.0)
    with pytest.raises(SeriesError) as exc:
        CanonicalCapacitySeries.build([s, s])
    assert exc.value.reason is SeriesErrorReason.DUPLICATE_TIMESTAMP


def test_duplicate_identical_collapsed_when_policy_opts_in():
    s = fx.cpu_state(fx.at(0), 10.0)
    s2 = fx.cpu_state(fx.at(0), 10.0)  # identical content, same timestamp
    series = CanonicalCapacitySeries.build(
        [s, s2], SeriesConstructionPolicy(duplicate_timestamp=DuplicateTimestampPolicy.COLLAPSE_IDENTICAL)
    )
    assert series.observation_count == 1
    assert series.collapsed_duplicate_count == 1


def test_conflicting_duplicate_always_rejected_even_with_collapse_policy():
    a = fx.cpu_state(fx.at(0), 10.0)
    b = fx.cpu_state(fx.at(0), 99.0)  # same timestamp, different content
    for pol in (
        SeriesConstructionPolicy(),
        SeriesConstructionPolicy(duplicate_timestamp=DuplicateTimestampPolicy.COLLAPSE_IDENTICAL),
    ):
        with pytest.raises(SeriesError) as exc:
            CanonicalCapacitySeries.build([a, b], pol)
        assert exc.value.reason is SeriesErrorReason.CONFLICTING_DUPLICATE


def test_digest_changes_with_content():
    s1 = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0]))
    s2 = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 21.0]))
    assert s1.digest() != s2.digest()
    # Reproducible for identical inputs.
    s1b = CanonicalCapacitySeries.build(fx.cpu_series_states([10.0, 20.0]))
    assert s1.digest() == s1b.digest()


def test_observations_at_or_before_is_leakage_safe():
    states = fx.cpu_series_states([10.0, 20.0, 30.0, 40.0])
    s = CanonicalCapacitySeries.build(states)
    cutoff = states[1].observed_at
    got = s.observations_at_or_before(cutoff)
    assert len(got) == 2
    assert all(o.observed_at <= cutoff for o in got)


def test_policy_digest_stable():
    p = SeriesConstructionPolicy()
    assert p.digest().startswith("sha256:")
    assert p.digest() == SeriesConstructionPolicy().digest()
