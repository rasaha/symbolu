"""
Interference Cross-Term Diagnostics
=====================================

Per-example logging and 6-step validation of the interference mechanism:

  Step 1 — Collapse Detection
  Step 2 — Correlation Analysis
  Step 3 — Stratified Accuracy
  Step 4 — Comparative Accuracy
  Step 5 — Causal Proxy Check
  Step 6 — Final Determination

Logs are written in JSONL format (one example per line) for clean analysis.
"""

import json
import math
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from torch import Tensor

from resonant_model.evaluator import EvaluationResult, PredictionRecord


# ─── Per-Example Log Entry ────────────────────────────────────────────────────

@dataclass
class ResonanceLogEntry:
    """Logged quantities for a single example."""
    example_id: int
    r_y: float              # resonance score (logit) of true token
    r_neg_max: float        # highest logit among incorrect names
    margin: float           # r_y - r_neg_max
    g: float                # mean gate value at correct-answer positions
    a1_y: float             # mean |a1| norm at correct-answer positions
    a2_y: float             # mean |a2| norm at correct-answer positions
    interference_strength: float  # sqrt(g*(1-g)) * |a1_y| * |a2_y|
    correct: int            # 1 if correct, 0 if wrong
    distance: int           # separation distance
    distractor_count: int   # number of distractors


def write_log(entries: List[ResonanceLogEntry], path: str) -> None:
    """Write log entries to JSONL file."""
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(asdict(entry)) + "\n")


def read_log(path: str) -> List[ResonanceLogEntry]:
    """Read log entries from JSONL file."""
    entries = []
    with open(path) as f:
        for line in f:
            d = json.loads(line.strip())
            entries.append(ResonanceLogEntry(**d))
    return entries


# ─── Extract Log Entries from Evaluation ──────────────────────────────────────

def extract_log_entries(
    model,
    dataset,
    result: EvaluationResult,
    config,
    device=None,
) -> List[ResonanceLogEntry]:
    """
    Run model forward on each example and extract internal tensors
    to build ResonanceLogEntry records.

    Args:
        model: A ResonanceBindingHead (must have get_last_internals).
        dataset: The binding dataset.
        result: EvaluationResult from evaluation (for correctness).
        config: HeadConfig.
        device: torch device.

    Returns:
        List of ResonanceLogEntry, one per example.
    """
    from resonant_model.heads import CharTokenizer, build_name_masks

    device = device or torch.device("cpu")
    tokenizer = CharTokenizer(config.vocab_size)
    model.eval()
    model = model.to(device)

    entries = []
    pred_map = {p.example_id: p for p in result.predictions}

    with torch.no_grad():
        for example in dataset:
            # Tokenize
            token_ids = tokenizer.encode(
                example.passage, example.question, config.max_seq_len,
            ).unsqueeze(0).to(device)

            # Build name masks
            name_masks, padded_names = build_name_masks(
                tokenizer,
                example.passage,
                example.question,
                example.all_names,
                config.max_seq_len,
                config.max_names,
            )
            name_masks = name_masks.to(device)

            # Forward pass
            logits = model(token_ids, name_masks)  # [1, max_names]

            # Get internal tensors
            internals = model.get_last_internals()

            # Extract per-name logits
            num_valid = len(example.all_names)
            valid_logits = logits[0, :num_valid]

            # r_y: logit of correct answer
            try:
                correct_idx = example.all_names.index(example.correct_answer)
            except ValueError:
                continue
            r_y = valid_logits[correct_idx].item()

            # r_neg_max: max logit among incorrect names
            neg_logits = [
                valid_logits[j].item()
                for j in range(num_valid) if j != correct_idx
            ]
            r_neg_max = max(neg_logits) if neg_logits else 0.0

            # Extract g, a1, a2 at correct-answer positions
            # name_masks: [1, max_names, L], correct answer is at index correct_idx
            correct_mask = name_masks[0, correct_idx]  # [L]
            mask_positions = correct_mask.nonzero(as_tuple=True)[0]  # position indices

            if len(mask_positions) > 0 and "g" in internals:
                g_vals = internals["g"]  # [1, L, H]
                a1_vals = internals["a1"]  # [1, L, H, d_h]
                a2_vals = internals["a2"]  # [1, L, H, d_h]

                # Mean over correct-answer positions and heads
                g_at_pos = g_vals[0, mask_positions].mean().item()
                a1_at_pos = a1_vals[0, mask_positions].norm(dim=-1).mean().item()
                a2_at_pos = a2_vals[0, mask_positions].norm(dim=-1).mean().item()
            else:
                g_at_pos = 0.5
                a1_at_pos = 0.0
                a2_at_pos = 0.0

            interference_strength = (
                math.sqrt(g_at_pos * (1.0 - g_at_pos) + 1e-8)
                * abs(a1_at_pos) * abs(a2_at_pos)
            )

            pred = pred_map.get(example.example_id)
            is_correct = pred.is_correct if pred else False

            entries.append(ResonanceLogEntry(
                example_id=example.example_id,
                r_y=r_y,
                r_neg_max=r_neg_max,
                margin=r_y - r_neg_max,
                g=g_at_pos,
                a1_y=a1_at_pos,
                a2_y=a2_at_pos,
                interference_strength=interference_strength,
                correct=1 if is_correct else 0,
                distance=example.separation_distance,
                distractor_count=example.num_distractors,
            ))

    return entries


