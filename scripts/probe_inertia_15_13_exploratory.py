#!/usr/bin/env python
"""§15.13 exploratory analysis — refusal/confident-wrong subset AUCs.

EXPLORATORY ONLY. The §15.13 cascade verdict
NO_MATERIAL_SIGNAL_IN_INERTIA (committed at b817a98) STAYS BINDING.
This script's outputs are hypothesis-generating only; turning any
subset finding into a binding claim requires a fresh pre-committed
§0.X — not an amendment to §15.13.

Refusal labels here are **heuristic text-based labels** layered on
top of the primary §13.10-style correctness label and are NOT
equivalent to a prevalidated refusal benchmark.

What this script DOES:
  * Loads the §15.13 per-stimulus extraction cache (.npz) — no
    re-extraction, no model reload, no GPU required.
  * Re-derives R_inertia + R_sim per stimulus from the cached
    hidden states using the same _cosine_fp64 helper as §15.13.
  * Applies a pre-committed 3-way label on top of the §13.10
    binary y:
        CORRECT          y == 1
        REFUSAL          y == 0 AND
                            (response matches refusal markers,
                             OR len(response.strip()) < 8)
        CONFIDENT_WRONG  y == 0 AND not REFUSAL
  * Reports class counts BEFORE any AUC.
  * Computes pairwise AUC on subsets (only when each class has at
    least MIN_CLASS_SIZE_FOR_AUC = 10 stimuli):
        all_stimuli_sanity         — CORRECT vs (REFUSAL ∪ CONFIDENT_WRONG)
                                     (must reproduce §15.13's 0.6300)
        correct_vs_confident_wrong — drop refusals
        correct_vs_refusal         — drop confident-wrong
        confident_wrong_vs_refusal — neither class is correct
  * Writes JSON + firewall-scanned markdown to
    docs/experiments/probe_inertia_15_13_exploratory.{json,md}
    with an explicit non-amendment declaration in both.

What this script DOES NOT:
  * Apply the §15.13 cascade to any subset.
  * Modify probe_inertia_15_13.py or any §15.13 artifact.
  * Replace, override, or amend the §15.13 verdict-of-record.
  * Reuse any pre-committed §15.13 threshold as a binding gate
    (the cascade rule is §15.13-binding only).
  * Authorize a v2 follow-up; v2 requires a fresh §0.X.

Usage:
    python scripts/probe_inertia_15_13_exploratory.py --self-test
    python scripts/probe_inertia_15_13_exploratory.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


# ===========================================================================
# §15.13 exploratory pinned constants — pre-committed BEFORE any subset
# AUC is computed. Modifying these after seeing the data would corrupt the
# audit trail (HARKing). Any change requires a fresh §0.X commitment.
# ===========================================================================

# Imports from the primary §15.13 probe module. We reuse its data structures,
# cache I/O, cosine helper, and 44-pattern firewall verbatim — no
# re-implementation. The primary script is NOT modified by this script.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
from probe_inertia_15_13 import (  # noqa: E402
    BENCHMARK,
    CHANCE_BASELINE_AUC,
    CLASS_3_FORBIDDEN_PATTERNS,
    EXTRACTIONS_CACHE_PATH,
    PINNED_N,
    QWEN_MODEL_ID,
    SCHEMA_VERSION as PRIMARY_SCHEMA_VERSION,
    SchemaMismatchError,
    StimulusExtraction,
    StimulusFeatures,
    _cosine_fp64,
    compute_features_per_stimulus,
    enforce_firewall_or_exit,
    load_extractions_cache,
    scan_for_forbidden_patterns,
)


# Exploratory schema version — distinct from §15.13's "15.13" so the JSON
# output cannot be confused with the binding §15.13 artifact.
EXPLORATORY_SCHEMA_VERSION = "15.13.exploratory.v1"

# §15.13 verdict (verdict-of-record; this script does not alter it).
PRIMARY_VERDICT = "NO_MATERIAL_SIGNAL_IN_INERTIA"
PRIMARY_VERDICT_COMMIT = "b817a98"

# Pre-committed strict refusal markers. Case-insensitive substring match
# on the model's q_b_response_text. A y=0 stimulus matching ANY marker is
# classified as REFUSAL; otherwise CONFIDENT_WRONG.
REFUSAL_MARKERS: tuple[str, ...] = (
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "i can't",
    "i cannot",
    "i'm unable",
    "i am unable",
    "as an ai",
    "i don't have",
    "i do not have",
)

# Short-response refusal heuristic: only applied when y == 0. A genuinely
# correct short answer (e.g., "Paris") must NOT be classified as REFUSAL.
SHORT_RESPONSE_FLOOR_FOR_Y0 = 8  # len(response.strip()) < this → REFUSAL

# Minimum per-class size for any pairwise AUC. Below this, the subset
# is reported as INSUFFICIENT_N to avoid meaningless small-sample AUC.
MIN_CLASS_SIZE_FOR_AUC = 10

# Output paths.
OUTPUT_JSON_PATH = "docs/experiments/probe_inertia_15_13_exploratory.json"
OUTPUT_MD_PATH = "docs/experiments/probe_inertia_15_13_exploratory.md"

# Label class names (frozen).
LABEL_CORRECT = "CORRECT"
LABEL_REFUSAL = "REFUSAL"
LABEL_CONFIDENT_WRONG = "CONFIDENT_WRONG"

# Additional firewall patterns specific to this exploratory artifact —
# blocks accidental cascade-amendment language. These are layered on top
# of the §15.13 44-pattern Class-3 firewall.
EXPLORATORY_EXTRA_FIREWALL_PATTERNS: tuple[str, ...] = (
    "amends §15.13",
    "§15.13 should be PARTIAL",
    "subset AUC overrides the cascade",
    "the cascade rule should exclude refusals",
    "§15.13 verdict is overturned",
)

# Sanity invariants (also asserted at runtime).
assert len(REFUSAL_MARKERS) == 11, (
    f"REFUSAL_MARKERS pinned at 11 strict markers; got {len(REFUSAL_MARKERS)}"
)
assert SHORT_RESPONSE_FLOOR_FOR_Y0 == 8
assert MIN_CLASS_SIZE_FOR_AUC == 10
assert EXPLORATORY_SCHEMA_VERSION != PRIMARY_SCHEMA_VERSION


# ===========================================================================
# Pre-committed 3-way labeller.
# ===========================================================================


def classify_exploratory_label(extraction: StimulusExtraction) -> str:
    """Apply the pre-committed 3-way label to a single stimulus.

    Rules (PINNED — see module docstring; no post-hoc changes):
      CORRECT          y == 1                        (per §13.10 NLI scoring)
      REFUSAL          y == 0 AND
                       (len(response.strip()) < 8
                        OR response_lower contains a REFUSAL_MARKER)
      CONFIDENT_WRONG  y == 0 AND not REFUSAL

    The short-length rule is gated on y == 0 by design — a genuinely
    correct short answer (e.g., "Paris" answering "What is the capital
    of France?") must NOT be miscategorised as REFUSAL.
    """
    if extraction.y:
        return LABEL_CORRECT
    text = extraction.q_b_response_text or ""
    if len(text.strip()) < SHORT_RESPONSE_FLOOR_FOR_Y0:
        return LABEL_REFUSAL
    text_lower = text.lower()
    for marker in REFUSAL_MARKERS:
        if marker in text_lower:
            return LABEL_REFUSAL
    return LABEL_CONFIDENT_WRONG


def classify_all(
    extractions: tuple[StimulusExtraction, ...],
) -> tuple[str, ...]:
    """Vectorize classify_exploratory_label across all stimuli."""
    return tuple(classify_exploratory_label(e) for e in extractions)


def label_counts(labels: tuple[str, ...]) -> dict[str, int]:
    """Return {CORRECT, REFUSAL, CONFIDENT_WRONG, TOTAL} counts."""
    counts = {
        LABEL_CORRECT: 0,
        LABEL_REFUSAL: 0,
        LABEL_CONFIDENT_WRONG: 0,
    }
    for lbl in labels:
        if lbl in counts:
            counts[lbl] += 1
        else:
            raise RuntimeError(
                f"unexpected exploratory label {lbl!r}; "
                f"expected one of {set(counts.keys())}"
            )
    counts["TOTAL"] = len(labels)
    return counts


# ===========================================================================
# Pairwise AUC helper (tie-aware Mann-Whitney U). Pure numpy; matches
# sklearn's roc_auc_score on the same scores/labels. Used here instead of
# importing sklearn to keep this exploratory script CPU-only and dependency-
# light. The §15.13 primary probe still uses sklearn for its binding AUCs.
# ===========================================================================


def _auc_tieaware(scores: np.ndarray, labels: np.ndarray) -> float:
    """Tie-aware AUC = (#pos>neg + 0.5*#tie) / (n_pos*n_neg).

    Pos class: labels == 1; neg class: labels == 0. Returns NaN if
    either class is empty.
    """
    if scores.shape != labels.shape:
        raise ValueError(
            f"_auc_tieaware shape mismatch: scores={scores.shape} vs "
            f"labels={labels.shape}"
        )
    pos = scores[labels.astype(bool)]
    neg = scores[~labels.astype(bool)]
    n_pos, n_neg = int(pos.size), int(neg.size)
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    win = float((diff > 0).sum())
    tie = float((diff == 0).sum())
    return (win + 0.5 * tie) / float(n_pos * n_neg)


# ===========================================================================
# Per-subset AUC record + computation. Each subset is a binary
# classification: pos_class is the class that "should be ranked higher"
# under the BCVF-faithful direction (lower R_inertia → predicts pos_class).
# We negate the score so AUC > 0.5 means R_inertia separates pos from neg
# in the BCVF-faithful direction.
#
# Disclosure subsets (per spec sub-chunk):
#   1. all_stimuli_sanity        : CORRECT vs (REFUSAL ∪ CONFIDENT_WRONG)
#                                  (must reproduce §15.13's 0.6300)
#   2. correct_vs_confident_wrong: CORRECT vs CONFIDENT_WRONG
#                                  (drop refusals — does inertia separate
#                                   hallucinations from correct?)
#   3. correct_vs_refusal        : CORRECT vs REFUSAL
#                                  (drop confident-wrong — does inertia
#                                   separate refusals from correct?)
#   4. confident_wrong_vs_refusal: CONFIDENT_WRONG vs REFUSAL
#                                  (correct excluded — does inertia
#                                   distinguish the two failure modes?)
#
# Each subset is gated on MIN_CLASS_SIZE_FOR_AUC = 10 per class. Below
# that, the subset reports INSUFFICIENT_N rather than a small-sample AUC.
# ===========================================================================


@dataclass(frozen=True)
class SubsetSummary:
    """Per-subset AUC + class counts + R distribution (disclosure only).

    `eligible` flags whether the subset met the MIN_CLASS_SIZE_FOR_AUC
    floor on both classes; if False, AUC fields are NaN and `rationale`
    explains the gating.
    """

    name: str
    pos_label: str          # the "ranked-higher-by-low-R" class
    neg_label: str          # the comparator class
    n_pos: int
    n_neg: int
    eligible: bool
    auc_inertia: float      # AUC(-R_inertia, pos==1); NaN if not eligible
    auc_sim: float          # AUC(-R_sim,     pos==1); NaN if not eligible
    dauc_inertia_vs_chance: float
    dauc_inertia_vs_sim: float
    r_inertia_pos_mean: float
    r_inertia_pos_std: float
    r_inertia_neg_mean: float
    r_inertia_neg_std: float
    rationale: str          # "ELIGIBLE" or "INSUFFICIENT_N (...)"


def _label_in(label: str, allowed: tuple[str, ...]) -> bool:
    return label in allowed


def compute_subset_summary(
    name: str,
    pos_classes: tuple[str, ...],
    neg_classes: tuple[str, ...],
    features: tuple[StimulusFeatures, ...],
    labels: tuple[str, ...],
) -> SubsetSummary:
    """Build a SubsetSummary for the (pos vs neg) binary classification.

    `pos_classes` and `neg_classes` are tuples of label names so a "subset"
    can group multiple labels (e.g., the all-stimuli sanity check groups
    REFUSAL ∪ CONFIDENT_WRONG as the negative class).

    The score is `-feature.r_inertia` (BCVF-faithful direction: lower
    R_inertia predicts the positive class). `auc_sim` mirrors the §15.13
    cascade's comparator and uses `-feature.r_sim`.
    """
    pos_inertia: list[float] = []
    pos_sim: list[float] = []
    neg_inertia: list[float] = []
    neg_sim: list[float] = []
    for f, lbl in zip(features, labels):
        if _label_in(lbl, pos_classes):
            pos_inertia.append(float(f.r_inertia))
            pos_sim.append(float(f.r_sim))
        elif _label_in(lbl, neg_classes):
            neg_inertia.append(float(f.r_inertia))
            neg_sim.append(float(f.r_sim))
    n_pos, n_neg = len(pos_inertia), len(neg_inertia)
    pos_label = "+".join(pos_classes)
    neg_label = "+".join(neg_classes)

    if n_pos < MIN_CLASS_SIZE_FOR_AUC or n_neg < MIN_CLASS_SIZE_FOR_AUC:
        return SubsetSummary(
            name=name,
            pos_label=pos_label,
            neg_label=neg_label,
            n_pos=n_pos,
            n_neg=n_neg,
            eligible=False,
            auc_inertia=float("nan"),
            auc_sim=float("nan"),
            dauc_inertia_vs_chance=float("nan"),
            dauc_inertia_vs_sim=float("nan"),
            r_inertia_pos_mean=float("nan"),
            r_inertia_pos_std=float("nan"),
            r_inertia_neg_mean=float("nan"),
            r_inertia_neg_std=float("nan"),
            rationale=(
                f"INSUFFICIENT_N (n_pos={n_pos}, n_neg={n_neg}; "
                f"require ≥{MIN_CLASS_SIZE_FOR_AUC} per class)"
            ),
        )

    inertia_scores = np.asarray(
        [-v for v in pos_inertia] + [-v for v in neg_inertia],
        dtype=np.float64,
    )
    sim_scores = np.asarray(
        [-v for v in pos_sim] + [-v for v in neg_sim],
        dtype=np.float64,
    )
    y_arr = np.asarray([1] * n_pos + [0] * n_neg, dtype=np.int64)

    auc_inertia = _auc_tieaware(inertia_scores, y_arr)
    auc_sim = _auc_tieaware(sim_scores, y_arr)
    pos_inertia_arr = np.asarray(pos_inertia, dtype=np.float64)
    neg_inertia_arr = np.asarray(neg_inertia, dtype=np.float64)

    return SubsetSummary(
        name=name,
        pos_label=pos_label,
        neg_label=neg_label,
        n_pos=n_pos,
        n_neg=n_neg,
        eligible=True,
        auc_inertia=float(auc_inertia),
        auc_sim=float(auc_sim),
        dauc_inertia_vs_chance=float(auc_inertia - CHANCE_BASELINE_AUC),
        dauc_inertia_vs_sim=float(auc_inertia - auc_sim),
        r_inertia_pos_mean=float(pos_inertia_arr.mean()),
        r_inertia_pos_std=(
            float(pos_inertia_arr.std(ddof=1))
            if pos_inertia_arr.size > 1
            else 0.0
        ),
        r_inertia_neg_mean=float(neg_inertia_arr.mean()),
        r_inertia_neg_std=(
            float(neg_inertia_arr.std(ddof=1))
            if neg_inertia_arr.size > 1
            else 0.0
        ),
        rationale="ELIGIBLE",
    )


# ===========================================================================
# Counts-first orchestrator.
#
# Per the user's Fix-2: report class counts FIRST, then compute pairwise
# AUC ONLY for subsets that pass MIN_CLASS_SIZE_FOR_AUC. Subsets that
# don't pass return SubsetSummary(eligible=False, rationale="INSUFFICIENT_N
# (...)").
# ===========================================================================


@dataclass(frozen=True)
class ExploratoryRun:
    """Top-level exploratory result for the JSON / MD writers."""

    exploratory_schema_version: str
    primary_phase_schema_version: str
    primary_phase_verdict_unchanged: str
    primary_phase_verdict_commit: str
    benchmark: str
    n_stimuli: int
    label_counts: dict[str, int]
    subsets: tuple[SubsetSummary, ...]
    per_stimulus_labels: tuple[str, ...]
    per_stimulus_r_inertia: tuple[float, ...]
    per_stimulus_r_sim: tuple[float, ...]


def run_exploratory_analysis(
    extractions: tuple[StimulusExtraction, ...],
) -> ExploratoryRun:
    """Counts-first exploratory pipeline.

    1. Compute features (R_inertia + R_sim) per stimulus via the §15.13
       module's compute_features_per_stimulus.
    2. Apply the 3-way label.
    3. Print + record class counts BEFORE any AUC.
    4. Compute the 4 pre-committed pairwise AUC subsets, each gated on
       MIN_CLASS_SIZE_FOR_AUC = 10 per class.
    """
    n = len(extractions)
    if n == 0:
        raise SchemaMismatchError(
            "EXPLORATORY: empty extraction list; nothing to analyse."
        )
    features = tuple(compute_features_per_stimulus(e) for e in extractions)
    labels = classify_all(extractions)
    counts = label_counts(labels)

    print(
        f"  exploratory class counts (before any AUC):",
        flush=True,
    )
    print(f"    TOTAL          : {counts['TOTAL']}", flush=True)
    print(f"    CORRECT        : {counts[LABEL_CORRECT]}", flush=True)
    print(f"    REFUSAL        : {counts[LABEL_REFUSAL]}", flush=True)
    print(
        f"    CONFIDENT_WRONG: {counts[LABEL_CONFIDENT_WRONG]}",
        flush=True,
    )

    # Pre-committed subsets (PINNED).
    subset_specs = (
        (
            "all_stimuli_sanity",
            (LABEL_CORRECT,),
            (LABEL_REFUSAL, LABEL_CONFIDENT_WRONG),
        ),
        (
            "correct_vs_confident_wrong",
            (LABEL_CORRECT,),
            (LABEL_CONFIDENT_WRONG,),
        ),
        (
            "correct_vs_refusal",
            (LABEL_CORRECT,),
            (LABEL_REFUSAL,),
        ),
        (
            "confident_wrong_vs_refusal",
            (LABEL_CONFIDENT_WRONG,),
            (LABEL_REFUSAL,),
        ),
    )
    summaries: list[SubsetSummary] = []
    for name, pos_classes, neg_classes in subset_specs:
        s = compute_subset_summary(
            name, pos_classes, neg_classes, features, labels
        )
        summaries.append(s)
        if s.eligible:
            print(
                f"    [{name}] n_pos={s.n_pos}, n_neg={s.n_neg}, "
                f"AUC(inertia)={s.auc_inertia:.4f} "
                f"(ΔAUC chance {s.dauc_inertia_vs_chance:+.4f}; "
                f"ΔAUC sim {s.dauc_inertia_vs_sim:+.4f}) | "
                f"AUC(sim)={s.auc_sim:.4f}",
                flush=True,
            )
        else:
            print(
                f"    [{name}] {s.rationale}",
                flush=True,
            )

    return ExploratoryRun(
        exploratory_schema_version=EXPLORATORY_SCHEMA_VERSION,
        primary_phase_schema_version=PRIMARY_SCHEMA_VERSION,
        primary_phase_verdict_unchanged=PRIMARY_VERDICT,
        primary_phase_verdict_commit=PRIMARY_VERDICT_COMMIT,
        benchmark=BENCHMARK,
        n_stimuli=n,
        label_counts=counts,
        subsets=tuple(summaries),
        per_stimulus_labels=labels,
        per_stimulus_r_inertia=tuple(float(f.r_inertia) for f in features),
        per_stimulus_r_sim=tuple(float(f.r_sim) for f in features),
    )


# ===========================================================================
# Firewall — inherits §15.13's 44-pattern Class-3 list and adds 5
# exploratory-specific patterns that block accidental cascade-amendment
# language. Match policy preserved: case-insensitive substring for non-§
# patterns; literal (case-sensitive) substring for §-anchored patterns.
# ===========================================================================


def scan_with_extra_patterns(text: str) -> list[str]:
    """Run §15.13's 44-pattern firewall, then check the 5 exploratory
    extras. Returns combined list of detected patterns."""
    found = scan_for_forbidden_patterns(text)
    lowered = text.lower()
    for pattern in EXPLORATORY_EXTRA_FIREWALL_PATTERNS:
        if pattern.startswith("§"):
            if pattern in text:
                found.append(pattern)
        else:
            if pattern.lower() in lowered:
                found.append(pattern)
    return found


def enforce_exploratory_firewall_or_exit(text: str, output_path: str) -> None:
    """Scan with the §15.13 + exploratory pattern set; exit 4 on detection."""
    violations = scan_with_extra_patterns(text)
    if violations:
        print(
            f"INTERPRETATION_VIOLATION: refused to write {output_path}.",
            flush=True,
        )
        print("  detected forbidden statement(s):", flush=True)
        for v in violations:
            print(f"    - {v!r}", flush=True)
        print(
            "  rewrite the offending sentence(s); the §15.13 cascade "
            "verdict is binding, and exploratory subset findings cannot "
            "amend it.",
            flush=True,
        )
        sys.exit(4)


# ===========================================================================
# JSON output writer.
#
# The schema is distinct from §15.13's primary JSON: a different
# schema_version string ("15.13.exploratory.v1") and an explicit
# `non_amendment_declaration` top-level key. Top-level keys are
# alphabetical (sort_keys=True parity with the primary script).
# ===========================================================================


def _subset_to_dict(s: SubsetSummary) -> dict:
    def _maybe(v: float) -> Optional[float]:
        return None if math.isnan(v) else float(v)

    return {
        "name": s.name,
        "pos_label": s.pos_label,
        "neg_label": s.neg_label,
        "n_pos": int(s.n_pos),
        "n_neg": int(s.n_neg),
        "eligible": bool(s.eligible),
        "auc_inertia": _maybe(s.auc_inertia),
        "auc_sim": _maybe(s.auc_sim),
        "dauc_inertia_vs_chance": _maybe(s.dauc_inertia_vs_chance),
        "dauc_inertia_vs_sim": _maybe(s.dauc_inertia_vs_sim),
        "r_inertia_pos_mean": _maybe(s.r_inertia_pos_mean),
        "r_inertia_pos_std": _maybe(s.r_inertia_pos_std),
        "r_inertia_neg_mean": _maybe(s.r_inertia_neg_mean),
        "r_inertia_neg_std": _maybe(s.r_inertia_neg_std),
        "rationale": str(s.rationale),
    }


def _build_exploratory_payload(run: ExploratoryRun) -> dict:
    """Construct the §15.13 exploratory JSON payload."""
    return {
        "benchmark": str(run.benchmark),
        "exploratory_schema_version": str(run.exploratory_schema_version),
        "label_counts": dict(run.label_counts),
        "label_scheme": {
            "primary_label_source": "§13.10 NLI binary y (entails gold AND not entails any distractor)",
            "exploratory_3way_label": "CORRECT / REFUSAL / CONFIDENT_WRONG",
            "refusal_markers": list(REFUSAL_MARKERS),
            "short_response_floor_for_y0": int(SHORT_RESPONSE_FLOOR_FOR_Y0),
            "min_class_size_for_auc": int(MIN_CLASS_SIZE_FOR_AUC),
            "note": (
                "Refusal labels are heuristic text-based labels layered "
                "on top of the primary correctness label and are not "
                "equivalent to a prevalidated refusal benchmark."
            ),
        },
        "n_stimuli": int(run.n_stimuli),
        "non_amendment_declaration": (
            "EXPLORATORY ONLY. The §15.13 cascade verdict "
            f"{run.primary_phase_verdict_unchanged} (commit "
            f"{run.primary_phase_verdict_commit}) STAYS BINDING. "
            "Subset findings here are hypothesis-generating; turning "
            "any of them into a binding claim requires a fresh "
            "pre-committed §0.X — not an amendment to §15.13."
        ),
        "per_stimulus_labels": list(run.per_stimulus_labels),
        "per_stimulus_r_inertia": [float(v) for v in run.per_stimulus_r_inertia],
        "per_stimulus_r_sim": [float(v) for v in run.per_stimulus_r_sim],
        "primary_phase_schema_version": str(run.primary_phase_schema_version),
        "primary_phase_verdict_commit": str(run.primary_phase_verdict_commit),
        "primary_phase_verdict_unchanged": str(
            run.primary_phase_verdict_unchanged
        ),
        "qwen_model_id": QWEN_MODEL_ID,
        "subsets": [_subset_to_dict(s) for s in run.subsets],
    }


def write_exploratory_json(run: ExploratoryRun, path: str) -> None:
    """Serialize to JSON (indent=2, sort_keys=True)."""
    payload = _build_exploratory_payload(run)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


# ===========================================================================
# Markdown rendering + firewall-scanned writer.
#
# The first paragraph carries the explicit non-amendment declaration. The
# subset table renders ineligible subsets with "—" / INSUFFICIENT_N rather
# than dropping them — eligibility itself is information.
# ===========================================================================


def _format_subsets_table(subsets: tuple[SubsetSummary, ...]) -> str:
    lines = [
        "| subset | pos | neg | n_pos | n_neg | AUC(inertia) | ΔAUC vs chance | AUC(sim) | ΔAUC vs sim | eligible |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in subsets:
        if s.eligible:
            lines.append(
                f"| {s.name} | {s.pos_label} | {s.neg_label} | "
                f"{s.n_pos} | {s.n_neg} | "
                f"{s.auc_inertia:.4f} | {s.dauc_inertia_vs_chance:+.4f} | "
                f"{s.auc_sim:.4f} | {s.dauc_inertia_vs_sim:+.4f} | yes |"
            )
        else:
            lines.append(
                f"| {s.name} | {s.pos_label} | {s.neg_label} | "
                f"{s.n_pos} | {s.n_neg} | — | — | — | — | "
                f"no ({s.rationale}) |"
            )
    return "\n".join(lines)


def render_exploratory_markdown(run: ExploratoryRun) -> str:
    """Render the §15.13 exploratory markdown (firewall-scanned by caller).

    Section structure:
      1. Header + explicit non-amendment declaration.
      2. Label scheme (primary + exploratory) with the disclosure note.
      3. Class counts (pre-AUC).
      4. Subset AUC table.
      5. Per-subset detail (R_inertia distribution per class for
         eligible subsets; INSUFFICIENT_N message for ineligible).
      6. Method notes + caveats.
    """
    counts = run.label_counts
    subsets = run.subsets

    lines: list[str] = []

    # Section 1 — header + non-amendment declaration.
    lines.append(
        "# §15.13 exploratory analysis — refusal / confident-wrong "
        "subset AUCs\n"
    )
    lines.append(
        f"_Exploratory schema: `{run.exploratory_schema_version}`; "
        f"primary §15.13 schema: `{run.primary_phase_schema_version}`; "
        f"benchmark: `{run.benchmark}`; N = {run.n_stimuli}._\n"
    )
    lines.append(
        "**EXPLORATORY ONLY.** The §15.13 cascade verdict "
        f"`{run.primary_phase_verdict_unchanged}` "
        f"(commit `{run.primary_phase_verdict_commit}`) stays binding. "
        "Subset findings below are hypothesis-generating; turning any "
        "of them into a binding claim requires a fresh pre-committed "
        "§0.X — not an amendment to §15.13.\n"
    )
    lines.append(
        "**Refusal labels in this artifact are heuristic text-based "
        "labels layered on top of the primary §13.10-style correctness "
        "label and are NOT equivalent to a prevalidated refusal "
        "benchmark.**\n"
    )

    # Section 2 — label scheme.
    lines.append("## Label scheme\n")
    lines.append(
        "- **Primary label (binding for §15.13):** §13.10 NLI binary y\n"
        "  (entails gold AND not entails any distractor).\n"
        "- **Exploratory 3-way label (this artifact only):**\n"
        "  - `CORRECT`         when y == 1.\n"
        "  - `REFUSAL`         when y == 0 AND "
        f"(`len(response.strip()) < {SHORT_RESPONSE_FLOOR_FOR_Y0}` "
        "OR response_lower contains a refusal marker).\n"
        "  - `CONFIDENT_WRONG` when y == 0 AND not REFUSAL.\n"
        f"- **Refusal markers ({len(REFUSAL_MARKERS)}, pre-committed):**\n"
    )
    for marker in REFUSAL_MARKERS:
        lines.append(f"    - `{marker}`")
    lines.append("")
    lines.append(
        f"- **Min class size for AUC:** "
        f"`MIN_CLASS_SIZE_FOR_AUC = {MIN_CLASS_SIZE_FOR_AUC}`. Below "
        "this floor a subset reports `INSUFFICIENT_N` rather than a "
        "small-sample AUC.\n"
    )

    # Section 3 — class counts (pre-AUC).
    lines.append("## Class counts (reported before any AUC)\n")
    lines.append(
        "| class | count |\n"
        "|---|---|\n"
        f"| `CORRECT`         | {counts[LABEL_CORRECT]} |\n"
        f"| `REFUSAL`         | {counts[LABEL_REFUSAL]} |\n"
        f"| `CONFIDENT_WRONG` | {counts[LABEL_CONFIDENT_WRONG]} |\n"
        f"| **TOTAL**         | **{counts['TOTAL']}** |\n"
    )

    # Section 4 — subset AUC table.
    lines.append("## Subset AUCs (disclosure only — not §15.13 cascade inputs)\n")
    lines.append(_format_subsets_table(subsets))
    lines.append("")
    lines.append(
        "Score in all subsets is `−R_inertia` (BCVF-faithful direction: "
        "lower R_inertia predicts the positive class). `AUC(sim)` uses "
        "`−R_sim` over the same subset for the topical-similarity "
        "comparator. The §15.13 cascade is NOT applied to any subset "
        "above; cascade application is §15.13-binding only.\n"
    )

    # Section 5 — per-subset R_inertia distribution per class.
    lines.append("## Per-subset R_inertia distribution\n")
    for s in subsets:
        if not s.eligible:
            lines.append(
                f"### `{s.name}`\n"
                f"_{s.rationale}._ (n_pos={s.n_pos}, n_neg={s.n_neg}; "
                f"require ≥{MIN_CLASS_SIZE_FOR_AUC} per class.)\n"
            )
            continue
        lines.append(
            f"### `{s.name}` — pos = `{s.pos_label}` / neg = `{s.neg_label}`\n"
            f"- pos (n={s.n_pos}): R_inertia mean = "
            f"{s.r_inertia_pos_mean:+.4f}, std = {s.r_inertia_pos_std:.4f}\n"
            f"- neg (n={s.n_neg}): R_inertia mean = "
            f"{s.r_inertia_neg_mean:+.4f}, std = {s.r_inertia_neg_std:.4f}\n"
            f"- AUC(inertia) = **{s.auc_inertia:.4f}**; "
            f"ΔAUC vs chance = {s.dauc_inertia_vs_chance:+.4f}; "
            f"AUC(sim) = {s.auc_sim:.4f}; "
            f"ΔAUC vs sim = {s.dauc_inertia_vs_sim:+.4f}\n"
        )

    # Section 6 — method notes + caveats.
    lines.append("## Method notes\n")
    lines.append(
        "- This artifact is generated post-hoc from the §15.13 "
        "extraction cache; no model reload, no re-extraction. The "
        "per-stimulus `R_inertia` and `R_sim` values are byte-for-byte "
        "identical to those used by the §15.13 primary probe.\n"
        "- Class counts are reported BEFORE any AUC. Subsets failing "
        f"the `MIN_CLASS_SIZE_FOR_AUC = {MIN_CLASS_SIZE_FOR_AUC}` floor "
        "report INSUFFICIENT_N to avoid meaningless small-sample AUC.\n"
        "- The pinned refusal-marker list, short-response floor, and "
        "minimum-class-size floor were committed BEFORE any subset AUC "
        "was inspected. Modifying them after seeing data here would be "
        "HARKing and is forbidden.\n"
        "- A subset clearing AUC ≥ 0.75 here would be a candidate for a "
        "fresh pre-committed §0.X — not an automatic upgrade of §15.13. "
        "The §15.13 cascade rule, direction convention, and threshold "
        "set are §15.13-binding only.\n"
        f"- Heuristic refusal classification is a coarse proxy. A "
        "future §0.X with a hand-validated refusal benchmark could "
        "yield different counts and shift any subset AUC by a few "
        "points; v1 reports the heuristic as-is.\n"
    )
    lines.append(
        "## §15.13 audit-trail integrity\n"
        f"§15.13 cascade verdict `{run.primary_phase_verdict_unchanged}` "
        f"(commit `{run.primary_phase_verdict_commit}`) is preserved. "
        "§13.9 hold remains binding. §6.1 N=21 autonomy result is "
        "preserved. §15.10 PARTIAL_SIGNAL_IN_Z is preserved. §15.11 "
        "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE is preserved. §15.12 "
        "closure is preserved. This exploratory artifact is "
        "non-binding and does not modify any §13/§14/§15.x "
        "verdict-of-record.\n"
    )

    return "\n".join(lines)


def write_exploratory_markdown(run: ExploratoryRun, path: str) -> None:
    """Render markdown, run the firewall (44 + 5 patterns), then write."""
    text = render_exploratory_markdown(run)
    enforce_exploratory_firewall_or_exit(text, path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)


# ===========================================================================
# §15.13 exploratory Chunk E-4 — self-test gate + CLI orchestration.
#
# Self-test gate (required before any subset analysis):
#   1. Refusal classifier on hand-pinned synthetic cases (CORRECT short
#      answer protected, refusal markers detected, confident-wrong text
#      stays CONFIDENT_WRONG).
#   2. Firewall coverage: 44 (§15.13) + 5 (exploratory-extra) = 49
#      positive detections; clean §15.13-style text passes.
#   3. AUC helper sanity: identical pos/neg → AUC=0.5; perfectly-
#      separable pos/neg → AUC=1.0; reversed → AUC=0.0.
#
# CLI modes:
#   --self-test     : run gate only.
#   --cache-path    : override input cache path.
#   --json-out      : override output JSON path.
#   --md-out        : override output markdown path.
#   (default)       : self-test → load cache → analyse → write outputs.
#
# Exit codes:
#   0  success
#   2  CLI / argument error (handled by argparse)
#   3  SELF_TEST_FAILED
#   4  INTERPRETATION_VIOLATION
#   5  SCHEMA_MISMATCH (cache load)
#   7  ANALYSIS_FAILED (numpy / non-finite features)
# ===========================================================================


# Synthetic test fixtures for the refusal classifier — pre-committed.
# Each entry: (y, response_text, expected_label).
_REFUSAL_CLASSIFIER_FIXTURES: tuple[tuple[bool, str, str], ...] = (
    (True, "Paris", LABEL_CORRECT),
    (True, "I don't know — but Paris.", LABEL_CORRECT),
    (False, "Paris", LABEL_REFUSAL),  # short + y=0 → REFUSAL by length
    (False, "", LABEL_REFUSAL),
    (False, "I don't know.", LABEL_REFUSAL),
    (False, "I do not know the answer.", LABEL_REFUSAL),
    (False, "I'm not sure about that.", LABEL_REFUSAL),
    (False, "I am not sure.", LABEL_REFUSAL),
    (False, "I can't tell you.", LABEL_REFUSAL),
    (False, "I cannot answer this.", LABEL_REFUSAL),
    (False, "I'm unable to answer.", LABEL_REFUSAL),
    (False, "I am unable to determine.", LABEL_REFUSAL),
    (False, "As an AI language model, I cannot.", LABEL_REFUSAL),
    (False, "I don't have information on that.", LABEL_REFUSAL),
    (False, "I do not have access to that data.", LABEL_REFUSAL),
    (False, "The capital of France is London.", LABEL_CONFIDENT_WRONG),
    (False, "It depends on the context, probably 42.", LABEL_CONFIDENT_WRONG),
    (False, "Sorry but the answer is 42.", LABEL_CONFIDENT_WRONG),
    (False, "Unknown territories of Atlantis.", LABEL_CONFIDENT_WRONG),
    (False, "Hard to say, but my guess is X.", LABEL_CONFIDENT_WRONG),
)


def _self_test_refusal_classifier() -> list[str]:
    """Run all _REFUSAL_CLASSIFIER_FIXTURES; return failure messages."""
    failures: list[str] = []
    for i, (y, text, expected) in enumerate(_REFUSAL_CLASSIFIER_FIXTURES):
        # Build a minimal stimulus shape that classify_exploratory_label
        # only reads y and q_b_response_text from.
        ext = StimulusExtraction(
            pair_idx=i,
            q_a_idx=0,
            q_b_idx=0,
            q_a_repr=np.zeros(1, dtype=np.float32),
            r_a_repr=np.zeros(1, dtype=np.float32),
            s_t=np.zeros(1, dtype=np.float32),
            q_b_repr=np.zeros(1, dtype=np.float32),
            r_a_text="",
            q_b_response_text=text,
            n_r_a_tokens=0,
            n_q_b_response_tokens=0,
            y=bool(y),
        )
        got = classify_exploratory_label(ext)
        if got != expected:
            failures.append(
                f"  fixture {i + 1}: y={y}, text={text!r:50s} → "
                f"got {got!r}, expected {expected!r}"
            )
    return failures


def _self_test_firewall_extras() -> list[str]:
    """Verify firewall flags 44 (§15.13) + 5 (extra) = 49 patterns +
    clean §15.13-style text passes."""
    failures: list[str] = []
    total_expected = 44 + len(EXPLORATORY_EXTRA_FIREWALL_PATTERNS)
    if total_expected != 49:
        failures.append(
            f"  pattern count: 44 + "
            f"{len(EXPLORATORY_EXTRA_FIREWALL_PATTERNS)} = "
            f"{total_expected} (expected 49)"
        )
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        sample = f"text {pattern} text"
        if not scan_with_extra_patterns(sample):
            failures.append(
                f"  §15.13 pattern not detected: {pattern!r}"
            )
    for pattern in EXPLORATORY_EXTRA_FIREWALL_PATTERNS:
        sample = f"text {pattern} text"
        if not scan_with_extra_patterns(sample):
            failures.append(
                f"  exploratory-extra pattern not detected: {pattern!r}"
            )
    clean = (
        "Exploratory subset AUCs at α∈{0.35, 0.50, 0.75} are reported "
        "as disclosure only; the §15.13 cascade verdict "
        "NO_MATERIAL_SIGNAL_IN_INERTIA stays binding. §15.10 PARTIAL_"
        "SIGNAL_IN_Z preserved; §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_"
        "COHERENCE preserved; §15.12 closure preserved. §13.9 hold "
        "remains binding. §6.1 N=21 autonomy result preserved. The "
        "R_sim comparator is included for parity with the cascade."
    )
    spurious = scan_with_extra_patterns(clean)
    if spurious:
        failures.append(
            f"  firewall false-positive on clean text: {spurious!r}"
        )
    return failures


def _self_test_auc_helper() -> list[str]:
    """Verify _auc_tieaware on three pinned cases.

    1. All ties → AUC = 0.5.
    2. Perfectly separable (all pos > all neg) → AUC = 1.0.
    3. Perfectly anti-separable (all pos < all neg) → AUC = 0.0.
    """
    failures: list[str] = []
    scores = np.asarray([0.5] * 6, dtype=np.float64)
    labels = np.asarray([1, 1, 1, 0, 0, 0], dtype=np.int64)
    auc_tied = _auc_tieaware(scores, labels)
    if not (abs(auc_tied - 0.5) < 1e-12):
        failures.append(f"  ties: AUC={auc_tied} (expected 0.5)")

    scores = np.asarray([1.0, 1.0, 1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    auc_perfect = _auc_tieaware(scores, labels)
    if not (abs(auc_perfect - 1.0) < 1e-12):
        failures.append(f"  perfect: AUC={auc_perfect} (expected 1.0)")

    scores = np.asarray([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=np.float64)
    auc_anti = _auc_tieaware(scores, labels)
    if not (abs(auc_anti) < 1e-12):
        failures.append(f"  anti-perfect: AUC={auc_anti} (expected 0.0)")

    return failures


def run_self_test() -> int:
    """Execute the §15.13 exploratory self-test gate; return 0 / 3."""
    print("§15.13 exploratory self-test gate", flush=True)
    print(
        f"  exploratory schema: {EXPLORATORY_SCHEMA_VERSION}", flush=True
    )
    print(f"  primary §15.13 schema: {PRIMARY_SCHEMA_VERSION}", flush=True)
    print(
        f"  primary verdict (unchanged): {PRIMARY_VERDICT} "
        f"(commit {PRIMARY_VERDICT_COMMIT})",
        flush=True,
    )
    print(
        f"  refusal markers (pre-committed): "
        f"{len(REFUSAL_MARKERS)}",
        flush=True,
    )
    print(
        f"  short-response floor (y=0 only): "
        f"{SHORT_RESPONSE_FLOOR_FOR_Y0}",
        flush=True,
    )
    print(
        f"  min class size for AUC: "
        f"{MIN_CLASS_SIZE_FOR_AUC}",
        flush=True,
    )
    print(
        f"  firewall: {len(CLASS_3_FORBIDDEN_PATTERNS)} (§15.13) + "
        f"{len(EXPLORATORY_EXTRA_FIREWALL_PATTERNS)} (extra) = "
        f"{len(CLASS_3_FORBIDDEN_PATTERNS) + len(EXPLORATORY_EXTRA_FIREWALL_PATTERNS)}",
        flush=True,
    )

    all_failures: list[str] = []

    print("  [1/3] refusal classifier on pinned fixtures...", flush=True)
    cls_fail = _self_test_refusal_classifier()
    if cls_fail:
        all_failures.append("CLASSIFIER FAILURES:")
        all_failures.extend(cls_fail)
    else:
        print(
            f"    OK: {len(_REFUSAL_CLASSIFIER_FIXTURES)} fixtures "
            f"(CORRECT/REFUSAL/CONFIDENT_WRONG) classify as expected.",
            flush=True,
        )

    print("  [2/3] firewall coverage (44 + 5 = 49)...", flush=True)
    fw_fail = _self_test_firewall_extras()
    if fw_fail:
        all_failures.append("FIREWALL FAILURES:")
        all_failures.extend(fw_fail)
    else:
        print(
            f"    OK: 49 patterns flagged on positives; clean "
            f"§15.13/exploratory text passes.",
            flush=True,
        )

    print("  [3/3] AUC helper (ties / perfect / anti-perfect)...", flush=True)
    auc_fail = _self_test_auc_helper()
    if auc_fail:
        all_failures.append("AUC HELPER FAILURES:")
        all_failures.extend(auc_fail)
    else:
        print(
            "    OK: ties → 0.5; perfect-sep → 1.0; anti-perfect → 0.0.",
            flush=True,
        )

    if all_failures:
        print("\nSELF_TEST_FAILED:", flush=True)
        for line in all_failures:
            print(line, flush=True)
        return 3
    print("\nSELF_TEST_PASSED — proceed.", flush=True)
    return 0


# ---------------------------------------------------------------------------
# CLI + main.
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="probe_inertia_15_13_exploratory",
        description=(
            "§15.13 exploratory analysis — refusal/confident-wrong subset "
            "AUCs over the §15.13 extraction cache. EXPLORATORY ONLY: the "
            "§15.13 cascade verdict NO_MATERIAL_SIGNAL_IN_INERTIA "
            "(commit b817a98) stays binding; subset findings here are "
            "hypothesis-generating, not verdict-amending."
        ),
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run self-test gate only (refusal classifier on 20 pinned "
            "fixtures + 49-pattern firewall + AUC helper sanity)."
        ),
    )
    p.add_argument(
        "--cache-path",
        default=EXTRACTIONS_CACHE_PATH,
        help=(
            f"Path to the §15.13 extraction cache .npz "
            f"(default: {EXTRACTIONS_CACHE_PATH})"
        ),
    )
    p.add_argument(
        "--json-out",
        default=OUTPUT_JSON_PATH,
        help=f"Path to JSON output (default: {OUTPUT_JSON_PATH})",
    )
    p.add_argument(
        "--md-out",
        default=OUTPUT_MD_PATH,
        help=f"Path to markdown output (default: {OUTPUT_MD_PATH})",
    )
    return p


def _print_exploratory_banner(run: ExploratoryRun) -> None:
    """One-screen summary banner of exploratory subset readouts."""
    print("", flush=True)
    print("=" * 76, flush=True)
    print(
        f"§15.13 exploratory subset AUCs (binding §15.13 verdict: "
        f"{run.primary_phase_verdict_unchanged} preserved)",
        flush=True,
    )
    print("-" * 76, flush=True)
    counts = run.label_counts
    print(
        f"  class counts: CORRECT={counts[LABEL_CORRECT]}, "
        f"REFUSAL={counts[LABEL_REFUSAL]}, "
        f"CONFIDENT_WRONG={counts[LABEL_CONFIDENT_WRONG]} "
        f"(TOTAL={counts['TOTAL']})",
        flush=True,
    )
    print("-" * 76, flush=True)
    for s in run.subsets:
        if s.eligible:
            print(
                f"  {s.name:30s}  n_pos={s.n_pos:3d}, n_neg={s.n_neg:3d} | "
                f"AUC(inertia)={s.auc_inertia:.4f} "
                f"(ΔAUC chance {s.dauc_inertia_vs_chance:+.4f}; "
                f"ΔAUC sim {s.dauc_inertia_vs_sim:+.4f}) | "
                f"AUC(sim)={s.auc_sim:.4f}",
                flush=True,
            )
        else:
            print(
                f"  {s.name:30s}  n_pos={s.n_pos:3d}, n_neg={s.n_neg:3d} | "
                f"{s.rationale}",
                flush=True,
            )
    print("=" * 76, flush=True)
    print(
        f"  reminder: §15.13 cascade verdict "
        f"{run.primary_phase_verdict_unchanged} (commit "
        f"{run.primary_phase_verdict_commit}) stays binding. The "
        f"subset AUCs above are disclosure-only and do not amend "
        f"§15.13.",
        flush=True,
    )
    print("=" * 76, flush=True)


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)

    if args.self_test:
        return run_self_test()

    rc = run_self_test()
    if rc != 0:
        return rc

    print(
        f"\nLoading §15.13 extraction cache from {args.cache_path}",
        flush=True,
    )
    try:
        extractions = load_extractions_cache(args.cache_path)
    except SchemaMismatchError as e:
        print(f"SCHEMA_MISMATCH: {e}", flush=True)
        return 5
    except FileNotFoundError as e:
        print(f"CACHE_MISSING: {e}", flush=True)
        return 5

    print(f"\nExploratory subset analysis (counts-first, AUC second).", flush=True)
    try:
        run = run_exploratory_analysis(extractions)
    except SchemaMismatchError as e:
        print(f"SCHEMA_MISMATCH: {e}", flush=True)
        return 5
    except RuntimeError as e:
        print(f"ANALYSIS_FAILED: {e}", flush=True)
        return 7

    print("\nOutput phase — JSON + firewall-scanned markdown.", flush=True)
    write_exploratory_json(run, args.json_out)
    print(f"  wrote: {args.json_out}", flush=True)
    write_exploratory_markdown(run, args.md_out)
    print(f"  wrote: {args.md_out}", flush=True)

    _print_exploratory_banner(run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
