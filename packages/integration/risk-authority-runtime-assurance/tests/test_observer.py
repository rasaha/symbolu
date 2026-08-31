"""Observer / trajectory-window tests (spec §11, §13, §24; matrix 8, 9).

Dedupe by event_id, re-sequence by (sequence_number, observed_at, event_id),
bounded window, and derived cumulative reads (facts the runtime owns; RA-7 only
risk-types them).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ugence_risk_authority_runtime_assurance import RuntimeAssuranceObserver

from ra7_scenario import FIXED_NOW, TENANT, WORKFLOW, make_observation


def test_record_new_then_duplicate_is_idempotent():
    obs = RuntimeAssuranceObserver()
    assert obs.record(make_observation(1)) is True
    assert obs.record(make_observation(1)) is False  # same event_id
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert len(traj.observations) == 1


def test_out_of_order_events_are_resequenced():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(3))
    obs.record(make_observation(1))
    obs.record(make_observation(2))
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert [o.sequence_number for o in traj.observations] == [1, 2, 3]


def test_bounded_window_marks_truncated():
    obs = RuntimeAssuranceObserver(window_size=3)
    for i in range(1, 6):
        obs.record(make_observation(i))
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert len(traj.observations) == 3
    assert [o.sequence_number for o in traj.observations] == [3, 4, 5]
    assert traj.truncated is True


def test_unseen_trajectory_returns_none():
    obs = RuntimeAssuranceObserver()
    assert obs.trajectory("nope", "nope") is None


def test_cumulative_exposure_sums_per_dimension():
    obs = RuntimeAssuranceObserver()
    for i in range(1, 4):
        obs.record(make_observation(i, detail={"exposure": {"model_cost": 1000.0, "tokens": 5.0}}))
    traj = obs.trajectory(TENANT, WORKFLOW)
    totals = traj.cumulative_exposure()
    assert totals["model_cost"] == 3000.0
    assert totals["tokens"] == 15.0


def test_cumulative_exposure_skips_malformed_amounts():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(1, detail={"exposure": {"model_cost": 1000.0}}))
    obs.record(make_observation(2, detail={"exposure": {"model_cost": "lots"}}))  # bad
    obs.record(make_observation(3, detail={"exposure": {"model_cost": float("inf")}}))  # bad
    obs.record(make_observation(4, detail={"exposure": {"model_cost": -5.0}}))  # bad
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert traj.cumulative_exposure()["model_cost"] == 1000.0


def test_attempts_by_action_counts_recurrence():
    obs = RuntimeAssuranceObserver()
    for i in range(1, 5):
        obs.record(make_observation(i, action_id="stuck-action"))
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert traj.attempts_by_action()["stuck-action"] == 4


def test_data_class_sequence_preserves_order():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(1, detail={"data_class": "public"}))
    obs.record(make_observation(2, detail={"data_class": "restricted"}))
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert traj.data_class_sequence() == ("public", "restricted")


def test_latest_detail_returns_most_recent():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(1, detail={"context_size": 10.0}))
    obs.record(make_observation(2, detail={"context_size": 99.0}))
    traj = obs.trajectory(TENANT, WORKFLOW)
    assert traj.latest_detail("context_size") == 99.0


def test_forget_drops_trajectory():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(1))
    obs.forget(TENANT, WORKFLOW)
    assert obs.trajectory(TENANT, WORKFLOW) is None


def test_distinct_tenants_isolated():
    obs = RuntimeAssuranceObserver()
    obs.record(make_observation(1, tenant_id="A", workflow_instance_id="w"))
    obs.record(make_observation(1, tenant_id="B", workflow_instance_id="w"))
    ta = obs.trajectory("A", "w")
    tb = obs.trajectory("B", "w")
    assert len(ta.observations) == 1 and len(tb.observations) == 1
    assert ta.tenant_id == "A" and tb.tenant_id == "B"
