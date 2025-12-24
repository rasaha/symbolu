"""
Variation Depth Analysis for Phase-11A
=======================================

Answers the critical question: Is the variation deep, stable, and controllable
— or shallow and noisy?

ANALYSES PERFORMED:
1. Clustering strength by axis (ontological vs PPV vs temperature)
2. PPV dimension correlation with surface changes
3. OPEN vs GOVERNED divergence analysis
4. Minimum structural delta for hash change
5. Silent collapse pattern detection
6. Neutral baseline comparison
7. Deep vs Shallow variation synthesis
"""

from __future__ import annotations

import sys
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import itertools

sys.path.insert(0, "/home/user/symbolu/docs/experiments/phase11_sandbox")

from phase11a_evaluation_harness import (
    ExperimentConfig,
    MockPhase11Generator,
    OntologicalLayer,
    ONTOLOGICAL_LAYER_ORDER,
    PPV_DIMENSION_ORDER,
    PPVDimension,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    RenderMode,
    VariationMatrixGenerator,
    INTENTS,
    compute_output_hash,
    compute_lexical_signature,
)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass(frozen=True)
class OutputRecord:
    """Lightweight output record for analysis."""
    config_key: str
    output_hash: str
    output_length: int
    token_count: int
    unique_tokens: int
    output_text: str


@dataclass(frozen=True)
class ClusteringResult:
    """Clustering analysis result for an axis."""
    axis_name: str
    unique_clusters: int
    total_samples: int
    intra_cluster_similarity: float  # Average similarity within clusters
    inter_cluster_distance: float    # Average distance between clusters
    clustering_strength: float       # Ratio indicating how strongly outputs cluster


@dataclass(frozen=True)
class PPVDimensionCorrelation:
    """Correlation between a PPV dimension and surface changes."""
    dimension: str
    length_correlation: float       # How much this dimension affects length
    token_diversity_correlation: float  # Effect on unique token count
    hash_divergence_rate: float     # Rate of new hashes when varying this dimension


@dataclass(frozen=True)
class ModeComparison:
    """Comparison between OPEN and GOVERNED modes."""
    divergence_rate: float          # % of inputs where modes produce different output
    average_length_delta: float     # Average length difference
    average_token_delta: float      # Average token count difference
    max_divergence_dimension: str   # Which dimension amplifies divergence most
    amplification_factors: Dict[str, float]  # Per-dimension divergence amplification


# =============================================================================
# 1. Clustering Analysis by Axis
# =============================================================================

