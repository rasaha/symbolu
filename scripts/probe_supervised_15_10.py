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
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# Targeted suppression of sklearn 1.8+ FutureWarning for the `penalty` kwarg.
# We keep `penalty='l2'` explicit for audit-trail symmetry with the pinned
# PROBE_PENALTY constant; sklearn 1.8 still accepts it (with a warning),
# and sklearn 1.10 will remove it (caught at runtime as TypeError if so).
warnings.filterwarnings(
    "ignore",
    message=r".*'penalty'.*",
    category=FutureWarning,
)

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

    # Required fields per §15.7's lighter loader: q_idx + greedy_matches_correct.
    # The 'question' field was added to the §13.10 producer in commit f2291fc
    # ("§13 audit fixes"); pre-f2291fc dumps lack it. We tolerate that here
    # and let load_benchmark_labels fall back to the HF dataset by q_idx.
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
        # Optional question field: validate type if present.
        if FIELD_QUESTION in rec and not isinstance(rec[FIELD_QUESTION], str):
            raise SchemaMismatchError(
                f"SCHEMA_MISMATCH: {source_path} record {i} field "
                f"'{FIELD_QUESTION}' is "
                f"{type(rec[FIELD_QUESTION]).__name__}, expected str."
            )
        # Duplicate q_idx → ambiguous alignment; abort early (matches §15.7).
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
            "§15.10 question-text fallback requires the `datasets` library. "
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
    record order in the dump. We deliberately do NOT re-sort by q_idx;
    the dump's record order is canonical (matches §15.1/§15.7 convention).

    Question text source: dump's `question` field if present on every
    record (post-§13-audit-fix dumps); else HF dataset by q_idx alignment
    (pre-audit-fix or partial dumps).
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


# ===========================================================================
# §15.10 Chunk I-3 — Linear probe (L2 LogisticRegression), 5-fold stratified
# CV with out-of-fold predictions, AUC + selective-prediction κ@α,
# cascade classifier.
#
# Discipline: probe configuration is pinned (PROBE_PENALTY/PROBE_C/
# PROBE_MAX_ITER/PROBE_SOLVER). No grid search. No alternative architectures.
# Single-shot per §15.10.
# ===========================================================================


def _lazy_import_sklearn():
    """Lazy import of sklearn (StratifiedKFold, LogisticRegression, AUC)."""
    try:
        from sklearn.linear_model import LogisticRegression  # noqa: F401
        from sklearn.metrics import roc_auc_score  # noqa: F401
        from sklearn.model_selection import StratifiedKFold  # noqa: F401
        from sklearn.preprocessing import StandardScaler  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "§15.10 probe requires scikit-learn. Install before running."
        ) from exc
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    return StratifiedKFold, LogisticRegression, StandardScaler, roc_auc_score


def _compute_brier(p: np.ndarray, y: np.ndarray) -> float:
    """Brier score = mean((p - y)^2). Lower is better."""
    return float(np.mean((p - y.astype(np.float64)) ** 2))


def _selective_kappa_at_alpha(
    p: np.ndarray, y: np.ndarray, alpha: float, pi: float
) -> tuple[float, float, dict]:
    """Compute κ@α: max coverage with conditional accuracy ≥ α at the threshold τ*.

    For probe probability p (= P[correct|x]), we sweep candidate thresholds
    over the unique p values; for each τ we admit {i : p_i ≥ τ} and compute:
       coverage = |admitted| / N
       conditional_accuracy = sum(y_i for i in admitted) / |admitted|
       eligible if |admitted| >= N_MIN AND conditional_accuracy >= alpha
    κ@α = best coverage among eligible thresholds; tau* = argmax τ.

    The base-rate-adjusted κ-frame matches §15.x convention: the alpha
    parameter is the *target conditional accuracy* (not the LLR threshold).
    pi is the population correctness rate (only logged, not used in the
    eligibility test, since the eligibility test is on conditional
    accuracy directly).
    """
    n = len(p)
    if n != len(y):
        raise ValueError("p and y length mismatch")
    # Candidate thresholds: every observed p plus 0.0 (admit-all sentinel).
    thresholds = sorted(set([float(0.0)] + [float(v) for v in p]))
    best_kappa = 0.0
    best_tau = float("nan")
    best_cov = 0.0
    best_cond_acc = float("nan")
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
        admitted = p >= tau
        n_adm = int(admitted.sum())
        if n_adm < N_MIN:
            continue
        cond_acc = float(y[admitted].mean())
        if cond_acc < alpha:
            continue
        coverage = n_adm / n
        if coverage > best_kappa:
            best_kappa = coverage
            best_tau = float(tau)
            best_cov = coverage
            best_cond_acc = cond_acc
            operating_point.update(
                tau_star=float(tau),
                kappa_at_alpha=float(coverage),
                coverage_at_tau_star=float(coverage),
                conditional_accuracy_at_tau_star=float(cond_acc),
                n_admitted_at_tau_star=int(n_adm),
                eligible=True,
            )
    return best_kappa, best_tau, operating_point


