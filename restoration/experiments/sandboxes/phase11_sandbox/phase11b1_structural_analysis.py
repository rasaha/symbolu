"""
Phase-11B.1 Structural Analysis Harness
========================================

Comprehensive structural analysis of Phase-11B.1 collision-free routing:

1. Structural Ceiling Analysis
   - At what point do variations stop producing new output hashes?

2. Clustering Analysis
   - Do outputs cluster more by ontological layer or by PPV?

3. PPV Dimension Correlation
   - Which dimensions correlate with surface changes?

4. OPEN vs GOVERNED Divergence
   - Divergence rate, magnitude, amplifying dimensions

5. Minimal Structural Change
   - Smallest change that produces a new output hash

6. Silent Collapse Detection
   - Multiple inputs producing identical outputs

7. Neutral Baseline Comparison
   - Neutral PPV vs structured runs

CONSTRAINTS:
    - No external LLM calls
    - No ML/NLP imports
    - Deterministic only
    - Uses Phase-11B.1 records only (no semantics)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from phase11b1_routing import (
    # Constants
    RENDER_BLOCKED,
    PPV_DIM_COUNT,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    SLOT_PLAN_VC_FACTS,
    # Enums
    PPVSubBand,
    PPVBand,
    OntologicalFamily,
    SlotPlan,
    RegistryType,
    RenderMode,
    FailureReason,
    # Dataclasses
    SubBandSignature,
    RoutingKey,
    Phase11B1Request,
    Phase11B1Response,
    # Functions
    create_subband_signature,
    create_routing_key,
    execute_phase11b1,
    get_registry,
)


# =============================================================================
# Analysis Record
# =============================================================================


@dataclass(frozen=True)
class AnalysisRecord:
    """Record of a single analysis run."""
    # Input
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    render_mode: RenderMode

    # Routing
    subband_variant_id: str
    band_signature: str
    template_id: str

    # Output metrics
    output_hash: str
    output_length: int
    token_count: int
    unique_token_count: int

    # Status
    is_blocked: bool

    def output_fingerprint(self) -> str:
        """Compact fingerprint of output characteristics."""
        return f"{self.output_hash[:8]}|len:{self.output_length}|tok:{self.token_count}"


def compute_output_hash(text: str) -> str:
    """Compute deterministic hash of output text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tokenize_simple(text: str) -> List[str]:
    """Simple whitespace tokenization."""
    return text.split()


# =============================================================================
# Analysis Configuration
# =============================================================================


# All ontological families (excluding DEFAULT for structured tests)
STRUCTURED_FAMILIES: Tuple[OntologicalFamily, ...] = tuple(
    f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT
)

# PPV dimension names
PPV_DIM_NAMES: Tuple[str, ...] = (
    "edge_tension",
    "edge_release",
    "onset_sharpness",
    "sonority_lift",
    "continuity",
    "discontinuity",
    "rhythmic_impulse",
    "stability_pressure",
)

# Neutral PPV (all mid-range)
NEUTRAL_PPV: Tuple[int, ...] = (4, 4, 4, 4, 4, 4, 4, 4)


def make_artifact_hash() -> str:
    """Create a valid 64-char hex hash."""
    return hashlib.sha256(b"analysis_artifact").hexdigest()


def make_vc_source_data() -> Dict[str, str]:
    """Create standard VC source data."""
    return {
        "vc_1_data": "observation_datum",
        "vc_2_data": "state_datum",
        "vc_3_data": "context_datum",
        "vc_4_data": "reference_datum",
        "vc_5_data": "marker_datum",
    }


# =============================================================================
# Analysis Runner
# =============================================================================


class Phase11B1AnalysisRunner:
    """Runner for Phase-11B.1 structural analysis."""

    def __init__(self) -> None:
        self._records: List[AnalysisRecord] = []
        self._vc_data = make_vc_source_data()

    def run_single(
        self,
        ontological_path: Tuple[str, ...],
        ppv_values: Tuple[int, ...],
        render_mode: RenderMode,
    ) -> AnalysisRecord:
        """Run a single analysis experiment."""
        request = Phase11B1Request(
            artifact_id="analysis",
            artifact_hash=make_artifact_hash(),
            ontological_path=ontological_path,
            ppv_values=ppv_values,
            render_mode=render_mode,
            vc_source_data=self._vc_data,
        )

        response = execute_phase11b1(request)

        tokens = tokenize_simple(response.output_text)

        record = AnalysisRecord(
            ontological_path=ontological_path,
            ppv_values=ppv_values,
            render_mode=render_mode,
            subband_variant_id=response.subband_variant_id,
            band_signature=response.band_signature,
            template_id=response.template_id,
            output_hash=compute_output_hash(response.output_text),
            output_length=len(response.output_text),
            token_count=len(tokens),
            unique_token_count=len(set(tokens)),
            is_blocked=response.is_blocked(),
        )

        self._records.append(record)
        return record

    def get_records(self) -> Tuple[AnalysisRecord, ...]:
        """Get all recorded runs."""
        return tuple(self._records)

    def clear_records(self) -> None:
        """Clear recorded runs."""
        self._records = []