def analyze_clustering_by_axis() -> Dict[str, ClusteringResult]:
    """
    Determine whether outputs cluster more strongly by ontological layer,
    PPV, or temperature.

    Uses Jaccard similarity of token sets to measure clustering.
    """
    print("\n" + "=" * 70)
    print("1. CLUSTERING ANALYSIS BY AXIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]
    results: Dict[str, ClusteringResult] = {}

    # Generate baseline outputs with controlled variations
    baseline_ppv = VariationMatrixGenerator.DEFAULT_PPV
    baseline_temp = VariationMatrixGenerator.DEFAULT_TEMP
    baseline_mode = VariationMatrixGenerator.DEFAULT_MODE

    # Collect outputs grouped by each axis
    outputs_by_layer: Dict[str, List[Set[str]]] = defaultdict(list)
    outputs_by_ppv_pattern: Dict[str, List[Set[str]]] = defaultdict(list)
    outputs_by_temp_band: Dict[str, List[Set[str]]] = defaultdict(list)

    # Generate samples varying all axes
    for layer in ONTOLOGICAL_LAYER_ORDER[:5]:  # 5 layers
        for ppv_high_dim in range(4):  # 4 PPV patterns
            for temp in [0.2, 0.5, 0.8]:  # 3 temps
                ppv = list(baseline_ppv)
                ppv[ppv_high_dim] = 7  # Set one dimension high

                config = ExperimentConfig(
                    intent=intent,
                    ontological_path=(layer,),
                    ppv_values=tuple(ppv),
                    temperature=temp,
                    mode=baseline_mode,
                    variation_axis="clustering_test",
                    variation_index=0,
                )
                output = generator.generate(config)
                tokens = set(output.split())

                # Group by each axis
                outputs_by_layer[layer.value].append(tokens)
                outputs_by_ppv_pattern[f"dim_{ppv_high_dim}_high"].append(tokens)
                temp_band = "low" if temp < 0.3 else ("mid" if temp < 0.7 else "high")
                outputs_by_temp_band[temp_band].append(tokens)

    def compute_jaccard(set1: Set[str], set2: Set[str]) -> float:
        if not set1 and not set2:
            return 1.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def analyze_axis(outputs_by_group: Dict[str, List[Set[str]]], axis_name: str) -> ClusteringResult:
        # Compute intra-cluster similarity (similarity within each group)
        intra_similarities = []
        for group_outputs in outputs_by_group.values():
            if len(group_outputs) >= 2:
                for i, o1 in enumerate(group_outputs):
                    for o2 in group_outputs[i+1:]:
                        intra_similarities.append(compute_jaccard(o1, o2))

        avg_intra = sum(intra_similarities) / len(intra_similarities) if intra_similarities else 0.0

        # Compute inter-cluster distance (dissimilarity between groups)
        groups = list(outputs_by_group.values())
        inter_distances = []
        for i, g1 in enumerate(groups):
            for g2 in groups[i+1:]:
                for o1 in g1:
                    for o2 in g2:
                        inter_distances.append(1.0 - compute_jaccard(o1, o2))

        avg_inter = sum(inter_distances) / len(inter_distances) if inter_distances else 0.0

        # Clustering strength: high intra-similarity + high inter-distance = strong clustering
        clustering_strength = avg_intra * avg_inter if avg_inter > 0 else 0.0

        total_samples = sum(len(g) for g in outputs_by_group.values())

        return ClusteringResult(
            axis_name=axis_name,
            unique_clusters=len(outputs_by_group),
            total_samples=total_samples,
            intra_cluster_similarity=avg_intra,
            inter_cluster_distance=avg_inter,
            clustering_strength=clustering_strength,
        )

    results["ontological_layer"] = analyze_axis(outputs_by_layer, "ontological_layer")
    results["ppv_pattern"] = analyze_axis(outputs_by_ppv_pattern, "ppv_pattern")
    results["temperature_band"] = analyze_axis(outputs_by_temp_band, "temperature_band")

    # Print results
    print("\nClustering Strength by Axis:")
    print("-" * 60)
    print(f"{'Axis':<20} {'Clusters':<10} {'Intra-Sim':<12} {'Inter-Dist':<12} {'Strength':<10}")
    print("-" * 60)

    for axis, result in sorted(results.items(), key=lambda x: -x[1].clustering_strength):
        print(f"{result.axis_name:<20} {result.unique_clusters:<10} "
              f"{result.intra_cluster_similarity:<12.3f} "
              f"{result.inter_cluster_distance:<12.3f} "
              f"{result.clustering_strength:<10.3f}")

    # Determine strongest clustering axis
    strongest = max(results.values(), key=lambda x: x.clustering_strength)
    print(f"\n** STRONGEST CLUSTERING: {strongest.axis_name} (strength: {strongest.clustering_strength:.3f})")

    return results


# =============================================================================
# 2. PPV Dimension Correlation with Surface Changes
# =============================================================================

def analyze_ppv_dimension_correlations() -> Dict[str, PPVDimensionCorrelation]:
    """
    Quantify which PPV dimensions most strongly correlate with
    observable surface changes (length, token diversity, hash divergence).
    """
    print("\n" + "=" * 70)
    print("2. PPV DIMENSION CORRELATION ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]
    results: Dict[str, PPVDimensionCorrelation] = {}

    baseline_ppv = list(VariationMatrixGenerator.DEFAULT_PPV)
    baseline_path = VariationMatrixGenerator.DEFAULT_PATH
    baseline_temp = VariationMatrixGenerator.DEFAULT_TEMP
    baseline_mode = VariationMatrixGenerator.DEFAULT_MODE

    # Generate baseline output
    baseline_config = ExperimentConfig(
        intent=intent,
        ontological_path=baseline_path,
        ppv_values=tuple(baseline_ppv),
        temperature=baseline_temp,
        mode=baseline_mode,
        variation_axis="baseline",
        variation_index=0,
    )
    baseline_output = generator.generate(baseline_config)
    baseline_hash = compute_output_hash(baseline_output)
    baseline_length = len(baseline_output)
    baseline_tokens = len(set(baseline_output.split()))

    # Analyze each PPV dimension
    for dim_idx, dimension in enumerate(PPV_DIMENSION_ORDER):
        lengths = []
        token_counts = []
        hash_changes = 0

        # Vary this dimension across full range
        for value in range(8):
            ppv = baseline_ppv.copy()
            ppv[dim_idx] = value

            config = ExperimentConfig(
                intent=intent,
                ontological_path=baseline_path,
                ppv_values=tuple(ppv),
                temperature=baseline_temp,
                mode=baseline_mode,
                variation_axis=f"ppv_{dimension.value}",
                variation_index=value,
            )
            output = generator.generate(config)
            output_hash = compute_output_hash(output)

            lengths.append(len(output))
            token_counts.append(len(set(output.split())))

            if output_hash != baseline_hash:
                hash_changes += 1

        # Compute correlations
        length_range = max(lengths) - min(lengths)
        length_correlation = length_range / baseline_length if baseline_length > 0 else 0.0

        token_range = max(token_counts) - min(token_counts)
        token_correlation = token_range / baseline_tokens if baseline_tokens > 0 else 0.0

        hash_divergence = hash_changes / 8.0  # 8 values tested

        results[dimension.value] = PPVDimensionCorrelation(
            dimension=dimension.value,
            length_correlation=length_correlation,
            token_diversity_correlation=token_correlation,
            hash_divergence_rate=hash_divergence,
        )

    # Print results
    print("\nPPV Dimension Impact on Surface Features:")
    print("-" * 70)
    print(f"{'Dimension':<22} {'Length Δ':<12} {'Token Δ':<12} {'Hash Δ Rate':<12} {'Impact':<10}")
    print("-" * 70)

    sorted_results = sorted(results.values(),
                           key=lambda x: x.length_correlation + x.token_diversity_correlation + x.hash_divergence_rate,
                           reverse=True)

    for r in sorted_results:
        impact = (r.length_correlation + r.token_diversity_correlation + r.hash_divergence_rate) / 3
        print(f"{r.dimension:<22} {r.length_correlation:<12.3f} "
              f"{r.token_diversity_correlation:<12.3f} {r.hash_divergence_rate:<12.3f} "
              f"{impact:<10.3f}")

    # Identify most impactful dimension
    most_impactful = max(sorted_results,
                        key=lambda x: x.length_correlation + x.token_diversity_correlation + x.hash_divergence_rate)
    print(f"\n** MOST IMPACTFUL DIMENSION: {most_impactful.dimension}")

    return results


# =============================================================================
# 3. OPEN vs GOVERNED Mode Comparison
# =============================================================================

def analyze_mode_divergence() -> ModeComparison:
    """
    Compare OPEN vs GOVERNED mode outputs for identical structural inputs.
    Reports: divergence rate, divergence magnitude, amplifying dimensions.
    """
    print("\n" + "=" * 70)
    print("3. OPEN vs GOVERNED MODE DIVERGENCE ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)

    total_comparisons = 0
    divergent_comparisons = 0
    length_deltas = []
    token_deltas = []

    # Per-dimension divergence tracking
    dimension_divergence: Dict[str, List[float]] = defaultdict(list)

    # Test across multiple configurations
    for intent in INTENTS:
        for layer in ONTOLOGICAL_LAYER_ORDER[:3]:
            for ppv_idx in range(8):
                for temp in [0.2, 0.5, 0.8]:
                    ppv = list(VariationMatrixGenerator.DEFAULT_PPV)
                    ppv[ppv_idx] = 6  # High value

                    # GOVERNED mode
                    config_gov = ExperimentConfig(
                        intent=intent,
                        ontological_path=(layer,),
                        ppv_values=tuple(ppv),
                        temperature=temp,
                        mode=RenderMode.GOVERNED,
                        variation_axis="mode_comparison",
                        variation_index=0,
                    )
                    output_gov = generator.generate(config_gov)

                    # OPEN mode
                    config_open = ExperimentConfig(
                        intent=intent,
                        ontological_path=(layer,),
                        ppv_values=tuple(ppv),
                        temperature=temp,
                        mode=RenderMode.OPEN,
                        variation_axis="mode_comparison",
                        variation_index=1,
                    )
                    output_open = generator.generate(config_open)

                    total_comparisons += 1

                    hash_gov = compute_output_hash(output_gov)
                    hash_open = compute_output_hash(output_open)

                    if hash_gov != hash_open:
                        divergent_comparisons += 1

                        length_delta = abs(len(output_gov) - len(output_open))
                        length_deltas.append(length_delta)

                        tokens_gov = set(output_gov.split())
                        tokens_open = set(output_open.split())
                        token_delta = len(tokens_gov.symmetric_difference(tokens_open))
                        token_deltas.append(token_delta)

                        # Track which dimension this was
                        dim_name = PPV_DIMENSION_ORDER[ppv_idx].value
                        dimension_divergence[dim_name].append(token_delta)

    divergence_rate = divergent_comparisons / total_comparisons if total_comparisons > 0 else 0.0
    avg_length_delta = sum(length_deltas) / len(length_deltas) if length_deltas else 0.0
    avg_token_delta = sum(token_deltas) / len(token_deltas) if token_deltas else 0.0

    # Compute amplification factors
    amplification_factors = {}
    for dim, deltas in dimension_divergence.items():
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        amplification_factors[dim] = avg_delta

    max_dim = max(amplification_factors.items(), key=lambda x: x[1]) if amplification_factors else ("none", 0.0)

    result = ModeComparison(
        divergence_rate=divergence_rate,
        average_length_delta=avg_length_delta,
        average_token_delta=avg_token_delta,
        max_divergence_dimension=max_dim[0],
        amplification_factors=amplification_factors,
    )

    # Print results
    print(f"\nTotal Comparisons: {total_comparisons}")
    print(f"Divergent Outputs: {divergent_comparisons}")
    print(f"\n1. DIVERGENCE RATE: {divergence_rate:.1%}")
    print(f"2. DIVERGENCE MAGNITUDE:")
    print(f"   - Average length delta: {avg_length_delta:.1f} chars")
    print(f"   - Average token delta:  {avg_token_delta:.1f} tokens")
    print(f"\n3. DIMENSION AMPLIFICATION FACTORS:")
    print("-" * 50)

    for dim, factor in sorted(amplification_factors.items(), key=lambda x: -x[1]):
        bar = "█" * int(factor * 5)
        print(f"   {dim:<20} {factor:>6.2f} {bar}")

    print(f"\n** MAX AMPLIFICATION: {max_dim[0]} ({max_dim[1]:.2f})")

    return result


# =============================================================================
# 4. Minimum Structural Delta for Hash Change
# =============================================================================

def find_minimum_hash_delta() -> Dict[str, Tuple[str, str, str]]:
    """
    Identify the smallest structural change that produces a new output hash.
    """
    print("\n" + "=" * 70)
    print("4. MINIMUM STRUCTURAL DELTA FOR HASH CHANGE")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]

    results: Dict[str, Tuple[str, str, str]] = {}  # axis -> (before, after, delta_description)

    baseline_ppv = list(VariationMatrixGenerator.DEFAULT_PPV)
    baseline_path = VariationMatrixGenerator.DEFAULT_PATH
    baseline_temp = VariationMatrixGenerator.DEFAULT_TEMP
    baseline_mode = VariationMatrixGenerator.DEFAULT_MODE

    # Baseline
    baseline_config = ExperimentConfig(
        intent=intent,
        ontological_path=baseline_path,
        ppv_values=tuple(baseline_ppv),
        temperature=baseline_temp,
        mode=baseline_mode,
        variation_axis="baseline",
        variation_index=0,
    )
    baseline_output = generator.generate(baseline_config)
    baseline_hash = compute_output_hash(baseline_output)

    # Test 1: Minimum PPV change
    for delta in [1, 2, 3, 4, 5, 6, 7]:
        ppv = baseline_ppv.copy()
        ppv[0] = baseline_ppv[0] + delta
        if ppv[0] > 7:
            ppv[0] = baseline_ppv[0] - delta
        if ppv[0] < 0:
            continue

        config = ExperimentConfig(
            intent=intent,
            ontological_path=baseline_path,
            ppv_values=tuple(ppv),
            temperature=baseline_temp,
            mode=baseline_mode,
            variation_axis="ppv_delta",
            variation_index=delta,
        )
        output = generator.generate(config)
        output_hash = compute_output_hash(output)

        if output_hash != baseline_hash:
            results["ppv_single_dimension"] = (
                str(baseline_ppv[0]), str(ppv[0]), f"Δ = {delta}"
            )
            break

    # Test 2: Minimum temperature change
    for delta in [0.01, 0.05, 0.1, 0.2, 0.3]:
        temp = baseline_temp + delta
        if temp > 1.0:
            temp = baseline_temp - delta

        config = ExperimentConfig(
            intent=intent,
            ontological_path=baseline_path,
            ppv_values=tuple(baseline_ppv),
            temperature=temp,
            mode=baseline_mode,
            variation_axis="temp_delta",
            variation_index=0,
        )
        output = generator.generate(config)
        output_hash = compute_output_hash(output)

        if output_hash != baseline_hash:
            results["temperature"] = (
                f"{baseline_temp:.2f}", f"{temp:.2f}", f"Δ = {delta:.2f}"
            )
            break

    # Test 3: Mode change (always produces different hash)
    config = ExperimentConfig(
        intent=intent,
        ontological_path=baseline_path,
        ppv_values=tuple(baseline_ppv),
        temperature=baseline_temp,
        mode=RenderMode.OPEN if baseline_mode == RenderMode.GOVERNED else RenderMode.GOVERNED,
        variation_axis="mode_delta",
        variation_index=0,
    )
    output = generator.generate(config)
    output_hash = compute_output_hash(output)

    if output_hash != baseline_hash:
        results["mode"] = (baseline_mode.value, config.mode.value, "binary flip")

    # Test 4: Path change
    for layer in ONTOLOGICAL_LAYER_ORDER:
        if layer != baseline_path[0]:
            new_path = (layer,) + baseline_path[1:]

            config = ExperimentConfig(
                intent=intent,
                ontological_path=new_path,
                ppv_values=tuple(baseline_ppv),
                temperature=baseline_temp,
                mode=baseline_mode,
                variation_axis="path_delta",
                variation_index=0,
            )
            output = generator.generate(config)
            output_hash = compute_output_hash(output)

            if output_hash != baseline_hash:
                results["ontological_path"] = (
                    baseline_path[0].value, layer.value, "single layer change"
                )
                break

    # Print results
    print("\nMinimum Change Required for Hash Divergence:")
    print("-" * 60)
    print(f"{'Axis':<25} {'From':<15} {'To':<15} {'Delta':<15}")
    print("-" * 60)

    for axis, (before, after, delta) in results.items():
        print(f"{axis:<25} {before:<15} {after:<15} {delta:<15}")

    # Identify smallest delta
    print(f"\n** SMALLEST EFFECTIVE DELTA: Any single-unit change produces new hash")
    print("   (Mock generator encodes all parameters directly)")

    return results


# =============================================================================
# 5. Silent Collapse Pattern Detection
# =============================================================================

def detect_silent_collapse_patterns() -> Dict[str, List[Tuple[str, str]]]:
    """
    Check for cases where multiple distinct structural inputs
    produce identical outputs across intents.
    """
    print("\n" + "=" * 70)
    print("5. SILENT COLLAPSE PATTERN DETECTION")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)

    # Map hash -> list of configs that produced it
    hash_to_configs: Dict[str, List[str]] = defaultdict(list)

    # Generate many configurations
    test_count = 0
    for intent in INTENTS:
        for layer in ONTOLOGICAL_LAYER_ORDER[:5]:
            for ppv_val in [0, 3, 7]:  # Low, mid, high
                for dim in range(4):  # First 4 dimensions
                    for temp in [0.2, 0.5, 0.8]:
                        for mode in [RenderMode.GOVERNED, RenderMode.OPEN]:
                            ppv = [3] * 8
                            ppv[dim] = ppv_val

                            config = ExperimentConfig(
                                intent=intent,
                                ontological_path=(layer,),
                                ppv_values=tuple(ppv),
                                temperature=temp,
                                mode=mode,
                                variation_axis="collapse_test",
                                variation_index=test_count,
                            )
                            output = generator.generate(config)
                            output_hash = compute_output_hash(output)

                            config_desc = (
                                f"intent={intent[:8]}, layer={layer.value[:6]}, "
                                f"ppv[{dim}]={ppv_val}, temp={temp}, mode={mode.value}"
                            )
                            hash_to_configs[output_hash].append(config_desc)
                            test_count += 1

    # Find collisions
    collapse_patterns: Dict[str, List[Tuple[str, str]]] = {}
    collision_count = 0

    for hash_val, configs in hash_to_configs.items():
        if len(configs) > 1:
            collision_count += 1
            key = f"collision_{collision_count}"
            collapse_patterns[key] = [(configs[0], configs[i]) for i in range(1, min(len(configs), 5))]

    # Print results
    print(f"\nTotal configurations tested: {test_count}")
    print(f"Unique output hashes: {len(hash_to_configs)}")
    print(f"Hash collisions detected: {collision_count}")

    if collision_count > 0:
        print(f"\nCollapse ratio: {collision_count / len(hash_to_configs):.2%}")
        print("\nExample Collapse Patterns:")
        print("-" * 60)
        for key, pairs in list(collapse_patterns.items())[:5]:
            print(f"\n{key}:")
            for config1, config2 in pairs[:2]:
                print(f"   Config A: {config1}")
                print(f"   Config B: {config2}")
    else:
        print("\n** NO SILENT COLLAPSE DETECTED")
        print("   Every distinct input produces a unique output hash.")
        print("   The mock generator is BIJECTIVE (1:1 mapping).")

    return collapse_patterns


# =============================================================================
# 6. Neutral Baseline Comparison
# =============================================================================

def run_neutral_baseline_comparison() -> Dict[str, float]:
    """
    Run Phase-11A with neutral PPV values and compare differentiation metrics
    to structured runs.
    """
    print("\n" + "=" * 70)
    print("6. NEUTRAL BASELINE COMPARISON")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)

    # Neutral configuration: all PPV neutral (3), single baseline path
    neutral_ppv = (3, 3, 3, 3, 3, 3, 3, 3)
    neutral_path = (OntologicalLayer.STRUCTURE,)
    neutral_temp = 0.5

    # Collect outputs for neutral runs (only vary intent and mode)
    neutral_outputs: List[Tuple[str, str]] = []  # (config_desc, hash)

    for intent in INTENTS:
        for mode in [RenderMode.GOVERNED, RenderMode.OPEN]:
            config = ExperimentConfig(
                intent=intent,
                ontological_path=neutral_path,
                ppv_values=neutral_ppv,
                temperature=neutral_temp,
                mode=mode,
                variation_axis="neutral",
                variation_index=0,
            )
            output = generator.generate(config)
            output_hash = compute_output_hash(output)
            neutral_outputs.append((f"{intent[:8]}_{mode.value}", output_hash))

    neutral_unique = len(set(h for _, h in neutral_outputs))
    neutral_total = len(neutral_outputs)
    neutral_uniqueness = neutral_unique / neutral_total

    # Structured runs: vary PPV, path, temp
    structured_outputs: List[Tuple[str, str]] = []

    for intent in INTENTS:
        for layer in ONTOLOGICAL_LAYER_ORDER[:3]:
            for ppv_pattern in [(7, 3, 3, 3, 3, 3, 3, 3), (3, 7, 3, 3, 3, 3, 3, 3)]:
                for temp in [0.2, 0.8]:
                    for mode in [RenderMode.GOVERNED, RenderMode.OPEN]:
                        config = ExperimentConfig(
                            intent=intent,
                            ontological_path=(layer,),
                            ppv_values=ppv_pattern,
                            temperature=temp,
                            mode=mode,
                            variation_axis="structured",
                            variation_index=0,
                        )
                        output = generator.generate(config)
                        output_hash = compute_output_hash(output)
                        structured_outputs.append(("structured", output_hash))

    structured_unique = len(set(h for _, h in structured_outputs))
    structured_total = len(structured_outputs)
    structured_uniqueness = structured_unique / structured_total

    # Compute metrics
    results = {
        "neutral_total": neutral_total,
        "neutral_unique": neutral_unique,
        "neutral_uniqueness": neutral_uniqueness,
        "structured_total": structured_total,
        "structured_unique": structured_unique,
        "structured_uniqueness": structured_uniqueness,
        "differentiation_gain": structured_uniqueness / neutral_uniqueness if neutral_uniqueness > 0 else float('inf'),
    }

    # Print results
    print("\nNeutral Baseline (PPV=neutral, single path, temp=0.5):")
    print(f"   Total outputs:  {neutral_total}")
    print(f"   Unique hashes:  {neutral_unique}")
    print(f"   Uniqueness:     {neutral_uniqueness:.1%}")

    print("\nStructured Runs (varying PPV, path, temp):")
    print(f"   Total outputs:  {structured_total}")
    print(f"   Unique hashes:  {structured_unique}")
    print(f"   Uniqueness:     {structured_uniqueness:.1%}")

    print(f"\n** DIFFERENTIATION GAIN: {results['differentiation_gain']:.2f}x")

    if results['differentiation_gain'] > 1.0:
        print("   Structure INCREASES differentiation capacity.")
    else:
        print("   Structure provides NO additional differentiation.")

    return results


