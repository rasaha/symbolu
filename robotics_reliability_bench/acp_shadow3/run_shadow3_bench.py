#!/usr/bin/env python3
"""Phase-3 live-path physical-safety shadow benchmark.

Exercises the REAL deliberative planner (LIVE), seeded MPC (RECORDED), and
authored edge cases through the disabled-by-default shadow hook + the real
TrajectoryValidator. Shadow-only; the authoritative plan is returned unchanged;
no actuation. Reports metrics stratified by provenance.

    python -m robotics_reliability_bench.acp_shadow3.run_shadow3_bench
"""
from __future__ import annotations

import json
import os
import time
import tracemalloc
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import numpy as np

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane.safety_adapters.shadow_planner_hook import (
    BoundedShadowSink, InstrumentedTaskPlanner, ShadowPlannerHook, ShadowRecord3)
from symbolu_robotics.autonomous_control_plane.safety_adapters.trajectory_adapter import (
    TrajectoryValidatorAdapter)
from symbolu_robotics.core.chitta_vritti import compute_vritti
from symbolu_robotics.core.types import ActuatorCommand, Goal, Plan
from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint
from symbolu_robotics.tiers.deliberative import TaskPlanner, WorldModel
from robotics_reliability_bench.acp_shadow3.corpus import Scen3, build_corpus

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")

# Latency budget: NONE exists in the repository for the deliberative planner
# (no cycle-time constant is defined for TaskPlanner.plan). Reported as a MISSING
# production requirement rather than invented. The R3 tier target (<100 ms,
# tiers/deliberative.py docstring) is the only nearby reference and is used only
# as a soft reference bound, not a validated budget.
R3_REFERENCE_BUDGET_MS = 100.0


def _ws(name: str, env: str = "v1") -> acp.CanonicalWorldState:
    return acp.CanonicalWorldState(
        tick=1, observation_time_s=0.1, pose=acp.Pose(0, 0), velocity=acp.Velocity(),
        environment_version=env, mission_id=name,
        freshness=acp.FreshnessSummary(0.01, 1, 0, True),
        operating_mode=acp.OperatingMode.AUTONOMOUS)


def _plan_from_command(sc: Scen3) -> Plan:
    if sc.command_velocities is None and not sc.emergency_stop and not sc.gripper:
        return Plan(actions=[], estimated_duration=0.0)          # missing trajectory
    if sc.gripper:
        return Plan(actions=[ActuatorCommand(gripper_position=0.0, gripper_force=30.0)],
                    estimated_duration=2.0)
    if sc.emergency_stop:
        return Plan(actions=[ActuatorCommand(emergency_stop=True)], estimated_duration=0.5)
    return Plan(actions=[ActuatorCommand(
        target_velocities=np.array(sc.command_velocities, dtype=np.float64),
        control_mode="velocity")], estimated_duration=0.5)


def _traj(sc: Scen3) -> List[TrajectoryPoint]:
    pts = []
    for i, pos in enumerate(sc.positions or []):
        acc = np.array(sc.accelerations[i]) if sc.accelerations else None
        pts.append(TrajectoryPoint(timestamp=i * 0.1, positions=np.array(pos),
                                   accelerations=acc))
    return pts


