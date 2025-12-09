#!/usr/bin/env python3
"""
Phase 1 Resonance Fixtures Generator
=====================================

This tool generates canonical fixture data for Phase 1 resonance formulas.

Usage:
    python symbolu/tools/formula_fixtures/generate_phase1_resonance_fixtures.py

Output:
    symbolu/core/formula_drift_tests/phase1_resonance_fixtures.json

IMPORTANT:
    This script is for manual developer use only when intentionally updating
    formulas. CI should NEVER call this script. The fixture file is version-
    controlled and serves as the canonical reference for drift detection.

Version: 1.0
Date: 2025-12-09
"""

import json
from pathlib import Path

from symbolu.formulas.resonance_formulas import (
    compute_smi,
    compute_delta_smi,
    compute_bhava_gap,
    compute_tension_corridor,
)


def round_to_6_decimals(value: float) -> float:
    """Round a float to 6 decimal places for stability."""
    return round(value, 6)


def generate_fixtures():
    """
    Generate canonical test fixtures for Phase 1 resonance formulas.

    Creates a 12-sample grid covering:
    - Low/mid/high dimensional_resonance (0.1, 0.5, 0.9)
    - Low/mid/high vrtti_intensity (0.1, 0.5, 0.9)
    - Low/mid/high bhava_position (0.0, 0.5, 1.0)
    - Bhava gaps: 0, 1, 2, 3, 6 (max), and wrap-around cases
    - Previous SMI values at different levels
    """

    # Define the canonical test grid
    # Each case: (dim_res, vrtti_int, bhava_pos, prev_smi, curr_bhava, prev_bhava, description)
    test_cases = [
        # Case 01: All zeros, first turn (no previous values)
        {
            "id": "case_01",
            "description": "All zeros, first turn (no previous SMI/bhava)",
            "dim_res": 0.0,
            "vrtti_int": 0.0,
            "bhava_pos": 0.0,
            "prev_smi": None,
            "curr_bhava": 0,
            "prev_bhava": None,
        },

        # Case 02: All ones, max values with large bhava gap
        {
            "id": "case_02",
            "description": "All ones, max bhava gap (6 steps)",
            "dim_res": 1.0,
            "vrtti_int": 1.0,
            "bhava_pos": 1.0,
            "prev_smi": 0.5,
            "curr_bhava": 6,
            "prev_bhava": 0,
        },

        # Case 03: All mid values, bhava gap = 0 (same bhava)
        {
            "id": "case_03",
            "description": "All mid values (0.5), same bhava",
            "dim_res": 0.5,
            "vrtti_int": 0.5,
            "bhava_pos": 0.5,
            "prev_smi": 0.4,
            "curr_bhava": 5,
            "prev_bhava": 5,
        },

        # Case 04: Low dim_res, high vrtti, low bhava_pos, bhava gap = 1
        {
            "id": "case_04",
            "description": "Low dim_res, high vrtti, bhava gap = 1",
            "dim_res": 0.1,
            "vrtti_int": 0.9,
            "bhava_pos": 0.0,
            "prev_smi": 0.6,
            "curr_bhava": 3,
            "prev_bhava": 4,
        },

        # Case 05: High dim_res, low vrtti, mid bhava_pos, bhava gap = 2
        {
            "id": "case_05",
            "description": "High dim_res, low vrtti, bhava gap = 2",
            "dim_res": 0.9,
            "vrtti_int": 0.1,
            "bhava_pos": 0.5,
            "prev_smi": 0.3,
            "curr_bhava": 7,
            "prev_bhava": 9,
        },

        # Case 06: Mid dim_res, mid vrtti, high bhava_pos, bhava gap = 3
        {
            "id": "case_06",
            "description": "Mid values, high bhava_pos, bhava gap = 3",
            "dim_res": 0.5,
            "vrtti_int": 0.5,
            "bhava_pos": 1.0,
            "prev_smi": 0.8,
            "curr_bhava": 10,
            "prev_bhava": 7,
        },

        # Case 07: Low all, bhava wrap-around (11 -> 0)
        {
            "id": "case_07",
            "description": "Low values, bhava wrap-around 11->0 (gap=1)",
            "dim_res": 0.1,
            "vrtti_int": 0.1,
            "bhava_pos": 0.0,
            "prev_smi": 0.1,
            "curr_bhava": 0,
            "prev_bhava": 11,
        },

        # Case 08: High dim_res, mid vrtti, low bhava_pos, bhava wrap-around (0 -> 11)
        {
            "id": "case_08",
            "description": "High dim_res, bhava wrap-around 0->11 (gap=1)",
            "dim_res": 0.9,
            "vrtti_int": 0.5,
            "bhava_pos": 0.0,
            "prev_smi": 0.7,
            "curr_bhava": 11,
            "prev_bhava": 0,
        },

        # Case 09: Mixed values, bhava gap = 4 (should use shorter path = 4)
        {
            "id": "case_09",
            "description": "Mixed values, bhava gap = 4",
            "dim_res": 0.3,
            "vrtti_int": 0.7,
            "bhava_pos": 0.5,
            "prev_smi": 0.2,
            "curr_bhava": 2,
            "prev_bhava": 6,
        },

        # Case 10: Mixed values, bhava gap = 5 (close to max)
        {
            "id": "case_10",
            "description": "Mixed values, bhava gap = 5",
            "dim_res": 0.6,
            "vrtti_int": 0.4,
            "bhava_pos": 0.8,
            "prev_smi": 0.9,
            "curr_bhava": 1,
            "prev_bhava": 6,
        },

        # Case 11: Edge case with very low values, SMI decrease
        {
            "id": "case_11",
            "description": "Very low values, SMI decrease",
            "dim_res": 0.1,
            "vrtti_int": 0.2,
            "bhava_pos": 0.1,
            "prev_smi": 0.5,
            "curr_bhava": 4,
            "prev_bhava": 2,
        },

        # Case 12: Edge case with high values, SMI increase
        {
            "id": "case_12",
            "description": "High values, SMI increase",
            "dim_res": 0.8,
            "vrtti_int": 0.9,
            "bhava_pos": 0.9,
            "prev_smi": 0.4,
            "curr_bhava": 8,
            "prev_bhava": 11,
        },
    ]

    fixtures = []

    for case in test_cases:
        # Compute SMI
        smi = compute_smi(
            case["dim_res"],
            case["vrtti_int"],
            case["bhava_pos"],
        )

        # Compute ΔSMI
        delta_smi = compute_delta_smi(smi, case["prev_smi"])

        # Compute Bhava Gap
        bhava_gap = compute_bhava_gap(case["curr_bhava"], case["prev_bhava"])

        # Compute Tension Corridor
        tension_corridor = compute_tension_corridor(delta_smi, bhava_gap)

        # Build fixture entry
        fixture = {
            "id": case["id"],
            "description": case["description"],
            "inputs": {
                "dimensional_resonance": case["dim_res"],
                "vrtti_intensity": case["vrtti_int"],
                "bhava_position": case["bhava_pos"],
                "previous_smi": case["prev_smi"],
                "current_bhava": case["curr_bhava"],
                "previous_bhava": case["prev_bhava"],
            },
            "outputs": {
                "smi": round_to_6_decimals(smi),
                "delta_smi": round_to_6_decimals(delta_smi),
                "bhava_gap": round_to_6_decimals(bhava_gap),
                "tension_corridor": round_to_6_decimals(tension_corridor),
            },
        }

        fixtures.append(fixture)

    return fixtures


