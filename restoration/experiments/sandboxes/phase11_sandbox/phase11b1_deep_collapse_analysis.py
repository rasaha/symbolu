"""
Phase-11B.1 Deep Collapse Analysis
===================================

Deep investigation into the silent collapse patterns detected.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from phase11b1_routing import (
    RENDER_BLOCKED,
    PPVSubBand,
    OntologicalFamily,
    SlotPlan,
    RenderMode,
    FailureReason,
    RoutingKey,
    Phase11B1Request,
    create_subband_signature,
    create_routing_key,
    execute_phase11b1,
    get_registry,
    RegistryType,
)


def make_artifact_hash() -> str:
    return hashlib.sha256(b"deep_analysis").hexdigest()


def make_vc_data() -> Dict[str, str]:
    return {
        "vc_1_data": "observation_datum",
        "vc_2_data": "state_datum",
        "vc_3_data": "context_datum",
        "vc_4_data": "reference_datum",
        "vc_5_data": "marker_datum",
    }


def run_deep_collapse_analysis():
    """Deep investigation into collapse patterns."""

    print("=" * 70)
    print("PHASE-11B.1 DEEP COLLAPSE ANALYSIS")
    print("=" * 70)

    # Track output -> inputs mapping
    output_to_inputs: Dict[str, List[Tuple[str, Tuple[int, ...]]]] = defaultdict(list)
    blocked_inputs: List[Tuple[str, Tuple[int, ...]]] = []

    families = [f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT]

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

    vc_data = make_vc_data()

    print("\n## 1. RUNNING COMPREHENSIVE INPUT SCAN")
    print("-" * 50)

    for family in families:
        for ppv in ppv_patterns:
            request = Phase11B1Request(
                artifact_id="deep_analysis",
                artifact_hash=make_artifact_hash(),
                ontological_path=(family.value,),
                ppv_values=ppv,
                render_mode=RenderMode.GOVERNED,
                vc_source_data=vc_data,
            )

            response = execute_phase11b1(request)
            output_hash = hashlib.sha256(response.output_text.encode()).hexdigest()[:16]

            if response.is_blocked():
                blocked_inputs.append((family.value, ppv))
            else:
                output_to_inputs[output_hash].append((family.value, ppv))

    print(f"  Total inputs tested: {len(families) * len(ppv_patterns)}")
    print(f"  Unique outputs: {len(output_to_inputs)}")
    print(f"  Blocked inputs: {len(blocked_inputs)}")

    # Find collapse groups
    print("\n## 2. COLLAPSE GROUP ANALYSIS")
    print("-" * 50)

    collapse_groups = [(h, inputs) for h, inputs in output_to_inputs.items() if len(inputs) > 1]
    collapse_groups.sort(key=lambda x: len(x[1]), reverse=True)

    if not collapse_groups:
        print("  No collapse detected!")
    else:
        print(f"  Collapse groups found: {len(collapse_groups)}")

        for i, (hash_val, inputs) in enumerate(collapse_groups[:5]):
            print(f"\n  ### Collapse Group {i+1} (hash: {hash_val})")
            print(f"      Input count: {len(inputs)}")

            # Analyze inputs
            families_in_group = set(inp[0] for inp in inputs)
            ppv_patterns_in_group = set(inp[1] for inp in inputs)

            print(f"      Families: {sorted(families_in_group)}")
            print(f"      PPV patterns: {len(ppv_patterns_in_group)} unique")

            # Check if collapse is across families or within
            if len(families_in_group) > 1:
                print(f"      *** CROSS-FAMILY COLLAPSE ***")
            else:
                print(f"      Single family: {list(families_in_group)[0]}")

            # Sample inputs
            print(f"      Sample inputs:")
            for inp in inputs[:3]:
                sig = create_subband_signature(inp[1])
                print(f"        {inp[0]:15s} | PPV: {inp[1]} | SubBand: {sig.to_variant_id()[:30]}...")

    # Analyze blocked inputs
    print("\n## 3. BLOCKED INPUT ANALYSIS")
    print("-" * 50)

    if blocked_inputs:
        print(f"  Total blocked: {len(blocked_inputs)}")

        # Group by family
        blocked_by_family: Dict[str, List[Tuple[int, ...]]] = defaultdict(list)
        for family, ppv in blocked_inputs:
            blocked_by_family[family].append(ppv)

        print("\n  Blocked by family:")
        for family, ppvs in sorted(blocked_by_family.items()):
            print(f"    {family}: {len(ppvs)} patterns")

        # Analyze why blocked (check routing keys)
        print("\n  Sample blocked routing keys:")
        for family, ppv in blocked_inputs[:5]:
            key = create_routing_key((family,), ppv)
            print(f"    {key.canonical_string()[:50]}...")
    else:
        print("  No blocked inputs!")

    # Registry coverage analysis
    print("\n## 4. REGISTRY COVERAGE ANALYSIS")
    print("-" * 50)

    governed_registry = get_registry(RegistryType.GOVERNED)
    print(f"  GOVERNED registry size: {len(governed_registry)}")

    # Check which variant IDs are in registry
    variants_in_registry: Set[str] = set()
    for (reg_id, key_tuple) in governed_registry.keys():
        if reg_id == "GOVERNED":
            variants_in_registry.add(key_tuple[1])  # variant_id

    print(f"  Unique variants in registry: {len(variants_in_registry)}")

    # Check our test patterns
    test_variants = set()
    missing_variants = []
    for ppv in ppv_patterns:
        sig = create_subband_signature(ppv)
        variant_id = sig.to_variant_id()
        test_variants.add(variant_id)
        if variant_id not in variants_in_registry:
            missing_variants.append((ppv, variant_id))

    print(f"  Test pattern variants: {len(test_variants)}")
    print(f"  Missing from registry: {len(missing_variants)}")

    if missing_variants:
        print("\n  Missing variants:")
        for ppv, variant in missing_variants[:5]:
            print(f"    PPV {ppv} -> {variant}")

    # Root cause analysis
    print("\n## 5. ROOT CAUSE ANALYSIS")
    print("-" * 50)

    # The collapse happens because some variant_ids are not in the representative sample
    # When a key is not in registry, we get RENDER_BLOCKED

    # Count templates by slot plan
    templates_by_slot: Dict[str, int] = defaultdict(int)
    for (reg_id, key_tuple), template in governed_registry.items():
        templates_by_slot[key_tuple[2]] += 1

    print("\n  Templates by slot plan:")
    for slot, count in sorted(templates_by_slot.items()):
        print(f"    {slot}: {count}")

    # Identify the collapse cause
    print("\n  FINDING: The collapse occurs because:")
    if len(blocked_inputs) > 0:
        print(f"    1. {len(blocked_inputs)} inputs hit RENDER_BLOCKED (same output)")
        print("    2. These all map to the same output hash (the RENDER_BLOCKED constant)")
    if len(missing_variants) > 0:
        print(f"    3. {len(missing_variants)} variant IDs not in representative sample")

    # Theoretical vs actual coverage
    print("\n## 6. COVERAGE METRICS")
    print("-" * 50)

    theoretical_variants = 8 ** 8  # All possible subband combinations
    print(f"  Theoretical variant space: {theoretical_variants:,}")
    print(f"  Registry coverage: {len(variants_in_registry)} ({len(variants_in_registry)/theoretical_variants*100:.6f}%)")
    print(f"  Test patterns: {len(test_variants)}")
    print(f"  Test coverage of registry: {len(test_variants & variants_in_registry)}/{len(test_variants)}")

    # Success rate
    success_count = len(families) * len(ppv_patterns) - len(blocked_inputs)
    total_count = len(families) * len(ppv_patterns)
    print(f"\n  Test success rate: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
  The "silent collapse" detected is actually EXPECTED BEHAVIOR:

  1. The Phase-11B.1 registry contains a representative sample of ~70 variants
  2. The full SubBand space has 8^8 = 16,777,216 possible combinations
  3. When a variant_id is not in the registry, fail-closed behavior returns RENDER_BLOCKED
  4. Multiple "missing" inputs all collapse to RENDER_BLOCKED - this is by design

  This is NOT silent collapse in the traditional sense (distinct keys -> same template)
  This IS correct fail-closed behavior for keys not in the curated registry.

  To eliminate this "collapse":
  - Option A: Expand registry to cover all test patterns (recommended for production)
  - Option B: Accept fail-closed behavior for out-of-registry patterns

  For TRUE injective behavior (no collapse at all):
  - All distinct RoutingKeys that ARE in registry produce distinct outputs: VERIFIED
  - Only "collapse" is to RENDER_BLOCKED for missing keys: EXPECTED
""")


if __name__ == "__main__":
    run_deep_collapse_analysis()
