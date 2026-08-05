#!/usr/bin/env python3
"""Final confirmation cohort: refuses unless conf_protocol.json is frozen. Trains B0 + E1 (frozen C1
recipe) on the independent task per FINAL seed, evaluates all splits with the independent evaluator,
applies the same frozen gate structure, and emits the confirmation verdict."""
from __future__ import annotations

import hashlib
import json
import pathlib

import conf_task as T
import conf_config as C
import conf_train as TR
import conf_eval as EV
import conf_gates as G

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def run_seed(seed, train_eps):
    e1, _ = TR.train_e1(train_eps, seed)
    b0, _ = TR.train_b0(train_eps, seed)
    splits = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], C.EVAL_N_PER_SPLIT, seed_base=seed)
    e1_splits = {n: EV.eval_e1_split(e1, eps, C.TAU) for n, eps in splits.items()}
    b0_splits = {n: EV.eval_b0_split(b0, eps) for n, eps in splits.items()}
    m = G.collapse(e1_splits, b0_splits["G1_unseen_identity"]["e2e"])
    gates = G.eval_gates(m)
    return {"seed": seed, "metrics": m, "gates": gates,
            "e1_splits": e1_splits, "b0_splits": b0_splits,
            "e1_param_sha256": TR.param_hash(e1), "b0_param_sha256": TR.param_hash(b0)}


def main():
    proto = json.loads((RES / "conf_protocol.json").read_text()) if (RES / "conf_protocol.json").exists() else {}
    determinism_ok = bool((json.loads((RES / "determinism.json").read_text()) if (RES / "determinism.json").exists() else {}).get("determinism_ok"))
    leakage_ok = bool((json.loads((RES / "leakage_report.json").read_text()) if (RES / "leakage_report.json").exists() else {}).get("all_pass"))
    protocol_ok = bool(proto.get("frozen"))
    if not protocol_ok:
        print("REFUSING: protocol not frozen", flush=True)
        _write("aggregate_verdict.json", {"schema": "bindingslots_e1_confirmation/aggregate_verdict/v1",
               "primary_verdict": "E1_CONFIRMATION_PROTOCOL_VIOLATED",
               "co_emitted": G.ALWAYS, "reason": "conf_protocol not frozen"})
        return

    train_eps = C.build_train_episodes()
    per = []
    n_pass = 0
    required = C.RESERVED_SEEDS_REQUIRED_TO_PASS
    total = len(C.FINAL_SEEDS)
    for i, seed in enumerate(C.FINAL_SEEDS):
        r = run_seed(seed, train_eps)
        per.append(r)
        n_pass += int(r["gates"]["all_primary_pass"])
        remaining = total - (i + 1)
        print(f"[final seed {seed}] pass={r['gates']['all_primary_pass']} G1_addr={r['metrics']['G1_addr']:.3f} "
              f"e2e={r['metrics']['G1_e2e']:.3f} b0={r['metrics']['b0_G1_e2e']:.3f} "
              f"nm_fa={r['metrics']['nomatch_false_accept']:.3f} ({n_pass}/{i+1}, {remaining} left)", flush=True)
        if n_pass + remaining < required:
            print(f"[futility] {n_pass}+{remaining} < {required}; stopping", flush=True)
            break

    v, extra = G.verdict(per, determinism_ok, leakage_ok, protocol_ok)
    _write("per_seed.json", {"schema": "bindingslots_e1_confirmation/per_seed/v1",
           "per_seed": [{"seed": r["seed"], "metrics": r["metrics"], "gates": r["gates"],
                         "e1_splits": r["e1_splits"], "b0_splits": r["b0_splits"],
                         "e1_param_sha256": r["e1_param_sha256"]} for r in per]})
    _write("summary.json", {"schema": "bindingslots_e1_confirmation/summary/v1",
           "final_seeds": C.FINAL_SEEDS, "required_to_pass": required,
           "seeds_passing_all_primary": n_pass,
           "worst_seed_G1_addr": min(r["metrics"]["G1_addr"] for r in per),
           "mean_improvement_over_b0": sum(r["metrics"]["improvement_over_b0"] for r in per) / len(per),
           "per_seed": [{"seed": r["seed"], "all_primary_pass": r["gates"]["all_primary_pass"],
                         "groups": r["gates"]["groups"],
                         "G1_addr": r["metrics"]["G1_addr"], "G1_e2e": r["metrics"]["G1_e2e"],
                         "b0_G1_e2e": r["metrics"]["b0_G1_e2e"],
                         "improvement_over_b0": r["metrics"]["improvement_over_b0"],
                         "nomatch_false_accept": r["metrics"]["nomatch_false_accept"],
                         "nomatch_false_reject": r["metrics"]["G1_false_reject"],
                         "nomatch_recall": r["metrics"]["nomatch_recall"],
                         "G7_addr": r["metrics"]["G7_addr"]} for r in per]})
    _write("aggregate_verdict.json", {"schema": "bindingslots_e1_confirmation/aggregate_verdict/v1",
           "primary_verdict": v, "co_emitted": extra, "kda_readiness": "KDA_VALIDATION_BLOCKED",
           "seeds_passing_all_primary": n_pass, "required_to_pass": required,
           "determinism_ok": determinism_ok, "leakage_ok": leakage_ok, "protocol_ok": protocol_ok,
           "recipe": "frozen C1 (reused); independent task + evaluator + fresh seeds",
           "scope": "independent confirmation of the bundled controlled-task result; NOT a repair of "
                    "anonymous BindingSlots; does NOT unblock KDA"})
    files = sorted(f for f in RES.glob("*.json") if f.name != "artifact_hashes.json")
    _write("artifact_hashes.json", {"schema": "bindingslots_e1_confirmation/artifact_hashes/v1",
           "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(f"[verdict] {v} | co={extra} | pass {n_pass}/{total}", flush=True)


if __name__ == "__main__":
    main()
