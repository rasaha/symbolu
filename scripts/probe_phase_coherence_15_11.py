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


# ===========================================================================
# §15.11 Chunk I-3 — Phase-coherence formula, F aggregation, AUC,
# selective-prediction κ@α, cascade classifier with direction gate.
#
# Formula (PINNED per §15.11 design-doc Chunk 2):
#   For each pair of layers (i, j):
#     C[i, j] = (1/W) · Σ_{k=1}^{1791} cos(φ_i[k] - φ_j[k])
#   where φ_i[k] = angle(rfft(h_i)[k]) and W = 1791.
#
# Vectorized identity (used in the implementation for speed and
# numerical stability):
#   cos(a - b) = cos(a)·cos(b) + sin(a)·sin(b)
#   ⇒ C = (A · A^T + B · B^T) / W, where
#     A[i, k] = cos(φ_i[k]),  B[i, k] = sin(φ_i[k]),
#     A and B are each shape (n_layers, W).
# This produces an exact equivalent result without an explicit
# pairwise loop over (i, j) and (i, j) is full 29x29.
# ===========================================================================


def _lazy_import_sklearn():
    """Lazy import of sklearn (only roc_auc_score is needed for §15.11)."""
    try:
        from sklearn.metrics import roc_auc_score  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.11 phase-coherence probe requires scikit-learn for "
            "roc_auc_score. Install before running."
        ) from exc
    from sklearn.metrics import roc_auc_score

    return roc_auc_score


def compute_phase_coherence_matrix(
    hidden_states_per_question: np.ndarray,
) -> np.ndarray:
    """Compute the 29x29 phase-coherence matrix C for one question.

    Args:
        hidden_states_per_question: shape (n_layers, d) = (29, 3584),
            real-valued layer-i last-token hidden state per row.

    Returns:
        C: shape (29, 29), real symmetric, C[i,i] = 1, C[i,j] ∈ [-1, +1].
    """
    if hidden_states_per_question.ndim != 2:
        raise ValueError(
            f"expected 2-D hidden states (n_layers, d); got shape "
            f"{hidden_states_per_question.shape}"
        )
    n_layers, d = hidden_states_per_question.shape
    if n_layers != N_LAYERS or d != HIDDEN_DIM:
        raise ValueError(
            f"expected shape ({N_LAYERS}, {HIDDEN_DIM}); got "
            f"({n_layers}, {d})"
        )

    # rfft along the hidden dim → (n_layers, 1793) complex.
    H = np.fft.rfft(hidden_states_per_question.astype(np.float64), axis=1)
    # Bins used: k=1..1791 (exclude DC k=0 and Nyquist k=1792).
    H_used = H[:, BIN_RANGE_USED[0] : BIN_RANGE_USED[1]]  # (n_layers, W)
    if H_used.shape[1] != W:
        raise RuntimeError(
            f"FFT_BIN_MISMATCH: got W={H_used.shape[1]}, expected {W}."
        )
    phi = np.angle(H_used)  # (n_layers, W)
    cos_phi = np.cos(phi)
    sin_phi = np.sin(phi)
    # C[i,j] = (1/W) · Σ_k [cos(φ_i[k]) cos(φ_j[k]) + sin(φ_i[k]) sin(φ_j[k])]
    C = (cos_phi @ cos_phi.T + sin_phi @ sin_phi.T) / float(W)
    # Numerical hygiene: clip to [-1, +1] (rounding can push diagonal
    # imperceptibly outside that range).
    C = np.clip(C, -1.0, 1.0)
    return C


def aggregate_F(C: np.ndarray) -> float:
    """Aggregate the 29x29 coherence matrix into a single scalar F.

    F = mean over the upper-triangular off-diagonal entries (i < j).
    """
    if C.shape != (N_LAYERS, N_LAYERS):
        raise ValueError(
            f"C must be shape ({N_LAYERS},{N_LAYERS}); got {C.shape}"
        )
    iu = np.triu_indices(N_LAYERS, k=1)
    off_diag = C[iu]
    if off_diag.size != N_OFF_DIAG_ENTRIES:
        raise RuntimeError(
            f"OFF_DIAG_COUNT_MISMATCH: got {off_diag.size}, expected "
            f"{N_OFF_DIAG_ENTRIES}."
        )
    return float(off_diag.mean())


def coherence_matrix_summary(C: np.ndarray) -> CoherenceMatrixSummary:
    """Min/mean/max/std of the 406 upper-triangular off-diagonal entries."""
    iu = np.triu_indices(N_LAYERS, k=1)
    off_diag = C[iu]
    return CoherenceMatrixSummary(
        off_diag_min=float(off_diag.min()),
        off_diag_mean=float(off_diag.mean()),
        off_diag_max=float(off_diag.max()),
        off_diag_std=float(off_diag.std(ddof=1)) if off_diag.size > 1 else 0.0,
        n_off_diag_entries=int(off_diag.size),
    )


def compute_F_per_question(
    extraction: HiddenStateExtraction,
) -> tuple[np.ndarray, CoherenceMatrixSummary]:
    """Compute F for all N questions of a benchmark.

    Returns:
        F: shape (N,) float64, one phase-coherence scalar per question.
        agg_summary: CoherenceMatrixSummary computed over the *aggregate*
            of all per-question off-diagonal entries (N · 406 values).
            Useful as a single sanity check across the run.
    """
    n = extraction.hidden_states.shape[0]
    F = np.full(n, np.nan, dtype=np.float64)
    all_off_diag: list[np.ndarray] = []
    iu = np.triu_indices(N_LAYERS, k=1)
    for q in range(n):
        C = compute_phase_coherence_matrix(extraction.hidden_states[q])
        F[q] = float(C[iu].mean())
        all_off_diag.append(C[iu])
    if np.isnan(F).any():
        raise RuntimeError(
            f"PROBE_INTERNAL: F contains NaN for benchmark "
            f"{extraction.benchmark}."
        )
    aggregate = np.concatenate(all_off_diag)
    agg_summary = CoherenceMatrixSummary(
        off_diag_min=float(aggregate.min()),
        off_diag_mean=float(aggregate.mean()),
        off_diag_max=float(aggregate.max()),
        off_diag_std=float(aggregate.std(ddof=1)) if aggregate.size > 1 else 0.0,
        n_off_diag_entries=int(N_OFF_DIAG_ENTRIES),
    )
    return F, agg_summary


