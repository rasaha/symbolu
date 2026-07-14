#!/usr/bin/env python3
"""Part 3 — action-selection head-to-head on shared candidate sets.

Runs every selector (deterministic lexicographic / weighted-utility /
constrained-opt, plus the REAL BCVF port) on a fixed scenario suite and records
who each picks, whether the pick is hard-admissible, and whether the selector
can say NO_SAFE_ACTION. Writes ``results/action_scenarios.json``.

    python -m robotics_reliability_bench.run_action_scenarios
"""
from __future__ import annotations

import json
import os
from typing import Dict, List

from robotics_reliability_bench.action_baselines import (ALL_SELECTORS,
                                                         ActionCandidate,
                                                         Outcome, _hard_admissible)

RESULTS = os.path.join(os.path.dirname(__file__), "results")

# name, hard_safe, feasible, coll, stab, goal, cost, sf, sb
SCENARIOS: Dict[str, List[ActionCandidate]] = {
    # BCVF's "most consistent" pick is hard-unsafe (margin 0.05 < 0.20 floor).
    "unsafe_but_consistent_wins": [
        ActionCandidate("charge_through", False, True, 0.05, 0.5, 0.95, 0.2, 0.92, 0.90),
        ActionCandidate("safe_detour",    True,  True, 0.60, 0.6, 0.55, 0.6, 0.70, 0.55),
        ActionCandidate("emergency_stop", True,  True, 0.90, 0.9, 0.10, 0.1, 1.00, 0.30),
    ],
    # Every candidate is hard-unsafe -> deterministic must say NO_SAFE_ACTION.
    "all_candidates_unsafe": [
        ActionCandidate("dash_left",  False, True, 0.05, 0.4, 0.9, 0.3, 0.90, 0.88),
        ActionCandidate("dash_right", False, True, 0.08, 0.3, 0.8, 0.3, 0.85, 0.80),
        ActionCandidate("ram_ahead",  True,  False, 0.02, 0.2, 0.95, 0.5, 0.95, 0.92),
    ],
    # Emergency stop is the only safe option; its BCVF profile (sf=1,sb=0.2)
    # is worst-scored by the consistency term.
    "only_stop_is_safe": [
        ActionCandidate("weave",         False, True, 0.10, 0.5, 0.9, 0.2, 0.9, 0.85),
        ActionCandidate("emergency_stop", True, True, 0.95, 0.95, 0.15, 0.1, 1.0, 0.20),
    ],
    # A genuine tradeoff among safe actions (no safety issue) — selectors may
    # legitimately differ; recorded for transparency.
    "safe_tradeoff": [
        ActionCandidate("fast_route", True, True, 0.35, 0.5, 0.90, 0.7, 0.85, 0.80),
        ActionCandidate("slow_route", True, True, 0.80, 0.8, 0.60, 0.3, 0.70, 0.68),
    ],
}


def run() -> Dict:
    out: Dict = {"scenarios": {}}
    for scen, cands in SCENARIOS.items():
        rec = {"candidates": [c.name for c in cands],
               "admissible": [c.name for c in cands if _hard_admissible(c)],
               "selectors": {}}
        for sel in ALL_SELECTORS:
            s = sel.select(cands)
            picked_admissible = (s.outcome is Outcome.SELECTED
                                 and _hard_admissible(cands[s.index]))
            rec["selectors"][sel.name] = {
                "outcome": s.outcome.value,
                "pick": s.name,
                "pick_hard_admissible": (None if s.outcome is Outcome.NO_SAFE_ACTION
                                         else picked_admissible),
                "rationale": s.rationale,
            }
        out["scenarios"][scen] = rec
    # summary invariant: deterministic selectors NEVER pick a hard-inadmissible.
    det = ["Lexicographic", "WeightedUtility", "ConstrainedOpt"]
    violations = []
    for scen, rec in out["scenarios"].items():
        for name in det:
            r = rec["selectors"][name]
            if r["pick_hard_admissible"] is False:
                violations.append((scen, name))
        bc = rec["selectors"]["BCVF"]
        if bc["pick_hard_admissible"] is False:
            rec["bcvf_selected_unsafe"] = True
    out["deterministic_selected_unsafe_count"] = len(violations)
    out["deterministic_never_selects_unsafe"] = (len(violations) == 0)
    return out


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    for scen, rec in out["scenarios"].items():
        print(f"\n[{scen}]  admissible={rec['admissible']}")
        for name, r in rec["selectors"].items():
            adm = "" if r["pick_hard_admissible"] is None else f" admissible={r['pick_hard_admissible']}"
            print(f"    {name:16s} -> {r['outcome']:14s} pick={r['pick']}{adm}")
    print(f"\ndeterministic_never_selects_unsafe = {out['deterministic_never_selects_unsafe']}")
    path = os.path.join(RESULTS, "action_scenarios.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
