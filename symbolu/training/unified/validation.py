"""
Validation utilities for testing Phase Attention and model quality.

Includes Long-Range Arena (LRA) validation for memory testing and
phase rotation tests for verifying relational structure encoding.

Extracted from train_unified_llm.py
"""

import math
from typing import Optional, Dict, List, Tuple, Any, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader


# =============================================================================
# LRA VALIDATOR: Long-Range Retrieval Testing
# =============================================================================

class LRAValidator:
    """
    Long-Range Arena Validator for Phase Attention Memory.

    Tests the model's ability to retrieve information over long distances,
    validating that Phase Oscillator memory works without decay.

    Tests:
    1. Needle-in-Haystack: Hide a key-value pair early, recall at end
    2. Distance Decay: Measure accuracy vs retrieval distance
    3. Multi-Needle: Multiple key-value pairs at different positions

    Patent Integration:
    - [U1] PhaseCoherenceMatrix: High coherence should correlate with good retrieval
    - [S5] Entropy: Low entropy during retrieval = confident recall
    - [B1] Consistency: Consistent forward/backward alignment aids retrieval

    Usage:
        validator = LRAValidator(model, tokenizer)
        results = validator.run_validation(step=1000)
        print(validator.format_results(results))
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: Optional[object] = None,
        device: torch.device = None,
        # Test configuration
        haystack_lengths: List[int] = None,  # Sequence lengths to test
        needle_positions: List[float] = None,  # Relative positions (0.0-1.0)
        num_samples: int = 50,  # Samples per test
        vocab_size: int = 50257,  # Tokenizer vocab size
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        # Test configurations
        self.haystack_lengths = haystack_lengths or [256, 512, 1024, 2048]
        self.needle_positions = needle_positions or [0.05, 0.1, 0.25, 0.5]  # 5%, 10%, 25%, 50%
        self.num_samples = num_samples
        self.vocab_size = vocab_size

        # Results history
        self.results_history = []

        # Special tokens for needle test
        self.key_token = 1      # Token ID for "KEY" marker
        self.query_token = 2    # Token ID for "QUERY" marker

    @torch.no_grad()
    def generate_needle_batch(
        self,
        batch_size: int,
        seq_len: int,
        needle_pos: int,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Generate a batch of needle-in-haystack sequences.

        Pattern:
            [noise...] [KEY] [VALUE] [noise...] [QUERY] [?]
                                                         ↑
                                                 Target: VALUE

        Returns:
            (sequences, targets, needle_positions)
        """
        # Create noise (haystack) - use tokens 10-vocab_size to avoid special tokens
        sequences = torch.randint(10, min(self.vocab_size, 1000), (batch_size, seq_len))

        # Generate random values for each sequence (tokens 10-99)
        values = torch.randint(10, 100, (batch_size,))
        targets = values.clone()

        # Insert needle at specified position
        # [KEY=1] [VALUE=random]
        sequences[:, needle_pos] = self.key_token
        sequences[:, needle_pos + 1] = values

        # Insert query at end - model must predict the value
        # [QUERY=2] [?]
        sequences[:, -2] = self.query_token
        sequences[:, -1] = values  # This is what we want to predict

        return sequences.to(self.device), targets.to(self.device), torch.tensor([needle_pos] * batch_size)

    @torch.no_grad()
    def test_needle_retrieval(
        self,
        seq_len: int,
        needle_pos_ratio: float,
    ) -> Dict[str, float]:
        """
        Test needle retrieval at a specific sequence length and position.

        Args:
            seq_len: Length of the haystack sequence
            needle_pos_ratio: Relative position of needle (0.0-1.0)

        Returns:
            Dict with accuracy, entropy, and confidence metrics
        """
        self.model.eval()

        needle_pos = int(seq_len * needle_pos_ratio)
        needle_pos = max(5, min(needle_pos, seq_len - 10))  # Safety bounds

        # Distance from needle to query
        retrieval_distance = seq_len - needle_pos - 3

        correct = 0
        total = 0
        entropies = []
        confidences = []

        # Run in batches
        batch_size = min(16, self.num_samples)
        num_batches = (self.num_samples + batch_size - 1) // batch_size

        for _ in range(num_batches):
            actual_batch = min(batch_size, self.num_samples - total)
            if actual_batch <= 0:
                break

            sequences, targets, _ = self.generate_needle_batch(
                actual_batch, seq_len, needle_pos
            )

            # Forward pass - get logits for the last position
            try:
                outputs = self.model(sequences[:, :-1])  # Input without last token
                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                else:
                    logits = outputs

                # Get predictions for the last position
                last_logits = logits[:, -1, :]  # [B, Vocab]

                # Compute predictions
                predictions = last_logits.argmax(dim=-1)

                # Compute accuracy
                correct += (predictions == targets).sum().item()
                total += actual_batch

                # Compute entropy of predictions
                probs = F.softmax(last_logits, dim=-1)
                entropy = -torch.sum(probs * torch.log(probs + 1e-9), dim=-1)
                max_entropy = math.log(last_logits.shape[-1])
                normalized_entropy = (entropy / max_entropy).mean().item()
                entropies.append(normalized_entropy)

                # Compute confidence (probability of correct token)
                target_probs = probs.gather(-1, targets.unsqueeze(-1)).squeeze(-1)
                confidences.append(target_probs.mean().item())

            except Exception as e:
                print(f"    Warning: LRA test failed for seq_len={seq_len}: {e}")
                break

        accuracy = correct / total if total > 0 else 0.0
        avg_entropy = sum(entropies) / len(entropies) if entropies else 1.0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "seq_len": seq_len,
            "needle_pos": needle_pos,
            "needle_pos_ratio": needle_pos_ratio,
            "retrieval_distance": retrieval_distance,
            "accuracy": accuracy,
            "entropy": avg_entropy,
            "confidence": avg_confidence,
            "samples": total,
        }

    @torch.no_grad()
    def run_validation(self, step: int = 0) -> Dict[str, any]:
        """
        Run full LRA validation suite.

        Returns comprehensive results including:
        - Per-length accuracy
        - Per-position accuracy
        - Distance decay curve
        - Overall retrieval score
        """
        self.model.eval()

        results = {
            "step": step,
            "tests": [],
            "by_length": {},
            "by_position": {},
            "distance_decay": [],
        }

        print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
        print(f"  ║  🔍 LRA VALIDATION (Step {step})                              ║")
        print(f"  ╠══════════════════════════════════════════════════════════════╣")

        # Run tests for each length and position combination
        for seq_len in self.haystack_lengths:
            if seq_len > 2048:  # Skip if seq_len exceeds typical model limits
                continue

            results["by_length"][seq_len] = []

            for pos_ratio in self.needle_positions:
                test_result = self.test_needle_retrieval(seq_len, pos_ratio)
                results["tests"].append(test_result)
                results["by_length"][seq_len].append(test_result)

                # Track by position
                pos_key = f"{pos_ratio:.0%}"
                if pos_key not in results["by_position"]:
                    results["by_position"][pos_key] = []
                results["by_position"][pos_key].append(test_result)

                # Track distance decay
                results["distance_decay"].append({
                    "distance": test_result["retrieval_distance"],
                    "accuracy": test_result["accuracy"],
                    "entropy": test_result["entropy"],
                })

                # Log result
                acc_icon = "✅" if test_result["accuracy"] > 0.8 else "⚠️" if test_result["accuracy"] > 0.5 else "❌"
                print(f"  ║  Len:{seq_len:>4} Pos:{pos_ratio:>4.0%} Dist:{test_result['retrieval_distance']:>4} │ "
                      f"Acc:{test_result['accuracy']:.1%} Ent:{test_result['entropy']:.2f} {acc_icon}  ║")

        # Compute summary statistics
        all_accuracies = [t["accuracy"] for t in results["tests"]]
        all_entropies = [t["entropy"] for t in results["tests"]]

        results["summary"] = {
            "mean_accuracy": sum(all_accuracies) / len(all_accuracies) if all_accuracies else 0,
            "min_accuracy": min(all_accuracies) if all_accuracies else 0,
            "max_accuracy": max(all_accuracies) if all_accuracies else 0,
            "mean_entropy": sum(all_entropies) / len(all_entropies) if all_entropies else 1,
        }

        # Compute distance decay coefficient (how fast accuracy drops with distance)
        if len(results["distance_decay"]) >= 2:
            distances = [d["distance"] for d in results["distance_decay"]]
            accuracies = [d["accuracy"] for d in results["distance_decay"]]
            # Simple linear regression for decay rate
            if max(distances) > min(distances):
                n = len(distances)
                mean_d = sum(distances) / n
                mean_a = sum(accuracies) / n
                numerator = sum((d - mean_d) * (a - mean_a) for d, a in zip(distances, accuracies))
                denominator = sum((d - mean_d) ** 2 for d in distances)
                decay_rate = numerator / denominator if denominator != 0 else 0
                results["summary"]["decay_rate"] = decay_rate
            else:
                results["summary"]["decay_rate"] = 0
        else:
            results["summary"]["decay_rate"] = 0

        # Print summary
        print(f"  ╠══════════════════════════════════════════════════════════════╣")
        summary = results["summary"]
        overall_icon = "🟢" if summary["mean_accuracy"] > 0.7 else "🟡" if summary["mean_accuracy"] > 0.4 else "🔴"
        print(f"  ║  SUMMARY: Avg Acc: {summary['mean_accuracy']:.1%} │ "
              f"Range: [{summary['min_accuracy']:.1%}-{summary['max_accuracy']:.1%}] {overall_icon}  ║")
        print(f"  ║  Decay Rate: {summary['decay_rate']:.4f}/token │ "
              f"Mean Entropy: {summary['mean_entropy']:.3f}         ║")
        print(f"  ╚══════════════════════════════════════════════════════════════╝\n")

        # Store in history
        self.results_history.append(results)

        return results

    def get_retrieval_score(self) -> float:
        """
        Get a single retrieval score (0-1) from the most recent validation.

        Score combines:
        - Mean accuracy (60%)
        - Distance resilience (30%) - how well accuracy holds over distance
        - Confidence (10%)
        """
        if not self.results_history:
            return 0.0

        latest = self.results_history[-1]
        summary = latest["summary"]

        # Mean accuracy component
        acc_score = summary["mean_accuracy"] * 0.6

        # Distance resilience (inverse of decay rate, normalized)
        # decay_rate is negative when accuracy drops with distance
        decay = abs(summary.get("decay_rate", 0))
        resilience = max(0, 1.0 - decay * 100)  # Scale decay to 0-1
        resilience_score = resilience * 0.3

        # Entropy component (lower is better)
        entropy_score = (1.0 - summary["mean_entropy"]) * 0.1

        return min(1.0, acc_score + resilience_score + entropy_score)

    def format_compact_result(self) -> str:
        """Format a compact one-line result for logging."""
        if not self.results_history:
            return "LRA: No data"

        latest = self.results_history[-1]
        summary = latest["summary"]
        score = self.get_retrieval_score()

        icon = "🟢" if score > 0.7 else "🟡" if score > 0.4 else "🔴"
        return f"LRA:{score:.2f}{icon} Acc:{summary['mean_accuracy']:.1%} Decay:{summary['decay_rate']:.4f}"