# =============================================================================
# 1. Structural Ceiling Analysis
# =============================================================================


@dataclass(frozen=True)
class CeilingAnalysisResult:
    """Result of structural ceiling analysis."""
    total_variations: int
    unique_output_hashes: int
    unique_template_ids: int
    saturation_point_ppv: Optional[int]  # Number of PPV variations before saturation
    saturation_point_ontological: Optional[int]  # Number of path variations before saturation
    ceiling_ratio: float  # unique_outputs / total_variations
    analysis_type: str


def analyze_structural_ceiling(runner: Phase11B1AnalysisRunner) -> Dict[str, CeilingAnalysisResult]:
    """
    Analyze structural ceiling of differentiation.

    Determines when additional variations stop producing new outputs.
    """
    results = {}

    # Analysis 1: PPV variation ceiling
    runner.clear_records()
    output_hashes: Set[str] = set()
    template_ids: Set[str] = set()
    saturation_point = None

    base_path = ("THINKING",)
    ppv_variations = 0

    # Vary each dimension through all values
    for dim in range(PPV_DIM_COUNT):
        for val in range(PPV_VALUE_MIN, PPV_VALUE_MAX + 1):
            ppv = list(NEUTRAL_PPV)
            ppv[dim] = val

            record = runner.run_single(base_path, tuple(ppv), RenderMode.GOVERNED)
            ppv_variations += 1

            prev_hash_count = len(output_hashes)
            output_hashes.add(record.output_hash)
            template_ids.add(record.template_id)

            # Check for saturation (5 consecutive no-new-hash)
            if saturation_point is None:
                if len(output_hashes) == prev_hash_count:
                    consecutive_no_new = getattr(analyze_structural_ceiling, '_consecutive', 0) + 1
                    analyze_structural_ceiling._consecutive = consecutive_no_new
                    if consecutive_no_new >= 5:
                        saturation_point = ppv_variations - 5
                else:
                    analyze_structural_ceiling._consecutive = 0

    results["ppv_single_dim"] = CeilingAnalysisResult(
        total_variations=ppv_variations,
        unique_output_hashes=len(output_hashes),
        unique_template_ids=len(template_ids),
        saturation_point_ppv=saturation_point,
        saturation_point_ontological=None,
        ceiling_ratio=len(output_hashes) / ppv_variations if ppv_variations > 0 else 0,
        analysis_type="PPV single dimension variation",
    )

    # Analysis 2: Ontological path variation ceiling
    runner.clear_records()
    output_hashes = set()
    template_ids = set()

    for family in STRUCTURED_FAMILIES:
        record = runner.run_single((family.value,), NEUTRAL_PPV, RenderMode.GOVERNED)
        output_hashes.add(record.output_hash)
        template_ids.add(record.template_id)

    results["ontological_path"] = CeilingAnalysisResult(
        total_variations=len(STRUCTURED_FAMILIES),
        unique_output_hashes=len(output_hashes),
        unique_template_ids=len(template_ids),
        saturation_point_ppv=None,
        saturation_point_ontological=len(STRUCTURED_FAMILIES) if len(output_hashes) == len(STRUCTURED_FAMILIES) else None,
        ceiling_ratio=len(output_hashes) / len(STRUCTURED_FAMILIES),
        analysis_type="Ontological path variation",
    )

    # Analysis 3: Combined variation ceiling
    runner.clear_records()
    output_hashes = set()
    template_ids = set()
    total = 0

    # Sample PPV patterns
    ppv_patterns = [
        (0, 0, 0, 0, 0, 0, 0, 0),
        (3, 3, 3, 3, 3, 3, 3, 3),
        (4, 4, 4, 4, 4, 4, 4, 4),
        (7, 7, 7, 7, 7, 7, 7, 7),
        (0, 1, 2, 3, 4, 5, 6, 7),
        (7, 6, 5, 4, 3, 2, 1, 0),
    ]

    for family in STRUCTURED_FAMILIES:
        for ppv in ppv_patterns:
            record = runner.run_single((family.value,), ppv, RenderMode.GOVERNED)
            output_hashes.add(record.output_hash)
            template_ids.add(record.template_id)
            total += 1

    results["combined"] = CeilingAnalysisResult(
        total_variations=total,
        unique_output_hashes=len(output_hashes),
        unique_template_ids=len(template_ids),
        saturation_point_ppv=None,
        saturation_point_ontological=None,
        ceiling_ratio=len(output_hashes) / total if total > 0 else 0,
        analysis_type="Combined path × PPV variation",
    )

    return results