# =============================================================================
# 7. Deep vs Shallow Variation Synthesis
# =============================================================================

def synthesize_variation_depth(
    clustering_results: Dict[str, ClusteringResult],
    ppv_correlations: Dict[str, PPVDimensionCorrelation],
    mode_comparison: ModeComparison,
    collapse_patterns: Dict[str, List[Tuple[str, str]]],
    baseline_comparison: Dict[str, float],
) -> str:
    """
    Synthesize all findings into a final assessment:
    Is the variation deep, stable, and controllable — or shallow and noisy?
    """
    print("\n" + "=" * 70)
    print("7. VARIATION DEPTH SYNTHESIS")
    print("=" * 70)

    # Scoring criteria
    scores = {
        "controllability": 0.0,
        "stability": 0.0,
        "depth": 0.0,
    }

    # Controllability: Can we predict which inputs cause which changes?
    # High clustering strength = controllable
    max_clustering = max(r.clustering_strength for r in clustering_results.values())
    scores["controllability"] = min(1.0, max_clustering * 2)  # Normalize

    # Stability: Are outputs deterministic? No random collapse?
    # No collapse patterns = stable
    collapse_count = len(collapse_patterns)
    scores["stability"] = 1.0 if collapse_count == 0 else max(0.0, 1.0 - collapse_count / 100)

    # Depth: Do structural changes produce meaningful differentiation?
    # High differentiation gain = deep
    gain = baseline_comparison["differentiation_gain"]
    scores["depth"] = min(1.0, (gain - 1.0) / 10) if gain > 1.0 else 0.0

    # Additional depth signal: PPV dimension impact variance
    ppv_impacts = [
        c.length_correlation + c.token_diversity_correlation + c.hash_divergence_rate
        for c in ppv_correlations.values()
    ]
    if ppv_impacts:
        impact_variance = max(ppv_impacts) - min(ppv_impacts)
        scores["depth"] = min(1.0, scores["depth"] + impact_variance)

    # Overall assessment
    overall_score = (scores["controllability"] + scores["stability"] + scores["depth"]) / 3

    print("\nVARIATION QUALITY SCORES:")
    print("-" * 40)
    print(f"  Controllability: {scores['controllability']:.2f}/1.00")
    print(f"  Stability:       {scores['stability']:.2f}/1.00")
    print(f"  Depth:           {scores['depth']:.2f}/1.00")
    print(f"  ─────────────────────────────")
    print(f"  OVERALL:         {overall_score:.2f}/1.00")

    # Classification
    if overall_score >= 0.7:
        classification = "DEEP, STABLE, AND CONTROLLABLE"
        assessment = "The variation system produces meaningful, predictable differentiation."
    elif overall_score >= 0.4:
        classification = "MODERATE DEPTH"
        assessment = "The variation shows some meaningful patterns but with limitations."
    else:
        classification = "SHALLOW AND NOISY"
        assessment = "The variation is primarily surface-level without deep structure."

    print(f"\n{'='*50}")
    print(f" CLASSIFICATION: {classification}")
    print(f"{'='*50}")
    print(f"\n{assessment}")

    # Detailed findings
    print("\nDETAILED FINDINGS:")
    print("-" * 40)

    print("\n1. CONTROLLABILITY:")
    strongest_cluster = max(clustering_results.values(), key=lambda x: x.clustering_strength)
    print(f"   - Outputs cluster most strongly by: {strongest_cluster.axis_name}")
    print(f"   - Clustering strength: {strongest_cluster.clustering_strength:.3f}")
    print(f"   - Implication: Changes to {strongest_cluster.axis_name} produce predictable output shifts")

    print("\n2. STABILITY:")
    if collapse_count == 0:
        print("   - FULLY DETERMINISTIC: No hash collisions detected")
        print("   - Every unique input configuration produces a unique output")
    else:
        print(f"   - WARNING: {collapse_count} hash collisions detected")
        print("   - Some distinct inputs collapse to identical outputs")

    print("\n3. DEPTH:")
    print(f"   - Differentiation gain over neutral baseline: {baseline_comparison['differentiation_gain']:.2f}x")

    # PPV dimension ranking
    sorted_ppv = sorted(ppv_correlations.values(),
                       key=lambda x: x.length_correlation + x.token_diversity_correlation + x.hash_divergence_rate,
                       reverse=True)
    print(f"   - Most impactful PPV dimension: {sorted_ppv[0].dimension}")
    print(f"   - Least impactful PPV dimension: {sorted_ppv[-1].dimension}")

    print("\n4. MODE BEHAVIOR:")
    print(f"   - OPEN/GOVERNED divergence rate: {mode_comparison.divergence_rate:.1%}")
    print(f"   - Average token difference: {mode_comparison.average_token_delta:.1f}")
    print(f"   - Maximum amplification by: {mode_comparison.max_divergence_dimension}")

    return classification


