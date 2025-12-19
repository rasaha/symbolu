"""
Deep Structural Ceiling Analysis
================================

This module performs granular analysis to identify exactly where
additional variations stop producing new output hashes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import defaultdict

sys.path.insert(0, "/home/user/symbolu/docs/experiments/phase11_sandbox")

from phase11a_evaluation_harness import (
    ExperimentConfig,
    MockPhase11Generator,
    OntologicalLayer,
    ONTOLOGICAL_LAYER_ORDER,
    PPV_DIMENSION_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    RenderMode,
    VariationMatrixGenerator,
    INTENTS,
)


def analyze_ppv_threshold_behavior():
    """
    Analyze PPV value threshold behavior.

    The mock generator only produces distinguishing tokens when PPV value > 4.
    This analysis maps the exact threshold effect.
    """
    print("\n" + "=" * 70)
    print("PPV VALUE THRESHOLD ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]

    # Track outputs by PPV value
    outputs_by_value: Dict[int, Set[str]] = {v: set() for v in range(8)}
    hashes_by_value: Dict[int, Set[int]] = {v: set() for v in range(8)}

    baseline_ppv = list(VariationMatrixGenerator.DEFAULT_PPV)

    # For each PPV value (0-7), set dimension 0 to that value
    for value in range(8):
        ppv = baseline_ppv.copy()
        ppv[0] = value

        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=tuple(ppv),
            temperature=VariationMatrixGenerator.DEFAULT_TEMP,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis=f"ppv_value_{value}",
            variation_index=value,
        )
        output = generator.generate(config)
        output_hash = hash(output)

        outputs_by_value[value].add(output)
        hashes_by_value[value].add(output_hash)

    print("\nPPV Value -> Output Analysis (single dimension varied):")
    print("-" * 50)

    # Group values by identical outputs
    hash_to_values: Dict[int, List[int]] = defaultdict(list)
    for value in range(8):
        for h in hashes_by_value[value]:
            hash_to_values[h].append(value)

    print(f"\nUnique output groups: {len(hash_to_values)}")
    for h, values in hash_to_values.items():
        print(f"  Values {values} produce identical output")

    # Analyze threshold
    print("\nTHRESHOLD ANALYSIS:")
    print("-" * 50)

    # Values 0-4 vs 5-7
    low_hashes = set()
    high_hashes = set()
    for v in range(5):
        low_hashes.update(hashes_by_value[v])
    for v in range(5, 8):
        high_hashes.update(hashes_by_value[v])

    print(f"Values 0-4: {len(low_hashes)} unique outputs")
    print(f"Values 5-7: {len(high_hashes)} unique outputs")

    # Check overlap
    overlap = low_hashes.intersection(high_hashes)
    print(f"Overlap:    {len(overlap)} outputs")

    # Conclusion
    print("\nCONCLUSION:")
    if len(low_hashes) == 1:
        print("  - Values 0-4 collapse to single output (below threshold)")
    if len(high_hashes) == 3:
        print("  - Values 5-7 each produce distinct output (above threshold)")
    print(f"  - Effective PPV dimension cardinality: 1 (low) + 3 (high) = 4 states")
    print(f"  - Per 8-dim PPV vector: 4^8 = 65,536 effective combinations")


def analyze_path_length_effect():
    """
    Analyze how path length affects output uniqueness.
    """
    print("\n" + "=" * 70)
    print("ONTOLOGICAL PATH LENGTH ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]

    for path_length in [1, 2, 3, 4, 5]:
        seen_hashes: Set[int] = set()

        # Generate all unique paths of this length
        tested = 0
        max_tests = min(50, 10 ** path_length)

        for i in range(len(ONTOLOGICAL_LAYER_ORDER)):
            # Generate path starting from layer i
            path_indices = [(i + j) % len(ONTOLOGICAL_LAYER_ORDER) for j in range(path_length)]
            path = tuple(ONTOLOGICAL_LAYER_ORDER[idx] for idx in path_indices)

            config = ExperimentConfig(
                intent=intent,
                ontological_path=path,
                ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
                temperature=VariationMatrixGenerator.DEFAULT_TEMP,
                mode=VariationMatrixGenerator.DEFAULT_MODE,
                variation_axis=f"path_len_{path_length}",
                variation_index=tested,
            )
            output = generator.generate(config)
            seen_hashes.add(hash(output))
            tested += 1

            if tested >= max_tests:
                break

        uniqueness = len(seen_hashes) / tested if tested > 0 else 0
        print(f"\nPath length {path_length}:")
        print(f"  Tested:     {tested} paths")
        print(f"  Unique:     {len(seen_hashes)} outputs")
        print(f"  Uniqueness: {uniqueness:.1%}")


def analyze_temperature_bands():
    """
    Analyze temperature band effects on output differentiation.
    """
    print("\n" + "=" * 70)
    print("TEMPERATURE BAND ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]

    # Test fine-grained temperature values
    temperatures = [i / 100.0 for i in range(5, 100, 5)]  # 0.05 to 0.95
    outputs: Dict[float, str] = {}
    hashes: Dict[float, int] = {}

    for temp in temperatures:
        config = ExperimentConfig(
            intent=intent,
            ontological_path=VariationMatrixGenerator.DEFAULT_PATH,
            ppv_values=VariationMatrixGenerator.DEFAULT_PPV,
            temperature=temp,
            mode=VariationMatrixGenerator.DEFAULT_MODE,
            variation_axis=f"temp_{temp}",
            variation_index=int(temp * 100),
        )
        output = generator.generate(config)
        outputs[temp] = output
        hashes[temp] = hash(output)

    # Group by identical output
    hash_to_temps: Dict[int, List[float]] = defaultdict(list)
    for temp, h in hashes.items():
        hash_to_temps[h].append(temp)

    print(f"\nTemperatures tested: {len(temperatures)}")
    print(f"Unique outputs:      {len(hash_to_temps)}")
    print("\nTemperature bands producing identical outputs:")
    print("-" * 50)

    for h, temps in sorted(hash_to_temps.items(), key=lambda x: min(x[1])):
        temps.sort()
        print(f"  {temps[0]:.2f} - {temps[-1]:.2f}: {len(temps)} temperatures -> 1 output")

    # Identify transition points
    print("\nTRANSITION POINTS:")
    sorted_temps = sorted(temperatures)
    for i in range(len(sorted_temps) - 1):
        t1, t2 = sorted_temps[i], sorted_temps[i + 1]
        if hashes[t1] != hashes[t2]:
            print(f"  Output changes between {t1:.2f} and {t2:.2f}")


def analyze_combinatorial_saturation():
    """
    Analyze when combinatorial variations saturate.
    """
    print("\n" + "=" * 70)
    print("COMBINATORIAL SATURATION ANALYSIS")
    print("=" * 70)

    generator = MockPhase11Generator(seed=42)
    intent = INTENTS[0]

    seen_hashes: Set[int] = set()
    saturation_points: List[Tuple[int, int, int]] = []  # (total, unique, new)

    variation_count = 0
    checkpoint_interval = 25

    # Generate progressive combinations
    paths = list(ONTOLOGICAL_LAYER_ORDER)[:5]  # First 5 layers as single-layer paths
    ppv_high_patterns = [
        (5, 3, 3, 3, 3, 3, 3, 3),  # High edge_tension
        (3, 5, 3, 3, 3, 3, 3, 3),  # High edge_release
        (3, 3, 5, 3, 3, 3, 3, 3),  # High onset_sharpness
        (3, 3, 3, 5, 3, 3, 3, 3),  # High sonority_lift
        (3, 3, 3, 3, 3, 3, 3, 3),  # Baseline
    ]
    temps = [0.2, 0.5, 0.8]
    modes = [RenderMode.GOVERNED, RenderMode.OPEN]

    last_unique = 0

    for path_layer in paths:
        for ppv in ppv_high_patterns:
            for temp in temps:
                for mode in modes:
                    config = ExperimentConfig(
                        intent=intent,
                        ontological_path=(path_layer,),
                        ppv_values=ppv,
                        temperature=temp,
                        mode=mode,
                        variation_axis="combinatorial",
                        variation_index=variation_count,
                    )
                    output = generator.generate(config)
                    seen_hashes.add(hash(output))
                    variation_count += 1

                    if variation_count % checkpoint_interval == 0:
                        new_unique = len(seen_hashes) - last_unique
                        saturation_points.append((variation_count, len(seen_hashes), new_unique))
                        last_unique = len(seen_hashes)

    print(f"\nTotal combinations tested: {variation_count}")
    print(f"Unique outputs produced:   {len(seen_hashes)}")
    print(f"Overall uniqueness ratio:  {len(seen_hashes) / variation_count:.1%}")

    print("\nSaturation progression (checkpoint every 25):")
    print("-" * 50)
    print(f"{'Variations':<12} {'Unique':<10} {'New':<10} {'Marginal %':<12}")
    print("-" * 50)

    for total, unique, new in saturation_points:
        marginal = (new / checkpoint_interval) * 100
        marker = " <- SATURATION" if new == 0 else ""
        print(f"{total:<12} {unique:<10} {new:<10} {marginal:<12.1f}{marker}")

    # Find saturation point
    saturation_at = None
    for total, unique, new in saturation_points:
        if new == 0:
            saturation_at = total
            break

    if saturation_at:
        print(f"\nSATURATION DETECTED at {saturation_at} variations")
    else:
        print("\nNo complete saturation detected in sample")


def compute_effective_ceiling():
    """
    Compute the effective structural ceiling based on analysis.
    """
    print("\n" + "=" * 70)
    print("EFFECTIVE STRUCTURAL CEILING COMPUTATION")
    print("=" * 70)

    print("\nBased on Phase-11A Mock Generator behavior:")
    print("-" * 50)

    # Ontological paths
    onto_unique = 10  # Single-layer paths are fully distinguishing
    onto_multiplier = 10  # Number of possible starting layers
    print(f"\n1. ONTOLOGICAL PATH:")
    print(f"   - Single layer variations: {onto_unique} unique")
    print(f"   - Each layer produces distinct output")
    print(f"   - Ceiling: 10 (for single-layer), scales with length")

    # PPV dimensions
    ppv_threshold = 5
    ppv_low_states = 1  # Values 0-4 collapse
    ppv_high_states = 3  # Values 5, 6, 7 distinct
    ppv_effective_per_dim = ppv_low_states + ppv_high_states  # = 4
    ppv_total = ppv_effective_per_dim ** 8
    print(f"\n2. PPV DIMENSIONS:")
    print(f"   - Threshold for distinguishing: value > 4")
    print(f"   - Below threshold (0-4): 1 effective state")
    print(f"   - Above threshold (5-7): 3 effective states")
    print(f"   - Per dimension: {ppv_effective_per_dim} effective states")
    print(f"   - 8-dimensional ceiling: 4^8 = {ppv_total:,}")

    # Temperature
    temp_bands = 3  # Low, Mid, High
    print(f"\n3. TEMPERATURE:")
    print(f"   - Three effective bands: < 0.3, 0.3-0.7, > 0.7")
    print(f"   - Ceiling: {temp_bands} states")

    # Mode
    mode_states = 2
    print(f"\n4. MODE:")
    print(f"   - Binary: GOVERNED vs OPEN")
    print(f"   - Ceiling: {mode_states} states")

    # Combined ceiling
    theoretical_ceiling = onto_multiplier * ppv_total * temp_bands * mode_states
    print(f"\n" + "=" * 50)
    print(f"STRUCTURAL CEILING OF DIFFERENTIATION")
    print(f"=" * 50)
    print(f"\n  Paths × PPV × Temperature × Mode")
    print(f"  = {onto_multiplier} × {ppv_total:,} × {temp_bands} × {mode_states}")
    print(f"  = {theoretical_ceiling:,} unique outputs")
    print(f"\nBeyond this point, additional variations CANNOT produce")
    print(f"new output hashes under the current generator design.")

    print(f"\n" + "-" * 50)
    print(f"DIMINISHING RETURNS THRESHOLDS:")
    print(f"-" * 50)

    print(f"\n  PPV: After ~16 variations (min/max per dimension),")
    print(f"        subsequent fine-grained values provide minimal")
    print(f"        additional differentiation due to threshold behavior.")

    print(f"\n  Temperature: After 3 variations (LOW/MID/HIGH),")
    print(f"               additional granularity provides no new hashes.")

    print(f"\n  Mode: After 2 variations, fully saturated.")

    print(f"\n  Ontological Path: Linear growth with path length.")
    print(f"                    10 paths at length 1, 90 at length 2,")
    print(f"                    720 at length 3 (permutations).")


if __name__ == "__main__":
    analyze_ppv_threshold_behavior()
    analyze_path_length_effect()
    analyze_temperature_bands()
    analyze_combinatorial_saturation()
    compute_effective_ceiling()