# =============================================================================
# 2. Clustering Analysis
# =============================================================================


@dataclass(frozen=True)
class ClusteringResult:
    """Result of clustering analysis."""
    ontological_cluster_strength: float  # How strongly outputs cluster by ontological layer
    ppv_cluster_strength: float  # How strongly outputs cluster by PPV pattern
    dominant_axis: str  # "ontological" or "ppv" or "equal"
    within_family_uniqueness: float  # Ratio of unique outputs within same family
    within_ppv_uniqueness: float  # Ratio of unique outputs within same PPV
    cross_analysis_details: Dict[str, int]


def analyze_clustering(runner: Phase11B1AnalysisRunner) -> ClusteringResult:
    """
    Analyze whether outputs cluster by ontological layer or PPV.

    Uses output hashes to measure clustering without semantics.
    """
    runner.clear_records()

    # Generate sample outputs
    family_to_hashes: Dict[str, Set[str]] = {}
    ppv_pattern_to_hashes: Dict[str, Set[str]] = {}

    ppv_patterns = [
        ("all_0", (0, 0, 0, 0, 0, 0, 0, 0)),
        ("all_3", (3, 3, 3, 3, 3, 3, 3, 3)),
        ("all_4", (4, 4, 4, 4, 4, 4, 4, 4)),
        ("all_7", (7, 7, 7, 7, 7, 7, 7, 7)),
        ("gradient", (0, 1, 2, 3, 4, 5, 6, 7)),
    ]

    for family in STRUCTURED_FAMILIES[:5]:  # Sample 5 families
        family_name = family.value
        family_to_hashes[family_name] = set()

        for ppv_name, ppv in ppv_patterns:
            if ppv_name not in ppv_pattern_to_hashes:
                ppv_pattern_to_hashes[ppv_name] = set()

            record = runner.run_single((family_name,), ppv, RenderMode.GOVERNED)

            family_to_hashes[family_name].add(record.output_hash)
            ppv_pattern_to_hashes[ppv_name].add(record.output_hash)

    # Calculate within-group uniqueness
    # Higher uniqueness = weaker clustering (more variation within group)

    total_family_hashes = sum(len(h) for h in family_to_hashes.values())
    total_family_groups = len(family_to_hashes)
    avg_family_uniqueness = total_family_hashes / (total_family_groups * len(ppv_patterns))

    total_ppv_hashes = sum(len(h) for h in ppv_pattern_to_hashes.values())
    total_ppv_groups = len(ppv_pattern_to_hashes)
    avg_ppv_uniqueness = total_ppv_hashes / (total_ppv_groups * len(STRUCTURED_FAMILIES[:5]))

    # Cluster strength = inverse of uniqueness (more unique = less clustered)
    # If all outputs in a group are the same, strength = 1.0
    # If all outputs in a group are different, strength = 0.0
    ontological_strength = 1.0 - avg_family_uniqueness
    ppv_strength = 1.0 - avg_ppv_uniqueness

    # Determine dominant axis
    if abs(ontological_strength - ppv_strength) < 0.05:
        dominant = "equal"
    elif ontological_strength > ppv_strength:
        dominant = "ontological"
    else:
        dominant = "ppv"

    return ClusteringResult(
        ontological_cluster_strength=max(0, ontological_strength),
        ppv_cluster_strength=max(0, ppv_strength),
        dominant_axis=dominant,
        within_family_uniqueness=avg_family_uniqueness,
        within_ppv_uniqueness=avg_ppv_uniqueness,
        cross_analysis_details={
            "families_tested": len(family_to_hashes),
            "ppv_patterns_tested": len(ppv_pattern_to_hashes),
            "total_runs": len(runner.get_records()),
        },
    )


# =============================================================================
# 3. PPV Dimension Correlation Analysis
# =============================================================================