# ─── Statistical Utilities ────────────────────────────────────────────────────

def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _pearson(xs: List[float], ys: List[float]) -> float:
    """Pearson correlation coefficient."""
    if len(xs) < 2:
        return 0.0
    n = len(xs)
    mx, my = _mean(xs), _mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    sx, sy = _std(xs), _std(ys)
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return cov / (sx * sy)


# ─── 6-Step Validation ───────────────────────────────────────────────────────

@dataclass
class CollapseResult:
    collapsed: bool
    mean_g: float
    std_g: float
    mean_interference: float
    reason: str


@dataclass
class CorrelationResult:
    corr_strength_correct: float
    corr_strength_margin: float
    corr_strength_distance: float
    corr_strength_distractors: float
    interpretation: str


@dataclass
class StratifiedResult:
    low_accuracy: float
    mid_accuracy: float
    high_accuracy: float
    monotonic: bool
    interpretation: str


@dataclass
class ComparativeResult:
    acc_a: float
    acc_b: float
    acc_diff: float
    high_distance_diff: float
    high_distractor_diff: float
    interpretation: str


@dataclass
class CausalProxyResult:
    low_interference_accuracy: float
    high_interference_accuracy: float
    estimated_drop: float
    interpretation: str


@dataclass
class ValidationReport:
    collapse: CollapseResult
    correlation: CorrelationResult
    stratified: StratifiedResult
    comparative: ComparativeResult
    causal_proxy: CausalProxyResult
    final_determination: str
    determination_level: str  # "collapse", "structural", "functional", "breakthrough"


def step1_collapse_detection(entries: List[ResonanceLogEntry]) -> CollapseResult:
    """Step 1: Detect whether Model B collapsed to Case A."""
    gs = [e.g for e in entries]
    strengths = [e.interference_strength for e in entries]

    mean_g = _mean(gs)
    std_g = _std(gs)
    mean_strength = _mean(strengths)

    reasons = []
    collapsed = False

    if mean_g < 0.05 or mean_g > 0.95:
        reasons.append(f"mean(g)={mean_g:.4f} is degenerate (near 0 or 1)")
        collapsed = True
    if std_g < 0.02:
        reasons.append(f"std(g)={std_g:.4f} < 0.02, gate is near-constant")
        collapsed = True
    if mean_strength < 0.01:
        reasons.append(f"mean(interference)={mean_strength:.4f} < 0.01, cross-term negligible")
        collapsed = True

    reason = "; ".join(reasons) if reasons else "No collapse detected"

    return CollapseResult(
        collapsed=collapsed,
        mean_g=mean_g,
        std_g=std_g,
        mean_interference=mean_strength,
        reason=reason,
    )