def run_probe_for_benchmark(extraction: HiddenStateExtraction) -> ProbeResult:
    """Train L2 LogisticRegression with 5-fold stratified CV; collect OOF preds.

    Per §15.10:
      * Penalty L2, C=1.0, lbfgs, max_iter=1000.
      * 5-fold stratified CV (shuffle=True, random_state=SEED_ENTROPY).
      * StandardScaler fit per fold on train, applied to val.
      * OOF predictions used for AUC, accuracy, Brier, κ@α.
      * Per-fold AUCs collected for cv_std diagnostic.
    """
    StratifiedKFold, LogisticRegression, StandardScaler, roc_auc_score = (
        _lazy_import_sklearn()
    )

    bench = extraction.benchmark
    X = extraction.hidden_states.astype(np.float64)  # (N, d)
    y = extraction.correctness.astype(np.int64)  # (N,)
    n = X.shape[0]

    if n != PINNED_N:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: extraction for {bench} has N={n}, expected "
            f"{PINNED_N}."
        )
    n_correct = int(y.sum())
    n_wrong = int(n - n_correct)
    pi_observed = float(n_correct / n)

    if n_correct < N_FOLDS or n_wrong < N_FOLDS:
        raise RuntimeError(
            f"PROBE_INFEASIBLE: {bench} has n_correct={n_correct}, "
            f"n_wrong={n_wrong}; need at least {N_FOLDS} of each class for "
            f"{N_FOLDS}-fold stratified CV."
        )

    skf = StratifiedKFold(
        n_splits=N_FOLDS, shuffle=True, random_state=SEED_ENTROPY
    )
    p_oof = np.full(n, np.nan, dtype=np.float64)
    fold_aucs: list[float] = []

    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[train_idx])
        X_va = scaler.transform(X[val_idx])
        clf = LogisticRegression(
            penalty=PROBE_PENALTY,
            C=PROBE_C,
            solver=PROBE_SOLVER,
            max_iter=PROBE_MAX_ITER,
            random_state=SEED_ENTROPY,
        )
        clf.fit(X_tr, y[train_idx])
        p_va = clf.predict_proba(X_va)[:, 1]
        p_oof[val_idx] = p_va
        # Per-fold AUC (val-only).
        try:
            fold_auc = float(roc_auc_score(y[val_idx], p_va))
        except ValueError:
            # Single-class fold val set — should not happen with stratified
            # splitting, but guard.
            fold_auc = float("nan")
        fold_aucs.append(fold_auc)

    if np.isnan(p_oof).any():
        raise RuntimeError(
            f"PROBE_INTERNAL: OOF predictions contain NaN for {bench}."
        )

    auc_oof = float(roc_auc_score(y, p_oof))
    finite_fold_aucs = [a for a in fold_aucs if not math.isnan(a)]
    auc_cv_std = float(np.std(finite_fold_aucs, ddof=1)) if len(finite_fold_aucs) >= 2 else float("nan")
    yhat = (p_oof >= 0.5).astype(np.int64)
    accuracy_oof = float((yhat == y).mean())
    brier_oof = _compute_brier(p_oof, y)

    # Operating points: all pinned alphas, plus the §15.10 primary alpha=0.50.
    alphas = ALPHA_TARGETS_PER_BENCHMARK[bench]
    operating_points: list[dict] = []
    primary_kappa = 0.0
    primary_tau = float("nan")
    pi_pinned = PINNED_PI[bench]
    for alpha in alphas:
        kappa, tau, op = _selective_kappa_at_alpha(p_oof, y, alpha, pi_pinned)
        operating_points.append(op)
        if math.isclose(alpha, ALPHA_PRIMARY, abs_tol=1e-9):
            primary_kappa = kappa
            primary_tau = tau

    if not any(math.isclose(op["alpha"], ALPHA_PRIMARY, abs_tol=1e-9) for op in operating_points):
        # Primary alpha not in pinned list for this benchmark — compute
        # separately so cascade has a value to cite.
        kappa, tau, op = _selective_kappa_at_alpha(p_oof, y, ALPHA_PRIMARY, pi_pinned)
        operating_points.append(op)
        primary_kappa = kappa
        primary_tau = tau

    return ProbeResult(
        benchmark=bench,
        n_questions=n,
        n_correct=n_correct,
        n_wrong=n_wrong,
        pi_observed=pi_observed,
        auc_oof=auc_oof,
        fold_aucs=tuple(fold_aucs),
        auc_cv_std=auc_cv_std,
        accuracy_oof=accuracy_oof,
        brier_oof=brier_oof,
        kappa_at_alpha2=primary_kappa,
        tau_star_at_alpha2=primary_tau,
        operating_points=tuple(operating_points),
        p_oof=tuple(float(v) for v in p_oof),
    )