@dataclass(frozen=True)
class DimensionCorrelationResult:
    """Correlation result for a single PPV dimension."""
    dimension_index: int
    dimension_name: str
    length_variance: float  # Variance in output length when dimension changes
    token_diversity_variance: float  # Variance in unique token ratio
    hash_divergence_rate: float  # Rate of hash changes when dimension changes
    correlation_strength: float  # Combined correlation score


@dataclass(frozen=True)
class PPVCorrelationAnalysisResult:
    """Result of PPV dimension correlation analysis."""
    dimension_results: Tuple[DimensionCorrelationResult, ...]
    strongest_dimension: str
    weakest_dimension: str
    overall_ppv_sensitivity: float


def analyze_ppv_dimension_correlation(runner: Phase11B1AnalysisRunner) -> PPVCorrelationAnalysisResult:
    """
    Quantify which PPV dimensions most strongly correlate with surface changes.
    """
    runner.clear_records()

    base_path = ("THINKING",)
    dimension_results: List[DimensionCorrelationResult] = []

    for dim_idx in range(PPV_DIM_COUNT):
        lengths: List[int] = []
        token_diversities: List[float] = []
        hashes: List[str] = []

        # Vary this dimension through all values
        for val in range(PPV_VALUE_MIN, PPV_VALUE_MAX + 1):
            ppv = list(NEUTRAL_PPV)
            ppv[dim_idx] = val

            record = runner.run_single(base_path, tuple(ppv), RenderMode.GOVERNED)

            if not record.is_blocked:
                lengths.append(record.output_length)
                diversity = record.unique_token_count / record.token_count if record.token_count > 0 else 0
                token_diversities.append(diversity)
                hashes.append(record.output_hash)

        # Calculate metrics
        if len(lengths) > 1:
            mean_len = sum(lengths) / len(lengths)
            length_var = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)

            mean_div = sum(token_diversities) / len(token_diversities)
            div_var = sum((x - mean_div) ** 2 for x in token_diversities) / len(token_diversities)

            unique_hashes = len(set(hashes))
            hash_divergence = unique_hashes / len(hashes)
        else:
            length_var = 0
            div_var = 0
            hash_divergence = 0

        # Combined correlation strength (normalized)
        correlation = (
            (length_var / 1000 if length_var > 0 else 0) * 0.3 +
            div_var * 0.3 +
            hash_divergence * 0.4
        )

        dimension_results.append(DimensionCorrelationResult(
            dimension_index=dim_idx,
            dimension_name=PPV_DIM_NAMES[dim_idx],
            length_variance=length_var,
            token_diversity_variance=div_var,
            hash_divergence_rate=hash_divergence,
            correlation_strength=correlation,
        ))

    # Find strongest and weakest
    sorted_dims = sorted(dimension_results, key=lambda x: x.correlation_strength, reverse=True)
    strongest = sorted_dims[0].dimension_name
    weakest = sorted_dims[-1].dimension_name

    overall_sensitivity = sum(d.correlation_strength for d in dimension_results) / len(dimension_results)

    return PPVCorrelationAnalysisResult(
        dimension_results=tuple(dimension_results),
        strongest_dimension=strongest,
        weakest_dimension=weakest,
        overall_ppv_sensitivity=overall_sensitivity,
    )


# =============================================================================
# 4. OPEN vs GOVERNED Divergence Analysis
# =============================================================================


@dataclass(frozen=True)
class ModeDivergenceResult:
    """Result of OPEN vs GOVERNED mode divergence analysis."""
    total_comparisons: int
    divergent_count: int
    divergence_rate: float  # Fraction of inputs that produce different outputs
    avg_length_divergence: float  # Average difference in output length
    avg_hash_similarity: float  # How often hashes match
    amplifying_dimensions: Tuple[str, ...]  # Dimensions that amplify divergence
    dimension_divergence_rates: Dict[str, float]


