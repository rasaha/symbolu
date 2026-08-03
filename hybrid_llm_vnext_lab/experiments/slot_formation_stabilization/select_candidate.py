#!/usr/bin/env python3
"""Apply the FROZEN candidate-selection rule (SELECTION_RULE.json) to Stage A eligibility.

Ranks eligible arms by: (k1) #seeds formed, (k2) #rescued non-formers, (k3) highest MIN per-seed
S-A+ margin, (k4) highest MEDIAN margin, (k5) lowest PPL, (k6) simplicity order O1|O2->K1->C1->R1
->CR1; ties -> lexicographically first arm id. No eligible arm -> NO_STABILIZATION_CANDIDATE.
NO manual override. Pure stdlib.
"""
from __future__ import annotations

import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SIMPLICITY = {"O1": 0, "O2": 0, "K1": 1, "C1": 2, "R1": 3, "CR1": 4}


def rank_key(sc):
    # all sort keys are "smaller is better" -> negate the maximize-terms
    return (
        -sc["n_forming"],
        -len(sc["rescued_nonformers"]),
        -sc["min_margin"],
        -sc["median_margin"],
        sc["ppl_mean_S256"],
        SIMPLICITY.get(sc["arm"], 99),
        sc["arm"],  # lexicographic final tie-break
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--classification", required=True)
    ap.add_argument("--out", default=str(HERE / "SELECTED_CANDIDATE.json"))
    args = ap.parse_args()

    cls = json.loads(pathlib.Path(args.classification).read_text())
    eligible = cls["eligible_arms"]
    per_arm = cls["per_arm"]

    trace = []
    if not eligible:
        result = {
            "selected": None,
            "classification": "NO_STABILIZATION_CANDIDATE",
            "reason": "No Stage A arm satisfied candidate eligibility (e1..e8).",
            "selection_trace": [{"arm": a, "eligible": per_arm[a].get("eligible", False),
                                 "eligibility": per_arm[a].get("eligibility")} for a in per_arm],
        }
        pathlib.Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0

    ranked = sorted((per_arm[a] for a in eligible), key=rank_key)
    for sc in ranked:
        trace.append({"arm": sc["arm"], "n_forming": sc["n_forming"],
                      "rescued": sc["rescued_nonformers"], "min_margin": sc["min_margin"],
                      "median_margin": sc["median_margin"], "ppl": sc["ppl_mean_S256"],
                      "simplicity_rank": SIMPLICITY.get(sc["arm"], 99), "sort_key": list(map(str, rank_key(sc)))})
    winner = ranked[0]
    tie = len(ranked) > 1 and rank_key(ranked[0])[:-1] == rank_key(ranked[1])[:-1]
    result = {
        "selected": winner["arm"],
        "classification": "CANDIDATE_SELECTED",
        "winner_scorecard": winner,
        "tie_detected": tie,
        "tie_note": "resolved by lexicographically-first arm id" if tie else "clear winner",
        "selection_trace": trace,
        "combination_prohibition": "single candidate only; no cross-family combination this phase.",
    }
    pathlib.Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