# ---------------------------------------------------------------------------
# Selective-prediction κ@α (mirrors §15.10's _selective_kappa_at_alpha).
# ---------------------------------------------------------------------------


def _selective_kappa_at_alpha(
    score: np.ndarray, y: np.ndarray, alpha: float, pi: float
) -> tuple[float, float, dict]:
    """κ@α: max coverage with conditional accuracy ≥ α at threshold τ*.

    score = F (higher → admit; per §15.11's BCVF-faithful direction).
    """
    n = len(score)
    if n != len(y):
        raise ValueError("score and y length mismatch")
    thresholds = sorted(set([float(score.min() - 1.0)] + [float(v) for v in score]))
    best_kappa = 0.0
    operating_point: dict = {
        "alpha": float(alpha),
        "pi": float(pi),
        "tau_star": float("nan"),
        "kappa_at_alpha": 0.0,
        "coverage_at_tau_star": 0.0,
        "conditional_accuracy_at_tau_star": float("nan"),
        "n_admitted_at_tau_star": 0,
        "eligible": False,
    }
    for tau in thresholds:
        admitted = score >= tau
        n_adm = int(admitted.sum())
        if n_adm < N_MIN:
            continue
        cond_acc = float(y[admitted].mean())
        if cond_acc < alpha:
            continue
        coverage = n_adm / n
        if coverage > best_kappa:
            best_kappa = coverage
            operating_point.update(
                tau_star=float(tau),
                kappa_at_alpha=float(coverage),
                coverage_at_tau_star=float(coverage),
                conditional_accuracy_at_tau_star=float(cond_acc),
                n_admitted_at_tau_star=int(n_adm),
                eligible=True,
            )
    return best_kappa, operating_point["tau_star"], operating_point


# ---------------------------------------------------------------------------
# Per-benchmark phase-coherence run.
# ---------------------------------------------------------------------------


def run_phase_coherence_for_benchmark(
    extraction: HiddenStateExtraction,
) -> PhaseCoherenceResult:
    """Compute F per question, AUC, ΔAUC, selective-prediction operating points."""
    roc_auc_score = _lazy_import_sklearn()

    bench = extraction.benchmark
    y = extraction.correctness.astype(np.int64)
    n = y.shape[0]
    if n != PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: extraction for {bench} has N={n}, expected "
            f"{PINNED_N}."
        )
    n_correct = int(y.sum())
    n_wrong = int(n - n_correct)
    pi_observed = float(n_correct / n)

    F, agg_summary = compute_F_per_question(extraction)

    auc_phase = float(roc_auc_score(y, F))
    auc_baseline = ENTROPY_BASELINE_AUC
    dauc_phase = auc_phase - auc_baseline
    auc_supervised_phase_1 = SUPERVISED_AUC_PER_BENCHMARK_PHASE_1[bench]
    dauc_phase_vs_supervised = auc_phase - auc_supervised_phase_1
    direction_held = bool(auc_phase >= DIRECTION_GATE_THRESHOLD)

    # Selective-prediction at pinned alphas.
    alphas = ALPHA_TARGETS_PER_BENCHMARK[bench]
    operating_points: list[dict] = []
    primary_kappa = 0.0
    primary_tau = float("nan")
    pi_pinned = PINNED_PI[bench]
    for alpha in alphas:
        kappa, tau, op = _selective_kappa_at_alpha(F, y, alpha, pi_pinned)
        operating_points.append(op)
        if math.isclose(alpha, ALPHA_PRIMARY, abs_tol=1e-9):
            primary_kappa = kappa
            primary_tau = tau

    if not any(
        math.isclose(op["alpha"], ALPHA_PRIMARY, abs_tol=1e-9)
        for op in operating_points
    ):
        kappa, tau, op = _selective_kappa_at_alpha(F, y, ALPHA_PRIMARY, pi_pinned)
        operating_points.append(op)
        primary_kappa = kappa
        primary_tau = tau

    return PhaseCoherenceResult(
        benchmark=bench,
        n_questions=n,
        n_correct=n_correct,
        n_wrong=n_wrong,
        pi_observed=pi_observed,
        auc_phase=auc_phase,
        auc_baseline=auc_baseline,
        dauc_phase=dauc_phase,
        auc_supervised_phase_1=auc_supervised_phase_1,
        dauc_phase_vs_supervised=dauc_phase_vs_supervised,
        direction_held=direction_held,
        f_per_question=tuple(float(v) for v in F),
        coherence_matrix_summary=agg_summary,
        operating_points=tuple(operating_points),
        kappa_at_alpha_primary=primary_kappa,
        tau_star_at_alpha_primary=primary_tau,
    )


# ---------------------------------------------------------------------------
# §15.11 cascade classifier with direction gate (PINNED per design-doc Chunk 4).
# ---------------------------------------------------------------------------