def analyze_mode_divergence(runner: Phase11B1AnalysisRunner) -> ModeDivergenceResult:
    """
    Compare OPEN vs GOVERNED mode outputs for identical structural inputs.
    """
    runner.clear_records()

    comparisons = 0
    divergent = 0
    length_diffs: List[float] = []
    hash_matches = 0

    dimension_divergence: Dict[str, List[bool]] = {name: [] for name in PPV_DIM_NAMES}

    # Test across families and PPV variations
    for family in STRUCTURED_FAMILIES[:5]:
        for dim_idx in range(PPV_DIM_COUNT):
            for val in [0, 4, 7]:  # LOW, MID, HIGH
                ppv = list(NEUTRAL_PPV)
                ppv[dim_idx] = val
                ppv_tuple = tuple(ppv)

                governed = runner.run_single((family.value,), ppv_tuple, RenderMode.GOVERNED)
                open_mode = runner.run_single((family.value,), ppv_tuple, RenderMode.OPEN)

                comparisons += 1

                # Check divergence
                is_divergent = governed.output_hash != open_mode.output_hash
                if is_divergent:
                    divergent += 1
                else:
                    hash_matches += 1

                length_diff = abs(governed.output_length - open_mode.output_length)
                length_diffs.append(length_diff)

                # Track which dimension this was
                dimension_divergence[PPV_DIM_NAMES[dim_idx]].append(is_divergent)

    # Calculate dimension-specific divergence rates
    dim_rates: Dict[str, float] = {}
    amplifying: List[str] = []

    for dim_name, divergences in dimension_divergence.items():
        if divergences:
            rate = sum(1 for d in divergences if d) / len(divergences)
            dim_rates[dim_name] = rate
            if rate > 0.5:  # More than 50% divergent
                amplifying.append(dim_name)

    return ModeDivergenceResult(
        total_comparisons=comparisons,
        divergent_count=divergent,
        divergence_rate=divergent / comparisons if comparisons > 0 else 0,
        avg_length_divergence=sum(length_diffs) / len(length_diffs) if length_diffs else 0,
        avg_hash_similarity=hash_matches / comparisons if comparisons > 0 else 0,
        amplifying_dimensions=tuple(amplifying),
        dimension_divergence_rates=dim_rates,
    )


# =============================================================================
# 5. Minimal Structural Change Analysis
# =============================================================================


@dataclass(frozen=True)
class MinimalChangeResult:
    """Result of minimal structural change analysis."""
    ppv_single_bit_changes_hash: bool  # Does changing one PPV value by 1 change hash?
    ppv_minimum_change_for_hash: int  # Minimum PPV delta to change hash
    ontological_single_change_produces_new_hash: bool
    smallest_change_type: str  # "ppv_single_value" or "ontological_path" or "both"
    examples: Tuple[str, ...]


def analyze_minimal_change(runner: Phase11B1AnalysisRunner) -> MinimalChangeResult:
    """
    Identify the smallest structural change that produces a new output hash.
    """
    runner.clear_records()

    base_path = ("THINKING",)
    base_ppv = NEUTRAL_PPV

    # Get baseline
    baseline = runner.run_single(base_path, base_ppv, RenderMode.GOVERNED)
    baseline_hash = baseline.output_hash

    examples: List[str] = []

    # Test single PPV value change (±1)
    single_bit_changes = False
    min_ppv_delta = None

    for dim in range(PPV_DIM_COUNT):
        for delta in [1, -1, 2, -2, 3, -3]:
            test_ppv = list(base_ppv)
            new_val = test_ppv[dim] + delta
            if 0 <= new_val <= 7:
                test_ppv[dim] = new_val
                record = runner.run_single(base_path, tuple(test_ppv), RenderMode.GOVERNED)

                if record.output_hash != baseline_hash:
                    if abs(delta) == 1:
                        single_bit_changes = True
                    if min_ppv_delta is None or abs(delta) < min_ppv_delta:
                        min_ppv_delta = abs(delta)
                        examples.append(f"PPV dim {dim} change by {delta}: hash changed")
                    break

    # Test ontological path change
    ontological_change = False
    for family in STRUCTURED_FAMILIES:
        if family.value != base_path[0]:
            record = runner.run_single((family.value,), base_ppv, RenderMode.GOVERNED)
            if record.output_hash != baseline_hash:
                ontological_change = True
                examples.append(f"Path change {base_path[0]} -> {family.value}: hash changed")
                break

    # Determine smallest change type
    if single_bit_changes and ontological_change:
        smallest = "both"
    elif single_bit_changes:
        smallest = "ppv_single_value"
    elif ontological_change:
        smallest = "ontological_path"
    else:
        smallest = "none_detected"

    return MinimalChangeResult(
        ppv_single_bit_changes_hash=single_bit_changes,
        ppv_minimum_change_for_hash=min_ppv_delta or 0,
        ontological_single_change_produces_new_hash=ontological_change,
        smallest_change_type=smallest,
        examples=tuple(examples[:5]),
    )


# =============================================================================
# 6. Silent Collapse Detection
# =============================================================================


@dataclass(frozen=True)
class SilentCollapseResult:
    """Result of silent collapse detection."""
    total_unique_inputs: int
    total_unique_outputs: int
    collapse_ratio: float  # unique_outputs / unique_inputs (1.0 = no collapse)
    collapse_groups: Tuple[Tuple[str, int], ...]  # (hash, count) for hashes with count > 1
    worst_collapse_count: int  # Most inputs mapping to same output
    collapse_detected: bool