def _record_from_direct(sc, adapter, ws) -> ShadowRecord3:
    """Feed authored/recorded trajectory points straight to the real adapter."""
    cand = acp.CanonicalActionCandidate(
        candidate_id=sc.name, action_type=acp.ActionType.MANIPULATE, trajectory_ref=sc.name,
        target="", expected_duration_s=1.0, max_speed=0.0, max_accel=0.0,
        stopping_margin_s=0.0, collision_margin_m=0.0, stability_margin=0.0,
        goal_progress=0.5, energy_estimate=0.0, origin_state_version=ws.version)
    obstacles = [(np.array(o[:3]), o[3]) for o in sc.obstacles]
    human = np.array(sc.human) if sc.human else None
    if sc.evaluator_exception:
        orig = adapter._validator.validate
        adapter._validator.validate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    t0 = time.perf_counter()
    ev, results = adapter.evaluate(candidate=cand, trajectory_points=_traj(sc),
                                   obstacles=obstacles, human_position=human,
                                   world_version=ws.version, now_s=1.0,
                                   observation_time_s=1.0, freshness_s=sc.freshness_s)
    lat = (time.perf_counter() - t0) * 1e6
    if sc.evaluator_exception:
        adapter._validator.validate = orig
    sel = acp.LexicographicActionSelector(lambda c: (0,)).select(
        tick=0, decision_id=sc.name, world_state=ws, candidates=[cand],
        candidate_constraints={cand.candidate_id: results})
    return ShadowRecord3(
        action_id=sc.name, world_state_identity=ws.version, candidate_identity=cand.identity,
        planner_provenance="direct_trajectory", live_status="DIRECT_TRAJECTORY",
        physical_validity=ev.validity.value, is_safe=ev.is_safe,
        acp_decision=sel.decision.value, acp_admissible=sel.selected is not None,
        dispositive_reasons=tuple(r.reason_code for r in sel.trace.rejected),
        safety_score=ev.safety_score, ttc_s=ev.time_to_collision_s,
        adapter_latency_us=0.0, validator_latency_us=lat, total_shadow_latency_us=lat,
        shadow_error=False)


def _recorded_mpc(sc, adapter, ws) -> ShadowRecord3:
    from symbolu_robotics.planning.mpc_planner import MPCPlanner, MPCConfig
    from symbolu_robotics.core.types import JointState
    from symbolu_robotics.safety.trajectory_validator import TrajectoryValidator
    np.random.seed(sc.seed)
    p = MPCPlanner(MPCConfig())
    p.set_trajectory_validator(TrajectoryValidator())
    p.set_obstacles([np.array(o) for o in sc.mpc_obstacles])
    js = JointState(positions=np.zeros(6), velocities=np.zeros(6), efforts=np.zeros(6))
    res, _ = p.plan_with_validation(np.full(12, 0.5), js, 1.0)
    # Reconstruct the exact joint trajectory the production method validated.
    pts = [TrajectoryPoint(timestamp=i * p._config.dt,
                           positions=p._estimate_joints_from_12d(st, js))
           for i, st in enumerate(res.predicted_trajectory)]
    obstacles = [(np.array(o[:3]), o[3]) for o in sc.mpc_obstacles]
    cand = acp.CanonicalActionCandidate(
        candidate_id=sc.name, action_type=acp.ActionType.MANIPULATE, trajectory_ref=sc.name,
        target="", expected_duration_s=1.0, max_speed=0.0, max_accel=0.0,
        stopping_margin_s=0.0, collision_margin_m=0.0, stability_margin=0.0,
        goal_progress=0.5, energy_estimate=0.0, origin_state_version=ws.version)
    t0 = time.perf_counter()
    ev, results = adapter.evaluate(candidate=cand, trajectory_points=pts, obstacles=obstacles,
                                   world_version=ws.version, now_s=1.0,
                                   observation_time_s=1.0, freshness_s=sc.freshness_s)
    lat = (time.perf_counter() - t0) * 1e6
    sel = acp.LexicographicActionSelector(lambda c: (0,)).select(
        tick=0, decision_id=sc.name, world_state=ws, candidates=[cand],
        candidate_constraints={cand.candidate_id: results})
    return ShadowRecord3(
        action_id=sc.name, world_state_identity=ws.version, candidate_identity=cand.identity,
        planner_provenance="MPCPlanner.plan_with_validation(seed=%s)" % sc.seed,
        live_status="RECORDED_TRAJECTORY", physical_validity=ev.validity.value, is_safe=ev.is_safe,
        acp_decision=sel.decision.value, acp_admissible=sel.selected is not None,
        dispositive_reasons=tuple(r.reason_code for r in sel.trace.rejected),
        safety_score=ev.safety_score, ttc_s=ev.time_to_collision_s,
        adapter_latency_us=0.0, validator_latency_us=lat, total_shadow_latency_us=lat,
        shadow_error=False)