def main():
    """Generate and write fixtures to JSON file."""
    print("Generating Phase 1 Resonance Formula Fixtures...")
    print("=" * 60)

    # Generate fixtures
    fixtures = generate_fixtures()

    # Determine output path (relative to repo root)
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[3]  # Go up from symbolu/tools/formula_fixtures/ to repo root
    output_path = repo_root / "symbolu" / "core" / "formula_drift_tests" / "phase1_resonance_fixtures.json"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to JSON
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(fixtures, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline

    print(f"\n✅ Generated {len(fixtures)} fixtures")
    print(f"📁 Output: {output_path}")
    print("\nFixture Summary:")
    print("-" * 60)

    for fixture in fixtures:
        print(f"{fixture['id']}: {fixture['description']}")
        outputs = fixture["outputs"]
        print(f"  SMI: {outputs['smi']:.6f}, ΔSMI: {outputs['delta_smi']:.6f}, "
              f"Bhava Gap: {outputs['bhava_gap']:.6f}, TC: {outputs['tension_corridor']:.6f}")

    print("\n" + "=" * 60)
    print("✅ Fixture generation complete!")
    print("\nIMPORTANT:")
    print("  - Review the generated fixtures before committing")
    print("  - This file serves as the canonical drift reference")
    print("  - Only regenerate when intentionally updating formulas")


if __name__ == "__main__":
    main()
