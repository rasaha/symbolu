"""
Evaluation, ablation, and rotation test functions.

Contains:
    - compute_param_diff: Calculate parameter count differences
    - evaluate: Evaluate on a single split
    - evaluate_all_splits: Evaluate across all test splits
    - run_ablation: Scramble/freeze phase to test causality
    - run_rotation_test: Rotate query phase for relational encoding test

CLI Usage::

    # With rotation test
    python train_hard_probes.py --rotation-test

    # Custom rotation angles
    python train_hard_probes.py --rotation-test --rotation-angles 0,30,60,90,120,150,180

    # Parameter-matched comparison
    python train_hard_probes.py --match-params
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Optional

# =============================================================================
# EVALUATION
# =============================================================================

def evaluate(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> float:
    """Evaluate model accuracy."""
    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for ids, targets, _ in loader:
            ids, targets = ids.to(device), targets.to(device)

            # Convert entity IDs to class indices
            target_idx = torch.tensor([
                vocab.entity_to_idx(t.item()) if t.item() in vocab.entities else 0
                for t in targets
            ], device=device)

            logits = model(ids)
            preds = logits.argmax(dim=-1)

            # Handle NULL (maps to class 0 by convention, or separate handling)
            for i in range(len(targets)):
                if targets[i].item() == vocab.NULL:
                    # NULL target — check if prediction is outside entity range or class 0
                    # For simplicity, we'll treat NULL as predicting the "NULL entity" which is vocab.entities[0]
                    target_idx[i] = 0

            correct += (preds == target_idx).sum().item()
            total += len(targets)

    return correct / max(total, 1)


def evaluate_all_splits(
    model: nn.Module,
    test_loaders: Dict[SplitType, DataLoader],
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Evaluate on all test splits separately."""
    results = {}
    for split, loader in test_loaders.items():
        acc = evaluate(model, loader, vocab, device)
        results[split.value] = acc
    return results


def run_ablation(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
) -> Dict[str, float]:
    """Run phase ablation tests."""
    results = {}
    for mode in ["none", "scramble", "freeze", "off"]:
        model.set_ablation(mode)
        acc = evaluate(model, loader, vocab, device)
        results[mode] = acc
    model.set_ablation("none")
    return results