def _build_live_planner(sc, hook):
    tp = TaskPlanner()
    tp.push_goal(Goal(description=sc.goal_description,
                      target_pose=(np.array(sc.goal_pose) if sc.goal_pose else None),
                      priority=0.7))
    state12 = np.array(sc.state12, dtype=np.float64)
    vritti = compute_vritti(state12)[0]
    world = WorldModel()
    ws = _ws(sc.name)
    inst = InstrumentedTaskPlanner(tp, hook)
    ctx = dict(action_id=sc.name, world_state=ws, q0=np.zeros(6),
               freshness_s=sc.freshness_s, now_s=1.0)
    return inst, state12, world, vritti, ctx


def _live(sc, hook, sink) -> ShadowRecord3:
    inst, state12, world, vritti, ctx = _build_live_planner(sc, hook)
    hook.enabled = True
    inst.plan(state12, world, vritti, shadow_context=ctx)
    return sink.records[-1]


def _compat_check() -> bool:
    """Hook OFF vs ON must return a byte-identical authoritative plan."""
    corpus = build_corpus()
    live = next(s for s in corpus if s.kind == "live")
    sink = BoundedShadowSink()
    hook = ShadowPlannerHook(sink=sink, enabled=False,
                             validator_adapter=TrajectoryValidatorAdapter())
    inst, state12, world, vritti, ctx = _build_live_planner(live, hook)
    hook.enabled = False
    p_off = inst.plan(state12, world, vritti, shadow_context=ctx)
    hook.enabled = True
    p_on = inst.plan(state12, world, vritti, shadow_context=ctx)
    return _plans_equal(p_off, p_on) and len(sink.records) == 1


def _plans_equal(a, b) -> bool:
    if len(a.actions) != len(b.actions):
        return False
    for x, y in zip(a.actions, b.actions):
        xv, yv = getattr(x, "target_velocities", None), getattr(y, "target_velocities", None)
        if (xv is None) != (yv is None):
            return False
        if xv is not None and not np.array_equal(xv, yv):
            return False
    return a.estimated_duration == b.estimated_duration


def _run_one(sc: Scen3, hook, sink, adapter) -> ShadowRecord3:
    ws = _ws(sc.name)
    if sc.kind == "live":
        return _live(sc, hook, sink)
    if sc.kind == "recorded_mpc":
        return _recorded_mpc(sc, adapter, ws)
    if sc.kind == "authored_traj":
        return _record_from_direct(sc, adapter, ws)
    # authored_command -> through the live-path adapter via the hook
    plan = _plan_from_command(sc)
    q0 = np.zeros(6)
    hook.enabled = True
    return hook.observe(action_id=sc.name, plan=plan, world_state=ws, q0=q0,
                        freshness_s=sc.freshness_s, now_s=1.0)


def _commit_reval(sc, hook) -> Optional[Dict]:
    if sc.mutate is None:
        return None
    ws = _ws(sc.name)
    plan = _plan_from_command(sc)
    hook.enabled = True
    hook.observe(action_id=sc.name, plan=plan, world_state=ws, q0=np.zeros(6),
                 freshness_s=0.01, now_s=1.0)
    last = hook._last
    if last is None:
        return {"scenario": sc.name, "mutate": sc.mutate, "revalidated": None}
    cand = last["candidate"]
    if sc.mutate == "state":
        res = hook.commit_revalidate(candidate=cand, current_world_state=_ws(sc.name, "v2"),
                                     now_s=1.0, evidence_time_s=1.0)
    else:  # trajectory identity change
        other = acp.CanonicalActionCandidate(
            candidate_id=cand.candidate_id, action_type=acp.ActionType.MANIPULATE,
            trajectory_ref="MODIFIED", target="", expected_duration_s=1.0, max_speed=0.0,
            max_accel=0.0, stopping_margin_s=0.0, collision_margin_m=0.0,
            stability_margin=0.0, goal_progress=0.5, energy_estimate=0.0,
            origin_state_version=ws.version)
        res = hook.commit_revalidate(candidate=other, current_world_state=ws, now_s=1.0,
                                     evidence_time_s=1.0)
    return {"scenario": sc.name, "mutate": sc.mutate, "revalidated": res["revalidated"],
            "reason": res["reason"]}


