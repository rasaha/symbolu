#!/usr/bin/env python
"""§15.11 Phase 2 — Layer-wise phase-coherence probe (final-resolution sprint).

Pure §0.8-binding implementation per the frozen §15.11 pre-
commitment. Tests whether truth signal is encoded in the
non-linear, multi-scale phase relationship across Qwen-7B's
29 per-layer last-token hidden states — a mechanism class
that §13.10 entropy and §15.10 supervised linear extraction
cannot capture by construction.

Reference: docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md §15.11
(commits 7c20d3b, ec6f667, f0a96a0, dab98cf, 7ba55ee, d59d4e7).

What this script DOES:
  * Loads correctness labels from the existing §13.10 dumps
    (per-question greedy_matches_correct booleans).
  * Optionally extracts ALL 29 layers' last-token hidden
    states from Qwen2.5-7B-Instruct over each question
    prompt `Q: {question}\\nA:` (or loads from a §15.11-
    specific cache if already extracted).
  * For each question, computes the 29x29 phase-coherence
    matrix C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])
    using rfft on each layer's last-token hidden state with
    W = 1791 frequency bins (DC and Nyquist excluded).
  * Aggregates each C matrix into a single scalar F per
    question via mean over the 406 upper-triangular off-
    diagonal entries.
  * Computes AUC(F vs correctness) per benchmark, ΔAUC vs
    §13.10 entropy baseline 0.661, and selective-prediction
    operating points.
  * Applies the §15.11 cascade: direction-gate then STRONG /
    PARTIAL / NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE.
  * Emits JSON + markdown artifacts with §15.7-pattern
    interpretation firewall enforced at write time.

What this script DOES NOT:
  * Re-classify any §13/§14/§15.x verdict-of-record. All
    bands remain binding regardless of §15.11 outputs.
  * Iterate on the formula, the FFT bin range, the layer
    subset, or the feature aggregation. All are pinned per
    the §15.11 pre-commitment; one shot.
  * Sign-flip if AUC < 0.5. The BCVF-faithful direction
    was the pre-committed hypothesis; failing it is a
    failure (NO_MATERIAL automatic), not a sign-flip
    opportunity.
  * Authorize Phase 3 (§15.12). Phase 3 requires its own
    §0.8 commitment.

Inputs (per §15.11):
    docs/experiments/probe_semantic_entropy.json
        (§13.10 TruthfulQA-MC dump; per-question correctness
        labels; first 100 questions used regardless of N status)
    docs/experiments/probe_semantic_entropy_halueval_qa.json
        (§13.10 HaluEval-QA dump; same usage)
    `Qwen/Qwen2.5-7B-Instruct` (cached HF model)
    HaluEval-QA + TruthfulQA-MC datasets (HuggingFace,
    fallback for question text if dump field absent)

Outputs (per §15.11):
    docs/experiments/hidden_states_all_layers_qwen_15_11.npz
        (cached extraction; (N, 29, 3584) per benchmark;
        allows skipping re-extraction)
    docs/experiments/probe_phase_coherence_15_11.json
        (machine-readable result, schema_version "15.11")
    docs/experiments/probe_phase_coherence_15_11.md
        (human-readable report, firewall-scanned at write time)

Usage:
    # Required pre-execution gate.
    python scripts/probe_phase_coherence_15_11.py --self-test

    # Full pipeline (extract + coherence + report).
    python scripts/probe_phase_coherence_15_11.py

    # Extract only (GPU phase; produces .npz cache).
    python scripts/probe_phase_coherence_15_11.py --extract-only

    # Probe only (CPU phase; uses .npz cache).
    python scripts/probe_phase_coherence_15_11.py --probe-only
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# Suppress sklearn FutureWarning for the `penalty` kwarg (mirrors §15.10).
# §15.11 only uses sklearn for roc_auc_score (no LogisticRegression), so
# this filter is precautionary.
warnings.filterwarnings(
    "ignore",
    message=r".*'penalty'.*",
    category=FutureWarning,
)

# ===========================================================================
# §15.11 PINNED CONSTANTS — DO NOT CHANGE during implementation.
# Any change requires a fresh §0.8 amendment to §15.11.
# ===========================================================================

SCHEMA_VERSION = "15.11"

# Target model (pinned per §15.11 spec; matches §15.10).
QWEN_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Benchmarks (pinned).
BENCHMARKS: tuple[str, ...] = ("halueval_qa", "truthfulqa_mc")

# Pinned size per benchmark.
PINNED_N = 100

# §13.10 dumps — used ONLY for correctness labels, first 100 records.
INPUT_S13_10_HALUEVAL = "docs/experiments/probe_semantic_entropy_halueval_qa.json"
INPUT_S13_10_TRUTHFULQA = "docs/experiments/probe_semantic_entropy.json"

# Pinned §13.10 baseline AUCs (per §13.10 verdict-of-record at N=100).
BASELINE_AUC_PER_BENCHMARK: dict[str, float] = {
    "halueval_qa": 0.661,
    "truthfulqa_mc": 0.661,
}
ENTROPY_BASELINE_AUC = 0.661

# §15.10 supervised AUCs (disclosure only; not in cascade).
SUPERVISED_AUC_PER_BENCHMARK_PHASE_1: dict[str, float] = {
    "halueval_qa": 0.6685714285714286,
    "truthfulqa_mc": 0.6224,
}

# Pinned base rates pi (per §13.10 prose; Qwen-greedy accuracy).
PINNED_PI: dict[str, float] = {
    "halueval_qa": 0.300,
    "truthfulqa_mc": 0.250,
}

# Pinned alpha targets per benchmark (matches §15.10).
ALPHA_TARGETS_PER_BENCHMARK: dict[str, tuple[float, ...]] = {
    "halueval_qa": (0.40, 0.50, 0.75),
    "truthfulqa_mc": (0.35, 0.50, 0.75),
}
ALPHA_PRIMARY = 0.50
N_MIN = 10  # selective-prediction floor (matches §15.10)
SEED_ENTROPY = 15  # for any rng calls; no CV in §15.11

# Cascade thresholds per §15.11 (pinned exhaustive partition;
# numerically identical to §15.10).
STRONG_AUC_THRESHOLD = 0.75
STRONG_DELTA_AUC_THRESHOLD = 0.05
PARTIAL_AUC_THRESHOLD = 0.66
DIRECTION_GATE_THRESHOLD = 0.5  # strict (AUC < 0.5 fails)

# Hidden-state extraction config (pinned).
PROMPT_FORMAT = "Q: {question}\nA:"
HIDDEN_DIM = 3584
N_LAYERS = 29  # 1 embedding output + 28 transformer-layer outputs
EXTRACT_DTYPE_INFERENCE = "float16"  # match Qwen2.5-7B's native fp16
EXTRACT_DTYPE_CACHE = "float32"  # cast for portability

# Phase-coherence config (pinned).
FFT_N = HIDDEN_DIM  # 3584
N_FREQ_BINS_TOTAL = FFT_N // 2 + 1  # 1793 (rfft length)
W = 1791  # frequency bins used (exclude DC at k=0 and Nyquist at k=1792)
BIN_RANGE_USED = (1, 1792)  # inclusive lo, exclusive hi → bins 1..1791
WINDOWING = "rectangular (none)"
DETRENDING = "none"
FEATURE_AGGREGATION = "mean over upper-triangular off-diagonal of 29x29 C (406 entries)"
DIRECTION_CONVENTION = "higher F predicts correct (BCVF-faithful)"
N_OFF_DIAG_ENTRIES = (N_LAYERS * (N_LAYERS - 1)) // 2  # 406

# Cache + output paths (pinned).
HIDDEN_STATES_CACHE_PATH = "docs/experiments/hidden_states_all_layers_qwen_15_11.npz"
OUTPUT_JSON_PATH = "docs/experiments/probe_phase_coherence_15_11.json"
OUTPUT_MD_PATH = "docs/experiments/probe_phase_coherence_15_11.md"

# §13.10 dump field names (per §15.1 Amendment 1 pinned schema).
FIELD_QID = "q_idx"
FIELD_CORRECT = "greedy_matches_correct"
FIELD_QUESTION = "question"

# §15.7-style Class-3 forbidden-statement patterns. Inherits §15.10/§15.7
# set (16 patterns) plus §15.11-specific (10 patterns) per design-doc
# Chunk 5 — total 26 patterns.
CLASS_3_FORBIDDEN_PATTERNS: list[str] = [
    # Inherited from §15.10 / §15.7.
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
    "actually STRONG",
    "should be classified as STRONG",
    "actually PARTIAL despite",
    "STRONG despite the cascade",
    # §15.11-specific (10).
    "actually STRONG_SIGNAL_IN_PHASE_COHERENCE despite",
    "should be STRONG_SIGNAL_IN_PHASE_COHERENCE",
    "actually PARTIAL_SIGNAL_IN_PHASE_COHERENCE despite",
    "should be classified as PARTIAL_SIGNAL_IN_PHASE_COHERENCE",
    "the wrong-direction failure should be flipped",
    "the direction gate should be relaxed",
    "the BCVF-faithful direction was wrong",
    "§15.10 PARTIAL is overturned",
    "§15.10 verdict is overturned",
    "§13.10 baseline should be replaced",
]

# Self-test boundary cases for the cascade classifier (per §15.11 design-doc
# Chunk 4). Each entry: (auc_h, auc_t, dauc_h, dauc_t, expected_label).
SELF_TEST_CASCADE_CASES: list[tuple[float, float, float, float, str]] = [
    # 1. STRONG clean.
    (0.80, 0.78, +0.139, +0.119, "STRONG_SIGNAL_IN_PHASE_COHERENCE"),
    # 2. STRONG boundary inclusive (both AUC=0.75; both ΔAUC≥0.05).
    (0.75, 0.75, +0.089, +0.089, "STRONG_SIGNAL_IN_PHASE_COHERENCE"),
    # 3. PARTIAL via auc_h just below STRONG.
    (0.74, 0.78, +0.079, +0.119, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 4. PARTIAL via one benchmark passes both PARTIAL conditions.
    (0.70, 0.62, +0.039, -0.041, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 5. PARTIAL boundary: auc_h = 0.66 inclusive.
    (0.66, 0.55, +0.001, -0.111, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 6. NO_MATERIAL: both AUC < 0.66; both ΔAUC < 0.
    (0.65, 0.65, -0.011, -0.011, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 7. NO_MATERIAL: exact baseline both; ΔAUC = 0 (not > 0).
    (0.661, 0.661, 0.0, 0.0, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 8. NO_MATERIAL via direction gate (auc_h < 0.5).
    (0.49, 0.78, -0.171, +0.119, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 9. NO_MATERIAL via direction gate (both < 0.5).
    (0.45, 0.40, -0.211, -0.261, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 10. PARTIAL via direction gate inclusive (auc_h = 0.5; passes gate).
    (0.50, 0.78, -0.161, +0.119, "PARTIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 11. NO_MATERIAL via direction gate strict (auc_h = 0.499).
    (0.499, 0.80, -0.162, +0.139, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
    # 12. NO_MATERIAL: direction holds but both fail PARTIAL conditions.
    (0.55, 0.55, -0.111, -0.111, "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE"),
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
    """All-29-layer last-token hidden states aligned with labels."""

    benchmark: str
    q_ids: np.ndarray  # int, shape (N,)
    hidden_states: np.ndarray  # float, shape (N, n_layers, d)
    correctness: np.ndarray  # bool, shape (N,)
    n_layers: int
    d: int


@dataclass(frozen=True)
class CoherenceMatrixSummary:
    """Sanity statistics over the 406 upper-triangular off-diagonal C entries."""

    off_diag_min: float
    off_diag_mean: float
    off_diag_max: float
    off_diag_std: float
    n_off_diag_entries: int


@dataclass(frozen=True)
class PhaseCoherenceResult:
    """Per-benchmark phase-coherence probe result."""

    benchmark: str
    n_questions: int
    n_correct: int
    n_wrong: int
    pi_observed: float
    auc_phase: float
    auc_baseline: float  # 0.661
    dauc_phase: float  # auc_phase - auc_baseline
    auc_supervised_phase_1: float  # disclosure only
    dauc_phase_vs_supervised: float  # disclosure only
    direction_held: bool  # auc_phase >= 0.5
    f_per_question: tuple[float, ...]
    coherence_matrix_summary: CoherenceMatrixSummary
    operating_points: tuple[dict, ...]
    kappa_at_alpha_primary: float
    tau_star_at_alpha_primary: float


@dataclass(frozen=True)
class CascadeVerdict:
    """Final §15.11 cascade outcome."""

    label: str  # STRONG_/PARTIAL_/NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE
    auc_halueval: float
    auc_truthfulqa: float
    dauc_halueval: float
    dauc_truthfulqa: float
    direction_held_halueval: bool
    direction_held_truthfulqa: bool
    rationale: str


@dataclass(frozen=True)
class PhaseAuditOutputs:
    """Top-level §15.11 outputs for both benchmarks."""

    schema_version: str
    halueval_result: PhaseCoherenceResult
    truthfulqa_result: PhaseCoherenceResult
    cascade_verdict: CascadeVerdict
    n_layers_used: int
    hidden_dim: int
    qwen_model_id: str


# ===========================================================================
# §15.11 Chunk I-2 — Schema validators, §13.10 label loader (HF fallback),
# all-29-layer hidden-state extraction with .npz caching.
#
# Mirrors §15.10's tightenings F1 (question optional + HF fallback) and
# F2 (duplicate-q_idx check). The extraction differs from §15.10 only
# in that it collects all 29 layers per question instead of layer -1.
# ===========================================================================


class SchemaMismatchError(RuntimeError):
    """Raised when a §13.10 dump or §15.11 cache fails schema validation."""


def _validate_s13_10_dump(payload: object, source_path: str) -> list[dict]:
    """Validate top-level shape of a §13.10 dump and return per-question records.

    Required fields per record: q_idx (int) + greedy_matches_correct (bool).
    The 'question' field is optional (matches §15.7's lighter loader);
    if missing on any record, load_benchmark_labels falls back to the
    HuggingFace dataset by q_idx alignment.

    Duplicate q_idx triggers SCHEMA_MISMATCH (matches §15.7 hardening).
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

    seen_qids: set[int] = set()
    for i, rec in enumerate(records[:PINNED_N]):
        if not isinstance(rec, dict):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} is "
                f"{type(rec).__name__}, expected dict."
            )
        for required in (FIELD_QID, FIELD_CORRECT):
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
        if not isinstance(rec[FIELD_CORRECT], bool):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_CORRECT}' is {type(rec[FIELD_CORRECT]).__name__}, "
                f"expected bool."
            )
        if FIELD_QUESTION in rec and not isinstance(rec[FIELD_QUESTION], str):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QUESTION}' is "
                f"{type(rec[FIELD_QUESTION]).__name__}, expected str."
            )
        qid = int(rec[FIELD_QID])
        if qid in seen_qids:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} duplicate "
                f"q_idx={qid}; ascending alignment would be ambiguous."
            )
        seen_qids.add(qid)
    return records