def run_rotation_test(
    model: nn.Module,
    loader: DataLoader,
    vocab: HardVocabulary,
    device: str,
    angles_degrees: List[float] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Run phase rotation tests to verify phase encodes relational structure.

    HYPOTHESIS:
    -----------
    If roles are encoded as phase offsets (e.g., R0 → φ=0, R1 → φ=π/2):
    - Rotating φ_q by θ should shift which role's binding is retrieved
    - Larger rotations should cause larger accuracy drops
    - Specific rotations might "swap" roles (retrieve R1 when querying R0)

    If phase is decorative:
    - Rotation should have minimal/random effect on accuracy
    - No systematic relationship between rotation angle and accuracy

    Args:
        model: Model with phase attention (must have set_rotation method)
        loader: DataLoader for evaluation
        vocab: Vocabulary for decoding
        device: Device to run on
        angles_degrees: List of rotation angles in degrees (default: 0, 45, 90, 135, 180)

    Returns:
        Dictionary with:
        - 'accuracy': {angle: accuracy} for each angle
        - 'delta': {angle: accuracy_change} relative to baseline
        - 'sensitivity': float (mean absolute delta, higher = more sensitive)
        - 'systematic': bool (True if accuracy decreases monotonically with angle)
    """
    if angles_degrees is None:
        angles_degrees = [0, 45, 90, 135, 180, 270]

    if not hasattr(model, 'set_rotation'):
        return {
            'accuracy': {0: evaluate(model, loader, vocab, device)},
            'delta': {0: 0.0},
            'sensitivity': 0.0,
            'systematic': False,
            'error': 'Model does not support rotation (no set_rotation method)'
        }

    results = {'accuracy': {}, 'delta': {}}

    # Get baseline (0° rotation)
    model.set_rotation(0.0)
    baseline = evaluate(model, loader, vocab, device)
    results['accuracy'][0] = baseline
    results['delta'][0] = 0.0

    # Test each rotation angle
    for angle_deg in angles_degrees:
        if angle_deg == 0:
            continue  # Already computed

        angle_rad = math.radians(angle_deg)
        model.set_rotation(angle_rad)
        acc = evaluate(model, loader, vocab, device)
        results['accuracy'][angle_deg] = acc
        results['delta'][angle_deg] = acc - baseline

    # Clear rotation
    model.clear_rotation()

    # Compute sensitivity metrics
    deltas = [abs(d) for a, d in results['delta'].items() if a != 0]
    results['sensitivity'] = sum(deltas) / len(deltas) if deltas else 0.0

    # Check if accuracy drops systematically with angle (up to 180°)
    angles_sorted = sorted([a for a in results['accuracy'].keys() if a <= 180])
    accs_sorted = [results['accuracy'][a] for a in angles_sorted]
    # Systematic if accuracy generally decreases (allowing small fluctuations)
    decreasing_pairs = sum(1 for i in range(len(accs_sorted)-1) if accs_sorted[i] >= accs_sorted[i+1] - 0.02)
    results['systematic'] = decreasing_pairs >= (len(accs_sorted) - 2) if len(accs_sorted) > 2 else False

    # Additional analysis: find angle of maximum disruption
    if results['delta']:
        min_delta_angle = min(results['delta'].items(), key=lambda x: x[1])
        results['max_disruption_angle'] = min_delta_angle[0]
        results['max_disruption_delta'] = min_delta_angle[1]

    return results


def print_rotation_test_results(
    results: Dict[str, Dict[str, float]],
    model_name: str = "Phase",
) -> None:
    """Pretty-print rotation test results."""
    print(f"\n--- PHASE ROTATION TEST: {model_name} ---")

    if 'error' in results:
        print(f"  ERROR: {results['error']}")
        return

    print(f"\n  {'Angle':>8}  {'Accuracy':>10}  {'Δ from 0°':>10}")
    print(f"  {'-'*8}  {'-'*10}  {'-'*10}")

    for angle in sorted(results['accuracy'].keys()):
        acc = results['accuracy'][angle]
        delta = results['delta'][angle]
        delta_str = f"{delta*100:+.1f}%" if angle != 0 else "baseline"
        print(f"  {angle:>6}°  {acc*100:>9.1f}%  {delta_str:>10}")

    print(f"\n  Sensitivity (mean |Δ|): {results['sensitivity']*100:.2f}%")
    print(f"  Systematic decrease:    {'Yes' if results['systematic'] else 'No'}")

    if 'max_disruption_angle' in results:
        print(f"  Max disruption at:      {results['max_disruption_angle']}° ({results['max_disruption_delta']*100:+.1f}%)")

    # Interpretation
    print(f"\n  INTERPRETATION:")
    if results['sensitivity'] > 0.10:
        print(f"    → Phase is SENSITIVE to rotation (sensitivity > 10%)")
        print(f"    → Phase likely encodes meaningful relational structure")
        if results['systematic']:
            print(f"    → Systematic decrease suggests phase offset = role encoding")
    elif results['sensitivity'] > 0.03:
        print(f"    → Phase shows MODERATE sensitivity to rotation")
        print(f"    → Phase may partially encode relational structure")
    else:
        print(f"    → Phase is INSENSITIVE to rotation (sensitivity < 3%)")
        print(f"    → Phase appears DECORATIVE (not encoding relations)")


# =============================================================================
# V10.5: INTERFERENCE-AWARE PROPOSAL SCORING BENCHMARKS
# =============================================================================
# Tests the text interference scoring implementation to verify correctness.

# Task classifier test cases: (prompt, expected_compositional)
INTERFERENCE_TASK_TEST_CASES = [
    # Compositional tasks (should enable interference)
    ("Compare and contrast the trade-offs between microservices and monoliths.", True),
    ("Synthesize the key findings from multiple research papers on climate change.", True),
    ("Write a narrative essay blending historical fiction with modern perspectives.", True),
    ("Analyze the dimensions of this problem across economic, social, and political factors.", True),
    ("Integrate these competing viewpoints into a coherent summary.", True),
    ("Plan a multi-step approach to solving this complex engineering problem.", True),
    # Factual/code tasks (should NOT enable interference)
    ("What is the capital of France?", False),
    ("Define photosynthesis.", False),
    ("Write a Python function to sort a list.", False),
    ("How many planets are in the solar system?", False),
    ("Implement a binary search tree in JavaScript.", False),
    ("What does the acronym SQL stand for?", False),
    ("Give me the code for a REST API endpoint.", False),
]


def run_interference_benchmarks(