def step2_correlation_analysis(entries: List[ResonanceLogEntry]) -> CorrelationResult:
    """Step 2: Correlation between interference_strength and outcomes."""
    strengths = [e.interference_strength for e in entries]
    corrects = [float(e.correct) for e in entries]
    margins = [e.margin for e in entries]
    distances = [float(e.distance) for e in entries]
    distractors = [float(e.distractor_count) for e in entries]

    c_correct = _pearson(strengths, corrects)
    c_margin = _pearson(strengths, margins)
    c_distance = _pearson(strengths, distances)
    c_distractors = _pearson(strengths, distractors)

    parts = []
    if c_correct >= 0.30:
        parts.append(f"Strong correlation with correctness ({c_correct:.3f})")
    elif c_correct >= 0.20:
        parts.append(f"Moderate correlation with correctness ({c_correct:.3f})")
    elif c_correct >= 0.15:
        parts.append(f"Weak correlation with correctness ({c_correct:.3f})")
    else:
        parts.append(f"No meaningful correlation with correctness ({c_correct:.3f})")

    if c_margin >= 0.25:
        parts.append(f"correlated with margin ({c_margin:.3f})")
    else:
        parts.append(f"weak/no margin correlation ({c_margin:.3f})")

    return CorrelationResult(
        corr_strength_correct=c_correct,
        corr_strength_margin=c_margin,
        corr_strength_distance=c_distance,
        corr_strength_distractors=c_distractors,
        interpretation="; ".join(parts),
    )


def step3_stratified_accuracy(entries: List[ResonanceLogEntry]) -> StratifiedResult:
    """Step 3: Accuracy stratified by interference strength terciles."""
    if not entries:
        return StratifiedResult(0, 0, 0, False, "No data")

    sorted_entries = sorted(entries, key=lambda e: e.interference_strength)
    n = len(sorted_entries)
    t1 = n // 3
    t2 = 2 * n // 3

    low = sorted_entries[:t1]
    mid = sorted_entries[t1:t2]
    high = sorted_entries[t2:]

    low_acc = _mean([float(e.correct) for e in low]) if low else 0.0
    mid_acc = _mean([float(e.correct) for e in mid]) if mid else 0.0
    high_acc = _mean([float(e.correct) for e in high]) if high else 0.0

    monotonic = low_acc <= mid_acc <= high_acc

    if monotonic and high_acc - low_acc > 0.10:
        interp = f"Monotonically increasing: {low_acc:.1%} -> {mid_acc:.1%} -> {high_acc:.1%}. Supports functional contribution."
    elif monotonic:
        interp = f"Weakly monotonic: {low_acc:.1%} -> {mid_acc:.1%} -> {high_acc:.1%}. Trend present but small."
    else:
        interp = f"Non-monotonic: {low_acc:.1%} -> {mid_acc:.1%} -> {high_acc:.1%}. Does not support functional contribution."

    return StratifiedResult(
        low_accuracy=low_acc,
        mid_accuracy=mid_acc,
        high_accuracy=high_acc,
        monotonic=monotonic,
        interpretation=interp,
    )


def step4_comparative_accuracy(
    result_a: EvaluationResult,
    result_b: EvaluationResult,
) -> ComparativeResult:
    """Step 4: Compare Model A vs Model B overall and on hard subsets."""
    from resonant_model.pass_criteria import (
        _extract_high_distance_subset,
        _extract_high_distractor_subset,
        _subset_accuracy,
    )

    acc_a = result_a.accuracy
    acc_b = result_b.accuracy
    diff = acc_b - acc_a

    hd_a = _subset_accuracy(_extract_high_distance_subset(result_a.predictions))
    hd_b = _subset_accuracy(_extract_high_distance_subset(result_b.predictions))
    hd_diff = hd_b - hd_a

    hdistr_a = _subset_accuracy(_extract_high_distractor_subset(result_a.predictions))
    hdistr_b = _subset_accuracy(_extract_high_distractor_subset(result_b.predictions))
    hdistr_diff = hdistr_b - hdistr_a

    parts = []
    if diff >= 0.10:
        parts.append(f"Strong overall improvement: {diff:+.1%}")
    elif diff >= 0.05:
        parts.append(f"Moderate overall improvement: {diff:+.1%}")
    else:
        parts.append(f"Marginal/no overall improvement: {diff:+.1%}")

    if hd_diff >= 0.10:
        parts.append(f"High-distance subset: {hd_diff:+.1%}")
    if hdistr_diff >= 0.10:
        parts.append(f"High-distractor subset: {hdistr_diff:+.1%}")

    return ComparativeResult(
        acc_a=acc_a,
        acc_b=acc_b,
        acc_diff=diff,
        high_distance_diff=hd_diff,
        high_distractor_diff=hdistr_diff,
        interpretation="; ".join(parts),
    )


