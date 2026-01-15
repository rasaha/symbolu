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
    # Additional metrics
    head_entropy: float               # Head contribution entropy (diversity)


@dataclass
class AblationComparison:
    """Comparison of a probe across different ablation modes."""
    probe_id: str
    category: str
    baseline_margin: float
    scramble_margin: float
    frozen_margin: float
    phase_off_margin: float           # Phase bypassed (uniform attention)
    delta_scramble: float             # baseline - scramble
    delta_frozen: float               # baseline - frozen
    delta_phase_off: float            # baseline - phase_off
    phase_sensitive: bool             # True if ablation hurts performance
    baseline_correct: bool
    scramble_correct: bool
    frozen_correct: bool
    phase_off_correct: bool
    # Additional diagnostic
    baseline_confidence: float
    scramble_confidence: float
    frozen_confidence: float
    phase_off_confidence: float


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
    phase_off_accuracy: float         # Phase bypassed accuracy
    # Phase sensitivity metrics
    phase_sensitive_count: int        # Probes where ablation hurts
    phase_sensitive_pct: float
    mean_delta_scramble: float        # Average margin drop from scramble
    mean_delta_frozen: float          # Average margin drop from frozen
    mean_delta_phase_off: float       # Average margin drop from phase_off
    phase_contribution_index: float   # avg(baseline_margin - scramble_margin)
    # Phase health (averaged over all probes)
    mean_R_k: float
    mean_R_q: float
    mean_amp_phase_corr: float
    mean_head_redundancy: float
    mean_head_entropy: float          # Head contribution entropy
    # Failure signatures
    phase_is_decorative: bool         # Delta ~ 0 everywhere
    phase_is_brittle: bool            # Scramble breaks everything
    amplitude_cheating: bool          # High amp-phase correlation
    collapse_detected: bool           # R_k > 0.5 (phase collapsed)
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
# PHASE HEALTH METRICS COMPUTATION
# =============================================================================

