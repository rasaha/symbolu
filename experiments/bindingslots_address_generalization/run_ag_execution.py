#!/usr/bin/env python3
"""Execution driver for the address-generalization / gradient-isolation phase.

Order (§6/§14): A+ x5, B0 x5 (references, all seeds), then A1 and G1 as selectable arms with
second-failure futility, then AG only if A1 and G1 both pass their mechanism gates. Resumable:
per-run results are written atomically to results/_progress/ and completed runs are skipped. The
verdict reconstructs mechanically from committed evidence via ag_classify.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "results"
PROG = RESULTS / "_progress"
sys.path.insert(0, str(HERE))

import ag_classify as AC          # noqa: E402
import ag_meta as META            # noqa: E402

SEEDS = [28, 29, 30, 31, 32]
CORE_FIELDS = ("arm", "seed", "needle_by_dist", "ppl", "binding_by_k", "supersession", "source",
               "multihop", "trajectory", "eval_time_routing", "grad_behaviour", "g1_log", "a1_log",
               "g1_negative_cosine_updates", "h2_teacher_hash", "train_s", "ablation")


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    tmp.replace(path)


def _run(arm, seed):
    import arms_ag as A
    rec = A.run_arm(arm, seed)
    return {k: rec[k] for k in CORE_FIELDS if k in rec} | {"config_arm": arm, "config_seed": seed}


def _load(arm, seed):
    p = PROG / f"{arm.replace('+', 'plus')}_{seed}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _do(arm, seed):
    cached = _load(arm, seed)
    if cached is not None:
        print(f"[skip] {arm} s{seed}", flush=True)
        return cached
    print(f"[run ] {arm} s{seed} ...", flush=True)
    t = time.time()
    out = _run(arm, seed)
    _write(PROG / f"{arm.replace('+', 'plus')}_{seed}.json", out)
    print(f"[done] {arm} s{seed} ({round(time.time() - t, 1)}s)", flush=True)
    return out


def main():
    PROG.mkdir(parents=True, exist_ok=True)
    aplus, b0 = {}, {}
    for s in SEEDS:
        aplus[s] = _do("A+", s)
    for s in SEEDS:
        b0[s] = _do("B0", s)
    aplus_by = {s: aplus[s] for s in SEEDS}
    b0_by = {s: b0[s] for s in SEEDS}

    # selectable arms with second-failure futility
    def run_selectable(arm):
        recs = {}
        for s in SEEDS:
            recs[s] = _do(arm, s)
            rows_so_far = AC.seed_rows(arm, recs, b0_by, aplus_by)
            if AC.arm_futile(rows_so_far) and len(recs) < len(SEEDS):
                print(f"[futile] {arm} after {len(recs)} seeds", flush=True)
                break
        return recs

    a1 = run_selectable("A1")
    g1 = run_selectable("G1")

    a1_rows = AC.seed_rows("A1", a1, b0_by, aplus_by)
    g1_rows = AC.seed_rows("G1", g1, b0_by, aplus_by)
    leakage_ok = _leakage_ok()
    a1_pass, a1_conds = AC.a1_gate(a1_rows, leakage_ok) if len(a1) == len(SEEDS) else (False, {"incomplete": True})
    g1_pass, g1_conds = AC.g1_gate(g1_rows) if len(g1) == len(SEEDS) else (False, {"incomplete": True})

    ag, ag_rows, ag_pass, ag_conds, ag_ran = {}, [], False, {}, False
    if a1_pass and g1_pass:
        ag_ran = True
        for s in SEEDS:
            ag[s] = _do("AG", s)
            rows_so_far = AC.seed_rows("AG", ag, b0_by, aplus_by)
            if AC.arm_futile(rows_so_far) and len(ag) < len(SEEDS):
                print(f"[futile] AG after {len(ag)} seeds", flush=True)
                break
        ag_rows = AC.seed_rows("AG", ag, b0_by, aplus_by)
        ag_pass, ag_conds = AC.ag_gate(ag_rows) if len(ag) == len(SEEDS) else (False, {"incomplete": True})

    verdict = AC.verdict(a1_pass, g1_pass, ag_ran, ag_pass)
    assemble(aplus_by, b0_by, a1_rows, g1_rows, ag_rows, a1_pass, a1_conds, g1_pass, g1_conds,
             ag_ran, ag_pass, ag_conds, verdict, leakage_ok)


def _leakage_ok():
    train = set(map(tuple, META.QUERY_TEMPLATES["train"])) | set(map(tuple, META.QUERY_TEMPLATES["dev"]))
    test = set(map(tuple, META.QUERY_TEMPLATES["test"]))
    return test.isdisjoint(train)


def _strip_rows(rows):
    """Drop bulky nested dicts for the compact ledger."""
    keep = ("arm", "seed", "quality_qualified", "clean_stable", "eval_prob", "eval_top1",
            "ordinary_needle", "oracle_needle", "prob_delta_vs_b0", "top1_delta_vs_b0",
            "approaches_oracle", "needle_noninf_vs_b0", "prob_noninf_vs_b0",
            "wak_cos_teacher_window", "b0_wak_cos_teacher_window", "g1_negative_cosine_updates")
    return [{k: r.get(k) for k in keep} for r in rows]


def assemble(aplus_by, b0_by, a1_rows, g1_rows, ag_rows, a1_pass, a1_conds, g1_pass, g1_conds,
             ag_ran, ag_pass, ag_conds, verdict, leakage_ok):
    kda = "KDA_VALIDATION_BLOCKED"
    selected = verdict in ("JOINT_BINDINGSLOTS_INTERVENTION_CANDIDATE_SELECTED",
                           "READ_ADDRESS_GENERALIZATION_CANDIDATE_SELECTED",
                           "ROUTING_GRADIENT_ISOLATION_CANDIDATE_SELECTED")
    agg = {
        "schema": "bindingslots_address_generalization/aggregate_conclusion/v1",
        "primary_verdict": verdict,
        "kda_readiness": kda,
        "independent_confirmation_required": selected,
        "ready_for_kda_validation": False,
        "seeds": SEEDS,
        "a1": {"pass": a1_pass, "conditions": a1_conds, "rows": _strip_rows(a1_rows)},
        "g1": {"pass": g1_pass, "conditions": g1_conds, "rows": _strip_rows(g1_rows)},
        "ag": {"ran": ag_ran, "pass": ag_pass, "conditions": ag_conds, "rows": _strip_rows(ag_rows)},
        "leakage_ok": leakage_ok,
        "frozen_thresholds": AC.FROZEN_THRESHOLDS,
        "next_phase_mapping": _next_phase(a1_pass, g1_pass, ag_ran, ag_pass),
        "scope": "intervention-development only; candidates require independent confirmation; KDA blocked",
    }
    _write(RESULTS / "aggregate_verdict.json", agg)
    _write(RESULTS / "paired_comparisons.json", {
        "schema": "bindingslots_address_generalization/paired_comparisons/v1",
        "A1_vs_B0": _strip_rows(a1_rows), "G1_vs_B0": _strip_rows(g1_rows),
        "AG_vs_B0": _strip_rows(ag_rows)})
    print(f"[assemble] verdict={verdict} | {kda}", flush=True)


def _next_phase(a1, g1, ag_ran, ag_pass):
    if a1 and not g1:
        return "confirm read-address generalization independently"
    if g1 and not a1:
        return "refine read-address generalization separately; do not combine mechanisms"
    if a1 and g1 and ag_ran and ag_pass:
        return "untouched joint confirmation"
    if a1 and g1 and ag_ran and not ag_pass:
        return "interaction-mechanism diagnosis"
    if a1 and g1 and not ag_ran:
        return "run/confirm the joint arm"
    return "controlled intervention redesign based on the failed mechanism gates"


if __name__ == "__main__":
    main()
