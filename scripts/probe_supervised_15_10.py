#!/usr/bin/env python
"""§15.10 Phase 1 — Supervised linear truth-probe (final-resolution sprint).

Pure §0.8-binding implementation per the frozen §15.10 pre-
commitment. Tests whether Qwen2.5-7B-Instruct's hidden
representations contain truth signal that the unsupervised
BCVF-style score family failed to extract.

Reference: docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §15.10.

What this script DOES:
  * Loads correctness labels from the existing §13.10 dumps
    (per-question greedy_matches_correct booleans).
  * Optionally extracts final-layer last-token hidden states
    from Qwen2.5-7B-Instruct over each question prompt
    `Q: {question}\\nA:` (or loads from cache if already
    extracted).
  * Trains an L2-regularized logistic regression probe per
    benchmark via 5-fold stratified cross-validation.
  * Computes probe AUC and selective-prediction kappa@alpha_2
    from out-of-fold predictions.
  * Compares probe AUC to §13.10 entropy baseline (0.661 on
    each benchmark per the §13.10 verdict-of-record).
  * Classifies into STRONG_SIGNAL_IN_Z / PARTIAL_SIGNAL_IN_Z
    / NO_MATERIAL_SIGNAL_IN_Z per the pinned cascade.
  * Emits JSON + markdown artifacts with §15.7-pattern
    interpretation firewall enforced at write time.

What this script DOES NOT:
  * Re-classify any §13/§14/§15.x verdict-of-record. All
    bands remain binding regardless of §15.10 outputs.
  * Iterate on probe architecture, feature selection, or
    hyperparameters. Linear only; one shot.
  * Authorize Phase 2 / Phase 3 of the sprint. Each requires
    its own §0.8 commitment.

Inputs (per §15.10):
    docs/experiments/probe_semantic_entropy.json
        (§13.10 TruthfulQA-MC dump; per-question correctness
        labels; first 100 questions used regardless of N status)
    docs/experiments/probe_semantic_entropy_halueval_qa.json
        (§13.10 HaluEval-QA dump; same usage)
    `Qwen/Qwen2.5-7B-Instruct` (cached HF model)
    HaluEval-QA + TruthfulQA-MC datasets (HuggingFace)

Outputs (per §15.10):
    docs/experiments/hidden_states_qwen_15_10.npz
        (cached extraction; allows skipping re-extraction)
    docs/experiments/probe_supervised_15_10.json
        (machine-readable result, schema_version "15.10")
    docs/experiments/probe_supervised_15_10.md
        (human-readable report, firewall-scanned at write time)

Usage:
    # Required pre-execution gate.
    python scripts/probe_supervised_15_10.py --self-test

    # Full pipeline (extract + probe + report).
    python scripts/probe_supervised_15_10.py

    # Extract only (GPU phase; produces .npz cache).
    python scripts/probe_supervised_15_10.py --extract-only

    # Probe only (CPU phase; uses .npz cache).
    python scripts/probe_supervised_15_10.py --probe-only

§15.7's interpretation firewall pattern is reused: rendered
markdown is scanned for Class-3 forbidden statements before
write; INTERPRETATION_VIOLATION exits 4 on detection.
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
# §15.10 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.10.
# ===========================================================================

SCHEMA_VERSION = "15.10"

# Target model (pinned per §15.10 spec; matches §13.10/§14a.2/§15.x).
QWEN_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Benchmarks (pinned).
BENCHMARKS: tuple[str, ...] = ("halueval_qa", "truthfulqa_mc")

# Pinned size per benchmark.
PINNED_N = 100

# §13.10 dumps — used ONLY for correctness labels, first 100 records.
# Per §15.10 §0.8 caveat: dumps may be N=100 or N=200 depending on
# runpod state; we use first PINNED_N=100 records regardless.
INPUT_S13_10_HALUEVAL = "docs/experiments/probe_semantic_entropy_halueval_qa.json"
INPUT_S13_10_TRUTHFULQA = "docs/experiments/probe_semantic_entropy.json"

# Pinned §13.10 baseline AUCs (per §13.10 verdict-of-record at N=100).
BASELINE_AUC_PER_BENCHMARK: dict[str, float] = {
    "halueval_qa": 0.661,
    "truthfulqa_mc": 0.661,
}

# Pinned base rates pi (per §13.10 prose; Qwen-greedy accuracy).
PINNED_PI: dict[str, float] = {
    "halueval_qa": 0.300,
    "truthfulqa_mc": 0.250,
}

# Pinned alpha targets per benchmark (matches §15.x).
ALPHA_TARGETS_PER_BENCHMARK: dict[str, tuple[float, ...]] = {
    "halueval_qa": (0.40, 0.50, 0.75),
    "truthfulqa_mc": (0.35, 0.50, 0.75),
}
ALPHA_PRIMARY = 0.50

# Probe parameters (pinned, single configuration).
PROBE_PENALTY = "l2"
PROBE_C = 1.0
PROBE_MAX_ITER = 1000
PROBE_SOLVER = "lbfgs"  # default for sklearn LogisticRegression with L2

# 5-fold stratified cross-validation per §15.10.
N_FOLDS = 5
N_MIN = 10  # selective-prediction floor (matches §15.x)
SEED_ENTROPY = 15

# Cascade thresholds per §15.10 (pinned exhaustive partition).
# STRONG_SIGNAL_IN_Z: AUC >= 0.75 on BOTH AND dAUC >= +0.05 on BOTH.
# PARTIAL_SIGNAL_IN_Z: AUC >= 0.66 on at least one AND dAUC > 0 on at least
#   one, AND not STRONG.
# NO_MATERIAL_SIGNAL_IN_Z: otherwise.
STRONG_AUC_THRESHOLD = 0.75
STRONG_DELTA_AUC_THRESHOLD = 0.05
PARTIAL_AUC_THRESHOLD = 0.66
NO_MATERIAL_AUC_FLOOR = 0.60

# Hidden-state extraction config (pinned).
PROMPT_FORMAT = "Q: {question}\nA:"
LAYER_IDX_FINAL = -1  # final-layer last-token hidden state
EXTRACT_DTYPE = "float16"  # match Qwen2.5-7B's native fp16

# Cache + output paths (pinned).
HIDDEN_STATES_CACHE_PATH = "docs/experiments/hidden_states_qwen_15_10.npz"
OUTPUT_JSON_PATH = "docs/experiments/probe_supervised_15_10.json"
OUTPUT_MD_PATH = "docs/experiments/probe_supervised_15_10.md"

# §13.10 dump field names (per §15.1 Amendment 1 pinned schema).
FIELD_QID = "q_idx"
FIELD_CORRECT = "greedy_matches_correct"
FIELD_QUESTION = "question"

# §15.7-style Class-3 forbidden-statement patterns. Same set as §15.7
# Chunk 7f, plus §15.10-specific patterns to prevent soft-override of
# the cascade.
CLASS_3_FORBIDDEN_PATTERNS: list[str] = [
    "verdict was wrong",
    "verdict is wrong",
    "should be re-classified",
    "should be reclassified",
    "is invalid because",
    "§13.9 should be relaxed",
    "§13.9 hold should be",
    "§13.9 hold can be",
    "§15.8 authorized",
    "§15.8 is authorized",
    "§6.1 is strengthened",
    "autonomy result is strengthened",
    # §15.10-specific.
    "actually STRONG",
    "should be classified as STRONG",
    "actually PARTIAL despite",
    "STRONG despite the cascade",
]

# Self-test boundary cases for the cascade classifier.
# Each entry: (auc_halueval, auc_truthfulqa, dauc_halueval,
#              dauc_truthfulqa, expected_label).
SELF_TEST_CASCADE_CASES: list[tuple[float, float, float, float, str]] = [
    # Clean STRONG: both AUCs above 0.75 AND both ΔAUCs above +0.05.
    (0.80, 0.78, 0.139, 0.119, "STRONG_SIGNAL_IN_Z"),
    # Just clears STRONG at boundary (inclusive).
    (0.75, 0.75, 0.05, 0.05, "STRONG_SIGNAL_IN_Z"),
    # AUC just below STRONG → PARTIAL (one benchmark above 0.66, ΔAUC>0).
    (0.74, 0.78, 0.079, 0.119, "PARTIAL_SIGNAL_IN_Z"),
    # ΔAUC just below STRONG → PARTIAL.
    (0.80, 0.78, 0.139, 0.04, "PARTIAL_SIGNAL_IN_Z"),
    # PARTIAL: one benchmark at 0.70 with positive ΔAUC, other failing.
    (0.70, 0.55, 0.039, -0.111, "PARTIAL_SIGNAL_IN_Z"),
    # PARTIAL: AUC = 0.66 threshold inclusive.
    (0.66, 0.55, 0.001, -0.111, "PARTIAL_SIGNAL_IN_Z"),
    # NO_MATERIAL: both probe AUCs below baseline (ΔAUC<=0 on both).
    (0.65, 0.65, -0.011, -0.011, "NO_MATERIAL_SIGNAL_IN_Z"),
    # NO_MATERIAL: both AUCs < 0.60 floor (regardless of ΔAUC sign).
    (0.55, 0.55, 0.05, 0.05, "NO_MATERIAL_SIGNAL_IN_Z"),
    # NO_MATERIAL: one benchmark above floor but probe doesn't beat
    # baseline on either.
    (0.661, 0.661, 0.0, 0.0, "NO_MATERIAL_SIGNAL_IN_Z"),
]


# ===========================================================================
# Dataclasses — immutable records.
# ===========================================================================


@dataclass(frozen=True)
class BenchmarkLabels:
    """Per-question correctness labels + question text loaded from §13.10 dump."""

    benchmark: str
    q_ids: tuple[int, ...]
    questions: tuple[str, ...]
    correctness: tuple[bool, ...]


@dataclass(frozen=True)
class HiddenStateExtraction:
    """Extracted final-layer last-token hidden states aligned with labels."""

    benchmark: str
    q_ids: np.ndarray  # int, shape (N,)
    hidden_states: np.ndarray  # float, shape (N, d)
    correctness: np.ndarray  # bool, shape (N,)
    layer_idx: int
    d: int


@dataclass(frozen=True)
class ProbeResult:
    """Per-benchmark probe result from 5-fold CV."""

    benchmark: str
    n_questions: int
    n_correct: int
    n_wrong: int
    pi_observed: float
    auc_oof: float
    fold_aucs: tuple[float, ...]
    auc_cv_std: float
    accuracy_oof: float
    brier_oof: float
    kappa_at_alpha2: float
    tau_star_at_alpha2: float
    operating_points: tuple[dict, ...]
    p_oof: tuple[float, ...]


@dataclass(frozen=True)
class CascadeVerdict:
    """Final §15.10 cascade outcome."""

    label: str  # STRONG_SIGNAL_IN_Z / PARTIAL_SIGNAL_IN_Z / NO_MATERIAL_SIGNAL_IN_Z
    auc_halueval: float
    auc_truthfulqa: float
    dauc_halueval: float
    dauc_truthfulqa: float
    rationale: str


@dataclass(frozen=True)
class SupervisedAuditOutputs:
    """Top-level §15.10 outputs for both benchmarks."""

    schema_version: str
    halueval_probe: ProbeResult
    truthfulqa_probe: ProbeResult
    cascade_verdict: CascadeVerdict
    extraction_layer: int
    hidden_dim: int
    qwen_model_id: str


# ===========================================================================
# §15.10 Chunk I-2 — Schema validators, §13.10 label loader, hidden-state
# extraction with .npz caching.
#
# Discipline: fail-fast SCHEMA_MISMATCH on any structural drift in the
# §13.10 dumps. We do not silently coerce; missing fields, wrong types,
# or short dumps abort with explicit cause.
# ===========================================================================


class SchemaMismatchError(RuntimeError):
    """Raised when a §13.10 dump fails schema validation."""


def _validate_s13_10_dump(payload: object, source_path: str) -> list[dict]:
    """Validate top-level shape of a §13.10 dump and return per-question records.

    The §13.10 dumps are JSON files whose top-level may be either a list of
    per-question records, or a dict containing a 'records' / 'per_question'
    list. We accept both shapes (per §15.1 Amendment 1 schema notes) but
    require the per-question records to expose {q_idx, question,
    greedy_matches_correct} at minimum.
    """
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        for key in ("per_question", "records", "questions"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
        else:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} top-level dict has no "
                f"'per_question'/'records'/'questions' list."
            )
    else:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: {source_path} top-level is "
            f"{type(payload).__name__}, expected list or dict."
        )

    if len(records) < PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: {source_path} has {len(records)} records, "
            f"need at least {PINNED_N}."
        )

    for i, rec in enumerate(records[:PINNED_N]):
        if not isinstance(rec, dict):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} is "
                f"{type(rec).__name__}, expected dict."
            )
        for required in (FIELD_QID, FIELD_QUESTION, FIELD_CORRECT):
            if required not in rec:
                raise SchemaMismatchError(
                    f"SCHEMA_MISMATCH: {source_path} record {i} missing "
                    f"required field '{required}'."
                )
        if not isinstance(rec[FIELD_QID], int):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QID}' is {type(rec[FIELD_QID]).__name__}, "
                f"expected int."
            )
        if not isinstance(rec[FIELD_QUESTION], str):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QUESTION}' is {type(rec[FIELD_QUESTION]).__name__}, "
                f"expected str."
            )
        if not isinstance(rec[FIELD_CORRECT], bool):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_CORRECT}' is {type(rec[FIELD_CORRECT]).__name__}, "
                f"expected bool."
            )
    return records


def load_benchmark_labels(benchmark: str) -> BenchmarkLabels:
    """Load first PINNED_N records from the §13.10 dump for `benchmark`.

    Returns BenchmarkLabels with q_ids/questions/correctness aligned by
    record order in the dump. We deliberately do NOT re-sort by q_idx;
    the dump's record order is canonical (matches §15.1/§15.7 convention).
    """
    if benchmark == "halueval_qa":
        path = INPUT_S13_10_HALUEVAL
    elif benchmark == "truthfulqa_mc":
        path = INPUT_S13_10_TRUTHFULQA
    else:
        raise ValueError(f"Unknown benchmark: {benchmark!r}")

    dump_path = Path(path)
    if not dump_path.exists():
        raise FileNotFoundError(
            f"§13.10 dump not found: {dump_path}. "
            f"Required for §15.10 Phase 1 label loading."
        )

    with dump_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    records = _validate_s13_10_dump(payload, str(dump_path))
    head = records[:PINNED_N]
    q_ids = tuple(int(r[FIELD_QID]) for r in head)
    questions = tuple(str(r[FIELD_QUESTION]) for r in head)
    correctness = tuple(bool(r[FIELD_CORRECT]) for r in head)

    return BenchmarkLabels(
        benchmark=benchmark,
        q_ids=q_ids,
        questions=questions,
        correctness=correctness,
    )


# ---------------------------------------------------------------------------
# Hidden-state extraction (Qwen2.5-7B-Instruct forward pass).
#
# We import torch + transformers lazily so that --probe-only and --self-test
# do not require a GPU stack. Errors during import surface clearly.
# ---------------------------------------------------------------------------


def _lazy_import_torch_and_transformers():
    """Lazy import of torch + transformers; raises with a clear message."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.10 hidden-state extraction requires torch + transformers. "
            "Install on the runpod GPU node before --extract-only or "
            "default --run."
        ) from exc
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    return torch, AutoModelForCausalLM, AutoTokenizer


