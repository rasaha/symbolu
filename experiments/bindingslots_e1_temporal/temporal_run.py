#!/usr/bin/env python3
"""Final temporal-transfer cohort: refuses unless the protocol is frozen. Trains B0 + E1 (frozen C1) per
final seed on identical episodes, evaluates all T1..T9 splits with the independent evaluator, applies the
frozen given gates, and emits the mechanical verdict. T5 is a reported diagnostic, never a gate."""
from __future__ import annotations

import hashlib
import json
import pathlib

import temporal_task as T
import temporal_config as C
import temporal_train as TR
import temporal_eval as EV
import temporal_gates as G

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def _load(name):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else {}


def run_seed(seed, train_eps):
    e1 = TR.train_e1(train_eps, seed)
    b0 = TR.train_b0(train_eps, seed)
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], C.EVAL_N_PER_SPLIT, seed_base=seed)
    e1_splits = {n: EV.eval_e1(e1, eps, C.TAU) for n, eps in splits.items()}
    b0_splits = {n: EV.eval_b0(b0, eps) for n, eps in splits.items()}
    m = G.collapse(e1_splits, b0_splits)
    gates = G.eval_gates(m)
    return {"seed": seed, "metrics": m, "gates": gates, "e1_splits": e1_splits, "b0_splits": b0_splits,
            "e1_param_sha256": TR.param_hash(e1)}


def main():
    proto = _load("temporal_protocol.json")
    protocol_ok = bool(proto.get("frozen"))
    determinism_ok = bool(_load("determinism.json").get("determinism_ok"))
    leakage_ok = bool(_load("leakage_report.json").get("all_pass"))
    if not protocol_ok:
        print("REFUSING: protocol not frozen", flush=True)
        _write("aggregate_verdict.json", {"schema": "bindingslots_e1_temporal/aggregate_verdict/v1",
               "primary_verdict": "E1_TEMPORAL_TRANSFER_PROTOCOL_VIOLATED", "co_emitted": G.ALWAYS})
        return

    train_eps = C.build_train_episodes()
    per = []
    for seed in C.FINAL_SEEDS:
        r = run_seed(seed, train_eps)
        per.append(r)
        mm = r["metrics"]
        print(f"[final {seed}] full_pass={r['gates']['all_primary_pass']} T3={mm['T3']:.3f} T4={mm['T4']:.3f} "
              f"T1={mm['T1']:.3f} T9={mm['T9']:.3f} nmFA={mm['nomatch_false_accept']:.3f} "
              f"imp={mm['improvement_over_b0']:.3f} T5diag={mm['T5_diagnostic']:.3f}", flush=True)

    v, extra = G.verdict(per, determinism_ok, leakage_ok, protocol_ok)
    full = sum(1 for s in per if s["gates"]["all_primary_pass"])

    _write("per_seed.json", {"schema": "bindingslots_e1_temporal/per_seed/v1",
           "per_seed": [{"seed": r["seed"], "metrics": r["metrics"], "gates": r["gates"],
                         "e1_splits": r["e1_splits"], "b0_splits": r["b0_splits"],
                         "e1_param_sha256": r["e1_param_sha256"]} for r in per]})
    _write("summary.json", {"schema": "bindingslots_e1_temporal/summary/v1",
           "final_seeds": C.FINAL_SEEDS, "required_to_pass": C.GATES["required_seeds_pass"],
           "seeds_full_pass": full,
           "worst_seed_min_T3T4": min(r["metrics"]["min_T3T4"] for r in per),
           "mean_improvement_over_b0": sum(r["metrics"]["improvement_over_b0"] for r in per) / len(per),
           "per_split_means": {k: sum(r["metrics"][k] for r in per) / len(per)
                               for k in ("T1", "T2", "T3", "T4", "T5_diagnostic", "T6", "T7", "T9",
                                         "nomatch_false_accept", "nomatch_false_reject", "nomatch_recall")},
           "per_seed": [{"seed": r["seed"], "all_primary_pass": r["gates"]["all_primary_pass"],
                         "groups": r["gates"]["groups"], "metrics": r["metrics"]} for r in per]})
    _write("aggregate_verdict.json", {"schema": "bindingslots_e1_temporal/aggregate_verdict/v1",
           "primary_verdict": v, "co_emitted": extra, "kda_readiness": "KDA_VALIDATION_BLOCKED",
           "seeds_full_pass": full, "required_to_pass": C.GATES["required_seeds_pass"],
           "determinism_ok": determinism_ok, "leakage_ok": leakage_ok, "protocol_ok": protocol_ok,
           "t5_diagnostic_only": True,
           "scope": "bounded structural-transfer test of the frozen C1 recipe to Temporal Event Memory; "
                    "T5 predecessor/successor is diagnostic; does NOT unblock KDA"})
    files = sorted(f for f in RES.glob("*.json") if f.name != "artifact_hashes.json")
    _write("artifact_hashes.json", {"schema": "bindingslots_e1_temporal/artifact_hashes/v1",
           "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(f"[verdict] {v} | co={extra} | full_pass {full}/{len(per)}", flush=True)


if __name__ == "__main__":
    main()