def _load_questions_from_hf_dataset(
    benchmark: str, q_ids: tuple[int, ...]
) -> tuple[str, ...]:
    """Load question text from HuggingFace dataset by q_idx alignment.

    Mirrors §13.10 producer's enumerate-after-select indexing
    (`scripts/probe_semantic_entropy.py`): q_idx corresponds to row index
    in the first N rows of the benchmark dataset.
    """
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise ImportError(
            "§15.11 question-text fallback requires the `datasets` library. "
            "Either ensure §13.10 dump records contain a 'question' field "
            "or install `datasets` on the runpod."
        ) from exc

    if benchmark == "halueval_qa":
        ds = load_dataset("pminervini/HaluEval", "qa", split="data")
    elif benchmark == "truthfulqa_mc":
        ds = load_dataset("truthful_qa", "multiple_choice", split="validation")
    else:
        raise ValueError(f"Unknown benchmark: {benchmark!r}")

    n_max = max(q_ids) + 1 if q_ids else 0
    if len(ds) < n_max:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: HF dataset for {benchmark} has only "
            f"{len(ds)} rows; need at least {n_max} for q_idx alignment."
        )
    ds = ds.select(range(n_max))
    return tuple(str(ds[int(q_id)]["question"]) for q_id in q_ids)


def load_benchmark_labels(benchmark: str) -> BenchmarkLabels:
    """Load first PINNED_N records from the §13.10 dump for `benchmark`.

    Returns BenchmarkLabels with q_ids/questions/correctness aligned by
    record order in the dump. Question text from dump field if all
    records have it, else HF dataset fallback.
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
            f"Required for §15.11 Phase 2 label loading."
        )

    with dump_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    records = _validate_s13_10_dump(payload, str(dump_path))
    head = records[:PINNED_N]
    q_ids = tuple(int(r[FIELD_QID]) for r in head)
    correctness = tuple(bool(r[FIELD_CORRECT]) for r in head)

    has_dump_questions = all(
        FIELD_QUESTION in r
        and isinstance(r[FIELD_QUESTION], str)
        and r[FIELD_QUESTION]
        for r in head
    )
    if has_dump_questions:
        questions = tuple(str(r[FIELD_QUESTION]) for r in head)
    else:
        print(
            f"  {benchmark}: dump lacks 'question' on at least one record; "
            f"loading question text from HuggingFace dataset by q_idx.",
            flush=True,
        )
        questions = _load_questions_from_hf_dataset(benchmark, q_ids)

    return BenchmarkLabels(
        benchmark=benchmark,
        q_ids=q_ids,
        questions=questions,
        correctness=correctness,
    )


# ---------------------------------------------------------------------------
# All-29-layer hidden-state extraction (Qwen2.5-7B-Instruct forward pass).
# ---------------------------------------------------------------------------


def _lazy_import_torch_and_transformers():
    """Lazy import of torch + transformers; raises with a clear message."""
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.11 hidden-state extraction requires torch + transformers. "
            "Install on the runpod GPU node before --extract-only or "
            "default --run."
        ) from exc
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    return torch, AutoModelForCausalLM, AutoTokenizer


def extract_hidden_states_all_layers(
    labels: BenchmarkLabels,
    *,
    model=None,
    tokenizer=None,
    device: Optional[str] = None,
) -> HiddenStateExtraction:
    """Forward-pass each prompt through Qwen-7B; collect ALL 29 layers'
    last-token hidden states.

    Per question:
      * Build prompt = `Q: {question}\\nA:` (PROMPT_FORMAT).
      * Run forward pass with output_hidden_states=True.
      * out.hidden_states is a tuple of length n_layers + 1 = 29
        (index 0 = embedding output; 1..28 = post-each-layer).
      * For each layer, take the LAST-TOKEN hidden state → R^3584.
      * Stack: per question, shape (29, 3584).

    Stored cast to fp32 for cache portability. Total cache shape per
    benchmark: (100, 29, 3584) → ~41 MB fp32.
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
            output_hidden_states=True,
        ).to(device)
        model.eval()

    n = len(labels.questions)
    per_question: list[np.ndarray] = []
    with torch.no_grad():
        for i, question in enumerate(labels.questions):
            prompt = PROMPT_FORMAT.format(question=question)
            enc = tokenizer(prompt, return_tensors="pt").to(device)
            out = model(**enc, output_hidden_states=True)
            # hidden_states is a tuple of length (n_layers + 1) = 29.
            hs_tuple = out.hidden_states
            if len(hs_tuple) != N_LAYERS:
                raise RuntimeError(
                    f"EXTRACTION_MISMATCH: expected {N_LAYERS} hidden_states "
                    f"layers, got {len(hs_tuple)} for question {i} of "
                    f"benchmark {labels.benchmark}."
                )
            # Per-layer last-token hidden state → (29, 3584).
            stacked = np.stack(
                [
                    h[0, -1, :].detach().to("cpu").float().numpy()
                    for h in hs_tuple
                ],
                axis=0,
            )
            if stacked.shape != (N_LAYERS, HIDDEN_DIM):
                raise RuntimeError(
                    f"EXTRACTION_MISMATCH: question {i} produced shape "
                    f"{stacked.shape}, expected {(N_LAYERS, HIDDEN_DIM)}."
                )
            per_question.append(stacked)
            if (i + 1) % 10 == 0:
                print(
                    f"  [extract:{labels.benchmark}] {i + 1}/{n} questions "
                    f"(all 29 layers)",
                    flush=True,
                )

    hidden_states = np.stack(per_question, axis=0).astype(np.float32)
    if hidden_states.shape != (n, N_LAYERS, HIDDEN_DIM):
        raise RuntimeError(
            f"EXTRACTION_MISMATCH: expected ({n}, {N_LAYERS}, {HIDDEN_DIM}) "
            f"hidden states, got {hidden_states.shape} for benchmark "
            f"{labels.benchmark}."
        )

    return HiddenStateExtraction(
        benchmark=labels.benchmark,
        q_ids=np.asarray(labels.q_ids, dtype=np.int64),
        hidden_states=hidden_states,
        correctness=np.asarray(labels.correctness, dtype=np.bool_),
        n_layers=N_LAYERS,
        d=HIDDEN_DIM,
    )


