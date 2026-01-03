"""
Phase-11B Structural Analysis Harness
=====================================

This module performs comprehensive structural analysis of Phase-11B to answer:

1. Structural Ceiling: At what point do additional PPV/ontological variations
   stop producing new output hashes?
2. Clustering Analysis: Do outputs cluster by ontological layer more strongly
   than by PPV or temperature?
3. PPV Dimension Correlation: Which PPV dimensions most strongly correlate
   with observable surface changes?
4. OPEN vs GOVERNED Divergence: Divergence rate, magnitude, amplifying dimensions
5. Minimum Change Detection: Smallest structural change producing new hash
6. Silent Collapse Detection: Multiple distinct inputs → identical outputs
7. Neutral Baseline: Phase-11B with neutral PPV vs structured runs

METHODOLOGY:
- No semantics - purely structural/mechanical analysis
- Deterministic - reproducible results
- Hash-based differentiation metrics
- Clustering by Jaccard similarity of hash prefixes
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from itertools import product, combinations

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    Phase10Result,
    RenderMode,
    compute_hash,
)
from symbolu.mechanical.pipeline.p11b_controller.p11b_schema import (
    OntologicalFamily,
    PPVBand,
    PPVBandSignature,
    RegistryType,
    SlotPlan,
    TemplateKey,
    Phase11BRequest,
    Phase11BResponse,
    LAYER_TO_FAMILY,
    PPV_DIM_NAMES,
    create_ppv_band_signature,
    compute_variant_id,
    get_template_family,
    get_slot_plan_from_ppv,
)
from symbolu.mechanical.pipeline.p11b_controller.p11b_controller import (
    Phase11BController,
    run_phase11b_controller,
)
from symbolu.mechanical.pipeline.p11b_controller.p11b_templates import (
    get_registry,
    get_registry_stats,
    validate_no_silent_collapse,
)


# =============================================================================
# Test Data Generation
# =============================================================================

ALL_ONTOLOGICAL_PATHS = [
    ("ACTING",), ("TAGGING",), ("FORMING",), ("THINKING",),
    ("DIRECTING",), ("REASONING",), ("PURPOSING",),
    ("META_OBSERVING",), ("UNIFYING",), ("ABSOLVING",),
]

# Representative PPV vectors
PPV_VARIANTS = {
    "all_low": (0, 0, 0, 0, 0, 0, 0, 0),
    "all_mid": (4, 4, 4, 4, 4, 4, 4, 4),
    "all_high": (7, 7, 7, 7, 7, 7, 7, 7),
    "neutral": (3, 3, 3, 3, 3, 3, 3, 3),  # All at band boundary
    "gradient_up": (0, 1, 2, 3, 4, 5, 6, 7),
    "gradient_down": (7, 6, 5, 4, 3, 2, 1, 0),
    "stability_high": (7, 0, 0, 0, 0, 0, 0, 7),  # High stability_pressure, edge_tension
    "discontinuity_high": (0, 0, 0, 0, 0, 7, 0, 0),  # High discontinuity only
    "continuity_high": (0, 0, 0, 0, 7, 0, 0, 0),  # High continuity only
    "sonority_high": (0, 0, 0, 7, 0, 0, 0, 0),  # High sonority only
    "onset_high": (0, 0, 7, 0, 0, 0, 0, 0),  # High onset_sharpness only
    "rhythmic_high": (0, 0, 0, 0, 0, 0, 7, 0),  # High rhythmic_impulse only
    "edge_release_high": (0, 7, 0, 0, 0, 0, 0, 0),  # High edge_release only
    "alternating_lh": (0, 7, 0, 7, 0, 7, 0, 7),  # Alternating low/high
    "alternating_mh": (4, 7, 4, 7, 4, 7, 4, 7),  # Alternating mid/high
}


def create_test_phase10_result(artifact_hash: str = None) -> Phase10Result:
    """Create a test Phase10Result with placeholder data."""
    if artifact_hash is None:
        artifact_hash = "a" * 64  # Default 64-char hex hash
    return Phase10Result(
        artifact_hash=artifact_hash,
        vc_facts=("VC-1", "VC-2", "VC-3", "VC-4", "VC-5"),
        acoustic_regime="TEST_REGIME",
        source_data={
            "vc_1_data": "data_slot_1",
            "vc_2_data": "data_slot_2",
            "vc_3_data": "data_slot_3",
            "vc_4_data": "data_slot_4",
            "vc_5_data": "data_slot_5",
        },
    )


_request_counter = 0

def create_test_request(
    path: Tuple[str, ...],
    ppv: Tuple[int, ...],
    mode: RenderMode = RenderMode.GOVERNED,
) -> Phase11BRequest:
    """Create a test Phase11BRequest with unique artifact ID."""
    global _request_counter
    _request_counter += 1

    # Ensure unique artifact_id by including counter and all parameters
    artifact_id = f"test_{path[0]}_{ppv}_{mode.value}_{_request_counter}"
    artifact_hash = hashlib.sha256(artifact_id.encode()).hexdigest()

    return Phase11BRequest(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase10_result=create_test_phase10_result(artifact_hash),
        ontological_path=path,
        ppv_values=ppv,
        render_mode=mode,
    )


# =============================================================================
# Analysis 1: Structural Ceiling
# =============================================================================

@dataclass
class CeilingAnalysisResult:
    """Result of structural ceiling analysis."""
    total_ppv_combinations: int
    unique_hashes_by_ppv: int
    total_path_combinations: int
    unique_hashes_by_path: int
    combined_combinations: int
    unique_hashes_combined: int
    ceiling_ppv: float  # unique/total ratio for PPV
    ceiling_path: float  # unique/total ratio for path
    ceiling_combined: float  # unique/total ratio combined
    saturation_point_ppv: Optional[int]  # When adding PPV stops helping
    saturation_point_path: Optional[int]  # When adding path stops helping


def analyze_structural_ceiling() -> CeilingAnalysisResult:
    """
    Identify the structural ceiling of differentiation.

    At what point do additional PPV or ontological variations
    stop producing new output hashes?
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 1: STRUCTURAL CEILING OF DIFFERENTIATION")
    print("=" * 70)

    controller = Phase11BController()

    # Generate all band combinations (3^8 = 6561)
    bands = [PPVBand.LOW, PPVBand.MID, PPVBand.HIGH]
    band_values = {"L": 1, "M": 4, "H": 7}  # Representative values

    # Test PPV-only variation (fixed path)
    fixed_path = ("THINKING",)
    ppv_hashes: Set[str] = set()
    ppv_combinations_tested = 0
    ppv_saturation_history: List[Tuple[int, int]] = []

    print("\nPhase 1: Testing PPV variations (fixed path: THINKING)")

    # Sample PPV space systematically
    for combo in product(bands, repeat=8):
        ppv = tuple(band_values[b.value] for b in combo)
        request = create_test_request(fixed_path, ppv)
        response = controller.execute(request)
        ppv_hashes.add(response.candidate_output_hash)
        ppv_combinations_tested += 1

        if ppv_combinations_tested % 1000 == 0:
            ppv_saturation_history.append((ppv_combinations_tested, len(ppv_hashes)))
            print(f"  PPV tested: {ppv_combinations_tested}, unique hashes: {len(ppv_hashes)}")

    ppv_saturation_history.append((ppv_combinations_tested, len(ppv_hashes)))

    # Find PPV saturation point
    saturation_ppv = None
    for i in range(1, len(ppv_saturation_history)):
        prev_count, prev_unique = ppv_saturation_history[i-1]
        curr_count, curr_unique = ppv_saturation_history[i]
        if curr_unique == prev_unique:
            saturation_ppv = prev_count
            break

    # Test path-only variation (fixed PPV)
    fixed_ppv = (4, 4, 4, 4, 4, 4, 4, 4)  # Neutral
    path_hashes: Set[str] = set()

    print("\nPhase 2: Testing path variations (fixed PPV: neutral)")

    for path in ALL_ONTOLOGICAL_PATHS:
        request = create_test_request(path, fixed_ppv)
        response = controller.execute(request)
        path_hashes.add(response.candidate_output_hash)

    path_combinations_tested = len(ALL_ONTOLOGICAL_PATHS)

    # Test combined variations
    combined_hashes: Set[str] = set()
    combined_tested = 0

    print("\nPhase 3: Testing combined PPV × path variations")

    # Sample combined space
    sample_ppvs = list(PPV_VARIANTS.values())
    for path in ALL_ONTOLOGICAL_PATHS:
        for ppv in sample_ppvs:
            request = create_test_request(path, ppv)
            response = controller.execute(request)
            combined_hashes.add(response.candidate_output_hash)
            combined_tested += 1

    print(f"  Combined tested: {combined_tested}, unique hashes: {len(combined_hashes)}")

    # Calculate ceilings
    ceiling_ppv = len(ppv_hashes) / ppv_combinations_tested
    ceiling_path = len(path_hashes) / path_combinations_tested
    ceiling_combined = len(combined_hashes) / combined_tested

    result = CeilingAnalysisResult(
        total_ppv_combinations=ppv_combinations_tested,
        unique_hashes_by_ppv=len(ppv_hashes),
        total_path_combinations=path_combinations_tested,
        unique_hashes_by_path=len(path_hashes),
        combined_combinations=combined_tested,
        unique_hashes_combined=len(combined_hashes),
        ceiling_ppv=ceiling_ppv,
        ceiling_path=ceiling_path,
        ceiling_combined=ceiling_combined,
        saturation_point_ppv=saturation_ppv,
        saturation_point_path=None,  # Path has limited space, no saturation
    )

    print("\n--- Ceiling Analysis Results ---")
    print(f"PPV only: {result.unique_hashes_by_ppv}/{result.total_ppv_combinations} "
          f"({result.ceiling_ppv:.4f} differentiation rate)")
    print(f"Path only: {result.unique_hashes_by_path}/{result.total_path_combinations} "
          f"({result.ceiling_path:.4f} differentiation rate)")
    print(f"Combined: {result.unique_hashes_combined}/{result.combined_combinations} "
          f"({result.ceiling_combined:.4f} differentiation rate)")

    if saturation_ppv:
        print(f"PPV saturation point: {saturation_ppv} combinations")
    else:
        print("PPV saturation: NOT REACHED (all combinations produce unique hashes)")

    return result


