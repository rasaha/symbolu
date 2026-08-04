#!/usr/bin/env python3
"""Torch-free pre-registration integrity verifier for the functional-routing development phase.

Verifies every frozen source the intervention runs through is byte-identical to the pinned value
(especially interventions.py and stabilize.py, which are swapped at RUNTIME but must be unchanged on
disk), that the fresh-seed manifest is well-formed and uncontaminated, that the training perturbation
is a distinct code path from the frozen randomized-address gate, and that no answer-label / frozen-gate
leakage exists in the objectives. Exit non-zero on any mismatch. Pure stdlib.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main() -> int:
    checks, fails = 0, []
    frozen = json.loads((HERE / "frozen_reference_config.json").read_text())
    cls = json.loads((HERE / "stable_classifier.json").read_text())
    seeds = json.loads((HERE / "stage1_seed_manifest.json").read_text())

    for rel, want in frozen["frozen_code_hashes_sha256"].items():
        checks += 1
        p = REPO / rel
        if not p.exists() or sha256(p) != want:
            fails.append(f"frozen hash mismatch/missing: {rel}")

    checks += 1
    if sha256(REPO / cls["inherited_from"]["file"]) != cls["inherited_from"]["sha256"]:
        fails.append("classify_stage_b.py changed vs frozen classifier")

    checks += 1
    if sha256(REPO / "experiments/phase_lc/results/abc.json") != "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482":
        fails.append("frozen abc.json changed")

    # seeds well-formed + uncontaminated
    s1 = seeds["stage1_seeds"]; s2 = seeds["stage2_reserved"]; s3 = seeds["confirmation_reserved"]
    checks += 1
    if s1 != [18, 19, 20, 21, 22]:
        fails.append(f"stage1 seeds not [18..22]: {s1}")
    checks += 1
    used = set(seeds["previously_used_bindingslots_training_seeds"])
    if used & (set(s1) | set(s2) | set(s3)):
        fails.append("reserved/stage seeds overlap a used BindingSlots training seed")
    checks += 1
    if len(set(s1)) != 5 or len(set(s1) | set(s2) | set(s3)) != 15:
        fails.append("duplicate or overlapping reserved seed sets")

    # arms + routing thresholds frozen
    checks += 1
    if cls["arms"] != ["R0", "O1", "O2", "H3"]:
        fails.append(f"unexpected classifier arms {cls['arms']}")
    checks += 1
    rt = cls["routing_metric_thresholds"]
    if not (rt["correct_slot_probability_min"] == 0.50 and rt["correct_slot_median_rank_max"] == 5
            and rt["correct_slot_address_margin_min"] == 3.0):
        fails.append("routing thresholds deviate")
    checks += 1
    fc = cls["frozen_constants"]
    if not (fc["FORM_MIN"] == 0.075 and fc["FORM_MARGIN"] == 0.050 and fc["CHANCE"] == 0.02):
        fails.append("frozen formation constants deviate")

    # training perturbation distinct from frozen randomized-address gate
    checks += 1
    cg = (HERE / "curriculum_gradual.py").read_text()
    obj = (HERE / "objectives.py").read_text()
    if "randomized_address" in cg or "randomized_address" in obj or "s_ablations" in obj:
        fails.append("training code references the frozen randomized-address gate (possible leakage)")

    # no answer-label leakage in objectives: strip comments/docstrings, then forbid concrete
    # supervision/evaluator code patterns; and require use of the captured address vectors only.
    checks += 1
    code_lines = []
    in_doc = False
    for ln in obj.splitlines():
        s = ln.strip()
        if s.startswith('"""') or s.startswith("'''"):
            in_doc = not in_doc if s.count('"""') % 2 or s.count("'''") % 2 else in_doc
            continue
        if in_doc or s.startswith("#"):
            continue
        code_lines.append(ln.split("#", 1)[0])
    code = "\n".join(code_lines)
    for bad in ("cross_entropy", "y_true", "s_ablations", '["y"]', "eval_suite", "make_eval_set"):
        if bad in code:
            fails.append(f"objectives.py code uses '{bad}' (possible label/evaluator leakage)")
    checks += 1
    if not ("_sfs_waddr" in code and "_sfs_raddr" in code):
        fails.append("objectives.py must read only the captured slot-address vectors (_sfs_waddr/_sfs_raddr)")

    # objectives must use stop-gradient target-slot selection
    checks += 1
    if obj.count(".detach().argmax") < 2:
        fails.append("objectives must select s* via stop-gradient argmax (w.detach().argmax) in O1 and O2")

    # R0 identity statement
    checks += 1
    if frozen["R0"]["run_mechanism"] != "frozen stabilize.run_arm('CR1', seed) with NO function swap":
        fails.append("R0 is not the unswapped frozen CR1")

    print(f"functional-routing pre-registration integrity: {checks} checks, {len(fails)} failures")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