# ---------------------------------------------------------------------------
# §15.10 cascade classifier (pinned exhaustive partition).
# ---------------------------------------------------------------------------


def classify_cascade(
    auc_halueval: float,
    auc_truthfulqa: float,
    dauc_halueval: float,
    dauc_truthfulqa: float,
) -> CascadeVerdict:
    """Apply §15.10 cascade. Inclusive thresholds; exhaustive partition.

    STRONG_SIGNAL_IN_Z:
        AUC ≥ STRONG_AUC_THRESHOLD (0.75) on BOTH benchmarks
        AND ΔAUC ≥ STRONG_DELTA_AUC_THRESHOLD (+0.05) on BOTH benchmarks.

    PARTIAL_SIGNAL_IN_Z:
        Not STRONG, AND
        AUC ≥ PARTIAL_AUC_THRESHOLD (0.66) on at least one benchmark, AND
        ΔAUC > 0 on at least one benchmark.

    NO_MATERIAL_SIGNAL_IN_Z:
        Otherwise (the strict complement of the above two).
    """
    aucs = (auc_halueval, auc_truthfulqa)
    dauces = (dauc_halueval, dauc_truthfulqa)

    is_strong = (
        all(a >= STRONG_AUC_THRESHOLD for a in aucs)
        and all(d >= STRONG_DELTA_AUC_THRESHOLD for d in dauces)
    )
    if is_strong:
        rationale = (
            f"STRONG: AUC ≥ {STRONG_AUC_THRESHOLD} on both "
            f"(HaluEval={auc_halueval:.3f}, TruthfulQA-MC={auc_truthfulqa:.3f}) "
            f"AND ΔAUC ≥ +{STRONG_DELTA_AUC_THRESHOLD} on both "
            f"(ΔHaluEval={dauc_halueval:+.3f}, ΔTruthfulQA-MC={dauc_truthfulqa:+.3f})."
        )
        return CascadeVerdict(
            label="STRONG_SIGNAL_IN_Z",
            auc_halueval=float(auc_halueval),
            auc_truthfulqa=float(auc_truthfulqa),
            dauc_halueval=float(dauc_halueval),
            dauc_truthfulqa=float(dauc_truthfulqa),
            rationale=rationale,
        )

    is_partial = (
        any(a >= PARTIAL_AUC_THRESHOLD for a in aucs)
        and any(d > 0.0 for d in dauces)
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
            label="PARTIAL_SIGNAL_IN_Z",
            auc_halueval=float(auc_halueval),
            auc_truthfulqa=float(auc_truthfulqa),
            dauc_halueval=float(dauc_halueval),
            dauc_truthfulqa=float(dauc_truthfulqa),
            rationale=rationale,
        )

    rationale = (
        f"NO_MATERIAL: neither STRONG nor PARTIAL; "
        f"AUCs (HaluEval={auc_halueval:.3f}, "
        f"TruthfulQA-MC={auc_truthfulqa:.3f}) and ΔAUCs "
        f"(ΔHaluEval={dauc_halueval:+.3f}, "
        f"ΔTruthfulQA-MC={dauc_truthfulqa:+.3f}) fail the cascade entry "
        f"conditions for STRONG and PARTIAL."
    )
    return CascadeVerdict(
        label="NO_MATERIAL_SIGNAL_IN_Z",
        auc_halueval=float(auc_halueval),
        auc_truthfulqa=float(auc_truthfulqa),
        dauc_halueval=float(dauc_halueval),
        dauc_truthfulqa=float(dauc_truthfulqa),
        rationale=rationale,
    )


