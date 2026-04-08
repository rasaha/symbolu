#!/usr/bin/env python3
"""
Show Vedic Drishti (Aspect) Patterns
====================================

Displays and captures the Vedic aspect strength matrix data.

Usage:
    python -m symbolu.ontological.show_drishti_patterns
    python -m symbolu.ontological.show_drishti_patterns --save
    python -m symbolu.ontological.show_drishti_patterns --save --output data/drishti.json
"""

import json
import argparse
from typing import Dict, List, Any
from pathlib import Path

from symbolu_core.ontological.bhava_relationships import (
    ASPECT_STRENGTH_MATRIX,
    compute_vedic_aspect_strength,
    LAYER_NAMES,
    get_relationship_meaning,
    BHAVA_SIGNIFICANCES,
    LAYER_TO_BHAVA,
)


def get_drishti_data() -> Dict[str, Any]:
    """
    Capture all Vedic Drishti pattern data as a dictionary.

    Returns:
        Dict containing all Drishti patterns, aspect matrix, and relationship data
    """

    # Pattern definitions with verification
    pattern_definitions = [
        {"name": "Conjunction", "distance": 0, "strength": 1.0, "description": "Same layer, strongest self-reference"},
        {"name": "Opposition", "distance": 6, "strength": 1.0, "description": "Complementary, full aspect (7th house)"},
        {"name": "Trine", "distance": 4, "strength": 0.9, "description": "Harmonious, flowing energy (5th house)"},
        {"name": "Trine", "distance": 8, "strength": 0.9, "description": "Harmonious, flowing energy (9th house)"},
        {"name": "Adjacent", "distance": 1, "strength": 0.8, "description": "Resource flow, immediate connection (2nd house)"},
        {"name": "Adjacent", "distance": 11, "strength": 0.8, "description": "Resource flow, immediate connection (12th house)"},
        {"name": "Square", "distance": 3, "strength": 0.75, "description": "Action/tension, growth through challenge (4th house)"},
        {"name": "Square", "distance": 9, "strength": 0.75, "description": "Action/tension, growth through challenge (10th house)"},
        {"name": "Sextile", "distance": 2, "strength": 0.7, "description": "Opportunity, cooperative aspects (3rd house)"},
        {"name": "Sextile", "distance": 10, "strength": 0.7, "description": "Opportunity, cooperative aspects (11th house)"},
        {"name": "Quincunx", "distance": 5, "strength": 0.5, "description": "Adjustment needed, indirect connection (6th house)"},
        {"name": "Quincunx", "distance": 7, "strength": 0.5, "description": "Adjustment needed, indirect connection (8th house)"},
    ]

    # Verify patterns
    patterns_verified = []
    for p in pattern_definitions:
        actual = ASPECT_STRENGTH_MATRIX[0][p["distance"]]
        patterns_verified.append({
            **p,
            "actual": actual,
            "verified": abs(actual - p["strength"]) < 0.01
        })

    # Full 12x12 aspect matrix
    aspect_matrix = {
        "dimensions": "12x12",
        "description": "Aspect strength between layer pairs based on Vedic Drishti",
        "matrix": ASPECT_STRENGTH_MATRIX,
        "layer_names": LAYER_NAMES,
    }

    # Bhava significances (12 houses)
    bhava_data = []
    for i in range(1, 13):
        bhava = BHAVA_SIGNIFICANCES[i]
        bhava_data.append({
            "number": i,
            "name": bhava["name"],
            "meaning": bhava["meaning"],
            "description": bhava["description"],
        })

    # Layer to Bhava mapping
    layer_bhava_mapping = []
    for layer_idx, bhava_num in LAYER_TO_BHAVA.items():
        layer_bhava_mapping.append({
            "layer_index": layer_idx,
            "layer_name": LAYER_NAMES[layer_idx],
            "primary_bhava": bhava_num,
            "bhava_name": BHAVA_SIGNIFICANCES[bhava_num]["name"],
            "bhava_meaning": BHAVA_SIGNIFICANCES[bhava_num]["meaning"],
        })

    # All 144 inter-layer relationships
    all_relationships = []
    for from_idx in range(12):
        for to_idx in range(12):
            meaning = get_relationship_meaning(from_idx, to_idx)
            strength = ASPECT_STRENGTH_MATRIX[from_idx][to_idx]

            # Determine pattern type based on distance
            diff = abs(from_idx - to_idx)
            circular_diff = min(diff, 12 - diff)

            if circular_diff == 0:
                pattern_type = "Conjunction"
            elif circular_diff == 6:
                pattern_type = "Opposition"
            elif circular_diff in [4, 8]:
                pattern_type = "Trine"
            elif circular_diff in [1, 11]:
                pattern_type = "Adjacent"
            elif circular_diff in [3, 9]:
                pattern_type = "Square"
            elif circular_diff in [2, 10]:
                pattern_type = "Sextile"
            else:
                pattern_type = "Quincunx"

            all_relationships.append({
                "from_layer_index": from_idx,
                "from_layer": meaning["from_layer"],
                "to_layer_index": to_idx,
                "to_layer": meaning["to_layer"],
                "aspect_strength": strength,
                "pattern_type": pattern_type,
                "distance": circular_diff,
                "relationship_bhava": {
                    "name": meaning["relationship_bhava"]["name"],
                    "meaning": meaning["relationship_bhava"]["meaning"],
                    "description": meaning["relationship_bhava"]["description"],
                },
                "interpretation": meaning["interpretation"],
            })

    # Compile full data
    data = {
        "title": "Vedic Drishti (Aspect) Patterns",
        "description": "Inter-layer relationship data based on Vedic astrology principles",
        "vedic_principle": "Bhavas are RELATIONSHIPS, not separate entities. The 12 ontological layers embody Bhava dynamics through their inter-layer relationships.",

        "pattern_summary": {
            "Conjunction": {"distance": 0, "strength": 1.0, "meaning": "Same layer, self-reference"},
            "Opposition": {"distance": 6, "strength": 1.0, "meaning": "Complementary, full aspect"},
            "Trine": {"distances": [4, 8], "strength": 0.9, "meaning": "Harmonious, flowing"},
            "Adjacent": {"distances": [1, 11], "strength": 0.8, "meaning": "Resource flow"},
            "Square": {"distances": [3, 9], "strength": 0.75, "meaning": "Action/tension"},
            "Sextile": {"distances": [2, 10], "strength": 0.7, "meaning": "Opportunity"},
            "Quincunx": {"distances": [5, 7], "strength": 0.5, "meaning": "Adjustment needed"},
        },

        "patterns": patterns_verified,
        "aspect_matrix": aspect_matrix,
        "bhava_significances": bhava_data,
        "layer_to_bhava_mapping": layer_bhava_mapping,
        "all_relationships": all_relationships,

        "statistics": {
            "total_layers": 12,
            "total_relationships": 144,
            "self_relationships": 12,
            "cross_relationships": 132,
            "all_patterns_verified": all(p["verified"] for p in patterns_verified),
        }
    }

    return data


