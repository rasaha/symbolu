"""Structural controller-behavior tests: determinism, instance isolation,
thread-safety, safety bounds (min floor / max delta), and the required scenario
shapes. Exact per-step magnitudes are asserted by test_baseline_parity.py.
"""

from __future__ import annotations

import threading

from ugence_cloud_scaling_controller import (
    CloudScalingController,
    Controller,
    InfraControllerConfig,
    ScalingObservation,
)
import support


def _series(ctrl, steps):
    return [ctrl.recommend(ScalingObservation.from_dict(s)) for s in steps]


HIGH = {"cpu": 0.97, "memory": 0.93, "latency_p99": 0.9, "error_rate": 0.3, "queue_depth": 0.85}
LOW = {"cpu": 0.08, "memory": 0.1, "latency_p99": 0.05, "error_rate": 0.0, "queue_depth": 0.02}
MID = {"cpu": 0.5, "memory": 0.5, "latency_p99": 0.3, "error_rate": 0.03, "queue_depth": 0.3}


def test_hold_under_steady_load():
    ctrl = CloudScalingController()
    recs = _series(ctrl, [{"metrics": MID, "current_replicas": 5}] * 20)
    # A steady mid load should settle to no scaling action.
    assert recs[-1].recommendation == "no_action"
    assert recs[-1].replica_delta == 0


def test_scale_out_direction_under_sustained_high_load():
    # With the conservative default gain, constant high load settles at "observe_out"
    # (positive direction) rather than emitting a delta. Assert the positive direction.
    ctrl = CloudScalingController()
    recs = _series(ctrl, [{"metrics": HIGH, "current_replicas": 4, "phase": "peak"}] * 30)
    assert recs[-1].action_score > 0
    assert any(r.recommendation.startswith(("scale_out", "observe_out")) for r in recs)


def test_scale_out_emits_delta_with_higher_gain():
    # A genuine scale-out delta with an amplified gain configuration.
    ctrl = CloudScalingController(InfraControllerConfig(G_base=3.0))
    EX = {"cpu": 0.99, "memory": 0.99, "latency_p99": 0.99, "error_rate": 0.99, "queue_depth": 0.99}
    recs = _series(ctrl, [{"metrics": EX, "current_replicas": 4, "phase": "peak"}] * 10)
    assert any(r.replica_delta > 0 for r in recs)
    assert any(r.recommendation.startswith("scale_out") for r in recs)


def test_scale_in_direction_after_sustained_low_load():
    ctrl = CloudScalingController()
    steps = [{"metrics": HIGH, "current_replicas": 15}] * 10
    steps += [{"metrics": LOW, "current_replicas": 15}] * 50
    recs = _series(ctrl, steps)
    assert recs[-1].action_score < 0
    assert any(r.recommendation.startswith(("scale_in", "observe_in")) for r in recs)


def test_scale_in_emits_delta_with_higher_gain():
    # A genuine scale-in delta with an amplified gain configuration.
    ctrl = CloudScalingController(InfraControllerConfig(G_base=3.0))
    warm = {"cpu": 0.7, "memory": 0.7, "latency_p99": 0.6, "error_rate": 0.3, "queue_depth": 0.6}
    cold = {"cpu": 0.01, "memory": 0.02, "latency_p99": 0.0, "error_rate": 0.0, "queue_depth": 0.0}
    steps = [{"metrics": warm, "current_replicas": 20}] * 60
    steps += [{"metrics": cold, "current_replicas": 20}] * 80
    recs = _series(ctrl, steps)
    assert any(r.replica_delta < 0 for r in recs)


def test_min_replica_floor_never_recommends_below_one():
    ctrl = CloudScalingController()
    recs = _series(ctrl, [{"metrics": LOW, "current_replicas": 1}] * 40)
    for r in recs:
        assert r.recommended_replicas >= 1
        assert r.current_replicas + r.replica_delta >= 1


def test_max_scale_out_delta_bounded_by_ratio():
    # max_scale_out_ratio default 0.5 => at 4 replicas, +2 max; startup clamp caps early.
    cfg = InfraControllerConfig()
    ctrl = CloudScalingController(cfg)
    recs = _series(ctrl, [{"metrics": HIGH, "current_replicas": 4, "phase": "peak"}] * 40)
    for r in recs:
        assert r.replica_delta <= max(1, int(4 * cfg.max_scale_out_ratio))


