"""
Evaluation module: validation, generation, and readiness assessment.

Combines LRA validation, phase rotation testing, text generation with
quality monitoring, and the ReadinessIndex composite stability measurement.

Merged from validation.py, generation.py, and ReadinessIndex from curriculum.py
"""

import math
from typing import Optional, Dict, List, Tuple, Any, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from symbolu.training.entropy_control import (
    EntropyControlConfig,
    AdaptiveEntropyController,
)

# Import clean_wikitext_artifacts (optional dependency)
try:
    from symbolu.training import clean_wikitext_artifacts
    _CLEAN_WIKITEXT_AVAILABLE = True
except ImportError:
    _CLEAN_WIKITEXT_AVAILABLE = False


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


# =============================================================================
# GENERATION: Text generation and quality monitoring
# =============================================================================

def generate_sample(
    model: nn.Module,
    tokenizer,
    prompt: str,
    device: torch.device,
    max_new_tokens: int = 128,
    temperature: float = 0.9,
    top_p: float = 0.95,
    top_k: int = 50,
    repetition_penalty: float = 1.15,
    no_repeat_ngram_size: int = 3,
    entropy_controller: Optional[AdaptiveEntropyController] = None,
) -> str:
    """
    Generate text from a prompt for quality monitoring.

    Uses nucleus (top-p) sampling with temperature for diverse outputs.
    ChatGPT recommendations for breaking repetition:
    - temperature = 0.8-1.0
    - top_p = 0.95
    - top_k = 50
    - repetition_penalty = 1.1-1.2
    - no_repeat_ngram_size = 3
    - max_new_tokens = 128-192

    If entropy_controller is provided, applies adaptive logit scaling
    to keep output entropy near target band.
    """
    model.eval()

    # Encode prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    prompt_len = input_ids.shape[1]

    # Generate tokens one by one
    generated = input_ids.clone()

    # Reset entropy controller for new generation
    if entropy_controller is not None:
        initial_scale = None
        if hasattr(model, 'entropy_logit_scale'):
            initial_scale = model.entropy_logit_scale.logit_scale
        entropy_controller.reset(initial_scale)

    # Track generated n-grams for no_repeat_ngram blocking
    def get_ngrams(seq, n):
        """Extract n-grams from a sequence."""
        ngrams = set()
        for i in range(len(seq) - n + 1):
            ngrams.add(tuple(seq[i:i+n].tolist()))
        return ngrams

    for step in range(max_new_tokens):
        # Forward pass
        outputs = model(generated)

        # Handle different output formats (dict with 'logits', tuple, or tensor)
        if isinstance(outputs, dict):
            logits = outputs.get('logits', outputs.get('output', None))
            if logits is None:
                # Try to find logits-like tensor in dict
                for key in ['logits', 'output', 'lm_logits']:
                    if key in outputs:
                        logits = outputs[key]
                        break
        elif isinstance(outputs, (tuple, list)):
            logits = outputs[0]
        else:
            logits = outputs

        if logits is None:
            break

        # Get next token logits
        next_logits = logits[:, -1, :].clone()

        # Adaptive entropy control (inference-time)
        if entropy_controller is not None:
            next_logits = entropy_controller.scale_logits(next_logits)
            entropy_controller.update(next_logits)

        # Apply repetition penalty to previously generated tokens
        if repetition_penalty != 1.0:
            for token_id in set(generated[0, prompt_len:].tolist()):
                if next_logits[0, token_id] > 0:
                    next_logits[0, token_id] /= repetition_penalty
                else:
                    next_logits[0, token_id] *= repetition_penalty

        # Apply no_repeat_ngram blocking
        if no_repeat_ngram_size > 0 and generated.shape[1] >= no_repeat_ngram_size:
            # Get the last (n-1) tokens as the prefix
            prefix = tuple(generated[0, -(no_repeat_ngram_size - 1):].tolist())
            # Get all existing n-grams
            existing_ngrams = get_ngrams(generated[0], no_repeat_ngram_size)
            # Block tokens that would create a repeated n-gram
            for ngram in existing_ngrams:
                if ngram[:-1] == prefix:
                    # This token would complete a repeated n-gram
                    next_logits[0, ngram[-1]] = float('-inf')

        # Apply temperature
        next_logits = next_logits / temperature

        # Top-k filtering (optional, applied before top-p)
        if top_k > 0:
            top_k_vals, _ = torch.topk(next_logits, min(top_k, next_logits.size(-1)))
            threshold = top_k_vals[0, -1]
            next_logits[next_logits < threshold] = float('-inf')

        # Top-p (nucleus) sampling
        sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
        cumsum = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Remove tokens with cumulative probability above threshold
        sorted_indices_to_remove = cumsum > top_p
        sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
        sorted_indices_to_remove[:, 0] = False

        # Set removed tokens to -inf
        indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
        next_logits[indices_to_remove] = float('-inf')

        # Sample next token
        probs = F.softmax(next_logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)

        # Append to sequence
        generated = torch.cat([generated, next_token], dim=1)

        # Check for EOS
        if next_token.item() == tokenizer.eos_token_id:
            break

    # Decode and return
    return tokenizer.decode(generated[0], skip_special_tokens=True)