def detect_silent_collapse(runner: Phase11B1AnalysisRunner) -> SilentCollapseResult:
    """
    Check for silent collapse patterns: multiple distinct inputs producing identical outputs.
    """
    runner.clear_records()

    hash_to_inputs: Dict[str, List[str]] = {}

    # Generate diverse inputs
    ppv_patterns = [
        (0, 0, 0, 0, 0, 0, 0, 0),
        (1, 1, 1, 1, 1, 1, 1, 1),
        (2, 2, 2, 2, 2, 2, 2, 2),
        (3, 3, 3, 3, 3, 3, 3, 3),
        (4, 4, 4, 4, 4, 4, 4, 4),
        (5, 5, 5, 5, 5, 5, 5, 5),
        (6, 6, 6, 6, 6, 6, 6, 6),
        (7, 7, 7, 7, 7, 7, 7, 7),
        (0, 1, 2, 3, 4, 5, 6, 7),
        (7, 6, 5, 4, 3, 2, 1, 0),
        (0, 7, 0, 7, 0, 7, 0, 7),
        (3, 4, 3, 4, 3, 4, 3, 4),
    ]

    for family in STRUCTURED_FAMILIES:
        for ppv in ppv_patterns:
            record = runner.run_single((family.value,), ppv, RenderMode.GOVERNED)

            input_key = f"{family.value}|{ppv}"

            if record.output_hash not in hash_to_inputs:
                hash_to_inputs[record.output_hash] = []
            hash_to_inputs[record.output_hash].append(input_key)

    # Analyze collapse
    total_inputs = sum(len(inputs) for inputs in hash_to_inputs.values())
    total_outputs = len(hash_to_inputs)

    collapse_groups = []
    worst_collapse = 1

    for hash_val, inputs in hash_to_inputs.items():
        if len(inputs) > 1:
            collapse_groups.append((hash_val[:16], len(inputs)))
            worst_collapse = max(worst_collapse, len(inputs))

    # Sort by collapse count descending
    collapse_groups.sort(key=lambda x: x[1], reverse=True)

    return SilentCollapseResult(
        total_unique_inputs=total_inputs,
        total_unique_outputs=total_outputs,
        collapse_ratio=total_outputs / total_inputs if total_inputs > 0 else 0,
        collapse_groups=tuple(collapse_groups[:10]),  # Top 10
        worst_collapse_count=worst_collapse,
        collapse_detected=len(collapse_groups) > 0,
    )


# =============================================================================
# 7. Neutral Baseline Comparison
# =============================================================================


@dataclass(frozen=True)
class NeutralBaselineResult:
    """Result of neutral baseline comparison."""
    neutral_unique_outputs: int
    neutral_output_hash: str
    structured_unique_outputs: int
    structured_total_runs: int
    differentiation_increase: float  # How much more differentiation with structure
    neutral_length: int
    structured_avg_length: float
    structured_length_variance: float


def analyze_neutral_baseline(runner: Phase11B1AnalysisRunner) -> NeutralBaselineResult:
    """
    Compare neutral PPV baseline with structured runs.
    """
    runner.clear_records()

    # Neutral baseline: all PPV values neutral, single path
    neutral_ppv = NEUTRAL_PPV
    neutral_records: List[AnalysisRecord] = []

    for family in STRUCTURED_FAMILIES:
        record = runner.run_single((family.value,), neutral_ppv, RenderMode.GOVERNED)
        neutral_records.append(record)

    neutral_hashes = set(r.output_hash for r in neutral_records)
    neutral_lengths = [r.output_length for r in neutral_records]

    # Structured runs: vary PPV
    structured_records: List[AnalysisRecord] = []

    ppv_patterns = [
        (0, 0, 0, 0, 0, 0, 0, 0),
        (3, 3, 3, 3, 3, 3, 3, 3),
        (7, 7, 7, 7, 7, 7, 7, 7),
        (0, 1, 2, 3, 4, 5, 6, 7),
        (7, 6, 5, 4, 3, 2, 1, 0),
    ]

    for family in STRUCTURED_FAMILIES:
        for ppv in ppv_patterns:
            record = runner.run_single((family.value,), ppv, RenderMode.GOVERNED)
            structured_records.append(record)

    structured_hashes = set(r.output_hash for r in structured_records)
    structured_lengths = [r.output_length for r in structured_records]

    # Calculate metrics
    neutral_unique = len(neutral_hashes)
    structured_unique = len(structured_hashes)

    diff_increase = (structured_unique - neutral_unique) / neutral_unique if neutral_unique > 0 else 0

    avg_structured_len = sum(structured_lengths) / len(structured_lengths) if structured_lengths else 0
    mean_len = avg_structured_len
    len_var = sum((x - mean_len) ** 2 for x in structured_lengths) / len(structured_lengths) if structured_lengths else 0

    return NeutralBaselineResult(
        neutral_unique_outputs=neutral_unique,
        neutral_output_hash=list(neutral_hashes)[0] if neutral_hashes else "",
        structured_unique_outputs=structured_unique,
        structured_total_runs=len(structured_records),
        differentiation_increase=diff_increase,
        neutral_length=neutral_lengths[0] if neutral_lengths else 0,
        structured_avg_length=avg_structured_len,
        structured_length_variance=len_var,
    )


