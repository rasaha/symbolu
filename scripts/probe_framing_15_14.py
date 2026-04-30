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
JUDGE_MODEL_ID_FALLBACK = "Qwen/Qwen2.5-7B-Instruct"

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
MAX_NEW_TOKENS_JUDGE = 128

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

Return JSON: {"severity": 0|1|2, "rationale": "<one short sentence>"}.
Do not return any other text.

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