def step5_causal_proxy(entries: List[ResonanceLogEntry]) -> CausalProxyResult:
    """Step 5: Compare low-interference vs high-interference accuracy as ablation proxy."""
    if not entries:
        return CausalProxyResult(0, 0, 0, "No data")

    sorted_entries = sorted(entries, key=lambda e: e.interference_strength)
    n = len(sorted_entries)
    t1 = n // 3
    t2 = 2 * n // 3

    low = sorted_entries[:t1]
    high = sorted_entries[t2:]

    low_acc = _mean([float(e.correct) for e in low]) if low else 0.0
    high_acc = _mean([float(e.correct) for e in high]) if high else 0.0
    drop = high_acc - low_acc

    if drop > 0.10:
        interp = f"Estimated {drop:.1%} accuracy drop if interference disabled. Supports causal contribution."
    elif drop > 0.05:
        interp = f"Estimated {drop:.1%} accuracy drop. Moderate evidence for causal contribution."
    else:
        interp = f"Estimated {drop:.1%} difference. Weak/no evidence for causal contribution."

    return CausalProxyResult(
        low_interference_accuracy=low_acc,
        high_interference_accuracy=high_acc,
        estimated_drop=drop,
        interpretation=interp,
    )


def step6_final_determination(
    collapse: CollapseResult,
    correlation: CorrelationResult,
    stratified: StratifiedResult,
    comparative: ComparativeResult,
    causal_proxy: CausalProxyResult,
) -> Tuple[str, str]:
    """Step 6: Final determination based on all steps."""

    if collapse.collapsed:
        return (
            "COLLAPSE: Interference mechanism is unused. "
            f"Reason: {collapse.reason}",
            "collapse",
        )

    functional_signals = 0

    # Correlation thresholds
    if correlation.corr_strength_correct >= 0.20:
        functional_signals += 1
    if correlation.corr_strength_margin >= 0.25:
        functional_signals += 1

    # Stratified monotonicity
    if stratified.monotonic and stratified.high_accuracy - stratified.low_accuracy > 0.05:
        functional_signals += 1

    # Causal proxy
    if causal_proxy.estimated_drop > 0.05:
        functional_signals += 1

    # Comparative accuracy
    if comparative.acc_diff >= 0.05:
        functional_signals += 1

    # Breakthrough check
    breakthrough = (
        correlation.corr_strength_correct >= 0.30
        and comparative.acc_diff >= 0.10
        and comparative.high_distance_diff >= 0.12
        and comparative.high_distractor_diff >= 0.12
    )

    if breakthrough:
        return (
            "BREAKTHROUGH CANDIDATE: Interference strongly improves binding. "
            f"Overall gain: {comparative.acc_diff:+.1%}, "
            f"HD gain: {comparative.high_distance_diff:+.1%}, "
            f"Corr: {correlation.corr_strength_correct:.3f}.",
            "breakthrough",
        )

    if functional_signals >= 3:
        return (
            f"FUNCTIONAL: Interference correlates with improved binding "
            f"({functional_signals}/5 signals). "
            f"Overall gain: {comparative.acc_diff:+.1%}, "
            f"Corr(strength, correct): {correlation.corr_strength_correct:.3f}.",
            "functional",
        )

    if functional_signals >= 1:
        return (
            f"STRUCTURAL BUT NON-FUNCTIONAL: Interference is active "
            f"but weakly correlated with performance "
            f"({functional_signals}/5 signals). "
            f"Corr(strength, correct): {correlation.corr_strength_correct:.3f}.",
            "structural",
        )

    return (
        "NO EVIDENCE: Interference is active but uncorrelated with binding accuracy.",
        "structural",
    )


