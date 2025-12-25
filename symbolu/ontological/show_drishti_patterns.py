#!/usr/bin/env python3
"""
Show Vedic Drishti (Aspect) Patterns
====================================

Displays the Vedic aspect strength matrix and verifies all patterns.
"""

from symbolu.ontological.bhava_relationships import (
    ASPECT_STRENGTH_MATRIX,
    compute_vedic_aspect_strength,
    LAYER_NAMES,
    get_relationship_meaning,
    BHAVA_SIGNIFICANCES,
)


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


if __name__ == "__main__":
    show_drishti_patterns()