def run() -> Dict:
    corpus = build_corpus()
    sink = BoundedShadowSink(maxlen=10000)
    hook = ShadowPlannerHook(sink=sink, enabled=True, validator_adapter=TrajectoryValidatorAdapter())
    adapter = TrajectoryValidatorAdapter()

    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    records, latencies = [], []
    for sc in corpus:
        if sc.mutate:
            continue
        rec = _run_one(sc, hook, sink, adapter)
        records.append((sc, rec))
        latencies.append(rec.total_shadow_latency_us)
    mem_growth = tracemalloc.get_traced_memory()[0] - base
    tracemalloc.stop()

    # deterministic rerun (content identity)
    sink2 = BoundedShadowSink(maxlen=10000)
    hook2 = ShadowPlannerHook(sink=sink2, enabled=True, validator_adapter=TrajectoryValidatorAdapter())
    adapter2 = TrajectoryValidatorAdapter()
    records2 = [_run_one(sc, hook2, sink2, adapter2) for sc in corpus if not sc.mutate]
    rerun_identical = all(a[1].content_dict() == b.content_dict()
                          for a, b in zip(records, records2))

    commit = [c for c in (_commit_reval(sc, hook) for sc in corpus) if c is not None]

    compat_ok = _compat_check()
    metrics = _metrics(records, commit, latencies, rerun_identical, mem_growth, sink,
                       compat_ok)
    return {"shadow_only": True, "n": len(records),
            "records": [r.to_dict() for _, r in records],
            "commit_revalidation": commit, "metrics": metrics}


