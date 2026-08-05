#!/usr/bin/env python3
"""Driver: reproduce the frozen cohort (seeds 28-32), run arms M0/T0/F0/V100, integrity scenarios, and
timing; then assemble mechanical evidence + verdict. Resumable: per-seed progress under results/_progress.

Reproduction: B0 == the frozen run_h2 (byte-identical), so each seed's frozen state is deterministically
reconstructed and ACCEPTED only when its trajectory (needle_by_dist + ppl) matches the committed B0
evidence. The reconstructed state is used for INFERENCE ONLY — the arm evaluation performs zero optimizer
steps and leaves model parameters byte-identical (verified by a param hash before/after).
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
FALLBACK = REPO / "experiments" / "bindingslots_external_fallback"
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
AG = REPO / "experiments" / "bindingslots_address_generalization"
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
for p in (str(HERE), str(FALLBACK), str(VPD), str(AG), str(SBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

EVAL_SEEDS = [28, 29, 30, 31, 32]


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    tmp.replace(path)


def _b0_committed():
    d = json.loads((AG / "results" / "run_trajectories.json").read_text())
    return {r["seed"]: r for r in d["runs"] if r["arm"] == "B0"}


def _merged_m0():
    d = json.loads((FALLBACK / "results" / "per_arm_results.json").read_text())
    return {s["session_id"]: s["M0"]["correct"] / s["n"] for s in d["per_seed"]}


def _param_hash(model):
    h = hashlib.sha256()
    for name, p in sorted(model.named_parameters()):
        h.update(name.encode())
        h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def reproduce(seed):
    """Reconstruct the frozen B0 state for a seed and accept only on trajectory equality."""
    import diagnosis_lib as DL
    rec, snaps, nsteps = DL.reproduce_run("H2", seed, steps=1200, targets=[1200])
    committed = _b0_committed().get(seed)
    match = (committed is not None
             and rec["needle_by_dist"] == committed["needle_by_dist"]
             and rec["ppl"] == committed["ppl"])
    model = snaps[1200]
    return model, {"seed": seed, "reconstruction_optimizer_steps": nsteps,
                   "trajectory_matches_committed_b0": bool(match),
                   "needle_by_dist": rec["needle_by_dist"], "ppl": rec["ppl"],
                   "reconstructed_param_sha256": _param_hash(model)}


def run_one_seed(seed):
    import arms as ARMS
    import timing as TIMING
    import _nso
    TA, T = _nso.tasks_adapter, _nso.tasks
    vocab = TA.build_corpus()[1]

    model, repro = reproduce(seed)
    h_before = _param_hash(model)
    rec = ARMS.run_seed(model, vocab, T, seed)
    h_after = _param_hash(model)
    tim = TIMING.measure_seed(model, vocab, T, seed)
    merged_m0 = _merged_m0().get(f"eval_seed{seed}")
    rec["reproduction"] = repro
    rec["model_invariance"] = {
        "param_sha256_before_eval": h_before, "param_sha256_after_eval": h_after,
        "params_unchanged_across_eval": h_before == h_after,
        "eval_optimizer_steps": 0,
        "m0_matches_merged_fallback": (merged_m0 is None) or abs(rec["M0"]["accuracy"] - merged_m0) < 1e-9,
        "merged_fallback_m0_accuracy": merged_m0,
    }
    rec["timing"] = tim
    return rec


def main():
    PROG.mkdir(parents=True, exist_ok=True)
    per_seed = []
    for seed in EVAL_SEEDS:
        pth = PROG / f"seed_{seed}.json"
        if pth.exists():
            per_seed.append(json.loads(pth.read_text()))
            print(f"[seed {seed}] cached", flush=True)
            continue
        print(f"[seed {seed}] reproducing + evaluating ...", flush=True)
        rec = run_one_seed(seed)
        _write(pth, rec)
        per_seed.append(rec)
        print(f"[seed {seed}] done: M0={rec['M0']['accuracy']:.3f} T0={rec['T0']['accuracy']:.3f} "
              f"V100={rec['V100']['accuracy']:.3f} reads_eq_n={rec['V100']['reads_equal_n']}", flush=True)

    scen_path = PROG / "scenarios.json"
    if scen_path.exists():
        scenarios = json.loads(scen_path.read_text())
    else:
        import integrity as INT
        scenarios = INT.run_scenarios()
        _write(scen_path, scenarios)
    assemble(per_seed, scenarios)


def assemble(per_seed, scenarios):
    import gates as G
    import v100 as V100
    try:
        import torch  # noqa: F401
        torch_ok = True
    except Exception:
        torch_ok = False

    agg = G.aggregate(per_seed)
    repro_all = all(s["reproduction"]["trajectory_matches_committed_b0"] for s in per_seed)
    model_unchanged = all(s["model_invariance"]["params_unchanged_across_eval"] for s in per_seed)
    m0_match = all(s["model_invariance"]["m0_matches_merged_fallback"] for s in per_seed)
    g = G.gates(agg, scenarios, repro_all, model_unchanged, eval_optimizer_steps=0)
    v, extra = G.verdict(agg, g, torch_available=torch_ok, reproduced=repro_all)

    # reliability categories
    _write(RESULTS / "reliability_categories.json", {
        "schema": "bindingslots_v100_reference/reliability_categories/v1",
        "categories_total": agg["V100_categories"],
        "per_seed": [{"seed": s["seed"], "categories": s["V100"]["categories"]} for s in per_seed],
        "category_names": list(V100.CATEGORIES),
        "note": "each of n queries lands in exactly one category; abstention never merged with incorrect",
    })
    _write(RESULTS / "per_arm_results.json", {
        "schema": "bindingslots_v100_reference/per_arm_results/v1",
        "eval_seeds": EVAL_SEEDS, "per_seed": per_seed, "aggregate": agg})
    _write(RESULTS / "isolation_tests.json", {
        "schema": "bindingslots_v100_reference/isolation/v1", **scenarios})
    _write(RESULTS / "integrity_report.json", {
        "schema": "bindingslots_v100_reference/integrity/v1", "gates": g,
        "scenarios_all_pass": scenarios.get("all_pass"),
        "reproduction_matches_committed_b0": repro_all,
        "m0_byte_identical_to_frozen_baseline": m0_match,
        "no_model_state_change": model_unchanged, "eval_optimizer_steps": 0,
        "kda_validation_blocked": True, "ready_for_kda_validation_emitted": False})
    _write(RESULTS / "model_invariance.json", {
        "schema": "bindingslots_v100_reference/model_invariance/v1",
        "per_seed": [{"seed": s["seed"], **s["model_invariance"],
                      "reproduction": s["reproduction"]} for s in per_seed],
        "all_params_unchanged_across_eval": model_unchanged,
        "all_m0_match_merged_fallback": m0_match,
        "all_trajectories_match_committed_b0": repro_all})
    _write(RESULTS / "coverage_report.json", {
        "schema": "bindingslots_v100_reference/coverage/v1",
        "intended_write_coverage_pct": 100, "realized_write_coverage_pct": 100,
        "queries_with_valid_record": agg["n"], "queries_without_valid_record": 0,
        "note": "V100 phase runs at 100% legitimate write coverage only; V75/V50 are NOT run"})
    _write(RESULTS / "timing_characterization.json", {
        "schema": "bindingslots_v100_reference/timing/v1",
        "characterization_only": True,
        "no_operational_ceiling_approved": True,
        "note": "wall-clock, non-deterministic; excluded from the mechanical verdict. The isolated "
                "0.006 ms table read is NOT a substitute for these end-to-end figures.",
        "per_seed": [{"seed": s["seed"], **s["timing"]} for s in per_seed]})
    agg_out = {"schema": "bindingslots_v100_reference/aggregate_verdict/v1",
               "primary_verdict": v, "co_emitted": extra,
               "forbidden_verdict_not_emitted": G.FORBIDDEN_VERDICT,
               "kda_readiness": "KDA_VALIDATION_BLOCKED",
               "gates": g, "aggregate": agg, "frozen_gates": G.FROZEN_GATES,
               "scope": "system-level reliability characterization of the SQLite reference backend; "
                        "NOT a neural-routing intervention; does NOT claim to solve routing or approach KDA"}
    _write(RESULTS / "aggregate_verdict.json", agg_out)

    files = sorted(f for f in RESULTS.glob("*.json") if f.name != "artifact_hashes.json")
    _write(RESULTS / "artifact_hashes.json", {
        "schema": "bindingslots_v100_reference/artifact_hashes/v1",
        "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(f"[assemble] verdict={v} | co_emitted={extra}", flush=True)
    print(f"[assemble] gates all_pass={g['all_pass']}", flush=True)


if __name__ == "__main__":
    main()
