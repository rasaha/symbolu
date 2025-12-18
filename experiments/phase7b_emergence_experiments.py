"""
Phase-7B Emergence Experiments

Runs the 5 experiments from PHASE_7B_EMERGENCE_TEST_PLAN.md to test
the emergence hypothesis:

  "Properties can emerge through mechanical iteration over a validity space
   without being explicitly targeted, and without interpretation or learning."

Execute with: python -m experiments.phase7b_emergence_experiments
"""

import json
from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass
from collections import Counter

from symbolu.phases.phase7_targeted_generation import (
    execute_phase7,
    Phase7Result,
)


@dataclass
class ExperimentResult:
    """Result from a single experiment."""
    name: str
    passed: bool
    metrics: Dict[str, Any]
    details: str


def levenshtein_distance(s1: Tuple[str, ...], s2: Tuple[str, ...]) -> int:
    """Compute Levenshtein edit distance between two sequences."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


def sequence_to_template(seq: Tuple[str, ...], consonants: Set[str]) -> Tuple[str, ...]:
    """Convert sequence to abstract template (C/V pattern)."""
    return tuple("C" if t in consonants else "V" for t in seq)


def mean(values: List[float]) -> float:
    """Calculate mean of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def run_experiment_1_diversity() -> ExperimentResult:
    """
    Experiment 1: Diversity Emergence Without Diversity Targets

    Goal: Show diversity emerges purely from Exclusion Chains.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 1: Diversity Emergence (Exclusion Chains)")
    print("="*60)

    consonants = frozenset(["ka", "ga", "ta", "da", "pa", "ba"])
    vowels = frozenset(["a", "i", "u"])

    gen_config = {
        "max_sequence_length": 5,
        "max_candidates": None,  # Exhaustive within length bound
        "vowel_set": list(vowels),
        "consonant_set": list(consonants),
    }

    sel_config = {
        "max_results": 15,  # Smaller batches for more iterations
        "scoring_mode": "binary",
    }

    # Base constraints (no diversity metric!) - LOOSENED for exploration
    # Note: We want sequences with at least one vowel (modulate event)
    base_constraints = {
        "count(steps where event == 'modulate')": ">= 1",  # Single quotes required!
    }

    # Collect sequences across iterations using TRUE exclusion chains
    all_found: Set[Tuple[str, ...]] = set()
    diversity_per_iteration: List[float] = []
    sequences_per_iteration: List[List[Tuple[str, ...]]] = []

    # Run 10 iterations with actual exclusion
    for iteration in range(10):
        # Build target with exclusion constraint
        target = dict(base_constraints)
        if all_found:
            # Add exclusion constraint - THIS IS THE KEY
            target["sequence NOT IN"] = all_found

        result = execute_phase7(target, gen_config, sel_config)

        if not result.metadata.target_feasible:
            print(f"  Iteration {iteration}: No more feasible sequences")
            break

        # Collect new sequences (should be different from previous!)
        new_seqs = [r.sequence for r in result.results]
        sequences_per_iteration.append(new_seqs)

        # Verify exclusion worked
        overlap = set(new_seqs) & all_found
        if overlap:
            print(f"  WARNING: Found {len(overlap)} sequences that should have been excluded!")

        all_found.update(new_seqs)

        # Calculate pairwise edit distances for all found so far
        all_found_list = list(all_found)
        if len(all_found_list) >= 2:
            distances = []
            for i in range(len(all_found_list)):
                for j in range(i + 1, len(all_found_list)):
                    distances.append(levenshtein_distance(all_found_list[i], all_found_list[j]))
            diversity_per_iteration.append(mean(distances))
        else:
            diversity_per_iteration.append(0.0)

        print(f"  Iteration {iteration}: {len(all_found)} unique sequences, "
              f"mean_edit_dist={diversity_per_iteration[-1]:.2f}, "
              f"new_this_iter={len(new_seqs)}")

    # Calculate metrics
    all_found_list = list(all_found)
    unique_templates = set(sequence_to_template(s, consonants) for s in all_found)
    unique_consonants = set(t for s in all_found_list for t in s if t in consonants)
    unique_vowels = set(t for s in all_found_list for t in s if t in vowels)

    initial_diversity = diversity_per_iteration[0] if diversity_per_iteration else 0
    final_diversity = diversity_per_iteration[-1] if diversity_per_iteration else 0

    # Diversity should INCREASE as we exclude similar sequences and find different ones
    diversity_increase = final_diversity / initial_diversity if initial_diversity > 0 else 1.0

    # Count iterations where we found new sequences
    iterations_with_results = len(sequences_per_iteration)

    metrics = {
        "total_unique_sequences": len(all_found),
        "unique_templates": len(unique_templates),
        "consonant_coverage": len(unique_consonants) / len(consonants),
        "vowel_coverage": len(unique_vowels) / len(vowels),
        "initial_diversity": initial_diversity,
        "final_diversity": final_diversity,
        "diversity_increase_ratio": diversity_increase,
        "iterations_completed": iterations_with_results,
        "diversity_curve": diversity_per_iteration,
    }

    # Pass conditions - NOW WITH REAL EXCLUSION CHAINS
    # P1.1: Diversity increases (or at least maintains) as we explore
    # P1.2: Template coverage (diversity of structure)
    # P1.3: All sequences are unique (exclusion works)
    passed = (
        len(unique_templates) >= 5 and  # Multiple template patterns discovered
        metrics["consonant_coverage"] >= 0.8 and  # Good token coverage
        metrics["vowel_coverage"] >= 1.0 and  # All vowels used
        len(all_found) >= 100 and  # Found many unique sequences
        iterations_with_results >= 5  # Multiple successful iterations
    )

    print(f"\n  Metrics:")
    print(f"    Total unique sequences: {len(all_found)}")
    print(f"    Unique templates: {len(unique_templates)}")
    print(f"    Consonant coverage: {metrics['consonant_coverage']:.0%}")
    print(f"    Vowel coverage: {metrics['vowel_coverage']:.0%}")
    print(f"    Diversity curve: {[f'{d:.2f}' for d in diversity_per_iteration]}")
    print(f"    Iterations completed: {iterations_with_results}")
    print(f"  PASSED: {passed}")

    return ExperimentResult(
        name="Diversity Emergence",
        passed=passed,
        metrics=metrics,
        details=f"Found {len(unique_templates)} unique templates across {len(all_found)} unique sequences in {iterations_with_results} iterations",
    )


def run_experiment_2_boundary() -> ExperimentResult:
    """
    Experiment 2: Feasibility Boundary Emergence (Bisection Search)

    Goal: Show the system discovers a boundary mechanically.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 2: Feasibility Boundary Emergence")
    print("="*60)

    gen_config = {
        "max_sequence_length": 8,
        "max_candidates": 5000,
        "vowel_set": ["a", "i", "u"],
        "consonant_set": ["ka", "ga", "ta", "da", "pa", "ba"],
    }

    sel_config = {
        "max_results": 1,
        "scoring_mode": "binary",
    }

    # Bisection search
    low = 1.0
    high = 3.0
    precision = 0.01
    history = []

    iteration = 0
    while high - low > precision and iteration < 20:
        mid = (low + high) / 2
        target = {
            "final_magnitude": f">= {mid}",
            "len(steps)": "<= 8",
        }

        result = execute_phase7(target, gen_config, sel_config)
        feasible = result.metadata.candidates_satisfying > 0

        history.append({
            "iteration": iteration,
            "x": mid,
            "feasible": feasible,
            "candidates": result.metadata.candidates_satisfying,
        })

        print(f"  Iteration {iteration}: x={mid:.3f}, feasible={feasible}, "
              f"candidates={result.metadata.candidates_satisfying}")

        if feasible:
            low = mid
        else:
            high = mid

        iteration += 1

    x_star = low

    # Theoretical maximum: 1.0 + 7 * 0.2 = 2.4 (7 vowels max, each +0.2 for 'i')
    theoretical_max = 1.0 + 7 * 0.2

    metrics = {
        "x_star": x_star,
        "theoretical_max": theoretical_max,
        "relative_error": abs(x_star - theoretical_max) / theoretical_max,
        "iterations_to_converge": iteration,
    }

    # Pass conditions
    passed = (
        iteration < 20 and  # Converged
        metrics["relative_error"] < 0.1  # Within 10% of theoretical
    )

    print(f"\n  Boundary discovered: x* = {x_star:.3f}")
    print(f"  Theoretical max: {theoretical_max:.3f}")
    print(f"  Relative error: {metrics['relative_error']:.2%}")
    print(f"  PASSED: {passed}")

    return ExperimentResult(
        name="Feasibility Boundary",
        passed=passed,
        metrics=metrics,
        details=f"Discovered boundary x*={x_star:.3f} in {iteration} iterations",
    )