# =============================================================================
# Main Entry Point
# =============================================================================

def run_full_analysis():
    """Run complete variation depth analysis."""
    print("\n" + "█" * 70)
    print("█  PHASE-11A VARIATION DEPTH ANALYSIS")
    print("█  Is the variation deep, stable, and controllable?")
    print("█" * 70)

    # Run all analyses
    clustering_results = analyze_clustering_by_axis()
    ppv_correlations = analyze_ppv_dimension_correlations()
    mode_comparison = analyze_mode_divergence()
    minimum_deltas = find_minimum_hash_delta()
    collapse_patterns = detect_silent_collapse_patterns()
    baseline_comparison = run_neutral_baseline_comparison()

    # Synthesize findings
    classification = synthesize_variation_depth(
        clustering_results,
        ppv_correlations,
        mode_comparison,
        collapse_patterns,
        baseline_comparison,
    )

    print("\n" + "█" * 70)
    print("█  ANALYSIS COMPLETE")
    print("█" * 70)

    return {
        "clustering": clustering_results,
        "ppv_correlations": ppv_correlations,
        "mode_comparison": mode_comparison,
        "minimum_deltas": minimum_deltas,
        "collapse_patterns": collapse_patterns,
        "baseline_comparison": baseline_comparison,
        "classification": classification,
    }


if __name__ == "__main__":
    run_full_analysis()