# =============================================================================
# Analysis 2: Clustering by Ontological Layer vs PPV
# =============================================================================

@dataclass
class ClusteringAnalysisResult:
    """Result of clustering analysis."""
    path_cluster_cohesion: float  # How similar outputs within same path are
    ppv_cluster_cohesion: float   # How similar outputs within same PPV are
    path_is_stronger_axis: bool   # True if path clusters more strongly
    path_clusters: Dict[str, List[str]]  # path -> list of hashes
    ppv_clusters: Dict[str, List[str]]   # ppv variant -> list of hashes
    cross_entropy_path: float  # Entropy of paths within hash groups
    cross_entropy_ppv: float   # Entropy of PPV within hash groups


def jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def analyze_clustering() -> ClusteringAnalysisResult:
    """
    Determine whether outputs cluster by ontological layer more
    strongly than by PPV or temperature.
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 2: CLUSTERING BY ONTOLOGICAL LAYER vs PPV")
    print("=" * 70)

    controller = Phase11BController()

    # Collect outputs grouped by path and PPV
    path_clusters: Dict[str, List[str]] = defaultdict(list)
    ppv_clusters: Dict[str, List[str]] = defaultdict(list)

    # Also track hash -> (path, ppv) mappings for cross-entropy
    hash_to_paths: Dict[str, Set[str]] = defaultdict(set)
    hash_to_ppvs: Dict[str, Set[str]] = defaultdict(set)

    print("\nCollecting output hashes by path and PPV...")

    for path in ALL_ONTOLOGICAL_PATHS:
        for ppv_name, ppv in PPV_VARIANTS.items():
            request = create_test_request(path, ppv)
            response = controller.execute(request)

            path_key = path[0]
            path_clusters[path_key].append(response.candidate_output_hash)
            ppv_clusters[ppv_name].append(response.candidate_output_hash)

            hash_to_paths[response.candidate_output_hash].add(path_key)
            hash_to_ppvs[response.candidate_output_hash].add(ppv_name)

    # Compute within-cluster hash diversity (lower = more cohesive)
    def cluster_cohesion(clusters: Dict[str, List[str]]) -> float:
        """
        Measure cluster cohesion as 1 - (avg unique hashes / cluster size).
        Higher = more cohesive (fewer unique hashes within cluster).
        """
        cohesion_scores = []
        for cluster_key, hashes in clusters.items():
            if len(hashes) > 0:
                unique_ratio = len(set(hashes)) / len(hashes)
                # Cohesion is inverse of unique ratio
                cohesion_scores.append(1 - unique_ratio + 0.001)  # Add small epsilon
        return sum(cohesion_scores) / len(cohesion_scores) if cohesion_scores else 0.0

    path_cohesion = cluster_cohesion(path_clusters)
    ppv_cohesion = cluster_cohesion(ppv_clusters)

    # Compute cross-entropy (how mixed are paths/ppvs across hash groups)
    def compute_cross_entropy(hash_to_labels: Dict[str, Set[str]], total_labels: int) -> float:
        """
        Lower cross-entropy = labels are concentrated in fewer hashes = stronger clustering.
        """
        if not hash_to_labels:
            return 0.0

        # For each hash, count how many different labels it has
        label_counts = [len(labels) for labels in hash_to_labels.values()]
        avg_labels_per_hash = sum(label_counts) / len(label_counts)

        # Normalize by total possible labels
        return avg_labels_per_hash / total_labels

    cross_entropy_path = compute_cross_entropy(hash_to_paths, len(ALL_ONTOLOGICAL_PATHS))
    cross_entropy_ppv = compute_cross_entropy(hash_to_ppvs, len(PPV_VARIANTS))

    # Path clusters more strongly if it has lower cross-entropy (more unique hashes per path)
    path_is_stronger = cross_entropy_path < cross_entropy_ppv

    result = ClusteringAnalysisResult(
        path_cluster_cohesion=path_cohesion,
        ppv_cluster_cohesion=ppv_cohesion,
        path_is_stronger_axis=path_is_stronger,
        path_clusters=dict(path_clusters),
        ppv_clusters=dict(ppv_clusters),
        cross_entropy_path=cross_entropy_path,
        cross_entropy_ppv=cross_entropy_ppv,
    )

    print("\n--- Clustering Analysis Results ---")
    print(f"Path cluster cohesion: {result.path_cluster_cohesion:.4f}")
    print(f"PPV cluster cohesion: {result.ppv_cluster_cohesion:.4f}")
    print(f"Cross-entropy (path): {result.cross_entropy_path:.4f}")
    print(f"Cross-entropy (PPV): {result.cross_entropy_ppv:.4f}")
    print(f"Stronger clustering axis: {'ONTOLOGICAL PATH' if path_is_stronger else 'PPV'}")

    # Detail breakdown
    print("\nPath cluster uniqueness:")
    for path_key, hashes in path_clusters.items():
        unique = len(set(hashes))
        print(f"  {path_key}: {unique}/{len(hashes)} unique hashes")

    print("\nPPV cluster uniqueness:")
    for ppv_name, hashes in ppv_clusters.items():
        unique = len(set(hashes))
        print(f"  {ppv_name}: {unique}/{len(hashes)} unique hashes")

    return result


# =============================================================================
# Analysis 3: PPV Dimension Correlation with Surface Changes
# =============================================================================

@dataclass
class PPVDimensionCorrelation:
    """Correlation of a PPV dimension with surface changes."""
    dimension_name: str
    dimension_index: int
    hash_divergence_score: float  # How much changing this dim affects output hash
    length_variance: float  # Variance in output length when dim changes
    token_diversity_score: float  # How much output tokens vary


@dataclass
class PPVCorrelationResult:
    """Result of PPV dimension correlation analysis."""
    dimension_correlations: List[PPVDimensionCorrelation]
    strongest_dimension: str
    weakest_dimension: str
    overall_ppv_impact: float


def analyze_ppv_correlation() -> PPVCorrelationResult:
    """
    Quantify which PPV dimensions most strongly correlate with
    observable surface changes (length, token diversity, hash divergence).
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 3: PPV DIMENSION CORRELATION WITH SURFACE CHANGES")
    print("=" * 70)

    controller = Phase11BController()

    # PPV dimension names in order (matching the tuple order)
    dim_names = [
        "edge_tension",      # 0
        "edge_release",      # 1
        "onset_sharpness",   # 2
        "sonority_lift",     # 3
        "continuity",        # 4
        "discontinuity",     # 5
        "rhythmic_impulse",  # 6
        "stability_pressure" # 7
    ]

    fixed_path = ("THINKING",)
    baseline_ppv = [4, 4, 4, 4, 4, 4, 4, 4]  # All mid

    dimension_correlations: List[PPVDimensionCorrelation] = []

    print("\nTesting each PPV dimension independently...")

    for dim_idx, dim_name in enumerate(dim_names):
        print(f"\n  Testing dimension {dim_idx}: {dim_name}")

        # Vary this dimension from 0 to 7, keeping others at 4
        hashes: List[str] = []
        lengths: List[int] = []
        tokens: List[Set[str]] = []

        for value in range(8):
            ppv = baseline_ppv.copy()
            ppv[dim_idx] = value

            request = create_test_request(fixed_path, tuple(ppv))
            response = controller.execute(request)

            hashes.append(response.candidate_output_hash)
            lengths.append(len(response.output_text))
            tokens.append(set(response.output_text.split()))

        # Calculate metrics
        unique_hashes = len(set(hashes))
        hash_divergence = unique_hashes / 8  # Normalize to [0, 1]

        # Length variance (normalized)
        avg_len = sum(lengths) / len(lengths)
        len_variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
        normalized_len_variance = min(len_variance / (avg_len ** 2 + 1), 1.0)

        # Token diversity (Jaccard distance across variations)
        token_distances = []
        for i in range(len(tokens)):
            for j in range(i + 1, len(tokens)):
                jacc = jaccard_similarity(tokens[i], tokens[j])
                token_distances.append(1 - jacc)  # Distance = 1 - similarity
        token_diversity = sum(token_distances) / len(token_distances) if token_distances else 0.0

        correlation = PPVDimensionCorrelation(
            dimension_name=dim_name,
            dimension_index=dim_idx,
            hash_divergence_score=hash_divergence,
            length_variance=normalized_len_variance,
            token_diversity_score=token_diversity,
        )
        dimension_correlations.append(correlation)

        print(f"    Unique hashes: {unique_hashes}/8 ({hash_divergence:.3f})")
        print(f"    Length variance: {normalized_len_variance:.4f}")
        print(f"    Token diversity: {token_diversity:.4f}")

    # Sort by impact (using hash divergence as primary metric)
    sorted_dims = sorted(dimension_correlations,
                         key=lambda x: x.hash_divergence_score,
                         reverse=True)

    overall_impact = sum(d.hash_divergence_score for d in dimension_correlations) / len(dimension_correlations)

    result = PPVCorrelationResult(
        dimension_correlations=dimension_correlations,
        strongest_dimension=sorted_dims[0].dimension_name,
        weakest_dimension=sorted_dims[-1].dimension_name,
        overall_ppv_impact=overall_impact,
    )

    print("\n--- PPV Correlation Results ---")
    print(f"Overall PPV impact on output: {result.overall_ppv_impact:.4f}")
    print(f"Strongest dimension: {result.strongest_dimension}")
    print(f"Weakest dimension: {result.weakest_dimension}")
    print("\nDimension ranking by hash divergence:")
    for i, dim in enumerate(sorted_dims):
        print(f"  {i+1}. {dim.dimension_name}: {dim.hash_divergence_score:.4f}")

    return result


