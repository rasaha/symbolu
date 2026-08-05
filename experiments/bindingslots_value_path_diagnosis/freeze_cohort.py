#!/usr/bin/env python3
"""Freeze the value-path/gradient diagnostic cohort MECHANICALLY from the merged persistence ledger.

Reads only committed evidence (results/seeds/<arm>/seed_<seed>/seed_classification.json and
raw_record.json from experiments/bindingslots_persistence). Selects the frozen cohort required by
the phase spec (§5) and writes cohort.json. This selection is committed BEFORE any newly captured
tensor is inspected. No seed is added or replaced based on any diagnostic outcome.

Torch-free.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PERS = REPO / "experiments" / "bindingslots_persistence"
SEEDS = PERS / "results" / "seeds"

# Provenance: which execution commit produced each arm's committed evidence (from the merged
# EXECUTION_REPORT / execution_authorization). A+, R0, O1R -> 5cc392e1; H2 -> 9380bdb1 (post the
# authorized H2 mask-fidelity correction). O1 was 9380bdb1 but O1 is not in the cohort.
SOURCE_EXECUTION_COMMIT = {
    "A+": "5cc392e1",
    "R0": "5cc392e1",
    "O1R": "5cc392e1",
    "H2": "9380bdb1",
}

# The frozen cohort: a symmetric 4-arm x 3-seed block that covers every §5-required exemplar.
# roles are documentary; membership is fixed here and never revised by diagnostics.
COHORT = [
    # arm, seed, role
    ("H2", 23, "principal_value_path_exemplar__routing_probe_vs_eval_dissociation"),
    ("H2", 24, "weak_clean_stable_former__control_interpretation"),
    ("H2", 25, "quality_failure__teacher_gradient_conflict_candidate"),
    ("O1R", 23, "o1r_clean_stable_control__gradient_alignment_reference"),
    ("O1R", 24, "o1r_quality_failed"),
    ("O1R", 25, "o1r_quality_failed"),
    ("R0", 23, "r0_formed_then_collapsed_representative"),
    ("R0", 24, "r0_clean_stable_representative"),
    ("R0", 25, "r0_quality_failed_representative"),
    ("A+", 23, "same_seed_aplus_control_for_seed23_exemplars"),
    ("A+", 24, "same_seed_aplus_control_for_seed24_exemplars"),
    ("A+", 25, "same_seed_aplus_control_for_seed25_exemplars"),
]

# Capture checkpoints per §5. step 700 is only required for H2 seed 23 (the dissociation point);
# it is captured for all slot arms because the cadence already records it (proven non-invasive),
# but is REQUIRED evidence only where the spec asks.
CAPTURE_CHECKPOINTS = [600, 700, 900, 1200]
REQUIRED_700 = [("H2", 23)]


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build():
    members = []
    for arm, seed, role in COHORT:
        sd = SEEDS / arm / f"seed_{seed}"
        rr = json.loads((sd / "raw_record.json").read_text())
        sc_path = sd / "seed_classification.json"
        sc = json.loads(sc_path.read_text()) if sc_path.exists() else None
        nbd = rr.get("needle_by_dist", {})
        entry = {
            "arm": arm,
            "seed": seed,
            "role": role,
            "source_execution_commit": SOURCE_EXECUTION_COMMIT[arm],
            "committed_category": (sc or {}).get("category"),
            "committed_clean_stable": (sc or {}).get("clean_stable"),
            "committed_needle_by_dist": nbd,
            "committed_needle_d96_1200": nbd.get("96"),
            "committed_ppl": rr.get("ppl"),
            "committed_correct_slot_prob_1200": (sc or {}).get("correct_slot_prob_1200"),
            "committed_correct_slot_prob_step600": (sc or {}).get("correct_slot_prob_step600"),
            "committed_needle_step600": (sc or {}).get("needle_step600"),
            "committed_slots_off": (sc or {}).get("slots_off"),
            "committed_randomized_address": (sc or {}).get("randomized_address"),
            "committed_train_s": rr.get("train_s"),
            "raw_record_sha256": _sha_file(sd / "raw_record.json"),
            "seed_classification_sha256": _sha_file(sc_path) if sc_path.exists() else None,
            "capture_checkpoints": list(CAPTURE_CHECKPOINTS),
            "step700_required_evidence": [arm, seed] in [list(x) for x in REQUIRED_700],
        }
        members.append(entry)

    doc = {
        "schema": "bindingslots_value_path_diagnosis/cohort/v1",
        "frozen_before_tensor_inspection": True,
        "selection_rule": (
            "Symmetric 4-arm x 3-seed block {A+,R0,O1R,H2} x {23,24,25} recovered mechanically from "
            "the merged persistence ledger. Covers every §5-required exemplar: H2 s23 "
            "(routing-probe/eval-retrieval dissociation), H2 s24 (weak CLEAN_STABLE former), H2 s25 "
            "(quality failure), O1R quality-failed seeds (24,25) + O1R clean control (23), one R0 "
            "CLEAN_STABLE (24), one R0 FORMED_THEN_COLLAPSED (23), one R0 QUALITY_FAILED (25), and "
            "same-seed A+ controls (23,24,25) for the principal H2 and O1R exemplars."
        ),
        "seed_provenance": "seeds 23-25 are a strict subset of the merged persistence reserved seeds 23-27",
        "no_replacement_policy": "FORBIDDEN to add/replace/drop any cohort member based on diagnostic outcomes",
        "capture_checkpoints": list(CAPTURE_CHECKPOINTS),
        "step700_required_for": [list(x) for x in REQUIRED_700],
        "source_execution_commits": SOURCE_EXECUTION_COMMIT,
        "ledger_source": "experiments/bindingslots_persistence/results/seeds",
        "members": members,
    }
    return doc


if __name__ == "__main__":
    doc = build()
    (HERE / "cohort.json").write_text(json.dumps(doc, indent=2) + "\n")
    print(f"cohort frozen: {len(doc['members'])} runs")
    for m in doc["members"]:
        print(f"  {m['arm']:4} s{m['seed']}  {str(m['committed_category']):32} "
              f"ndl96={m['committed_needle_d96_1200']}  role={m['role']}")