def save_hidden_states_cache(
    extractions: dict[str, HiddenStateExtraction], path: str
) -> None:
    """Persist per-benchmark all-layer extractions to a single .npz file."""
    out: dict[str, np.ndarray] = {}
    for bench, ext in extractions.items():
        out[f"{bench}__q_ids"] = ext.q_ids
        out[f"{bench}__hidden_states"] = ext.hidden_states
        out[f"{bench}__correctness"] = ext.correctness
        out[f"{bench}__n_layers"] = np.asarray(ext.n_layers, dtype=np.int64)
        out[f"{bench}__d"] = np.asarray(ext.d, dtype=np.int64)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **out)


def load_hidden_states_cache(path: str) -> dict[str, HiddenStateExtraction]:
    """Load per-benchmark all-layer extractions from a .npz file."""
    cache_path = Path(path)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Hidden-state cache not found: {cache_path}. "
            f"Run --extract-only first or default --run to populate."
        )
    npz = np.load(cache_path, allow_pickle=False)
    extractions: dict[str, HiddenStateExtraction] = {}
    for bench in BENCHMARKS:
        for suffix in ("q_ids", "hidden_states", "correctness", "n_layers", "d"):
            key = f"{bench}__{suffix}"
            if key not in npz.files:
                raise SchemaMismatchError(
                    f"SCHEMA_MISMATCH: cache {cache_path} missing key {key!r}."
                )
        hidden_states = npz[f"{bench}__hidden_states"]
        if hidden_states.ndim != 3 or hidden_states.shape[0] != PINNED_N:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} key "
                f"'{bench}__hidden_states' has shape {hidden_states.shape}, "
                f"expected ({PINNED_N}, n_layers, d)."
            )
        n_layers_cached = int(npz[f"{bench}__n_layers"])
        d_cached = int(npz[f"{bench}__d"])
        if n_layers_cached != N_LAYERS or d_cached != HIDDEN_DIM:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {bench} "
                f"n_layers={n_layers_cached} d={d_cached}; "
                f"expected n_layers={N_LAYERS}, d={HIDDEN_DIM}."
            )
        if hidden_states.shape[1] != N_LAYERS or hidden_states.shape[2] != HIDDEN_DIM:
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: cache {cache_path} {bench} "
                f"hidden_states shape {hidden_states.shape}, "
                f"expected (*, {N_LAYERS}, {HIDDEN_DIM})."
            )
        extractions[bench] = HiddenStateExtraction(
            benchmark=bench,
            q_ids=npz[f"{bench}__q_ids"],
            hidden_states=hidden_states.astype(np.float32),
            correctness=npz[f"{bench}__correctness"].astype(np.bool_),
            n_layers=n_layers_cached,
            d=d_cached,
        )
    return extractions
