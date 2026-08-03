#!/usr/bin/env python3
"""Torch-free preregistration integrity verifier for the BindingSlots confirmatory replication.

Verifies that every frozen artifact the confirmatory run depends on is byte-identical to the value
pinned in frozen_cr1_config.json / classifier.json, that the fresh-seed manifest is well-formed and
uncontaminated, and that no forbidden-architecture markers leak into the confirmatory harness.
Exit non-zero on any mismatch. Pure stdlib; safe to run in CI without torch.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# repo root = .../symbolu ; this file lives at experiments/bindingslots_confirmatory/
REPO = HERE.parents[1]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    checks = 0
    fails = []

    frozen = json.loads((HERE / "frozen_cr1_config.json").read_text())
    classifier = json.loads((HERE / "classifier.json").read_text())
    seeds = json.loads((HERE / "fresh_seeds.json").read_text())

    # 1. frozen code + config hashes
    for rel, want in frozen["frozen_code_hashes_sha256"].items():
        checks += 1
        p = REPO / rel
        if not p.exists():
            fails.append(f"missing frozen file {rel}")
            continue
        got = sha256(p)
        if got != want:
            fails.append(f"hash mismatch {rel}: want {want[:12]} got {got[:12]}")

    # 2. classifier inherits the frozen Stage B classifier unchanged
    checks += 1
    cls_path = REPO / classifier["inherited_from"]["file"]
    if sha256(cls_path) != classifier["inherited_from"]["sha256"]:
        fails.append("classify_stage_b.py sha256 changed vs frozen classifier")

    # 3. abc.json byte-stable
    checks += 1
    abc = REPO / "experiments/phase_lc/results/abc.json"
    if sha256(abc) != "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482":
        fails.append("frozen abc.json hash changed")

    # 4. fresh seeds well-formed + disjoint from all used training seeds
    checks += 1
    fs = seeds["confirmatory_seeds"]
    if fs != [13, 14, 15, 16, 17]:
        fails.append(f"confirmatory seeds are not [13..17]: {fs}")
    checks += 1
    if len(fs) != len(set(fs)):
        fails.append("duplicate confirmatory seed")
    checks += 1
    used = set(seeds["previously_used_bindingslots_training_seeds"]["union_all_training_seeds"])
    overlap = used & set(fs)
    if overlap:
        fails.append(f"confirmatory seed overlaps a used BindingSlots training seed: {sorted(overlap)}")

    # 5. arms + verdict enum are exactly the frozen set
    checks += 1
    if classifier["arms"] != ["A+", "B0", "CR1"]:
        fails.append(f"unexpected arms {classifier['arms']}")
    checks += 1
    verdicts = set(classifier["final_verdict_mapping"].keys())
    expected = {
        "REPLICATED_SLOT_FORMATION_STABILIZATION", "CONFIRMATORY_REPLICATION_FAILED",
        "CONFIRMATORY_PROTOCOL_VIOLATED", "CONFIRMATORY_INTEGRITY_FAILED",
        "CONFIRMATORY_ENVIRONMENT_MISMATCH", "CONFIRMATORY_RESOURCE_BLOCKED",
    }
    if verdicts != expected:
        fails.append(f"verdict enum mismatch: {verdicts ^ expected}")

    # 6. frozen thresholds unchanged vs merged Stage B constants
    checks += 1
    c = classifier["constants"]
    if not (c["CHANCE"] == 0.02 and c["FORM_MIN"] == 0.075 and c["FORM_MARGIN"] == 0.050
            and c["STAB_MEAN"] == 0.080 and c["STAB_MEDIAN"] == 0.050):
        fails.append("classifier constants deviate from frozen Stage B thresholds")

    # 7. CR1 config values frozen exactly
    checks += 1
    cand = frozen["candidate"]
    if not (cand["id"] == "CR1" and cand["curriculum"] is True and cand["alignment"] is True
            and cand["orthogonal_keys"] is False and cand["slot_lr"] == 0.002
            and cand["slot_warmup"] == 60 and cand["nonslot_lr"] == 0.002):
        fails.append("CR1 candidate config deviates from frozen selected candidate")
    checks += 1
    al = frozen["alignment"]
    if not (al["alignment_coefficient_peak"] == 0.10 and al["alignment_zero_point"] == 600):
        fails.append("alignment schedule deviates (peak 0.10, zero at 600)")
    checks += 1
    if frozen["curriculum"]["boundaries"] != [300, 700, 1200]:
        fails.append("curriculum boundaries deviate from [300,700,1200]")
    checks += 1
    if frozen["training"]["training_steps"] != 1200:
        fails.append("training step budget deviates from 1200")

    # 8. no forbidden-architecture tokens in the confirmatory harness sources
    forbidden = ["import Phase", "class KDA", "MultiLatentAttention", "quadratic_attention"]
    for src in ("run_confirmatory.py", "classify_confirmatory.py", "retention.py"):
        p = HERE / src
        if p.exists():
            checks += 1
            txt = p.read_text()
            hit = [t for t in forbidden if t in txt]
            if hit:
                fails.append(f"forbidden token(s) {hit} in {src}")

    print(f"confirmatory pre-registration integrity: {checks} checks, {len(fails)} failures")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