def compute_sample_metrics(text: str) -> Dict[str, float]:
    """
    Compute quality metrics for generated text.

    Returns:
        - completion_rate: 1.0 if ends with punctuation, 0.0 otherwise
        - repetition_score: n-gram repetition rate (lower is better)
        - unique_ratio: ratio of unique tokens to total tokens
        - coherence_score: basic semantic coherence (0.0-1.0, higher is better)
    """
    words = text.split()
    if len(words) < 2:
        return {"completion": 0.0, "repetition": 1.0, "unique_ratio": 0.0, "coherence": 0.0}

    # Completion rate: ends with sentence-ending punctuation
    completion = 1.0 if text.rstrip()[-1:] in '.!?' else 0.0

    # Repetition score: bigram repetition rate
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    if bigrams:
        unique_bigrams = len(set(bigrams))
        repetition = 1.0 - (unique_bigrams / len(bigrams))
    else:
        repetition = 0.0

    # Unique token ratio
    unique_ratio = len(set(words)) / len(words) if words else 0.0

    # CRITICAL FIX: Semantic coherence check (basic heuristics)
    # Checks for common signs of gibberish vs. meaningful text
    coherence = 1.0

    # Penalty 1: Too many short words (gibberish often has many 1-2 char tokens)
    short_word_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
    if short_word_ratio > 0.5:
        coherence *= 0.5

    # Penalty 2: Too many non-alphabetic tokens
    alpha_ratio = sum(1 for w in words if w.isalpha()) / len(words)
    if alpha_ratio < 0.6:
        coherence *= 0.6

    # Penalty 3: Excessive punctuation clustering (e.g., "... ,, ,,")
    punct_cluster = text.count(',,') + text.count('..') * 0.5
    if punct_cluster > 3:
        coherence *= 0.4

    # Penalty 4: Repeated single characters (e.g., "a a a a")
    single_char_repeat = sum(1 for i in range(len(words)-2)
                            if len(words[i]) == 1 and words[i] == words[i+1])
    if single_char_repeat > 2:
        coherence *= 0.3

    # Bonus: Reasonable average word length (4-8 chars is typical English)
    avg_word_len = sum(len(w) for w in words) / len(words)
    if 4.0 <= avg_word_len <= 8.0:
        coherence *= 1.1
    coherence = min(coherence, 1.0)

    return {
        "completion": completion,
        "repetition": repetition,
        "unique_ratio": unique_ratio,
        "coherence": coherence,
    }