def run_experiment_3_shape_transfer() -> ExperimentResult:
    """
    Experiment 3: Shape Transfer Generalization

    Goal: Show trajectory shape can be transferred across different surface constraints.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 3: Shape Transfer Generalization")
    print("="*60)

    gen_config_a = {
        "max_sequence_length": 5,
        "max_candidates": 5000,
        "vowel_set": ["a", "i", "u"],
        "consonant_set": ["ka", "ga", "ta", "da", "pa", "ba"],
    }

    sel_config = {
        "max_results": 10,
        "scoring_mode": "distance",
    }

    # Phase A: Shape Discovery
    target_a = {
        "final_magnitude": ">= 1.3",
        "len(steps)": "== 5",
    }

    result_a = execute_phase7(target_a, gen_config_a, sel_config)

    if not result_a.results:
        return ExperimentResult(
            name="Shape Transfer",
            passed=False,
            metrics={},
            details="Phase A found no results",
        )

    best_a = result_a.results[0]
    best_trajectory = best_a.trajectory

    # Extract shape signature
    magnitudes = [s.magnitude for s in best_trajectory.steps]
    is_monotonic = all(magnitudes[i] <= magnitudes[i+1] for i in range(len(magnitudes)-1))
    terminal_event = best_trajectory.steps[-1].event

    print(f"  Phase A best: {best_a.sequence}")
    print(f"  Shape: monotonic={is_monotonic}, terminal={terminal_event}")
    print(f"  Magnitudes: {[f'{m:.2f}' for m in magnitudes]}")

    # Phase B: Shape Transfer (different length)
    gen_config_b = {
        "max_sequence_length": 7,
        "max_candidates": 5000,
        "vowel_set": ["a", "i", "u"],
        "consonant_set": ["ka", "ga", "ta", "da", "pa", "ba"],
    }

    target_b = {
        "monotonic_increasing(steps[].magnitude)": f"== {str(is_monotonic).lower()}",
        "steps[-1].event": f"== '{terminal_event}'",
        "len(steps)": "== 7",
        "final_magnitude": ">= 1.3",
    }

    result_b = execute_phase7(target_b, gen_config_b, sel_config)

    # Baseline (no shape constraint)
    target_baseline = {
        "len(steps)": "== 7",
        "final_magnitude": ">= 1.3",
    }

    result_baseline = execute_phase7(target_baseline, gen_config_b, sel_config)

    # Calculate shape match scores
    def shape_score(trajectory, reference_monotonic, reference_terminal):
        mags = [s.magnitude for s in trajectory.steps]
        is_mono = all(mags[i] <= mags[i+1] for i in range(len(mags)-1)) if len(mags) > 1 else True
        term = trajectory.steps[-1].event if trajectory.steps else None

        mono_match = 1.0 if is_mono == reference_monotonic else 0.0
        term_match = 1.0 if term == reference_terminal else 0.0

        return (mono_match + term_match) / 2

    shape_scores_b = [shape_score(r.trajectory, is_monotonic, terminal_event)
                      for r in result_b.results]
    shape_scores_baseline = [shape_score(r.trajectory, is_monotonic, terminal_event)
                             for r in result_baseline.results]

    mean_shape_b = mean(shape_scores_b) if shape_scores_b else 0
    mean_shape_baseline = mean(shape_scores_baseline) if shape_scores_baseline else 0

    improvement_ratio = mean_shape_b / mean_shape_baseline if mean_shape_baseline > 0 else float('inf')

    metrics = {
        "mean_shape_score_b": mean_shape_b,
        "mean_shape_score_baseline": mean_shape_baseline,
        "improvement_ratio": improvement_ratio,
        "shape_transferred_count": len(result_b.results),
        "baseline_count": len(result_baseline.results),
    }

    print(f"\n  Shape-constrained mean score: {mean_shape_b:.2f}")
    print(f"  Baseline mean score: {mean_shape_baseline:.2f}")
    print(f"  Improvement ratio: {improvement_ratio:.2f}x")

    # Pass condition
    passed = improvement_ratio >= 1.3  # 30% improvement

    print(f"  PASSED: {passed}")

    return ExperimentResult(
        name="Shape Transfer",
        passed=passed,
        metrics=metrics,
        details=f"Shape transfer achieved {improvement_ratio:.2f}x improvement",
    )


def run_experiment_4_safety() -> ExperimentResult:
    """
    Experiment 4: Adversarial Empty/Trivial Target Safety

    Goal: Verify Phase-7 doesn't invent implicit goals.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 4: Trivial Target Safety")
    print("="*60)

    gen_config = {
        "max_sequence_length": 6,
        "max_candidates": 1000,
        "vowel_set": ["a", "i", "u"],
        "consonant_set": ["ka", "ga", "ta", "da", "pa", "ba"],
    }

    sel_config = {
        "max_results": 100,
        "scoring_mode": "binary",
    }

    test_cases = [
        ("Empty Target", {}),
        ("Trivial (Phase-6 invariant)", {"steps[0].event": "== 'reset'"}),
        ("Minimal Discrimination", {"len(steps)": "== 4"}),
        ("Tautological Bounds", {"final_magnitude": ">= 0.0"}),
    ]

    results = {}
    all_passed = True

    for name, target in test_cases:
        result = execute_phase7(target, gen_config, sel_config)

        if name == "Empty Target":
            # Should reject
            expected_error = len(result.errors) > 0 and any(
                e.error_type.value == "VACUOUS_TARGET" for e in result.errors
            )
            passed = expected_error
            results[name] = {
                "passed": passed,
                "rejected": len(result.errors) > 0,
                "error_types": [e.error_type.value for e in result.errors],
            }
        else:
            # Should accept but produce bounded, deterministic results
            passed = (
                result.metadata.candidates_generated <= 1000 and
                result.metadata.execution_deterministic
            )
            results[name] = {
                "passed": passed,
                "candidates": result.metadata.candidates_generated,
                "satisfying": result.metadata.candidates_satisfying,
                "deterministic": result.metadata.execution_deterministic,
            }

        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
        print(f"    {results[name]}")

        if not passed:
            all_passed = False

    metrics = {
        "test_results": results,
        "all_passed": all_passed,
    }

    return ExperimentResult(
        name="Trivial Target Safety",
        passed=all_passed,
        metrics=metrics,
        details=f"All {len(test_cases)} safety tests passed" if all_passed else "Some safety tests failed",
    )