# =============================================================================
# Phase Rotation Test (validates phase encodes relational structure)
# =============================================================================

def run_phase_rotation_test(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    config: 'UnifiedTrainingConfig',
    autocast_dtype: torch.dtype,
    evaluate_fn: Callable = None,
    angles_degrees: List[float] = None,
    cached_val_batches: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Run phase rotation test to verify phase encodes relational structure.

    HYPOTHESIS:
    -----------
    If roles/relations are encoded as phase offsets:
    - Rotating φ_k by θ should shift which bindings are retrieved
    - Larger rotations should cause larger perplexity increases
    - 180° rotation should cause maximum disruption

    If phase is decorative:
    - Rotation should have minimal/random effect on perplexity
    - No systematic relationship between rotation angle and perplexity

    Args:
        model: Model with phase attention (must have set_rotation method)
        val_loader: Validation DataLoader
        device: Device to run on
        config: Training configuration
        autocast_dtype: Autocast dtype for mixed precision
        evaluate_fn: Callable that performs evaluation. Signature:
            evaluate_fn(model, val_loader, device, config, autocast_dtype,
                        cached_val_batches=...) -> (loss, metrics_dict)
            where metrics_dict contains 'ppl'. If None, the function will
            attempt to import ``evaluate`` from the parent training module.
        angles_degrees: List of rotation angles in degrees (default: 0, 45, 90, 135, 180, 270)
        cached_val_batches: Optional pre-cached validation batches

    Returns:
        Dictionary with:
        - 'perplexity': {angle: ppl} for each angle
        - 'loss': {angle: loss} for each angle
        - 'delta_ppl': {angle: ppl_change} relative to baseline
        - 'sensitivity': float (mean absolute ppl delta, higher = more sensitive)
        - 'systematic': bool (True if ppl increases with angle up to 180°)
    """
    if evaluate_fn is None:
        raise ValueError(
            "evaluate_fn must be provided. Pass the evaluate() function from "
            "the training module, e.g.: run_phase_rotation_test(..., evaluate_fn=evaluate)"
        )

    if angles_degrees is None:
        angles_degrees = [0, 45, 90, 135, 180, 270]

    if not hasattr(model, 'set_rotation'):
        return {
            'perplexity': {0: float('nan')},
            'loss': {0: float('nan')},
            'delta_ppl': {0: 0.0},
            'sensitivity': 0.0,
            'systematic': False,
            'error': 'Model does not support rotation (no set_rotation method)'
        }

    results = {'perplexity': {}, 'loss': {}, 'delta_ppl': {}}

    # Get baseline (0° rotation)
    model.set_rotation(0.0)
    baseline_loss, baseline_metrics = evaluate_fn(
        model, val_loader, device, config, autocast_dtype,
        cached_val_batches=cached_val_batches
    )
    baseline_ppl = baseline_metrics['ppl']
    results['perplexity'][0] = baseline_ppl
    results['loss'][0] = baseline_loss
    results['delta_ppl'][0] = 0.0

    # Test each rotation angle
    for angle_deg in angles_degrees:
        if angle_deg == 0:
            continue  # Already computed

        angle_rad = math.radians(angle_deg)
        model.set_rotation(angle_rad)
        loss, metrics = evaluate_fn(
            model, val_loader, device, config, autocast_dtype,
            cached_val_batches=cached_val_batches
        )
        ppl = metrics['ppl']
        results['perplexity'][angle_deg] = ppl
        results['loss'][angle_deg] = loss
        results['delta_ppl'][angle_deg] = ppl - baseline_ppl

    # Clear rotation
    model.clear_rotation()

    # Compute sensitivity metrics (normalized by baseline)
    deltas = [abs(d) / baseline_ppl for a, d in results['delta_ppl'].items() if a != 0]
    results['sensitivity'] = sum(deltas) / len(deltas) if deltas else 0.0

    # Check if perplexity increases systematically with angle (up to 180°)
    angles_sorted = sorted([a for a in results['perplexity'].keys() if a <= 180])
    ppls_sorted = [results['perplexity'][a] for a in angles_sorted]
    # Systematic if ppl generally increases (allowing small fluctuations)
    increasing_pairs = sum(1 for i in range(len(ppls_sorted)-1) if ppls_sorted[i] <= ppls_sorted[i+1] * 1.02)
    results['systematic'] = increasing_pairs >= (len(ppls_sorted) - 2) if len(ppls_sorted) > 2 else False

    # Additional analysis: find angle of maximum disruption
    if results['delta_ppl']:
        max_delta = max(results['delta_ppl'].items(), key=lambda x: x[1])
        results['max_disruption_angle'] = max_delta[0]
        results['max_disruption_delta'] = max_delta[1]

    return results


def print_phase_rotation_results(
    results: Dict[str, Any],
    model_name: str = "Model",
) -> None:
    """Pretty-print phase rotation test results."""
    print(f"\n{'='*70}")
    print(f"PHASE ROTATION TEST: {model_name}")
    print(f"{'='*70}")

    if 'error' in results:
        print(f"  ERROR: {results['error']}")
        return

    baseline_ppl = results['perplexity'].get(0, 1.0)

    print(f"\nHypothesis: If phase encodes relations, rotating φ_k should disrupt retrieval.")
    print(f"\n  {'Angle':>8}  {'Perplexity':>12}  {'Δ PPL':>10}  {'Δ %':>8}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*10}  {'-'*8}")

    for angle in sorted(results['perplexity'].keys()):
        ppl = results['perplexity'][angle]
        delta = results['delta_ppl'][angle]
        delta_pct = (delta / baseline_ppl) * 100 if baseline_ppl > 0 else 0
        delta_str = f"{delta:+.2f}" if angle != 0 else "baseline"
        pct_str = f"{delta_pct:+.1f}%" if angle != 0 else ""
        print(f"  {angle:>6}°  {ppl:>12.2f}  {delta_str:>10}  {pct_str:>8}")

    print(f"\n  Sensitivity (mean |Δ|/baseline): {results['sensitivity']*100:.2f}%")
    print(f"  Systematic increase:             {'Yes' if results['systematic'] else 'No'}")

    if 'max_disruption_angle' in results:
        print(f"  Max disruption at:               {results['max_disruption_angle']}° (+{results['max_disruption_delta']:.2f} PPL)")

    # Interpretation
    print(f"\n  INTERPRETATION:")
    if results['sensitivity'] > 0.10:
        print(f"    → Phase is SENSITIVE to rotation (sensitivity > 10%)")
        print(f"    → Phase likely encodes meaningful relational structure")
        if results['systematic']:
            print(f"    → Systematic increase suggests phase offset = relation encoding")
    elif results['sensitivity'] > 0.05:
        print(f"    → Phase shows MODERATE sensitivity to rotation")
        print(f"    → Phase may partially encode relational structure")
    else:
        print(f"    → Phase is INSENSITIVE to rotation (sensitivity < 5%)")
        print(f"    → Phase may be DECORATIVE (not encoding relations)")