def run_quality_samples(
    model: nn.Module,
    tokenizer,
    config: 'UnifiedTrainingConfig',
    device: torch.device,
    step: int,
    logger=None,
):
    """
    Generate sample outputs to monitor training quality.

    This provides a qualitative check that the model is learning
    meaningful language patterns, not just minimizing perplexity.

    Samples are logged with prompts, generated completions, and quality metrics.
    """
    def log(msg):
        if logger:
            logger.info(msg)
        else:
            print(msg)

    log("")
    log("=" * 60)
    log(f"  📝 QUALITY SAMPLES (Step {step})")
    log("=" * 60)

    # V9.6.10 Diagnostic: Show top predicted tokens for first prompt
    try:
        diag_prompt = config.sample_prompts[0] if config.sample_prompts else "The"
        diag_ids = tokenizer.encode(diag_prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            diag_out = model(diag_ids)
            if isinstance(diag_out, dict):
                diag_logits = diag_out.get('logits', diag_out.get('output'))
            else:
                diag_logits = diag_out
            # Get logits for last position
            last_logits = diag_logits[0, -1, :]
            top_probs = torch.softmax(last_logits, dim=-1)
            top_vals, top_ids = torch.topk(top_probs, 10)
            log(f"  🔍 [DIAGNOSTIC] Top-10 predicted tokens after \"{diag_prompt}\":")
            for i, (prob, tid) in enumerate(zip(top_vals, top_ids)):
                tok_str = tokenizer.decode([tid.item()])
                log(f"      {i+1}. '{tok_str}' (id={tid.item()}, p={prob.item():.4f})")
    except Exception as e:
        log(f"  🔍 [DIAGNOSTIC] Failed: {e}")

    # Aggregate metrics across all samples
    total_completion = 0.0
    total_repetition = 0.0
    total_unique = 0.0
    total_coherence = 0.0
    sample_count = 0

    for prompt in config.sample_prompts:
        try:
            # ChatGPT recommendations for quality samples:
            # temperature=0.9, top_p=0.95, top_k=50
            # repetition_penalty=1.15, no_repeat_ngram_size=3
            # Create adaptive entropy controller for inference if enabled
            _infer_entropy_ctrl = None
            if hasattr(config, 'enable_entropy_control_infer') and config.enable_entropy_control_infer:
                _ec_cfg = EntropyControlConfig(
                    enable_entropy_control_infer=True,
                    entropy_topk=getattr(config, 'entropy_topk', 50),
                    infer_h_target=getattr(config, 'infer_h_target', 0.25),
                    infer_eta=getattr(config, 'infer_eta', 0.02),
                    infer_delta_clip=getattr(config, 'infer_delta_clip', 0.05),
                    logit_scale_min=getattr(config, 'logit_scale_min', -4.0),
                    logit_scale_max=getattr(config, 'logit_scale_max', 4.0),
                )
                _init_scale = None
                if hasattr(model, 'entropy_logit_scale'):
                    _init_scale = model.entropy_logit_scale.logit_scale
                _infer_entropy_ctrl = AdaptiveEntropyController(_ec_cfg, _init_scale)
            generated = generate_sample(
                model, tokenizer, prompt, device,
                max_new_tokens=128,
                temperature=0.9,
                top_p=0.95,
                top_k=50,
                repetition_penalty=1.15,
                no_repeat_ngram_size=3,
                entropy_controller=_infer_entropy_ctrl,
            )
            # Clean up WikiText artifacts and truncate for display
            generated = generated.strip().replace('\n', ' ')
            if _CLEAN_WIKITEXT_AVAILABLE:
                generated = clean_wikitext_artifacts(generated)
            generated = generated[:200]

            # Compute quality metrics
            metrics = compute_sample_metrics(generated)
            total_completion += metrics["completion"]
            total_repetition += metrics["repetition"]
            total_unique += metrics["unique_ratio"]
            total_coherence += metrics["coherence"]
            sample_count += 1

            log(f"  Prompt: \"{prompt}\"")
            log(f"  Output: \"{generated}\"")
            log("")
        except Exception as e:
            log(f"  ⚠️ Sampling failed for prompt '{prompt[:30]}...': {e}")

    # Log aggregate quality metrics
    if sample_count > 0:
        avg_completion = total_completion / sample_count
        avg_repetition = total_repetition / sample_count
        avg_unique = total_unique / sample_count
        avg_coherence = total_coherence / sample_count

        log("  ────────────────────────────────────────────────────────")
        log(f"  📊 SAMPLE QUALITY METRICS (n={sample_count})")
        log(f"     Completion Rate: {avg_completion*100:.0f}% (ends with punctuation)")
        log(f"     Repetition Score: {avg_repetition*100:.1f}% (lower is better)")
        log(f"     Unique Token Ratio: {avg_unique*100:.1f}%")
        log(f"     Coherence Score: {avg_coherence*100:.0f}% (semantic quality)")

        # CRITICAL FIX: Quality indicator now includes coherence
        # Previous logic was misleading - high diversity alone doesn't mean good quality
        if avg_coherence > 0.7 and avg_repetition < 0.3 and avg_unique > 0.6:
            log("     Quality: 🟢 GOOD (coherent + diverse)")
        elif avg_coherence > 0.5 and avg_repetition < 0.5:
            log("     Quality: 🟡 IMPROVING (needs better coherence)")
        else:
            log("     Quality: 🔴 NEEDS WORK (likely gibberish despite diversity)")
            log("     ⚠️  WARNING: High diversity without coherence = meaningless tokens")

    log("=" * 60)
    log("")


# =============================================================================
# READINESS INDEX: Composite stability measurement
# =============================================================================

class ReadinessIndex:
    """
    V9.9.4: Composite stability measurement for curriculum transitions.

    Combines surface metrics (PPL velocity/acceleration) with internal
    geometry metrics (phase coherence, state-delta stability) to determine
    true learning stability.

    ChatGPT's analogy: "Learning to ride a bicycle - true stability is when
    you are no longer correcting every second and your balance stops oscillating."

    The index answers: "Has PPL stopped changing because the model has SETTLED?"
    Not just: "Is PPL going down?"
    """

    def __init__(
        self,
        ppl_velocity_threshold: float = 5.0,      # Max |ΔPPL| for "settled"
        ppl_accel_threshold: float = 2.0,         # Max |ΔΔPPL| for "settled"
        phase_stability_threshold: float = 0.1,   # Max phase variance for stable
        state_delta_threshold: float = 0.5,       # Max state-delta magnitude for stable
        history_window: int = 10,                 # Steps to track
        require_geometry_check: bool = True,      # Gate with internal metrics
        required_consecutive_stable: int = 3,     # N consecutive windows for persistence
    ):
        """
        Initialize ReadinessIndex.

        Args:
            ppl_velocity_threshold: Maximum PPL velocity (ΔPPL) to consider stable
            ppl_accel_threshold: Maximum PPL acceleration (ΔΔPPL) to consider stable
            phase_stability_threshold: Maximum phase coherence variance for stable
            state_delta_threshold: Maximum state-delta norm for stable geometry
            history_window: Number of steps to track in history
            require_geometry_check: If True, also check internal geometry metrics
            required_consecutive_stable: Number of consecutive windows that must
                pass all checks before declaring truly ready (persistence guard)
        """
        self.ppl_velocity_threshold = ppl_velocity_threshold
        self.ppl_accel_threshold = ppl_accel_threshold
        self.phase_stability_threshold = phase_stability_threshold
        self.state_delta_threshold = state_delta_threshold
        self.history_window = history_window
        self.require_geometry_check = require_geometry_check
        self.required_consecutive_stable = required_consecutive_stable

        # History tracking
        self.ppl_history: List[float] = []
        self.phase_coherence_history: List[float] = []
        self.state_delta_history: List[float] = []

        # V9.9.4 Persistence Guard: Track consecutive stable windows
        # "Geometry must be stable for N consecutive windows, not just one"
        # This prevents premature advancement during "false calm" when phase
        # appears stable briefly during representation re-binding.
        self.consecutive_stable_count: int = 0

    def update(
        self,
        ppl: float,
        phase_coherence: Optional[float] = None,
        state_delta_norm: Optional[float] = None,
    ):
        """
        Update history with latest metrics.

        Args:
            ppl: Current perplexity
            phase_coherence: Phase coherence from SPC diagnostics (0-1)
            state_delta_norm: Magnitude of state-delta from Sovereign State
        """
        self.ppl_history.append(ppl)
        if len(self.ppl_history) > self.history_window:
            self.ppl_history.pop(0)

        if phase_coherence is not None:
            self.phase_coherence_history.append(phase_coherence)
            if len(self.phase_coherence_history) > self.history_window:
                self.phase_coherence_history.pop(0)

        if state_delta_norm is not None:
            self.state_delta_history.append(state_delta_norm)
            if len(self.state_delta_history) > self.history_window:
                self.state_delta_history.pop(0)

    def compute_ppl_velocity(self) -> float:
        """Compute ΔPPL (first derivative) - rate of PPL change."""
        if len(self.ppl_history) < 2:
            return float('inf')

        # Average of differences
        diffs = [self.ppl_history[i+1] - self.ppl_history[i]
                 for i in range(len(self.ppl_history) - 1)]
        return sum(diffs) / len(diffs)

    def compute_ppl_acceleration(self) -> float:
        """Compute ΔΔPPL (second derivative) - rate of velocity change."""
        if len(self.ppl_history) < 3:
            return float('inf')

        # First differences (velocities)
        velocities = [self.ppl_history[i+1] - self.ppl_history[i]
                      for i in range(len(self.ppl_history) - 1)]

        # Second differences (acceleration)
        accels = [velocities[i+1] - velocities[i]
                  for i in range(len(velocities) - 1)]

        return sum(accels) / len(accels) if accels else float('inf')

    def compute_phase_stability(self) -> float:
        """Compute variance in phase coherence (lower = more stable)."""
        if len(self.phase_coherence_history) < 3:
            return float('inf')

        mean = sum(self.phase_coherence_history) / len(self.phase_coherence_history)
        variance = sum((x - mean) ** 2 for x in self.phase_coherence_history) / len(self.phase_coherence_history)
        return variance ** 0.5  # Standard deviation

    def compute_state_delta_stability(self) -> float:
        """Compute average state-delta magnitude (lower = more settled)."""
        if len(self.state_delta_history) < 2:
            return float('inf')

        return sum(self.state_delta_history) / len(self.state_delta_history)

    def is_ready(self, require_geometry: Optional[bool] = None) -> Tuple[bool, Dict[str, any]]:
        """
        Check if model has truly settled (ready for curriculum advancement).

        Returns:
            Tuple of (is_ready, diagnostics_dict)
        """
        if require_geometry is None:
            require_geometry = self.require_geometry_check

        velocity = self.compute_ppl_velocity()
        acceleration = self.compute_ppl_acceleration()
        phase_std = self.compute_phase_stability()
        state_delta_avg = self.compute_state_delta_stability()

        diagnostics = {
            'ppl_velocity': velocity,
            'ppl_acceleration': acceleration,
            'phase_stability': phase_std,
            'state_delta_avg': state_delta_avg,
            'checks': {},
        }

        # Check 1: PPL velocity collapsed (ΔPPL → 0)
        velocity_ok = abs(velocity) <= self.ppl_velocity_threshold
        diagnostics['checks']['velocity'] = velocity_ok

        # Check 2: PPL acceleration collapsed (ΔΔPPL → 0)
        accel_ok = abs(acceleration) <= self.ppl_accel_threshold
        diagnostics['checks']['acceleration'] = accel_ok

        # Check 3: Internal geometry stable (if required)
        geometry_ok = True
        if require_geometry:
            phase_ok = phase_std <= self.phase_stability_threshold if phase_std != float('inf') else True
            state_ok = state_delta_avg <= self.state_delta_threshold if state_delta_avg != float('inf') else True
            geometry_ok = phase_ok and state_ok
            diagnostics['checks']['phase_stable'] = phase_ok
            diagnostics['checks']['state_settled'] = state_ok

        diagnostics['checks']['geometry'] = geometry_ok

        # All individual checks pass this window?
        window_stable = velocity_ok and accel_ok and geometry_ok

        # V9.9.4 Persistence Guard: Track consecutive stable windows
        # "Geometry must be stable for N consecutive windows, not just one"
        # This prevents premature advancement during "false calm" when phase
        # appears stable briefly during representation re-binding.
        if window_stable:
            self.consecutive_stable_count += 1
        else:
            self.consecutive_stable_count = 0

        # True readiness requires N consecutive stable windows
        is_ready = self.consecutive_stable_count >= self.required_consecutive_stable

        diagnostics['consecutive_stable'] = self.consecutive_stable_count
        diagnostics['required_consecutive'] = self.required_consecutive_stable
        diagnostics['window_stable'] = window_stable
        diagnostics['ready'] = is_ready

        # Generate reason string
        if is_ready:
            diagnostics['reason'] = "settled"
        elif window_stable and self.consecutive_stable_count < self.required_consecutive_stable:
            diagnostics['reason'] = f"stabilizing_{self.consecutive_stable_count}/{self.required_consecutive_stable}"
        elif not velocity_ok:
            if velocity > 0:
                diagnostics['reason'] = "ppl_rising"
            else:
                diagnostics['reason'] = "ppl_dropping_fast"
        elif not accel_ok:
            diagnostics['reason'] = "ppl_unstable"
        elif not geometry_ok:
            diagnostics['reason'] = "geometry_rotating"
        else:
            diagnostics['reason'] = "unknown"

        return is_ready, diagnostics

    def get_composite_score(self) -> float:
        """
        Get a 0-1 readiness score (useful for logging/visualization).

        Higher = more ready to advance. Includes persistence progress.
        """
        velocity = abs(self.compute_ppl_velocity())
        accel = abs(self.compute_ppl_acceleration())

        # Normalize to 0-1 (higher = better)
        velocity_score = max(0, 1 - velocity / (self.ppl_velocity_threshold * 3))
        accel_score = max(0, 1 - accel / (self.ppl_accel_threshold * 3))

        # Persistence progress: how close are we to required consecutive stable?
        persistence_score = min(1.0, self.consecutive_stable_count / max(1, self.required_consecutive_stable))

        # Weight: velocity + acceleration determine metric stability,
        # persistence determines temporal stability
        metric_score = 0.6 * velocity_score + 0.4 * accel_score
        return 0.7 * metric_score + 0.3 * persistence_score

    def reset_persistence(self):
        """
        Reset the consecutive stability counter.

        Call this after a curriculum transition to start fresh with
        stability tracking for the new stage.
        """
        self.consecutive_stable_count = 0

    def get_persistence_progress(self) -> Tuple[int, int]:
        """Get (current_consecutive, required_consecutive) for logging."""
        return self.consecutive_stable_count, self.required_consecutive_stable


