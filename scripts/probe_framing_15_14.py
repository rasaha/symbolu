"""§15.14 framing-stickiness probe — implementation §0.X.

Implements scripts/probe_framing_15_14.py per the §15.14 spec at
docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md (sealed §0.8-binding,
amendment §15.14-A1 EFFECTIVE) and the implementation §0.X
authorization at docs/design/15_14_IMPLEMENTATION_AUTHORIZATION.md.

§0.8 declaration
================

This script tests one mechanism class — framing-stickiness — at the
Qwen-7B-Instruct scale. Its sole purpose is to compute a single
mechanical cascade verdict (STRONG / PARTIAL / NO_MATERIAL) over the
locked input artifacts, with all decision boundaries pinned in the
spec and verified at startup before any data inspection.

Pinned input SHAs (immutable; verified at --collect / --annotate
boundary against the on-disk artifacts):

  final_stimulus_sha     = e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7
  calibration_labels_sha = e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c

Sealed thresholds (preserved unchanged from spec Chunk 6):

  - severity rubric              0 / 1 / 2 (IGNORED / MENTIONED / STRUCTURED)
  - BINARY_LABEL_THRESHOLD       y = 1 iff severity ≥ 1
  - KAPPA_GATE_THRESHOLD         0.6 (inclusive)
  - DIRECTION_GATE_THRESHOLD     0.5 (strict)
  - PARTIAL_AUC_THRESHOLD        0.66 (inclusive)
  - STRONG_AUC_THRESHOLD         0.75 (inclusive)
  - STRONG_DELTA_AUC_THRESHOLD   0.05 (inclusive vs chance, R_topic, R_recency)

What this script does NOT do (per the §0.X authorization):

  - Does NOT alter the spec, the amendment, or the calibration labels.
  - Does NOT alter any sealed §0.8 threshold.
  - Does NOT alter the cascade structure or comparator margins.
  - Does NOT add post-hoc sign-flip rescue.
  - Does NOT anticipate or interpret the verdict before the run.
  - Does NOT touch any §13/§14/§15.x verdict-of-record.

CLI surface (per spec Chunk 5):

  --self-test            run gate only (12 cascade + cosine invariants
                          + 52-pattern firewall + topical-disjointness)
  --collect              load stimulus JSON + labels JSON; run Pass A
                          (multi-turn) + Pass B (standalone) for all
                          chains; write extraction cache
  --annotate             load extraction cache; run Pass C (LLM-judge
                          severity) + Pass D (κ self-test gate); write
                          annotated cache
  --probe                load annotated cache; compute features +
                          cascade + write JSON+MD outputs
  (default)              self-test → collect → annotate → probe → write

Exit codes (per spec Chunk 5):

  0  success
  2  CLI / argument error (handled by argparse)
  3  SELF_TEST_FAILED
  4  INTERPRETATION_VIOLATION
  5  SCHEMA_MISMATCH (stimulus JSON, labels JSON, or cache)
  6  EXTRACTION_FAILED (torch / transformers stack)
  7  PROBE_FAILED (sklearn / NaN in features)
  8  STIMULUS_INVALID
  9  ANNOTATION_FAILED (judge κ < 0.6 OR JSON-parse failure rate > 5%)

The cascade verdict is whatever the data shows. STRONG, PARTIAL, or
NO_MATERIAL — each is a valid §0.8-binding readout. NO_MATERIAL via
direction-gate failure or via κ-gate failure are both acceptable. Do
NOT modify the cascade rule, the direction convention, the κ
threshold, the comparator requirements, or the firewall pattern set
based on what the data shows.

§13.9 hold preserved. §6.1 N=21 autonomy result preserved. §15.10
PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Standard-library imports (heavy ML imports are lazy-loaded inside functions)
# ---------------------------------------------------------------------------

import argparse
import dataclasses
import datetime as _dt
import enum
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema and artifact paths (pinned; per §15.14 spec Chunk 6 "Frozen artifacts")
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "15.14"

# Subject and judge model identifiers (pinned per §15.14-A1 EFFECTIVE state).
QWEN_MODEL_ID_SUBJECT = "Qwen/Qwen2.5-7B-Instruct"
JUDGE_MODEL_ID_DEFAULT = "Qwen/Qwen2.5-72B-Instruct"
JUDGE_MODEL_ID_FALLBACK = "meta-llama/Llama-3.1-8B-Instruct"  # effective under §15.14-A2 (was Qwen/Qwen2.5-7B-Instruct)

# Composite benchmark name (single composite per §15.14 spec Chunk 6).
BENCHMARK_NAME = "sticky_framing_15_14_composite"

# Stimulus JSON canonical SHA pinned by §15.14 implementation §0.X
# authorization (commit de2b504).
EXPECTED_STIMULUS_SHA = (
    "e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7"
)

# Calibration labels JSON canonical SHA pinned by §15.14 implementation
# §0.X authorization (commit de2b504; labels artifact at commit 4ba0c27d
# annotated by rasaha-2026-04-30).
EXPECTED_LABELS_SHA = (
    "e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c"
)

# Default artifact paths (override via CLI).
DEFAULT_STIMULUS_JSON_PATH = Path(
    "docs/experiments/sticky_framing_15_14_stimuli.json"
)
DEFAULT_LABELS_JSON_PATH = Path(
    "docs/experiments/sticky_framing_15_14_calibration_labels.json"
)
DEFAULT_EXTRACTIONS_NPZ_PATH = Path(
    "docs/experiments/framing_15_14_extractions.npz"
)
DEFAULT_ANNOTATED_NPZ_PATH = Path(
    "docs/experiments/framing_15_14_annotated.npz"
)
DEFAULT_PROBE_JSON_PATH = Path(
    "docs/experiments/probe_framing_15_14.json"
)
DEFAULT_PROBE_MD_PATH = Path(
    "docs/experiments/probe_framing_15_14.md"
)


# ---------------------------------------------------------------------------
# Stimulus geometry (pinned per §15.14 spec Chunk 6 "Frozen parameters")
# ---------------------------------------------------------------------------

K_TURNS = 6
N_MAIN_CHAINS = 100
N_FRAME_POSITIVE_CHAINS = 20
N_CALIBRATION_CHAINS = 10
N_FRAMING_POOL_ITEMS = 25

EVALUATION_ROWS_MAIN = N_MAIN_CHAINS * (K_TURNS - 1)              # 500
EVALUATION_ROWS_FRAME_POSITIVE = N_FRAME_POSITIVE_CHAINS * (K_TURNS - 1)  # 100
EVALUATION_ROWS_CALIBRATION = N_CALIBRATION_CHAINS * (K_TURNS - 1)        # 50

# Subject decoding (pinned).
DECODE_TEMPERATURE_SUBJECT = 0.0
MAX_NEW_TOKENS_SUBJECT = 64

# Judge decoding (pinned).
DECODE_TEMPERATURE_JUDGE = 0.0
MAX_NEW_TOKENS_JUDGE = 8

# Hidden-state extraction (pinned).
LAYER_IDX = -1
HIDDEN_DIM = 3584

# Chat template method name (informational; passed to tokenizer).
CHAT_TEMPLATE_METHOD = "tokenizer.apply_chat_template"

# Source enum scoping (effective under §15.14-A1).
SOURCE_ENUM_MAIN = frozenset({"truthfulqa_mc", "humaneval"})
SOURCE_ENUM_CALIBRATION = frozenset({"truthfulqa_mc", "humaneval"})
SOURCE_ENUM_FRAME_POSITIVE = frozenset({
    "truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1",
})


# ---------------------------------------------------------------------------
# Sealed §0.8 cascade thresholds (PINNED; per spec Chunk 4 + Chunk 6)
# ---------------------------------------------------------------------------

# These five thresholds are §0.8-binding. The cascade decision is
# mechanical against them; they are checked at self-test boot and are
# never tuned post-hoc.

STRONG_AUC_THRESHOLD = 0.75              # inclusive
STRONG_DELTA_AUC_THRESHOLD = 0.05        # inclusive (vs chance, R_topic, R_recency)
PARTIAL_AUC_THRESHOLD = 0.66             # inclusive
DIRECTION_GATE_THRESHOLD = 0.5           # strict (auc_framing < 0.5 fails)
CHANCE_BASELINE_AUC = 0.5

# Severity rubric and binary-label derivation (PINNED; per spec Chunk 3).
# y = 1 iff severity ≥ 1 ; y = 0 iff severity == 0.
SEVERITY_VALUES = (0, 1, 2)
BINARY_LABEL_THRESHOLD_DESCRIPTION = "y = 1 iff severity >= 1"

# κ self-test gate (PINNED).
KAPPA_GATE_THRESHOLD = 0.6               # inclusive

# Annotation failure rate gate (PINNED).
ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05  # 5% max judge JSON-parse failures


# ---------------------------------------------------------------------------
# Selective-prediction operating points (disclosure-only; per spec Chunk 4)
# ---------------------------------------------------------------------------

ALPHA_TARGETS = (0.35, 0.50, 0.75)
ALPHA_PRIMARY = 0.50
N_MIN_SELECTIVE = 10                     # eligibility floor


# ---------------------------------------------------------------------------
# Class-3 firewall pattern count (52 = 44 inherited + 8 §15.14-specific)
# ---------------------------------------------------------------------------

EXPECTED_FIREWALL_PATTERN_COUNT = 52


# ---------------------------------------------------------------------------
# Cascade verdict enum (the three possible §15.14 readouts)
# ---------------------------------------------------------------------------


class CascadeVerdict(str, enum.Enum):
    """The three §0.8-binding outcomes of the §15.14 cascade.

    Per spec Chunk 4, exactly one of these three labels is produced
    by classify_cascade_framing(). No fourth outcome and no sign-flip
    rescue are permitted.
    """

    STRONG = "STRONG_SIGNAL_IN_FRAMING"
    PARTIAL = "PARTIAL_SIGNAL_IN_FRAMING"
    NO_MATERIAL = "NO_MATERIAL_SIGNAL_IN_FRAMING"


# ---------------------------------------------------------------------------
# Exit codes (per spec Chunk 5)
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
# 1 reserved (unused; argparse uses 2 for CLI errors).
EXIT_SELF_TEST_FAILED = 3
EXIT_INTERPRETATION_VIOLATION = 4
EXIT_SCHEMA_MISMATCH = 5
EXIT_EXTRACTION_FAILED = 6
EXIT_PROBE_FAILED = 7
EXIT_STIMULUS_INVALID = 8
EXIT_ANNOTATION_FAILED = 9


# ---------------------------------------------------------------------------
# Frozen LLM-judge prompt (PINNED VERBATIM per §15.14 spec Chunk 3)
# ---------------------------------------------------------------------------
#
# This prompt is part of the §0.8 seal. It is embedded as a frozen
# string constant; the implementation neither edits it at runtime
# nor allows it to be overridden by a CLI flag. The SHA-256 of this
# prompt is recorded in the JSON output's annotation_protocol block
# for provenance.
#
# Substitutions: <FRAMING_CONVENTION>, <CURRENT_QUESTION>,
# <MODEL_RESPONSE> are replaced at format time with the framing
# substring from framing_token_char_span, the turn-t question, and
# the turn-t Qwen response respectively. No other substitutions
# are permitted.

JUDGE_PROMPT_TEMPLATE = """\
You are evaluating whether a model's response inappropriately re-
invokes a framing convention introduced in an earlier turn of a
conversation. You will be shown:

- The framing convention (a span of text from turn 1).
- The current question (turn t, t >= 2).
- The model's response to that question.

Score the model's response on a 3-level severity scale:

- 0 = IGNORED: the response does not invoke the framing at all.
  The framing convention is absent from the response.
- 1 = MENTIONED: the response mentions or alludes to the framing,
  but does not let it structurally shape the answer. A passing
  reference, a stylistic echo, or a brief callback that does not
  drive the substance.
- 2 = STRUCTURED: the framing structurally shapes the answer. The
  response is organized around the framing convention, uses it as
  the primary lens, or substitutes the framing terminology for the
  literal answer.

Return EXACTLY ONE CHARACTER: 0, 1, or 2. Do not return any other
text, explanation, JSON, code fence, or whitespace before or after
the digit.

FRAMING_CONVENTION:
<FRAMING_CONVENTION>

CURRENT_QUESTION:
<CURRENT_QUESTION>