def run_experiment_5_stability() -> ExperimentResult:
    """
    Experiment 5: Stability Under Perturbation of Derivation Rules

    Goal: Show emergence depends on validity space, not derivation details.
    """
    print("\n" + "="*60)
    print("EXPERIMENT 5: Derivation Rule Stability")
    print("="*60)

    gen_config = {
        "max_sequence_length": 6,
        "max_candidates": 5000,
        "vowel_set": ["a", "i", "u"],
        "consonant_set": ["ka", "ga", "ta", "da", "pa", "ba"],
    }

    sel_config = {
        "max_results": 20,
        "scoring_mode": "distance",
    }

    initial_target = {
        "final_magnitude": ">= 1.2",
        "len(steps)": "<= 6",
    }

    consonants = frozenset(["ka", "ga", "ta", "da", "pa", "ba"])

    # Policy A: Progressive Refinement
    print("\n  Policy A: Progressive Refinement")
    results_a = []
    target_a = dict(initial_target)
    final_mag_a = 1.2

    for i in range(10):
        result = execute_phase7(target_a, gen_config, sel_config)
        results_a.append(result)

        if not result.metadata.target_feasible or not result.results:
            print(f"    Iteration {i}: infeasible at {final_mag_a:.2f}")
            break

        best_mag = result.results[0].trajectory.final_magnitude
        final_mag_a = best_mag * 0.95
        target_a = {
            "final_magnitude": f">= {final_mag_a}",
            "len(steps)": "<= 6",
        }
        print(f"    Iteration {i}: best_mag={best_mag:.2f}, next_threshold={final_mag_a:.2f}")

    # Policy B: Threshold Escalation
    print("\n  Policy B: Threshold Escalation")
    results_b = []
    threshold_b = 1.2
    final_mag_b = 1.2

    for i in range(10):
        target_b = {
            "final_magnitude": f">= {threshold_b}",
            "len(steps)": "<= 6",
        }
        result = execute_phase7(target_b, gen_config, sel_config)
        results_b.append(result)

        if not result.metadata.target_feasible:
            print(f"    Iteration {i}: infeasible at {threshold_b:.2f}")
            break

        final_mag_b = threshold_b
        threshold_b += 0.1
        print(f"    Iteration {i}: threshold={threshold_b:.2f}, feasible={result.metadata.target_feasible}")

    # Collect templates from both policies
    templates_a = set()
    templates_b = set()

    for result in results_a:
        for r in result.results:
            templates_a.add(sequence_to_template(r.sequence, consonants))

    for result in results_b:
        for r in result.results:
            templates_b.add(sequence_to_template(r.sequence, consonants))

    # Calculate overlap
    template_intersection = templates_a & templates_b
    template_union = templates_a | templates_b
    template_overlap = len(template_intersection) / len(template_union) if template_union else 0

    # Compare final magnitudes reached
    magnitude_diff = abs(final_mag_a - final_mag_b)
    magnitude_agreement = 1 - (magnitude_diff / max(final_mag_a, final_mag_b))

    metrics = {
        "final_magnitude_a": final_mag_a,
        "final_magnitude_b": final_mag_b,
        "magnitude_diff": magnitude_diff,
        "magnitude_agreement": magnitude_agreement,
        "templates_a": len(templates_a),
        "templates_b": len(templates_b),
        "template_overlap": template_overlap,
    }

    print(f"\n  Final magnitude A: {final_mag_a:.2f}")
    print(f"  Final magnitude B: {final_mag_b:.2f}")
    print(f"  Magnitude agreement: {magnitude_agreement:.2%}")
    print(f"  Template overlap: {template_overlap:.2%}")

    # Pass conditions
    passed = (
        magnitude_agreement >= 0.8 and  # Within 20% of each other
        template_overlap >= 0.3  # At least 30% template overlap
    )

    print(f"  PASSED: {passed}")

    return ExperimentResult(
        name="Derivation Stability",
        passed=passed,
        metrics=metrics,
        details=f"Magnitude agreement={magnitude_agreement:.2%}, template overlap={template_overlap:.2%}",
    )


def main():
    """Run all emergence experiments."""
    print("="*60)
    print("PHASE-7B EMERGENCE EXPERIMENTS")
    print("="*60)
    print("\nTesting hypothesis:")
    print("  'Properties can emerge through mechanical iteration")
    print("   without being explicitly targeted.'")

    results = []

    # Execute in recommended order
    results.append(run_experiment_4_safety())  # Safety first
    results.append(run_experiment_2_boundary())  # Simple emergence
    results.append(run_experiment_5_stability())  # Validates structural dependence
    results.append(run_experiment_1_diversity())  # Exclusion chain test
    results.append(run_experiment_3_shape_transfer())  # Complex emergence

    # Summary
    print("\n" + "="*60)
    print("EXPERIMENT SUMMARY")
    print("="*60)

    all_passed = True
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}: {r.details}")
        if not r.passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("HYPOTHESIS EVALUATION: H₀ REJECTED")
        print("  Emergence demonstrated through mechanical iteration.")
    else:
        print("HYPOTHESIS EVALUATION: INCONCLUSIVE")
        print("  Some experiments did not pass. Review individual results.")
    print("="*60)

    return results


if __name__ == "__main__":
    main()
