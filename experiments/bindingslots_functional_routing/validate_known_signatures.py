#!/usr/bin/env python3
"""Validate that the address-specific routing metrics reproduce the KNOWN signatures on the already-
committed confirmatory CR1 trajectories (seeds 13-17 from PR #1324). Diagnostic only: these seeds are
NOT used to select any intervention. Pure stdlib.

Expected (from PR #1324):
  clean+retained (15, 17): high correct-slot prob, low rank, strong margin, clean causal ablations
  impure  (16):            low correct-slot prob, poor rank, weak margin, randomized-address impurity
  collapsed (13, 14):      aggregate overlap stays high while endpoint retrieval is absent
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONF = REPO / "experiments" / "bindingslots_confirmatory" / "results" / "seeds"
RT = json.loads((HERE / "stable_classifier.json").read_text())["routing_metric_thresholds"]


def routing_at(rec, step):
    for t in rec.get("trajectory", []):
        if t["step"] == step:
            return t.get("routing", {}) or {}
    return {}


def needle_at(rec, step):
    for t in rec.get("trajectory", []):
        if t["step"] == step:
            return t.get("needle_d96")
    return None


def load(seed):
    p = CONF / f"CR1_seed{seed}.json"
    return json.loads(p.read_text()) if p.exists() else None


def main():
    out = {"schema": "bindingslots_functional_routing/known_signature_validation/v1",
           "source": "experiments/bindingslots_confirmatory/results/seeds (PR #1324)",
           "thresholds": RT, "seeds": {}, "diagnostic_only": True}
    checks, fails = 0, []
    for seed in (13, 14, 15, 16, 17):
        rec = load(seed)
        if rec is None:
            fails.append(f"missing committed CR1 seed {seed}")
            continue
        r = routing_at(rec, 1200)
        prob = r.get("read_prob_on_highest_write_slot")
        rank = r.get("rank_of_highest_write_slot_under_read")
        margin = r.get("address_logit_margin")
        overlap = r.get("write_read_overlap")
        endpoint = needle_at(rec, 1200)
        clean = (prob is not None and prob >= RT["correct_slot_probability_min"]
                 and rank <= RT["correct_slot_median_rank_max"]
                 and margin >= RT["correct_slot_address_margin_min"])
        out["seeds"][str(seed)] = {"needle_d96_1200": endpoint, "correct_slot_prob": prob,
                                   "correct_slot_rank": rank, "address_margin": margin,
                                   "aggregate_overlap": overlap, "routing_clean_by_thresholds": clean}
        # expected-signature assertions
        if seed in (15, 17):
            checks += 1
            if not clean:
                fails.append(f"seed {seed} expected routing-clean, got prob={prob} rank={rank} margin={margin}")
        if seed == 16:
            checks += 1
            if clean:
                fails.append(f"seed 16 expected routing-IMPURE, but passed thresholds")
        if seed in (13, 14):
            checks += 1
            if not (endpoint is not None and endpoint < 0.075 and overlap is not None and overlap >= 0.5):
                fails.append(f"seed {seed} expected collapse (endpoint<0.075 with overlap>=0.5), got endpoint={endpoint} overlap={overlap}")
    out["checks"] = checks
    out["failures"] = fails
    out["reproduces_known_signatures"] = len(fails) == 0
    print(json.dumps(out, indent=2))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "known_signature_validation.json").write_text(json.dumps(out, indent=2) + "\n")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
