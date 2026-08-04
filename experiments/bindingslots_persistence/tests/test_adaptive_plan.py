#!/usr/bin/env python3
"""Torch-free tests for the adaptive-execution amendment decision tree. Standalone or pytest."""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import adaptive_plan as AP  # noqa: E402

PLAN = json.loads((EXP / "adaptive_execution_plan.json").read_text())
SEEDS = [23, 24, 25, 26, 27]


def R(arm, seed, cs):
    return {"arm": arm, "seed": seed, "clean_stable": cs}


def ref_block(r0_clean_seeds=()):
    """A+ 5 (clean_stable irrelevant) + R0 5 with the given clean seeds."""
    out = [R("A+", s, False) for s in SEEDS]
    out += [R("R0", s, s in r0_clean_seeds) for s in SEEDS]
    return out


# ---------- reference stage ----------
def test_aplus_runs_all_five_first_and_before_r0():
    act = AP.next_action([])
    assert act == {"action": "run", "arm": "A+", "seed": 23}
    # after A+ 1-4, still A+
    comp = [R("A+", s, False) for s in (23, 24, 25, 26)]
    assert AP.next_action(comp)["arm"] == "A+" and AP.next_action(comp)["seed"] == 27
    # A+ complete -> R0 starts at 23
    comp = [R("A+", s, False) for s in SEEDS]
    assert AP.next_action(comp) == {"action": "run", "arm": "R0", "seed": 23}


def test_r0_runs_all_five_before_any_candidate():
    comp = [R("A+", s, False) for s in SEEDS] + [R("R0", s, True) for s in (23, 24, 25, 26)]
    assert AP.next_action(comp) == {"action": "run", "arm": "R0", "seed": 27}


# ---------- fixed order ----------
def test_o1r_precedes_h1_precedes_h2():
    comp = ref_block()
    assert AP.next_action(comp) == {"action": "run", "arm": "O1R", "seed": 23}
    # O1R futile (2 fails) -> H1
    comp2 = comp + [R("O1R", 23, False), R("O1R", 24, False)]
    assert AP.next_action(comp2)["arm"] == "H1"
    # H1 futile too -> H2
    comp3 = comp2 + [R("H1", 23, False), R("H1", 24, False)]
    assert AP.next_action(comp3)["arm"] == "H2"


def test_seed_order_always_23_to_27():
    comp = ref_block() + [R("O1R", 23, True)]
    assert AP.next_action(comp)["seed"] == 24


def test_o1_only_in_all_fail_branch():
    # all three candidates futile -> O1 runs
    comp = ref_block(r0_clean_seeds=(23,))
    for arm in ("O1R", "H1", "H2"):
        comp += [R(arm, 23, False), R(arm, 24, False)]
    assert AP.next_action(comp) == {"action": "run", "arm": "O1", "seed": 23}


# ---------- futility ----------
def test_futility_zero_and_one_failure_continue():
    comp = ref_block() + [R("O1R", 23, True), R("O1R", 24, False)]  # 1 failure
    assert AP.next_action(comp) == {"action": "run", "arm": "O1R", "seed": 25}


def test_futility_two_failures_stops_arm():
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", 23, False), R("O1R", 24, False)]
    nxt = AP.next_action(comp)
    assert nxt["arm"] != "O1R"  # O1R stopped
    st = AP.full_status(comp)["status"]
    assert st["O1R:25"] == "ARM_FUTILITY_REACHED" and st["O1R:27"] == "ARM_FUTILITY_REACHED"


def test_futile_arm_cannot_reach_4of5():
    # 2 failures => max clean = 3 < 4, mathematically cannot pass
    comp = ref_block() + [R("O1R", 23, False), R("O1R", 24, False)]
    assert not AP._arm_succeeds(comp, "O1R")


# ---------- success ----------
def test_four_successes_from_four_completed_does_not_pass():
    # only 4 O1R seeds completed (all clean) -> must run the 5th, not terminate
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", s, True) for s in (23, 24, 25, 26)]
    act = AP.next_action(comp)
    assert act == {"action": "run", "arm": "O1R", "seed": 27}  # NOT a terminate/select