def show_drishti_patterns():
    """Display all Vedic Drishti patterns with verification."""

    print("=" * 70)
    print("VEDIC DRISHTI (ASPECT) PATTERNS")
    print("=" * 70)

    # Pattern definitions
    patterns = {
        "Conjunction (same layer)": {"distance": 0, "expected": 1.0},
        "Opposition (6 apart)": {"distance": 6, "expected": 1.0},
        "Trine (4 apart)": {"distance": 4, "expected": 0.9},
        "Trine (8 apart)": {"distance": 8, "expected": 0.9},
        "Square (3 apart)": {"distance": 3, "expected": 0.75},
        "Square (9 apart)": {"distance": 9, "expected": 0.75},
        "Sextile (2 apart)": {"distance": 2, "expected": 0.7},
        "Sextile (10 apart)": {"distance": 10, "expected": 0.7},
        "Adjacent (1 apart)": {"distance": 1, "expected": 0.8},
        "Adjacent (11 apart)": {"distance": 11, "expected": 0.8},
        "Quincunx (5 apart)": {"distance": 5, "expected": 0.5},
        "Quincunx (7 apart)": {"distance": 7, "expected": 0.5},
    }

    print("\n1. PATTERN VERIFICATION")
    print("-" * 70)
    print(f"{'Pattern':<30} {'Distance':<10} {'Expected':<10} {'Actual':<10} {'Status'}")
    print("-" * 70)

    all_correct = True
    for name, info in patterns.items():
        dist = info["distance"]
        expected = info["expected"]
        actual = ASPECT_STRENGTH_MATRIX[0][dist]
        status = "✓" if abs(actual - expected) < 0.01 else "✗"
        if status == "✗":
            all_correct = False
        print(f"{name:<30} {dist:<10} {expected:<10.2f} {actual:<10.2f} {status}")

    print("-" * 70)
    print(f"All patterns correct: {all_correct}")

    # Show full aspect matrix (first row represents layer 0's view)
    print("\n\n2. FULL ASPECT STRENGTH MATRIX")
    print("-" * 70)
    print("How each layer 'sees' other layers (Vedic Drishti strengths):")
    print()

    # Header
    print("From\\To  ", end="")
    for j in range(12):
        print(f"O{j+1:02d} ", end="")
    print()
    print("-" * 60)

    for i in range(12):
        print(f"O{i+1:02d}     ", end="")
        for j in range(12):
            strength = ASPECT_STRENGTH_MATRIX[i][j]
            print(f"{strength:.2f} ", end="")
        print()

    # Show example relationships with their meanings
    print("\n\n3. EXAMPLE INTER-LAYER RELATIONSHIPS")
    print("-" * 70)

    examples = [
        (0, 0, "Conjunction"),    # Same layer
        (0, 6, "Opposition"),     # 6 apart
        (1, 5, "Trine"),          # 4 apart
        (2, 5, "Square"),         # 3 apart
        (3, 4, "Adjacent"),       # 1 apart
        (4, 9, "Quincunx"),       # 5 apart
    ]

    for from_idx, to_idx, pattern_name in examples:
        meaning = get_relationship_meaning(from_idx, to_idx)
        strength = ASPECT_STRENGTH_MATRIX[from_idx][to_idx]

        print(f"\n{pattern_name.upper()} Example:")
        print(f"  {meaning['from_layer']} → {meaning['to_layer']}")
        print(f"  Aspect Strength: {strength:.2f}")
        print(f"  Bhava: {meaning['relationship_bhava']['name']} ({meaning['relationship_bhava']['meaning']})")
        print(f"  Interpretation: {meaning['interpretation']}")

    # Show Bhava significances
    print("\n\n4. BHAVA SIGNIFICANCES (12 Houses)")
    print("-" * 70)
    print(f"{'#':<4} {'Name':<10} {'Meaning':<15} {'Description'}")
    print("-" * 70)

    for i in range(1, 13):
        bhava = BHAVA_SIGNIFICANCES[i]
        print(f"{i:<4} {bhava['name']:<10} {bhava['meaning']:<15} {bhava['description']}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
Vedic Drishti (Aspect) Patterns in Symbol-U:

  CONJUNCTION (0 apart):  1.00  - Same layer, strongest self-reference
  OPPOSITION  (6 apart):  1.00  - Complementary, full aspect (7th house)
  TRINE       (4/8):      0.90  - Harmonious, flowing energy (5th/9th)
  ADJACENT    (1/11):     0.80  - Resource flow, immediate connection
  SQUARE      (3/9):      0.75  - Action/tension, growth through challenge
  SEXTILE     (2/10):     0.70  - Opportunity, cooperative aspects
  QUINCUNX    (5/7):      0.50  - Adjustment needed, indirect connection

These patterns are:
1. Initialized from Vedic astrology principles
2. Used as learnable parameters in the model
3. Applied in DrishtiAttention for cross-layer attention
4. Used in coherence computation (aspect alignment score)
""")


def save_drishti_data(output_path: str = "data/drishti_patterns.json"):
    """Save all Drishti pattern data to a JSON file."""

    data = get_drishti_data()

    # Create output directory if needed
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nData saved to: {output_file}")
    print(f"  - {len(data['patterns'])} patterns verified")
    print(f"  - {len(data['bhava_significances'])} Bhava significances")
    print(f"  - {len(data['all_relationships'])} inter-layer relationships")
    print(f"  - 12x12 aspect strength matrix")

    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Show Vedic Drishti patterns")
    parser.add_argument("--save", action="store_true", help="Save data to JSON file")
    parser.add_argument("--output", "-o", default="data/drishti_patterns.json",
                        help="Output file path (default: data/drishti_patterns.json)")

    args = parser.parse_args()

    show_drishti_patterns()

    if args.save:
        save_drishti_data(args.output)
