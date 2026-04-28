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