def test_four_of_five_from_five_completed_may_pass():
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", s, s != 27) for s in SEEDS]  # 4 clean, 1 fail
    act = AP.next_action(comp)
    assert act["action"] == "terminate" and act["selected"] == "O1R"


def test_candidate_must_beat_r0():
    # O1R clean 4/5 but R0 also clean 4/5 -> not > R0 -> not selected
    comp = ref_block(r0_clean_seeds=(23, 24, 25, 26)) + [R("O1R", s, s != 27) for s in SEEDS]
    assert not AP._arm_succeeds(comp, "O1R")
    # controller moves on to H1
    assert AP.next_action(comp)["arm"] == "H1"


def test_quality_failure_blocks_success_via_clean_stable():
    # clean_stable already encodes quality/distance/causal; a non-clean seed reduces the count
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", s, s in (23, 24)) for s in SEEDS]  # 2 clean, 3 fail
    assert not AP._arm_succeeds(comp, "O1R")


def test_successful_earlier_candidate_skips_later_arms():
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", s, True) for s in SEEDS]
    term = AP.next_action(comp)
    assert term["action"] == "terminate" and term["selected"] == "O1R"
    st = AP.full_status(comp)["status"]
    assert st["H1:23"] == "EARLIER_CANDIDATE_SELECTED" and st["H2:27"] == "EARLIER_CANDIDATE_SELECTED"
    assert st["O1:23"] == "DIAGNOSTIC_NOT_REQUIRED"


# ---------- O1 branch ----------
def test_o1_not_selectable():
    assert PLAN["o1_diagnostic_branch"]["selectable"] is False
    # even if O1 all clean, verdict is NO_PERSISTENCE_INTERVENTION_SELECTED
    comp = ref_block(r0_clean_seeds=(23,))
    for arm in ("O1R", "H1", "H2"):
        comp += [R(arm, 23, False), R(arm, 24, False)]
    comp += [R("O1", s, True) for s in SEEDS]
    term = AP.next_action(comp)
    assert term["verdict"] == "NO_PERSISTENCE_INTERVENTION_SELECTED" and term["selected"] is None


def test_o1_does_not_run_after_candidate_success():
    comp = ref_block(r0_clean_seeds=(23,)) + [R("O1R", s, True) for s in SEEDS]
    assert AP.full_status(comp)["status"]["O1:23"] == "DIAGNOSTIC_NOT_REQUIRED"


# ---------- scope ----------
def test_no_training_or_results():
    # preregistration-mode invariant only; execution-authorized mode permits committed evidence
    auth = EXP / "execution_authorization.json"
    if auth.exists():
        try:
            if json.loads(auth.read_text()).get("pr_1332_merge_commit") == "101951cb8bbccca32b6e3faa371bc675371dca89":
                return
        except Exception:
            pass
    sd = EXP / "results" / "seeds"
    assert not (sd.exists() and any(sd.iterdir()))
    for banned in ("aggregate_classification.json", "selection_decision.json"):
        assert not (EXP / "results" / banned).exists()


def test_no_frozen_definition_changed():
    import hashlib
    for rel, want in PLAN["frozen_source_hashes_sha256"].items():
        assert hashlib.sha256((EXP / rel).read_bytes()).hexdigest() == want, rel


def test_controller_has_no_training_code():
    src = (EXP / "adaptive_plan.py").read_text()
    for bad in ("run_arm", "build_matched", "backward()", "opt.step"):
        assert bad not in src


def test_reason_codes_frozen():
    assert set(PLAN["skipped_run_reason_codes"]) == {
        "NOT_REACHED", "EARLIER_CANDIDATE_SELECTED", "ARM_FUTILITY_REACHED",
        "DIAGNOSTIC_NOT_REQUIRED", "COMPLETED", "INTERRUPTED_RESUMABLE",
        "INTEGRITY_FAILED", "RESOURCE_BLOCKED"}


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"adaptive-plan tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