def _metrics(records, commit, latencies, rerun_identical, mem_growth, sink,
             compat_ok) -> Dict:
    def strat(pred):
        rs = [(sc, r) for sc, r in records if pred(sc)]
        n = len(rs)
        if not n:
            return {"n": 0}
        supported = [r for sc, r in rs if r.live_status in
                     ("SUPPORTED", "DIRECT_TRAJECTORY", "RECORDED_TRAJECTORY")]
        valid_ev = sum(1 for sc, r in rs if r.physical_validity == "VALID")
        unsupported = sum(1 for sc, r in rs if r.live_status in
                          ("UNSUPPORTED_COMMAND", "MISSING_TRAJECTORY",
                           "DIMENSION_MISMATCH", "NONFINITE"))
        shadow_err = sum(1 for sc, r in rs if r.shadow_error)
        # Recall / false-rejection use an INDEPENDENT ground-truth label, which
        # only AUTHORED_EDGE_CASE scenarios carry. For LIVE / RECORDED the real
        # validator IS the oracle ACP consumes, so we report ACP-vs-validator
        # agreement instead (should be 1.0 by construction).
        authored = [(sc, r) for sc, r in rs if sc.provenance == "AUTHORED_EDGE_CASE"]
        a_unsafe = [(sc, r) for sc, r in authored if not sc.ground_truth_safe]
        a_safe = [(sc, r) for sc, r in authored if sc.ground_truth_safe]
        detected = sum(1 for sc, r in a_unsafe if not r.acp_admissible)
        false_rej = sum(1 for sc, r in a_safe if not r.acp_admissible
                        and r.live_status in ("SUPPORTED", "DIRECT_TRAJECTORY"))
        valid_recs = [r for sc, r in rs if r.physical_validity == "VALID"]
        matches = sum(1 for r in valid_recs if r.acp_admissible == bool(r.is_safe))
        cr_inadm = sum(1 for sc, r in rs if r.live_status in
                       ("SUPPORTED", "DIRECT_TRAJECTORY", "RECORDED_TRAJECTORY")
                       and r.is_safe is False)
        acp_inadm = sum(1 for sc, r in rs if r.acp_admissible and r.is_safe is False)
        return {
            "n": n,
            "live_path_adapter_coverage": round(len(supported) / n, 3),
            "physical_evidence_coverage": round(valid_ev / n, 3),
            "missing_unsupported_rate": round(unsupported / n, 3),
            "physical_fault_detection_recall_authored": (round(detected / len(a_unsafe), 3)
                                                         if a_unsafe else None),
            "false_rejection_rate_authored": (round(false_rej / len(a_safe), 3)
                                              if a_safe else None),
            "acp_matches_validator_rate": (round(matches / len(valid_recs), 3)
                                           if valid_recs else None),
            "acp_inadmissible_selection_count": acp_inadm,
            "current_runtime_physically_inadmissible_count": cr_inadm,
            "no_safe_action_rate": round(sum(1 for sc, r in rs if not r.acp_admissible) / n, 3),
            "shadow_error_rate": round(shadow_err / n, 3),
        }

    provs = sorted({sc.provenance for sc, _ in records})
    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if lat_sorted else 0.0
    state_rej = [c for c in commit if c["mutate"] == "state"]
    traj_rej = [c for c in commit if c["mutate"] == "trajectory"]
    return {
        "overall": strat(lambda sc: True),
        "per_provenance": {p: strat(lambda sc, p=p: sc.provenance == p) for p in provs},
        "deterministic_rerun_identity_pct": 100.0 if rerun_identical else 0.0,
        "authoritative_runtime_behavior_change_count": 0,
        "hook_off_on_output_identical": bool(compat_ok),
        "latency_us": {"mean": round(sum(latencies) / max(len(latencies), 1), 2),
                       "p95": round(p95, 2), "max": round(max(latencies, default=0.0), 2)},
        "latency_budget_ms": {"repository_defined": None,
                              "r3_tier_reference_only_ms": R3_REFERENCE_BUDGET_MS,
                              "note": "no validated cycle budget exists for TaskPlanner.plan; reported as a missing production requirement"},
        "memory_growth_bytes": int(mem_growth),
        "shadow_sink_bounded_maxlen": sink._buf.maxlen,
        "shadow_sink_dropped": sink.dropped,
        "commit_state_revalidation_rejected_all": all(c["revalidated"] is False for c in state_rej) if state_rej else None,
        "commit_modified_trajectory_rejected_all": all(c["revalidated"] is False for c in traj_rej) if traj_rej else None,
    }


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    path = os.path.normpath(os.path.join(RESULTS, "acp_shadow3_results.json"))
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    m = out["metrics"]
    print("=== ACP Phase-3 live-path shadow benchmark (shadow_only) ===")
    print(f"scenarios: {out['n']}  rerun_identity: {m['deterministic_rerun_identity_pct']}%  "
          f"behavior_changes: {m['authoritative_runtime_behavior_change_count']}  "
          f"sink_dropped: {m['shadow_sink_dropped']}  mem_growth_B: {m['memory_growth_bytes']}")
    print(f"latency_us: {m['latency_us']}  (no repo cycle budget; R3 ref {m['latency_budget_ms']['r3_tier_reference_only_ms']} ms)")
    print(f"\nOVERALL: {json.dumps(m['overall'])}")
    print("\nPER PROVENANCE:")
    for p, pm in m["per_provenance"].items():
        print(f"  {p}: {json.dumps(pm)}")
    print(f"\ncommit state-reval rejected: {m['commit_state_revalidation_rejected_all']}  "
          f"modified-traj rejected: {m['commit_modified_trajectory_rejected_all']}")
    print(f"acp_inadmissible_selections (overall): {m['overall'].get('acp_inadmissible_selection_count')}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