def classify_cascade_phase(
    auc_halueval: float,
    auc_truthfulqa: float,
    dauc_halueval: float,
    dauc_truthfulqa: float,
) -> CascadeVerdict:
    """Apply §15.11 cascade. Direction gate first, then STRONG/PARTIAL.

    Step 1: direction gate. If either AUC < 0.5 → NO_MATERIAL automatic.
    Step 2: STRONG. Both AUC ≥ 0.75 AND both ΔAUC ≥ +0.05.
    Step 3: PARTIAL. Not STRONG, AND (any AUC ≥ 0.66) AND (any ΔAUC > 0).
    Step 4: NO_MATERIAL (default).
    """
    direction_held_h = bool(auc_halueval >= DIRECTION_GATE_THRESHOLD)
    direction_held_t = bool(auc_truthfulqa >= DIRECTION_GATE_THRESHOLD)

    # Step 1: direction gate.
    if not (direction_held_h and direction_held_t):
        rationale = (
            f"NO_MATERIAL (direction gate): wrong-direction failure on at "
            f"least one benchmark. BCVF-faithful direction (higher F "
            f"predicts correct) did not hold. "
            f"(HaluEval={auc_halueval:.3f} {'≥' if direction_held_h else '<'} 0.5; "
            f"TruthfulQA-MC={auc_truthfulqa:.3f} "
            f"{'≥' if direction_held_t else '<'} 0.5)."
        )
        return CascadeVerdict(
            label="NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE",
            auc_halueval=float(auc_halueval),
            auc_truthfulqa=float(auc_truthfulqa),
            dauc_halueval=float(dauc_halueval),
            dauc_truthfulqa=float(dauc_truthfulqa),
            direction_held_halueval=direction_held_h,
            direction_held_truthfulqa=direction_held_t,
            rationale=rationale,
        )

    aucs = (auc_halueval, auc_truthfulqa)
    dauces = (dauc_halueval, dauc_truthfulqa)

    # Step 2: STRONG check.
    is_strong = all(a >= STRONG_AUC_THRESHOLD for a in aucs) and all(
        d >= STRONG_DELTA_AUC_THRESHOLD for d in dauces
    )
    if is_strong:
        rationale = (
            f"STRONG: AUC ≥ {STRONG_AUC_THRESHOLD} on both "
            f"(HaluEval={auc_halueval:.3f}, TruthfulQA-MC={auc_truthfulqa:.3f}) "
            f"AND ΔAUC ≥ +{STRONG_DELTA_AUC_THRESHOLD} on both "
            f"(ΔHaluEval={dauc_halueval:+.3f}, "
            f"ΔTruthfulQA-MC={dauc_truthfulqa:+.3f})."
        )
        return CascadeVerdict(
            label="STRONG_SIGNAL_IN_PHASE_COHERENCE",
            auc_halueval=float(auc_halueval),
            auc_truthfulqa=float(auc_truthfulqa),
            dauc_halueval=float(dauc_halueval),
            dauc_truthfulqa=float(dauc_truthfulqa),
            direction_held_halueval=direction_held_h,
            direction_held_truthfulqa=direction_held_t,
            rationale=rationale,
        )

    # Step 3: PARTIAL check.
    is_partial = any(a >= PARTIAL_AUC_THRESHOLD for a in aucs) and any(
        d > 0.0 for d in dauces
    )
    if is_partial:
        rationale = (
            f"PARTIAL: not STRONG; AUC ≥ {PARTIAL_AUC_THRESHOLD} on at least "
            f"one benchmark (HaluEval={auc_halueval:.3f}, "
            f"TruthfulQA-MC={auc_truthfulqa:.3f}) AND ΔAUC > 0 on at least "
            f"one benchmark (ΔHaluEval={dauc_halueval:+.3f}, "
            f"ΔTruthfulQA-MC={dauc_truthfulqa:+.3f})."
        )
        return CascadeVerdict(
            label="PARTIAL_SIGNAL_IN_PHASE_COHERENCE",
            auc_halueval=float(auc_halueval),
            auc_truthfulqa=float(auc_truthfulqa),
            dauc_halueval=float(dauc_halueval),
            dauc_truthfulqa=float(dauc_truthfulqa),
            direction_held_halueval=direction_held_h,
            direction_held_truthfulqa=direction_held_t,
            rationale=rationale,
        )

    # Step 4: default.
    rationale = (
        f"NO_MATERIAL: direction held on both benchmarks, but neither STRONG "
        f"nor PARTIAL conditions met. AUCs (HaluEval={auc_halueval:.3f}, "
        f"TruthfulQA-MC={auc_truthfulqa:.3f}) and ΔAUCs "
        f"(ΔHaluEval={dauc_halueval:+.3f}, "
        f"ΔTruthfulQA-MC={dauc_truthfulqa:+.3f}) fail the cascade entry "
        f"conditions."
    )
    return CascadeVerdict(
        label="NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE",
        auc_halueval=float(auc_halueval),
        auc_truthfulqa=float(auc_truthfulqa),
        dauc_halueval=float(dauc_halueval),
        dauc_truthfulqa=float(dauc_truthfulqa),
        direction_held_halueval=direction_held_h,
        direction_held_truthfulqa=direction_held_t,
        rationale=rationale,
    )


# ===========================================================================
# §15.11 Chunk I-4a — Interpretation firewall (mirrors §15.10's design).
#
# Case-insensitive substring match for non-§ patterns; literal match for
# §-anchored patterns to preserve precise §-numbering.
# ===========================================================================


def scan_for_forbidden_patterns(text: str) -> list[str]:
    """Return Class-3 forbidden patterns found in `text`.

    Case-insensitive for non-§ patterns; literal (case-sensitive) for
    §-anchored patterns to preserve precise §-numbering.
    """
    found: list[str] = []
    lowered = text.lower()
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        if pattern.startswith("§"):
            if pattern in text:
                found.append(pattern)
        else:
            if pattern.lower() in lowered:
                found.append(pattern)
    return found


def enforce_firewall_or_exit(text: str, output_path: str) -> None:
    """Scan `text`; if any Class-3 forbidden patterns are found, print
    INTERPRETATION_VIOLATION and exit 4 without writing."""
    violations = scan_for_forbidden_patterns(text)
    if violations:
        print(
            f"INTERPRETATION_VIOLATION: refused to write {output_path}.",
            flush=True,
        )
        print("  detected Class-3 forbidden statement(s):", flush=True)
        for v in violations:
            print(f"    - {v!r}", flush=True)
        print(
            "  rewrite the offending sentence(s) to remove the override "
            "language; the §15.11 cascade verdict is binding.",
            flush=True,
        )
        sys.exit(4)


# ===========================================================================
# §15.11 Chunk I-4b — Self-test gate.
#
# Three required sub-tests (per §15.11 design-doc Chunk 5):
#   1. 12 cascade boundary cases.
#   2. Phase-coherence formula smoke test (identical / random / opposite-phase).
#   3. Firewall coverage (26 positive + clean negative).
#
# Any failure exits 3 (SELF_TEST_FAILED).
# ===========================================================================


def _self_test_cascade() -> list[str]:
    """Run all SELF_TEST_CASCADE_CASES; return list of failure messages."""
    failures: list[str] = []
    for i, (auc_h, auc_t, dauc_h, dauc_t, expected) in enumerate(
        SELF_TEST_CASCADE_CASES
    ):
        verdict = classify_cascade_phase(auc_h, auc_t, dauc_h, dauc_t)
        if verdict.label != expected:
            failures.append(
                f"  case {i + 1}: AUC=({auc_h:.3f},{auc_t:.3f}) "
                f"ΔAUC=({dauc_h:+.3f},{dauc_t:+.3f}) → "
                f"got {verdict.label!r}, expected {expected!r}"
            )
    return failures