def extract_hidden_states(
    labels: BenchmarkLabels,
    *,
    model=None,
    tokenizer=None,
    device: Optional[str] = None,
) -> HiddenStateExtraction:
    """Forward-pass each prompt through Qwen-7B; collect final-layer last-token h.

    For each question q_i, we build the prompt `Q: {question}\\nA:` (PROMPT_FORMAT),
    tokenize, run a forward pass with output_hidden_states=True, and take
    the final-layer hidden state at the LAST token position. This matches
    the standard "linear truth probe" extraction pattern (Burns et al.,
    Marks & Tegmark) modulo prompt template — we use the §13.10 prompt
    template for alignment with the labels.

    We force fp16 inference (EXTRACT_DTYPE) and no_grad to fit a 7B model
    on a single GPU. Hidden states are cast to fp32 before stacking so the
    .npz cache is portable to CPU-only probe runs.
    """
    torch, AutoModelForCausalLM, AutoTokenizer = _lazy_import_torch_and_transformers()

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    if tokenizer is None:
        tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL_ID)
    if model is None:
        model = AutoModelForCausalLM.from_pretrained(
            QWEN_MODEL_ID,
            torch_dtype=torch.float16,
            device_map=device,
            output_hidden_states=True,
        )
        model.eval()

    n = len(labels.questions)
    hidden_list: list[np.ndarray] = []
    with torch.no_grad():
        for i, question in enumerate(labels.questions):
            prompt = PROMPT_FORMAT.format(question=question)
            enc = tokenizer(prompt, return_tensors="pt").to(device)
            out = model(**enc, output_hidden_states=True)
            # out.hidden_states is a tuple of length (n_layers + 1);
            # index LAYER_IDX_FINAL = -1 selects the final layer's output.
            h_last_layer = out.hidden_states[LAYER_IDX_FINAL]  # (1, T, d)
            h_last_token = h_last_layer[0, -1, :]  # (d,)
            hidden_list.append(h_last_token.detach().to("cpu").float().numpy())
            if (i + 1) % 10 == 0:
                print(
                    f"  [extract:{labels.benchmark}] {i + 1}/{n} questions",
                    flush=True,
                )

    hidden_states = np.stack(hidden_list, axis=0).astype(np.float32)  # (N, d)
    if hidden_states.shape[0] != n:
        raise RuntimeError(
            f"EXTRACTION_MISMATCH: expected {n} hidden states, got "
            f"{hidden_states.shape[0]} for benchmark {labels.benchmark}."
        )

    return HiddenStateExtraction(
        benchmark=labels.benchmark,
        q_ids=np.asarray(labels.q_ids, dtype=np.int64),
        hidden_states=hidden_states,
        correctness=np.asarray(labels.correctness, dtype=np.bool_),
        layer_idx=LAYER_IDX_FINAL,
        d=int(hidden_states.shape[1]),
    )