# ===========================================================================
# §15.10 Chunk I-4 — Self-test gate, interpretation firewall, output
# writers (JSON + markdown).
#
# Discipline:
#   * Self-test is a required pre-execution gate; any failure exits 3.
#   * Interpretation firewall scans rendered markdown for Class-3 forbidden
#     statements before write; detection exits 4 (INTERPRETATION_VIOLATION).
#   * JSON schema_version pinned to "15.10" per §15.10 spec.
# ===========================================================================


# ---------------------------------------------------------------------------
# Self-test gate.
# ---------------------------------------------------------------------------


def _self_test_cascade() -> list[str]:
    """Run all SELF_TEST_CASCADE_CASES; return list of failure messages."""
    failures: list[str] = []
    for i, (auc_h, auc_t, dauc_h, dauc_t, expected) in enumerate(
        SELF_TEST_CASCADE_CASES
    ):
        verdict = classify_cascade(auc_h, auc_t, dauc_h, dauc_t)
        if verdict.label != expected:
            failures.append(
                f"  case {i}: AUC=({auc_h:.3f},{auc_t:.3f}) "
                f"ΔAUC=({dauc_h:+.3f},{dauc_t:+.3f}) → "
                f"got {verdict.label!r}, expected {expected!r}"
            )
    return failures


def _self_test_kappa_at_alpha() -> list[str]:
    """Smoke-test selective-prediction κ@α on synthetic perfectly-separable
    and pathological cases."""
    failures: list[str] = []
    rng = np.random.default_rng(SEED_ENTROPY)

    # Perfectly separable: p in [0.6, 1.0] for y=1; p in [0.0, 0.4] for y=0.
    n_each = 50
    p_pos = rng.uniform(0.6, 1.0, size=n_each)
    p_neg = rng.uniform(0.0, 0.4, size=n_each)
    p = np.concatenate([p_pos, p_neg])
    y = np.concatenate([np.ones(n_each, dtype=np.int64), np.zeros(n_each, dtype=np.int64)])
    kappa, tau, op = _selective_kappa_at_alpha(p, y, alpha=0.99, pi=0.5)
    if not (kappa >= 0.40 and op["eligible"]):
        failures.append(
            f"  perfectly-separable @ α=0.99: kappa={kappa:.3f}, "
            f"eligible={op['eligible']} (expected kappa ≥ 0.40, eligible)"
        )

    # Pathological: random p, target α=0.99 with low base rate → infeasible.
    p_rand = rng.uniform(0.0, 1.0, size=100)
    y_low = (rng.uniform(0.0, 1.0, size=100) < 0.05).astype(np.int64)
    kappa, tau, op = _selective_kappa_at_alpha(p_rand, y_low, alpha=0.99, pi=0.05)
    if op["eligible"] and op["coverage_at_tau_star"] > 0.50:
        failures.append(
            f"  pathological random/low-base-rate @ α=0.99: "
            f"kappa={kappa:.3f}, eligible={op['eligible']} (expected "
            f"infeasible or very low coverage)"
        )

    return failures


def _self_test_firewall() -> list[str]:
    """Verify firewall flags every Class-3 forbidden pattern."""
    failures: list[str] = []
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        sample = f"Some innocuous text. {pattern} more text."
        violations = scan_for_forbidden_patterns(sample)
        if not violations:
            failures.append(
                f"  firewall failed to detect pattern: {pattern!r}"
            )
    # Negative case: clean text should produce zero violations.
    clean = (
        "The probe AUC is 0.61 on HaluEval-QA, ΔAUC = -0.05. The cascade "
        "label is NO_MATERIAL_SIGNAL_IN_Z by mechanical readout. The §13.9 "
        "hold remains binding."
    )
    if scan_for_forbidden_patterns(clean):
        failures.append(
            "  firewall false-positive on clean text: "
            f"{scan_for_forbidden_patterns(clean)!r}"
        )
    return failures