def _self_test_phase_coherence_formula() -> list[str]:
    """Three pinned formula smoke tests (per §15.11 design-doc Chunk 5).

    1. Two identical hidden states → C[i,j] = 1 (within tolerance).
    2. Two random hidden states (independent normal) → mean |C[i,j]| < 0.1.
    3. Two opposite-phase hidden states (h_b = -h_a) → C[i,j] = -1.

    Each test exercises the full compute_phase_coherence_matrix path.
    """
    failures: list[str] = []
    rng = np.random.default_rng(SEED_ENTROPY)
    base = rng.normal(0, 1, HIDDEN_DIM).astype(np.float32)

    # Test 1: identical → C[i,j] = 1.
    hs_identical = np.tile(base[None, :], (N_LAYERS, 1))
    C_id = compute_phase_coherence_matrix(hs_identical)
    iu = np.triu_indices(N_LAYERS, k=1)
    if not np.allclose(C_id[iu], 1.0, atol=1e-9):
        failures.append(
            f"  identical-layers: max |C[i,j] - 1| on off-diagonal = "
            f"{float(np.max(np.abs(C_id[iu] - 1.0))):.2e} (expect ≤ 1e-9)"
        )

    # Test 2: independent random → mean |C[i,j]| small (large-N law over
    # W=1791 bins; CLT gives std ~ 1/sqrt(W) ≈ 0.024). Threshold 0.1 is
    # a generous 4-sigma envelope.
    hs_rand = rng.normal(0, 1, (N_LAYERS, HIDDEN_DIM)).astype(np.float32)
    C_rand = compute_phase_coherence_matrix(hs_rand)
    mean_abs_off = float(np.mean(np.abs(C_rand[iu])))
    if mean_abs_off >= 0.1:
        failures.append(
            f"  random-layers: mean |C[i,j]| on off-diagonal = "
            f"{mean_abs_off:.4f} (expect < 0.1)"
        )

    # Test 3: opposite-phase (h_b = -h_a). rfft is linear, so phase shifts
    # by exactly π and cos(phi_a - phi_b) = cos(-π) = -1.
    # Construct: layer 0 = base; layers 1..28 = -base.
    hs_opp = np.empty((N_LAYERS, HIDDEN_DIM), dtype=np.float32)
    hs_opp[0] = base
    hs_opp[1:] = -base
    C_opp = compute_phase_coherence_matrix(hs_opp)
    # C[0, j] for j>0 should equal -1; C[i, j] for i,j > 0 should equal +1.
    if not np.allclose(C_opp[0, 1:], -1.0, atol=1e-9):
        failures.append(
            f"  opposite-phase: max |C[0, 1:] - (-1)| = "
            f"{float(np.max(np.abs(C_opp[0, 1:] + 1.0))):.2e} (expect ≤ 1e-9)"
        )
    if N_LAYERS > 2 and not np.allclose(C_opp[1:, 1:][np.triu_indices(N_LAYERS - 1, k=1)], 1.0, atol=1e-9):
        failures.append(
            f"  opposite-phase: layers 1..28 should be mutually +1; "
            f"got max deviation "
            f"{float(np.max(np.abs(C_opp[1:, 1:][np.triu_indices(N_LAYERS - 1, k=1)] - 1.0))):.2e}"
        )

    return failures


def _self_test_firewall() -> list[str]:
    """Verify firewall flags all 26 Class-3 patterns + clean text passes."""
    failures: list[str] = []
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        sample = f"Some innocuous text. {pattern} more text."
        if not scan_for_forbidden_patterns(sample):
            failures.append(
                f"  firewall failed to detect pattern: {pattern!r}"
            )
    clean = (
        "The phase-coherence AUC is 0.61 on HaluEval-QA, ΔAUC = -0.05. "
        "The cascade label is NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE by "
        "mechanical readout. The §13.9 hold remains binding. §15.10's "
        "PARTIAL_SIGNAL_IN_Z verdict is preserved."
    )
    if scan_for_forbidden_patterns(clean):
        failures.append(
            "  firewall false-positive on clean text: "
            f"{scan_for_forbidden_patterns(clean)!r}"
        )
    return failures


def run_self_test() -> int:
    """Execute the §15.11 self-test gate; return 0 on success, 3 on failure."""
    print("§15.11 self-test gate", flush=True)
    print(f"  schema_version: {SCHEMA_VERSION}", flush=True)
    print(f"  benchmarks: {BENCHMARKS}", flush=True)
    print(f"  pinned_N: {PINNED_N}", flush=True)
    print(f"  baseline AUCs: {BASELINE_AUC_PER_BENCHMARK}", flush=True)
    print(
        f"  cascade thresholds: STRONG_AUC≥{STRONG_AUC_THRESHOLD}, "
        f"STRONG_dAUC≥+{STRONG_DELTA_AUC_THRESHOLD}, "
        f"PARTIAL_AUC≥{PARTIAL_AUC_THRESHOLD}, "
        f"DIRECTION_GATE={DIRECTION_GATE_THRESHOLD}",
        flush=True,
    )
    print(
        f"  phase-coherence: W={W} (bins {BIN_RANGE_USED[0]}..{BIN_RANGE_USED[1] - 1}); "
        f"n_layers={N_LAYERS}; n_off_diag={N_OFF_DIAG_ENTRIES}",
        flush=True,
    )

    all_failures: list[str] = []

    print("  [1/3] cascade boundary cases (12)...", flush=True)
    cascade_fail = _self_test_cascade()
    if cascade_fail:
        all_failures.append("CASCADE FAILURES:")
        all_failures.extend(cascade_fail)
    else:
        print(
            f"    OK: {len(SELF_TEST_CASCADE_CASES)} boundary cases pass.",
            flush=True,
        )

    print("  [2/3] phase-coherence formula smoke tests (3)...", flush=True)
    formula_fail = _self_test_phase_coherence_formula()
    if formula_fail:
        all_failures.append("FORMULA FAILURES:")
        all_failures.extend(formula_fail)
    else:
        print(
            "    OK: identical→1, random→~0, opposite-phase→-1.",
            flush=True,
        )

    print(
        f"  [3/3] interpretation firewall ({len(CLASS_3_FORBIDDEN_PATTERNS)} patterns)...",
        flush=True,
    )
    firewall_fail = _self_test_firewall()
    if firewall_fail:
        all_failures.append("FIREWALL FAILURES:")
        all_failures.extend(firewall_fail)
    else:
        print(
            f"    OK: firewall flags all {len(CLASS_3_FORBIDDEN_PATTERNS)} "
            f"Class-3 patterns; clean text passes.",
            flush=True,
        )

    if all_failures:
        print("\nSELF_TEST_FAILED:", flush=True)
        for line in all_failures:
            print(line, flush=True)
        return 3
    print("\nSELF_TEST_PASSED — proceed.", flush=True)
    return 0


