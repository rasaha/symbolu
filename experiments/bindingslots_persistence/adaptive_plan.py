#!/usr/bin/env python3
"""Deterministic adaptive execution controller for the persistence phase (PLANNING ONLY — never trains).

Encodes the frozen amendment decision tree: mandatory A+/R0 reference block, candidate order
O1R -> H1 -> H2 with a second-failure futility stop and a five-completed-seed success requirement, an
O1 diagnostic branch only if all candidates fail, first-success-selects-and-stops, and machine-readable
skipped-run reason codes. It is a pure function of COMPLETED-SEED classifications, so it can never
early-stop a seed (it only ever sees whole-seed outcomes) and resumes deterministically.

A future, separately-authorized runner calls `next_action(...)`, executes exactly that one run through
step 1200, classifies it with the frozen classifier, appends the result, and repeats. This module
contains NO training code; `main` only prints dry-run schedules for hypothetical outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
PLAN = json.loads((HERE / "adaptive_execution_plan.json").read_text())

SEEDS = [23, 24, 25, 26, 27]
REFERENCE = ["A+", "R0"]
CANDIDATES = ["O1R", "H1", "H2"]
DIAGNOSTIC = "O1"
NEED_CLEAN = 4          # >= 4/5
FUTILITY_FAILS = 2      # second non-CLEAN_STABLE seed => cannot reach 4/5


class ProtocolError(Exception):
    pass


def _validate_result(arm, seed, is_clean_stable):
    if arm not in REFERENCE + CANDIDATES + [DIAGNOSTIC]:
        raise ProtocolError(f"unknown arm {arm}")
    if seed not in SEEDS:
        raise ProtocolError(f"unknown seed {seed}")
    if not isinstance(is_clean_stable, bool):
        raise ProtocolError("is_clean_stable must be bool from the frozen classifier")


def _by_arm(completed, arm):
    """completed: ordered list of dicts {arm, seed, clean_stable}. Return this arm's records in
    the fixed seed order they were run (input order is assumed to be execution order)."""
    return [r for r in completed if r["arm"] == arm]


def _clean_count(completed, arm):
    return sum(1 for r in _by_arm(completed, arm) if r["clean_stable"])


def _fail_count(completed, arm):
    return sum(1 for r in _by_arm(completed, arm) if not r["clean_stable"])


def _done_seeds(completed, arm):
    return [r["seed"] for r in _by_arm(completed, arm)]


def _reference_complete(completed):
    return all(set(_done_seeds(completed, a)) >= set(SEEDS) for a in REFERENCE)


def _arm_futile(completed, arm):
    return _fail_count(completed, arm) >= FUTILITY_FAILS


def _arm_complete(completed, arm):
    return set(_done_seeds(completed, arm)) >= set(SEEDS)


def _arm_succeeds(completed, arm):
    """Success requires ALL FIVE completed, clean>=4/5, and clean > R0 clean (R0 must be complete)."""
    if not _arm_complete(completed, arm):
        return False
    if not _arm_complete(completed, "R0"):
        return False
    return _clean_count(completed, arm) >= NEED_CLEAN and _clean_count(completed, arm) > _clean_count(completed, "R0")


def _next_seed_for_arm(completed, arm):
    done = set(_done_seeds(completed, arm))
    for s in SEEDS:  # fixed order 23..27
        if s not in done:
            return s
    return None


def next_action(completed):
    """Return the single next run to execute, or a terminal decision. Pure/deterministic.

    completed: ordered list of {"arm","seed","clean_stable"} for FINISHED (through-step-1200) runs.
    """
    for r in completed:
        _validate_result(r["arm"], r["seed"], r["clean_stable"])

    # 1) mandatory reference block, A+ fully then R0 fully (A+ precedes R0 per same-seed requirement)
    for arm in REFERENCE:
        s = _next_seed_for_arm(completed, arm)
        if s is not None:
            # A+ must be complete before R0 begins (same-seed causal reference)
            if arm == "R0" and not _arm_complete(completed, "A+"):
                a = _next_seed_for_arm(completed, "A+")
                return {"action": "run", "arm": "A+", "seed": a}
            return {"action": "run", "arm": arm, "seed": s}

    # 2) candidate stages in fixed order
    for arm in CANDIDATES:
        if _arm_succeeds(completed, arm):
            return {"action": "terminate", "verdict": "FUNCTIONAL_ROUTING_PERSISTENCE_CANDIDATE_SELECTED",
                    "selected": arm, "kda_readiness": "KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION"}
        if _arm_futile(completed, arm):
            continue  # arm cannot reach 4/5 -> move to next candidate
        if _arm_complete(completed, arm):
            continue  # completed but did not pass the advancement gate -> next candidate
        # otherwise this arm still has seeds to run
        s = _next_seed_for_arm(completed, arm)
        return {"action": "run", "arm": arm, "seed": s}

    # 3) all candidates failed -> O1 diagnostic branch (not selectable)
    if not _arm_complete(completed, DIAGNOSTIC):
        s = _next_seed_for_arm(completed, DIAGNOSTIC)
        return {"action": "run", "arm": DIAGNOSTIC, "seed": s}

    return {"action": "terminate", "verdict": "NO_PERSISTENCE_INTERVENTION_SELECTED",
            "selected": None, "kda_readiness": "KDA_VALIDATION_BLOCKED"}


def full_status(completed):
    """Return every (arm, seed)'s status with a reason code, plus the terminal decision if reached."""
    # replay the plan to know which arm (if any) was selected and where futility hit
    selected = None
    terminal = None
    # discover terminal via a copy of the completed sequence
    term = next_action(completed)
    if term["action"] == "terminate":
        terminal = term
        selected = term.get("selected")

    status = {}
    # reference
    for arm in REFERENCE:
        for s in SEEDS:
            done = s in _done_seeds(completed, arm)
            status[f"{arm}:{s}"] = "COMPLETED" if done else "NOT_REACHED"

    ref_done = _reference_complete(completed)
    earlier_selected = False
    for arm in CANDIDATES:
        futile = _arm_futile(completed, arm)
        for s in SEEDS:
            key = f"{arm}:{s}"
            done = s in _done_seeds(completed, arm)
            if done:
                status[key] = "COMPLETED"
            elif not ref_done:
                status[key] = "NOT_REACHED"
            elif earlier_selected or (selected and CANDIDATES.index(arm) > (CANDIDATES.index(selected) if selected in CANDIDATES else -1)):
                status[key] = "EARLIER_CANDIDATE_SELECTED"
            elif futile:
                status[key] = "ARM_FUTILITY_REACHED"
            else:
                status[key] = "NOT_REACHED"
        if selected == arm:
            earlier_selected = True

    # diagnostic
    all_cand_failed = all((_arm_futile(completed, a) or (_arm_complete(completed, a) and not _arm_succeeds(completed, a))) for a in CANDIDATES)
    for s in SEEDS:
        key = f"{DIAGNOSTIC}:{s}"
        done = s in _done_seeds(completed, DIAGNOSTIC)
        if done:
            status[key] = "COMPLETED"
        elif selected in CANDIDATES:
            status[key] = "DIAGNOSTIC_NOT_REQUIRED"
        elif all_cand_failed and ref_done:
            status[key] = "NOT_REACHED"
        else:
            status[key] = "DIAGNOSTIC_NOT_REQUIRED" if (selected in CANDIDATES) else "NOT_REACHED"

    return {"terminal": terminal, "selected": selected,
            "run_count_so_far": len(completed), "status": status}


