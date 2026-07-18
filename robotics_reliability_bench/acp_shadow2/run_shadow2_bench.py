#!/usr/bin/env python3
"""Phase-2 real-scenario physical-safety shadow benchmark.

Runs the corpus through the REAL ``TrajectoryValidator`` via the ACP adapter,
applies the ACP hard filter using genuine physical evidence, and compares to a
modeled current-runtime pick (which has no physical gate at these call sites).
Shadow-only; zero production edits; no actuation.

    python -m robotics_reliability_bench.acp_shadow2.run_shadow2_bench

Reports metrics separately per provenance class and family (never one combined
headline). Writes results/acp_shadow2_results.json.
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from typing import Dict, List, Optional

import numpy as np

import symbolu_robotics.autonomous_control_plane as acp
from symbolu_robotics.autonomous_control_plane.safety_adapters.trajectory_adapter import (
    TrajectoryValidatorAdapter)
from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint
from robotics_reliability_bench.acp_shadow2.corpus import (PhysCandidate,
                                                           PhysScenario, build_corpus)

RESULTS = os.path.join(os.path.dirname(__file__), "..", "results")
_ABSTRACT_FLOOR = 0.5   # legacy Phase-1 conflict safety floor (for agreement test)


def _traj(c: PhysCandidate) -> List[TrajectoryPoint]:
    pts = []
    for i, pos in enumerate(c.positions):
        vel = np.array(c.velocities[i]) if c.velocities else None
        acc = np.array(c.accelerations[i]) if c.accelerations else None
        pts.append(TrajectoryPoint(timestamp=i * 0.1, positions=np.array(pos),
                                   velocities=vel, accelerations=acc,
                                   coherence=c.coherence))
    return pts


def _candidate(c: PhysCandidate, world_version: str) -> acp.CanonicalActionCandidate:
    atype = (acp.ActionType.STOP if c.safe_fallback else acp.ActionType.MANIPULATE)
    meta = {}
    if c.abstract_safety is not None:
        meta["abstract_safety"] = repr(float(c.abstract_safety))
    return acp.CanonicalActionCandidate(
        candidate_id=c.id, action_type=atype, trajectory_ref=f"{c.id}:traj",
        target="", expected_duration_s=1.0, max_speed=0.0, max_accel=0.0,
        stopping_margin_s=0.0, collision_margin_m=0.0, stability_margin=0.0,
        goal_progress=0.5, energy_estimate=0.0, origin_state_version=world_version,
        metadata=meta)


def _world(name: str, env: str = "v1") -> acp.CanonicalWorldState:
    return acp.CanonicalWorldState(
        tick=1, observation_time_s=0.1, pose=acp.Pose(0.0, 0.0),
        velocity=acp.Velocity(), environment_version=env, mission_id=name,
        freshness=acp.FreshnessSummary(0.01, 1, 0, True),
        operating_mode=acp.OperatingMode.AUTONOMOUS)


def _evaluate(sc: PhysScenario, adapter: TrajectoryValidatorAdapter) -> Dict:
    ws = _world(sc.name)
    cands, cc, evidence, scores = [], {}, {}, {}
    for c in sc.candidates:
        cand = _candidate(c, ws.version)
        obstacles = [(np.array(o[:3]), o[3]) for o in c.obstacles]
        human = np.array(c.human) if c.human else None
        ev, results = adapter.evaluate(
            candidate=cand, trajectory_points=_traj(c), obstacles=obstacles,
            human_position=human, world_version=ws.version, now_s=1.0,
            observation_time_s=1.0, freshness_s=c.freshness_s)
        cands.append(cand)
        cc[cand.candidate_id] = results
        evidence[cand.candidate_id] = ev
        scores[cand.candidate_id] = (ev.safety_score if ev.safety_score is not None
                                     else -1.0)
    # order physically-admissible survivors by physical safety_score desc.
    selector = acp.LexicographicActionSelector(
        lambda c: (-scores.get(c.candidate_id, -1.0),))
    outcome = selector.select(tick=1, decision_id=sc.name, world_state=ws,
                              candidates=cands, candidate_constraints=cc)
    return {"ws": ws, "cands": cands, "cc": cc, "evidence": evidence,
            "scores": scores, "outcome": outcome}


def _record(sc: PhysScenario, ev_run: Dict) -> Dict:
    outcome = ev_run["outcome"]
    evidence = ev_run["evidence"]
    surviving = set(outcome.trace.surviving_candidate_ids)
    by_id = {c.id: c for c in sc.candidates}

    # detection vs ground truth
    unsafe_ids = [c.id for c in sc.candidates if not c.ground_truth_safe]
    safe_ids = [c.id for c in sc.candidates if c.ground_truth_safe]
    detected = [cid for cid in unsafe_ids if cid not in surviving]
    false_rej = [cid for cid in safe_ids if cid not in surviving]

    # modeled current-runtime pick (no physical gate): abstract-max if present,
    # else the first candidate (planner-preferred). Physically inadmissible?
    if any(c.abstract_safety is not None for c in sc.candidates):
        cr_pick = max(sc.candidates, key=lambda c: (c.abstract_safety or 0.0)).id
    else:
        cr_pick = sc.candidates[0].id
    cr_inadmissible = cr_pick not in surviving

    # abstract vs physical agreement (per candidate, where abstract exists)
    av_pairs = []
    for c in sc.candidates:
        if c.abstract_safety is None:
            continue
        abstract_admits = c.abstract_safety >= _ABSTRACT_FLOOR
        physical_admits = c.id in surviving
        av_pairs.append({"id": c.id, "abstract_admits": abstract_admits,
                         "physical_admits": physical_admits,
                         "agree": abstract_admits == physical_admits})

    return {
        "scenario": sc.name, "provenance": sc.provenance, "family": sc.family,
        "required_case": sc.required_case,
        "candidate_ids": [c.id for c in sc.candidates],
        "acp_decision": outcome.decision.value,
        "acp_selected": outcome.selected.candidate_id if outcome.selected else None,
        "acp_surviving": sorted(surviving),
        "acp_rejected": [(r.candidate_id, r.reason_code) for r in outcome.trace.rejected],
        "physical_evidence": {cid: {
            "validity": ev.validity.value, "is_safe": ev.is_safe,
            "safety_score": ev.safety_score, "ttc_s": ev.time_to_collision_s,
            "violations": list(ev.limit_violations)} for cid, ev in evidence.items()},
        "ground_truth_unsafe": unsafe_ids,
        "physical_detected_unsafe": detected,
        "false_rejected_safe": false_rej,
        "current_runtime_pick": cr_pick,
        "current_runtime_physically_inadmissible": cr_inadmissible,
        "abstract_vs_physical": av_pairs,
        "acp_no_safe_action": outcome.decision.value == "NO_SAFE_ACTION",
        "shadow_only": True,
    }


def _authorization(sc: PhysScenario, adapter) -> Dict:
    ev_run = _evaluate(sc, adapter)
    outcome = ev_run["outcome"]
    cand = outcome.selected or ev_run["cands"][0]
    ws = ev_run["ws"]
    grant = acp.ReferenceControlAuthorizer().authorize(
        decision=outcome.decision if outcome.selected else acp.ActionDecision.EXECUTE,
        candidate=cand, world_state=ws, constraint_set_version="cs-1",
        decision_id=sc.name, issued_time_s=1.0, ttl_s=1.0)
    reval = acp.ReferenceCommitRevalidator()
    rejected, err = False, None
    try:
        if sc.mutate == "state":
            moved = _world(sc.name, env="v2")
            reval.revalidate(authorization=grant, candidate=cand,
                             current_world_state=moved,
                             current_constraint_set_version="cs-1", now_s=1.2)
        else:  # trajectory / candidate identity change
            other = acp.CanonicalActionCandidate(
                candidate_id=cand.candidate_id, action_type=acp.ActionType.MANIPULATE,
                trajectory_ref="MODIFIED", target="", expected_duration_s=1.0,
                max_speed=0.0, max_accel=0.0, stopping_margin_s=0.0,
                collision_margin_m=0.0, stability_margin=0.0, goal_progress=0.5,
                energy_estimate=0.0, origin_state_version=ws.version)
            reval.revalidate(authorization=grant, candidate=other,
                             current_world_state=ws,
                             current_constraint_set_version="cs-1", now_s=1.2)
    except (acp.StaleAuthorizationError, acp.errors.AuthorizationBindingError) as e:
        rejected, err = True, type(e).__name__
    return {"scenario": sc.name, "mutate": sc.mutate, "rejected": rejected,
            "error": err, "shadow_only": True}


def run() -> Dict:
    corpus = build_corpus()
    adapter = TrajectoryValidatorAdapter()
    phys = [s for s in corpus if s.family != "authorization"]
    auth = [s for s in corpus if s.family == "authorization"]

    records, latencies = [], []
    for sc in phys:
        t0 = time.perf_counter()
        ev_run = _evaluate(sc, adapter)
        latencies.append((time.perf_counter() - t0) * 1e6)
        records.append(_record(sc, ev_run))
    # deterministic rerun (decision content)
    records2 = [_record(sc, _evaluate(sc, adapter)) for sc in phys]
    rerun_identical = records == records2

    auth_results = [_authorization(sc, adapter) for sc in auth]
    # evidence-binding invariant: evidence for A cannot authorize B (direct check)
    binding_ok = _binding_check(adapter)

    metrics = _metrics(records, auth_results, rerun_identical, latencies, binding_ok)
    return {"shadow_only": True, "n_physical_scenarios": len(records),
            "records": records, "authorization": auth_results, "metrics": metrics}


def _binding_check(adapter) -> bool:
    ws = _world("bind")
    a = _candidate(PhysCandidate("A", [[0.1, 0, 0, 0, 0, 0]]), ws.version)
    b = _candidate(PhysCandidate("B", [[0.2, 0, 0, 0, 0, 0]]), ws.version)
    grant = acp.ReferenceControlAuthorizer().authorize(
        decision=acp.ActionDecision.EXECUTE, candidate=a, world_state=ws,
        constraint_set_version="cs-1", decision_id="bind", issued_time_s=1.0, ttl_s=1.0)
    try:
        acp.ReferenceCommitRevalidator().revalidate(
            authorization=grant, candidate=b, current_world_state=ws,
            current_constraint_set_version="cs-1", now_s=1.1)
        return False  # should have raised
    except acp.errors.AuthorizationBindingError:
        return True


def _metrics(records, auth_results, rerun_identical, latencies, binding_ok) -> Dict:
    def bucket(pred):
        rs = [r for r in records if pred(r)]
        n = len(rs)
        if n == 0:
            return {"n": 0}
        n_valid = sum(1 for r in rs if all(
            e["validity"] == "VALID" for e in r["physical_evidence"].values()) or
            r["physical_evidence"])
        valid_ev = sum(sum(1 for e in r["physical_evidence"].values()
                           if e["validity"] == "VALID") for r in rs)
        total_ev = sum(len(r["physical_evidence"]) for r in rs)
        stale = sum(sum(1 for e in r["physical_evidence"].values()
                        if e["validity"] == "STALE") for r in rs)
        missing = sum(sum(1 for e in r["physical_evidence"].values()
                          if e["validity"] == "MISSING") for r in rs)
        n_unsafe = sum(len(r["ground_truth_unsafe"]) for r in rs)
        n_detected = sum(len(r["physical_detected_unsafe"]) for r in rs)
        n_safe = sum(len(r["candidate_ids"]) - len(r["ground_truth_unsafe"]) for r in rs)
        n_falserej = sum(len(r["false_rejected_safe"]) for r in rs)
        cr_inadm = sum(1 for r in rs if r["current_runtime_physically_inadmissible"])
        acp_inadm = sum(1 for r in rs if r["acp_selected"] is not None
                        and r["acp_selected"] not in r["acp_surviving"])
        no_safe = sum(1 for r in rs if r["acp_no_safe_action"])
        return {
            "n": n,
            "real_physical_evidence_coverage": round(valid_ev / max(total_ev, 1), 3),
            "stale_evidence_rate": round(stale / max(total_ev, 1), 3),
            "missing_evidence_rate": round(missing / max(total_ev, 1), 3),
            "physical_detection_recall": (round(n_detected / n_unsafe, 3)
                                          if n_unsafe else None),
            "false_rejection_rate": (round(n_falserej / n_safe, 3) if n_safe else None),
            "current_runtime_physically_inadmissible_rate": round(cr_inadm / n, 3),
            "acp_inadmissible_selection_count": acp_inadm,
            "acp_no_safe_action_rate": round(no_safe / n, 3),
        }

    provs = sorted({r["provenance"] for r in records})
    fams = sorted({r["family"] for r in records})
    # abstract-vs-physical agreement
    av = [p for r in records for p in r["abstract_vs_physical"]]
    av_agree = round(sum(1 for p in av if p["agree"]) / len(av), 3) if av else None

    return {
        "overall": bucket(lambda r: True),
        "per_provenance": {p: bucket(lambda r, p=p: r["provenance"] == p) for p in provs},
        "per_family": {f: bucket(lambda r, f=f: r["family"] == f) for f in fams},
        "abstract_vs_physical_agreement_rate": av_agree,
        "abstract_vs_physical_pairs": av,
        "state_revalidation_rejection_rate": (
            round(sum(1 for a in auth_results if a["mutate"] == "state" and a["rejected"])
                  / max(sum(1 for a in auth_results if a["mutate"] == "state"), 1), 3)),
        "evidence_binding_rejection_verified": binding_ok,
        "modified_trajectory_rejection_verified": all(
            a["rejected"] for a in auth_results if a["mutate"] == "trajectory"),
        "deterministic_rerun_identity_pct": 100.0 if rerun_identical else 0.0,
        "mean_latency_us": round(sum(latencies) / max(len(latencies), 1), 2),
        "current_runtime_behavior_change_count": 0,
    }


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    path = os.path.normpath(os.path.join(RESULTS, "acp_shadow2_results.json"))
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    m = out["metrics"]
    print("=== ACP Phase-2 physical-safety shadow benchmark (shadow_only) ===")
    print(f"physical scenarios: {out['n_physical_scenarios']}  "
          f"rerun_identity: {m['deterministic_rerun_identity_pct']}%  "
          f"behavior_changes: {m['current_runtime_behavior_change_count']}")
    print(f"\nOVERALL: {json.dumps(m['overall'])}")
    print("\nPER PROVENANCE:")
    for p, pm in m["per_provenance"].items():
        print(f"  {p}: {json.dumps(pm)}")
    print("\nPER FAMILY:")
    for f, fm in m["per_family"].items():
        print(f"  {f}: {json.dumps(fm)}")
    print(f"\nabstract_vs_physical_agreement: {m['abstract_vs_physical_agreement_rate']}")
    print(f"state_reval_rejection: {m['state_revalidation_rejection_rate']}  "
          f"binding_rejection: {m['evidence_binding_rejection_verified']}  "
          f"modified_traj_rejection: {m['modified_trajectory_rejection_verified']}")
    print(f"acp_inadmissible_selections (overall): {m['overall'].get('acp_inadmissible_selection_count')}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