# =============================================================================
# Main Analysis Runner
# =============================================================================


@dataclass
class FullAnalysisReport:
    """Complete analysis report."""
    ceiling_results: Dict[str, CeilingAnalysisResult]
    clustering_result: ClusteringResult
    ppv_correlation_result: PPVCorrelationAnalysisResult
    mode_divergence_result: ModeDivergenceResult
    minimal_change_result: MinimalChangeResult
    silent_collapse_result: SilentCollapseResult
    neutral_baseline_result: NeutralBaselineResult
    total_records: int


def run_full_analysis() -> FullAnalysisReport:
    """Run complete Phase-11B.1 structural analysis."""
    runner = Phase11B1AnalysisRunner()

    print("Running Phase-11B.1 Structural Analysis...")
    print("=" * 60)

    print("\n1. Structural Ceiling Analysis...")
    ceiling = analyze_structural_ceiling(runner)

    print("2. Clustering Analysis...")
    clustering = analyze_clustering(runner)

    print("3. PPV Dimension Correlation...")
    ppv_corr = analyze_ppv_dimension_correlation(runner)

    print("4. OPEN vs GOVERNED Divergence...")
    mode_div = analyze_mode_divergence(runner)

    print("5. Minimal Structural Change...")
    minimal = analyze_minimal_change(runner)

    print("6. Silent Collapse Detection...")
    collapse = detect_silent_collapse(runner)

    print("7. Neutral Baseline Comparison...")
    baseline = analyze_neutral_baseline(runner)

    print("\nAnalysis complete!")
    print("=" * 60)

    return FullAnalysisReport(
        ceiling_results=ceiling,
        clustering_result=clustering,
        ppv_correlation_result=ppv_corr,
        mode_divergence_result=mode_div,
        minimal_change_result=minimal,
        silent_collapse_result=collapse,
        neutral_baseline_result=baseline,
        total_records=len(runner.get_records()),
    )


