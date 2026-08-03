#!/usr/bin/env python3
"""Analyze slots_only_results.json -> S-A / S-A+ deltas, ablation collapse, and a verdict.

Pure stdlib (reads JSON). Reports EVERY seed (not just means). Emits the S-arm verdict per the
pre-registered decision rule.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics as st


def _needle96(rec):
    return rec["needle_by_dist"]["96"]


def verdict(res):
    arms = res["arms"]
    A = [_needle96(r) for r in arms["A"]]
    S = [_needle96(r) for r in arms["S"]]
    Ap = [_needle96(r) for r in arms.get("A+", [])]
    s_seed0 = arms["S"][0]
    abl = s_seed0.get("ablation", {})
    s0 = _needle96(s_seed0)
    s_minus_a = st.mean(S) - st.mean(A)
    s_minus_ap = st.mean(S) - (st.mean(Ap) if Ap else st.mean(A))
    # per-seed S must beat A somewhere; primary causal pattern on the forming seed (max-S seed)
    forming = max(range(len(S)), key=lambda i: S[i])
    forms = S[forming] > 0.20 and S[forming] - A[forming] > 0.10
    slots_off = abl.get("slots_off")
    rand_addr = abl.get("randomized_address")
    baseline = abl.get("baseline", s0)
    collapse = (slots_off is not None and baseline - slots_off >= 0.20)
    addr_reduces = (rand_addr is not None and rand_addr < max(0.15, baseline - 0.20))

    if forms and collapse and addr_reduces:
        v = "PROVISIONALLY_SUPPORTED (H1/H2/H3 met; H4 Phase-independence = YES)"
        ready = True
    elif forms:
        v = "WORKING_BUT_UNSTABLE (forms in a subset of seeds; ablation pattern incomplete)"
        ready = False
    else:
        v = "NOT_SUPPORTED (S does not exceed A at needle@d96 at this scale)"
        ready = False
    return {
        "A_needle96_per_seed": A, "S_needle96_per_seed": S, "Aplus_needle96_per_seed": Ap,
        "S_minus_A_mean": round(s_minus_a, 4), "S_minus_Aplus_mean": round(s_minus_ap, 4),
        "forming_seed_index": forming, "S_forming": S[forming] if S else None,
        "ablation_seed0": {"baseline": baseline, "slots_off": slots_off,
                            "randomized_address": rand_addr,
                            "shuffle_values": abl.get("shuffle_values"),
                            "write_gate_zero": abl.get("write_gate_zero"),
                            "slot_keys_randomized": abl.get("slot_keys_randomized")},
        "relational_means": {
            "binding_k2": round(st.mean([r["binding_by_k"]["2"] for r in arms["S"]]), 4),
            "supersession_current": round(st.mean([r["supersession"]["current_acc"] for r in arms["S"]]), 4),
            "source": round(st.mean([r["source"] for r in arms["S"]]), 4),
            "multihop": round(st.mean([r["multihop"] for r in arms["S"]]), 4),
        },
        "verdict": v,
        "ready_for_five_seed_validation": ready,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    p = pathlib.Path(args.results)
    if not p.exists():
        print(f"NOT_YET_RUN: {p} does not exist")
        return 0
    res = json.loads(p.read_text())
    v = verdict(res)
    print(json.dumps(v, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(v, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