# ===========================================================================
# §15.11 Chunk I-4c — JSON output writer.
#
# Schema pinned per §15.11 design-doc Chunk 5; schema_version = "15.11".
# ===========================================================================


def _coherence_summary_to_dict(s: CoherenceMatrixSummary) -> dict:
    return {
        "off_diag_min": s.off_diag_min,
        "off_diag_mean": s.off_diag_mean,
        "off_diag_max": s.off_diag_max,
        "off_diag_std": s.off_diag_std,
        "n_off_diag_entries": s.n_off_diag_entries,
    }


def _phase_result_to_dict(pr: PhaseCoherenceResult) -> dict:
    return {
        "benchmark": pr.benchmark,
        "n_questions": pr.n_questions,
        "n_correct": pr.n_correct,
        "n_wrong": pr.n_wrong,
        "pi_observed": pr.pi_observed,
        "auc_phase": pr.auc_phase,
        "auc_baseline": pr.auc_baseline,
        "dauc_phase": pr.dauc_phase,
        "auc_supervised_phase_1": pr.auc_supervised_phase_1,
        "dauc_phase_vs_supervised": pr.dauc_phase_vs_supervised,
        "direction_held": pr.direction_held,
        "f_per_question": list(pr.f_per_question),
        "coherence_matrix_summary": _coherence_summary_to_dict(
            pr.coherence_matrix_summary
        ),
        "selective_prediction_operating_points": list(pr.operating_points),
        "kappa_at_alpha_primary": pr.kappa_at_alpha_primary,
        "tau_star_at_alpha_primary": pr.tau_star_at_alpha_primary,
        "alpha_primary": ALPHA_PRIMARY,
    }


def _cascade_verdict_to_dict(cv: CascadeVerdict) -> dict:
    return {
        "label": cv.label,
        "auc_halueval": cv.auc_halueval,
        "auc_truthfulqa": cv.auc_truthfulqa,
        "dauc_halueval": cv.dauc_halueval,
        "dauc_truthfulqa": cv.dauc_truthfulqa,
        "direction_held_halueval": cv.direction_held_halueval,
        "direction_held_truthfulqa": cv.direction_held_truthfulqa,
        "rationale": cv.rationale,
    }