def print_report(report: FullAnalysisReport) -> str:
    """Generate printable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("PHASE-11B.1 STRUCTURAL ANALYSIS REPORT")
    lines.append("=" * 70)

    # 1. Ceiling Analysis
    lines.append("\n## 1. STRUCTURAL CEILING ANALYSIS")
    lines.append("-" * 50)
    for name, result in report.ceiling_results.items():
        lines.append(f"\n### {result.analysis_type}")
        lines.append(f"  Total variations:     {result.total_variations}")
        lines.append(f"  Unique output hashes: {result.unique_output_hashes}")
        lines.append(f"  Unique template IDs:  {result.unique_template_ids}")
        lines.append(f"  Ceiling ratio:        {result.ceiling_ratio:.3f}")
        if result.saturation_point_ppv:
            lines.append(f"  PPV saturation point: {result.saturation_point_ppv}")

    # 2. Clustering Analysis
    lines.append("\n## 2. CLUSTERING ANALYSIS")
    lines.append("-" * 50)
    c = report.clustering_result
    lines.append(f"  Ontological cluster strength: {c.ontological_cluster_strength:.3f}")
    lines.append(f"  PPV cluster strength:         {c.ppv_cluster_strength:.3f}")
    lines.append(f"  Dominant clustering axis:     {c.dominant_axis.upper()}")
    lines.append(f"  Within-family uniqueness:     {c.within_family_uniqueness:.3f}")
    lines.append(f"  Within-PPV uniqueness:        {c.within_ppv_uniqueness:.3f}")

    # 3. PPV Dimension Correlation
    lines.append("\n## 3. PPV DIMENSION CORRELATION")
    lines.append("-" * 50)
    p = report.ppv_correlation_result
    lines.append(f"  Strongest dimension: {p.strongest_dimension}")
    lines.append(f"  Weakest dimension:   {p.weakest_dimension}")
    lines.append(f"  Overall PPV sensitivity: {p.overall_ppv_sensitivity:.3f}")
    lines.append("\n  Dimension-wise hash divergence rates:")
    for d in sorted(p.dimension_results, key=lambda x: x.hash_divergence_rate, reverse=True):
        lines.append(f"    {d.dimension_name:20s}: {d.hash_divergence_rate:.3f} (len_var: {d.length_variance:.1f})")

    # 4. Mode Divergence
    lines.append("\n## 4. OPEN vs GOVERNED DIVERGENCE")
    lines.append("-" * 50)
    m = report.mode_divergence_result
    lines.append(f"  Total comparisons:        {m.total_comparisons}")
    lines.append(f"  Divergent count:          {m.divergent_count}")
    lines.append(f"  Divergence rate:          {m.divergence_rate:.3f}")
    lines.append(f"  Avg length divergence:    {m.avg_length_divergence:.1f}")
    lines.append(f"  Hash similarity:          {m.avg_hash_similarity:.3f}")
    lines.append(f"  Amplifying dimensions:    {', '.join(m.amplifying_dimensions) or 'None'}")
    if m.dimension_divergence_rates:
        lines.append("\n  Dimension divergence rates:")
        for dim, rate in sorted(m.dimension_divergence_rates.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"    {dim:20s}: {rate:.3f}")

    # 5. Minimal Change
    lines.append("\n## 5. MINIMAL STRUCTURAL CHANGE")
    lines.append("-" * 50)
    mc = report.minimal_change_result
    lines.append(f"  PPV single-bit changes hash:     {mc.ppv_single_bit_changes_hash}")
    lines.append(f"  PPV minimum delta for hash:      {mc.ppv_minimum_change_for_hash}")
    lines.append(f"  Ontological change produces new: {mc.ontological_single_change_produces_new_hash}")
    lines.append(f"  Smallest change type:            {mc.smallest_change_type}")
    if mc.examples:
        lines.append("  Examples:")
        for ex in mc.examples:
            lines.append(f"    - {ex}")

    # 6. Silent Collapse
    lines.append("\n## 6. SILENT COLLAPSE DETECTION")
    lines.append("-" * 50)
    sc = report.silent_collapse_result
    lines.append(f"  Total unique inputs:   {sc.total_unique_inputs}")
    lines.append(f"  Total unique outputs:  {sc.total_unique_outputs}")
    lines.append(f"  Collapse ratio:        {sc.collapse_ratio:.3f} (1.0 = no collapse)")
    lines.append(f"  Collapse detected:     {sc.collapse_detected}")
    lines.append(f"  Worst collapse count:  {sc.worst_collapse_count}")
    if sc.collapse_groups:
        lines.append("  Collapse groups (hash, count):")
        for hash_val, count in sc.collapse_groups[:5]:
            lines.append(f"    {hash_val}: {count} inputs")

    # 7. Neutral Baseline
    lines.append("\n## 7. NEUTRAL BASELINE COMPARISON")
    lines.append("-" * 50)
    nb = report.neutral_baseline_result
    lines.append(f"  Neutral unique outputs:      {nb.neutral_unique_outputs}")
    lines.append(f"  Structured unique outputs:   {nb.structured_unique_outputs}")
    lines.append(f"  Structured total runs:       {nb.structured_total_runs}")
    lines.append(f"  Differentiation increase:    {nb.differentiation_increase:.1%}")
    lines.append(f"  Neutral output length:       {nb.neutral_length}")
    lines.append(f"  Structured avg length:       {nb.structured_avg_length:.1f}")
    lines.append(f"  Structured length variance:  {nb.structured_length_variance:.1f}")

    # Summary
    lines.append("\n" + "=" * 70)
    lines.append("SUMMARY")
    lines.append("=" * 70)
    lines.append(f"  Total analysis records: {report.total_records}")
    lines.append(f"  Dominant clustering:    {c.dominant_axis.upper()}")
    lines.append(f"  Silent collapse:        {'YES - DETECTED' if sc.collapse_detected else 'NO'}")
    lines.append(f"  Minimal change type:    {mc.smallest_change_type}")
    lines.append(f"  Mode divergence rate:   {m.divergence_rate:.1%}")

    return "\n".join(lines)


# =============================================================================
# Entry Point
# =============================================================================


if __name__ == "__main__":
    report = run_full_analysis()
    output = print_report(report)
    print(output)