def save_hidden_states_cache(
    extractions: dict[str, HiddenStateExtraction], path: str
) -> None:
    """Persist per-benchmark extractions to a single .npz file."""
    out: dict[str, np.ndarray] = {}
    for bench, ext in extractions.items():
        out[f"{bench}__q_ids"] = ext.q_ids
        out[f"{bench}__hidden_states"] = ext.hidden_states
        out[f"{bench}__correctness"] = ext.correctness
        out[f"{bench}__layer_idx"] = np.asarray(ext.layer_idx, dtype=np.int64)
        out[f"{bench}__d"] = np.asarray(ext.d, dtype=np.int64)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **out)


def load_hidden_states_cache(path: str) -> dict[str, HiddenStateExtraction]:
    """Load per-benchmark extractions from a .npz file produced by save_*."""
    cache_path = Path(path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Hidden-state cache not found: {cache_path}. "
            f"Run --extract-only first or default --run to populate."
        )
    npz = np.load(cache_path, allow_pickle=False)
    extractions: dict[str, HiddenStateExtraction] = {}
    for bench in BENCHMARKS:
        for suffix in ("q_ids", "hidden_states", "correctness", "layer_idx", "d"):
            key = f"{bench}__{suffix}"
            if key not in npz.files:
                raise SchemaMismatchError(
                    f"SCHEMA_MISMATCH: cache {cache_path} missing key {key!r}."
                )
        hidden_states = npz[f"{bench}__hidden_states"]
        if hidden_states.ndim != 2 or hidden_states.shape[0] != PINNED_N:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} key "
                f"'{bench}__hidden_states' has shape {hidden_states.shape}, "
                f"expected ({PINNED_N}, d)."
            )
        extractions[bench] = HiddenStateExtraction(
            benchmark=bench,
            q_ids=npz[f"{bench}__q_ids"],
            hidden_states=hidden_states.astype(np.float32),
            correctness=npz[f"{bench}__correctness"].astype(np.bool_),
            layer_idx=int(npz[f"{bench}__layer_idx"]),
            d=int(npz[f"{bench}__d"]),
        )
    return extractions