def run_validation(
    entries_b: List[ResonanceLogEntry],
    result_a: EvaluationResult,
    result_b: EvaluationResult,
) -> ValidationReport:
    """Run full 6-step validation and return structured report."""

    collapse = step1_collapse_detection(entries_b)
    correlation = step2_correlation_analysis(entries_b)
    stratified = step3_stratified_accuracy(entries_b)
    comparative = step4_comparative_accuracy(result_a, result_b)
    causal_proxy = step5_causal_proxy(entries_b)
    determination, level = step6_final_determination(
        collapse, correlation, stratified, comparative, causal_proxy,
    )

    return ValidationReport(
        collapse=collapse,
        correlation=correlation,
        stratified=stratified,
        comparative=comparative,
        causal_proxy=causal_proxy,
        final_determination=determination,
        determination_level=level,
    )


def format_validation_report(report: ValidationReport) -> str:
    """Format validation report as structured text."""
    lines = []
    lines.append("=" * 72)
    lines.append("INTERFERENCE CROSS-TERM VALIDATION")
    lines.append("=" * 72)
    lines.append("")

    # Step 1
    lines.append("─── Step 1: Collapse Detection ───")
    c = report.collapse
    status = "COLLAPSED" if c.collapsed else "OK"
    lines.append(f"  Status:    {status}")
    lines.append(f"  mean(g):   {c.mean_g:.4f}")
    lines.append(f"  std(g):    {c.std_g:.4f}")
    lines.append(f"  mean(I):   {c.mean_interference:.4f}")
    lines.append(f"  {c.reason}")
    lines.append("")

    # Step 2
    lines.append("─── Step 2: Correlation Analysis ───")
    r = report.correlation
    lines.append(f"  Corr(strength, correct):     {r.corr_strength_correct:+.3f}")
    lines.append(f"  Corr(strength, margin):      {r.corr_strength_margin:+.3f}")
    lines.append(f"  Corr(strength, distance):    {r.corr_strength_distance:+.3f}")
    lines.append(f"  Corr(strength, distractors): {r.corr_strength_distractors:+.3f}")
    lines.append(f"  {r.interpretation}")
    lines.append("")

    # Step 3
    lines.append("─── Step 3: Stratified Accuracy ───")
    s = report.stratified
    lines.append(f"  Low interference:  {s.low_accuracy:.1%}")
    lines.append(f"  Mid interference:  {s.mid_accuracy:.1%}")
    lines.append(f"  High interference: {s.high_accuracy:.1%}")
    lines.append(f"  Monotonic: {s.monotonic}")
    lines.append(f"  {s.interpretation}")
    lines.append("")

    # Step 4
    lines.append("─── Step 4: Comparative Accuracy ───")
    v = report.comparative
    lines.append(f"  Model A: {v.acc_a:.1%}")
    lines.append(f"  Model B: {v.acc_b:.1%}")
    lines.append(f"  Overall diff: {v.acc_diff:+.1%}")
    lines.append(f"  High-distance diff: {v.high_distance_diff:+.1%}")
    lines.append(f"  High-distractor diff: {v.high_distractor_diff:+.1%}")
    lines.append(f"  {v.interpretation}")
    lines.append("")

    # Step 5
    lines.append("─── Step 5: Causal Proxy Check ───")
    p = report.causal_proxy
    lines.append(f"  Low-interference accuracy:  {p.low_interference_accuracy:.1%}")
    lines.append(f"  High-interference accuracy: {p.high_interference_accuracy:.1%}")
    lines.append(f"  Estimated drop: {p.estimated_drop:+.1%}")
    lines.append(f"  {p.interpretation}")
    lines.append("")

    # Step 6
    lines.append("─── Step 6: Final Determination ───")
    lines.append(f"  Level: {report.determination_level.upper()}")
    lines.append(f"  {report.final_determination}")
    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)
