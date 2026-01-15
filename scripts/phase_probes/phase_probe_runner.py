#!/usr/bin/env python3
"""
PhaseAttention Behavioral Probe Runner
=======================================

A standalone diagnostic script to test what PhaseAttention layers are learning
behaviorally. This is a scientific probe, not a training script.

Key Questions This Script Answers:
1. Does PhaseAttention enable correct pronoun/reference resolution?
2. Does phase disruption (scramble/freeze) break relational reasoning?
3. Is phase actually contributing, or is it decorative?

Usage:
    python phase_probe_runner.py --checkpoint checkpoints/best.pt
    python phase_probe_runner.py --checkpoint checkpoints/best.pt --verbose
    python phase_probe_runner.py --checkpoint checkpoints/best.pt --probe RB1

Hard Constraints:
- Does NOT modify model architecture
- Does NOT add or change any loss
- Does NOT depend on CSR/SRK internals
- Runs POST-TRAINING on a checkpoint
- Outputs MEASURABLE, COMPARABLE metrics

Author: Claude (Diagnostic Script for PhaseAttention)
Date: January 2026
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import math

import torch
import torch.nn as nn
import torch.nn.functional as F

# Add parent directories to path
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(script_dir))

# Import probe cases
from probe_cases import (
    MinimalPairProbe,
    SingleProbe,
    ProbeCategory,
    MINIMAL_PAIR_PROBES,
    SINGLE_PROBES,
    get_probe_by_id,
    get_all_probe_ids,
    construct_qa_prompt,
)

# Import ablation utilities
from phase_ablation import (
    AblationMode,
    AblationResult,
    run_ablated_inference,
)


# =============================================================================
# RESULT DATA STRUCTURES
# =============================================================================

@dataclass
class ProbeResult:
    """Result from running a single probe."""
    probe_id: str
    category: str
    mode: str                         # Ablation mode
    text: str                         # Input text used
    question: str
    expected_answer: str
    model_answer: str                 # Top predicted token
    is_correct: bool
    confidence: float                 # Probability of predicted token
    log_prob: float                   # Log probability
    margin: float                     # logP(correct) - logP(best_wrong)
    target_log_prob: float            # Log prob of expected token
    # Phase health metrics
    R_k: float
    R_q: float
    amp_phase_corr: float
    head_redundancy: float
    phase_drift_mean: float
    phase_drift_std: float


@dataclass
class AblationComparison:
    """Comparison of a probe across different ablation modes."""
    probe_id: str
    category: str
    baseline_margin: float
    scramble_margin: float
    frozen_margin: float
    delta_scramble: float             # baseline - scramble
    delta_frozen: float               # baseline - frozen
    phase_sensitive: bool             # True if ablation hurts performance
    baseline_correct: bool
    scramble_correct: bool
    frozen_correct: bool


@dataclass
class ProbeSuiteResults:
    """Aggregate results from the full probe suite."""
    timestamp: str
    checkpoint_path: str
    total_probes: int
    # Accuracy metrics
    baseline_accuracy: float
    scramble_accuracy: float
    frozen_accuracy: float
    # Phase sensitivity metrics
    phase_sensitive_count: int        # Probes where ablation hurts
    phase_sensitive_pct: float
    mean_delta_scramble: float        # Average margin drop from scramble
    mean_delta_frozen: float          # Average margin drop from frozen
    # Phase health (averaged over all probes)
    mean_R_k: float
    mean_R_q: float
    mean_amp_phase_corr: float
    mean_head_redundancy: float
    # Failure signatures
    phase_is_decorative: bool         # Delta ~ 0 everywhere
    phase_is_brittle: bool            # Scramble breaks everything
    amplitude_cheating: bool          # High amp-phase correlation
    # Per-probe results
    probe_results: List[Dict[str, Any]]
    comparisons: List[Dict[str, Any]]


# =============================================================================
# MODEL LOADING
# =============================================================================

def load_model_and_tokenizer(checkpoint_path: str, device: torch.device):
    """
    Load model from checkpoint with tokenizer.

    Supports multiple model types from train_unified_llm.py.
    """
    from train_unified_llm import UnifiedTrainingConfig, create_model

    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Extract config
    config_dict = checkpoint.get('config', {})
    config = UnifiedTrainingConfig(**config_dict)

    # Create model
    model = create_model(config)
    model.load_state_dict(checkpoint['model'], strict=False)
    model.to(device)
    model.eval()

    # Get tokenizer
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
    except ImportError:
        raise ImportError("transformers package required for tokenizer")

    print(f"  Model type: {type(model).__name__}")
    print(f"  Device: {device}")

    return model, tokenizer, config


# =============================================================================
# INFERENCE UTILITIES
# =============================================================================

def get_next_token_probs(
    model: nn.Module,
    tokenizer,
    text: str,
    device: torch.device,
    ablation_mode: AblationMode = AblationMode.BASELINE,
    scramble_seed: int = 42,
) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, float]]:
    """
    Get next-token probability distribution for a given text.

    Returns:
        probs: [vocab_size] probability distribution
        log_probs: [vocab_size] log probabilities
        health: Phase health metrics
    """
    # Tokenize
    tokens = tokenizer.encode(text, return_tensors="pt").to(device)

    # Run inference with ablation
    result = run_ablated_inference(
        model=model,
        input_ids=tokens,
        mode=ablation_mode,
        enable_health_capture=True,
        scramble_seed=scramble_seed,
    )

    # Get logits for last position
    logits = result.logits[:, -1, :]  # [1, vocab_size]

    # Convert to probabilities
    probs = F.softmax(logits, dim=-1).squeeze(0)     # [vocab_size]
    log_probs = F.log_softmax(logits, dim=-1).squeeze(0)  # [vocab_size]

    return probs, log_probs, result.phase_health


def compute_answer_metrics(
    probs: torch.Tensor,
    log_probs: torch.Tensor,
    target_tokens: List[str],
    distractor_tokens: List[str],
    tokenizer,
) -> Dict[str, Any]:
    """
    Compute answer metrics given probability distribution.

    Returns:
        Dict with:
        - top_token: Most probable token
        - top_prob: Its probability
        - target_log_prob: Max log prob among target tokens
        - margin: log(target) - log(best_non_target)
        - is_correct: Whether top token is in targets
    """
    # Get top prediction
    top_prob, top_idx = probs.max(dim=0)
    top_token = tokenizer.decode([top_idx.item()]).strip()

    # Get target token IDs and probabilities
    target_ids = []
    for t in target_tokens:
        try:
            # Try with and without space
            for variant in [t, " " + t.strip(), t.strip()]:
                encoded = tokenizer.encode(variant, add_special_tokens=False)
                if encoded:
                    target_ids.extend(encoded)
        except:
            pass
    target_ids = list(set(target_ids))

    # Get distractor token IDs
    distractor_ids = []
    for t in distractor_tokens:
        try:
            for variant in [t, " " + t.strip(), t.strip()]:
                encoded = tokenizer.encode(variant, add_special_tokens=False)
                if encoded:
                    distractor_ids.extend(encoded)
        except:
            pass
    distractor_ids = list(set(distractor_ids))

    # Compute target log prob (max over target tokens)
    if target_ids:
        target_log_prob = log_probs[target_ids].max().item()
    else:
        target_log_prob = float('-inf')

    # Compute margin: log(best_target) - log(best_non_target)
    # Get log prob of best non-target token
    mask = torch.ones_like(log_probs, dtype=torch.bool)
    if target_ids:
        mask[target_ids] = False
    non_target_log_probs = log_probs.clone()
    non_target_log_probs[~mask] = float('-inf')

    if mask.any():
        best_non_target_log_prob = non_target_log_probs.max().item()
    else:
        best_non_target_log_prob = float('-inf')

    margin = target_log_prob - best_non_target_log_prob

    # Check if correct
    is_correct = top_idx.item() in target_ids if target_ids else False

    return {
        'top_token': top_token,
        'top_prob': top_prob.item(),
        'top_log_prob': log_probs[top_idx].item(),
        'target_log_prob': target_log_prob,
        'margin': margin,
        'is_correct': is_correct,
    }


# =============================================================================
# PROBE EXECUTION
# =============================================================================

def run_single_probe(
    model: nn.Module,
    tokenizer,
    probe: SingleProbe,
    device: torch.device,
    mode: AblationMode = AblationMode.BASELINE,
    scramble_seed: int = 42,
) -> ProbeResult:
    """
    Run a single (non-minimal-pair) probe with specified ablation.
    """
    # Construct prompt
    prompt = construct_qa_prompt(probe.text, probe.question)

    # Get probabilities
    probs, log_probs, health = get_next_token_probs(
        model, tokenizer, prompt, device, mode, scramble_seed
    )

    # Compute answer metrics
    metrics = compute_answer_metrics(
        probs, log_probs, probe.target_tokens, probe.distractor_tokens, tokenizer
    )

    return ProbeResult(
        probe_id=probe.id,
        category=probe.category.value,
        mode=mode.value,
        text=probe.text,
        question=probe.question,
        expected_answer=probe.correct_answer,
        model_answer=metrics['top_token'],
        is_correct=metrics['is_correct'],
        confidence=metrics['top_prob'],
        log_prob=metrics['top_log_prob'],
        margin=metrics['margin'],
        target_log_prob=metrics['target_log_prob'],
        R_k=health.get('R_k', 0.0),
        R_q=health.get('R_q', 0.0),
        amp_phase_corr=health.get('amp_phase_corr', 0.0),
        head_redundancy=health.get('head_redundancy', 0.0),
        phase_drift_mean=health.get('phase_drift_mean', 0.0),
        phase_drift_std=health.get('phase_drift_std', 0.0),
    )


def run_minimal_pair_probe(
    model: nn.Module,
    tokenizer,
    probe: MinimalPairProbe,
    device: torch.device,
    mode: AblationMode = AblationMode.BASELINE,
    scramble_seed: int = 42,
    variant: str = 'A',
) -> ProbeResult:
    """
    Run one variant (A or B) of a minimal-pair probe.
    """
    if variant == 'A':
        text = probe.text_a
        answer = probe.answer_a
        targets = probe.target_tokens_a
    else:
        text = probe.text_b
        answer = probe.answer_b
        targets = probe.target_tokens_b

    # Construct prompt
    prompt = construct_qa_prompt(text, probe.question)

    # Get probabilities
    probs, log_probs, health = get_next_token_probs(
        model, tokenizer, prompt, device, mode, scramble_seed
    )

    # Compute answer metrics
    metrics = compute_answer_metrics(
        probs, log_probs, targets, probe.distractor_tokens, tokenizer
    )

    return ProbeResult(
        probe_id=f"{probe.id}_{variant}",
        category=probe.category.value,
        mode=mode.value,
        text=text,
        question=probe.question,
        expected_answer=answer,
        model_answer=metrics['top_token'],
        is_correct=metrics['is_correct'],
        confidence=metrics['top_prob'],
        log_prob=metrics['top_log_prob'],
        margin=metrics['margin'],
        target_log_prob=metrics['target_log_prob'],
        R_k=health.get('R_k', 0.0),
        R_q=health.get('R_q', 0.0),
        amp_phase_corr=health.get('amp_phase_corr', 0.0),
        head_redundancy=health.get('head_redundancy', 0.0),
        phase_drift_mean=health.get('phase_drift_mean', 0.0),
        phase_drift_std=health.get('phase_drift_std', 0.0),
    )


def run_probe_with_ablations(
    model: nn.Module,
    tokenizer,
    probe,
    device: torch.device,
    scramble_seed: int = 42,
) -> Dict[str, ProbeResult]:
    """
    Run a probe with all ablation modes.

    Returns dict mapping mode name to ProbeResult.
    """
    results = {}
    modes = [AblationMode.BASELINE, AblationMode.PHASE_SCRAMBLE, AblationMode.PHASE_FROZEN]

    for mode in modes:
        if isinstance(probe, MinimalPairProbe):
            # Run both variants for minimal pairs
            result_a = run_minimal_pair_probe(
                model, tokenizer, probe, device, mode, scramble_seed, 'A'
            )
            result_b = run_minimal_pair_probe(
                model, tokenizer, probe, device, mode, scramble_seed, 'B'
            )
            results[f"{mode.value}_A"] = result_a
            results[f"{mode.value}_B"] = result_b
        else:
            result = run_single_probe(
                model, tokenizer, probe, device, mode, scramble_seed
            )
            results[mode.value] = result

    return results


# =============================================================================
# ANALYSIS AND AGGREGATION
# =============================================================================

def compute_ablation_comparison(
    baseline_result: ProbeResult,
    scramble_result: ProbeResult,
    frozen_result: ProbeResult,
) -> AblationComparison:
    """
    Compare probe results across ablation modes.
    """
    delta_scramble = baseline_result.margin - scramble_result.margin
    delta_frozen = baseline_result.margin - frozen_result.margin

    # Phase is "sensitive" if either ablation hurts margin by > 0.3
    # or changes correctness
    phase_sensitive = (
        delta_scramble > 0.3 or
        delta_frozen > 0.3 or
        (baseline_result.is_correct and not scramble_result.is_correct) or
        (baseline_result.is_correct and not frozen_result.is_correct)
    )

    return AblationComparison(
        probe_id=baseline_result.probe_id,
        category=baseline_result.category,
        baseline_margin=baseline_result.margin,
        scramble_margin=scramble_result.margin,
        frozen_margin=frozen_result.margin,
        delta_scramble=delta_scramble,
        delta_frozen=delta_frozen,
        phase_sensitive=phase_sensitive,
        baseline_correct=baseline_result.is_correct,
        scramble_correct=scramble_result.is_correct,
        frozen_correct=frozen_result.is_correct,
    )


def detect_failure_signatures(
    comparisons: List[AblationComparison],
    all_results: List[ProbeResult],
) -> Dict[str, bool]:
    """
    Detect failure signatures indicating phase issues.

    Returns dict of failure flags:
    - phase_is_decorative: Delta ~ 0 everywhere
    - phase_is_brittle: Scramble breaks everything
    - amplitude_cheating: High amp-phase correlation
    """
    # F1: Phase is decorative (delta close to 0 for most probes)
    deltas = [c.delta_scramble for c in comparisons] + [c.delta_frozen for c in comparisons]
    mean_abs_delta = sum(abs(d) for d in deltas) / len(deltas) if deltas else 0
    phase_is_decorative = mean_abs_delta < 0.1

    # F2: Phase is brittle (scramble breaks most probes)
    scramble_break_count = sum(
        1 for c in comparisons
        if c.baseline_correct and not c.scramble_correct
    )
    phase_is_brittle = scramble_break_count > len(comparisons) * 0.7

    # F4: Amplitude cheating (high amp-phase correlation)
    baseline_results = [r for r in all_results if r.mode == 'baseline']
    mean_amp_corr = sum(r.amp_phase_corr for r in baseline_results) / len(baseline_results) if baseline_results else 0
    amplitude_cheating = abs(mean_amp_corr) > 0.6

    return {
        'phase_is_decorative': phase_is_decorative,
        'phase_is_brittle': phase_is_brittle,
        'amplitude_cheating': amplitude_cheating,
    }


def aggregate_results(
    all_results: List[ProbeResult],
    comparisons: List[AblationComparison],
    checkpoint_path: str,
) -> ProbeSuiteResults:
    """
    Aggregate all probe results into summary statistics.
    """
    # Split by mode
    baseline_results = [r for r in all_results if r.mode == 'baseline']
    scramble_results = [r for r in all_results if r.mode == 'scramble']
    frozen_results = [r for r in all_results if r.mode == 'frozen']

    # Accuracy
    def accuracy(results):
        if not results:
            return 0.0
        return sum(1 for r in results if r.is_correct) / len(results)

    baseline_acc = accuracy(baseline_results)
    scramble_acc = accuracy(scramble_results)
    frozen_acc = accuracy(frozen_results)

    # Phase sensitivity
    phase_sensitive_count = sum(1 for c in comparisons if c.phase_sensitive)
    phase_sensitive_pct = phase_sensitive_count / len(comparisons) if comparisons else 0

    # Mean deltas
    mean_delta_scramble = sum(c.delta_scramble for c in comparisons) / len(comparisons) if comparisons else 0
    mean_delta_frozen = sum(c.delta_frozen for c in comparisons) / len(comparisons) if comparisons else 0

    # Phase health averages (from baseline only)
    mean_R_k = sum(r.R_k for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_R_q = sum(r.R_q for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_amp_corr = sum(r.amp_phase_corr for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_head_red = sum(r.head_redundancy for r in baseline_results) / len(baseline_results) if baseline_results else 0

    # Failure signatures
    failures = detect_failure_signatures(comparisons, all_results)

    return ProbeSuiteResults(
        timestamp=datetime.now().isoformat(),
        checkpoint_path=checkpoint_path,
        total_probes=len(comparisons),
        baseline_accuracy=baseline_acc,
        scramble_accuracy=scramble_acc,
        frozen_accuracy=frozen_acc,
        phase_sensitive_count=phase_sensitive_count,
        phase_sensitive_pct=phase_sensitive_pct,
        mean_delta_scramble=mean_delta_scramble,
        mean_delta_frozen=mean_delta_frozen,
        mean_R_k=mean_R_k,
        mean_R_q=mean_R_q,
        mean_amp_phase_corr=mean_amp_corr,
        mean_head_redundancy=mean_head_red,
        phase_is_decorative=failures['phase_is_decorative'],
        phase_is_brittle=failures['phase_is_brittle'],
        amplitude_cheating=failures['amplitude_cheating'],
        probe_results=[asdict(r) for r in all_results],
        comparisons=[asdict(c) for c in comparisons],
    )


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def print_results_table(comparisons: List[AblationComparison], verbose: bool = False):
    """Print results as a formatted table."""
    print("\n" + "=" * 100)
    print("PROBE RESULTS")
    print("=" * 100)

    # Header
    header = f"{'Probe':<10} {'Mode':<10} {'Correct':<8} {'BL_Margin':>10} {'SC_Margin':>10} {'FR_Margin':>10} {'Delta_SC':>10} {'Phase-Sens':<12}"
    print(header)
    print("-" * 100)

    for comp in comparisons:
        correct_str = f"{'Y' if comp.baseline_correct else 'N'}/{('Y' if comp.scramble_correct else 'N')}/{('Y' if comp.frozen_correct else 'N')}"
        sens_str = "YES" if comp.phase_sensitive else "no"

        row = f"{comp.probe_id:<10} {'all':<10} {correct_str:<8} {comp.baseline_margin:>10.3f} {comp.scramble_margin:>10.3f} {comp.frozen_margin:>10.3f} {comp.delta_scramble:>10.3f} {sens_str:<12}"
        print(row)

    print("-" * 100)


def print_health_table(results: List[ProbeResult]):
    """Print phase health metrics table."""
    baseline_results = [r for r in results if r.mode == 'baseline']

    print("\n" + "=" * 80)
    print("PHASE HEALTH METRICS (Baseline Mode)")
    print("=" * 80)

    header = f"{'Probe':<10} {'R_k':>8} {'R_q':>8} {'AmpCorr':>10} {'HeadRed':>10} {'Drift':>10}"
    print(header)
    print("-" * 80)

    for r in baseline_results:
        row = f"{r.probe_id:<10} {r.R_k:>8.4f} {r.R_q:>8.4f} {r.amp_phase_corr:>10.4f} {r.head_redundancy:>10.4f} {r.phase_drift_mean:>10.4f}"
        print(row)

    print("-" * 80)


def print_summary(summary: ProbeSuiteResults):
    """Print summary statistics and interpretation."""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nCheckpoint: {summary.checkpoint_path}")
    print(f"Total probes: {summary.total_probes}")

    print(f"\n--- Accuracy ---")
    print(f"  Baseline:  {summary.baseline_accuracy*100:.1f}%")
    print(f"  Scramble:  {summary.scramble_accuracy*100:.1f}%")
    print(f"  Frozen:    {summary.frozen_accuracy*100:.1f}%")

    print(f"\n--- Phase Sensitivity ---")
    print(f"  Phase-sensitive probes: {summary.phase_sensitive_count}/{summary.total_probes} ({summary.phase_sensitive_pct*100:.1f}%)")
    print(f"  Mean delta (scramble): {summary.mean_delta_scramble:.4f}")
    print(f"  Mean delta (frozen):   {summary.mean_delta_frozen:.4f}")

    print(f"\n--- Phase Health (averaged) ---")
    print(f"  R_k (collapse):        {summary.mean_R_k:.4f} {'(healthy)' if summary.mean_R_k < 0.3 else '(WARNING)' if summary.mean_R_k < 0.5 else '(COLLAPSED)'}")
    print(f"  R_q (collapse):        {summary.mean_R_q:.4f} {'(healthy)' if summary.mean_R_q < 0.3 else '(WARNING)' if summary.mean_R_q < 0.5 else '(COLLAPSED)'}")
    print(f"  Amp-Phase correlation: {summary.mean_amp_phase_corr:.4f} {'(OK)' if abs(summary.mean_amp_phase_corr) < 0.3 else '(HIGH)'}")
    print(f"  Head redundancy:       {summary.mean_head_redundancy:.4f} {'(diverse)' if summary.mean_head_redundancy < 0.5 else '(redundant)'}")

    print(f"\n--- Failure Signatures ---")
    if summary.phase_is_decorative:
        print("  [F1] PHASE IS DECORATIVE: Ablations have minimal effect. Phase may not be contributing.")
    if summary.phase_is_brittle:
        print("  [F2] PHASE IS BRITTLE: Scramble breaks most probes. Phase is over-coupled.")
    if summary.amplitude_cheating:
        print("  [F4] AMPLITUDE CHEATING: High amp-phase correlation. Amplitude may be compensating.")
    if not (summary.phase_is_decorative or summary.phase_is_brittle or summary.amplitude_cheating):
        print("  No major failure signatures detected.")

    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    if summary.phase_sensitive_pct > 0.5 and not summary.phase_is_decorative:
        print("\nPhase appears to be LEARNING RELATIONAL SELECTIVITY:")
        print("  - More than 50% of probes are phase-sensitive")
        print("  - Ablations cause measurable degradation")
        print("  - This suggests phase is encoding binding/persistence information")
    elif summary.phase_is_decorative:
        print("\nPhase appears DECORATIVE (not contributing):")
        print("  - Ablations have minimal effect on predictions")
        print("  - Model may be relying on other pathways")
        print("  - Consider: Is phase loss too low? Is amplitude dominant?")
    elif summary.phase_is_brittle:
        print("\nPhase is OVER-COUPLED (too dominant):")
        print("  - Scrambling breaks everything")
        print("  - Model may be over-relying on phase without robustness")
        print("  - Consider: Phase diversity may be too high?")
    else:
        print("\nMixed results - phase has partial effect:")
        print(f"  - {summary.phase_sensitive_pct*100:.0f}% probes show phase sensitivity")
        print("  - Further investigation recommended")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="PhaseAttention Behavioral Probe Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python phase_probe_runner.py --checkpoint checkpoints/best.pt
    python phase_probe_runner.py --checkpoint checkpoints/best.pt --verbose
    python phase_probe_runner.py --checkpoint checkpoints/best.pt --probe RB1
    python phase_probe_runner.py --checkpoint checkpoints/best.pt --output results.json
        """
    )
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to model checkpoint")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device to run on (cuda/cpu)")
    parser.add_argument("--probe", type=str, default=None,
                        help="Run only specific probe ID (e.g., RB1)")
    parser.add_argument("--category", type=str, default=None,
                        choices=['role_binding', 'long_range', 'interference', 'negation_polarity'],
                        help="Run only probes from specific category")
    parser.add_argument("--verbose", action="store_true",
                        help="Print detailed per-probe output")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    parser.add_argument("--scramble_seed", type=int, default=42,
                        help="Random seed for phase scrambling (for reproducibility)")

    args = parser.parse_args()

    # Check device
    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU")
        args.device = "cpu"
    device = torch.device(args.device)

    # Load model
    model, tokenizer, config = load_model_and_tokenizer(args.checkpoint, device)

    # Select probes to run
    probes_to_run = []

    if args.probe:
        # Run specific probe
        probe = get_probe_by_id(args.probe)
        if probe is None:
            print(f"Error: Probe '{args.probe}' not found. Available: {get_all_probe_ids()}")
            sys.exit(1)
        probes_to_run = [probe]
    elif args.category:
        # Run probes from category
        from probe_cases import PROBES_BY_CATEGORY
        cat = ProbeCategory(args.category)
        probes_to_run = PROBES_BY_CATEGORY.get(cat, [])
    else:
        # Run all probes
        probes_to_run = MINIMAL_PAIR_PROBES + SINGLE_PROBES

    print(f"\nRunning {len(probes_to_run)} probes...")

    # Run probes
    all_results = []
    comparisons = []

    for i, probe in enumerate(probes_to_run):
        print(f"\n[{i+1}/{len(probes_to_run)}] Running probe {probe.id}...")

        probe_results = run_probe_with_ablations(
            model, tokenizer, probe, device, args.scramble_seed
        )

        # Collect results
        for key, result in probe_results.items():
            all_results.append(result)

        # Create comparison
        if isinstance(probe, MinimalPairProbe):
            # Compare A variant across modes
            baseline_a = probe_results.get('baseline_A')
            scramble_a = probe_results.get('scramble_A')
            frozen_a = probe_results.get('frozen_A')

            if baseline_a and scramble_a and frozen_a:
                comp_a = compute_ablation_comparison(baseline_a, scramble_a, frozen_a)
                comparisons.append(comp_a)

            # Compare B variant across modes
            baseline_b = probe_results.get('baseline_B')
            scramble_b = probe_results.get('scramble_B')
            frozen_b = probe_results.get('frozen_B')

            if baseline_b and scramble_b and frozen_b:
                comp_b = compute_ablation_comparison(baseline_b, scramble_b, frozen_b)
                comparisons.append(comp_b)
        else:
            # Single probe
            baseline = probe_results.get('baseline')
            scramble = probe_results.get('scramble')
            frozen = probe_results.get('frozen')

            if baseline and scramble and frozen:
                comp = compute_ablation_comparison(baseline, scramble, frozen)
                comparisons.append(comp)

        if args.verbose and comparisons:
            last_comp = comparisons[-1]
            print(f"    Baseline correct: {last_comp.baseline_correct}")
            print(f"    Scramble correct: {last_comp.scramble_correct}")
            print(f"    Delta margin: {last_comp.delta_scramble:.3f}")

    # Aggregate and print results
    summary = aggregate_results(all_results, comparisons, args.checkpoint)

    print_results_table(comparisons, args.verbose)
    print_health_table(all_results)
    print_summary(summary)

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