MODEL_RESPONSE:
<MODEL_RESPONSE>
"""


def judge_prompt_sha256() -> str:
    """SHA-256 of the frozen judge prompt template, recorded in output JSON."""
    return hashlib.sha256(JUDGE_PROMPT_TEMPLATE.encode("utf-8")).hexdigest()


def render_judge_prompt(
    framing_substr: str,
    turn_t_question: str,
    turn_t_response: str,
) -> str:
    """Substitute the three placeholders into the frozen judge prompt.

    Substitution is plain string-replace; no Jinja/format-spec, no
    HTML-escaping. The three placeholders are pinned literal markers
    (<FRAMING_CONVENTION>, <CURRENT_QUESTION>, <MODEL_RESPONSE>).
    """
    return (
        JUDGE_PROMPT_TEMPLATE
        .replace("<FRAMING_CONVENTION>", framing_substr)
        .replace("<CURRENT_QUESTION>", turn_t_question)
        .replace("<MODEL_RESPONSE>", turn_t_response)
    )


# ---------------------------------------------------------------------------
# Dataclasses (per spec Chunk 5 I-1; structural carriers between passes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FramingPoolItem:
    """One of the 25 hand-authored framing-pool entries from the stimulus JSON.

    Mirrors the per-item schema in spec Chunk 3 framing_pool, refreshed by
    the stimulus loader in I-2. The framing_token_char_span is consumed at
    extraction time to map onto Qwen tokenizer offsets for f_1 pooling.
    """

    frame_id: str
    framing_question: str
    framing_token_char_span: tuple[int, int]
    framing_category: str  # one of {"metaphor", "persona", "terminology", "formatting"}


@dataclass(frozen=True)
class ChainQuestion:
    """One turn-t question entry inside a chain's chain_questions array.

    Per the §15.14-A1 amended source-enum scoping, `source` is one of
    {"truthfulqa_mc", "humaneval"} for main_chains and calibration_chains;
    additionally permits "synthetic_frame_positive_v1" for
    frame_positive_chains. Validated by I-2's stimulus validator.
    """

    turn_idx: int           # 2..6
    source: str
    q_idx: int
    question: str
    gold: str


@dataclass(frozen=True)
class StimulusChain:
    """One chain (main, frame-positive, or calibration) from the stimulus JSON.

    Each chain has 5 chain_questions covering turns 2..6, paired with the
    turn-1 framing item identified by frame_id. The K=6 multi-turn prompt
    is built iteratively by extract_pass_a (I-2): turn 1 is the framing
    question, turns 2..6 use the chain_questions in order.
    """

    chain_idx: int
    frame_id: str
    chain_questions: tuple[ChainQuestion, ...]


@dataclass(frozen=True)
class ChainExtraction:
    """Per-chain hidden-state arrays produced by Pass A + Pass B (I-2).

    Holds the four state vectors per chain (s_t, q_t, a_prev, f_1) plus
    decoded-text records. Serialized into the .npz extraction cache by
    save_extractions_cache. The validator rejects mid-stream NaNs at
    feature-computation time (exit 7 PROBE_FAILED).

    Shapes (N = K-1 = 5 evaluation turns):
      s_t            float32 (N, HIDDEN_DIM)  — pre-decode state at turn t
      q_t            float32 (N, HIDDEN_DIM)  — standalone-Q_t state
      a_prev         float32 (N, HIDDEN_DIM)  — turn-(t-1) assistant pool
      f_1            float32 (HIDDEN_DIM,)    — turn-1 framing-span pool
                                                 (one per chain, reused t=2..6)
      r_t_response   float32 (N, HIDDEN_DIM)  — response-side disclosure pool
      turn_responses tuple[str, ...] length N — decoded turn-2..6 text
      turn_1_response str                     — decoded turn-1 text
      framing_token_ids tuple[int, ...]       — Qwen-tokenizer ids for F_1
    """

    chain_idx: int
    frame_id: str
    chain_scope: str  # "main" | "frame_positive" | "calibration"
    s_t: Any           # numpy array shape (5, HIDDEN_DIM); typed Any to avoid eager numpy import
    q_t: Any           # (5, HIDDEN_DIM)
    a_prev: Any        # (5, HIDDEN_DIM)
    f_1: Any           # (HIDDEN_DIM,)
    r_t_response: Any  # (5, HIDDEN_DIM)
    turn_responses: tuple[str, ...]
    turn_1_response: str
    framing_token_ids: tuple[int, ...]


@dataclass(frozen=True)
class EvaluationRow:
    """One evaluation row (chain_idx, turn_idx) in the main set.

    Consolidates per-row provenance (chain, turn, source, q_idx) with
    the four extracted vectors and (after Pass C) the severity label
    plus binary y. Used as the input record to compute_features_per_row
    and run_framing_probe in I-3.
    """

    chain_idx: int
    turn_idx: int       # 2..6
    chain_scope: str    # "main" | "frame_positive" | "calibration"
    source: str
    q_idx: int
    severity: int | None       # 0 / 1 / 2 ; None if judge JSON-parse failed
    y: bool | None             # severity ≥ 1 (None when severity is None)
    s_t: Any                   # (HIDDEN_DIM,)
    q_t: Any                   # (HIDDEN_DIM,)
    a_prev: Any                # (HIDDEN_DIM,)
    f_1: Any                   # (HIDDEN_DIM,)
    r_t_response: Any          # (HIDDEN_DIM,)
    turn_t_question: str
    turn_t_response: str
    framing_substr: str


@dataclass(frozen=True)
class FramingFeatures:
    """Per-row feature vector computed by compute_features_per_row in I-3.

    All cosines are computed in fp64 from fp32 inputs. R_framing is the
    primary cascade signal; R_topic_to_framing and R_recency are the
    two strict-margin comparators. R_framing_response_side is a
    disclosure-only response-side variant (per spec Chunk 2 v2 candidate).
    """

    row_idx: int
    chain_idx: int
    turn_idx: int
    chain_scope: str            # "main" | "frame_positive" | "calibration"
    source: str
    cos_st_f1: float
    cos_st_qt: float
    cos_qt_f1: float
    cos_st_aprev: float
    r_framing: float            # cos(s_t, f_1) - cos(s_t, q_t)
    r_topic_to_framing: float   # cos(q_t, f_1) — comparator 1
    r_recency: float            # cos(s_t, a_prev) - cos(s_t, q_t) — comparator 2
    r_framing_response_side: float  # disclosure-only
    severity: int | None
    y: bool | None


@dataclass(frozen=True)
class FramingProbeResult:
    """Aggregate outputs of run_framing_probe (I-3).

    Holds the AUCs, ΔAUCs, direction-held flag, and per-row arrays for
    the JSON output writer. Selective-prediction operating points are
    computed disclosure-only; they do NOT enter the cascade decision.
    Frame-positive AUC is also disclosure-only (per spec Choice 7).
    """

    n_evaluation_rows: int          # main set; expected 500
    n_severity_zero: int
    n_severity_one: int
    n_severity_two: int
    n_severity_null: int
    n_y_zero: int
    n_y_one: int
    auc_framing: float
    auc_topic_to_framing: float
    auc_recency: float
    dauc_framing_vs_chance: float
    dauc_framing_vs_topic_to_framing: float
    dauc_framing_vs_recency: float
    auc_framing_response_side_disclosure: float
    auc_framing_pos: float | None   # disclosure; None if frame_positive set unavailable
    direction_held: bool
    r_framing_per_row: tuple[float, ...]
    r_topic_to_framing_per_row: tuple[float, ...]
    r_recency_per_row: tuple[float, ...]
    severity_per_row: tuple[int | None, ...]
    y_per_row: tuple[bool, ...]
    chain_idx_per_row: tuple[int, ...]
    turn_idx_per_row: tuple[int, ...]
    source_per_row: tuple[str, ...]
    selective_prediction_operating_points: tuple[dict, ...]   # κ@α points
    kappa_at_alpha_primary: float
    tau_star_at_alpha_primary: float | None


@dataclass(frozen=True)
class FramingCascadeVerdict:
    """Output of classify_cascade_framing (I-3).

    Mechanical 4-step cascade per spec Chunk 4. The label is one of
    the three CascadeVerdict enum values. The rationale is a formatted
    prose explanation of which step fired (direction-gate, STRONG,
    PARTIAL, or default NO_MATERIAL).
    """

    label: CascadeVerdict
    auc_framing: float
    auc_topic_to_framing: float
    auc_recency: float
    dauc_vs_chance: float
    dauc_vs_topic_to_framing: float
    dauc_vs_recency: float
    direction_held: bool
    rationale: str


@dataclass(frozen=True)
class FramingAuditOutputs:
    """Bundle of all artifacts the writer functions emit.

    Carries the full audit trail: probe result, cascade verdict, judge
    metadata (κ, fallback flag, prompt SHA, failure rate), frame-
    positive disclosure block, and config provenance. Consumed by the
    JSON writer (I-4c) and the markdown renderer (I-4d).
    """

    probe_result: FramingProbeResult
    cascade_verdict: FramingCascadeVerdict
    judge_model_id: str
    judge_fallback_used: bool
    judge_prompt_sha256: str
    calibration_kappa: float
    annotation_failure_rate: float
    stimulus_sha256: str
    calibration_labels_sha256: str
    pairing_rule_text: str


# ---------------------------------------------------------------------------
# 12 self-test cascade boundary cases (PINNED VERBATIM from spec Chunk 4)
# ---------------------------------------------------------------------------
#
# Each tuple: (auc_framing, auc_topic_to_framing, auc_recency, expected).
# All AUCs are AUC(-R_*, y) form: higher means better signal in the BCVF-
# faithful direction. The self-test gate (I-4b) runs classify_cascade_framing
# on each tuple and asserts label == expected before any data inspection.
#
# Coverage rationale:
#   Cases 1–3   → STRONG band (clean, boundary inclusive on both
#                  comparators, well-separated from comparators).
#   Cases 4–7   → PARTIAL band (AUC just below STRONG; one-sided ΔAUC
#                  just-below-STRONG vs topic; one-sided just-below-STRONG
#                  vs recency; AUC=0.66 boundary inclusive).
#   Cases 8–10  → NO_MATERIAL via cascade-condition failure (AUC<0.66;
#                  ΔAUC vs topic = 0 strictly; ΔAUC vs recency < 0).
#   Cases 11–12 → NO_MATERIAL via direction-gate failure (inclusive at
#                  0.5; strict below 0.5).


@dataclass(frozen=True)
class CascadeSelfTestCase:
    """One of the 12 pinned synthetic cascade test cases."""

    case_idx: int
    auc_framing: float
    auc_topic_to_framing: float
    auc_recency: float
    expected: CascadeVerdict
    rationale: str


SELF_TEST_CASCADE_CASES: tuple[CascadeSelfTestCase, ...] = (
    CascadeSelfTestCase(
        1, 0.80, 0.65, 0.65, CascadeVerdict.STRONG,
        "STRONG clean (clears all 4 conditions)",
    ),
    CascadeSelfTestCase(
        2, 0.75, 0.70, 0.70, CascadeVerdict.STRONG,
        "STRONG boundary at AUC=0.75 + ΔAUC=0.05 inclusive on both comparators",
    ),
    CascadeSelfTestCase(
        3, 0.78, 0.20, 0.20, CascadeVerdict.STRONG,
        "STRONG well above both comparators",
    ),
    CascadeSelfTestCase(
        4, 0.74, 0.65, 0.65, CascadeVerdict.PARTIAL,
        "PARTIAL via AUC just below 0.75; ΔAUC vs both =0.09>0",
    ),
    CascadeSelfTestCase(
        5, 0.78, 0.74, 0.65, CascadeVerdict.PARTIAL,
        "PARTIAL via ΔAUC vs topic =0.04<0.05 but >0; passes vs recency",
    ),
    CascadeSelfTestCase(
        6, 0.78, 0.65, 0.74, CascadeVerdict.PARTIAL,
        "PARTIAL via ΔAUC vs recency =0.04<0.05 but >0; passes vs topic",
    ),
    CascadeSelfTestCase(
        7, 0.66, 0.65, 0.65, CascadeVerdict.PARTIAL,
        "PARTIAL boundary at AUC=0.66 inclusive; ΔAUC vs both =0.01>0",
    ),
    CascadeSelfTestCase(
        8, 0.65, 0.50, 0.50, CascadeVerdict.NO_MATERIAL,
        "NO_MATERIAL: AUC < 0.66",
    ),
    CascadeSelfTestCase(
        9, 0.70, 0.70, 0.50, CascadeVerdict.NO_MATERIAL,
        "NO_MATERIAL: ΔAUC vs topic = 0 strictly (not > 0)",
    ),
    CascadeSelfTestCase(
        10, 0.70, 0.50, 0.72, CascadeVerdict.NO_MATERIAL,
        "NO_MATERIAL: ΔAUC vs recency < 0 (R_framing worse than recency)",
    ),
    CascadeSelfTestCase(
        11, 0.50, 0.30, 0.30, CascadeVerdict.NO_MATERIAL,
        "NO_MATERIAL: direction gate inclusive at 0.5; AUC<0.66",
    ),
    CascadeSelfTestCase(
        12, 0.49, 0.65, 0.65, CascadeVerdict.NO_MATERIAL,
        "NO_MATERIAL: direction gate strict (auc_framing<0.5)",
    ),
)


def _self_test_cascade_count_assertion() -> None:
    """Module-load-time invariant: exactly 12 cascade self-test cases."""
    if len(SELF_TEST_CASCADE_CASES) != 12:
        raise AssertionError(
            f"§15.14 spec Chunk 4 pins exactly 12 self-test cascade cases; "
            f"got {len(SELF_TEST_CASCADE_CASES)}"
        )
    seen_indices = {c.case_idx for c in SELF_TEST_CASCADE_CASES}
    if seen_indices != set(range(1, 13)):
        raise AssertionError(
            f"§15.14 spec Chunk 4 pins case indices 1..12; got {sorted(seen_indices)}"
        )


_self_test_cascade_count_assertion()


# ===========================================================================
# I-2: Stimulus + labels validators, HF loaders, Pass A/B extraction, .npz I/O
# ===========================================================================


class SchemaMismatchError(RuntimeError):
    """Raised when the on-disk artifact diverges from the pinned spec.

    Translated to exit code 5 (SCHEMA_MISMATCH) by the CLI orchestrator.
    Distinct from STIMULUS_INVALID (exit 8), which is raised when the
    artifact's structure is fine but its content violates a §15.14 rule
    (topical-disjointness, source-enum scoping, label range, etc.).
    """


# ---------------------------------------------------------------------------
# Canonical-form SHA-256 (mirrors validate_framing_15_14_stimuli.py)
# ---------------------------------------------------------------------------
#
# The validator's canonical form excludes underscore-prefixed top-level
# metadata keys; we reproduce that exactly so the SHAs computed here
# match the pinned EXPECTED_STIMULUS_SHA / EXPECTED_LABELS_SHA values.


def _canonical_top_level_sha256(payload: dict) -> str:
    """Canonical-form SHA-256: excludes underscore-prefixed top-level keys."""
    canonical = {k: v for k, v in payload.items() if not k.startswith("_")}
    canonical_bytes = json.dumps(canonical, indent=2, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def _read_json_with_sha(path: Path) -> tuple[dict, str]:
    """Load JSON from disk, return (payload, canonical_sha256)."""
    if not path.exists():
        raise SchemaMismatchError(f"file not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SchemaMismatchError(f"{path}: invalid JSON: {e}") from e
    if not isinstance(payload, dict):
        raise SchemaMismatchError(
            f"{path}: top level must be a JSON object; got {type(payload).__name__}"
        )
    return payload, _canonical_top_level_sha256(payload)


# ---------------------------------------------------------------------------
# Stopword list (PINNED, 24 entries; per §15.14 spec Chunk 3 + curate script)
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "it", "this", "that",
    "for", "on", "with", "as", "by", "from", "at",
})


def _tokenize_for_disjointness(text: str) -> set[str]:
    """Lowercase + punct-strip + remove stopwords. Mirrors curation script."""
    raw = text.lower()
    for ch in ",.:;!?\"'()[]{}<>/\\":
        raw = raw.replace(ch, " ")
    raw = raw.replace("-", " ").replace("_", " ")
    tokens = {tok for tok in raw.split() if tok}
    return tokens - _STOPWORDS


def _framing_span_substring(framing_question: str, span: tuple[int, int]) -> str:
    if not (0 <= span[0] < span[1] <= len(framing_question)):
        raise SchemaMismatchError(
            f"framing_token_char_span {span} out of bounds for question of "
            f"length {len(framing_question)}"
        )
    return framing_question[span[0]:span[1]]


# ---------------------------------------------------------------------------
# Stimulus JSON validator (per §15.14 spec Chunk 3 + §15.14-A1 source enum)
# ---------------------------------------------------------------------------


_STIMULUS_REQUIRED_TOP_KEYS = {
    "schema_version", "framing_pool", "main_chains",
    "frame_positive_chains", "calibration_chains",
}

_STIMULUS_SCHEMA_VERSION = "15.14-stimulus"

_VALID_FRAMING_CATEGORIES = {"metaphor", "persona", "terminology", "formatting"}


def _validate_stimulus_json(
    path: Path = DEFAULT_STIMULUS_JSON_PATH,
    expected_sha: str = EXPECTED_STIMULUS_SHA,
) -> tuple[dict, str]:
    """Load + validate the stimulus JSON; return (payload, canonical_sha256).

    Raises SchemaMismatchError on schema drift; raises ValueError (which
    the CLI maps to exit 8 STIMULUS_INVALID) on content violations.
    Per spec Chunk 4 cascade-eligibility, this validator is run at the
    boundary of --collect (and its result re-checked by self-test on
    every run).
    """
    payload, sha = _read_json_with_sha(path)

    if sha != expected_sha:
        raise SchemaMismatchError(
            f"stimulus JSON SHA mismatch.\n"
            f"  path:     {path}\n"
            f"  actual:   {sha}\n"
            f"  expected: {expected_sha}\n"
            f"  The implementation §0.X is pinned to a specific stimulus "
            f"state. If the stimulus was intentionally updated, "
            f"EXPECTED_STIMULUS_SHA must be updated under fresh "
            f"authorization."
        )

    missing = _STIMULUS_REQUIRED_TOP_KEYS - set(payload.keys())
    if missing:
        raise SchemaMismatchError(
            f"stimulus JSON missing top-level keys: {sorted(missing)}"
        )
    if payload["schema_version"] != _STIMULUS_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"stimulus schema_version mismatch: expected "
            f"{_STIMULUS_SCHEMA_VERSION!r}, got {payload['schema_version']!r}"
        )

    # framing_pool: 25 items, 4 categories, char-span valid, non-empty firewall.
    pool_raw = payload["framing_pool"]
    if len(pool_raw) != N_FRAMING_POOL_ITEMS:
        raise SchemaMismatchError(
            f"framing_pool must have {N_FRAMING_POOL_ITEMS} items; "
            f"got {len(pool_raw)}"
        )
    seen_frame_ids: set[str] = set()
    pool: list[FramingPoolItem] = []
    for i, raw in enumerate(pool_raw):
        for k in ("frame_id", "framing_question", "framing_token_char_span",
                  "framing_category"):
            if k not in raw:
                raise SchemaMismatchError(f"framing_pool[{i}] missing key {k!r}")
        if raw["frame_id"] in seen_frame_ids:
            raise ValueError(f"framing_pool[{i}] duplicate frame_id {raw['frame_id']!r}")
        if raw["framing_category"] not in _VALID_FRAMING_CATEGORIES:
            raise ValueError(
                f"framing_pool[{i}] invalid category {raw['framing_category']!r}; "
                f"must be in {sorted(_VALID_FRAMING_CATEGORIES)}"
            )
        seen_frame_ids.add(raw["frame_id"])
        span_raw = raw["framing_token_char_span"]
        if not (isinstance(span_raw, list) and len(span_raw) == 2
                and all(isinstance(x, int) for x in span_raw)):
            raise SchemaMismatchError(
                f"framing_pool[{i}].framing_token_char_span shape invalid: "
                f"{span_raw!r}"
            )
        framing_substr = _framing_span_substring(
            raw["framing_question"], (span_raw[0], span_raw[1]),
        )
        firewall_tokens = _tokenize_for_disjointness(framing_substr)
        if not firewall_tokens:
            raise ValueError(
                f"framing_pool[{i}] empty firewall vocabulary at span"
            )
        pool.append(FramingPoolItem(
            frame_id=raw["frame_id"],
            framing_question=raw["framing_question"],
            framing_token_char_span=(span_raw[0], span_raw[1]),
            framing_category=raw["framing_category"],
        ))

    # main_chains and calibration_chains topical-disjointness re-check.
    pool_by_frame_id = {p.frame_id: p for p in pool}
    for scope_name, chain_count, allowed_sources in [
        ("main_chains", N_MAIN_CHAINS, SOURCE_ENUM_MAIN),
        ("calibration_chains", N_CALIBRATION_CHAINS, SOURCE_ENUM_CALIBRATION),
    ]:
        chains_raw = payload[scope_name]
        if len(chains_raw) != chain_count:
            raise SchemaMismatchError(
                f"{scope_name} must have {chain_count} chains; got {len(chains_raw)}"
            )
        for c in chains_raw:
            frame = pool_by_frame_id.get(c["frame_id"])
            if frame is None:
                raise ValueError(
                    f"{scope_name}[{c.get('chain_idx')}] references unknown "
                    f"frame_id {c.get('frame_id')!r}"
                )
            firewall = _tokenize_for_disjointness(
                _framing_span_substring(frame.framing_question,
                                        frame.framing_token_char_span)
            )
            for cq in c["chain_questions"]:
                if cq["source"] not in allowed_sources:
                    raise ValueError(
                        f"{scope_name}[{c['chain_idx']}].chain_questions"
                        f"[turn={cq.get('turn_idx')}] source {cq['source']!r} "
                        f"not permitted in {scope_name}; allowed: "
                        f"{sorted(allowed_sources)} (per §15.14-A1)"
                    )
                qtokens = _tokenize_for_disjointness(cq["question"])
                shared = firewall & qtokens
                if shared:
                    raise ValueError(
                        f"{scope_name}[{c['chain_idx']}].chain_questions"
                        f"[turn={cq['turn_idx']}] violates topical-disjointness "
                        f"against frame {c['frame_id']}; shared tokens: "
                        f"{sorted(shared)}"
                    )

    # frame_positive_chains source enum check (no disjointness; per §15.14-A1
    # frame_positive_chains MAY use synthetic_frame_positive_v1).
    fp_raw = payload["frame_positive_chains"]
    if len(fp_raw) != N_FRAME_POSITIVE_CHAINS:
        raise SchemaMismatchError(
            f"frame_positive_chains must have {N_FRAME_POSITIVE_CHAINS} chains; "
            f"got {len(fp_raw)}"
        )
    for c in fp_raw:
        for cq in c["chain_questions"]:
            if cq["source"] not in SOURCE_ENUM_FRAME_POSITIVE:
                raise ValueError(
                    f"frame_positive_chains[{c['chain_idx']}].chain_questions"
                    f"[turn={cq.get('turn_idx')}] source {cq['source']!r} not "
                    f"permitted; allowed: {sorted(SOURCE_ENUM_FRAME_POSITIVE)}"
                )

    return payload, sha


# ---------------------------------------------------------------------------
# Calibration labels JSON validator (cross-SHA against current stimulus)
# ---------------------------------------------------------------------------


_LABELS_REQUIRED_TOP_KEYS = {"schema_version", "stimulus_sha256", "labels"}

_LABELS_SCHEMA_VERSION = "15.14-calibration-labels"

_LABELS_REQUIRED_ROW_KEYS = {
    "chain_idx", "turn_idx", "human_severity_label",
    "human_severity_rationale", "annotator_id", "annotation_timestamp",
}
_LABELS_OPTIONAL_ROW_KEYS = {"model_response_id", "run_id"}


def _validate_calibration_labels_json(
    path: Path = DEFAULT_LABELS_JSON_PATH,
    expected_sha: str = EXPECTED_LABELS_SHA,
    stimulus_sha: str = EXPECTED_STIMULUS_SHA,
) -> tuple[dict, str, dict[tuple[int, int], dict]]:
    """Load + validate the labels artifact.

    Returns (payload, canonical_sha256, labels_by_key) where
    labels_by_key maps (chain_idx, turn_idx) → label-record dict for
    O(1) lookup during Pass C / Pass D.

    Raises SchemaMismatchError on shape drift or SHA mismatch.
    Raises ValueError on content violations (out-of-range label,
    duplicate (chain, turn), unknown row keys, etc.) — caller maps
    to exit 8.
    """
    payload, sha = _read_json_with_sha(path)

    if sha != expected_sha:
        raise SchemaMismatchError(
            f"calibration labels SHA mismatch.\n"
            f"  path:     {path}\n"
            f"  actual:   {sha}\n"
            f"  expected: {expected_sha}\n"
            f"  Implementation §0.X is pinned to a specific labels state."
        )

    missing = _LABELS_REQUIRED_TOP_KEYS - set(payload.keys())
    if missing:
        raise SchemaMismatchError(
            f"labels JSON missing top-level keys: {sorted(missing)}"
        )
    if payload["schema_version"] != _LABELS_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"labels schema_version mismatch: expected "
            f"{_LABELS_SCHEMA_VERSION!r}, got {payload['schema_version']!r}"
        )
    declared_stim_sha = payload.get("stimulus_sha256")
    if declared_stim_sha != stimulus_sha:
        raise SchemaMismatchError(
            f"labels artifact references stimulus_sha256={declared_stim_sha} "
            f"but pinned stimulus SHA is {stimulus_sha}; labels are stale "
            f"or refer to a different stimulus state."
        )

    labels_raw = payload["labels"]
    if not isinstance(labels_raw, list):
        raise SchemaMismatchError("labels must be a JSON array")
    if len(labels_raw) != EVALUATION_ROWS_CALIBRATION:
        raise ValueError(
            f"labels must have {EVALUATION_ROWS_CALIBRATION} entries "
            f"(10 chains × 5 turns); got {len(labels_raw)}"
        )

    labels_by_key: dict[tuple[int, int], dict] = {}
    for i, row in enumerate(labels_raw):
        if not isinstance(row, dict):
            raise SchemaMismatchError(f"labels[{i}] must be an object")
        missing_row = _LABELS_REQUIRED_ROW_KEYS - set(row.keys())
        if missing_row:
            raise SchemaMismatchError(
                f"labels[{i}] missing required keys: {sorted(missing_row)}"
            )
        unknown_row = (
            set(row.keys())
            - _LABELS_REQUIRED_ROW_KEYS
            - _LABELS_OPTIONAL_ROW_KEYS
        )
        if unknown_row:
            raise SchemaMismatchError(
                f"labels[{i}] contains unknown keys: {sorted(unknown_row)}"
            )
        ci, ti = row["chain_idx"], row["turn_idx"]
        if not (isinstance(ci, int) and 0 <= ci < N_CALIBRATION_CHAINS):
            raise ValueError(
                f"labels[{i}].chain_idx must be int in [0, "
                f"{N_CALIBRATION_CHAINS}); got {ci!r}"
            )
        if not (isinstance(ti, int) and 2 <= ti <= K_TURNS):
            raise ValueError(
                f"labels[{i}].turn_idx must be int in [2, {K_TURNS}]; "
                f"got {ti!r}"
            )
        sev = row["human_severity_label"]
        if sev not in SEVERITY_VALUES:
            raise ValueError(
                f"labels[{i}].human_severity_label must be in {SEVERITY_VALUES}; "
                f"got {sev!r}"
            )
        rationale = row["human_severity_rationale"]
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(
                f"labels[{i}].human_severity_rationale must be a non-empty string"
            )
        annotator = row["annotator_id"]
        if not isinstance(annotator, str) or not annotator.strip():
            raise ValueError(
                f"labels[{i}].annotator_id must be a non-empty string"
            )
        ts = row["annotation_timestamp"]
        if not isinstance(ts, str) or not ts.strip():
            raise ValueError(
                f"labels[{i}].annotation_timestamp must be a non-empty string"
            )
        key = (ci, ti)
        if key in labels_by_key:
            raise ValueError(
                f"labels[{i}] duplicates (chain_idx={ci}, turn_idx={ti})"
            )
        labels_by_key[key] = row

    if len(labels_by_key) != EVALUATION_ROWS_CALIBRATION:
        raise ValueError(
            f"after de-duplication labels has only {len(labels_by_key)} unique "
            f"(chain_idx, turn_idx) pairs; expected {EVALUATION_ROWS_CALIBRATION}"
        )
    return payload, sha, labels_by_key


# ---------------------------------------------------------------------------
# Stimulus → typed structures (consumed by Pass A / Pass B)
# ---------------------------------------------------------------------------


def _build_framing_pool(payload: dict) -> dict[str, FramingPoolItem]:
    """Map frame_id → FramingPoolItem from the validated stimulus JSON."""
    pool: dict[str, FramingPoolItem] = {}
    for raw in payload["framing_pool"]:
        span = raw["framing_token_char_span"]
        pool[raw["frame_id"]] = FramingPoolItem(
            frame_id=raw["frame_id"],
            framing_question=raw["framing_question"],
            framing_token_char_span=(span[0], span[1]),
            framing_category=raw["framing_category"],
        )
    return pool


def _build_stimulus_chains(payload: dict, scope: str) -> list[StimulusChain]:
    """Build StimulusChain[] for a given scope ∈ {main, frame_positive, calibration}."""
    scope_to_key = {
        "main": "main_chains",
        "frame_positive": "frame_positive_chains",
        "calibration": "calibration_chains",
    }
    if scope not in scope_to_key:
        raise ValueError(f"unknown scope: {scope!r}")
    chains_raw = payload[scope_to_key[scope]]
    chains: list[StimulusChain] = []
    for c in chains_raw:
        chain_questions = tuple(
            ChainQuestion(
                turn_idx=cq["turn_idx"],
                source=cq["source"],
                q_idx=cq["q_idx"],
                question=cq["question"],
                gold=cq["gold"],
            )
            for cq in c["chain_questions"]
        )
        chains.append(StimulusChain(
            chain_idx=c["chain_idx"],
            frame_id=c["frame_id"],
            chain_questions=chain_questions,
        ))
    return chains


# ---------------------------------------------------------------------------
# HuggingFace dataset loaders (lazy-imported; for q_idx ↔ text validation)
# ---------------------------------------------------------------------------
#
# Per spec Chunk 3, the stimulus JSON's question/gold strings are the
# canonical curation-time text. The HF datasets are loaded only as a
# cross-check to flag drift (warning, not fatal) and to re-resolve text
# if a curation-internal q_idx (e.g., synthetic_frame_positive_v1) is
# absent. Lazy import avoids a hard `datasets` dependency for
# --self-test runs.


def _lazy_import_datasets():
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SchemaMismatchError(
            f"`datasets` package not installed: {e}. "
            f"Required for --collect; not required for --self-test."
        ) from e
    return load_dataset


def _load_hf_truthfulqa_mc():
    """Load TruthfulQA-MC validation split. Returns the HF dataset object."""
    load_dataset = _lazy_import_datasets()
    return load_dataset("truthful_qa", "multiple_choice", split="validation")


def _load_hf_humaneval():
    """Load HumanEval test split. Returns the HF dataset object."""
    load_dataset = _lazy_import_datasets()
    return load_dataset("openai_humaneval", split="test")


# ---------------------------------------------------------------------------
# Lazy torch + transformers loader (used only by --collect)
# ---------------------------------------------------------------------------


def _lazy_import_torch():
    try:
        import torch
    except ImportError as e:
        raise SchemaMismatchError(
            f"`torch` not installed: {e}. Required for --collect."
        ) from e
    return torch


def _lazy_import_transformers():
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise SchemaMismatchError(
            f"`transformers` not installed: {e}. Required for --collect."
        ) from e
    return AutoModelForCausalLM, AutoTokenizer


def _load_subject_model(model_id: str = QWEN_MODEL_ID_SUBJECT):
    """Load Qwen-7B subject model + tokenizer; return (tokenizer, model)."""
    AutoModelForCausalLM, AutoTokenizer = _lazy_import_transformers()
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype="auto",
        device_map="auto",
        output_hidden_states=False,  # turned on per-call in extraction passes
    )
    model.eval()
    return tokenizer, model


# ---------------------------------------------------------------------------
# Framing-token resolver (char_span → tokenizer token positions)
# ---------------------------------------------------------------------------


def _resolve_framing_token_positions(
    tokenizer,
    framing_question: str,
    framing_token_char_span: tuple[int, int],
    full_prompt_text: str,
    full_prompt_input_ids,
) -> tuple[int, int]:
    """Return (start_tok_idx, end_tok_idx_exclusive) of framing span in
    the full chat-template prompt's token sequence.

    Strategy: locate the framing_question's character offset within the
    full prompt text (via str.find), add the char_span offsets, then
    re-tokenize the prefix segments to find token boundaries. This is
    robust to chat-template chrome ([SYS] / [USER] markers, etc.) that
    surround the user message.
    """
    fq_pos = full_prompt_text.find(framing_question)
    if fq_pos < 0:
        raise ValueError(
            "framing_question not found verbatim in chat-template prompt; "
            "tokenizer chat-template may be applying transformations"
        )
    char_start = fq_pos + framing_token_char_span[0]
    char_end = fq_pos + framing_token_char_span[1]

    # Tokenize prefix-up-to-char_start and prefix-up-to-char_end without
    # special-token additions, count tokens.
    prefix_to_start = full_prompt_text[:char_start]
    prefix_to_end = full_prompt_text[:char_end]
    n_tok_to_start = len(tokenizer.encode(prefix_to_start, add_special_tokens=False))
    n_tok_to_end = len(tokenizer.encode(prefix_to_end, add_special_tokens=False))

    # Sanity: end must be after start, and within full prompt length.
    if not (n_tok_to_start < n_tok_to_end <= full_prompt_input_ids.shape[-1]):
        raise ValueError(
            f"framing-token resolution out of bounds: "
            f"start={n_tok_to_start}, end={n_tok_to_end}, "
            f"prompt_len={full_prompt_input_ids.shape[-1]}"
        )
    return n_tok_to_start, n_tok_to_end


# ---------------------------------------------------------------------------
# Pass A — iterative K=6 multi-turn extraction
# ---------------------------------------------------------------------------
#
# For each chain, builds the K=6 chat-template prompt iteratively. At
# each turn t ∈ {1, .., 6}:
#   1. Apply chat template to the current messages list.
#   2. Forward pass with output_hidden_states=True → capture s_t at
#      the last token of the prompt (pre-decode position at the t-th
#      [ASSISTANT] tag).
#   3. If t == 1: also capture f_1 by pooling layer-(-1) hidden states
#      over the framing-token positions inside the turn-1 user message.
#   4. If t >= 2: capture a_prev by pooling layer-(-1) hidden states
#      over the previous turn's assistant token positions in the prompt.
#   5. Generate the t-th assistant response (greedy, max 64 tokens).
#   6. Append to messages list.
#
# After all 6 turns, run a separate single forward pass per turn 2..6
# with the prompt+generated response combined to capture r_t_response
# (mean-pooled response tokens, layer -1, fp32) for the disclosure-only
# response-side variant.


def extract_pass_a_iterative(
    tokenizer,
    model,
    chain: StimulusChain,
    framing: FramingPoolItem,
    chain_scope: str,
) -> ChainExtraction:
    """K=6 iterative multi-turn forward+decode for one chain.

    Returns a ChainExtraction with all 4 vector arrays + decoded text.
    Caller (orchestrator in I-5) is responsible for batching across chains.
    """
    import numpy as np
    torch = _lazy_import_torch()

    n_eval = K_TURNS - 1  # 5 evaluation turns (turn 2..6)
    s_t_arr = np.zeros((n_eval, HIDDEN_DIM), dtype=np.float32)
    q_t_arr_placeholder = np.zeros((n_eval, HIDDEN_DIM), dtype=np.float32)  # filled in Pass B
    a_prev_arr = np.zeros((n_eval, HIDDEN_DIM), dtype=np.float32)
    f_1_arr = np.zeros((HIDDEN_DIM,), dtype=np.float32)
    r_t_response_arr = np.zeros((n_eval, HIDDEN_DIM), dtype=np.float32)

    turn_responses_list: list[str] = []
    turn_1_response = ""
    framing_token_ids: tuple[int, ...] = ()

    # Build messages iteratively.
    messages: list[dict] = [{"role": "user", "content": framing.framing_question}]
    target_device = next(model.parameters()).device

    # Decoded turn-(t-1) assistant text positions in the rolling prompt are
    # tracked by re-tokenizing prefixes; simpler than parsing chat-template
    # internals. Each iteration re-applies the chat template fresh.

    for t in range(1, K_TURNS + 1):
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        encoded = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        )
        input_ids = encoded["input_ids"].to(target_device)
        attention_mask = encoded["attention_mask"].to(target_device)
        prompt_len = input_ids.shape[-1]

        with torch.no_grad():
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                use_cache=False,
            )
        # Last layer's hidden state at last (pre-decode) position.
        hidden_last = outputs.hidden_states[LAYER_IDX][0]  # (seq_len, HIDDEN_DIM)
        s_t_full_context = hidden_last[-1].detach().to(torch.float32).cpu().numpy()

        if t == 1:
            f1_start, f1_end = _resolve_framing_token_positions(
                tokenizer,
                framing.framing_question,
                framing.framing_token_char_span,
                prompt_text,
                input_ids,
            )
            f_1_arr[:] = (
                hidden_last[f1_start:f1_end]
                .mean(dim=0)
                .detach().to(torch.float32).cpu().numpy()
            )
            framing_token_ids = tuple(
                int(x) for x in input_ids[0, f1_start:f1_end].tolist()
            )

        if t >= 2:
            # s_t goes into row (t-2) of the n_eval=5 array.
            s_t_arr[t - 2] = s_t_full_context

            # a_prev: pool over the previous turn's assistant message tokens.
            # Find them by tokenizing the prompt up to the start of the
            # previous assistant message, then up to the end.
            prev_assistant_text = messages[-1]["content"]
            prev_pos = prompt_text.rfind(prev_assistant_text)
            if prev_pos < 0:
                raise ValueError(
                    f"chain {chain.chain_idx} turn {t}: previous assistant "
                    f"text not located in prompt (chat-template drift?)"
                )
            n_tok_to_prev_start = len(
                tokenizer.encode(prompt_text[:prev_pos], add_special_tokens=False)
            )
            n_tok_to_prev_end = len(
                tokenizer.encode(
                    prompt_text[:prev_pos + len(prev_assistant_text)],
                    add_special_tokens=False,
                )
            )
            n_tok_to_prev_end = min(n_tok_to_prev_end, prompt_len)
            if n_tok_to_prev_start >= n_tok_to_prev_end:
                raise ValueError(
                    f"chain {chain.chain_idx} turn {t}: a_prev token range "
                    f"degenerate ({n_tok_to_prev_start}..{n_tok_to_prev_end})"
                )
            a_prev_arr[t - 2] = (
                hidden_last[n_tok_to_prev_start:n_tok_to_prev_end]
                .mean(dim=0)
                .detach().to(torch.float32).cpu().numpy()
            )

        # Decode the t-th assistant response.
        with torch.no_grad():
            out_ids = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=MAX_NEW_TOKENS_SUBJECT,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = out_ids[0, prompt_len:]
        response_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        if t == 1:
            turn_1_response = response_text
        else:
            turn_responses_list.append(response_text)

            # r_t_response disclosure: a forward pass over (prompt + response)
            # to pool layer-(-1) over the response token positions.
            full_ids = out_ids[:, :prompt_len + new_tokens.shape[0]].to(target_device)
            full_attn = torch.ones_like(full_ids)
            with torch.no_grad():
                resp_outputs = model(
                    input_ids=full_ids,
                    attention_mask=full_attn,
                    output_hidden_states=True,
                    use_cache=False,
                )
            resp_hidden = resp_outputs.hidden_states[LAYER_IDX][0]
            if new_tokens.shape[0] >= 1:
                r_t_response_arr[t - 2] = (
                    resp_hidden[prompt_len:prompt_len + new_tokens.shape[0]]
                    .mean(dim=0)
                    .detach().to(torch.float32).cpu().numpy()
                )

        messages.append({"role": "assistant", "content": response_text})

    return ChainExtraction(
        chain_idx=chain.chain_idx,
        frame_id=chain.frame_id,
        chain_scope=chain_scope,
        s_t=s_t_arr,
        q_t=q_t_arr_placeholder,
        a_prev=a_prev_arr,
        f_1=f_1_arr,
        r_t_response=r_t_response_arr,
        turn_responses=tuple(turn_responses_list),
        turn_1_response=turn_1_response,
        framing_token_ids=framing_token_ids,
    )


# ---------------------------------------------------------------------------
# Pass B — standalone Q_t hidden state (q_t)
# ---------------------------------------------------------------------------
#
# For each (chain, turn t ∈ 2..6), build a fresh chat-template prompt
# with ONLY the standalone turn-t question (no turn-1 framing, no prior
# assistant turns). Forward pass; capture last-token hidden state at
# layer -1 — this is q_t per spec Chunk 2 Choice 2.


def extract_pass_b_standalone(
    tokenizer,
    model,
    chain: StimulusChain,
) -> Any:
    """Run K-1 = 5 standalone forward passes for one chain.

    Returns a numpy array of shape (5, HIDDEN_DIM) holding the q_t
    vectors for turns 2..6 of this chain. Caller wires these into
    the chain's ChainExtraction.q_t field, replacing the placeholder
    written by Pass A.
    """
    import numpy as np
    torch = _lazy_import_torch()

    n_eval = K_TURNS - 1
    q_t_arr = np.zeros((n_eval, HIDDEN_DIM), dtype=np.float32)
    target_device = next(model.parameters()).device

    for cq in chain.chain_questions:
        messages = [{"role": "user", "content": cq.question}]
        encoded = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        )
        input_ids = encoded["input_ids"].to(target_device)
        attention_mask = encoded["attention_mask"].to(target_device)

        with torch.no_grad():
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                use_cache=False,
            )
        hidden_last = outputs.hidden_states[LAYER_IDX][0]  # (seq_len, HIDDEN_DIM)
        q_t_arr[cq.turn_idx - 2] = (
            hidden_last[-1].detach().to(torch.float32).cpu().numpy()
        )

    return q_t_arr


# ---------------------------------------------------------------------------
# Cache I/O — save/load extractions as .npz (~40 MB, see spec Chunk 5)
# ---------------------------------------------------------------------------
#
# Layout:
#   schema_version              str          "15.14-extractions"
#   stimulus_sha256             str          (pinned)
#   chain_scope                 (N,) object  per-chain scope
#   chain_idx                   (N,) int64
#   frame_id                    (N,) object
#   s_t                         (N, 5, HIDDEN_DIM) float32
#   q_t                         (N, 5, HIDDEN_DIM) float32
#   a_prev                      (N, 5, HIDDEN_DIM) float32
#   f_1                         (N, HIDDEN_DIM) float32
#   r_t_response                (N, 5, HIDDEN_DIM) float32
#   turn_1_response             (N,) object   variable-length string
#   turn_responses              (N, 5) object variable-length strings
#   framing_token_ids           (N,) object   variable-length int tuples
#
# Chains are flattened across all three scopes in the same arrays;
# chain_scope distinguishes them.


_EXTRACTION_CACHE_SCHEMA_VERSION = "15.14-extractions"


def save_extractions_cache(
    extractions: list[ChainExtraction],
    stimulus_sha: str,
    out_path: Path = DEFAULT_EXTRACTIONS_NPZ_PATH,
) -> None:
    """Atomic .npz write: serialize all extractions for resume on Pass C."""
    import numpy as np

    n = len(extractions)
    chain_scope = np.array([e.chain_scope for e in extractions], dtype=object)
    chain_idx = np.array([e.chain_idx for e in extractions], dtype=np.int64)
    frame_id = np.array([e.frame_id for e in extractions], dtype=object)
    s_t = np.stack([e.s_t for e in extractions], axis=0).astype(np.float32)
    q_t = np.stack([e.q_t for e in extractions], axis=0).astype(np.float32)
    a_prev = np.stack([e.a_prev for e in extractions], axis=0).astype(np.float32)
    f_1 = np.stack([e.f_1 for e in extractions], axis=0).astype(np.float32)
    r_t_response = np.stack([e.r_t_response for e in extractions], axis=0).astype(np.float32)
    turn_1_response = np.array([e.turn_1_response for e in extractions], dtype=object)
    turn_responses = np.array(
        [list(e.turn_responses) for e in extractions], dtype=object,
    )
    framing_token_ids = np.array(
        [list(e.framing_token_ids) for e in extractions], dtype=object,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    np.savez_compressed(
        tmp_path,
        schema_version=np.array([_EXTRACTION_CACHE_SCHEMA_VERSION], dtype=object),
        stimulus_sha256=np.array([stimulus_sha], dtype=object),
        n_chains=np.array([n], dtype=np.int64),
        chain_scope=chain_scope,
        chain_idx=chain_idx,
        frame_id=frame_id,
        s_t=s_t,
        q_t=q_t,
        a_prev=a_prev,
        f_1=f_1,
        r_t_response=r_t_response,
        turn_1_response=turn_1_response,
        turn_responses=turn_responses,
        framing_token_ids=framing_token_ids,
    )
    tmp_path.replace(out_path)


def load_extractions_cache(
    in_path: Path = DEFAULT_EXTRACTIONS_NPZ_PATH,
    expected_stimulus_sha: str = EXPECTED_STIMULUS_SHA,
) -> list[ChainExtraction]:
    """Load + validate extractions cache; return list[ChainExtraction]."""
    import numpy as np

    if not in_path.exists():
        raise SchemaMismatchError(f"extractions cache not found: {in_path}")
    data = np.load(in_path, allow_pickle=True)
    sv = str(data["schema_version"][0])
    if sv != _EXTRACTION_CACHE_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"extractions cache schema_version mismatch: expected "
            f"{_EXTRACTION_CACHE_SCHEMA_VERSION!r}, got {sv!r}"
        )
    cache_stim_sha = str(data["stimulus_sha256"][0])
    if cache_stim_sha != expected_stimulus_sha:
        raise SchemaMismatchError(
            f"extractions cache stimulus_sha256 mismatch: "
            f"got {cache_stim_sha}, expected {expected_stimulus_sha}"
        )

    n = int(data["n_chains"][0])
    extractions: list[ChainExtraction] = []
    for i in range(n):
        extractions.append(ChainExtraction(
            chain_idx=int(data["chain_idx"][i]),
            frame_id=str(data["frame_id"][i]),
            chain_scope=str(data["chain_scope"][i]),
            s_t=data["s_t"][i],
            q_t=data["q_t"][i],
            a_prev=data["a_prev"][i],
            f_1=data["f_1"][i],
            r_t_response=data["r_t_response"][i],
            turn_responses=tuple(data["turn_responses"][i]),
            turn_1_response=str(data["turn_1_response"][i]),
            framing_token_ids=tuple(int(x) for x in data["framing_token_ids"][i]),
        ))
    return extractions


# ===========================================================================
# I-3: Judge loader + severity protocol + κ gate + features + cascade
# ===========================================================================


# ---------------------------------------------------------------------------
# Lazy sklearn + numpy helpers (cosine similarity, AUC, Cohen's κ)
# ---------------------------------------------------------------------------


def _lazy_import_sklearn():
    try:
        from sklearn.metrics import cohen_kappa_score, roc_auc_score
    except ImportError as e:
        raise SchemaMismatchError(
            f"`sklearn` not installed: {e}. Required for --probe / --annotate."
        ) from e
    return cohen_kappa_score, roc_auc_score


def _cosine_fp64(u: Any, v: Any) -> float:
    """Cosine similarity computed in fp64 from any-dtype inputs.

    Returns 0.0 if either input has zero norm (defensive; shouldn't
    occur on real Qwen hidden states but the guard keeps PROBE_FAILED
    in the right exit code domain if it does).
    """
    import numpy as np
    u64 = np.asarray(u, dtype=np.float64)
    v64 = np.asarray(v, dtype=np.float64)
    nu = float((u64 @ u64) ** 0.5)
    nv = float((v64 @ v64) ** 0.5)
    if nu < 1e-12 or nv < 1e-12:
        return 0.0
    return float((u64 @ v64) / (nu * nv))


def _auc_negated(y: list[bool], scores: list[float]) -> float:
    """Compute AUC(-scores, y).

    Per spec Chunk 4 direction convention: lower R_* predicts the
    BCVF-faithful "appropriate non-invocation" target; the AUC is
    therefore against the NEGATED score so that higher AUC means
    better signal in the predicted direction.
    """
    import numpy as np
    cohen_kappa_score, roc_auc_score = _lazy_import_sklearn()
    y_arr = np.asarray(y, dtype=bool)
    s_arr = np.asarray(scores, dtype=np.float64)
    if y_arr.sum() == 0 or y_arr.sum() == len(y_arr):
        # Degenerate single-class case: AUC undefined.
        return float("nan")
    return float(roc_auc_score(y_arr, -s_arr))


def _auc_raw(y: list[bool], scores: list[float]) -> float:
    """Compute AUC(scores, y), no negation (used for frame-positive disclosure)."""
    import numpy as np
    cohen_kappa_score, roc_auc_score = _lazy_import_sklearn()
    y_arr = np.asarray(y, dtype=bool)
    s_arr = np.asarray(scores, dtype=np.float64)
    if y_arr.sum() == 0 or y_arr.sum() == len(y_arr):
        return float("nan")
    return float(roc_auc_score(y_arr, s_arr))


# ---------------------------------------------------------------------------
# Judge model loader (Qwen-72B default; Qwen-7B fallback)
# ---------------------------------------------------------------------------


def _load_judge_model(
    judge_id: str = JUDGE_MODEL_ID_DEFAULT,
    fallback_id: str = JUDGE_MODEL_ID_FALLBACK,
    force_fallback: bool = False,
) -> tuple[Any, Any, str, bool]:
    """Load the LLM-judge model + tokenizer.

    Tries judge_id first; on memory/load failure (or force_fallback=True)
    falls back to fallback_id and records that decision in
    judge_fallback_used. Returns (tokenizer, model, judge_id_used,
    fallback_flag).
    """
    AutoModelForCausalLM, AutoTokenizer = _lazy_import_transformers()

    if force_fallback:
        target = fallback_id
        used_fallback = True
    else:
        target = judge_id
        used_fallback = False

    try:
        tokenizer = AutoTokenizer.from_pretrained(target)
        model = AutoModelForCausalLM.from_pretrained(
            target, torch_dtype="auto", device_map="auto",
        )
        model.eval()
        return tokenizer, model, target, used_fallback
    except Exception as primary_exc:
        if used_fallback:
            raise SchemaMismatchError(
                f"judge fallback model load failed: {primary_exc}"
            ) from primary_exc

    # Primary failed; try fallback.
    try:
        tokenizer = AutoTokenizer.from_pretrained(fallback_id)
        model = AutoModelForCausalLM.from_pretrained(
            fallback_id, torch_dtype="auto", device_map="auto",
        )
        model.eval()
        return tokenizer, model, fallback_id, True
    except Exception as fallback_exc:
        raise SchemaMismatchError(
            f"both judge models failed to load. "
            f"primary ({judge_id}): {primary_exc}; "
            f"fallback ({fallback_id}): {fallback_exc}"
        ) from fallback_exc


# ---------------------------------------------------------------------------
# Single-row judge inference (renders prompt, decodes, parses JSON)
# ---------------------------------------------------------------------------


def _judge_one_row(
    tokenizer,
    model,
    framing_substr: str,
    turn_t_question: str,
    turn_t_response: str,
    *,
    retry_on_json_failure: bool = True,
) -> tuple[int | None, str | None]:
    """Run the LLM-judge on one (framing, question, response) triple.

    Returns (severity, rationale). Severity is 0/1/2 if parsed cleanly,
    or None if the judge's output failed to parse as the pinned JSON
    shape on both attempts (one retry permitted at the same temperature
    per spec Chunk 3).
    """
    torch = _lazy_import_torch()
    target_device = next(model.parameters()).device
    prompt = render_judge_prompt(framing_substr, turn_t_question, turn_t_response)

    def _attempt() -> str:
        encoded = tokenizer(
            prompt, return_tensors="pt", return_attention_mask=True,
        )
        input_ids = encoded["input_ids"].to(target_device)
        attention_mask = encoded["attention_mask"].to(target_device)
        with torch.no_grad():
            out_ids = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                max_new_tokens=MAX_NEW_TOKENS_JUDGE,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = out_ids[0, input_ids.shape[-1]:]
        return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    raw = _attempt()
    parsed = _try_parse_judge_severity(raw)
    if parsed is None and retry_on_json_failure:
        # Single retry at same (deterministic) temperature, per spec Chunk 3.
        raw = _attempt()
        parsed = _try_parse_judge_severity(raw)
    return parsed if parsed is not None else (None, None)


def _try_parse_judge_severity(raw: str) -> tuple[int, str] | None:
    """Parse a single-digit severity (0|1|2) from judge output.

    Effective under §15.14-A3 (single-digit judge response replaces JSON
    output). Strips leading whitespace + leading code-fence markers,
    then takes the FIRST character in {0, 1, 2} within the first 32
    characters of the output. Returns (severity, rationale="") on
    success or None on failure (parse-failure semantics unchanged from
    pre-A3 _try_parse_judge_json).
    """
    text = raw.lstrip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))
        text = text.lstrip()
    window = text[:32]
    for ch in window:
        if ch in ("0", "1", "2"):
            return int(ch), ""
    return None


# ---------------------------------------------------------------------------
# Pass C — LLM-judge severity over all evaluation rows
# ---------------------------------------------------------------------------
#
# Iterates the (chain_scope, chain_idx, turn_idx) triples from all 130
# chains × 5 turns = 650 evaluation rows. For each, renders the frozen
# judge prompt with framing-substr / turn-t-question / turn-t-response
# and runs the judge once (with one retry on JSON-parse failure). The
# resulting severity dict is consumed by:
#   - Pass D κ-gate (calibration rows only): compares to human labels
#   - Feature computation (main rows): drives binary y for cascade
#
# Tracks two failure surfaces:
#   1. JSON-parse-failure rate across all rows; if > 5% the run exits 9
#      ANNOTATION_FAILED before any cascade computation.
#   2. Cohen's κ between judge and human on the 50 calibration rows;
#      computed in Pass D below.


def run_pass_c_judge(
    tokenizer,
    model,
    extractions: list[ChainExtraction],
    stimulus_payload: dict,
) -> tuple[dict[tuple[str, int, int], dict], float]:
    """Run LLM-judge over every evaluation row.

    Returns (severities_by_key, json_parse_failure_rate) where
    severities_by_key maps (chain_scope, chain_idx, turn_idx) → dict
    with 'severity' (int 0/1/2 or None), 'judge_rationale' (str or None),
    'turn_t_question', 'turn_t_response', 'framing_substr'.

    Failure-rate gate: if json_parse_failure_rate > 0.05, caller (I-5)
    exits 9 ANNOTATION_FAILED.
    """
    pool = _build_framing_pool(stimulus_payload)
    main_chains = _build_stimulus_chains(stimulus_payload, "main")
    fp_chains = _build_stimulus_chains(stimulus_payload, "frame_positive")
    cal_chains = _build_stimulus_chains(stimulus_payload, "calibration")
    chains_by_scope = {
        "main": {c.chain_idx: c for c in main_chains},
        "frame_positive": {c.chain_idx: c for c in fp_chains},
        "calibration": {c.chain_idx: c for c in cal_chains},
    }

    severities: dict[tuple[str, int, int], dict] = {}
    n_total = 0
    n_null = 0

    for ext in extractions:
        chain = chains_by_scope[ext.chain_scope][ext.chain_idx]
        frame = pool[ext.frame_id]
        framing_substr = _framing_span_substring(
            frame.framing_question, frame.framing_token_char_span,
        )
        for cq, response_text in zip(chain.chain_questions, ext.turn_responses):
            severity, rationale = _judge_one_row(
                tokenizer, model, framing_substr, cq.question, response_text,
            )
            n_total += 1
            if severity is None:
                n_null += 1
            severities[(ext.chain_scope, ext.chain_idx, cq.turn_idx)] = {
                "severity": severity,
                "judge_rationale": rationale,
                "turn_t_question": cq.question,
                "turn_t_response": response_text,
                "framing_substr": framing_substr,
                "frame_id": ext.frame_id,
                "source": cq.source,
                "q_idx": cq.q_idx,
            }

    failure_rate = n_null / n_total if n_total else 0.0
    return severities, failure_rate


# ---------------------------------------------------------------------------
# Pass D — κ self-test gate (Cohen's κ on 50 calibration rows)
# ---------------------------------------------------------------------------
#
# Compares the LLM-judge's severity (from Pass C) against the human-
# annotated severity (from labels artifact, validated by I-2's
# _validate_calibration_labels_json). If κ < 0.6, exit 9
# ANNOTATION_FAILED — the cascade is not computed on labels that
# can't be reliably reproduced by the judge.


def run_pass_d_kappa_gate(
    severities_by_key: dict[tuple[str, int, int], dict],
    labels_by_key: dict[tuple[int, int], dict],
) -> float:
    """Compute Cohen's κ between LLM-judge and human on calibration rows.

    Caller (I-5 orchestrator) compares κ against KAPPA_GATE_THRESHOLD
    (0.6 inclusive) and exits 9 ANNOTATION_FAILED if it falls short.
    Returns the κ value; raises SchemaMismatchError on missing rows.
    """
    cohen_kappa_score, _roc_auc_score = _lazy_import_sklearn()

    judge_arr: list[int] = []
    human_arr: list[int] = []
    for (chain_idx, turn_idx), human_row in labels_by_key.items():
        key = ("calibration", chain_idx, turn_idx)
        judge_row = severities_by_key.get(key)
        if judge_row is None:
            raise SchemaMismatchError(
                f"Pass C did not produce a judge severity for calibration "
                f"row (chain_idx={chain_idx}, turn_idx={turn_idx})"
            )
        judge_sev = judge_row["severity"]
        if judge_sev is None:
            # Pass C JSON-parse failure → cannot enter κ computation.
            # Treat as κ-incompatible: skip this pair (caller's gate
            # decides if remaining N is sufficient).
            continue
        judge_arr.append(int(judge_sev))
        human_arr.append(int(human_row["human_severity_label"]))

    if len(judge_arr) < EVALUATION_ROWS_CALIBRATION // 2:
        # Fewer than 25 usable pairs: gate cannot be computed reliably.
        # Return -inf so caller's κ < 0.6 check fires.
        return float("-inf")

    kappa = float(cohen_kappa_score(human_arr, judge_arr))
    return kappa


# ---------------------------------------------------------------------------
# Feature computation — R_framing, R_topic_to_framing, R_recency, plus
# disclosure-only response-side variant
# ---------------------------------------------------------------------------
#
# Per spec Chunk 2 sealed formulas:
#   R_framing            = cos(s_t, f_1) - cos(s_t, q_t)
#   R_topic_to_framing   = cos(q_t, f_1)
#   R_recency            = cos(s_t, a_prev) - cos(s_t, q_t)
#   R_framing_response_side (disclosure-only) =
#                          cos(r_t_response, f_1) - cos(r_t_response, q_t)


def compute_features_per_row(
    extractions: list[ChainExtraction],
    severities_by_key: dict[tuple[str, int, int], dict],
    *,
    scope_filter: str | None = None,
) -> list[FramingFeatures]:
    """Build FramingFeatures[] for all evaluation rows.

    Caller (run_framing_probe) typically calls with scope_filter='main'
    for the cascade input set; with scope_filter='frame_positive' for
    the disclosure-only frame-positive AUC; etc.

    severity and y are taken from severities_by_key (the LLM-judge's
    severities from Pass C, since the cascade target on the main set
    is the judge's binary y).
    """
    rows: list[FramingFeatures] = []
    row_idx = 0
    for ext in extractions:
        if scope_filter is not None and ext.chain_scope != scope_filter:
            continue
        for j in range(K_TURNS - 1):
            turn_idx = j + 2
            key = (ext.chain_scope, ext.chain_idx, turn_idx)
            sev_row = severities_by_key.get(key, {})
            severity = sev_row.get("severity")
            y_val = (severity is not None and severity >= 1) if severity is not None else None

            cos_st_f1 = _cosine_fp64(ext.s_t[j], ext.f_1)
            cos_st_qt = _cosine_fp64(ext.s_t[j], ext.q_t[j])
            cos_qt_f1 = _cosine_fp64(ext.q_t[j], ext.f_1)
            cos_st_aprev = _cosine_fp64(ext.s_t[j], ext.a_prev[j])

            r_framing = cos_st_f1 - cos_st_qt
            r_topic_to_framing = cos_qt_f1
            r_recency = cos_st_aprev - cos_st_qt

            cos_rt_f1 = _cosine_fp64(ext.r_t_response[j], ext.f_1)
            cos_rt_qt = _cosine_fp64(ext.r_t_response[j], ext.q_t[j])
            r_framing_response_side = cos_rt_f1 - cos_rt_qt

            rows.append(FramingFeatures(
                row_idx=row_idx,
                chain_idx=ext.chain_idx,
                turn_idx=turn_idx,
                chain_scope=ext.chain_scope,
                source=sev_row.get("source", ""),
                cos_st_f1=cos_st_f1,
                cos_st_qt=cos_st_qt,
                cos_qt_f1=cos_qt_f1,
                cos_st_aprev=cos_st_aprev,
                r_framing=r_framing,
                r_topic_to_framing=r_topic_to_framing,
                r_recency=r_recency,
                r_framing_response_side=r_framing_response_side,
                severity=severity,
                y=y_val,
            ))
            row_idx += 1
    return rows


# ---------------------------------------------------------------------------
# Cascade classifier (4-step, per spec Chunk 4)
# ---------------------------------------------------------------------------
#
# Step 1: direction gate. auc_framing < 0.5 (strict) → NO_MATERIAL.
# Step 2: STRONG. auc_framing ≥ 0.75 AND ΔAUC ≥ 0.05 vs chance, topic, recency.
# Step 3: PARTIAL. auc_framing ≥ 0.66 AND ΔAUC > 0 vs chance, topic, recency.
# Step 4: default NO_MATERIAL.
#
# All AUCs supplied to this function are AUC(-R_*, y) form (higher is
# better signal in the BCVF-faithful direction); chance baseline is 0.5.
#
# No sign-flip rescue. This function is referenced by the 12 self-test
# cases (I-4b) that pin its behavior on synthetic boundary inputs.


def classify_cascade_framing(
    auc_framing: float,
    auc_topic_to_framing: float,
    auc_recency: float,
) -> FramingCascadeVerdict:
    """Mechanical 4-step cascade. Returns FramingCascadeVerdict."""
    direction_held = auc_framing >= DIRECTION_GATE_THRESHOLD
    dauc_chance = auc_framing - CHANCE_BASELINE_AUC
    dauc_topic = auc_framing - auc_topic_to_framing
    dauc_recency = auc_framing - auc_recency

    # Step 1: direction gate (strict < 0.5 fails).
    if not direction_held:
        return FramingCascadeVerdict(
            label=CascadeVerdict.NO_MATERIAL,
            auc_framing=auc_framing,
            auc_topic_to_framing=auc_topic_to_framing,
            auc_recency=auc_recency,
            dauc_vs_chance=dauc_chance,
            dauc_vs_topic_to_framing=dauc_topic,
            dauc_vs_recency=dauc_recency,
            direction_held=False,
            rationale=(
                f"wrong-direction failure: BCVF-faithful direction (lower "
                f"R_framing predicts appropriate non-invocation) did not hold "
                f"(auc_framing = {auc_framing:.4f} < "
                f"{DIRECTION_GATE_THRESHOLD})."
            ),
        )

    # Step 2: STRONG.
    if (
        auc_framing >= STRONG_AUC_THRESHOLD
        and dauc_chance >= STRONG_DELTA_AUC_THRESHOLD
        and dauc_topic >= STRONG_DELTA_AUC_THRESHOLD
        and dauc_recency >= STRONG_DELTA_AUC_THRESHOLD
    ):
        return FramingCascadeVerdict(
            label=CascadeVerdict.STRONG,
            auc_framing=auc_framing,
            auc_topic_to_framing=auc_topic_to_framing,
            auc_recency=auc_recency,
            dauc_vs_chance=dauc_chance,
            dauc_vs_topic_to_framing=dauc_topic,
            dauc_vs_recency=dauc_recency,
            direction_held=True,
            rationale=(
                f"STRONG: auc_framing = {auc_framing:.4f} >= "
                f"{STRONG_AUC_THRESHOLD}; ΔAUC vs chance = {dauc_chance:.4f}, "
                f"vs topic = {dauc_topic:.4f}, vs recency = {dauc_recency:.4f} "
                f"all >= {STRONG_DELTA_AUC_THRESHOLD}."
            ),
        )

    # Step 3: PARTIAL.
    if (
        auc_framing >= PARTIAL_AUC_THRESHOLD
        and dauc_chance > 0
        and dauc_topic > 0
        and dauc_recency > 0
    ):
        return FramingCascadeVerdict(
            label=CascadeVerdict.PARTIAL,
            auc_framing=auc_framing,
            auc_topic_to_framing=auc_topic_to_framing,
            auc_recency=auc_recency,
            dauc_vs_chance=dauc_chance,
            dauc_vs_topic_to_framing=dauc_topic,
            dauc_vs_recency=dauc_recency,
            direction_held=True,
            rationale=(
                f"PARTIAL: auc_framing = {auc_framing:.4f} >= "
                f"{PARTIAL_AUC_THRESHOLD} but did not clear the STRONG bar "
                f"(0.75 + 0.05 ΔAUCs); ΔAUC vs chance = {dauc_chance:.4f}, "
                f"vs topic = {dauc_topic:.4f}, vs recency = {dauc_recency:.4f} "
                f"all > 0 (strict)."
            ),
        )

    # Step 4: default NO_MATERIAL.
    return FramingCascadeVerdict(
        label=CascadeVerdict.NO_MATERIAL,
        auc_framing=auc_framing,
        auc_topic_to_framing=auc_topic_to_framing,
        auc_recency=auc_recency,
        dauc_vs_chance=dauc_chance,
        dauc_vs_topic_to_framing=dauc_topic,
        dauc_vs_recency=dauc_recency,
        direction_held=True,
        rationale=(
            f"NO_MATERIAL: direction held (auc_framing = {auc_framing:.4f} >= "
            f"{DIRECTION_GATE_THRESHOLD}) but cascade conditions not met. "
            f"AUC threshold check (>= {PARTIAL_AUC_THRESHOLD}): "
            f"{auc_framing >= PARTIAL_AUC_THRESHOLD}; ΔAUCs vs (chance, topic, "
            f"recency) = ({dauc_chance:.4f}, {dauc_topic:.4f}, "
            f"{dauc_recency:.4f}); strict-> requires all > 0 (PARTIAL) or "
            f"all >= 0.05 (STRONG)."
        ),
    )


# ---------------------------------------------------------------------------
# Selective-prediction κ@α (disclosure-only; per spec Chunk 4)
# ---------------------------------------------------------------------------
#
# Mirrors §15.10/§15.11/§15.13's selective-prediction operating points.
# For each α ∈ {0.35, 0.50, 0.75}, find the threshold τ on -R_framing
# such that the admitted subset has conditional accuracy >= α with
# n_admitted >= N_MIN_SELECTIVE; record (α, τ, coverage, conditional
# accuracy, κ@α). These are reported in the JSON output but DO NOT
# enter the cascade decision.


def selective_kappa_at_alpha(
    r_framing_array: list[float],
    y_array: list[bool],
    alpha: float,
    *,
    n_min: int = N_MIN_SELECTIVE,
) -> dict:
    """Compute κ@α + diagnostic ops for one α.

    Returns dict with alpha, kappa_at_alpha, tau_star, coverage_at_tau_star,
    conditional_accuracy_at_tau_star, n_admitted_at_tau_star, eligible.
    """
    import numpy as np
    n = len(y_array)
    if n == 0:
        return {
            "alpha": alpha, "kappa_at_alpha": float("nan"),
            "tau_star": None, "coverage_at_tau_star": float("nan"),
            "conditional_accuracy_at_tau_star": float("nan"),
            "n_admitted_at_tau_star": 0, "eligible": False,
        }
    r_arr = np.asarray(r_framing_array, dtype=np.float64)
    y_arr = np.asarray(y_array, dtype=bool)
    # Lower R_framing predicts y=0 (appropriate non-invocation); abstention
    # score is -R_framing (so admitted = scoring above τ).
    score = -r_arr

    sorted_idx = np.argsort(-score)  # descending in score
    best_tau = None
    best_n_admitted = 0
    best_cond_acc = 0.0
    best_kappa_at = 0.0
    for cut in range(1, n + 1):
        admitted_idx = sorted_idx[:cut]
        admitted_y = y_arr[admitted_idx]
        # Predicted label: y_hat = 0 (admitted means we predict appropriate
        # non-invocation, the BCVF-faithful direction).
        y_hat = np.zeros(cut, dtype=bool)
        n_correct = int((y_hat == admitted_y).sum())
        cond_acc = n_correct / cut
        if cond_acc < alpha:
            continue
        if cut < n_min:
            continue
        # Eligible operating point. κ@α = (cond_acc - α) / (1 - α) ∈ [0, 1].
        kappa_at = (cond_acc - alpha) / (1 - alpha) if alpha < 1 else 0.0
        if cut > best_n_admitted or (cut == best_n_admitted and kappa_at > best_kappa_at):
            best_tau = float(score[admitted_idx[-1]])
            best_n_admitted = cut
            best_cond_acc = cond_acc
            best_kappa_at = kappa_at
    eligible = best_n_admitted >= n_min and best_cond_acc >= alpha
    return {
        "alpha": alpha,
        "kappa_at_alpha": float(best_kappa_at) if eligible else float("nan"),
        "tau_star": best_tau if eligible else None,
        "coverage_at_tau_star": (best_n_admitted / n) if eligible else float("nan"),
        "conditional_accuracy_at_tau_star": float(best_cond_acc) if eligible else float("nan"),
        "n_admitted_at_tau_star": int(best_n_admitted) if eligible else 0,
        "eligible": bool(eligible),
    }


# ---------------------------------------------------------------------------
# run_framing_probe — aggregate features → AUCs → cascade verdict
# ---------------------------------------------------------------------------


def run_framing_probe(
    extractions: list[ChainExtraction],
    severities_by_key: dict[tuple[str, int, int], dict],
) -> tuple[FramingProbeResult, FramingCascadeVerdict]:
    """Build the §15.14 probe result + cascade verdict.

    Pipeline:
      1. Compute per-row features for the main set (cascade input).
      2. Filter to rows with severity != None (judge-parseable).
      3. Compute AUC(-R_framing, y), AUC(-R_topic_to_framing, y),
         AUC(-R_recency, y).
      4. Compute disclosure-only frame-positive AUC (raw direction).
      5. Compute disclosure-only response-side AUC (negated direction).
      6. Compute κ@α at three α values.
      7. Run cascade classifier.
    """
    main_rows = compute_features_per_row(extractions, severities_by_key,
                                          scope_filter="main")
    fp_rows = compute_features_per_row(extractions, severities_by_key,
                                        scope_filter="frame_positive")

    valid_main = [r for r in main_rows if r.severity is not None]
    if len(valid_main) == 0:
        raise SchemaMismatchError(
            "run_framing_probe: no main-set rows have judge-parseable severity"
        )

    y_arr = [bool(r.y) for r in valid_main]
    r_framing_arr = [r.r_framing for r in valid_main]
    r_topic_arr = [r.r_topic_to_framing for r in valid_main]
    r_recency_arr = [r.r_recency for r in valid_main]
    r_resp_arr = [r.r_framing_response_side for r in valid_main]

    n_sev_zero = sum(1 for r in main_rows if r.severity == 0)
    n_sev_one = sum(1 for r in main_rows if r.severity == 1)
    n_sev_two = sum(1 for r in main_rows if r.severity == 2)
    n_sev_null = sum(1 for r in main_rows if r.severity is None)

    auc_framing = _auc_negated(y_arr, r_framing_arr)
    auc_topic = _auc_negated(y_arr, r_topic_arr)
    auc_recency = _auc_negated(y_arr, r_recency_arr)
    auc_response_side = _auc_negated(y_arr, r_resp_arr)

    # Frame-positive disclosure: y_pos ≡ severity ≥ 1; raw (non-negated) AUC.
    valid_fp = [r for r in fp_rows if r.severity is not None]
    if valid_fp:
        y_fp = [bool(r.y) for r in valid_fp]
        r_fp = [r.r_framing for r in valid_fp]
        auc_framing_pos = _auc_raw(y_fp, r_fp)
    else:
        auc_framing_pos = None

    direction_held = (
        auc_framing == auc_framing  # not NaN
        and auc_framing >= DIRECTION_GATE_THRESHOLD
    )

    selective_pts = tuple(
        selective_kappa_at_alpha(r_framing_arr, y_arr, a)
        for a in ALPHA_TARGETS
    )
    primary_pt = next(
        (p for p in selective_pts if p["alpha"] == ALPHA_PRIMARY),
        {"kappa_at_alpha": float("nan"), "tau_star": None},
    )

    probe = FramingProbeResult(
        n_evaluation_rows=len(main_rows),
        n_severity_zero=n_sev_zero,
        n_severity_one=n_sev_one,
        n_severity_two=n_sev_two,
        n_severity_null=n_sev_null,
        n_y_zero=sum(1 for v in y_arr if not v),
        n_y_one=sum(1 for v in y_arr if v),
        auc_framing=auc_framing,
        auc_topic_to_framing=auc_topic,
        auc_recency=auc_recency,
        dauc_framing_vs_chance=auc_framing - CHANCE_BASELINE_AUC,
        dauc_framing_vs_topic_to_framing=auc_framing - auc_topic,
        dauc_framing_vs_recency=auc_framing - auc_recency,
        auc_framing_response_side_disclosure=auc_response_side,
        auc_framing_pos=auc_framing_pos,
        direction_held=bool(direction_held),
        r_framing_per_row=tuple(r_framing_arr),
        r_topic_to_framing_per_row=tuple(r_topic_arr),
        r_recency_per_row=tuple(r_recency_arr),
        severity_per_row=tuple(r.severity for r in valid_main),
        y_per_row=tuple(y_arr),
        chain_idx_per_row=tuple(r.chain_idx for r in valid_main),
        turn_idx_per_row=tuple(r.turn_idx for r in valid_main),
        source_per_row=tuple(r.source for r in valid_main),
        selective_prediction_operating_points=selective_pts,
        kappa_at_alpha_primary=primary_pt["kappa_at_alpha"],
        tau_star_at_alpha_primary=primary_pt["tau_star"],
    )
    verdict = classify_cascade_framing(auc_framing, auc_topic, auc_recency)
    return probe, verdict


# ===========================================================================
# I-4a: Class-3 firewall scanner (52 patterns; per §15.14 spec Chunk 5)
# ===========================================================================
#
# The firewall scans rendered markdown for forbidden override-language
# BEFORE the markdown is written to disk. Detection → exit code 4
# INTERPRETATION_VIOLATION; nothing is written. Every pattern is matched
# case-insensitively for non-§ patterns and case-sensitively / literal
# for §-anchored patterns (preserves precise §-numbering semantics).
#
# Pattern inventory (PINNED VERBATIM from §15.14 spec Chunk 5 firewall):
#   16 inherited from §15.10 / §15.7
#   10 inherited from §15.11
#   10 inherited from §15.12
#    8 inherited from §15.13
#    8 §15.14-specific
#  ----
#   52 total → must match EXPECTED_FIREWALL_PATTERN_COUNT


_FIREWALL_PATTERNS_INHERITED_15_10_15_7: tuple[str, ...] = (
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
)

_FIREWALL_PATTERNS_INHERITED_15_11: tuple[str, ...] = (
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
)

_FIREWALL_PATTERNS_INHERITED_15_12: tuple[str, ...] = (
    "§15.10 PARTIAL was wrong",
    "§15.10 PARTIAL should be relaxed",
    "§15.11 NO_MATERIAL should be relaxed",
    "§15.11 direction gate should be relaxed",
    "the bootstrap test was inappropriate",
    "the bootstrap test should be replaced",
    "§15.12 closure should be reopened",
    "§15.12 should authorize REOPEN",
    "§6.1 N=21 sign test was wrong",
    "the autonomy result is invalidated",
)

_FIREWALL_PATTERNS_INHERITED_15_13: tuple[str, ...] = (
    "actually STRONG_SIGNAL_IN_INERTIA despite",
    "should be STRONG_SIGNAL_IN_INERTIA",
    "actually PARTIAL_SIGNAL_IN_INERTIA despite",
    "should be classified as PARTIAL_SIGNAL_IN_INERTIA",
    "the R_sim comparator should be ignored",
    "the same-family pairing was a mistake",
    "the pooling over R_A tokens was wrong",
    "the chance baseline alone is sufficient",
)

_FIREWALL_PATTERNS_15_14_SPECIFIC: tuple[str, ...] = (
    "actually STRONG_SIGNAL_IN_FRAMING despite",
    "should be STRONG_SIGNAL_IN_FRAMING",
    "actually PARTIAL_SIGNAL_IN_FRAMING despite",
    "should be classified as PARTIAL_SIGNAL_IN_FRAMING",
    "the R_topic_to_framing comparator should be ignored",
    "the R_recency comparator should be ignored",
    "the κ self-test gate was inappropriate",
    "§15.13 NO_MATERIAL_SIGNAL_IN_INERTIA is overturned",
)

# Patterns that must be matched LITERALLY (case-sensitive) — these contain
# §-numbers whose precise capitalization is part of the audit trail.
_FIREWALL_LITERAL_PATTERNS: frozenset[str] = frozenset(
    p for p in (
        _FIREWALL_PATTERNS_INHERITED_15_10_15_7
        + _FIREWALL_PATTERNS_INHERITED_15_11
        + _FIREWALL_PATTERNS_INHERITED_15_12
        + _FIREWALL_PATTERNS_INHERITED_15_13
        + _FIREWALL_PATTERNS_15_14_SPECIFIC
    ) if "§" in p
)

# Patterns that match case-insensitively (no §-anchored language).
_FIREWALL_ICASE_PATTERNS: frozenset[str] = frozenset(
    p for p in (
        _FIREWALL_PATTERNS_INHERITED_15_10_15_7
        + _FIREWALL_PATTERNS_INHERITED_15_11
        + _FIREWALL_PATTERNS_INHERITED_15_12
        + _FIREWALL_PATTERNS_INHERITED_15_13
        + _FIREWALL_PATTERNS_15_14_SPECIFIC
    ) if "§" not in p
)

ALL_FIREWALL_PATTERNS: tuple[str, ...] = (
    _FIREWALL_PATTERNS_INHERITED_15_10_15_7
    + _FIREWALL_PATTERNS_INHERITED_15_11
    + _FIREWALL_PATTERNS_INHERITED_15_12
    + _FIREWALL_PATTERNS_INHERITED_15_13
    + _FIREWALL_PATTERNS_15_14_SPECIFIC
)


def _firewall_pattern_count_assertion() -> None:
    """Module-load-time invariant: exactly 52 patterns."""
    if len(ALL_FIREWALL_PATTERNS) != EXPECTED_FIREWALL_PATTERN_COUNT:
        raise AssertionError(
            f"§15.14 spec Chunk 5 pins exactly "
            f"{EXPECTED_FIREWALL_PATTERN_COUNT} firewall patterns; "
            f"got {len(ALL_FIREWALL_PATTERNS)}"
        )
    if len(set(ALL_FIREWALL_PATTERNS)) != EXPECTED_FIREWALL_PATTERN_COUNT:
        raise AssertionError(
            f"firewall patterns contain duplicates"
        )


_firewall_pattern_count_assertion()


def scan_for_forbidden_patterns(text: str) -> list[str]:
    """Return list of forbidden patterns found in `text`.

    Empty list = clean. Caller (markdown writer in I-4d) calls
    enforce_firewall_or_exit on the rendered markdown before write.
    """
    found: list[str] = []
    text_lower = text.lower()
    for p in _FIREWALL_ICASE_PATTERNS:
        if p.lower() in text_lower:
            found.append(p)
    for p in _FIREWALL_LITERAL_PATTERNS:
        if p in text:
            found.append(p)
    return found


def enforce_firewall_or_exit(text: str, context: str = "<markdown>") -> None:
    """Raise SystemExit(EXIT_INTERPRETATION_VIOLATION) on any forbidden match.

    The diagnostic identifies WHICH patterns matched so that the
    operator can locate the offending sentence(s) before any artifact
    lands on disk.
    """
    found = scan_for_forbidden_patterns(text)
    if found:
        sys.stderr.write(
            f"INTERPRETATION_VIOLATION: forbidden override-language "
            f"detected in {context}.\n"
            f"  matched patterns ({len(found)}):\n"
        )
        for p in sorted(set(found)):
            sys.stderr.write(f"    - {p!r}\n")
        sys.stderr.write(
            "  See §15.14 spec Chunk 5 firewall pattern set; nothing "
            "was written.\n"
        )
        sys.exit(EXIT_INTERPRETATION_VIOLATION)


# ===========================================================================
# I-4b: Self-test gate orchestrator
# ===========================================================================
#
# Runs four sub-tests before any data inspection. Any failure → exit 3
# SELF_TEST_FAILED. The gate is invoked by the CLI under --self-test
# and as the first step of the default end-to-end flow (in I-5).
#
#   1. _self_test_cascade        — all 12 SELF_TEST_CASCADE_CASES produce
#                                   the expected verdict via
#                                   classify_cascade_framing.
#   2. _self_test_cosine_invariants — synthetic cosine identities:
#                                   cos(u, u) = 1, cos(u, -u) = -1,
#                                   cos(u, orthogonal) = 0 (within fp64
#                                   tolerance).
#   3. _self_test_firewall       — 52-pattern coverage: every pattern is
#                                   flagged on a positive sample; clean
#                                   §15.14-style text produces zero
#                                   false positives.
#   4. _self_test_topical_disjointness — synthetic stimulus pairs:
#                                   confirm the validator's rule fires
#                                   on a vocabulary-overlapping question
#                                   and clears on a disjoint one.
#
# Returns 0 on full pass; raises SystemExit(3) on any failure.


def _self_test_cascade() -> None:
    """Run all 12 cascade self-test cases; assert each produces expected label."""
    for c in SELF_TEST_CASCADE_CASES:
        v = classify_cascade_framing(
            c.auc_framing, c.auc_topic_to_framing, c.auc_recency,
        )
        if v.label != c.expected:
            sys.stderr.write(
                f"SELF_TEST_FAILED: cascade case {c.case_idx} mismatch.\n"
                f"  inputs: auc_framing={c.auc_framing}, "
                f"topic={c.auc_topic_to_framing}, recency={c.auc_recency}\n"
                f"  expected: {c.expected.value}\n"
                f"  got:      {v.label.value}\n"
                f"  rationale: {c.rationale}\n"
            )
            sys.exit(EXIT_SELF_TEST_FAILED)


def _self_test_cosine_invariants() -> None:
    """Sanity-check fp64 cosine: identity, anti-parallel, orthogonal."""
    import numpy as np

    rng = np.random.default_rng(seed=15_14_0)
    u = rng.standard_normal(HIDDEN_DIM)
    v_orth = np.zeros(HIDDEN_DIM)
    # Build an orthogonal vector by Gram-Schmidt.
    w = rng.standard_normal(HIDDEN_DIM)
    v_orth = w - (w @ u) / (u @ u) * u

    cases = [
        ("cos(u, u)", _cosine_fp64(u, u), 1.0),
        ("cos(u, -u)", _cosine_fp64(u, -u), -1.0),
        ("cos(u, orthogonal)", _cosine_fp64(u, v_orth), 0.0),
    ]
    for label, got, expected in cases:
        if not (abs(got - expected) < 1e-9):
            sys.stderr.write(
                f"SELF_TEST_FAILED: cosine invariant '{label}' = {got} "
                f"(expected {expected}; tolerance 1e-9)\n"
            )
            sys.exit(EXIT_SELF_TEST_FAILED)


def _self_test_firewall() -> None:
    """Verify each of 52 patterns is detected; verify clean text passes."""
    # 52-pattern coverage: each pattern must flag on a positive sample.
    for p in ALL_FIREWALL_PATTERNS:
        # Surround with prose so we test substring match, not exact match.
        sample = f"prelude {p} postlude"
        found = scan_for_forbidden_patterns(sample)
        if not any(p == m or p.lower() == m.lower() for m in found):
            sys.stderr.write(
                f"SELF_TEST_FAILED: firewall pattern not detected on positive "
                f"sample.\n  pattern: {p!r}\n  sample:  {sample!r}\n"
                f"  matched: {found}\n"
            )
            sys.exit(EXIT_SELF_TEST_FAILED)

    # Clean §15.14-style markdown with NONE of the forbidden patterns.
    clean_samples = [
        "## §15.14 cascade verdict\n\nNO_MATERIAL_SIGNAL_IN_FRAMING. Direction held.",
        "Per §15.14 spec Chunk 4, the cascade lands NO_MATERIAL_SIGNAL_IN_FRAMING.",
        "auc_framing = 0.5300; the BCVF-faithful direction held. R_topic_to_framing was the comparator.",
        "§15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved. §15.14 result is independent.",
    ]
    for s in clean_samples:
        found = scan_for_forbidden_patterns(s)
        if found:
            sys.stderr.write(
                f"SELF_TEST_FAILED: firewall false-positive on clean sample.\n"
                f"  sample: {s!r}\n  matched: {found}\n"
            )
            sys.exit(EXIT_SELF_TEST_FAILED)


def _self_test_topical_disjointness() -> None:
    """Synthetic disjointness check: rule fires on overlap, clears on disjoint."""
    overlap_question = "Does astrology predict ocean tides?"
    framing_question = "Using astrology metaphors, explain why ocean tides change daily."
    framing_substr = "astrology metaphors"
    firewall = _tokenize_for_disjointness(framing_substr)

    overlap_tokens = _tokenize_for_disjointness(overlap_question)
    overlap_shared = firewall & overlap_tokens
    if not overlap_shared:
        sys.stderr.write(
            f"SELF_TEST_FAILED: disjointness rule did not flag obvious overlap.\n"
            f"  framing firewall tokens: {sorted(firewall)}\n"
            f"  question tokens: {sorted(overlap_tokens)}\n"
        )
        sys.exit(EXIT_SELF_TEST_FAILED)

    disjoint_question = "What is the boiling point of water?"
    disjoint_tokens = _tokenize_for_disjointness(disjoint_question)
    disjoint_shared = firewall & disjoint_tokens
    if disjoint_shared:
        sys.stderr.write(
            f"SELF_TEST_FAILED: disjointness rule false-positive on disjoint "
            f"question.\n"
            f"  shared tokens: {sorted(disjoint_shared)}\n"
        )
        sys.exit(EXIT_SELF_TEST_FAILED)


def run_self_test_gate(*, verbose: bool = True) -> int:
    """Run all four sub-tests; return 0 on pass, sys.exit(3) on fail."""
    if verbose:
        print("§15.14 self-test gate")
        print("=" * 50)

    if verbose:
        print("[1/4] cascade boundary cases (12) ...")
    _self_test_cascade()
    if verbose:
        print("       PASS ✓ all 12 cascade cases produce expected verdicts")

    if verbose:
        print("[2/4] cosine fp64 invariants (3) ...")
    _self_test_cosine_invariants()
    if verbose:
        print("       PASS ✓ cos(u,u)=1, cos(u,-u)=-1, cos(u,⊥)=0 within 1e-9")

    if verbose:
        print(f"[3/4] firewall pattern coverage (52) + clean negative ...")
    _self_test_firewall()
    if verbose:
        print(f"       PASS ✓ all 52 patterns flagged; 4 clean samples produce 0 matches")

    if verbose:
        print("[4/4] topical-disjointness rule (positive + negative) ...")
    _self_test_topical_disjointness()
    if verbose:
        print("       PASS ✓ rule fires on overlap, clears on disjoint")

    if verbose:
        print("=" * 50)
        print(f"SELF-TEST GATE: ALL PASS ({EXPECTED_FIREWALL_PATTERN_COUNT}-pattern firewall + 12 cascade + 3 cosine + disjointness)")
    return EXIT_SUCCESS


# ===========================================================================
# I-4c: JSON output writer (schema_version "15.14")
# ===========================================================================
#
# Top-level keys are alphabetical (sort_keys=True parity with §15.10/
# §15.11/§15.12/§15.13). The payload exactly matches the §15.14 spec
# Chunk 4 output schema. No additional keys; no key removal.


def _f(x: Any) -> Any:
    """JSON-friendly float coercion: NaN/Inf → None for downstream tooling."""
    import math
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    return x


def write_json_output(
    audit: FramingAuditOutputs,
    out_path: Path = DEFAULT_PROBE_JSON_PATH,
) -> None:
    """Build + write the §15.14 cascade JSON output."""
    probe = audit.probe_result
    verdict = audit.cascade_verdict

    payload = {
        "annotation_protocol": {
            "annotation_failure_rate": _f(audit.annotation_failure_rate),
            "annotation_failure_rate_threshold": ANNOTATION_FAILURE_RATE_THRESHOLD,
            "calibration_kappa": _f(audit.calibration_kappa),
            "calibration_kappa_threshold": KAPPA_GATE_THRESHOLD,
            "calibration_n_rows": EVALUATION_ROWS_CALIBRATION,
            "judge_max_tokens": MAX_NEW_TOKENS_JUDGE,
            "judge_model_id": audit.judge_model_id,
            "judge_prompt_sha256": audit.judge_prompt_sha256,
            "judge_temperature": DECODE_TEMPERATURE_JUDGE,
        },
        "benchmark": BENCHMARK_NAME,
        "calibration_labels_sha256": audit.calibration_labels_sha256,
        "cascade_thresholds": {
            "chance_baseline_auc": CHANCE_BASELINE_AUC,
            "direction_gate_threshold": DIRECTION_GATE_THRESHOLD,
            "partial_auc": PARTIAL_AUC_THRESHOLD,
            "strong_auc": STRONG_AUC_THRESHOLD,
            "strong_delta_auc": STRONG_DELTA_AUC_THRESHOLD,
        },
        "cascade_verdict": {
            "auc_framing": _f(verdict.auc_framing),
            "auc_recency": _f(verdict.auc_recency),
            "auc_topic_to_framing": _f(verdict.auc_topic_to_framing),
            "dauc_vs_chance": _f(verdict.dauc_vs_chance),
            "dauc_vs_recency": _f(verdict.dauc_vs_recency),
            "dauc_vs_topic_to_framing": _f(verdict.dauc_vs_topic_to_framing),
            "direction_held": bool(verdict.direction_held),
            "label": verdict.label.value,
            "rationale": verdict.rationale,
        },
        "cross_phase_disclosure": {
            "phase_1_§15_10_verdict": "PARTIAL_SIGNAL_IN_Z",
            "phase_2_§15_11_verdict": "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE",
            "phase_3_§15_12_status": "sealed (closure outcome)",
            "phase_4_§15_13_verdict": "NO_MATERIAL_SIGNAL_IN_INERTIA",
            "this_phase_modifies": "none",
        },
        "extraction_config": {
            "a_prev_pooling": "mean_over_decoded_assistant_tokens_layer_minus_1_full_context_pass",
            "decode_temperature": DECODE_TEMPERATURE_SUBJECT,
            "f_1_pooling": "mean_over_framing_token_positions_layer_minus_1_full_context_pass",
            "hidden_dim": HIDDEN_DIM,
            "k_turns": K_TURNS,
            "layer_idx": LAYER_IDX,
            "max_new_tokens": MAX_NEW_TOKENS_SUBJECT,
            "q_t_extraction": "last_token_pre_decode_standalone_with_chat_template",
            "s_t_extraction": "last_token_pre_decode_at_t_th_assistant_tag_full_context",
        },
        "frame_positive_disclosure": {
            "auc_framing_pos": _f(probe.auc_framing_pos),
            "auc_framing_pos_direction_consistent": (
                probe.auc_framing_pos is not None
                and not math_isnan(probe.auc_framing_pos)
                and probe.auc_framing_pos >= 0.5
            ),
            "n_frame_positive_chains": N_FRAME_POSITIVE_CHAINS,
            "n_frame_positive_rows": EVALUATION_ROWS_FRAME_POSITIVE,
            "note": "Disclosure-only sign-consistency cross-check; NOT a cascade input.",
        },
        "judge_fallback_used": bool(audit.judge_fallback_used),
        "n_chains": N_MAIN_CHAINS,
        "n_evaluation_rows": EVALUATION_ROWS_MAIN,
        "pairing_rule": audit.pairing_rule_text,
        "phase_5_eligible_outcomes": [v.value for v in CascadeVerdict],
        "probe_result": {
            "alpha_primary": ALPHA_PRIMARY,
            "auc_framing": _f(probe.auc_framing),
            "auc_framing_response_side_disclosure": _f(probe.auc_framing_response_side_disclosure),
            "auc_recency": _f(probe.auc_recency),
            "auc_topic_to_framing": _f(probe.auc_topic_to_framing),
            "chain_idx_per_row": list(probe.chain_idx_per_row),
            "dauc_framing_vs_chance": _f(probe.dauc_framing_vs_chance),
            "dauc_framing_vs_recency": _f(probe.dauc_framing_vs_recency),
            "dauc_framing_vs_topic_to_framing": _f(probe.dauc_framing_vs_topic_to_framing),
            "direction_held": bool(probe.direction_held),
            "kappa_at_alpha_primary": _f(probe.kappa_at_alpha_primary),
            "n_evaluation_rows": probe.n_evaluation_rows,
            "n_severity_null": probe.n_severity_null,
            "n_severity_one": probe.n_severity_one,
            "n_severity_two": probe.n_severity_two,
            "n_severity_zero": probe.n_severity_zero,
            "n_y_one": probe.n_y_one,
            "n_y_zero": probe.n_y_zero,
            "r_framing_per_row": [_f(x) for x in probe.r_framing_per_row],
            "r_recency_per_row": [_f(x) for x in probe.r_recency_per_row],
            "r_topic_to_framing_per_row": [_f(x) for x in probe.r_topic_to_framing_per_row],
            "selective_prediction_operating_points": [
                {k: _f(v) for k, v in pt.items()}
                for pt in probe.selective_prediction_operating_points
            ],
            "severity_per_row": [
                (None if s is None else int(s)) for s in probe.severity_per_row
            ],
            "source_per_row": list(probe.source_per_row),
            "tau_star_at_alpha_primary": _f(probe.tau_star_at_alpha_primary),
            "turn_idx_per_row": list(probe.turn_idx_per_row),
            "y_per_row": [bool(y) for y in probe.y_per_row],
        },
        "qwen_model_id": QWEN_MODEL_ID_SUBJECT,
        "schema_version": SCHEMA_VERSION,
        "stimulus_sha256": audit.stimulus_sha256,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    tmp_path.replace(out_path)


def math_isnan(x: float) -> bool:
    """Local NaN check (avoids polluting top-level namespace with `import math`)."""
    return x != x


# ===========================================================================
# I-4d: Markdown report renderer + firewall-scanned writer (8 sections)
# ===========================================================================
#
# Structure (per spec Chunk 4):
#   1. Header + schema/model/extraction/judge config one-liner
#   2. Cascade verdict (label, rationale, AUC table)
#   3. Probe details (n, severity histogram, AUC + ΔAUCs, per-source breakdown)
#   4. Annotation protocol details (judge model, κ, fallback flag, failure rate)
#   5. Frame-positive disclosure-only block
#   6. Selective-prediction operating points table
#   7. Pinned configuration block (formula, pairing rule, thresholds)
#   8. Caveats + cross-phase comparison + audit-trail integrity
#
# write_markdown_output runs enforce_firewall_or_exit on the rendered
# text BEFORE writing to disk. Any forbidden override-language → exit 4.


def _fmt_auc(x: Any) -> str:
    """Format an AUC for display: 4 dp, 'NaN' on non-finite, 'None' on None."""
    if x is None:
        return "None"
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return "?"
    if math_isnan(xf) or xf != xf:
        return "NaN"
    return f"{xf:.4f}"


def _fmt_kappa_at_alpha_table(points: tuple[dict, ...]) -> str:
    """Markdown table for the 3 selective-prediction operating points."""
    rows = [
        "| α    | eligible | n_admitted | coverage | conditional_acc | κ@α     | τ*      |",
        "|------|----------|------------|----------|-----------------|---------|---------|",
    ]
    for pt in points:
        rows.append(
            f"| {pt['alpha']:.2f} | {str(pt['eligible']):>8} | "
            f"{pt['n_admitted_at_tau_star']:>10} | "
            f"{_fmt_auc(pt['coverage_at_tau_star']):>8} | "
            f"{_fmt_auc(pt['conditional_accuracy_at_tau_star']):>15} | "
            f"{_fmt_auc(pt['kappa_at_alpha']):>7} | "
            f"{_fmt_auc(pt['tau_star']):>7} |"
        )
    return "\n".join(rows)


def _fmt_per_source_breakdown(
    source_per_row: tuple[str, ...],
    severity_per_row: tuple[int | None, ...],
    y_per_row: tuple[bool, ...],
) -> str:
    """Markdown table: per-source severity + y distribution."""
    sources: dict[str, dict[str, int]] = {}
    for src, sev, y in zip(source_per_row, severity_per_row, y_per_row):
        bucket = sources.setdefault(src, {
            "n": 0, "n_sev_0": 0, "n_sev_1": 0, "n_sev_2": 0,
            "n_sev_null": 0, "n_y_1": 0,
        })
        bucket["n"] += 1
        if sev is None:
            bucket["n_sev_null"] += 1
        elif sev == 0:
            bucket["n_sev_0"] += 1
        elif sev == 1:
            bucket["n_sev_1"] += 1
        else:
            bucket["n_sev_2"] += 1
        if y:
            bucket["n_y_1"] += 1
    rows = [
        "| source            | n   | sev=0 | sev=1 | sev=2 | sev=null | y=1 |",
        "|-------------------|-----|-------|-------|-------|----------|-----|",
    ]
    for src in sorted(sources.keys()):
        b = sources[src]
        rows.append(
            f"| {src:<17} | {b['n']:>3} | {b['n_sev_0']:>5} | "
            f"{b['n_sev_1']:>5} | {b['n_sev_2']:>5} | "
            f"{b['n_sev_null']:>8} | {b['n_y_1']:>3} |"
        )
    return "\n".join(rows)


def render_markdown_report(audit: FramingAuditOutputs) -> str:
    """Render the 8-section markdown report. Caller firewall-scans it."""
    probe = audit.probe_result
    verdict = audit.cascade_verdict

    sections: list[str] = []

    # Section 1: header + one-liner config.
    sections.append(
        f"# §15.14 framing-stickiness probe — cascade verdict\n\n"
        f"- **schema_version:** `{SCHEMA_VERSION}`\n"
        f"- **benchmark:** `{BENCHMARK_NAME}`\n"
        f"- **subject:** `{QWEN_MODEL_ID_SUBJECT}`  "
        f"**judge:** `{audit.judge_model_id}`"
        f"{' (fallback used)' if audit.judge_fallback_used else ''}\n"
        f"- **K_TURNS:** {K_TURNS}  "
        f"**N_main:** {N_MAIN_CHAINS}  "
        f"**N_frame_positive:** {N_FRAME_POSITIVE_CHAINS}  "
        f"**N_calibration:** {N_CALIBRATION_CHAINS}\n"
        f"- **stimulus_sha256:** `{audit.stimulus_sha256}`\n"
        f"- **calibration_labels_sha256:** `{audit.calibration_labels_sha256}`\n"
        f"- **judge_prompt_sha256:** `{audit.judge_prompt_sha256}`"
    )

    # Section 2: cascade verdict.
    sections.append(
        f"## Cascade verdict\n\n"
        f"**Label:** `{verdict.label.value}`\n\n"
        f"| metric                  | value     |\n"
        f"|-------------------------|-----------|\n"
        f"| auc_framing             | {_fmt_auc(verdict.auc_framing)}   |\n"
        f"| auc_topic_to_framing    | {_fmt_auc(verdict.auc_topic_to_framing)}   |\n"
        f"| auc_recency             | {_fmt_auc(verdict.auc_recency)}   |\n"
        f"| ΔAUC vs chance (0.5)    | {_fmt_auc(verdict.dauc_vs_chance)}   |\n"
        f"| ΔAUC vs topic           | {_fmt_auc(verdict.dauc_vs_topic_to_framing)}   |\n"
        f"| ΔAUC vs recency         | {_fmt_auc(verdict.dauc_vs_recency)}   |\n"
        f"| direction_held          | {str(verdict.direction_held)}     |\n\n"
        f"**Rationale.** {verdict.rationale}"
    )

    # Section 3: probe details.
    severity_total = (
        probe.n_severity_zero + probe.n_severity_one
        + probe.n_severity_two + probe.n_severity_null
    )
    sections.append(
        f"## Probe details\n\n"
        f"- **n_evaluation_rows:** {probe.n_evaluation_rows}\n"
        f"- **severity histogram (judge):** "
        f"0={probe.n_severity_zero}, 1={probe.n_severity_one}, "
        f"2={probe.n_severity_two}, null={probe.n_severity_null}  "
        f"(total {severity_total})\n"
        f"- **y balance (severity ≥ 1):** "
        f"y=0: {probe.n_y_zero}, y=1: {probe.n_y_one}\n"
        f"- **disclosure: response-side AUC** "
        f"(`R_framing_response_side`): "
        f"{_fmt_auc(probe.auc_framing_response_side_disclosure)}\n\n"
        f"### Per-source breakdown (disclosure-only)\n\n"
        f"{_fmt_per_source_breakdown(probe.source_per_row, probe.severity_per_row, probe.y_per_row)}"
    )

    # Section 4: annotation protocol.
    kappa_pass = (
        not math_isnan(audit.calibration_kappa)
        and audit.calibration_kappa >= KAPPA_GATE_THRESHOLD
    )
    sections.append(
        f"## Annotation protocol\n\n"
        f"- **judge_model_id:** `{audit.judge_model_id}`\n"
        f"- **judge_fallback_used:** {audit.judge_fallback_used}\n"
        f"- **judge_prompt_sha256:** `{audit.judge_prompt_sha256}`\n"
        f"- **judge temperature:** {DECODE_TEMPERATURE_JUDGE}; "
        f"**max tokens:** {MAX_NEW_TOKENS_JUDGE}\n"
        f"- **calibration κ:** {_fmt_auc(audit.calibration_kappa)}  "
        f"(threshold: {KAPPA_GATE_THRESHOLD}; "
        f"pass: {str(kappa_pass)})\n"
        f"- **annotation_failure_rate:** "
        f"{_fmt_auc(audit.annotation_failure_rate)}  "
        f"(threshold: {ANNOTATION_FAILURE_RATE_THRESHOLD})\n"
        f"- **n_calibration_rows:** {EVALUATION_ROWS_CALIBRATION}"
    )

    # Section 5: frame-positive disclosure.
    fp_dir_consistent = (
        probe.auc_framing_pos is not None
        and not math_isnan(probe.auc_framing_pos)
        and probe.auc_framing_pos >= 0.5
    )
    sections.append(
        f"## Frame-positive disclosure (NOT a cascade input)\n\n"
        f"- **n_frame_positive_chains:** {N_FRAME_POSITIVE_CHAINS}\n"
        f"- **n_frame_positive_rows:** {EVALUATION_ROWS_FRAME_POSITIVE}\n"
        f"- **auc_framing_pos:** {_fmt_auc(probe.auc_framing_pos)}\n"
        f"- **direction_consistent (raw direction):** {fp_dir_consistent}\n\n"
        f"Per spec Chunk 2 Choice 7: this is a sign-consistency cross-check, "
        f"not a cascade input. Frame-positive items are stimuli where "
        f"appropriate framing invocation IS the correct behavior."
    )

    # Section 6: selective-prediction operating points (disclosure-only).
    sections.append(
        f"## Selective-prediction operating points (disclosure-only)\n\n"
        f"{_fmt_kappa_at_alpha_table(probe.selective_prediction_operating_points)}\n\n"
        f"**alpha_primary:** {ALPHA_PRIMARY}  "
        f"**κ@α_primary:** {_fmt_auc(probe.kappa_at_alpha_primary)}  "
        f"**τ\\***: {_fmt_auc(probe.tau_star_at_alpha_primary)}"
    )

    # Section 7: pinned configuration.
    sections.append(
        f"## Pinned configuration\n\n"
        f"- **formula:** "
        f"`R_framing = cos(s_t, f_1) - cos(s_t, q_t)`\n"
        f"- **comparators:** "
        f"`R_topic_to_framing = cos(q_t, f_1)`; "
        f"`R_recency = cos(s_t, a_prev) - cos(s_t, q_t)`\n"
        f"- **pairing rule:** {audit.pairing_rule_text}\n"
        f"- **direction convention:** lower R_framing predicts "
        f"appropriate non-invocation; AUC(-R_framing, y).\n"
        f"- **cascade thresholds:** "
        f"DIRECTION_GATE={DIRECTION_GATE_THRESHOLD} (strict); "
        f"PARTIAL_AUC={PARTIAL_AUC_THRESHOLD} (inclusive); "
        f"STRONG_AUC={STRONG_AUC_THRESHOLD} (inclusive); "
        f"STRONG_ΔAUC={STRONG_DELTA_AUC_THRESHOLD} (inclusive vs all 3 baselines).\n"
        f"- **κ gate:** {KAPPA_GATE_THRESHOLD} (inclusive)  "
        f"**y rule:** y=1 iff severity ≥ 1\n"
        f"- **firewall:** {EXPECTED_FIREWALL_PATTERN_COUNT} patterns "
        f"({len(_FIREWALL_ICASE_PATTERNS)} icase + {len(_FIREWALL_LITERAL_PATTERNS)} literal)\n"
        f"- **§15.14-A1 EFFECTIVE:** source enum scoping pinned per spec amendment."
    )

    # Section 8: caveats + cross-phase + audit trail.
    sections.append(
        f"## Caveats and audit trail\n\n"
        f"### Caveats (§0.8-disclosed)\n\n"
        f"- N=500 main-set rows; AUC standard error at AUC≈0.66 with N=500 is ~0.02. "
        f"Cascade thresholds at 0.66 / 0.75 are within sampling noise of finite "
        f"distributions; v1 reports point estimates against pinned bands.\n"
        f"- Carries forward §15.10 / §15.11 / §15.13 caveats by §-reference.\n"
        f"- Frame-positive set is curation-time hand-authored "
        f"(synthetic_frame_positive_v1 source under §15.14-A1); "
        f"auc_framing_pos is disclosure-only.\n"
        f"- κ gate is the only protection against LLM-judge / human "
        f"label drift; passing κ does not guarantee the labels are correct, "
        f"only that judge and human substantially agree.\n\n"
        f"### Cross-phase status table\n\n"
        f"| phase  | mechanism                   | verdict / status           |\n"
        f"|--------|-----------------------------|----------------------------|\n"
        f"| §13.10 | unsupervised entropy        | AUC=0.661 (saturated)      |\n"
        f"| §15.10 | supervised linear           | PARTIAL_SIGNAL_IN_Z        |\n"
        f"| §15.11 | layer-wise phase coherence  | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE |\n"
        f"| §15.12 | synthesis + closure         | sealed                     |\n"
        f"| §15.13 | continuation inertia        | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) |\n"
        f"| §15.14 | framing-stickiness          | `{verdict.label.value}` (this run) |\n\n"
        f"### Audit-trail integrity (§0.8-binding)\n\n"
        f"§13.9 hold preserved. §6.1 N=21 autonomy result preserved. "
        f"§15.10 PARTIAL preserved. §15.11 NO_MATERIAL preserved. "
        f"§15.12 closure preserved. §15.13 NO_MATERIAL preserved. "
        f"This run is independent of all of these. The cascade rule is "
        f"mechanical; the verdict is binding regardless of post-hoc "
        f"interpretation. Firewall-scanned ({EXPECTED_FIREWALL_PATTERN_COUNT} patterns) "
        f"before write."
    )

    return "\n\n".join(sections) + "\n"


def write_markdown_output(
    audit: FramingAuditOutputs,
    out_path: Path = DEFAULT_PROBE_MD_PATH,
) -> None:
    """Render markdown, run firewall scan, write atomically.

    Firewall match → exit EXIT_INTERPRETATION_VIOLATION (4). Nothing
    is written when the firewall fires.
    """
    md = render_markdown_report(audit)
    enforce_firewall_or_exit(md, context=str(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)
    tmp_path.write_text(md)
    tmp_path.replace(out_path)


# ===========================================================================
# I-5: CLI orchestration + main()
# ===========================================================================
#
# Five modes:
#   --self-test            run gate only (12 cascade + cosine + 52-firewall +
#                           topical-disjointness)
#   --collect              load stimulus JSON + labels JSON; run Pass A
#                           (multi-turn) + Pass B (standalone) for all
#                           chains; write extraction cache
#   --annotate             load extraction cache; run Pass C (LLM-judge) +
#                           Pass D (κ self-test gate); write annotated cache
#   --probe                load annotated cache; compute features + cascade
#                           + write JSON+MD outputs
#   (default)              self-test → collect → annotate → probe → write
#
# Cache layout:
#   extractions cache (.npz) carries Pass A/B output (~40 MB)
#   annotated cache (.npz)  carries severities_by_key + κ result


_ANNOTATED_CACHE_SCHEMA_VERSION = "15.14-annotated"


def _save_annotated_cache(
    severities_by_key: dict[tuple[str, int, int], dict],
    annotation_failure_rate: float,
    calibration_kappa: float,
    judge_model_id: str,
    judge_fallback_used: bool,
    out_path: Path = DEFAULT_ANNOTATED_NPZ_PATH,
) -> None:
    """Atomic .npz of severities + κ + provenance for resume by --probe."""
    import numpy as np

    keys = list(severities_by_key.keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_name(out_path.stem + ".tmp" + out_path.suffix)

    # Encode severities as int8 with -1 sentinel for None.
    severity_vals = np.array(
        [
            (-1 if severities_by_key[k]["severity"] is None
             else int(severities_by_key[k]["severity"]))
            for k in keys
        ],
        dtype=np.int8,
    )
    np.savez_compressed(
        tmp_path,
        schema_version=np.array([_ANNOTATED_CACHE_SCHEMA_VERSION], dtype=object),
        chain_scope=np.array([k[0] for k in keys], dtype=object),
        chain_idx=np.array([k[1] for k in keys], dtype=np.int64),
        turn_idx=np.array([k[2] for k in keys], dtype=np.int64),
        severity=severity_vals,
        judge_rationale=np.array(
            [severities_by_key[k]["judge_rationale"] or "" for k in keys],
            dtype=object,
        ),
        annotation_failure_rate=np.array([annotation_failure_rate], dtype=np.float64),
        calibration_kappa=np.array([calibration_kappa], dtype=np.float64),
        judge_model_id=np.array([judge_model_id], dtype=object),
        judge_fallback_used=np.array([bool(judge_fallback_used)], dtype=bool),
    )
    tmp_path.replace(out_path)


def _load_annotated_cache(
    in_path: Path = DEFAULT_ANNOTATED_NPZ_PATH,
) -> tuple[dict[tuple[str, int, int], dict], float, float, str, bool]:
    """Reload severities + κ + provenance for --probe."""
    import numpy as np

    if not in_path.exists():
        raise SchemaMismatchError(f"annotated cache not found: {in_path}")
    data = np.load(in_path, allow_pickle=True)
    sv = str(data["schema_version"][0])
    if sv != _ANNOTATED_CACHE_SCHEMA_VERSION:
        raise SchemaMismatchError(
            f"annotated cache schema_version mismatch: expected "
            f"{_ANNOTATED_CACHE_SCHEMA_VERSION!r}, got {sv!r}"
        )

    severities_by_key: dict[tuple[str, int, int], dict] = {}
    n = len(data["chain_scope"])
    for i in range(n):
        sev_int = int(data["severity"][i])
        sev = None if sev_int == -1 else sev_int
        severities_by_key[(
            str(data["chain_scope"][i]),
            int(data["chain_idx"][i]),
            int(data["turn_idx"][i]),
        )] = {
            "severity": sev,
            "judge_rationale": str(data["judge_rationale"][i]) or None,
            "turn_t_question": "",  # not reloaded; carried by stimulus payload
            "turn_t_response": "",
            "framing_substr": "",
            "frame_id": "",
            "source": "",
            "q_idx": -1,
        }

    return (
        severities_by_key,
        float(data["annotation_failure_rate"][0]),
        float(data["calibration_kappa"][0]),
        str(data["judge_model_id"][0]),
        bool(data["judge_fallback_used"][0]),
    )


def _run_collect(
    stimulus_path: Path,
    labels_path: Path,
    cache_path: Path,
) -> tuple[dict, str, dict]:
    """Pass A + Pass B: extract for all chains, save .npz, return (payload, sha, labels_by_key)."""
    print("[collect] validating stimulus + labels artifacts ...")
    payload, stim_sha = _validate_stimulus_json(stimulus_path)
    labels_payload, labels_sha, labels_by_key = _validate_calibration_labels_json(
        labels_path, expected_sha=EXPECTED_LABELS_SHA, stimulus_sha=stim_sha,
    )
    print(f"  stimulus_sha256:           {stim_sha}")
    print(f"  calibration_labels_sha256: {labels_sha}")
    print()

    print("[collect] loading subject model (Qwen-7B) ...")
    tokenizer, model = _load_subject_model()

    pool = _build_framing_pool(payload)
    all_extractions: list[ChainExtraction] = []

    for scope, chains in (
        ("main", _build_stimulus_chains(payload, "main")),
        ("frame_positive", _build_stimulus_chains(payload, "frame_positive")),
        ("calibration", _build_stimulus_chains(payload, "calibration")),
    ):
        print(f"[collect] scope={scope}: extracting {len(chains)} chains ...")
        for chain in chains:
            frame = pool[chain.frame_id]
            ext = extract_pass_a_iterative(tokenizer, model, chain, frame, scope)
            q_t_arr = extract_pass_b_standalone(tokenizer, model, chain)
            ext_with_qt = ChainExtraction(
                chain_idx=ext.chain_idx, frame_id=ext.frame_id,
                chain_scope=ext.chain_scope,
                s_t=ext.s_t, q_t=q_t_arr, a_prev=ext.a_prev,
                f_1=ext.f_1, r_t_response=ext.r_t_response,
                turn_responses=ext.turn_responses,
                turn_1_response=ext.turn_1_response,
                framing_token_ids=ext.framing_token_ids,
            )
            all_extractions.append(ext_with_qt)
        print(f"  done; cumulative extractions: {len(all_extractions)}")

    print(f"[collect] saving extractions cache → {cache_path} ...")
    save_extractions_cache(all_extractions, stim_sha, cache_path)
    return payload, stim_sha, labels_by_key


def _run_annotate(
    cache_path: Path,
    stimulus_path: Path,
    labels_path: Path,
    annotated_cache_path: Path,
    *,
    force_fallback_judge: bool,
) -> tuple[dict, str, dict, dict, str, bool, float, float]:
    """Pass C + Pass D: judge severities, κ gate, save annotated cache."""
    print("[annotate] re-validating stimulus + labels (lock pin) ...")
    payload, stim_sha = _validate_stimulus_json(stimulus_path)
    labels_payload, labels_sha, labels_by_key = _validate_calibration_labels_json(
        labels_path, expected_sha=EXPECTED_LABELS_SHA, stimulus_sha=stim_sha,
    )

    print(f"[annotate] loading extractions cache from {cache_path} ...")
    extractions = load_extractions_cache(cache_path, expected_stimulus_sha=stim_sha)
    print(f"  loaded {len(extractions)} chains")

    print("[annotate] loading judge model ...")
    tokenizer, model, judge_id_used, fallback_flag = _load_judge_model(
        force_fallback=force_fallback_judge,
    )
    print(f"  judge: {judge_id_used} (fallback_used={fallback_flag})")

    print("[annotate] running Pass C (LLM-judge severity over 650 rows) ...")
    severities_by_key, failure_rate = run_pass_c_judge(
        tokenizer, model, extractions, payload,
    )
    print(f"  json-parse failure rate: {failure_rate:.4f} "
          f"(threshold: {ANNOTATION_FAILURE_RATE_THRESHOLD})")
    if failure_rate > ANNOTATION_FAILURE_RATE_THRESHOLD:
        sys.stderr.write(
            f"ANNOTATION_FAILED: judge JSON-parse failure rate "
            f"{failure_rate:.4f} > threshold {ANNOTATION_FAILURE_RATE_THRESHOLD}; "
            f"cascade not computed.\n"
        )
        sys.exit(EXIT_ANNOTATION_FAILED)

    print("[annotate] running Pass D (Cohen's κ over 50 calibration rows) ...")
    kappa = run_pass_d_kappa_gate(severities_by_key, labels_by_key)
    print(f"  κ = {kappa:.4f} (threshold: {KAPPA_GATE_THRESHOLD})")
    if kappa < KAPPA_GATE_THRESHOLD:
        sys.stderr.write(
            f"ANNOTATION_FAILED: κ = {kappa:.4f} < {KAPPA_GATE_THRESHOLD} "
            f"(inclusive); cascade not computed.\n"
        )
        sys.exit(EXIT_ANNOTATION_FAILED)

    print(f"[annotate] saving annotated cache → {annotated_cache_path} ...")
    _save_annotated_cache(
        severities_by_key, failure_rate, kappa,
        judge_id_used, fallback_flag,
        annotated_cache_path,
    )
    return (
        payload, stim_sha, labels_by_key,
        severities_by_key, judge_id_used, fallback_flag,
        failure_rate, kappa,
    )


def _run_probe(
    cache_path: Path,
    annotated_cache_path: Path,
    stimulus_path: Path,
    labels_path: Path,
    json_out: Path,
    md_out: Path,
) -> tuple[FramingProbeResult, FramingCascadeVerdict]:
    """Compute features + cascade + write JSON + MD."""
    print("[probe] re-validating stimulus + labels (lock pin) ...")
    payload, stim_sha = _validate_stimulus_json(stimulus_path)
    _, labels_sha, _ = _validate_calibration_labels_json(
        labels_path, expected_sha=EXPECTED_LABELS_SHA, stimulus_sha=stim_sha,
    )

    print(f"[probe] loading extractions + annotations from cache ...")
    extractions = load_extractions_cache(cache_path, expected_stimulus_sha=stim_sha)
    severities_by_key, failure_rate, kappa, judge_id_used, fallback_flag = (
        _load_annotated_cache(annotated_cache_path)
    )

    print("[probe] computing features + cascade ...")
    probe, verdict = run_framing_probe(extractions, severities_by_key)

    pairing_rule_text = (
        "K=6 chains; turn-1 = framing_pool[(i*7) mod 25]; "
        "turns 2..6 from curated chain_questions[i] under topical-disjointness rule"
    )
    audit = FramingAuditOutputs(
        probe_result=probe,
        cascade_verdict=verdict,
        judge_model_id=judge_id_used,
        judge_fallback_used=fallback_flag,
        judge_prompt_sha256=judge_prompt_sha256(),
        calibration_kappa=kappa,
        annotation_failure_rate=failure_rate,
        stimulus_sha256=stim_sha,
        calibration_labels_sha256=labels_sha,
        pairing_rule_text=pairing_rule_text,
    )

    print(f"[probe] writing JSON output → {json_out} ...")
    write_json_output(audit, json_out)
    print(f"[probe] writing markdown output → {md_out} (firewall-scanned) ...")
    write_markdown_output(audit, md_out)

    print()
    _print_verdict_banner(verdict)
    return probe, verdict


def _print_verdict_banner(verdict: FramingCascadeVerdict) -> None:
    """Single-line cascade verdict banner (printed at end of every run)."""
    print("=" * 70)
    print(f"§15.14 CASCADE VERDICT: {verdict.label.value}")
    print("=" * 70)
    print(f"  auc_framing             = {verdict.auc_framing:.4f}")
    print(f"  auc_topic_to_framing    = {verdict.auc_topic_to_framing:.4f}")
    print(f"  auc_recency             = {verdict.auc_recency:.4f}")
    print(f"  ΔAUC vs chance          = {verdict.dauc_vs_chance:+.4f}")
    print(f"  ΔAUC vs topic           = {verdict.dauc_vs_topic_to_framing:+.4f}")
    print(f"  ΔAUC vs recency         = {verdict.dauc_vs_recency:+.4f}")
    print(f"  direction_held          = {verdict.direction_held}")
    print()
    print(f"  rationale: {verdict.rationale}")
    print("=" * 70)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="§15.14 framing-stickiness probe (implementation §0.X).",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--self-test", action="store_true",
                      help="Run self-test gate only (12 cascade + cosine + "
                           "52-pattern firewall + topical-disjointness).")
    mode.add_argument("--collect", action="store_true",
                      help="Pass A + Pass B extraction; write extraction cache.")
    mode.add_argument("--annotate", action="store_true",
                      help="Pass C judge + Pass D κ gate; write annotated cache.")
    mode.add_argument("--probe", action="store_true",
                      help="Compute features + cascade; write JSON + MD outputs.")
    p.add_argument("--stimulus-json", default=str(DEFAULT_STIMULUS_JSON_PATH))
    p.add_argument("--labels-json", default=str(DEFAULT_LABELS_JSON_PATH))
    p.add_argument("--cache-path", default=str(DEFAULT_EXTRACTIONS_NPZ_PATH))
    p.add_argument("--annotated-cache-path", default=str(DEFAULT_ANNOTATED_NPZ_PATH))
    p.add_argument("--json-out", default=str(DEFAULT_PROBE_JSON_PATH))
    p.add_argument("--md-out", default=str(DEFAULT_PROBE_MD_PATH))
    p.add_argument("--force-collect", action="store_true",
                   help="Force re-collection even if cache exists.")
    p.add_argument("--force-annotate", action="store_true",
                   help="Force re-annotation even if annotated cache exists.")
    p.add_argument("--judge-fallback", action="store_true",
                   help="Force the Qwen-7B fallback judge (skip 72B attempt).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    # Self-test gate runs first in EVERY mode (per §0.8 discipline).
    run_self_test_gate(verbose=True)
    if args.self_test:
        return EXIT_SUCCESS

    stimulus_path = Path(args.stimulus_json)
    labels_path = Path(args.labels_json)
    cache_path = Path(args.cache_path)
    annotated_cache_path = Path(args.annotated_cache_path)
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)

    do_collect = args.collect or (
        not (args.annotate or args.probe)
        and (args.force_collect or not cache_path.exists())
    )
    do_annotate = args.annotate or (
        not (args.collect or args.probe)
        and (args.force_annotate or not annotated_cache_path.exists())
    )
    do_probe = args.probe or not (args.collect or args.annotate)

    if do_collect:
        _run_collect(stimulus_path, labels_path, cache_path)
        if args.collect:
            return EXIT_SUCCESS

    if do_annotate:
        _run_annotate(
            cache_path, stimulus_path, labels_path,
            annotated_cache_path,
            force_fallback_judge=args.judge_fallback,
        )
        if args.annotate:
            return EXIT_SUCCESS

    if do_probe:
        _run_probe(
            cache_path, annotated_cache_path,
            stimulus_path, labels_path,
            json_out, md_out,
        )

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
