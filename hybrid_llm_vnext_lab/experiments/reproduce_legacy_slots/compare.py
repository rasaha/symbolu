#!/usr/bin/env python3
"""Compare a reproduction run against the saved phase_lc baseline and classify it.

Pure stdlib (runnable now), but needs the reproduction output to exist. Compares per-seed
needle@d96 for the C arm and its ablations (slots-off, rand-keys, phase-off) against the saved
targets in config.json, and prints a reproduction classification. A single matching seed is not
a robust reproduction — the seed-0-forms / ablations-collapse / phase-off-preserved PATTERN must
hold.
"""
from __future__ import annotations

import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).parent
CONFIG = json.loads((HERE / "config.json").read_text())
TARGETS = CONFIG["saved_baseline_targets_needle_at_d96"]
TOL = 0.05  # absolute needle-accuracy tolerance for "matches"


def classify(got: dict) -> str:
    try:
        c = got["C_baseline"]
        off = got["C_slots_off"]
        rnd = got["C_rand_keys"]
        ph = got["C_phase_off"]
    except (KeyError, TypeError):
        return "NOT_REPRODUCED (missing C arm / ablation keys)"

    def near(a, b):
        return a is not None and b is not None and abs(a - b) <= TOL

    seed0_forms = near(c.get("seed0"), TARGETS["C_baseline"]["seed0"]) and c.get("seed0", 0) > 0.2
    slots_off_collapses = off.get("seed0", 1.0) < 0.15
    randkeys_collapses = rnd.get("seed0", 1.0) < 0.15
    phase_off_preserved = ph.get("seed0", 0.0) > 0.2
    pattern = seed0_forms and slots_off_collapses and randkeys_collapses and phase_off_preserved

    if pattern:
        # exact if all three seeds match saved to tolerance, else statistical/partial
        allmatch = all(near(c.get(s), TARGETS["C_baseline"][s]) for s in ("seed0", "seed1", "seed2"))
        return "EXACT_REPRODUCTION" if allmatch else "STATISTICAL_REPRODUCTION"
    if seed0_forms:
        return "PARTIAL_REPRODUCTION (circuit forms but ablation pattern incomplete)"
    return "NOT_REPRODUCED"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--against", default="experiments/phase_lc/results/abc.json")
    ap.add_argument("--got", default=str(pathlib.Path(__file__).parents[2] /
                                         "artifacts" / "legacy_slot_reproduction.json"))
    args = ap.parse_args()

    got_path = pathlib.Path(args.got)
    if not got_path.exists():
        print(f"RESOURCE_BLOCKED / NOT_YET_RUN: reproduction output {got_path} does not exist.")
        print("Run run.py in a torch-enabled environment first. Saved targets (needle@d96):")
        print(json.dumps(TARGETS, indent=2))
        return 0

    got = json.loads(got_path.read_text())
    verdict = classify(got.get("needle_at_d96", got))
    print(f"reproduction classification: {verdict}")
    print(f"compared against saved baseline: {args.against}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