def run_self_test() -> int:
    """Execute the §15.10 self-test gate; return 0 on success, 3 on failure."""
    print("§15.10 self-test gate", flush=True)
    print(f"  schema_version: {SCHEMA_VERSION}", flush=True)
    print(f"  benchmarks: {BENCHMARKS}", flush=True)
    print(f"  pinned_N: {PINNED_N}", flush=True)
    print(f"  baseline AUCs: {BASELINE_AUC_PER_BENCHMARK}", flush=True)
    print(
        f"  cascade thresholds: STRONG_AUC≥{STRONG_AUC_THRESHOLD}, "
        f"STRONG_dAUC≥+{STRONG_DELTA_AUC_THRESHOLD}, "
        f"PARTIAL_AUC≥{PARTIAL_AUC_THRESHOLD}",
        flush=True,
    )

    all_failures: list[str] = []

    print("  [1/3] cascade boundary cases...", flush=True)
    cascade_fail = _self_test_cascade()
    if cascade_fail:
        all_failures.append("CASCADE FAILURES:")
        all_failures.extend(cascade_fail)
    else:
        print(
            f"    OK: {len(SELF_TEST_CASCADE_CASES)} boundary cases pass.",
            flush=True,
        )

    print("  [2/3] selective-prediction κ@α smoke test...", flush=True)
    kappa_fail = _self_test_kappa_at_alpha()
    if kappa_fail:
        all_failures.append("KAPPA FAILURES:")
        all_failures.extend(kappa_fail)
    else:
        print("    OK: κ@α behaves on separable + pathological inputs.", flush=True)

    print("  [3/3] interpretation firewall...", flush=True)
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


# ---------------------------------------------------------------------------
# Interpretation firewall (§15.7-pattern reuse).
# ---------------------------------------------------------------------------


def scan_for_forbidden_patterns(text: str) -> list[str]:
    """Return the Class-3 forbidden patterns found in `text` (case-insensitive
    for the BCVF/discipline patterns; literal §-numbered patterns matched
    case-sensitively to avoid noise)."""
    found: list[str] = []
    lowered = text.lower()
    for pattern in CLASS_3_FORBIDDEN_PATTERNS:
        if pattern.startswith("§"):
            # §-anchored patterns: literal match (preserves precise §-numbering).
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
            "language; the cascade verdict is binding.",
            flush=True,
        )
        sys.exit(4)


# ---------------------------------------------------------------------------
# Output writers — JSON + markdown.
# ---------------------------------------------------------------------------


def _probe_result_to_dict(pr: ProbeResult) -> dict:
    return {
        "benchmark": pr.benchmark,
        "n_questions": pr.n_questions,
        "n_correct": pr.n_correct,
        "n_wrong": pr.n_wrong,
        "pi_observed": pr.pi_observed,
        "auc_oof": pr.auc_oof,
        "fold_aucs": list(pr.fold_aucs),
        "auc_cv_std": pr.auc_cv_std,
        "accuracy_oof": pr.accuracy_oof,
        "brier_oof": pr.brier_oof,
        "kappa_at_alpha_primary": pr.kappa_at_alpha2,
        "tau_star_at_alpha_primary": pr.tau_star_at_alpha2,
        "alpha_primary": ALPHA_PRIMARY,
        "operating_points": list(pr.operating_points),
        "p_oof": list(pr.p_oof),
    }


def _cascade_verdict_to_dict(cv: CascadeVerdict) -> dict:
    return {
        "label": cv.label,
        "auc_halueval": cv.auc_halueval,
        "auc_truthfulqa": cv.auc_truthfulqa,
        "dauc_halueval": cv.dauc_halueval,
        "dauc_truthfulqa": cv.dauc_truthfulqa,
        "rationale": cv.rationale,
    }


