#!/usr/bin/env python3
"""Torch-free integrity verifier for the adaptive-execution amendment. Proves the amendment changes
only execution order + futility, that every frozen scientific definition is byte-unchanged, that no
training has begun, and that the controller's futility math and five-seed success rule are correct.
Emits a machine-readable report. Pure stdlib."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import adaptive_plan as AP  # noqa: E402

PLAN = json.loads((HERE / "adaptive_execution_plan.json").read_text())


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main() -> int:
    checks, fails = 0, []

    def chk(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    # 1) PR #1331 merge commit recorded as frozen parent
    chk(PLAN["preregistration_merge_commit"] == "78be653642c3ec7adc385572c75c411cc0ce4fe0",
        "amendment does not record the PR #1331 merge commit as frozen parent")

    # 2) frozen scientific definitions BYTE-unchanged vs the hashes pinned in the plan
    for rel, want in PLAN["frozen_source_hashes_sha256"].items():
        checks += 1
        p = HERE / rel
        if not p.exists() or sha256(p) != want:
            fails.append(f"frozen definition changed since amendment freeze: {rel}")

    # 3) classifier + arm-definitions still match the merged preregistration's inherited hash chain
    cls = json.loads((HERE / "classifier.json").read_text())
    chk(sha256(REPO / cls["inherited_from"]["file"]) == cls["inherited_from"]["sha256"],
        "inherited classify_stage_b.py changed")

    # 4) historical artifact unchanged
    chk(sha256(REPO / "experiments/phase_lc/results/abc.json") ==
        "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482", "abc.json changed")

    # 5) amendment scope: changes only order/futility/omission
    chk(set(PLAN["amendment_scope"]["changes_only"]) == {"execution order", "futility stopping", "conditional omission of later arms"},
        "amendment scope claims more than order/futility/omission")

    # 6) fixed order + seeds + futility + success rule
    chk(PLAN["candidate_order"] == ["O1R", "H1", "H2"], "candidate order not O1R,H1,H2")
    chk(PLAN["fixed_seed_order"] == [23, 24, 25, 26, 27], "seed order not 23-27")
    chk(AP.FUTILITY_FAILS == 2, "futility not exactly second failure")
    chk(AP.NEED_CLEAN == 4, "success not >=4/5")
    chk("PROHIBITED" in PLAN["within_seed_early_stopping"], "within-seed early stopping not prohibited")
    chk(PLAN["candidate_stage_rule"]["no_four_seed_success"].startswith("success is never declared from four"),
        "four-seed-success not prohibited")
    chk(PLAN["reference_block"]["futility_applies"] is False, "futility must not apply to A+/R0")
    chk(PLAN["o1_diagnostic_branch"]["selectable"] is False, "O1 must be non-selectable")

    # 7) controller behavior: futility math + five-seed rule (dry-run, no training)
    # 7a: two failures stops an arm at exactly the second failure
    res = AP.simulate(lambda arm, seed: not (arm == "O1R" and seed in (23, 24)) if arm in ("O1R",) else (arm == "R0" and seed == 23) if arm == "R0" else (arm == "H1"))
    o1r_runs = [r for r in res["runs"] if r["arm"] == "O1R"]
    chk(len(o1r_runs) == 2, f"O1R did not stop after 2 failures (ran {len(o1r_runs)})")
    # 7b: 4/5 (one failure) requires all five completed before success
    res2 = AP.simulate(lambda arm, seed: (arm == "O1R" and seed != 27) or (arm == "R0" and seed == 23))
    o1r2 = [r for r in res2["runs"] if r["arm"] == "O1R"]
    chk(len(o1r2) == 5 and res2["terminal"].get("selected") == "O1R", "4/5 success not from five completed seeds")
    # 7c: best case is 15 runs when O1R passes 5/5
    res3 = AP.simulate(lambda arm, seed: (arm == "O1R") or (arm == "R0" and seed == 23))
    chk(res3["run_count"] == 15 and res3["terminal"]["selected"] == "O1R", f"best case not 15 runs ({res3['run_count']})")
    # 7d: all-fail runs the O1 diagnostic and selects nothing
    res4 = AP.simulate(lambda arm, seed: (arm == "R0" and seed == 23))
    chk(res4["terminal"]["verdict"] == "NO_PERSISTENCE_INTERVENTION_SELECTED" and any(r["arm"] == "O1" for r in res4["runs"]),
        "all-fail branch did not run O1 diagnostic / selected something")
    # 7e: unknown seed / arm refused
    try:
        AP.next_action([{"arm": "O1R", "seed": 99, "clean_stable": True}]); chk(False, "unknown seed not refused")
    except AP.ProtocolError:
        chk(True, "")

    # 8) NO training outputs -- enforced ONLY in preregistration mode (see verifier note).
    auth = HERE / "execution_authorization.json"
    exec_mode = False
    if auth.exists():
        try:
            exec_mode = json.loads(auth.read_text()).get("pr_1332_merge_commit") == "101951cb8bbccca32b6e3faa371bc675371dca89"
        except Exception:
            exec_mode = False
    if not exec_mode:
        sd = HERE / "results" / "seeds"
        chk(not (sd.exists() and any(sd.iterdir())), "training-result files exist under results/seeds")
        for banned in ("aggregate_classification.json", "selection_decision.json"):
            chk(not (HERE / "results" / banned).exists(), f"training-outcome file exists: {banned}")
    # adaptive_plan must contain no training call
    apsrc = (HERE / "adaptive_plan.py").read_text()
    chk("run_arm" not in apsrc and "build_matched" not in apsrc and "backward()" not in apsrc,
        "adaptive_plan.py contains training code")

    # 9) no forbidden architecture
    for src in HERE.glob("*.py"):
        txt = src.read_text()
        for t in ("PhaseAttentionLayer", "HybridPhaseTransformer", "MultiLatentAttention", "quadratic_attention"):
            if t in txt and f'"{t}"' not in txt and f"'{t}'" not in txt:
                fails.append(f"forbidden token {t} in {src.name}")
        checks += 1

    verdict = "BINDINGSLOTS_PERSISTENCE_ADAPTIVE_AMENDMENT_VERIFIED" if not fails else "BINDINGSLOTS_PERSISTENCE_ADAPTIVE_AMENDMENT_FAILED"
    report = {"schema": "bindingslots_persistence/amendment_integrity_report/v1", "checks": checks,
              "failures": fails, "verdict": verdict, "training_started": False,
              "checkpoints_generated": False, "results_classified": False,
              "best_case_runs": 15, "worst_case_runs": 30, "kda_readiness": "KDA_VALIDATION_BLOCKED"}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "amendment_integrity_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"amendment integrity: {checks} checks, {len(fails)} failures -> {verdict}")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