def compute_head_entropy(model: nn.Module) -> float:
    """
    Compute head contribution entropy from captured phase data.

    Higher entropy = more diverse head contributions (healthy)
    Lower entropy = heads contributing similar information (redundant)

    This measures the diversity of head-wise attention patterns.
    """
    try:
        from symbolu.phase_transformer import _collect_health_captures

        captures = _collect_health_captures(model)
        if not captures:
            return 0.0

        entropies = []
        for capture in captures:
            phi_k = capture.get('phi_k')
            if phi_k is None:
                continue

            # Compute per-head mean phasor: z̄_h = mean_{b,n,d} exp(i * phi_k)
            # Shape: [B, N, H, D_h] -> [H]
            z_real = torch.cos(phi_k).mean(dim=(0, 1, 3))  # [H]
            z_imag = torch.sin(phi_k).mean(dim=(0, 1, 3))  # [H]

            # Magnitude per head represents how "aligned" each head is
            z_mag = torch.sqrt(z_real ** 2 + z_imag ** 2 + 1e-8)  # [H]

            # Normalize to get distribution
            z_mag_norm = z_mag / (z_mag.sum() + 1e-8)

            # Shannon entropy: -sum(p * log(p))
            # Higher = more uniform contribution across heads
            entropy = -torch.sum(z_mag_norm * torch.log(z_mag_norm + 1e-8))
            entropies.append(entropy.item())

        return sum(entropies) / len(entropies) if entropies else 0.0

    except Exception:
        return 0.0


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
        health: Phase health metrics (including head_entropy)
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

    # Add head entropy to health metrics
    health = result.phase_health.copy() if result.phase_health else {}
    if 'head_entropy' not in health:
        health['head_entropy'] = compute_head_entropy(model)

    return probs, log_probs, health


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
        head_entropy=health.get('head_entropy', 0.0),
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
        head_entropy=health.get('head_entropy', 0.0),
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
    Modes: BASELINE, PHASE_SCRAMBLE, PHASE_FROZEN, PHASE_OFF
    """
    results = {}
    modes = [
        AblationMode.BASELINE,
        AblationMode.PHASE_SCRAMBLE,
        AblationMode.PHASE_FROZEN,
        AblationMode.PHASE_OFF,
    ]

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
    phase_off_result: Optional[ProbeResult] = None,
) -> AblationComparison:
    """
    Compare probe results across ablation modes.

    Args:
        baseline_result: Normal inference
        scramble_result: Phases randomly permuted
        frozen_result: Phases set to constant
        phase_off_result: Phases set to uniform (bypass phase selectivity)
    """
    delta_scramble = baseline_result.margin - scramble_result.margin
    delta_frozen = baseline_result.margin - frozen_result.margin

    # Handle phase_off (if provided)
    if phase_off_result is not None:
        delta_phase_off = baseline_result.margin - phase_off_result.margin
        phase_off_margin = phase_off_result.margin
        phase_off_correct = phase_off_result.is_correct
        phase_off_confidence = phase_off_result.confidence
    else:
        delta_phase_off = 0.0
        phase_off_margin = 0.0
        phase_off_correct = False
        phase_off_confidence = 0.0

    # Phase is "sensitive" if ANY ablation hurts margin by > 0.3
    # or changes correctness from correct to incorrect
    phase_sensitive = (
        delta_scramble > 0.3 or
        delta_frozen > 0.3 or
        delta_phase_off > 0.3 or
        (baseline_result.is_correct and not scramble_result.is_correct) or
        (baseline_result.is_correct and not frozen_result.is_correct) or
        (phase_off_result is not None and baseline_result.is_correct and not phase_off_correct)
    )

    return AblationComparison(
        probe_id=baseline_result.probe_id,
        category=baseline_result.category,
        baseline_margin=baseline_result.margin,
        scramble_margin=scramble_result.margin,
        frozen_margin=frozen_result.margin,
        phase_off_margin=phase_off_margin,
        delta_scramble=delta_scramble,
        delta_frozen=delta_frozen,
        delta_phase_off=delta_phase_off,
        phase_sensitive=phase_sensitive,
        baseline_correct=baseline_result.is_correct,
        scramble_correct=scramble_result.is_correct,
        frozen_correct=frozen_result.is_correct,
        phase_off_correct=phase_off_correct,
        baseline_confidence=baseline_result.confidence,
        scramble_confidence=scramble_result.confidence,
        frozen_confidence=frozen_result.confidence,
        phase_off_confidence=phase_off_confidence,
    )


def detect_failure_signatures(
    comparisons: List[AblationComparison],
    all_results: List[ProbeResult],
) -> Dict[str, bool]:
    """
    Detect failure signatures indicating phase issues.

    Returns dict of failure flags:
    - phase_is_decorative: Delta ~ 0 everywhere (phase not contributing)
    - phase_is_brittle: Scramble breaks everything (phase over-coupled)
    - amplitude_cheating: High amp-phase correlation (amplitude compensating)
    - collapse_detected: R_k > 0.5 (phase diversity collapsed)
    """
    baseline_results = [r for r in all_results if r.mode == 'baseline']

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

    # F3: Collapse detected (R_k > 0.5 means phases clustered)
    mean_R_k = sum(r.R_k for r in baseline_results) / len(baseline_results) if baseline_results else 0
    collapse_detected = mean_R_k > 0.5

    # F4: Amplitude cheating (high amp-phase correlation)
    mean_amp_corr = sum(r.amp_phase_corr for r in baseline_results) / len(baseline_results) if baseline_results else 0
    amplitude_cheating = abs(mean_amp_corr) > 0.6

    return {
        'phase_is_decorative': phase_is_decorative,
        'phase_is_brittle': phase_is_brittle,
        'amplitude_cheating': amplitude_cheating,
        'collapse_detected': collapse_detected,
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
    phase_off_results = [r for r in all_results if r.mode == 'phase_off']

    # Accuracy
    def accuracy(results):
        if not results:
            return 0.0
        return sum(1 for r in results if r.is_correct) / len(results)

    baseline_acc = accuracy(baseline_results)
    scramble_acc = accuracy(scramble_results)
    frozen_acc = accuracy(frozen_results)
    phase_off_acc = accuracy(phase_off_results)

    # Phase sensitivity
    phase_sensitive_count = sum(1 for c in comparisons if c.phase_sensitive)
    phase_sensitive_pct = phase_sensitive_count / len(comparisons) if comparisons else 0

    # Mean deltas
    mean_delta_scramble = sum(c.delta_scramble for c in comparisons) / len(comparisons) if comparisons else 0
    mean_delta_frozen = sum(c.delta_frozen for c in comparisons) / len(comparisons) if comparisons else 0
    mean_delta_phase_off = sum(c.delta_phase_off for c in comparisons) / len(comparisons) if comparisons else 0

    # Phase contribution index = average margin improvement from phase
    phase_contribution_index = mean_delta_scramble  # Higher = phase helping more

    # Phase health averages (from baseline only)
    mean_R_k = sum(r.R_k for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_R_q = sum(r.R_q for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_amp_corr = sum(r.amp_phase_corr for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_head_red = sum(r.head_redundancy for r in baseline_results) / len(baseline_results) if baseline_results else 0
    mean_head_ent = sum(r.head_entropy for r in baseline_results) / len(baseline_results) if baseline_results else 0

    # Failure signatures
    failures = detect_failure_signatures(comparisons, all_results)

    return ProbeSuiteResults(
        timestamp=datetime.now().isoformat(),
        checkpoint_path=checkpoint_path,
        total_probes=len(comparisons),
        baseline_accuracy=baseline_acc,
        scramble_accuracy=scramble_acc,
        frozen_accuracy=frozen_acc,
        phase_off_accuracy=phase_off_acc,
        phase_sensitive_count=phase_sensitive_count,
        phase_sensitive_pct=phase_sensitive_pct,
        mean_delta_scramble=mean_delta_scramble,
        mean_delta_frozen=mean_delta_frozen,
        mean_delta_phase_off=mean_delta_phase_off,
        phase_contribution_index=phase_contribution_index,
        mean_R_k=mean_R_k,
        mean_R_q=mean_R_q,
        mean_amp_phase_corr=mean_amp_corr,
        mean_head_redundancy=mean_head_red,
        mean_head_entropy=mean_head_ent,
        phase_is_decorative=failures['phase_is_decorative'],
        phase_is_brittle=failures['phase_is_brittle'],
        amplitude_cheating=failures['amplitude_cheating'],
        collapse_detected=failures['collapse_detected'],
        probe_results=[asdict(r) for r in all_results],
        comparisons=[asdict(c) for c in comparisons],
    )


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================

def print_results_table(comparisons: List[AblationComparison], all_results: List[ProbeResult], verbose: bool = False):
    """
    Print results as a formatted table.

    Format: Probe | Mode | Answer | Correct | ΔConfidence | R_k | HeadEntropy
    """
    print("\n" + "=" * 120)
    print("PROBE RESULTS BY ABLATION MODE")
    print("=" * 120)

    # Header matching user's requested format
    header = f"{'Probe':<12} {'Mode':<10} {'Answer':<12} {'Correct':<8} {'Margin':>8} {'ΔConf':>8} {'R_k':>8} {'HeadEnt':>8} {'Phase-Sens':<10}"
    print(header)
    print("-" * 120)

    # Group results by probe
    probes_seen = set()
    for comp in comparisons:
        probe_id_base = comp.probe_id.rsplit('_', 1)[0] if '_' in comp.probe_id else comp.probe_id
        if probe_id_base in probes_seen:
            continue
        probes_seen.add(probe_id_base)

        # Find all results for this probe
        probe_results = [r for r in all_results if r.probe_id.startswith(comp.probe_id.rsplit('_', 1)[0])]
        baseline_result = next((r for r in probe_results if r.mode == 'baseline'), None)

        if not baseline_result:
            continue

        # Print comparison row
        correct_str = f"{'Y' if comp.baseline_correct else 'N'}/{('Y' if comp.scramble_correct else 'N')}/{('Y' if comp.frozen_correct else 'N')}/{('Y' if comp.phase_off_correct else 'N')}"
        delta_conf = comp.baseline_confidence - comp.scramble_confidence
        sens_str = "YES" if comp.phase_sensitive else "no"

        row = f"{comp.probe_id:<12} {'compare':<10} {baseline_result.model_answer[:10]:<12} {correct_str:<8} {comp.baseline_margin:>8.3f} {delta_conf:>+8.3f} {baseline_result.R_k:>8.4f} {baseline_result.head_entropy:>8.4f} {sens_str:<10}"
        print(row)

        if verbose:
            # Print individual mode rows
            for mode_name in ['baseline', 'scramble', 'frozen', 'phase_off']:
                mode_result = next((r for r in probe_results if r.mode == mode_name), None)
                if mode_result:
                    correct_mark = 'Y' if mode_result.is_correct else 'N'
                    delta_from_baseline = mode_result.confidence - baseline_result.confidence if mode_name != 'baseline' else 0.0
                    row = f"  {'└':<10} {mode_name:<10} {mode_result.model_answer[:10]:<12} {correct_mark:<8} {mode_result.margin:>8.3f} {delta_from_baseline:>+8.3f} {mode_result.R_k:>8.4f} {mode_result.head_entropy:>8.4f}"
                    print(row)

    print("-" * 120)

    # Print compact summary table
    print("\n" + "=" * 100)
    print("ABLATION COMPARISON SUMMARY")
    print("=" * 100)
    header2 = f"{'Probe':<12} {'BL':>8} {'SC':>8} {'FR':>8} {'OFF':>8} │ {'Δ_SC':>8} {'Δ_FR':>8} {'Δ_OFF':>8} {'Sens':<6}"
    print(header2)
    print("-" * 100)

    for comp in comparisons:
        sens = "YES" if comp.phase_sensitive else "no"
        row = f"{comp.probe_id:<12} {comp.baseline_margin:>8.3f} {comp.scramble_margin:>8.3f} {comp.frozen_margin:>8.3f} {comp.phase_off_margin:>8.3f} │ {comp.delta_scramble:>+8.3f} {comp.delta_frozen:>+8.3f} {comp.delta_phase_off:>+8.3f} {sens:<6}"
        print(row)

    print("-" * 100)


def print_health_table(results: List[ProbeResult]):
    """Print phase health metrics table."""
    baseline_results = [r for r in results if r.mode == 'baseline']

    print("\n" + "=" * 100)
    print("PHASE HEALTH METRICS (Baseline Mode)")
    print("=" * 100)

    header = f"{'Probe':<12} {'R_k':>8} {'R_q':>8} {'AmpCorr':>10} {'HeadRed':>10} {'HeadEnt':>10} {'Drift':>10}"
    print(header)
    print("-" * 100)

    for r in baseline_results:
        row = f"{r.probe_id:<12} {r.R_k:>8.4f} {r.R_q:>8.4f} {r.amp_phase_corr:>10.4f} {r.head_redundancy:>10.4f} {r.head_entropy:>10.4f} {r.phase_drift_mean:>10.4f}"
        print(row)

    print("-" * 100)


def print_summary(summary: ProbeSuiteResults):
    """Print summary statistics and interpretation."""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\nCheckpoint: {summary.checkpoint_path}")
    print(f"Total probes: {summary.total_probes}")

    print(f"\n--- Accuracy by Mode ---")
    print(f"  Baseline:   {summary.baseline_accuracy*100:>6.1f}%")
    print(f"  Scramble:   {summary.scramble_accuracy*100:>6.1f}%  (Δ = {(summary.baseline_accuracy - summary.scramble_accuracy)*100:+.1f}%)")
    print(f"  Frozen:     {summary.frozen_accuracy*100:>6.1f}%  (Δ = {(summary.baseline_accuracy - summary.frozen_accuracy)*100:+.1f}%)")
    print(f"  Phase-Off:  {summary.phase_off_accuracy*100:>6.1f}%  (Δ = {(summary.baseline_accuracy - summary.phase_off_accuracy)*100:+.1f}%)")

    print(f"\n--- Phase Sensitivity ---")
    print(f"  Phase-sensitive probes: {summary.phase_sensitive_count}/{summary.total_probes} ({summary.phase_sensitive_pct*100:.1f}%)")
    print(f"  Phase contribution index: {summary.phase_contribution_index:.4f}")
    print(f"  Mean delta (scramble):    {summary.mean_delta_scramble:+.4f}")
    print(f"  Mean delta (frozen):      {summary.mean_delta_frozen:+.4f}")
    print(f"  Mean delta (phase-off):   {summary.mean_delta_phase_off:+.4f}")

    print(f"\n--- Phase Health (averaged) ---")
    print(f"  R_k (collapse):        {summary.mean_R_k:.4f} {'(healthy)' if summary.mean_R_k < 0.3 else '(WARNING)' if summary.mean_R_k < 0.5 else '(COLLAPSED)'}")
    print(f"  R_q (collapse):        {summary.mean_R_q:.4f} {'(healthy)' if summary.mean_R_q < 0.3 else '(WARNING)' if summary.mean_R_q < 0.5 else '(COLLAPSED)'}")
    print(f"  Amp-Phase correlation: {summary.mean_amp_phase_corr:.4f} {'(OK)' if abs(summary.mean_amp_phase_corr) < 0.3 else '(HIGH)'}")
    print(f"  Head redundancy:       {summary.mean_head_redundancy:.4f} {'(diverse)' if summary.mean_head_redundancy < 0.5 else '(redundant)'}")
    print(f"  Head entropy:          {summary.mean_head_entropy:.4f}")

    print(f"\n--- Failure Signatures ---")
    any_failure = False
    if summary.phase_is_decorative:
        print("  [F1] PHASE IS DECORATIVE: Ablations have minimal effect. Phase may not be contributing.")
        any_failure = True
    if summary.phase_is_brittle:
        print("  [F2] PHASE IS BRITTLE: Scramble breaks most probes. Phase is over-coupled.")
        any_failure = True
    if summary.collapse_detected:
        print("  [F3] COLLAPSE DETECTED: R_k > 0.5. Phase diversity has collapsed.")
        any_failure = True
    if summary.amplitude_cheating:
        print("  [F4] AMPLITUDE CHEATING: High amp-phase correlation. Amplitude may be compensating.")
        any_failure = True
    if not any_failure:
        print("  No major failure signatures detected.")

    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)

    # Detailed scientific interpretation
    if summary.phase_sensitive_pct > 0.5 and not summary.phase_is_decorative:
        print("\n[POSITIVE] Phase appears to be LEARNING RELATIONAL SELECTIVITY:")
        print("  - More than 50% of probes are phase-sensitive")
        print("  - Ablations cause measurable degradation")
        print("  - This suggests phase is encoding binding/persistence information")
        if summary.phase_contribution_index > 0.3:
            print(f"  - Phase contribution index ({summary.phase_contribution_index:.3f}) is substantial")
    elif summary.phase_is_decorative:
        print("\n[NEGATIVE] Phase appears DECORATIVE (not contributing):")
        print("  - Ablations have minimal effect on predictions")
        print("  - Model may be relying on other pathways (amplitude, standard attention)")
        print("  - CANNOT demonstrate phase is learning relational selectivity")
        print("  - Consider: Is phase loss too low? Is amplitude dominant?")
    elif summary.phase_is_brittle:
        print("\n[CONCERNING] Phase is OVER-COUPLED (too dominant):")
        print("  - Scrambling breaks everything")
        print("  - Model may be over-relying on phase without robustness")
        print("  - Consider: Phase diversity loss may be too high")
    elif summary.collapse_detected:
        print("\n[WARNING] Phase COLLAPSE detected:")
        print("  - R_k > 0.5 indicates phases have clustered")
        print("  - Phase diversity is insufficient for selective binding")
        print("  - May need more training or diversity regularization")
    else:
        print("\n[MIXED] Partial phase contribution detected:")
        print(f"  - {summary.phase_sensitive_pct*100:.0f}% probes show phase sensitivity")
        print(f"  - Phase contribution index: {summary.phase_contribution_index:.4f}")
        if summary.phase_contribution_index < 0.1:
            print("  - Contribution is minimal - phase may not be fully utilized")
        else:
            print("  - Further investigation recommended")

    # Scientific verdict
    print("\n" + "-" * 40)
    print("SCIENTIFIC VERDICT")
    print("-" * 40)

    can_demonstrate = (
        summary.phase_sensitive_pct >= 0.5 and
        not summary.phase_is_decorative and
        summary.phase_contribution_index > 0.2
    )

    if can_demonstrate:
        print("\nCAN demonstrate that PhaseAttention is learning relational selectivity.")
        print("Evidence:")
        print(f"  - Phase-sensitive probes: {summary.phase_sensitive_pct*100:.0f}%")
        print(f"  - Phase contribution: {summary.phase_contribution_index:.4f}")
        print(f"  - Baseline outperforms ablations by {(summary.baseline_accuracy - summary.scramble_accuracy)*100:.1f}%")
    else:
        print("\nCANNOT conclusively demonstrate that PhaseAttention is learning")
        print("relational selectivity with this checkpoint.")
        print("Reasons:")
        if summary.phase_is_decorative:
            print("  - Ablations have minimal effect (decorative)")
        if summary.phase_sensitive_pct < 0.5:
            print(f"  - Only {summary.phase_sensitive_pct*100:.0f}% probes are phase-sensitive (<50%)")
        if summary.phase_contribution_index <= 0.2:
            print(f"  - Phase contribution index ({summary.phase_contribution_index:.4f}) is too low")
        if summary.collapse_detected:
            print("  - Phase diversity has collapsed")


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
                        choices=['role_binding', 'long_range', 'interference', 'negation_polarity', 'amplitude_conflict'],
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
            phase_off_a = probe_results.get('phase_off_A')

            if baseline_a and scramble_a and frozen_a:
                comp_a = compute_ablation_comparison(baseline_a, scramble_a, frozen_a, phase_off_a)
                comparisons.append(comp_a)

            # Compare B variant across modes
            baseline_b = probe_results.get('baseline_B')
            scramble_b = probe_results.get('scramble_B')
            frozen_b = probe_results.get('frozen_B')
            phase_off_b = probe_results.get('phase_off_B')

            if baseline_b and scramble_b and frozen_b:
                comp_b = compute_ablation_comparison(baseline_b, scramble_b, frozen_b, phase_off_b)
                comparisons.append(comp_b)
        else:
            # Single probe
            baseline = probe_results.get('baseline')
            scramble = probe_results.get('scramble')
            frozen = probe_results.get('frozen')
            phase_off = probe_results.get('phase_off')

            if baseline and scramble and frozen:
                comp = compute_ablation_comparison(baseline, scramble, frozen, phase_off)
                comparisons.append(comp)

        if args.verbose and comparisons:
            last_comp = comparisons[-1]
            print(f"    Baseline correct: {last_comp.baseline_correct}")
            print(f"    Scramble correct: {last_comp.scramble_correct}")
            print(f"    Delta margin: {last_comp.delta_scramble:.3f}")

    # Aggregate and print results
    summary = aggregate_results(all_results, comparisons, args.checkpoint)

    print_results_table(comparisons, all_results, args.verbose)
    print_health_table(all_results)
    print_summary(summary)

    # Save to file if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(asdict(summary), f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