def write_json_output(outputs: SupervisedAuditOutputs, path: str) -> None:
    """Serialize SupervisedAuditOutputs to a JSON file."""
    payload = {
        "schema_version": outputs.schema_version,
        "qwen_model_id": outputs.qwen_model_id,
        "extraction_layer": outputs.extraction_layer,
        "hidden_dim": outputs.hidden_dim,
        "pinned_N": PINNED_N,
        "baseline_auc_per_benchmark": BASELINE_AUC_PER_BENCHMARK,
        "pinned_pi": PINNED_PI,
        "cascade_thresholds": {
            "strong_auc": STRONG_AUC_THRESHOLD,
            "strong_delta_auc": STRONG_DELTA_AUC_THRESHOLD,
            "partial_auc": PARTIAL_AUC_THRESHOLD,
            "no_material_auc_floor": NO_MATERIAL_AUC_FLOOR,
        },
        "probe_config": {
            "penalty": PROBE_PENALTY,
            "C": PROBE_C,
            "max_iter": PROBE_MAX_ITER,
            "solver": PROBE_SOLVER,
            "n_folds": N_FOLDS,
            "seed_entropy": SEED_ENTROPY,
            "n_min": N_MIN,
            "prompt_format": PROMPT_FORMAT,
        },
        "halueval_qa": _probe_result_to_dict(outputs.halueval_probe),
        "truthfulqa_mc": _probe_result_to_dict(outputs.truthfulqa_probe),
        "cascade_verdict": _cascade_verdict_to_dict(outputs.cascade_verdict),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


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


def render_markdown_report(outputs: SupervisedAuditOutputs) -> str:
    """Render the §15.10 markdown report. Output is firewall-scanned by the
    caller before write."""
    cv = outputs.cascade_verdict
    h = outputs.halueval_probe
    t = outputs.truthfulqa_probe
    base_h = BASELINE_AUC_PER_BENCHMARK["halueval_qa"]
    base_t = BASELINE_AUC_PER_BENCHMARK["truthfulqa_mc"]

    lines: list[str] = []
    lines.append("# §15.10 Phase 1 — Supervised linear truth-probe (result)\n")
    prompt_repr = PROMPT_FORMAT.replace("\n", "\\n")
    lines.append(
        f"_Schema version: `{outputs.schema_version}`._  \n"
        f"_Model: `{outputs.qwen_model_id}`; "
        f"layer index: `{outputs.extraction_layer}`; "
        f"hidden dim: `{outputs.hidden_dim}`; "
        f"prompt format: `{prompt_repr}`._\n"
    )

    lines.append("## Cascade verdict (mechanical readout)\n")
    lines.append(f"**Label:** `{cv.label}`\n")
    lines.append(f"**Rationale:** {cv.rationale}\n")
    lines.append(
        "| benchmark | probe AUC (OOF) | §13.10 baseline AUC | ΔAUC |\n"
        "|---|---|---|---|\n"
        f"| HaluEval-QA | {cv.auc_halueval:.3f} | {base_h:.3f} | "
        f"{cv.dauc_halueval:+.3f} |\n"
        f"| TruthfulQA-MC | {cv.auc_truthfulqa:.3f} | {base_t:.3f} | "
        f"{cv.dauc_truthfulqa:+.3f} |\n"
    )

    for label, pr, base in (
        ("HaluEval-QA", h, base_h),
        ("TruthfulQA-MC", t, base_t),
    ):
        lines.append(f"## Probe details — {label}\n")
        lines.append(
            f"- N questions: {pr.n_questions} "
            f"(correct: {pr.n_correct}, wrong: {pr.n_wrong})\n"
            f"- π observed: {pr.pi_observed:.3f} "
            f"(pinned: {PINNED_PI[pr.benchmark]:.3f})\n"
            f"- Probe OOF AUC: **{pr.auc_oof:.3f}** "
            f"(§13.10 baseline: {base:.3f}; ΔAUC: {pr.auc_oof - base:+.3f})\n"
            f"- Per-fold AUCs: {[round(a, 3) for a in pr.fold_aucs]}\n"
            f"- CV std (AUC): {pr.auc_cv_std:.3f}\n"
            f"- OOF accuracy @ p≥0.5: {pr.accuracy_oof:.3f}\n"
            f"- OOF Brier: {pr.brier_oof:.4f}\n"
        )
        lines.append("**Selective-prediction operating points:**\n")
        lines.append(_format_operating_points_table(pr.operating_points))
        lines.append("")

    lines.append("## Pinned configuration (§15.10 §0.8-binding)\n")
    lines.append(
        f"- Probe: L2 LogisticRegression, C={PROBE_C}, solver={PROBE_SOLVER}, "
        f"max_iter={PROBE_MAX_ITER}\n"
        f"- CV: {N_FOLDS}-fold stratified, shuffle=True, "
        f"random_state={SEED_ENTROPY}\n"
        f"- Per-fold StandardScaler fit on train, applied to val\n"
        f"- Selective-prediction floor: N_MIN={N_MIN}\n"
        f"- Cascade thresholds: STRONG AUC≥{STRONG_AUC_THRESHOLD} "
        f"AND ΔAUC≥+{STRONG_DELTA_AUC_THRESHOLD} (both benchmarks); "
        f"PARTIAL AUC≥{PARTIAL_AUC_THRESHOLD} AND ΔAUC>0 (at least one); "
        f"otherwise NO_MATERIAL\n"
    )

    lines.append("## Caveats (§0.8-disclosed)\n")
    lines.append(
        "- **Prompt format vs §13.10 labeling regime.** §15.10 pinned "
        "`Q: {question}\\nA:` regardless of how §13.10 generated the "
        "correctness labels. §13.10's HaluEval producer defaults to "
        "no-context (matches the pinned format), but `--include-context` "
        "would prepend the HaluEval `knowledge` passage. Without an "
        "explicit pin to the §13.10 invocation, we cannot rule out a "
        "prompt-template mismatch on HaluEval. This is the standard linear "
        "truth-probe convention; the cascade verdict is binding regardless.\n"
        "- **Question text source.** Question text used for the Qwen-7B "
        "forward pass is read from the §13.10 dump's `question` field "
        "when present on every record, else loaded from the HuggingFace "
        "dataset by `q_idx` alignment.\n"
        "- **sklearn API surface.** The probe call passes `penalty='l2'` "
        "explicitly; sklearn 1.8 deprecated this kwarg (still accepted), "
        "and sklearn 1.10 will remove it. A targeted FutureWarning filter "
        "is installed at module load; if the runpod's sklearn ≥ 1.10, the "
        "script will exit 7 (PROBE_FAILED) with a clear TypeError, "
        "unambiguously diagnosable.\n"
    )

    lines.append("## Audit-trail integrity\n")
    lines.append(
        "This result is a mechanical readout of the §15.10 cascade applied "
        "to OOF probe outputs. Per §0.8 discipline, the cascade label is "
        "binding regardless of any post-hoc interpretation, and §15.10 "
        "outputs do NOT modify any §13/§14/§15.x verdict-of-record. The "
        "interpretation firewall scanned this document for Class-3 "
        "forbidden statements before write.\n"
    )

    return "\n".join(lines)


def write_markdown_output(outputs: SupervisedAuditOutputs, path: str) -> None:
    """Render markdown, run interpretation firewall, then write."""
    text = render_markdown_report(outputs)
    enforce_firewall_or_exit(text, path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(text)


# ===========================================================================
# §15.10 Chunk I-5 — main() orchestration + CLI.
#
# Modes:
#   --self-test    : run gate only, exit 0/3
#   --extract-only : load labels + Qwen-7B forward pass + write .npz cache
#   --probe-only   : load .npz cache + train probes + write outputs
#   (default)      : self-test → extract (or load cache) → probe → write
#
# Exit codes:
#   0  success
#   2  CLI / argument error (handled by argparse)
#   3  SELF_TEST_FAILED
#   4  INTERPRETATION_VIOLATION
#   5  SCHEMA_MISMATCH (label dump or cache)
#   6  EXTRACTION_FAILED (torch/transformers stack error)
#   7  PROBE_FAILED (sklearn / class-imbalance / NaN)
# ===========================================================================


def _run_extraction(verbose: bool = True) -> dict[str, HiddenStateExtraction]:
    """Load labels + run Qwen-7B forward pass per benchmark; return dict."""
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
        device_map=device,
        output_hidden_states=True,
    )
    model.eval()

    for bench in BENCHMARKS:
        if verbose:
            print(f"  loading labels: {bench}", flush=True)
        labels = load_benchmark_labels(bench)
        if verbose:
            print(
                f"  extracting hidden states: {bench} "
                f"(N={len(labels.questions)})",
                flush=True,
            )
        ext = extract_hidden_states(
            labels, model=model, tokenizer=tokenizer, device=device
        )
        extractions[bench] = ext
        if verbose:
            print(
                f"    {bench}: hidden_states shape={ext.hidden_states.shape}, "
                f"d={ext.d}",
                flush=True,
            )
    return extractions


def _run_probes(
    extractions: dict[str, HiddenStateExtraction],
) -> SupervisedAuditOutputs:
    """Run probe per benchmark; classify cascade; return SupervisedAuditOutputs."""
    pr_h = run_probe_for_benchmark(extractions["halueval_qa"])
    pr_t = run_probe_for_benchmark(extractions["truthfulqa_mc"])
    dauc_h = pr_h.auc_oof - BASELINE_AUC_PER_BENCHMARK["halueval_qa"]
    dauc_t = pr_t.auc_oof - BASELINE_AUC_PER_BENCHMARK["truthfulqa_mc"]
    cv = classify_cascade(pr_h.auc_oof, pr_t.auc_oof, dauc_h, dauc_t)

    # Sanity: both extractions should share the same hidden_dim and layer.
    if extractions["halueval_qa"].d != extractions["truthfulqa_mc"].d:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: hidden_dim differs across benchmarks: "
            f"HaluEval={extractions['halueval_qa'].d}, "
            f"TruthfulQA-MC={extractions['truthfulqa_mc'].d}."
        )
    if extractions["halueval_qa"].layer_idx != extractions["truthfulqa_mc"].layer_idx:
        raise SchemaMismatchError(
            f"SCHEMA_MISMATCH: layer_idx differs across benchmarks: "
            f"HaluEval={extractions['halueval_qa'].layer_idx}, "
            f"TruthfulQA-MC={extractions['truthfulqa_mc'].layer_idx}."
        )

    return SupervisedAuditOutputs(
        schema_version=SCHEMA_VERSION,
        halueval_probe=pr_h,
        truthfulqa_probe=pr_t,
        cascade_verdict=cv,
        extraction_layer=extractions["halueval_qa"].layer_idx,
        hidden_dim=extractions["halueval_qa"].d,
        qwen_model_id=QWEN_MODEL_ID,
    )


