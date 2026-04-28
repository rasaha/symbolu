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
