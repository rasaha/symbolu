"""
Phase-11B.2 Structural Analysis
================================

Comprehensive structural analysis of Phase-11B.2 routing behavior:

1. Structural Ceiling of Differentiation
   - When do additional PPV/ontological variations stop producing new hashes?

2. Output Clustering Analysis
   - Do outputs cluster by ontological layer or PPV more strongly?

3. PPV Dimension Correlation Analysis
   - Which PPV dimensions most strongly correlate with surface changes?

4. OPEN vs GOVERNED Mode Divergence
   - Divergence rate, magnitude, and amplifying dimensions

5. Minimum Structural Change Detection
   - Smallest change that produces a new output hash

6. Silent Collapse Pattern Detection
   - Multiple distinct inputs producing identical outputs

7. Neutral Baseline Comparison
   - Differentiation with neutral PPV vs structured runs

CONSTRAINTS:
    - No external LLM calls
    - No ML/NLP imports
    - Deterministic only
    - Uses only Phase-11B.2 structural data (no semantics)
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from phase11b1_routing import (
    PPVSubBand,
    OntologicalFamily,
    SlotPlan,
    RenderMode,
    PPV_DIM_COUNT,
)

from phase11b2_canonicalization import (
    ACCEPTED_FAMILIES,
    ACCEPTED_SLOT_PLANS,
    CANONICAL_SIGNATURES,
    Phase11B2Request,
    Phase11B2Response,
    execute_phase11b2,
    canonicalize_variant_id,
)


# =============================================================================
# Analysis Data Structures
# =============================================================================

@dataclass(frozen=True)
class StructuralInput:
    """Represents a structural input for analysis."""
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    mode: RenderMode

    def input_hash(self) -> str:
        """Compute deterministic hash of input."""
        canonical = f"{self.ontological_path}|{self.ppv_values}|{self.mode.value}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class AnalysisRecord:
    """Record of a single analysis run."""
    input: StructuralInput
    output_hash: str
    template_id: str
    canonical_signature: str
    raw_signature: str
    canonicalization_applied: bool
    is_blocked: bool


@dataclass
class CeilingAnalysisResult:
    """Results of structural ceiling analysis."""
    total_inputs: int
    unique_outputs: int
    saturation_ratio: float
    saturation_point_ppv: Optional[int]  # Number of PPV variations at saturation
    saturation_point_family: Optional[int]  # Number of families at saturation
    marginal_yield_by_ppv_count: Dict[int, float]  # PPV variation count -> new hashes ratio
    marginal_yield_by_family_count: Dict[int, float]


@dataclass
class ClusteringAnalysisResult:
    """Results of output clustering analysis."""
    family_cluster_strength: float  # How strongly outputs cluster by family
    ppv_cluster_strength: float  # How strongly outputs cluster by PPV
    dominant_clustering_axis: str  # "FAMILY", "PPV", or "BALANCED"
    family_homogeneity: Dict[str, float]  # Per-family output homogeneity
    ppv_pattern_homogeneity: Dict[str, float]  # Per-PPV-pattern output homogeneity
    cross_entropy_family: float
    cross_entropy_ppv: float


@dataclass
class PPVCorrelationResult:
    """Results of PPV dimension correlation analysis."""
    dimension_impact: Dict[int, float]  # Dimension index -> impact score
    strongest_dimension: int
    weakest_dimension: int
    dimension_names: Tuple[str, ...]
    single_flip_divergence: Dict[int, int]  # Dimension -> count of hash changes
    dimension_contribution_ratio: Dict[int, float]


@dataclass
class ModeComparisonResult:
    """Results of OPEN vs GOVERNED comparison."""
    total_comparisons: int
    divergence_count: int
    divergence_rate: float
    output_matches: int
    template_matches: int
    trace_content_matches: int
    amplifying_dimensions: List[int]  # PPV dimensions that amplify divergence
    divergence_by_family: Dict[str, int]


@dataclass
class MinimalChangeResult:
    """Results of minimum structural change analysis."""
    minimal_ppv_change: int  # Minimum PPV delta for hash change
    minimal_ppv_dimension: int  # Which dimension
    minimal_family_change: bool  # Does family change alone produce new hash?
    examples: List[Tuple[StructuralInput, StructuralInput, str, str]]  # (input1, input2, hash1, hash2)


@dataclass
class SilentCollapseResult:
    """Results of silent collapse detection."""
    collapse_detected: bool
    collapse_count: int
    collapse_groups: Dict[str, List[StructuralInput]]  # output_hash -> list of inputs
    worst_collapse_size: int
    collapse_rate: float


@dataclass
class NeutralBaselineResult:
    """Results of neutral baseline comparison."""
    neutral_unique_outputs: int
    structured_unique_outputs: int
    differentiation_ratio_neutral: float
    differentiation_ratio_structured: float
    differentiation_improvement: float


# =============================================================================
# Analysis Engine
# =============================================================================

class Phase11B2StructuralAnalyzer:
    """Engine for comprehensive structural analysis of Phase-11B.2."""

    PPV_DIMENSION_NAMES = (
        "edge_tension",
        "edge_release",
        "onset_sharpness",
        "sonority_lift",
        "continuity",
        "discontinuity",
        "rhythmic_impulse",
        "stability_pressure",
    )

    def __init__(self) -> None:
        self.records: List[AnalysisRecord] = []
        self._cache: Dict[str, AnalysisRecord] = {}

    def _make_artifact_hash(self, seed: str) -> str:
        """Create deterministic 64-char artifact hash."""
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def run_single(self, input: StructuralInput) -> AnalysisRecord:
        """Run a single analysis and cache result."""
        cache_key = input.input_hash()
        if cache_key in self._cache:
            return self._cache[cache_key]

        request = Phase11B2Request(
            artifact_id=f"analysis-{cache_key}",
            artifact_hash=self._make_artifact_hash(cache_key),
            ontological_path=input.ontological_path,
            ppv_values=input.ppv_values,
            render_mode=input.mode,
            vc_source_data={
                "vc_1_data": "analysis_datum_1",
                "vc_2_data": "analysis_datum_2",
                "vc_3_data": "analysis_datum_3",
                "vc_4_data": "analysis_datum_4",
                "vc_5_data": "analysis_datum_5",
            },
        )

        response = execute_phase11b2(request)

        record = AnalysisRecord(
            input=input,
            output_hash=response.output_hash(),
            template_id=response.template_id,
            canonical_signature=response.routing_trace.canonical_signature,
            raw_signature=response.routing_trace.raw_signature,
            canonicalization_applied=response.routing_trace.canonicalization_applied,
            is_blocked=response.is_blocked(),
        )

        self._cache[cache_key] = record
        self.records.append(record)
        return record

    def generate_ppv_variations(self, count: int = 100) -> List[Tuple[int, ...]]:
        """Generate diverse PPV value combinations."""
        variations: List[Tuple[int, ...]] = []

        # All same values (8 variations)
        for v in range(8):
            variations.append(tuple([v] * 8))

        # Gradients
        variations.append((0, 1, 2, 3, 4, 5, 6, 7))
        variations.append((7, 6, 5, 4, 3, 2, 1, 0))

        # Alternating patterns
        for low, high in [(0, 7), (1, 6), (2, 5), (3, 4)]:
            variations.append(tuple(low if i % 2 == 0 else high for i in range(8)))

        # Single dimension variations
        base = (4, 4, 4, 4, 4, 4, 4, 4)
        for dim in range(8):
            for val in range(8):
                if val != 4:
                    new_ppv = list(base)
                    new_ppv[dim] = val
                    variations.append(tuple(new_ppv))

        # Random-like deterministic patterns
        for seed in range(20):
            ppv = tuple((seed * 7 + i * 3) % 8 for i in range(8))
            variations.append(ppv)

        return list(set(variations))[:count]

    # =========================================================================
    # Analysis 1: Structural Ceiling of Differentiation
    # =========================================================================

    def analyze_structural_ceiling(self) -> CeilingAnalysisResult:
        """
        Analyze when additional variations stop producing new output hashes.
        """
        families = list(ACCEPTED_FAMILIES)
        ppv_variations = self.generate_ppv_variations(200)

        seen_hashes: Set[str] = set()
        marginal_ppv: Dict[int, float] = {}
        marginal_family: Dict[int, float] = {}

        # Analyze PPV ceiling with fixed family
        family = OntologicalFamily.THINKING
        for i, ppv in enumerate(ppv_variations):
            input = StructuralInput(
                ontological_path=(family.value,),
                ppv_values=ppv,
                mode=RenderMode.GOVERNED,
            )
            record = self.run_single(input)
            if not record.is_blocked:
                prev_count = len(seen_hashes)
                seen_hashes.add(record.output_hash)
                new_count = len(seen_hashes)

                if (i + 1) % 10 == 0:
                    marginal_ppv[i + 1] = (new_count - prev_count) / 10

        ppv_saturation_point = None
        for count, yield_rate in sorted(marginal_ppv.items()):
            if yield_rate < 0.1:  # Less than 10% new hashes
                ppv_saturation_point = count
                break

        # Analyze family ceiling with fixed PPV
        seen_hashes_family: Set[str] = set()
        ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        for i, family in enumerate(families):
            input = StructuralInput(
                ontological_path=(family.value,),
                ppv_values=ppv,
                mode=RenderMode.GOVERNED,
            )
            record = self.run_single(input)
            if not record.is_blocked:
                prev_count = len(seen_hashes_family)
                seen_hashes_family.add(record.output_hash)
                new_count = len(seen_hashes_family)
                marginal_family[i + 1] = new_count - prev_count

        family_saturation_point = None
        for count, yield_rate in sorted(marginal_family.items()):
            if yield_rate == 0:
                family_saturation_point = count
                break

        # Combined analysis
        all_hashes: Set[str] = set()
        for family in families:
            for ppv in ppv_variations[:50]:
                input = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)
                if not record.is_blocked:
                    all_hashes.add(record.output_hash)

        total_inputs = len(families) * min(50, len(ppv_variations))
        unique_outputs = len(all_hashes)

        return CeilingAnalysisResult(
            total_inputs=total_inputs,
            unique_outputs=unique_outputs,
            saturation_ratio=unique_outputs / total_inputs if total_inputs > 0 else 0,
            saturation_point_ppv=ppv_saturation_point,
            saturation_point_family=family_saturation_point,
            marginal_yield_by_ppv_count=marginal_ppv,
            marginal_yield_by_family_count=marginal_family,
        )

    # =========================================================================
    # Analysis 2: Output Clustering
    # =========================================================================

    def analyze_clustering(self) -> ClusteringAnalysisResult:
        """
        Determine whether outputs cluster by ontological layer or PPV.
        """
        families = list(ACCEPTED_FAMILIES)
        ppv_variations = self.generate_ppv_variations(50)

        # Collect outputs by family
        outputs_by_family: Dict[str, Set[str]] = defaultdict(set)
        # Collect outputs by canonical signature
        outputs_by_signature: Dict[str, Set[str]] = defaultdict(set)

        all_outputs: Set[str] = set()

        for family in families:
            for ppv in ppv_variations:
                input = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)
                if not record.is_blocked:
                    outputs_by_family[family.value].add(record.output_hash)
                    outputs_by_signature[record.canonical_signature].add(record.output_hash)
                    all_outputs.add(record.output_hash)

        total_unique = len(all_outputs)

        # Calculate family homogeneity (how many unique outputs per family)
        family_homogeneity: Dict[str, float] = {}
        for family, hashes in outputs_by_family.items():
            # Homogeneity = 1 - (unique_in_family / total_unique)
            family_homogeneity[family] = 1 - (len(hashes) / max(1, total_unique))

        # Calculate PPV pattern homogeneity
        ppv_pattern_homogeneity: Dict[str, float] = {}
        for sig, hashes in outputs_by_signature.items():
            ppv_pattern_homogeneity[sig[:16]] = 1 - (len(hashes) / max(1, total_unique))

        # Calculate cluster strength
        # Family cluster strength: how much does knowing family reduce output entropy?
        avg_family_unique = sum(len(h) for h in outputs_by_family.values()) / len(outputs_by_family)
        family_cluster_strength = 1 - (avg_family_unique / max(1, total_unique))

        # PPV cluster strength
        if outputs_by_signature:
            avg_sig_unique = sum(len(h) for h in outputs_by_signature.values()) / len(outputs_by_signature)
            ppv_cluster_strength = 1 - (avg_sig_unique / max(1, total_unique))
        else:
            ppv_cluster_strength = 0

        # Determine dominant axis
        if abs(family_cluster_strength - ppv_cluster_strength) < 0.1:
            dominant = "BALANCED"
        elif family_cluster_strength > ppv_cluster_strength:
            dominant = "FAMILY"
        else:
            dominant = "PPV"

        # Cross-entropy approximation
        cross_entropy_family = sum(len(h) for h in outputs_by_family.values()) / max(1, len(all_outputs))
        cross_entropy_ppv = sum(len(h) for h in outputs_by_signature.values()) / max(1, len(all_outputs))

        return ClusteringAnalysisResult(
            family_cluster_strength=family_cluster_strength,
            ppv_cluster_strength=ppv_cluster_strength,
            dominant_clustering_axis=dominant,
            family_homogeneity=family_homogeneity,
            ppv_pattern_homogeneity=dict(list(ppv_pattern_homogeneity.items())[:10]),
            cross_entropy_family=cross_entropy_family,
            cross_entropy_ppv=cross_entropy_ppv,
        )

    # =========================================================================
    # Analysis 3: PPV Dimension Correlation
    # =========================================================================

    def analyze_ppv_correlations(self) -> PPVCorrelationResult:
        """
        Quantify which PPV dimensions most strongly correlate with output changes.
        """
        base_ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        family = OntologicalFamily.THINKING

        # Get base output
        base_input = StructuralInput(
            ontological_path=(family.value,),
            ppv_values=base_ppv,
            mode=RenderMode.GOVERNED,
        )
        base_record = self.run_single(base_input)
        base_hash = base_record.output_hash

        # Track changes per dimension
        single_flip_divergence: Dict[int, int] = {i: 0 for i in range(8)}
        dimension_impact: Dict[int, float] = {}

        for dim in range(8):
            changes = 0
            for val in range(8):
                if val == 4:
                    continue

                new_ppv = list(base_ppv)
                new_ppv[dim] = val
                input = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=tuple(new_ppv),
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)

                if not record.is_blocked and record.output_hash != base_hash:
                    changes += 1
                    single_flip_divergence[dim] += 1

            dimension_impact[dim] = changes / 7  # 7 possible changes per dimension

        # Calculate contribution ratios
        total_changes = sum(single_flip_divergence.values())
        dimension_contribution_ratio = {
            dim: count / max(1, total_changes)
            for dim, count in single_flip_divergence.items()
        }

        strongest = max(dimension_impact, key=dimension_impact.get)
        weakest = min(dimension_impact, key=dimension_impact.get)

        return PPVCorrelationResult(
            dimension_impact=dimension_impact,
            strongest_dimension=strongest,
            weakest_dimension=weakest,
            dimension_names=self.PPV_DIMENSION_NAMES,
            single_flip_divergence=single_flip_divergence,
            dimension_contribution_ratio=dimension_contribution_ratio,
        )

    # =========================================================================
    # Analysis 4: OPEN vs GOVERNED Mode Comparison
    # =========================================================================

    def analyze_mode_divergence(self) -> ModeComparisonResult:
        """
        Compare OPEN vs GOVERNED outputs for identical structural inputs.
        """
        families = list(ACCEPTED_FAMILIES)
        ppv_variations = self.generate_ppv_variations(30)

        total = 0
        divergence_count = 0
        output_matches = 0
        template_matches = 0
        trace_content_matches = 0
        divergence_by_family: Dict[str, int] = defaultdict(int)
        divergence_by_dimension: Dict[int, int] = defaultdict(int)

        for family in families:
            for ppv in ppv_variations:
                input_open = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.OPEN,
                )
                input_governed = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.GOVERNED,
                )

                record_open = self.run_single(input_open)
                record_governed = self.run_single(input_governed)

                total += 1

                # Compare outputs
                if record_open.output_hash == record_governed.output_hash:
                    output_matches += 1
                else:
                    divergence_count += 1
                    divergence_by_family[family.value] += 1
                    # Track which PPV dimensions might amplify divergence
                    for dim, val in enumerate(ppv):
                        if val != 4:  # Non-neutral value
                            divergence_by_dimension[dim] += 1

                if record_open.template_id == record_governed.template_id:
                    template_matches += 1

                if record_open.canonical_signature == record_governed.canonical_signature:
                    trace_content_matches += 1

        # Identify amplifying dimensions
        amplifying_dimensions = [
            dim for dim, count in divergence_by_dimension.items()
            if count > divergence_count * 0.2  # More than 20% of divergences
        ]

        return ModeComparisonResult(
            total_comparisons=total,
            divergence_count=divergence_count,
            divergence_rate=divergence_count / max(1, total),
            output_matches=output_matches,
            template_matches=template_matches,
            trace_content_matches=trace_content_matches,
            amplifying_dimensions=amplifying_dimensions,
            divergence_by_family=dict(divergence_by_family),
        )

    # =========================================================================
    # Analysis 5: Minimum Structural Change
    # =========================================================================

    def analyze_minimal_change(self) -> MinimalChangeResult:
        """
        Identify the smallest structural change that produces a new output hash.
        """
        examples: List[Tuple[StructuralInput, StructuralInput, str, str]] = []

        # Test single PPV value changes
        base_ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        family = OntologicalFamily.THINKING

        base_input = StructuralInput(
            ontological_path=(family.value,),
            ppv_values=base_ppv,
            mode=RenderMode.GOVERNED,
        )
        base_record = self.run_single(base_input)

        minimal_ppv_change = 8  # Maximum possible
        minimal_ppv_dimension = -1

        for dim in range(8):
            for delta in [1, -1, 2, -2, 3, -3]:
                new_val = 4 + delta
                if 0 <= new_val <= 7:
                    new_ppv = list(base_ppv)
                    new_ppv[dim] = new_val
                    input = StructuralInput(
                        ontological_path=(family.value,),
                        ppv_values=tuple(new_ppv),
                        mode=RenderMode.GOVERNED,
                    )
                    record = self.run_single(input)

                    if not record.is_blocked and record.output_hash != base_record.output_hash:
                        if abs(delta) < minimal_ppv_change:
                            minimal_ppv_change = abs(delta)
                            minimal_ppv_dimension = dim
                            examples.append((
                                base_input,
                                input,
                                base_record.output_hash,
                                record.output_hash,
                            ))

        # Test family change alone
        family_change_produces_new_hash = False
        for other_family in ACCEPTED_FAMILIES:
            if other_family != family:
                input = StructuralInput(
                    ontological_path=(other_family.value,),
                    ppv_values=base_ppv,
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)

                if not record.is_blocked and record.output_hash != base_record.output_hash:
                    family_change_produces_new_hash = True
                    examples.append((
                        base_input,
                        input,
                        base_record.output_hash,
                        record.output_hash,
                    ))
                    break

        return MinimalChangeResult(
            minimal_ppv_change=minimal_ppv_change,
            minimal_ppv_dimension=minimal_ppv_dimension,
            minimal_family_change=family_change_produces_new_hash,
            examples=examples[:5],
        )

    # =========================================================================
    # Analysis 6: Silent Collapse Detection
    # =========================================================================

    def detect_silent_collapse(self) -> SilentCollapseResult:
        """
        Check for cases where multiple distinct inputs produce identical outputs.
        """
        families = list(ACCEPTED_FAMILIES)
        ppv_variations = self.generate_ppv_variations(100)

        output_to_inputs: Dict[str, List[StructuralInput]] = defaultdict(list)

        for family in families:
            for ppv in ppv_variations:
                input = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)

                if not record.is_blocked:
                    output_to_inputs[record.output_hash].append(input)

        # Find collapse groups (outputs with multiple inputs)
        collapse_groups = {
            hash: inputs
            for hash, inputs in output_to_inputs.items()
            if len(inputs) > 1
        }

        total_inputs = sum(len(inputs) for inputs in output_to_inputs.values())
        collapsed_inputs = sum(len(inputs) for inputs in collapse_groups.values())

        worst_collapse = max(
            (len(inputs) for inputs in collapse_groups.values()),
            default=0
        )

        return SilentCollapseResult(
            collapse_detected=len(collapse_groups) > 0,
            collapse_count=len(collapse_groups),
            collapse_groups={k: v[:3] for k, v in list(collapse_groups.items())[:5]},
            worst_collapse_size=worst_collapse,
            collapse_rate=collapsed_inputs / max(1, total_inputs),
        )

    # =========================================================================
    # Analysis 7: Neutral Baseline Comparison
    # =========================================================================

    def analyze_neutral_baseline(self) -> NeutralBaselineResult:
        """
        Compare differentiation with neutral PPV vs structured runs.
        """
        families = list(ACCEPTED_FAMILIES)

        # Neutral run: all PPV values at 4 (neutral/middle)
        neutral_hashes: Set[str] = set()
        neutral_ppv = (4, 4, 4, 4, 4, 4, 4, 4)

        for family in families:
            input = StructuralInput(
                ontological_path=(family.value,),
                ppv_values=neutral_ppv,
                mode=RenderMode.GOVERNED,
            )
            record = self.run_single(input)
            if not record.is_blocked:
                neutral_hashes.add(record.output_hash)

        neutral_unique = len(neutral_hashes)
        neutral_total = len(families)

        # Structured run: varied PPV values
        structured_hashes: Set[str] = set()
        ppv_variations = self.generate_ppv_variations(20)

        for family in families:
            for ppv in ppv_variations:
                input = StructuralInput(
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    mode=RenderMode.GOVERNED,
                )
                record = self.run_single(input)
                if not record.is_blocked:
                    structured_hashes.add(record.output_hash)

        structured_unique = len(structured_hashes)
        structured_total = len(families) * len(ppv_variations)

        neutral_ratio = neutral_unique / max(1, neutral_total)
        structured_ratio = structured_unique / max(1, structured_total)

        improvement = (structured_ratio - neutral_ratio) / max(0.001, neutral_ratio)

        return NeutralBaselineResult(
            neutral_unique_outputs=neutral_unique,
            structured_unique_outputs=structured_unique,
            differentiation_ratio_neutral=neutral_ratio,
            differentiation_ratio_structured=structured_ratio,
            differentiation_improvement=improvement,
        )

    # =========================================================================
    # Run All Analyses
    # =========================================================================

    def run_full_analysis(self) -> Dict:
        """Run all analyses and return comprehensive results."""
        print("Running Phase-11B.2 Structural Analysis...")
        print("-" * 60)

        print("\n[1/7] Analyzing structural ceiling...")
        ceiling = self.analyze_structural_ceiling()

        print("[2/7] Analyzing output clustering...")
        clustering = self.analyze_clustering()

        print("[3/7] Analyzing PPV dimension correlations...")
        ppv_corr = self.analyze_ppv_correlations()

        print("[4/7] Analyzing OPEN vs GOVERNED divergence...")
        mode_div = self.analyze_mode_divergence()

        print("[5/7] Analyzing minimum structural change...")
        minimal = self.analyze_minimal_change()

        print("[6/7] Detecting silent collapse patterns...")
        collapse = self.detect_silent_collapse()

        print("[7/7] Analyzing neutral baseline...")
        baseline = self.analyze_neutral_baseline()

        return {
            "ceiling": ceiling,
            "clustering": clustering,
            "ppv_correlation": ppv_corr,
            "mode_divergence": mode_div,
            "minimal_change": minimal,
            "silent_collapse": collapse,
            "neutral_baseline": baseline,
        }


# =============================================================================
# Report Generation
# =============================================================================

def generate_analysis_report(results: Dict) -> str:
    """Generate human-readable analysis report."""
    lines = []
    lines.append("=" * 70)
    lines.append("PHASE-11B.2 STRUCTURAL ANALYSIS REPORT")
    lines.append("=" * 70)

    # 1. Structural Ceiling
    ceiling = results["ceiling"]
    lines.append("\n## 1. STRUCTURAL CEILING OF DIFFERENTIATION")
    lines.append("-" * 50)
    lines.append(f"Total inputs tested: {ceiling.total_inputs}")
    lines.append(f"Unique outputs produced: {ceiling.unique_outputs}")
    lines.append(f"Saturation ratio: {ceiling.saturation_ratio:.2%}")
    lines.append(f"PPV saturation point: {ceiling.saturation_point_ppv or 'Not reached'}")
    lines.append(f"Family saturation point: {ceiling.saturation_point_family or 'Not reached'}")
    lines.append("")
    lines.append("FINDING: " + (
        "Output space saturates rapidly - additional variations yield diminishing returns"
        if ceiling.saturation_ratio < 0.5
        else "Output space has high capacity - variations produce diverse outputs"
    ))

    # 2. Clustering Analysis
    clustering = results["clustering"]
    lines.append("\n## 2. OUTPUT CLUSTERING ANALYSIS")
    lines.append("-" * 50)
    lines.append(f"Family cluster strength: {clustering.family_cluster_strength:.3f}")
    lines.append(f"PPV cluster strength: {clustering.ppv_cluster_strength:.3f}")
    lines.append(f"Dominant clustering axis: {clustering.dominant_clustering_axis}")
    lines.append(f"Cross-entropy (family): {clustering.cross_entropy_family:.3f}")
    lines.append(f"Cross-entropy (PPV): {clustering.cross_entropy_ppv:.3f}")
    lines.append("")
    lines.append("FINDING: Outputs cluster more strongly by " +
                 clustering.dominant_clustering_axis.lower() +
                 " than the other axis.")

    # 3. PPV Dimension Correlation
    ppv = results["ppv_correlation"]
    lines.append("\n## 3. PPV DIMENSION CORRELATION ANALYSIS")
    lines.append("-" * 50)
    lines.append("Dimension impact scores (higher = more output variation):")
    for dim, impact in sorted(ppv.dimension_impact.items(), key=lambda x: -x[1]):
        name = ppv.dimension_names[dim]
        bar = "#" * int(impact * 20)
        lines.append(f"  [{dim}] {name:20s}: {impact:.3f} {bar}")
    lines.append("")
    lines.append(f"Strongest dimension: [{ppv.strongest_dimension}] {ppv.dimension_names[ppv.strongest_dimension]}")
    lines.append(f"Weakest dimension: [{ppv.weakest_dimension}] {ppv.dimension_names[ppv.weakest_dimension]}")

    # 4. Mode Divergence
    mode = results["mode_divergence"]
    lines.append("\n## 4. OPEN vs GOVERNED MODE COMPARISON")
    lines.append("-" * 50)
    lines.append(f"Total comparisons: {mode.total_comparisons}")
    lines.append(f"Divergence count: {mode.divergence_count}")
    lines.append(f"Divergence rate: {mode.divergence_rate:.2%}")
    lines.append(f"Output matches: {mode.output_matches}")
    lines.append(f"Template matches: {mode.template_matches}")
    lines.append(f"Trace content matches: {mode.trace_content_matches}")
    lines.append("")
    if mode.divergence_rate == 0:
        lines.append("FINDING: MODE IDENTITY LOCK VERIFIED - Zero divergence between OPEN and GOVERNED")
    else:
        lines.append(f"WARNING: Mode divergence detected in {mode.divergence_count} cases")
        if mode.amplifying_dimensions:
            lines.append(f"Amplifying dimensions: {mode.amplifying_dimensions}")

    # 5. Minimal Change
    minimal = results["minimal_change"]
    lines.append("\n## 5. MINIMUM STRUCTURAL CHANGE DETECTION")
    lines.append("-" * 50)
    lines.append(f"Minimal PPV change for new hash: {minimal.minimal_ppv_change} unit(s)")
    if minimal.minimal_ppv_dimension >= 0:
        dim_name = Phase11B2StructuralAnalyzer.PPV_DIMENSION_NAMES[minimal.minimal_ppv_dimension]
        lines.append(f"Most sensitive dimension: [{minimal.minimal_ppv_dimension}] {dim_name}")
    lines.append(f"Family change alone produces new hash: {minimal.minimal_family_change}")
    lines.append("")
    lines.append("FINDING: " + (
        "Single unit changes can produce new hashes - high sensitivity"
        if minimal.minimal_ppv_change == 1
        else f"Requires {minimal.minimal_ppv_change}+ unit change for new hash"
    ))

    # 6. Silent Collapse
    collapse = results["silent_collapse"]
    lines.append("\n## 6. SILENT COLLAPSE PATTERN DETECTION")
    lines.append("-" * 50)
    lines.append(f"Collapse detected: {collapse.collapse_detected}")
    lines.append(f"Collapse count: {collapse.collapse_count}")
    lines.append(f"Worst collapse size: {collapse.worst_collapse_size}")
    lines.append(f"Collapse rate: {collapse.collapse_rate:.2%}")
    lines.append("")
    if collapse.collapse_detected:
        lines.append("WARNING: Silent collapse detected - multiple inputs produce identical outputs")
        lines.append("This is EXPECTED due to canonicalization (by design, not a bug)")
    else:
        lines.append("FINDING: No silent collapse - all distinct inputs produce distinct outputs")

    # 7. Neutral Baseline
    baseline = results["neutral_baseline"]
    lines.append("\n## 7. NEUTRAL BASELINE COMPARISON")
    lines.append("-" * 50)
    lines.append(f"Neutral unique outputs: {baseline.neutral_unique_outputs}")
    lines.append(f"Structured unique outputs: {baseline.structured_unique_outputs}")
    lines.append(f"Neutral differentiation ratio: {baseline.differentiation_ratio_neutral:.2%}")
    lines.append(f"Structured differentiation ratio: {baseline.differentiation_ratio_structured:.2%}")
    lines.append(f"Differentiation improvement: {baseline.differentiation_improvement:.2%}")
    lines.append("")
    lines.append("FINDING: " + (
        "Structured PPV variations improve differentiation over neutral baseline"
        if baseline.differentiation_improvement > 0
        else "Structured PPV variations do not improve differentiation"
    ))

    lines.append("\n" + "=" * 70)
    lines.append("END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

def run_analysis() -> Tuple[Dict, str]:
    """Run full analysis and generate report."""
    analyzer = Phase11B2StructuralAnalyzer()
    results = analyzer.run_full_analysis()
    report = generate_analysis_report(results)
    return results, report


if __name__ == "__main__":
    results, report = run_analysis()
    print(report)