# =============================================================================
# Analysis 4: OPEN vs GOVERNED Divergence
# =============================================================================

@dataclass
class ModeComparisonResult:
    """Result of OPEN vs GOVERNED mode comparison."""
    total_comparisons: int
    divergent_count: int
    divergence_rate: float
    divergent_by_dimension: Dict[str, int]  # Which dims cause divergence
    amplifying_dimensions: List[str]  # Dims that increase divergence
    average_hash_distance: float  # Average character difference in hashes


def analyze_mode_divergence() -> ModeComparisonResult:
    """
    Compare OPEN vs GOVERNED mode outputs for identical structural inputs.

    Report:
    1. Divergence rate
    2. Divergence magnitude
    3. Which dimensions amplify divergence
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 4: OPEN vs GOVERNED MODE DIVERGENCE")
    print("=" * 70)

    controller = Phase11BController()

    divergent_count = 0
    total_comparisons = 0
    divergent_by_dimension: Dict[str, int] = defaultdict(int)
    hash_distances: List[int] = []

    print("\nComparing OPEN vs GOVERNED outputs...")

    for path in ALL_ONTOLOGICAL_PATHS:
        for ppv_name, ppv in PPV_VARIANTS.items():
            # Create identical requests with different modes
            governed_request = create_test_request(path, ppv, RenderMode.GOVERNED)
            open_request = create_test_request(path, ppv, RenderMode.OPEN)

            # Force artifact hash to match for fair comparison
            governed_hash = governed_request.artifact_hash
            open_request = Phase11BRequest(
                artifact_id=open_request.artifact_id,
                artifact_hash=governed_hash,
                phase10_result=open_request.phase10_result,
                ontological_path=open_request.ontological_path,
                ppv_values=open_request.ppv_values,
                render_mode=RenderMode.OPEN,
            )

            governed_response = controller.execute(governed_request)
            open_response = controller.execute(open_request)

            total_comparisons += 1

            # Check for divergence
            if governed_response.candidate_output_hash != open_response.candidate_output_hash:
                divergent_count += 1
                divergent_by_dimension[ppv_name] = divergent_by_dimension.get(ppv_name, 0) + 1

                # Calculate hash distance (character differences)
                hash1 = governed_response.candidate_output_hash
                hash2 = open_response.candidate_output_hash
                distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
                hash_distances.append(distance)

    divergence_rate = divergent_count / total_comparisons if total_comparisons > 0 else 0.0
    avg_hash_distance = sum(hash_distances) / len(hash_distances) if hash_distances else 0.0

    # Identify amplifying dimensions (those that cause more divergence)
    avg_divergence = divergent_count / len(PPV_VARIANTS) if PPV_VARIANTS else 0
    amplifying = [dim for dim, count in divergent_by_dimension.items()
                  if count > avg_divergence]

    result = ModeComparisonResult(
        total_comparisons=total_comparisons,
        divergent_count=divergent_count,
        divergence_rate=divergence_rate,
        divergent_by_dimension=dict(divergent_by_dimension),
        amplifying_dimensions=amplifying,
        average_hash_distance=avg_hash_distance,
    )

    print("\n--- Mode Divergence Results ---")
    print(f"Total comparisons: {result.total_comparisons}")
    print(f"Divergent outputs: {result.divergent_count}")
    print(f"Divergence rate: {result.divergence_rate:.4f} ({result.divergence_rate*100:.2f}%)")
    print(f"Average hash distance (when divergent): {result.average_hash_distance:.2f} chars")

    if result.divergent_count > 0:
        print(f"Amplifying dimensions: {', '.join(amplifying) if amplifying else 'None identified'}")
        print("\nDivergence by PPV variant:")
        for ppv_name, count in sorted(divergent_by_dimension.items(), key=lambda x: -x[1]):
            print(f"  {ppv_name}: {count} divergences")
    else:
        print("NO DIVERGENCE: OPEN and GOVERNED produce identical outputs for same inputs")

    return result


# =============================================================================
# Analysis 5: Minimum Structural Change for New Hash
# =============================================================================

@dataclass
class MinimumChangeResult:
    """Result of minimum change analysis."""
    smallest_ppv_change: int  # Minimum PPV value delta for new hash
    smallest_path_change: bool  # Whether changing path always produces new hash
    single_bit_ppv_effective: bool  # Can single PPV bit flip produce new hash
    critical_dimensions: List[str]  # PPV dimensions where small changes matter


def analyze_minimum_change() -> MinimumChangeResult:
    """
    Identify the smallest structural change that produces a new output hash.
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 5: MINIMUM STRUCTURAL CHANGE FOR NEW HASH")
    print("=" * 70)

    controller = Phase11BController()

    # Baseline configuration
    baseline_path = ("THINKING",)
    baseline_ppv = [4, 4, 4, 4, 4, 4, 4, 4]  # All mid

    baseline_request = create_test_request(baseline_path, tuple(baseline_ppv))
    baseline_response = controller.execute(baseline_request)
    baseline_hash = baseline_response.candidate_output_hash

    print(f"\nBaseline: path={baseline_path[0]}, ppv={tuple(baseline_ppv)}")
    print(f"Baseline hash: {baseline_hash[:16]}...")

    # Test 1: Single PPV unit changes
    print("\nTest 1: Single PPV unit changes (+1 or -1)")
    single_bit_effective = False
    smallest_ppv_change = 8  # Max possible
    critical_dims: List[str] = []

    dim_names = [
        "edge_tension", "edge_release", "onset_sharpness", "sonority_lift",
        "continuity", "discontinuity", "rhythmic_impulse", "stability_pressure"
    ]

    for dim_idx, dim_name in enumerate(dim_names):
        for delta in [1, -1]:
            test_ppv = baseline_ppv.copy()
            new_val = test_ppv[dim_idx] + delta
            if 0 <= new_val <= 7:
                test_ppv[dim_idx] = new_val
                request = create_test_request(baseline_path, tuple(test_ppv))
                response = controller.execute(request)

                if response.candidate_output_hash != baseline_hash:
                    single_bit_effective = True
                    smallest_ppv_change = min(smallest_ppv_change, abs(delta))
                    if dim_name not in critical_dims:
                        critical_dims.append(dim_name)
                    print(f"  {dim_name} {'+' if delta > 0 else ''}{delta}: NEW HASH")

    # Test 2: Minimum path change
    print("\nTest 2: Path changes")
    path_always_changes = True
    for path in ALL_ONTOLOGICAL_PATHS:
        if path != baseline_path:
            request = create_test_request(path, tuple(baseline_ppv))
            response = controller.execute(request)
            if response.candidate_output_hash == baseline_hash:
                path_always_changes = False
                print(f"  {baseline_path[0]} -> {path[0]}: SAME HASH (collision!)")
            else:
                print(f"  {baseline_path[0]} -> {path[0]}: Different hash")

    result = MinimumChangeResult(
        smallest_ppv_change=smallest_ppv_change if single_bit_effective else -1,
        smallest_path_change=path_always_changes,
        single_bit_ppv_effective=single_bit_effective,
        critical_dimensions=critical_dims,
    )

    print("\n--- Minimum Change Results ---")
    if single_bit_effective:
        print(f"Smallest PPV change: {result.smallest_ppv_change} unit(s)")
        print(f"Critical dimensions: {', '.join(critical_dims)}")
    else:
        print("Single PPV unit changes do NOT produce new hashes")
        print("(This suggests PPV banding quantizes changes)")

    print(f"Path change always produces new hash: {path_always_changes}")

    return result