def write_json_output(outputs: PhaseAuditOutputs, path: str) -> None:
    """Serialize PhaseAuditOutputs to a JSON file (schema_version "15.11")."""
    payload = {
        "alpha_targets_per_benchmark": {
            bench: list(alphas)
            for bench, alphas in ALPHA_TARGETS_PER_BENCHMARK.items()
        },
        "baseline_auc_per_benchmark": BASELINE_AUC_PER_BENCHMARK,
        "cascade_thresholds": {
            "strong_auc": STRONG_AUC_THRESHOLD,
            "strong_delta_auc": STRONG_DELTA_AUC_THRESHOLD,
            "partial_auc": PARTIAL_AUC_THRESHOLD,
            "direction_gate_threshold": DIRECTION_GATE_THRESHOLD,
            "entropy_baseline_auc": ENTROPY_BASELINE_AUC,
        },
        "cascade_verdict": _cascade_verdict_to_dict(outputs.cascade_verdict),
        "extraction_layer": "all_29",
        "halueval_qa": _phase_result_to_dict(outputs.halueval_result),
        "hidden_dim": outputs.hidden_dim,
        "n_layers_used": outputs.n_layers_used,
        "phase_coherence_config": {
            "fft_n": FFT_N,
            "n_freq_bins_total": N_FREQ_BINS_TOTAL,
            "n_freq_bins_used": W,
            "bin_range_excluded": "DC (k=0) and Nyquist (k=1792)",
            "windowing": WINDOWING,
            "detrending": DETRENDING,
            "feature_aggregation": FEATURE_AGGREGATION,
            "direction_convention": DIRECTION_CONVENTION,
        },
        "pinned_N": PINNED_N,
        "pinned_pi": PINNED_PI,
        "qwen_model_id": outputs.qwen_model_id,
        "schema_version": outputs.schema_version,
        "supervised_auc_per_benchmark_phase_1": (
            SUPERVISED_AUC_PER_BENCHMARK_PHASE_1
        ),
        "truthfulqa_mc": _phase_result_to_dict(outputs.truthfulqa_result),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


# ===========================================================================
# §15.11 Chunk I-4d — Markdown rendering + firewall-scanned writer.
#
# 8-section structure pinned per §15.11 design-doc Chunk 5.
# ===========================================================================


def _format_operating_points_table(ops: tuple[dict, ...]) -> str:
    lines = [
        "| α | τ* | κ@α | coverage | cond. acc. | n_admitted | eligible |",
        "|---|----|-----|----------|------------|------------|----------|",
    ]
    for op in ops:
        tau_str = (
            f"{op['tau_star']:.4f}"
            if not math.isnan(op.get("tau_star", float("nan")))
            else "—"
        )
        cond_str = (
            f"{op['conditional_accuracy_at_tau_star']:.3f}"
            if not math.isnan(
                op.get("conditional_accuracy_at_tau_star", float("nan"))
            )
            else "—"
        )
        lines.append(
            f"| {op['alpha']:.2f} | {tau_str} | {op['kappa_at_alpha']:.3f} | "
            f"{op['coverage_at_tau_star']:.3f} | {cond_str} | "
            f"{op['n_admitted_at_tau_star']} | "
            f"{'yes' if op['eligible'] else 'no'} |"
        )
    return "\n".join(lines)


def render_markdown_report(outputs: PhaseAuditOutputs) -> str:
    """Render the §15.11 markdown report. Output is firewall-scanned by
    the caller before write."""
    cv = outputs.cascade_verdict
    h = outputs.halueval_result
    t = outputs.truthfulqa_result
    base = ENTROPY_BASELINE_AUC
    sup_h = SUPERVISED_AUC_PER_BENCHMARK_PHASE_1["halueval_qa"]
    sup_t = SUPERVISED_AUC_PER_BENCHMARK_PHASE_1["truthfulqa_mc"]
    prompt_repr = PROMPT_FORMAT.replace("\n", "\\n")

    lines: list[str] = []

    # Section 1: header.
    lines.append("# §15.11 Phase 2 — Layer-wise phase-coherence probe (result)\n")
    lines.append(
        f"_Schema version: `{outputs.schema_version}`._  \n"
        f"_Model: `{outputs.qwen_model_id}`; "
        f"layers used: {outputs.n_layers_used} (embedding + 28 transformer); "
        f"hidden dim: `{outputs.hidden_dim}`; "
        f"FFT bins used: W={W} of {N_FREQ_BINS_TOTAL} (DC and Nyquist excluded); "
        f"prompt format: `{prompt_repr}`._\n"
    )

    # Section 2: cascade verdict.
    lines.append("## Cascade verdict (mechanical readout)\n")
    lines.append(f"**Label:** `{cv.label}`\n")
    lines.append(f"**Rationale:** {cv.rationale}\n")
    lines.append(
        "| benchmark | phase AUC | §13.10 baseline | ΔAUC vs §13.10 | "
        "§15.10 supervised | ΔAUC vs §15.10 | direction held |\n"
        "|---|---|---|---|---|---|---|\n"
        f"| HaluEval-QA | {cv.auc_halueval:.3f} | {base:.3f} | "
        f"{cv.dauc_halueval:+.3f} | {sup_h:.3f} | "
        f"{(cv.auc_halueval - sup_h):+.3f} | "
        f"{'yes' if cv.direction_held_halueval else 'no'} |\n"
        f"| TruthfulQA-MC | {cv.auc_truthfulqa:.3f} | {base:.3f} | "
        f"{cv.dauc_truthfulqa:+.3f} | {sup_t:.3f} | "
        f"{(cv.auc_truthfulqa - sup_t):+.3f} | "
        f"{'yes' if cv.direction_held_truthfulqa else 'no'} |\n"
    )

    # Sections 3 & 4: per-benchmark probe details.
    for label, pr, sup in (
        ("HaluEval-QA", h, sup_h),
        ("TruthfulQA-MC", t, sup_t),
    ):
        s = pr.coherence_matrix_summary
        lines.append(f"## Probe details — {label}\n")
        lines.append(
            f"- N questions: {pr.n_questions} "
            f"(correct: {pr.n_correct}, wrong: {pr.n_wrong})\n"
            f"- π observed: {pr.pi_observed:.3f} "
            f"(pinned: {PINNED_PI[pr.benchmark]:.3f})\n"
            f"- Phase-coherence AUC: **{pr.auc_phase:.3f}** "
            f"(§13.10 baseline: {base:.3f}; "
            f"ΔAUC vs §13.10: {pr.dauc_phase:+.3f})\n"
            f"- §15.10 supervised AUC (disclosure): {sup:.3f} "
            f"(ΔAUC vs §15.10: {pr.dauc_phase_vs_supervised:+.3f})\n"
            f"- Direction held (AUC ≥ 0.5): "
            f"**{'yes' if pr.direction_held else 'no'}**\n"
            f"- Coherence matrix summary (over {s.n_off_diag_entries} "
            f"off-diagonal entries × {pr.n_questions} questions):\n"
            f"  - off-diagonal min:  {s.off_diag_min:+.4f}\n"
            f"  - off-diagonal mean: {s.off_diag_mean:+.4f}\n"
            f"  - off-diagonal max:  {s.off_diag_max:+.4f}\n"
            f"  - off-diagonal std:  {s.off_diag_std:.4f}\n"
        )
        lines.append("**Selective-prediction operating points (disclosure only):**\n")
        lines.append(_format_operating_points_table(pr.operating_points))
        lines.append("")

    # Section 5: pinned configuration.
    lines.append("## Pinned configuration (§15.11 §0.8-binding)\n")
    lines.append(
        f"- **Model:** `{outputs.qwen_model_id}`; all "
        f"{outputs.n_layers_used} per-layer last-token hidden states "
        f"(embedding + 28 transformer layers).\n"
        f"- **Prompt format:** `{prompt_repr}` "
        f"(matches §15.10 PROMPT_FORMAT).\n"
        f"- **FFT:** `numpy.fft.rfft` along hidden dim "
        f"(N={FFT_N} → {N_FREQ_BINS_TOTAL} complex bins); "
        f"used bins k ∈ [{BIN_RANGE_USED[0]}, {BIN_RANGE_USED[1] - 1}] "
        f"(W={W}; excludes DC k=0 and Nyquist k={FFT_N // 2}).\n"
        f"- **Windowing:** {WINDOWING}.\n"
        f"- **Detrending:** {DETRENDING}.\n"
        f"- **Coherence formula:** "
        f"C[i, j] = (1/W) · Σ_k cos(φ_i[k] − φ_j[k]).\n"
        f"- **Feature aggregation:** {FEATURE_AGGREGATION}.\n"
        f"- **Direction convention:** {DIRECTION_CONVENTION}.\n"
        f"- **Cascade thresholds:** STRONG AUC≥{STRONG_AUC_THRESHOLD} "
        f"AND ΔAUC≥+{STRONG_DELTA_AUC_THRESHOLD} (both benchmarks); "
        f"PARTIAL AUC≥{PARTIAL_AUC_THRESHOLD} AND ΔAUC>0 (at least one); "
        f"otherwise NO_MATERIAL. Direction gate: AUC<{DIRECTION_GATE_THRESHOLD} "
        f"on either benchmark → NO_MATERIAL automatic.\n"
        f"- **Selective-prediction floor:** N_MIN={N_MIN}; primary "
        f"alpha = {ALPHA_PRIMARY}.\n"
    )

    # Section 6: caveats.
    lines.append("## Caveats (§0.8-disclosed)\n")
    lines.append(
        "- **Single mechanism within the phase-coherence class.** This "
        "tests ONE phase-coherence formula: layer-wise, mean off-diagonal, "
        "BCVF-faithful direction. A negative result rules out THIS "
        "instantiation; sample-wise (multi-decode), paraphrase-wise "
        "(multi-prompt), and alternative aggregations remain untested but "
        "known.\n"
        "- **Layer-wise was selected over sample-wise / paraphrase-wise** "
        "for cost (single forward pass per question) and BCVF-analog "
        "cleanness (layers as N streams). It is not claimed to be the most "
        "powerful instantiation.\n"
        "- **Direction is pinned BCVF-faithful (higher F predicts correct).** "
        "Wrong-direction outcomes count as failures; no sign-flip rescue.\n"
        "- **N = 100 per benchmark** (matches §15.10/§13.10). AUC standard "
        "error at AUC ≈ 0.66 with N=100 is ~0.05–0.06; bands at 0.66 and "
        "0.75 are hit/miss-able by sampling noise.\n"
        "- **Single model size: Qwen2.5-7B-Instruct.** Does not speak to "
        "scaling at 13B / 32B / 70B.\n"
        "- **Inherited from §15.10:** prompt-format vs §13.10 labeling "
        f"regime (pinned `{prompt_repr}` regardless of how §13.10 generated "
        "labels); question-text source (dump field if present, else HF "
        "dataset by `q_idx`).\n"
        "- **sklearn API surface (precautionary).** Module-level filter "
        "for the `penalty` FutureWarning is installed even though §15.11 "
        "uses only `roc_auc_score` (no LogisticRegression).\n"
    )

    # Section 7: cross-phase comparison (disclosure only).
    lines.append("## Cross-phase comparison (disclosure only)\n")
    lines.append(
        "Phase 1 (§15.10) verdict-of-record: `PARTIAL_SIGNAL_IN_Z` "
        "(HaluEval-QA AUC=0.6686, ΔAUC=+0.008; TruthfulQA-MC AUC=0.6224, "
        "ΔAUC=−0.039 vs §13.10 entropy baseline 0.661).  \n"
        f"Phase 2 (§15.11) cascade outcome: `{cv.label}` "
        f"(HaluEval-QA AUC={cv.auc_halueval:.3f}, ΔAUC={cv.dauc_halueval:+.3f}; "
        f"TruthfulQA-MC AUC={cv.auc_truthfulqa:.3f}, ΔAUC={cv.dauc_truthfulqa:+.3f} "
        "vs the same baseline).  \n"
        "This subsection is disclosure only and does not enter either "
        "phase's cascade decision. Both verdicts are independent §0.8-"
        "binding mechanical readouts; neither modifies the other.\n"
    )

    # Section 8: audit-trail integrity.
    lines.append("## Audit-trail integrity\n")
    lines.append(
        "This result is a mechanical readout of the §15.11 cascade applied "
        "to the per-question phase-coherence scalar F over Qwen-7B's 29 "
        "per-layer last-token hidden states. Per §0.8 discipline, the "
        "cascade label is binding regardless of any post-hoc "
        "interpretation. §15.11 outputs do NOT modify any "
        "§13/§14/§15.x verdict-of-record (including §13.9's hold and "
        "§15.10's `PARTIAL_SIGNAL_IN_Z`); those are preserved. The "
        "interpretation firewall scanned this document for "
        f"{len(CLASS_3_FORBIDDEN_PATTERNS)} Class-3 forbidden statements "
        "before write.\n"
    )

    return "\n".join(lines)


def write_markdown_output(outputs: PhaseAuditOutputs, path: str) -> None:
    """Render markdown, run interpretation firewall, then write."""
    text = render_markdown_report(outputs)
    enforce_firewall_or_exit(text, path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)


# ===========================================================================
# §15.11 Chunk I-5 — main() orchestration + CLI.
#
# Modes:
#   --self-test    : run gate only, exit 0/3
#   --extract-only : labels + Qwen-7B all-29-layer forward pass + .npz cache
#   --probe-only   : load .npz cache + phase-coherence + write outputs
#   (default)      : self-test → extract (or load cache) → probe → write
#
# Exit codes:
#   0  success
#   2  CLI / argument error (handled by argparse)
#   3  SELF_TEST_FAILED
#   4  INTERPRETATION_VIOLATION
#   5  SCHEMA_MISMATCH (label dump or cache)
#   6  EXTRACTION_FAILED (torch / transformers stack error)
#   7  PROBE_FAILED (numpy / sklearn / NaN in F)
# ===========================================================================


def _run_extraction(verbose: bool = True) -> dict[str, HiddenStateExtraction]:
    """Load labels + run Qwen-7B all-29-layer forward pass per benchmark."""
    extractions: dict[str, HiddenStateExtraction] = {}
    torch, AutoModelForCausalLM, AutoTokenizer = _lazy_import_torch_and_transformers()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if verbose:
        print(f"  device: {device}", flush=True)
        print(f"  loading tokenizer + model: {QWEN_MODEL_ID}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_MODEL_ID,
        torch_dtype=torch.float16,
        output_hidden_states=True,
    ).to(device)
    model.eval()

    for bench in BENCHMARKS:
        if verbose:
            print(f"  loading labels: {bench}", flush=True)
        labels = load_benchmark_labels(bench)
        if verbose:
            print(
                f"  extracting all-{N_LAYERS}-layer hidden states: {bench} "
                f"(N={len(labels.questions)})",
                flush=True,
            )
        ext = extract_hidden_states_all_layers(
            labels, model=model, tokenizer=tokenizer, device=device
        )
        extractions[bench] = ext
        if verbose:
            print(
                f"    {bench}: hidden_states shape={ext.hidden_states.shape}, "
                f"d={ext.d}, n_layers={ext.n_layers}",
                flush=True,
            )
    return extractions


def _run_probes(
    extractions: dict[str, HiddenStateExtraction],
) -> PhaseAuditOutputs:
    """Run phase coherence per benchmark; classify cascade; return outputs."""
    pr_h = run_phase_coherence_for_benchmark(extractions["halueval_qa"])
    pr_t = run_phase_coherence_for_benchmark(extractions["truthfulqa_mc"])
    cv = classify_cascade_phase(
        pr_h.auc_phase, pr_t.auc_phase, pr_h.dauc_phase, pr_t.dauc_phase
    )

    if extractions["halueval_qa"].d != extractions["truthfulqa_mc"].d:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: hidden_dim differs across benchmarks: "
            f"HaluEval={extractions['halueval_qa'].d}, "
            f"TruthfulQA-MC={extractions['truthfulqa_mc'].d}."
        )
    if (
        extractions["halueval_qa"].n_layers
        != extractions["truthfulqa_mc"].n_layers
    ):
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: n_layers differs across benchmarks: "
            f"HaluEval={extractions['halueval_qa'].n_layers}, "
            f"TruthfulQA-MC={extractions['truthfulqa_mc'].n_layers}."
        )

    return PhaseAuditOutputs(
        schema_version=SCHEMA_VERSION,
        halueval_result=pr_h,
        truthfulqa_result=pr_t,
        cascade_verdict=cv,
        n_layers_used=extractions["halueval_qa"].n_layers,
        hidden_dim=extractions["halueval_qa"].d,
        qwen_model_id=QWEN_MODEL_ID,
    )


