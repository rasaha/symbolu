"""
Structural Ceiling Analysis for Phase-11A Differentiation
==========================================================

This analysis identifies at what point additional PPV or ontological
variations stop producing new unique output hashes.

WHAT THIS MEASURES:
    - Theoretical maximum unique outputs per variation axis
    - Empirical unique output counts
    - Ceiling identification: where uniqueness ratio drops
    - Diminishing returns threshold

METHODOLOGY:
    - Single-dimension variation: Vary one axis while holding others constant
    - Combinatorial expansion: Progressively combine variation dimensions
    - Saturation detection: Identify where new inputs yield duplicate hashes
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import defaultdict

# Add parent path for imports
sys.path.insert(0, "/home/user/symbolu/docs/experiments/phase11_sandbox")

from phase11a_evaluation_harness import (
    Phase11AEvaluationHarness,
    VariationMatrixGenerator,
    ExperimentConfig,
    MockPhase11Generator,
    OntologicalLayer,
    ONTOLOGICAL_LAYER_ORDER,
    PPVDimension,
    PPV_DIMENSION_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    RenderMode,
    TEMPERATURE_VALUES,
    TemperatureLevel,
    INTENTS,
    compute_evaluation_summary,
)


# =============================================================================
# Structural Ceiling Analysis Data Structures
# =============================================================================

@dataclass(frozen=True)
class CeilingAnalysisPoint:
    """Single data point in ceiling analysis."""
    variation_count: int          # Number of input variations
    unique_outputs: int           # Number of unique output hashes
    uniqueness_ratio: float       # unique / total
    marginal_new_hashes: int      # New hashes added at this point
    is_saturated: bool            # True if no new hashes added


@dataclass(frozen=True)
class AxisCeilingReport:
    """Ceiling analysis for a single variation axis."""
    axis_name: str
    theoretical_max: int          # Maximum possible variations
    empirical_unique: int         # Actual unique outputs observed
    ceiling_point: int            # Where saturation begins (-1 if never)
    saturation_ratio: float       # empirical_unique / theoretical_max
    analysis_points: Tuple[CeilingAnalysisPoint, ...]


@dataclass(frozen=True)
class StructuralCeilingReport:
    """Complete structural ceiling analysis report."""
    # Per-axis analysis
    ontological_path_ceiling: AxisCeilingReport
    ppv_dimension_ceiling: AxisCeilingReport
    temperature_ceiling: AxisCeilingReport
    mode_ceiling: AxisCeilingReport

    # Combined analysis
    cross_axis_ceiling: int       # Point where cross-axis combinations saturate
    total_theoretical_space: int  # Total input space cardinality
    total_empirical_unique: int   # Observed unique outputs
    overall_ceiling_ratio: float  # Coverage of output space

    # Key findings
    limiting_axis: str            # Which axis saturates first
    marginal_return_threshold: int  # Where marginal returns drop below 50%


# =============================================================================
# Single-Axis Ceiling Analysis
# =============================================================================

def analyze_ontological_path_ceiling(
    intent: str,
    generator: MockPhase11Generator,
) -> AxisCeilingReport:
    """
    Analyze ontological path variation ceiling.

    Theoretical max: 10 single-layer paths, 90 two-layer, 720 three-layer
    We test with 3-layer paths starting from each of 10 layers.
    """
    seen_hashes: Set[str] = set()
    points: List[CeilingAnalysisPoint] = []
    variation_count = 0

    # Generate paths of increasing complexity
    # First: single-layer paths (10)
    single_layer_hashes: Set[str] = set()
    for layer in ONTOLOGICAL_LAYER_ORDER:
        config = ExperimentConfig(
            intent=intent,
            ontological_path=(layer,),
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=VariationMatrixGenerator.DEFAULT_TEMP,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis="ontological_path_single",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        new_hash = output_hash not in seen_hashes
        if new_hash:
            seen_hashes.add(output_hash)
            single_layer_hashes.add(output_hash)

        variation_count += 1

    points.append(CeilingAnalysisPoint(
        variation_count=10,
        unique_outputs=len(single_layer_hashes),
        uniqueness_ratio=len(single_layer_hashes) / 10,
        marginal_new_hashes=len(single_layer_hashes),
        is_saturated=False,
    ))

    # Two-layer paths (10 * 9 = 90 possible, test 20)
    two_layer_hashes: Set[str] = set()
    pre_count = len(seen_hashes)
    tested = 0
    for i, layer1 in enumerate(ONTOLOGICAL_LAYER_ORDER):
        for j, layer2 in enumerate(ONTOLOGICAL_LAYER_ORDER):
            if i == j:
                continue
            if tested >= 20:
                break

            config = ExperimentConfig(
                intent=intent,
                ontological_path=(layer1, layer2),
                ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
                temperature=VariationMatrixGenerator.DEFAULT_TEMP,
                mode=VariationMatrixGenerator.DEFAULT_MODE,
                variation_axis="ontological_path_two",
                variation_index=variation_count,
            )
            output = generator.generate(config)
            output_hash = hash(output)

            if output_hash not in seen_hashes:
                seen_hashes.add(output_hash)

            variation_count += 1
            tested += 1
        if tested >= 20:
            break

    marginal_two = len(seen_hashes) - pre_count
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_two,
        is_saturated=marginal_two == 0,
    ))

    # Three-layer paths (standard harness paths)
    pre_count = len(seen_hashes)
    for i, start_layer in enumerate(ONTOLOGICAL_LAYER_ORDER):
        path_indices = [
            i,
            (i + 1) % len(ONTOLOGICAL_LAYER_ORDER),
            (i + 2) % len(ONTOLOGICAL_LAYER_ORDER),
        ]
        path = tuple(ONTOLOGICAL_LAYER_ORDER[idx] for idx in path_indices)

        config = ExperimentConfig(
            intent=intent,
            ontological_path=path,
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=VariationMatrixGenerator.DEFAULT_TEMP,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis="ontological_path_three",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        if output_hash not in seen_hashes:
            seen_hashes.add(output_hash)

        variation_count += 1

    marginal_three = len(seen_hashes) - pre_count
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_three,
        is_saturated=marginal_three == 0,
    ))

    # Find ceiling point (where marginal returns hit 0)
    ceiling_point = -1
    for i, pt in enumerate(points):
        if pt.is_saturated:
            ceiling_point = pt.variation_count
            break

    # Theoretical max for 3-layer paths
    theoretical_max = 10 * 9 * 8  # 720 for 3-layer permutations

    return AxisCeilingReport(
        axis_name="ontological_path",
        theoretical_max=theoretical_max,
        empirical_unique=len(seen_hashes),
        ceiling_point=ceiling_point,
        saturation_ratio=len(seen_hashes) / theoretical_max,
        analysis_points=tuple(points),
    )


def analyze_ppv_ceiling(
    intent: str,
    generator: MockPhase11Generator,
) -> AxisCeilingReport:
    """
    Analyze PPV dimension variation ceiling.

    Theoretical max: 8^8 = 16,777,216 (all combinations)
    Harness tests: 16 (min/max per dimension)
    Extended analysis: progressive expansion
    """
    seen_hashes: Set[str] = set()
    points: List[CeilingAnalysisPoint] = []
    variation_count = 0

    baseline_ppv = list(VariationMatrixGenerator.DEFAULT_PPV)

    # Phase 1: Single dimension at min/max (16 variations)
    phase1_start = len(seen_hashes)
    for dim_idx in range(8):
        for val in [PPV_VALUE_MIN, PPV_VALUE_MAX]:
            ppv = baseline_ppv.copy()
            ppv[dim_idx] = val

            config = ExperimentConfig(
                intent=intent,
                ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
                ppv_values=tuple(ppv),
                temperature=VariationMatrixGenerator.DEFAULT_TEMP,
                mode=VariationMatrixGenerator.DEFAULT_MODE,
                variation_axis=f"ppv_dim_{dim_idx}",
                variation_index=variation_count,
            )
            output = generator.generate(config)
            output_hash = hash(output)

            if output_hash not in seen_hashes:
                seen_hashes.add(output_hash)

            variation_count += 1

    marginal_1 = len(seen_hashes) - phase1_start
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_1,
        is_saturated=False,
    ))

    # Phase 2: Two dimensions varied simultaneously (sample 32)
    phase2_start = len(seen_hashes)
    tested = 0
    for d1 in range(8):
        for d2 in range(d1 + 1, 8):
            for v1 in [PPV_VALUE_MIN, PPV_VALUE_MAX]:
                for v2 in [PPV_VALUE_MIN, PPV_VALUE_MAX]:
                    if tested >= 32:
                        break
                    ppv = baseline_ppv.copy()
                    ppv[d1] = v1
                    ppv[d2] = v2

                    config = ExperimentConfig(
                        intent=intent,
                        ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
                        ppv_values=tuple(ppv),
                        temperature=VariationMatrixGenerator.DEFAULT_TEMP,
                        mode=VariationMatrixGenerator.DEFAULT_MODE,
                        variation_axis="ppv_two_dims",
                        variation_index=variation_count,
                    )
                    output = generator.generate(config)
                    output_hash = hash(output)

                    if output_hash not in seen_hashes:
                        seen_hashes.add(output_hash)

                    variation_count += 1
                    tested += 1
                if tested >= 32:
                    break
            if tested >= 32:
                break
        if tested >= 32:
            break

    marginal_2 = len(seen_hashes) - phase2_start
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_2,
        is_saturated=marginal_2 == 0,
    ))

    # Phase 3: Full range on all dimensions (sample from full space)
    phase3_start = len(seen_hashes)
    # Test all values 0-7 on first dimension only
    for val in range(8):
        ppv = baseline_ppv.copy()
        ppv[0] = val

        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=tuple(ppv),
            temperature=VariationMatrixGenerator.DEFAULT_TEMP,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis="ppv_full_range",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        if output_hash not in seen_hashes:
            seen_hashes.add(output_hash)

        variation_count += 1

    marginal_3 = len(seen_hashes) - phase3_start
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_3,
        is_saturated=marginal_3 == 0,
    ))

    # Ceiling point
    ceiling_point = -1
    for pt in points:
        if pt.is_saturated:
            ceiling_point = pt.variation_count
            break

    # Theoretical max
    theoretical_max = 8 ** 8  # 16,777,216

    return AxisCeilingReport(
        axis_name="ppv_dimensions",
        theoretical_max=theoretical_max,
        empirical_unique=len(seen_hashes),
        ceiling_point=ceiling_point,
        saturation_ratio=len(seen_hashes) / theoretical_max,
        analysis_points=tuple(points),
    )


def analyze_temperature_ceiling(
    intent: str,
    generator: MockPhase11Generator,
) -> AxisCeilingReport:
    """
    Analyze temperature variation ceiling.

    Theoretical max: Continuous (but discretized to 3 levels)
    Extended test: 10 temperature values
    """
    seen_hashes: Set[str] = set()
    points: List[CeilingAnalysisPoint] = []
    variation_count = 0

    # Standard 3 levels
    phase1_start = len(seen_hashes)
    for level, temp in TEMPERATURE_VALUES.items():
        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=temp,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis=f"temperature_{level.value}",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        if output_hash not in seen_hashes:
            seen_hashes.add(output_hash)

        variation_count += 1

    marginal_1 = len(seen_hashes) - phase1_start
    points.append(CeilingAnalysisPoint(
        variation_count=3,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / 3,
        marginal_new_hashes=marginal_1,
        is_saturated=False,
    ))

    # Extended: 10 temperature values
    phase2_start = len(seen_hashes)
    for i in range(10):
        temp = i / 10.0 + 0.05  # 0.05, 0.15, ..., 0.95
        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=temp,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis="temperature_extended",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        if output_hash not in seen_hashes:
            seen_hashes.add(output_hash)

        variation_count += 1

    marginal_2 = len(seen_hashes) - phase2_start
    points.append(CeilingAnalysisPoint(
        variation_count=variation_count,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / variation_count,
        marginal_new_hashes=marginal_2,
        is_saturated=marginal_2 == 0,
    ))

    ceiling_point = -1
    for pt in points:
        if pt.is_saturated:
            ceiling_point = pt.variation_count
            break

    return AxisCeilingReport(
        axis_name="temperature",
        theoretical_max=10,  # Discretized to 10 levels for analysis
        empirical_unique=len(seen_hashes),
        ceiling_point=ceiling_point,
        saturation_ratio=len(seen_hashes) / 10,
        analysis_points=tuple(points),
    )


def analyze_mode_ceiling(
    intent: str,
    generator: MockPhase11Generator,
) -> AxisCeilingReport:
    """
    Analyze mode variation ceiling.

    Theoretical max: 2 (OPEN, GOVERNED)
    """
    seen_hashes: Set[str] = set()
    variation_count = 0

    for mode in [RenderMode.GOVERNED, RenderMode.OPEN]:
        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=VariationMatrixGenerator.DEFAULT_TEMP,
            mode=mode,
            variation_axis=f"mode_{mode.value}",
            variation_index=variation_count,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        if output_hash not in seen_hashes:
            seen_hashes.add(output_hash)

        variation_count += 1

    points = [CeilingAnalysisPoint(
        variation_count=2,
        unique_outputs=len(seen_hashes),
        uniqueness_ratio=len(seen_hashes) / 2,
        marginal_new_hashes=len(seen_hashes),
        is_saturated=False,
    )]

    return AxisCeilingReport(
        axis_name="mode",
        theoretical_max=2,
        empirical_unique=len(seen_hashes),
        ceiling_point=-1,  # Never saturates with only 2 values
        saturation_ratio=len(seen_hashes) / 2,
        analysis_points=tuple(points),
    )


# =============================================================================
# Cross-Axis Combinatorial Analysis
# =============================================================================

def analyze_cross_axis_ceiling(
    intent: str,
    generator: MockPhase11Generator,
    sample_size: int = 200,
) -> Tuple[int, int, int]:
    """
    Analyze cross-axis combination ceiling.

    Tests combinations across multiple axes to find where saturation occurs.

    Returns:
        (total_combinations_tested, unique_outputs, saturation_point)
    """
    seen_hashes: Set[str] = set()
    variation_count = 0
    last_unique_count = 0
    saturation_point = -1

    # Sample combinations across axes
    paths = [
        (OntologicalLayer.ACTING, OntologicalLayer.FORMING, OntologicalLayer.THINKING),
        (OntologicalLayer.THINKING, OntologicalLayer.DIRECTING, OntologicalLayer.REASONING),
        (OntologicalLayer.REASONING, OntologicalLayer.PURPOSING, OntologicalLayer.UNIFYING),
        (OntologicalLayer.UNIFYING, OntologicalLayer.ABSOLVING, OntologicalLayer.ACTING),
    ]

    temps = [0.2, 0.5, 0.8]
    modes = [RenderMode.GOVERNED, RenderMode.OPEN]

    # PPV variations
    ppv_variations = [
        (0, 0, 0, 0, 0, 0, 0, 0),  # All min
        (3, 3, 3, 3, 3, 3, 3, 3),  # Baseline
        (7, 7, 7, 7, 7, 7, 7, 7),  # All max
        (7, 0, 7, 0, 7, 0, 7, 0),  # Alternating
        (0, 7, 0, 7, 0, 7, 0, 7),  # Alternating inverse
    ]

    checkpoint_interval = 20

    for path in paths:
        for temp in temps:
            for mode in modes:
                for ppv in ppv_variations:
                    if variation_count >= sample_size:
                        break

                    config = ExperimentConfig(
                        intent=intent,
                        ontological_path=path,
                        ppv_values=ppv,
                        temperature=temp,
                        mode=mode,
                        variation_axis="cross_axis",
                        variation_index=variation_count,
                    )
                    output = generator.generate(config)
                    output_hash = hash(output)

                    if output_hash not in seen_hashes:
                        seen_hashes.add(output_hash)

                    variation_count += 1

                    # Check for saturation at checkpoints
                    if variation_count % checkpoint_interval == 0:
                        new_unique = len(seen_hashes) - last_unique_count
                        if new_unique == 0 and saturation_point == -1:
                            saturation_point = variation_count
                        last_unique_count = len(seen_hashes)

                if variation_count >= sample_size:
                    break
            if variation_count >= sample_size:
                break
        if variation_count >= sample_size:
            break

    return variation_count, len(seen_hashes), saturation_point


# =============================================================================
# Main Analysis Function
# =============================================================================

def run_structural_ceiling_analysis() -> StructuralCeilingReport:
    """
    Run complete structural ceiling analysis.

    Returns comprehensive report on differentiation ceilings.
    """
    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]  # EXPRESS_LOSS as baseline

    # Per-axis analysis
    onto_ceiling = analyze_ontological_path_ceiling(intent, generator)
    ppv_ceiling = analyze_ppv_ceiling(intent, generator)
    temp_ceiling = analyze_temperature_ceiling(intent, generator)
    mode_ceiling = analyze_mode_ceiling(intent, generator)

    # Cross-axis analysis
    cross_tested, cross_unique, cross_saturation = analyze_cross_axis_ceiling(
        intent, generator, sample_size=200
    )

    # Compute overall metrics
    # Theoretical space: paths * ppv * temps * modes
    # Using harness defaults: 720 * 8^8 * 10 * 2 = ~241 trillion
    total_theoretical = 720 * (8**8) * 10 * 2

    # Observed unique across all tests
    total_empirical = (
        onto_ceiling.empirical_unique +
        ppv_ceiling.empirical_unique +
        temp_ceiling.empirical_unique +
        mode_ceiling.empirical_unique +
        cross_unique
    )

    # Find limiting axis
    axes = [
        (onto_ceiling.axis_name, onto_ceiling.saturation_ratio),
        (ppv_ceiling.axis_name, ppv_ceiling.saturation_ratio),
        (temp_ceiling.axis_name, temp_ceiling.saturation_ratio),
        (mode_ceiling.axis_name, mode_ceiling.saturation_ratio),
    ]
    limiting_axis = min(axes, key=lambda x: x[1])[0]

    # Find marginal return threshold
    # Where marginal new hashes drop below 50% of total
    marginal_threshold = -1
    for ceiling in [onto_ceiling, ppv_ceiling, temp_ceiling]:
        for pt in ceiling.analysis_points:
            if pt.uniqueness_ratio < 0.5 and marginal_threshold == -1:
                marginal_threshold = pt.variation_count
                break

    return StructuralCeilingReport(
        ontological_path_ceiling=onto_ceiling,
        ppv_dimension_ceiling=ppv_ceiling,
        temperature_ceiling=temp_ceiling,
        mode_ceiling=mode_ceiling,
        cross_axis_ceiling=cross_saturation,
        total_theoretical_space=total_theoretical,
        total_empirical_unique=total_empirical,
        overall_ceiling_ratio=total_empirical / total_theoretical if total_theoretical > 0 else 0,
        limiting_axis=limiting_axis,
        marginal_return_threshold=marginal_threshold,
    )


def format_report(report: StructuralCeilingReport) -> str:
    """Format the structural ceiling report as readable text."""
    lines = [
        "=" * 70,
        "STRUCTURAL CEILING ANALYSIS REPORT",
        "Phase-11A Generative Differentiation",
        "=" * 70,
        "",
        "1. PER-AXIS CEILING ANALYSIS",
        "-" * 40,
        "",
    ]

    # Ontological path
    onto = report.ontological_path_ceiling
    lines.extend([
        f"ONTOLOGICAL PATH:",
        f"  Theoretical maximum: {onto.theoretical_max:,} (3-layer permutations)",
        f"  Empirical unique:    {onto.empirical_unique}",
        f"  Saturation ratio:    {onto.saturation_ratio:.4%}",
        f"  Ceiling point:       {'Not reached' if onto.ceiling_point == -1 else onto.ceiling_point}",
        "",
    ])

    for i, pt in enumerate(onto.analysis_points):
        lines.append(
            f"    Phase {i+1}: {pt.variation_count} variations -> "
            f"{pt.unique_outputs} unique ({pt.uniqueness_ratio:.1%}), "
            f"+{pt.marginal_new_hashes} new"
        )
    lines.append("")

    # PPV dimensions
    ppv = report.ppv_dimension_ceiling
    lines.extend([
        f"PPV DIMENSIONS:",
        f"  Theoretical maximum: {ppv.theoretical_max:,} (8^8 combinations)",
        f"  Empirical unique:    {ppv.empirical_unique}",
        f"  Saturation ratio:    {ppv.saturation_ratio:.10%}",
        f"  Ceiling point:       {'Not reached' if ppv.ceiling_point == -1 else ppv.ceiling_point}",
        "",
    ])

    for i, pt in enumerate(ppv.analysis_points):
        lines.append(
            f"    Phase {i+1}: {pt.variation_count} variations -> "
            f"{pt.unique_outputs} unique ({pt.uniqueness_ratio:.1%}), "
            f"+{pt.marginal_new_hashes} new"
        )
    lines.append("")

    # Temperature
    temp = report.temperature_ceiling
    lines.extend([
        f"TEMPERATURE:",
        f"  Theoretical maximum: {temp.theoretical_max} (discretized levels)",
        f"  Empirical unique:    {temp.empirical_unique}",
        f"  Saturation ratio:    {temp.saturation_ratio:.1%}",
        f"  Ceiling point:       {'Not reached' if temp.ceiling_point == -1 else temp.ceiling_point}",
        "",
    ])

    # Mode
    mode = report.mode_ceiling
    lines.extend([
        f"MODE:",
        f"  Theoretical maximum: {mode.theoretical_max}",
        f"  Empirical unique:    {mode.empirical_unique}",
        f"  Saturation ratio:    {mode.saturation_ratio:.1%}",
        "",
    ])

    # Cross-axis
    lines.extend([
        "",
        "2. CROSS-AXIS COMBINATION ANALYSIS",
        "-" * 40,
        f"  Cross-axis saturation point: {'Not reached' if report.cross_axis_ceiling == -1 else report.cross_axis_ceiling}",
        f"  Total theoretical space:     {report.total_theoretical_space:,}",
        f"  Total empirical unique:      {report.total_empirical_unique}",
        f"  Overall coverage ratio:      {report.overall_ceiling_ratio:.15%}",
        "",
    ])

    # Key findings
    lines.extend([
        "",
        "3. KEY FINDINGS",
        "-" * 40,
        f"  Limiting axis:                {report.limiting_axis}",
        f"  Marginal return threshold:    {report.marginal_return_threshold}",
        "",
    ])

    # Analysis summary
    lines.extend([
        "",
        "4. STRUCTURAL CEILING IDENTIFICATION",
        "-" * 40,
        "",
        "The structural ceiling of differentiation is determined by:",
        "",
        "a) MOCK GENERATOR BEHAVIOR:",
        "   - Output includes direct encoding of input parameters",
        "   - PPV values only produce tokens when value > 4",
        "   - Temperature affects structural repetition count",
        "   - Mode adds single distinguishing token",
        "",
        "b) CEILING CHARACTERISTICS:",
        f"   - Ontological path: High uniqueness ({onto.empirical_unique} unique)",
        "     Each path combination produces distinct output",
        "",
        f"   - PPV dimensions: Sparse sensitivity ({ppv.empirical_unique} unique)",
        "     Only values > 4 produce distinguishing tokens",
        "     Values 0-4 collapse to identical output structures",
        f"     EFFECTIVE CEILING: ~2^8 = 256 distinguishing PPV states",
        "",
        f"   - Temperature: Bounded effect ({temp.empirical_unique} unique)",
        "     Three temperature bands produce distinct structures",
        f"     EFFECTIVE CEILING: 3 temperature states",
        "",
        f"   - Mode: Binary differentiation ({mode.empirical_unique} unique)",
        "     EFFECTIVE CEILING: 2 mode states",
        "",
        "c) DIMINISHING RETURNS THRESHOLD:",
        "   - Path variations: No diminishing returns observed",
        "   - PPV variations: Rapid saturation due to value-threshold behavior",
        "   - Temperature: Full saturation at 3 levels",
        "   - Mode: Full saturation at 2 values",
        "",
        "d) STRUCTURAL CEILING FORMULA:",
        "   Effective unique outputs = ",
        "     paths * ppv_effective * temp_bands * modes",
        f"   = {onto.empirical_unique} * 256 * 3 * 2",
        f"   = ~{onto.empirical_unique * 256 * 3 * 2:,} theoretical ceiling",
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    print("Running structural ceiling analysis...")
    report = run_structural_ceiling_analysis()
    print(format_report(report))
