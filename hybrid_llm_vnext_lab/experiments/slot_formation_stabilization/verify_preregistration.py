#!/usr/bin/env python3
"""Pre-registration integrity verifier for the slot-formation-stabilization phase.

Fails (non-zero) if ANY of the following changed after pre-registration:
  * the pre-registration files (ACCEPTANCE_GATES / EXPERIMENT_MATRIX / SELECTION_RULE);
  * any frozen scientific input (frozen abc.json, five-seed results/classification, the S
    architecture source, the BindingSlots class, the task generator, the frozen five-seed gates);
  * the frozen scalar parameters (seeds, arms, LRs, warmups, curriculum boundaries, alignment
    lambda schedule + epsilon, formation threshold, Stage-B gates, readiness under provisional).

Pure stdlib. Run before any training and again before Stage B. Exit 0 = OK, 1 = drift.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parents[1]
REPO = LAB.parent
CH = json.loads((HERE / "CONFIG_HASHES.json").read_text())


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    fails = []
    checks = 0

    # 1. pre-registration files unchanged
    for name, want in CH["preregistration_files"].items():
        checks += 1
        got = _sha(HERE / name)
        if got != want:
            fails.append(f"pre-registration file changed: {name}\n  want {want}\n  got  {got}")

    # 2. frozen inputs unchanged
    for rel, want in CH["frozen_inputs"].items():
        checks += 1
        p = REPO / rel
        if not p.exists():
            fails.append(f"frozen input missing: {rel}")
            continue
        got = _sha(p)
        if got != want:
            fails.append(f"frozen input changed: {rel}\n  want {want}\n  got  {got}")

    # 3. frozen scalar parameters echoed into the matrix/gates still match
    mx = json.loads((HERE / "EXPERIMENT_MATRIX.json").read_text())
    gates = json.loads((HERE / "ACCEPTANCE_GATES.json").read_text())
    sp = CH["frozen_scalar_parameters"]

    def check(cond, msg):
        nonlocal checks
        checks += 1
        if not cond:
            fails.append(msg)

    check(mx["stage_a"]["diagnostic_seeds"] == sp["seeds_stage_a"], "stage A seeds drift")
    check(mx["stage_b"]["fresh_seeds"] == sp["seeds_stage_b"], "stage B seeds drift")
    check([a["id"] for a in mx["stage_a"]["arms"]] == sp["arms_stage_a"], "stage A arm list drift")
    check(mx["frozen_architecture"]["training_steps"] == sp["training_steps"], "training steps drift")
    arms = {a["id"]: a for a in mx["stage_a"]["arms"]}
    check(arms["O1"]["slot_lr"] == sp["O1_slot_lr"] and arms["O1"]["slot_warmup"] == sp["O1_slot_warmup"], "O1 schedule drift")
    check(arms["O2"]["slot_lr"] == sp["O2_slot_lr"] and arms["O2"]["slot_warmup"] == sp["O2_slot_warmup"], "O2 schedule drift")
    cur = mx["curriculum_C1"]
    check("1-300" in cur["phase_1_steps"] and "301-700" in cur["phase_2_steps"] and "701-1200" in cur["phase_3_steps"], "curriculum boundary drift")
    al = mx["alignment_R1"]["lambda_schedule"]
    check(al["steps_1_300"] == sp["alignment_lambda_start"], "alignment lambda start drift")
    check(al["steps_601_1200"] == 0.0, "alignment lambda must be 0 after step 600")
    check(mx["alignment_R1"]["objective"].startswith("label-free write-read overlap"), "alignment objective drift")
    fr = gates["formation_rule"]["all_required"]
    check(any("0.075" in x for x in fr) and any("0.050" in x for x in fr), "formation threshold drift")
    sb = gates["stage_b_gates"]["all_required"]
    check(any(">= 4 of 5" in x for x in sb), "stage B >=4/5 gate drift")
    check(gates["readiness_under_provisional"].startswith("PROVISIONALLY_STABILIZED STILL reports NOT_READY_FOR_KDA_VALIDATION"), "readiness-under-provisional drift")
    check(sp["readiness_under_provisional"] == "NOT_READY_FOR_KDA_VALIDATION", "readiness scalar drift")

    print(f"pre-registration integrity: {checks} checks, {len(fails)} failures")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