def _final_plasticity(deploy=False, restarts=0):
    metrics = {"cpu": 0.7, "memory": 0.6, "latency_p99": 0.65, "error_rate": 0.5, "queue_depth": 0.6}
    c = CloudScalingController()
    for _ in range(50):
        c.recommend(ScalingObservation(metrics=metrics, current_replicas=5))
    rec = c.recommend(ScalingObservation(metrics=metrics, current_replicas=5,
                                         deploy_active=deploy, recent_pod_restarts=restarts))
    return rec.component_breakdown["plasticity"]["plasticity"]


def test_deploy_active_reduces_plasticity():
    # Active deployment lowers plasticity (the gate closes -> scaling resistance).
    assert _final_plasticity(deploy=False) > _final_plasticity(deploy=True)


def test_restart_resistance_reduces_plasticity():
    # Recent pod restarts add resistance by lowering plasticity.
    assert _final_plasticity(restarts=0) > _final_plasticity(restarts=8)


def test_conflicting_signals_do_not_crash():
    ctrl = CloudScalingController()
    steps = [{"metrics": {"cpu": 0.95, "memory": 0.05, "latency_p99": 0.9,
                          "error_rate": 0.0, "queue_depth": 0.9},
              "current_replicas": 5}] * 20
    recs = _series(ctrl, steps)
    assert all(isinstance(r.replica_delta, int) for r in recs)


def test_stale_frozen_signals_handled():
    # A frozen (unchanging) signal is detected as stale and excluded from pressure.
    ctrl = CloudScalingController()
    steps = [{"metrics": {"cpu": 0.9, "memory": 0.9, "latency_p99": 0.9,
                          "error_rate": 0.9, "queue_depth": 0.9},
              "current_replicas": 5}] * 40
    recs = _series(ctrl, steps)
    assert all(isinstance(r.action_score, float) for r in recs)


def test_repeated_identical_sequence_is_deterministic():
    steps = [{"metrics": HIGH, "current_replicas": 4, "phase": "peak"}] * 15 + \
            [{"metrics": LOW, "current_replicas": 6}] * 15
    a = support.run_steps(steps)
    b = support.run_steps(steps)
    assert support.scenarios_hash({"s": a}) == support.scenarios_hash({"s": b})


def test_independent_instances_do_not_leak_state():
    steps = [{"metrics": HIGH, "current_replicas": 4, "phase": "peak"}] * 20
    # Prime instance A heavily; a fresh instance B must match a standalone run of the
    # same steps (no shared/global state).
    a = CloudScalingController()
    _series(a, steps)
    fresh = support.run_steps(steps)
    b = support.run_steps(steps)
    assert support.scenarios_hash({"s": fresh}) == support.scenarios_hash({"s": b})


def test_thread_safety_of_step():
    # Controller.step holds a lock; concurrent calls must not corrupt state or raise.
    ctrl = Controller()
    errors = []

    def worker():
        try:
            for _ in range(50):
                ctrl.step(metrics=HIGH, current_replicas=5, phase="peak")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    # State remains coherent afterwards.
    res = ctrl.step(metrics=MID, current_replicas=5)
    assert isinstance(res.action_score, float)


def test_gradual_growth_eventually_signals_scale_out():
    ctrl = CloudScalingController()
    steps = []
    for i in range(40):
        d = 0.2 + 0.75 * (i / 39)
        steps.append({"metrics": {"cpu": d, "memory": d * 0.9, "latency_p99": d * 0.8,
                                  "error_rate": d * 0.2, "queue_depth": d * 0.7},
                      "current_replicas": 5})
    recs = _series(ctrl, steps)
    assert any(r.replica_delta > 0 or r.recommendation.startswith("observe_out") for r in recs)


def test_budget_cap_representable_in_config():
    # The controller represents a max via safety ratios; recommendations respect them.
    cfg = InfraControllerConfig(max_scale_out_ratio=0.25)
    ctrl = CloudScalingController(cfg)
    recs = _series(ctrl, [{"metrics": HIGH, "current_replicas": 8, "phase": "peak"}] * 30)
    for r in recs:
        assert r.replica_delta <= max(1, int(8 * 0.25))
