#!/usr/bin/env python3
"""T1 four-arm evaluation scaffold. Pre-reg: docs/CG_TRAINING_CRS_MISTRAL_PREREG.md.

MANDATORY four arms:
  A: base Mistral                         B: base Mistral + C×R×S wrapper (validated baseline)
  C: crs-lora Mistral                     D: crs-lora Mistral + C×R×S wrapper
The key question is whether C/D add value BEYOND B — not just whether C beats A.

CPU-SAFE: `--dry-run` validates the arm config + emits the report skeleton with no generation. Actual
four-arm generation + scoring requires a GPU + the cu121 stack and reuses the SAME deterministic rubric/
audit as the validated eval (no new judge, no model-as-judge). Decision uses ONLY the pre-registered
labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARMS = {
    "A": {"model": "base", "wrapper": False},
    "B": {"model": "base", "wrapper": True},
    "C": {"model": "crs_lora", "wrapper": False},
    "D": {"model": "crs_lora", "wrapper": True},
}
METRICS = ("primary_frame_correct", "rejected_domain_avoidance", "secondary_overpromotion_rate",
           "rejected_domain_leak_rate", "factuality_preserved", "clarity_usefulness",
           "must_include_recall", "answer_length", "generalization_to_unseen_terms",
           "generalization_to_unseen_domains")
SLICES = ("high_conf_primary", "ambiguous", "rejected_trap", "unseen_term", "domain_conflict",
          "negative_control", "per_domain")
DECISIONS = ("CG_TRAINING_CRS_ADDS_VALUE", "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE",
             "CG_TRAINING_WRAPPER_STILL_BEST", "CG_TRAINING_DEGRADES_FACTUALITY",
             "CG_TRAINING_OVERFITS_FRAMES", "CG_TRAINING_INSUFFICIENT_DATA",
             "CG_TRAINING_ENV_UNAVAILABLE")


def decide(arm_metrics: dict, *, factuality_tol=0.02) -> tuple:
    """Apply the pre-registered §11 gate to per-arm metric dicts (each metric -> float). Returns
    (decision_label, reasons). Uses ONLY the pre-registered labels."""
    A, B, C, D = (arm_metrics.get(k) for k in ("A", "B", "C", "D"))
    if not all((A, B, C, D)):
        return "CG_TRAINING_INSUFFICIENT_DATA", {"reason": "missing arm metrics"}
    r = {}
    c_beats_a = (C["primary_frame_correct"] > A["primary_frame_correct"]
                 and C["rejected_domain_avoidance"] > A["rejected_domain_avoidance"])
    r["c_beats_a"] = c_beats_a
    if C["factuality_preserved"] < A["factuality_preserved"] - factuality_tol \
            or C["clarity_usefulness"] < A["clarity_usefulness"] - factuality_tol:
        return "CG_TRAINING_DEGRADES_FACTUALITY", r
    generalizes = (C.get("generalization_to_unseen_terms", 0) > A.get("generalization_to_unseen_terms", 0)
                   and C.get("generalization_to_unseen_domains", 0) >= A.get("generalization_to_unseen_domains", 0))
    r["generalizes"] = generalizes
    if c_beats_a and not generalizes:
        return "CG_TRAINING_OVERFITS_FRAMES", r
    # value beyond the validated wrapper B, and D not worse than B
    approaches_or_beats_b = any(C.get(m, 0) >= B.get(m, 0) for m in
                                ("primary_frame_correct", "rejected_domain_avoidance"))
    d_not_worse_than_b = (D["primary_frame_correct"] >= B["primary_frame_correct"] - factuality_tol
                          and D["rejected_domain_avoidance"] >= B["rejected_domain_avoidance"] - factuality_tol)
    r.update(approaches_or_beats_b=approaches_or_beats_b, d_not_worse_than_b=d_not_worse_than_b)
    if c_beats_a and generalizes and approaches_or_beats_b and d_not_worse_than_b:
        return "CG_TRAINING_CRS_ADDS_VALUE", r
    # B clearly best (C/D don't clear the beyond-wrapper bar)
    if B["primary_frame_correct"] >= max(C["primary_frame_correct"], D["primary_frame_correct"]):
        return "CG_TRAINING_WRAPPER_STILL_BEST", r
    return "CG_TRAINING_CRS_NO_INCREMENTAL_VALUE", r


def gpu_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:                                     # noqa: BLE001
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Four-arm C×R×S-LoRA evaluation (T1).")
    ap.add_argument("--data-dir", default="runs/cg_training/crs_sft")
    ap.add_argument("--lora", default="runs/cg_training/crs_lora")
    ap.add_argument("--base-model", default="mistralai/Mistral-7B-Instruct-v0.3")
    ap.add_argument("--out", default="runs/cg_training/crs_eval/four_arm_eval.json")
    ap.add_argument("--report", default="runs/cg_training/crs_eval/four_arm_eval.md")
    ap.add_argument("--execute", action="store_true", help="run real generation (needs GPU)")
    args = ap.parse_args(argv)

    test = Path(args.data_dir) / "test.jsonl"
    n_test = sum(1 for l in test.read_text().splitlines() if l.strip()) if test.exists() else 0
    skeleton = {"arms": ARMS, "metrics": list(METRICS), "slices": list(SLICES),
                "decision_labels": list(DECISIONS), "n_test": n_test,
                "rubric": "same deterministic rubric/audit as the validated eval (no new judge)"}

    if not args.execute or not gpu_available():
        skeleton["decision"] = "CG_TRAINING_ENV_UNAVAILABLE" if not gpu_available() else "dry_run"
        skeleton["note"] = ("DRY-RUN: four-arm config validated; real generation needs a GPU + cu121 "
                            "stack. No model loaded, no claim made.")
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(skeleton, indent=2))
        Path(args.report).write_text(
            "# Four-arm C×R×S-LoRA evaluation (T1) — DRY-RUN / ENV_UNAVAILABLE\n\n"
            f"- arms: {list(ARMS)}  ·  n_test: {n_test}\n- decision: {skeleton['decision']}\n"
            "- arms A/B/C/D and the §11 gate are wired; run with --execute on a GPU pod.\n")
        print(f"DECISION: {skeleton['decision']} (dry-run; wrote {args.out})")
        return 0

    raise SystemExit("real four-arm generation path runs on the pod; wire generation + reuse the "
                     "validated rubric/audit, then call decide(arm_metrics).")


if __name__ == "__main__":
    raise SystemExit(main())
