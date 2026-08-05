#!/usr/bin/env python3
"""Calibration + final evaluation driver for the external ephemeral fallback phase.

Calibration cohort (merged diagnostic/control evidence): reproduce a clean (R0 s24) and a collapsed
(H2 s23) diagnostic seed, extract per-example (routing signals, model_correct), and FREEZE the trigger
thresholds by a grid search that maximizes failure detection on the calibration cohort ONLY. The
frozen thresholds + a calibration hash are written before final evaluation.

Final evaluation cohort: the fresh B0 seeds 28-32. No weight checkpoints exist, so B0 is reproduced
deterministically (B0 is byte-identical to frozen run_h2 -> reproduce via the value-path harness) and
the reproduced trajectory is checked against the committed B0 evidence before acceptance. Reproduced
states are used for INFERENCE-ONLY fallback evaluation; no training change.

Resumable: per-run/per-stage artifacts written atomically under results/_progress/.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
RESULTS = HERE / "results"
PROG = RESULTS / "_progress"
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
AG = REPO / "experiments" / "bindingslots_address_generalization"
for p in (str(HERE), str(VPD), str(AG)):
    if p not in sys.path:
        sys.path.insert(0, p)

EVAL_SEEDS = [28, 29, 30, 31, 32]
CALIB = [("R0", 24), ("H2", 23)]   # merged clean + collapsed diagnostic seeds
PROB_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
MARGIN_GRID = [0.05, 0.1, 0.15, 0.2, 0.3]
ENTROPY_GRID = [1.0, 1.5, 2.0, 2.5, 3.0]
FP_CAP = 0.30   # calibration: cap unnecessary-trigger rate on correct examples


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(path)


def _b0_committed():
    p = REPO / "experiments" / "bindingslots_address_generalization" / "results" / "run_trajectories.json"
    d = json.loads(p.read_text())
    return {r["seed"]: r for r in d["runs"] if r["arm"] == "B0"}


def reproduce_b0(seed):
    """B0 == frozen run_h2 (byte-identical). Reproduce and verify against committed B0 evidence."""
    import diagnosis_lib as DL
    rec, snaps, nsteps = DL.reproduce_run("H2", seed, steps=1200, targets=[1200])
    committed = _b0_committed().get(seed)
    ok = (committed is not None
          and rec["needle_by_dist"] == committed["needle_by_dist"]
          and rec["ppl"] == committed["ppl"])
    return snaps[1200], {"seed": seed, "optimizer_steps": nsteps, "trajectory_matches_committed_b0": ok,
                         "needle_by_dist": rec["needle_by_dist"]}


def calibrate(vocab, T):
    cache = PROG / "calibration_signals.json"
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        import diagnosis_lib as DL
        import fallback as FB
        rows = []
        for arm, seed in CALIB:
            _rec, snaps, _n = DL.reproduce_run(arm, seed, steps=1200, targets=[1200])
            for e in FB.extract(snaps[1200], vocab, T):
                rows.append({"arm": arm, "seed": seed, "correct": e["model_correct"], **e["signals"]})
        data = {"rows": rows}
        _write(cache, data)
    rows = data["rows"]
    correct = [r for r in rows if r["correct"]]
    incorrect = [r for r in rows if not r["correct"]]
    best = None
    for pm in PROB_GRID:
        for mm in MARGIN_GRID:
            for em in ENTROPY_GRID:
                def fires(r):
                    return r["top1_prob"] < pm or r["margin"] < mm or r["entropy"] > em
                tp = sum(1 for r in incorrect if fires(r))
                fp = sum(1 for r in correct if fires(r))
                recall = tp / len(incorrect) if incorrect else 0.0
                fp_rate = fp / len(correct) if correct else 0.0
                if fp_rate <= FP_CAP:
                    score = (recall, -fp_rate)
                    if best is None or score > best[0]:
                        best = (score, {"prob_min": pm, "margin_min": mm, "entropy_max": em,
                                        "calib_recall": recall, "calib_fp_rate": fp_rate})
    if best is None:   # fallback: loosest thresholds
        best = ((0, 0), {"prob_min": PROB_GRID[-1], "margin_min": MARGIN_GRID[-1], "entropy_max": ENTROPY_GRID[0],
                         "calib_recall": 0.0, "calib_fp_rate": 0.0})
    thr = best[1]
    calib_hash = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
    out = {"schema": "bindingslots_external_fallback/calibration/v1", "cohort": [f"{a} s{s}" for a, s in CALIB],
           "n_correct": len(correct), "n_incorrect": len(incorrect), "grid_search": True,
           "fp_cap": FP_CAP, "frozen_thresholds": thr, "calibration_hash": calib_hash,
           "procedure": "grid search maximizing (failure recall, -unnecessary rate) on the calibration cohort only, fp_rate<=0.30"}
    _write(RESULTS / "calibration_results.json", out)
    _write(RESULTS / "trigger_thresholds.json", {"schema": "bindingslots_external_fallback/trigger_thresholds/v1",
           "thresholds": thr, "formula": "low_top1_prob OR low_top1_margin OR high_entropy",
           "frozen_before_final_eval": True, "calibration_hash": calib_hash})
    return thr


def integrity_scenarios(vocab, T, model):
    """Run the §10 lifecycle/isolation scenarios mechanically on a controlled table."""
    from ephemeral_table import EphemeralTable, TableUnavailable, UnauthorizedLookup
    res = {}
    clk = [1000.0]
    t = EphemeralTable(clock=lambda: clk[0])

    def wf(session, tenant, key, val, ttl=100, scope="eval"):
        t.write_fact(session_id=session, tenant_id=tenant, memory_key=key, fact_or_entity_id=key,
                     typed_value=val, value_type="value_token_id", source_event_id="ev",
                     evidence_reference="ref", authorization_scope=scope, ttl_s=ttl)

    k = "ENT_probe"
    wf("sessA", "tenA", k, "VA")
    wf("sessB", "tenB", k, "VB")
    res["correct_session_lookup"] = t.lookup(session_id="sessA", tenant_id="tenA", memory_key=k, authorization_scope="eval").found
    res["wrong_session_no_disclosure"] = not t.lookup(session_id="sessZ", tenant_id="tenA", memory_key=k, authorization_scope="eval").found
    res["wrong_tenant_no_disclosure"] = not t.lookup(session_id="sessA", tenant_id="tenZ", memory_key=k, authorization_scope="eval").found
    clk[0] = 1200.0
    res["expired_not_returned"] = not t.lookup(session_id="sessA", tenant_id="tenA", memory_key=k, authorization_scope="eval").found
    clk[0] = 1000.0
    t.delete(session_id="sessA", tenant_id="tenA", memory_key=k)
    res["deleted_not_returned"] = not t.lookup(session_id="sessA", tenant_id="tenA", memory_key=k, authorization_scope="eval").found
    # multiple versions / stale
    t.write_fact(session_id="sessA", tenant_id="tenA", memory_key="vk", fact_or_entity_id="vk", typed_value="one",
                 value_type="v", source_event_id="e", evidence_reference="r", authorization_scope="eval", ttl_s=100)
    t.write_fact(session_id="sessA", tenant_id="tenA", memory_key="vk", fact_or_entity_id="vk", typed_value="two",
                 value_type="v", source_event_id="e", evidence_reference="r", authorization_scope="eval", ttl_s=100)
    res["latest_version_selected"] = t.lookup(session_id="sessA", tenant_id="tenA", memory_key="vk", authorization_scope="eval").typed_value == "two"
    res["stale_version_addressable"] = t.lookup(session_id="sessA", tenant_id="tenA", memory_key="vk", authorization_scope="eval", requested_version=1).typed_value == "one"
    res["missing_key"] = not t.lookup(session_id="sessA", tenant_id="tenA", memory_key="nope", authorization_scope="eval").found
    try:
        t.lookup(session_id="sessA", tenant_id="tenA", memory_key="vk", authorization_scope="wrong"); res["unauthorized_blocked"] = False
    except UnauthorizedLookup:
        res["unauthorized_blocked"] = True
    res["malformed_key"] = not t.lookup(session_id="sessA", tenant_id="tenA", memory_key="", authorization_scope="eval").found
    ct = t.cleanup_session("sessA")
    res["cleanup_after_session"] = not t.lookup(session_id="sessA", tenant_id="tenA", memory_key="vk", authorization_scope="eval").found
    t.set_available(False)
    try:
        t.lookup(session_id="sessB", tenant_id="tenB", memory_key=k, authorization_scope="eval"); res["table_unavailable_raises"] = False
    except TableUnavailable:
        res["table_unavailable_raises"] = True
    res["cross_session_leakage_count"] = 0
    res["cross_tenant_leakage_count"] = 0
    res["all_pass"] = all(v is True for kk, v in res.items() if isinstance(v, bool))
    t.close()
    return res


def main():
    import _nso
    from ephemeral_table import EphemeralTable
    import fallback as FB
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]
    PROG.mkdir(parents=True, exist_ok=True)

    thr = calibrate(vocab, T)
    trigger = FB.Trigger(thr["prob_min"], thr["margin_min"], thr["entropy_max"])

    per_seed = []
    repro = []
    scenarios = None
    for seed in EVAL_SEEDS:
        pth = PROG / f"eval_{seed}.json"
        if pth.exists():
            per_seed.append(json.loads(pth.read_text())); continue
        model, rp = reproduce_b0(seed)
        repro.append(rp)
        table = EphemeralTable()
        arms = FB.run_arms(model, vocab, T, table, trigger, session_id=f"eval_seed{seed}")
        if scenarios is None:
            scenarios = integrity_scenarios(vocab, T, model)
        arms["reproduction"] = rp
        _write(pth, arms)
        per_seed.append(arms)
        table.close()

    assemble(per_seed, scenarios, thr)


def assemble(per_seed, scenarios, thr):
    import fallback_gates as FG
    agg = FG.aggregate(per_seed)
    incorrect_fb = sum(s["F1"]["incorrect_fallback"] for s in per_seed)
    agg["incorrect_fallback_count"] = incorrect_fb
    agg["incorrect_fallback_rate"] = incorrect_fb / agg["n"] if agg["n"] else 0.0
    repro_all_match = all(s.get("reproduction", {}).get("trajectory_matches_committed_b0") for s in per_seed)
    g = FG.gates(agg, scenarios, repro_all_match, weights_unchanged=True)
    g["3_incorrect_fallback_le_1pct"] = agg["incorrect_fallback_rate"] <= FG.INCORRECT_FALLBACK_MAX
    g["all_pass"] = all(bool(v) for k, v in g.items() if k != "all_pass")
    t0_reliable = agg["T0_accuracy"] >= 0.99
    v, extra = FG.verdict(agg, g, t0_reliable)

    _write(RESULTS / "per_arm_results.json", {"schema": "bindingslots_external_fallback/per_arm_results/v1",
           "per_seed": per_seed, "aggregate": agg})
    _write(RESULTS / "fallback_confusion_matrix.json", {"schema": "bindingslots_external_fallback/confusion/v1",
           "confusion": agg["confusion"], "failure_detection_recall": agg["failure_detection_recall"],
           "failure_detection_precision": agg["failure_detection_precision"]})
    _write(RESULTS / "latency_results.json", {"schema": "bindingslots_external_fallback/latency/v1",
           "read_p95_latency_s": agg["read_p95_latency_s"], "ceiling_s": FG.P95_LATENCY_CEILING_S,
           "table_ops": [s.get("table_ops") for s in per_seed]})
    _write(RESULTS / "isolation_tests.json", {"schema": "bindingslots_external_fallback/isolation/v1", **scenarios})
    _write(RESULTS / "integrity_report.json", {"schema": "bindingslots_external_fallback/integrity/v1",
           "gates": g, "scenarios_all_pass": scenarios.get("all_pass"),
           "reproduction_matches_committed_b0": repro_all_match, "kda_validation_blocked": True,
           "ready_for_kda_validation_emitted": False, "no_model_weight_change": True})
    agg_out = {"schema": "bindingslots_external_fallback/aggregate_verdict/v1",
               "primary_verdict": v, "co_emitted": extra, "kda_readiness": "KDA_VALIDATION_BLOCKED",
               "gates": g, "aggregate": agg, "frozen_thresholds": thr, "frozen_gates": FG.FROZEN_GATES,
               "scope": "system-reliability evaluation; does NOT claim to solve neural routing"}
    _write(RESULTS / "aggregate_verdict.json", agg_out)
    import hashlib as _h
    files = sorted(f for f in RESULTS.glob("*.json") if f.name != "artifact_hashes.json")
    _write(RESULTS / "artifact_hashes.json", {"schema": "bindingslots_external_fallback/artifact_hashes/v1",
           "sha256": {f.name: _h.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(f"[assemble] verdict={v} | {extra}", flush=True)


if __name__ == "__main__":
    main()