def simulate(oracle):
    """Dry-run: oracle(arm, seed) -> bool clean_stable. Returns the executed run sequence + terminal.
    PLANNING ONLY: no model is built, nothing is trained."""
    completed = []
    guard = 0
    while True:
        guard += 1
        if guard > 100:
            raise ProtocolError("planner did not converge")
        act = next_action(completed)
        if act["action"] == "terminate":
            return {"runs": completed, "terminal": act, "run_count": len(completed),
                    "full_status": full_status(completed)}
        cs = bool(oracle(act["arm"], act["seed"]))
        completed.append({"arm": act["arm"], "seed": act["seed"], "clean_stable": cs})


def plan_hash():
    return hashlib.sha256((HERE / "adaptive_execution_plan.json").read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="dry-run planner (never trains)")
    ap.add_argument("--scenario", default="o1r_pass",
                    help="o1r_pass | o1r_futile_h1_pass | all_fail | o1r_4of5_pass")
    args = ap.parse_args()

    scenarios = {
        # O1R clean on all 5 -> best case 15 runs
        "o1r_pass": lambda arm, seed: arm in ("A+",) and False or (arm == "R0" and seed in (23,)) or (arm == "O1R"),
        # O1R fails seeds 23,24 (futile) -> H1 clean 5/5
        "o1r_futile_h1_pass": lambda arm, seed: (arm == "O1R" and seed not in (23, 24)) or (arm == "H1") or (arm == "R0" and seed == 23),
        # everything fails -> O1 diagnostic runs
        "all_fail": lambda arm, seed: (arm == "R0" and seed == 23),
        # O1R clean on 4, fails 1 (seed 27) -> 4/5, beats R0(<=3) -> pass after 5 completed
        "o1r_4of5_pass": lambda arm, seed: (arm == "O1R" and seed != 27) or (arm == "R0" and seed == 23),
    }
    oracle = scenarios[args.scenario]
    res = simulate(oracle)
    print(json.dumps({"scenario": args.scenario, "run_count": res["run_count"],
                      "terminal": res["terminal"],
                      "runs": [f"{r['arm']}:{r['seed']}={'CS' if r['clean_stable'] else 'x'}" for r in res["runs"]]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