def _print_verdict_banner(outputs: SupervisedAuditOutputs) -> None:
    """Emit a one-screen mechanical-readout banner."""
    cv = outputs.cascade_verdict
    print("", flush=True)
    print("=" * 72, flush=True)
    print(f"§15.10 cascade verdict: {cv.label}", flush=True)
    print("-" * 72, flush=True)
    print(
        f"  HaluEval-QA   AUC = {cv.auc_halueval:.3f}  "
        f"(baseline {BASELINE_AUC_PER_BENCHMARK['halueval_qa']:.3f}; "
        f"ΔAUC {cv.dauc_halueval:+.3f})",
        flush=True,
    )
    print(
        f"  TruthfulQA-MC AUC = {cv.auc_truthfulqa:.3f}  "
        f"(baseline {BASELINE_AUC_PER_BENCHMARK['truthfulqa_mc']:.3f}; "
        f"ΔAUC {cv.dauc_truthfulqa:+.3f})",
        flush=True,
    )
    print("-" * 72, flush=True)
    print(f"  rationale: {cv.rationale}", flush=True)
    print("=" * 72, flush=True)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="probe_supervised_15_10",
        description=(
            "§15.10 Phase 1 — supervised linear truth-probe over Qwen-7B "
            "final-layer last-token hidden states. Single-shot, pinned "
            "configuration, mechanical readout."
        ),
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--self-test",
        action="store_true",
        help="Run self-test gate only (cascade boundaries + κ@α + firewall).",
    )
    mode.add_argument(
        "--extract-only",
        action="store_true",
        help=(
            "Run hidden-state extraction only; write .npz cache. "
            "Skips probe + outputs."
        ),
    )
    mode.add_argument(
        "--probe-only",
        action="store_true",
        help=(
            "Run probes from existing .npz cache; skip extraction. "
            "Self-test gate still runs first."
        ),
    )
    p.add_argument(
        "--cache-path",
        default=HIDDEN_STATES_CACHE_PATH,
        help=(
            f"Path to hidden-states .npz cache "
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

    # Self-test gate is a required pre-execution check for every mode
    # except the explicit --self-test (which IS the gate).
    if args.self_test:
        return run_self_test()

    rc = run_self_test()
    if rc != 0:
        return rc

    cache_path = args.cache_path

    # Extraction phase.
    if args.probe_only:
        print(f"\n--probe-only: loading hidden-state cache from {cache_path}", flush=True)
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
                "\nExtraction phase — Qwen2.5-7B-Instruct forward pass.",
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
            print("\n--extract-only: extraction complete; skipping probe.", flush=True)
            return 0

    # Probe phase.
    print("\nProbe phase — 5-fold stratified CV per benchmark.", flush=True)
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