# =============================================================================
# Analysis 6: Silent Collapse Detection
# =============================================================================

@dataclass
class SilentCollapseResult:
    """Result of silent collapse detection."""
    total_input_combinations: int
    unique_output_hashes: int
    collision_count: int
    collision_groups: List[List[Tuple[str, str]]]  # Groups of colliding (path, ppv_name)
    collapse_rate: float
    has_silent_collapse: bool


def analyze_silent_collapse() -> SilentCollapseResult:
    """
    Check for silent collapse patterns: cases where multiple distinct
    structural inputs produce identical outputs across intents.
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 6: SILENT COLLAPSE DETECTION")
    print("=" * 70)

    controller = Phase11BController()

    # Map hash -> list of (path, ppv_name) that produced it
    hash_to_inputs: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    print("\nScanning for silent collapse across all path × PPV combinations...")

    for path in ALL_ONTOLOGICAL_PATHS:
        for ppv_name, ppv in PPV_VARIANTS.items():
            request = create_test_request(path, ppv)
            response = controller.execute(request)

            hash_to_inputs[response.candidate_output_hash].append((path[0], ppv_name))

    total_inputs = len(ALL_ONTOLOGICAL_PATHS) * len(PPV_VARIANTS)
    unique_hashes = len(hash_to_inputs)

    # Find collisions (multiple inputs -> same hash)
    collision_groups: List[List[Tuple[str, str]]] = []
    collision_count = 0

    for hash_val, inputs in hash_to_inputs.items():
        if len(inputs) > 1:
            collision_groups.append(inputs)
            collision_count += len(inputs) - 1  # Count extra inputs as collisions

    collapse_rate = collision_count / total_inputs if total_inputs > 0 else 0.0
    has_collapse = collision_count > 0

    result = SilentCollapseResult(
        total_input_combinations=total_inputs,
        unique_output_hashes=unique_hashes,
        collision_count=collision_count,
        collision_groups=collision_groups,
        collapse_rate=collapse_rate,
        has_silent_collapse=has_collapse,
    )

    print("\n--- Silent Collapse Results ---")
    print(f"Total input combinations: {result.total_input_combinations}")
    print(f"Unique output hashes: {result.unique_output_hashes}")
    print(f"Collision count: {result.collision_count}")
    print(f"Collapse rate: {result.collapse_rate:.4f} ({result.collapse_rate*100:.2f}%)")

    if has_collapse:
        print("\nWARNING: SILENT COLLAPSE DETECTED!")
        print("Collision groups:")
        for i, group in enumerate(collision_groups[:10]):  # Show first 10
            print(f"  Group {i+1}: {group}")
        if len(collision_groups) > 10:
            print(f"  ... and {len(collision_groups) - 10} more groups")
    else:
        print("\nNO SILENT COLLAPSE: All input combinations produce unique outputs")

    return result


# =============================================================================
# Analysis 7: Neutral Baseline Comparison
# =============================================================================

@dataclass
class NeutralBaselineResult:
    """Result of neutral baseline comparison."""
    neutral_differentiation: float  # Differentiation score with neutral PPV
    structured_differentiation: float  # Differentiation score with structured PPV
    improvement_factor: float  # How much better structured is
    neutral_unique_hashes: int
    structured_unique_hashes: int


def analyze_neutral_baseline() -> NeutralBaselineResult:
    """
    Run Phase-11B with all PPV values neutral and random ontological paths disabled.
    Compare differentiation metrics to the structured runs.
    """
    print("\n" + "=" * 70)
    print("ANALYSIS 7: NEUTRAL BASELINE COMPARISON")
    print("=" * 70)

    controller = Phase11BController()

    # Neutral configuration: All PPV at band boundary (3 = MID)
    neutral_ppv = (3, 3, 3, 3, 3, 3, 3, 3)

    # Collect neutral outputs (vary only path)
    print("\nPhase 1: Neutral PPV, varying paths only")
    neutral_hashes: Set[str] = set()

    for path in ALL_ONTOLOGICAL_PATHS:
        request = create_test_request(path, neutral_ppv)
        response = controller.execute(request)
        neutral_hashes.add(response.candidate_output_hash)

    neutral_unique = len(neutral_hashes)
    neutral_diff = neutral_unique / len(ALL_ONTOLOGICAL_PATHS)

    print(f"  Unique hashes (neutral): {neutral_unique}/{len(ALL_ONTOLOGICAL_PATHS)}")

    # Structured configuration: Varied PPV
    print("\nPhase 2: Structured PPV, varying paths")
    structured_hashes: Set[str] = set()
    total_structured = 0

    for path in ALL_ONTOLOGICAL_PATHS:
        for ppv_name, ppv in PPV_VARIANTS.items():
            if ppv_name != "neutral":  # Skip neutral variant
                request = create_test_request(path, ppv)
                response = controller.execute(request)
                structured_hashes.add(response.candidate_output_hash)
                total_structured += 1

    structured_unique = len(structured_hashes)
    structured_diff = structured_unique / total_structured if total_structured > 0 else 0.0

    print(f"  Unique hashes (structured): {structured_unique}/{total_structured}")

    # Calculate improvement
    improvement = structured_diff / neutral_diff if neutral_diff > 0 else float('inf')

    result = NeutralBaselineResult(
        neutral_differentiation=neutral_diff,
        structured_differentiation=structured_diff,
        improvement_factor=improvement,
        neutral_unique_hashes=neutral_unique,
        structured_unique_hashes=structured_unique,
    )

    print("\n--- Neutral Baseline Results ---")
    print(f"Neutral differentiation: {result.neutral_differentiation:.4f}")
    print(f"Structured differentiation: {result.structured_differentiation:.4f}")
    print(f"Improvement factor: {result.improvement_factor:.2f}x")

    if improvement > 1:
        print(f"\nStructured PPV provides {(improvement-1)*100:.1f}% more differentiation")
    elif improvement < 1:
        print(f"\nWARNING: Neutral PPV provides better differentiation (unexpected)")
    else:
        print(f"\nNo difference between neutral and structured (PPV has no effect)")

    return result


# =============================================================================
# Main Analysis Runner
# =============================================================================

@dataclass
class FullAnalysisReport:
    """Complete analysis report."""
    ceiling: CeilingAnalysisResult
    clustering: ClusteringAnalysisResult
    ppv_correlation: PPVCorrelationResult
    mode_divergence: ModeComparisonResult
    minimum_change: MinimumChangeResult
    silent_collapse: SilentCollapseResult
    neutral_baseline: NeutralBaselineResult

    def to_summary(self) -> str:
        """Generate summary string."""
        lines = [
            "\n" + "=" * 70,
            "PHASE-11B STRUCTURAL ANALYSIS SUMMARY",
            "=" * 70,
            "",
            "1. STRUCTURAL CEILING:",
            f"   - PPV ceiling: {self.ceiling.ceiling_ppv:.4f}",
            f"   - Path ceiling: {self.ceiling.ceiling_path:.4f}",
            f"   - Combined ceiling: {self.ceiling.ceiling_combined:.4f}",
            "",
            "2. CLUSTERING:",
            f"   - Stronger axis: {'ONTOLOGICAL PATH' if self.clustering.path_is_stronger_axis else 'PPV'}",
            f"   - Path cross-entropy: {self.clustering.cross_entropy_path:.4f}",
            f"   - PPV cross-entropy: {self.clustering.cross_entropy_ppv:.4f}",
            "",
            "3. PPV DIMENSION IMPACT:",
            f"   - Strongest: {self.ppv_correlation.strongest_dimension}",
            f"   - Weakest: {self.ppv_correlation.weakest_dimension}",
            f"   - Overall impact: {self.ppv_correlation.overall_ppv_impact:.4f}",
            "",
            "4. OPEN vs GOVERNED:",
            f"   - Divergence rate: {self.mode_divergence.divergence_rate:.4f}",
            f"   - Avg hash distance: {self.mode_divergence.average_hash_distance:.2f}",
            "",
            "5. MINIMUM CHANGE:",
            f"   - Single PPV unit effective: {self.minimum_change.single_bit_ppv_effective}",
            f"   - Path change always effective: {self.minimum_change.smallest_path_change}",
            "",
            "6. SILENT COLLAPSE:",
            f"   - Collapse detected: {self.silent_collapse.has_silent_collapse}",
            f"   - Collapse rate: {self.silent_collapse.collapse_rate:.4f}",
            "",
            "7. NEUTRAL BASELINE:",
            f"   - Neutral differentiation: {self.neutral_baseline.neutral_differentiation:.4f}",
            f"   - Structured differentiation: {self.neutral_baseline.structured_differentiation:.4f}",
            f"   - Improvement: {self.neutral_baseline.improvement_factor:.2f}x",
            "",
            "=" * 70,
        ]
        return "\n".join(lines)


def run_full_analysis() -> FullAnalysisReport:
    """Run all analysis components and generate full report."""
    print("\n" + "#" * 70)
    print("#" + " " * 20 + "PHASE-11B STRUCTURAL ANALYSIS" + " " * 19 + "#")
    print("#" * 70)

    # Run all analyses
    ceiling = analyze_structural_ceiling()
    clustering = analyze_clustering()
    ppv_correlation = analyze_ppv_correlation()
    mode_divergence = analyze_mode_divergence()
    minimum_change = analyze_minimum_change()
    silent_collapse = analyze_silent_collapse()
    neutral_baseline = analyze_neutral_baseline()

    report = FullAnalysisReport(
        ceiling=ceiling,
        clustering=clustering,
        ppv_correlation=ppv_correlation,
        mode_divergence=mode_divergence,
        minimum_change=minimum_change,
        silent_collapse=silent_collapse,
        neutral_baseline=neutral_baseline,
    )

    print(report.to_summary())

    return report


if __name__ == "__main__":
    report = run_full_analysis()
