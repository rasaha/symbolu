#!/usr/bin/env python3
"""Stage 3: one bounded B0-vs-E1 go/no-go on the RESERVED final pool + reserved seeds. Refuses to run
unless protocol_lock.json says E1_PROTOCOL_LOCKED. Mechanical futility stop. Emits the frozen verdict.

Nothing frozen may change after the first reserved seed; this driver only reads the frozen config."""
from __future__ import annotations

import hashlib
import json
import pathlib

import config as C
import harness as H
import gates as G

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def _load(name):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    lock = _load("protocol_lock.json")
    protocol_ok = lock.get("result") == "E1_PROTOCOL_LOCKED"
    if not protocol_ok:
        print("REFUSING: protocol not locked ->", lock.get("result"), flush=True)
        _write("aggregate_verdict.json", {"schema": "bindingslots_e1/aggregate_verdict/v1",
               "primary_verdict": "EXPLICIT_KEY_PROTOCOL_VIOLATED",
               "co_emitted": ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "KDA_VALIDATION_BLOCKED"],
               "reason": "protocol_lock not E1_PROTOCOL_LOCKED"})
        return

    determinism_ok = bool(_load("determinism.json").get("determinism_ok"))
    leakage_ok = bool(_load("leakage_report.json").get("all_pass"))

    required = C.RESERVED_SEEDS_REQUIRED_TO_PASS
    total = len(C.RESERVED_SEEDS)
    per_seed = []
    n_pass = 0
    futility_stopped = False
    train_eps = C.build_train_episodes()
    for i, seed in enumerate(C.RESERVED_SEEDS):
        r = H.run_seed(seed, "final", train_eps=train_eps)
        per_seed.append(r)
        if r["gates"]["all_primary_pass"]:
            n_pass += 1
        remaining = total - (i + 1)
        print(f"[reserved seed {seed}] all_primary_pass={r['gates']['all_primary_pass']} "
              f"G1_addr={r['metrics']['G1_addr']:.3f} e2e={r['metrics']['G1_e2e']:.3f} "
              f"b0={r['metrics']['b0_G1_e2e']:.3f} nm_fa={r['metrics']['nomatch_false_accept']:.3f} "
              f"(pass {n_pass}/{i+1}, {remaining} left)", flush=True)
        # mechanical futility: if even all remaining passing cannot reach `required`, stop
        if n_pass + remaining < required:
            futility_stopped = True
            print(f"[futility] max possible {n_pass + remaining} < required {required}; stopping", flush=True)
            break

    v, extra = G.verdict(per_seed, determinism_ok, leakage_ok, protocol_ok, resource_ok=True)

    # persist evidence
    _write("per_seed_reserved.json", {"schema": "bindingslots_e1/per_seed_reserved/v1",
           "per_seed": [{"seed": r["seed"], "metrics": r["metrics"], "gates": r["gates"],
                         "e1_splits": r["e1_splits"], "b0_splits": r["b0_splits"],
                         "e1_param_sha256": r["e1_param_sha256"], "b0_param_sha256": r["b0_param_sha256"]}
                        for r in per_seed]})
    _write("reserved_eval.json", {"schema": "bindingslots_e1/reserved_eval/v1",
           "reserved_seeds": C.RESERVED_SEEDS, "required_to_pass": required,
           "seeds_passing_all_primary": n_pass, "futility_stopped": futility_stopped,
           "worst_seed_G1_addr": min(r["metrics"]["G1_addr"] for r in per_seed),
           "summary": [{"seed": r["seed"], "all_primary_pass": r["gates"]["all_primary_pass"],
                        "groups": r["gates"]["groups"],
                        "G1_addr": r["metrics"]["G1_addr"], "G1_e2e": r["metrics"]["G1_e2e"],
                        "b0_G1_e2e": r["metrics"]["b0_G1_e2e"],
                        "improvement_over_b0": r["metrics"]["improvement_over_b0"],
                        "nomatch_false_accept": r["metrics"]["nomatch_false_accept"],
                        "nomatch_recall": r["metrics"]["nomatch_recall"],
                        "nomatch_precision": r["metrics"]["nomatch_precision"],
                        "G7_addr": r["metrics"]["G7_addr"]} for r in per_seed]})
    agg = {"schema": "bindingslots_e1/aggregate_verdict/v1",
           "primary_verdict": v, "co_emitted": extra,
           "kda_readiness": "KDA_VALIDATION_BLOCKED",
           "seeds_passing_all_primary": n_pass, "required_to_pass": required,
           "futility_stopped": futility_stopped,
           "determinism_ok": determinism_ok, "leakage_ok": leakage_ok, "protocol_ok": protocol_ok,
           "frozen_gates": C.GATES,
           "scope": "capability probe; NOT a repair of anonymous BindingSlots; does NOT unblock KDA"}
    _write("aggregate_verdict.json", agg)

    files = sorted(f for f in RES.glob("*.json") if f.name != "artifact_hashes.json")
    _write("artifact_hashes.json", {"schema": "bindingslots_e1/artifact_hashes/v1",
           "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}})
    print(f"[verdict] {v} | co={extra} | pass {n_pass}/{total}", flush=True)


if __name__ == "__main__":
    main()