def _print_verdict_banner(outputs: PhaseAuditOutputs) -> None:
    """Emit a one-screen mechanical-readout banner."""
    cv = outputs.cascade_verdict
    print("", flush=True)
    print("=" * 76, flush=True)
    print(f"§15.11 cascade verdict: {cv.label}", flush=True)
    print("-" * 76, flush=True)
    print(
        f"  HaluEval-QA   AUC = {cv.auc_halueval:.3f}  "
        f"(baseline {ENTROPY_BASELINE_AUC:.3f}; "
        f"ΔAUC {cv.dauc_halueval:+.3f}; "
        f"direction_held={'yes' if cv.direction_held_halueval else 'no'})",
        flush=True,
    )
    print(
        f"  TruthfulQA-MC AUC = {cv.auc_truthfulqa:.3f}  "
        f"(baseline {ENTROPY_BASELINE_AUC:.3f}; "
        f"ΔAUC {cv.dauc_truthfulqa:+.3f}; "
        f"direction_held={'yes' if cv.direction_held_truthfulqa else 'no'})",
        flush=True,
    )
    print(
        f"  §15.10 supervised AUCs (disclosure): "
        f"HaluEval={SUPERVISED_AUC_PER_BENCHMARK_PHASE_1['halueval_qa']:.4f}; "
        f"TruthfulQA-MC={SUPERVISED_AUC_PER_BENCHMARK_PHASE_1['truthfulqa_mc']:.4f}",
        flush=True,
    )
    print("-" * 76, flush=True)
    print(f"  rationale: {cv.rationale}", flush=True)
    print("=" * 76, flush=True)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="probe_phase_coherence_15_11",
        description=(
            "§15.11 Phase 2 — layer-wise phase-coherence probe over Qwen-7B's "
            "29 per-layer last-token hidden states. Single-shot, pinned "
            "configuration, mechanical readout."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Run self-test gate only (12 cascade boundary cases + 3 phase-"
            "coherence formula smoke tests + 26-pattern firewall)."
        ),
    )
    mode.add_argument(
        "--extract-only",
        action="store_true",
        help=(
            "Run all-29-layer hidden-state extraction only; write .npz cache. "
            "Skips probe + outputs."
        ),
    )
    mode.add_argument(
        "--probe-only",
        action="store_true",
        help=(
            "Run phase-coherence probe from existing .npz cache; skip "
            "extraction. Self-test gate still runs first."
        ),
    )
    p.add_argument(
        "--cache-path",
        default=HIDDEN_STATES_CACHE_PATH,
        help=(
            f"Path to all-layer hidden-states .npz cache "
            f"(default: {HIDDEN_STATES_CACHE_PATH})"
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
    p.add_argument(
        "--force-extract",
        action="store_true",
        help=(
            "Force re-extraction even if --cache-path exists "
            "(default: skip extraction when cache present)."
        ),
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)

    # Self-test gate is required for every mode except explicit --self-test.
    if args.self_test:
        return run_self_test()

    rc = run_self_test()
    if rc != 0:
        return rc

    cache_path = args.cache_path

    # Extraction phase.
    if args.probe_only:
        print(
            f"\n--probe-only: loading hidden-state cache from {cache_path}",
            flush=True,
        )
        try:
            extractions = load_hidden_states_cache(cache_path)
        except SchemaMismatchError as e:
            print(f"SCHEMA_MISMATCH: {e}", flush=True)
            return 5
        except FileNotFoundError as e:
            print(f"CACHE_MISSING: {e}", flush=True)
            return 5
    else:
        cache_exists = Path(cache_path).exists()
        if cache_exists and not args.force_extract:
            print(
                f"\nCache already present at {cache_path}; "
                f"loading instead of re-extracting "
                f"(use --force-extract to override).",
                flush=True,
            )
            try:
                extractions = load_hidden_states_cache(cache_path)
            except SchemaMismatchError as e:
                print(f"SCHEMA_MISMATCH: {e}", flush=True)
                return 5
        else:
            print(
                "\nExtraction phase — Qwen2.5-7B-Instruct all-29-layer "
                "forward pass.",
                flush=True,
            )
            try:
                extractions = _run_extraction(verbose=True)
            except (ImportError, RuntimeError) as e:
                print(f"EXTRACTION_FAILED: {e}", flush=True)
                return 6
            try:
                save_hidden_states_cache(extractions, cache_path)
                print(f"  cache written: {cache_path}", flush=True)
            except OSError as e:
                print(f"CACHE_WRITE_FAILED: {e}", flush=True)
                return 6

        if args.extract_only:
            print(
                "\n--extract-only: extraction complete; skipping probe.",
                flush=True,
            )
            return 0

    # Probe phase.
    print(
        "\nProbe phase — phase coherence per benchmark "
        "(formula + AUC + cascade).",
        flush=True,
    )
    try:
        outputs = _run_probes(extractions)
    except SchemaMismatchError as e:
        print(f"SCHEMA_MISMATCH: {e}", flush=True)
        return 5
    except RuntimeError as e:
        print(f"PROBE_FAILED: {e}", flush=True)
        return 7
    except ImportError as e:
        print(f"PROBE_FAILED: {e}", flush=True)
        return 7

    # Output phase.
    print("\nOutput phase — JSON + markdown.", flush=True)
    write_json_output(outputs, args.json_out)
    print(f"  wrote: {args.json_out}", flush=True)
    write_markdown_output(outputs, args.md_out)
    print(f"  wrote: {args.md_out}", flush=True)

    _print_verdict_banner(outputs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
