#!/usr/bin/env python3
"""
Determinism Verification Test for Phases 13, 19, 31
====================================================

Runs 50 repeated calculations for each phase and verifies hash consistency.
"""

import hashlib
import json
from symbolu.formulas.enhanced_smi import compute_enhanced_smi
from symbolu.formulas.drift_fusion import compute_drift_fusion_snapshot
from symbolu.mechanical.persona.persona_echo_layer import compute_adaptive_persona_echo_profile
from dataclasses import dataclass


@dataclass
class MockSessionSummary:
    drift_risk_band: str = "low"
    stability_band: str = "stable"
    temporal_entropy_band: str = "balanced"
    coherence_fused: float = 0.75


@dataclass
class MockResonanceMap:
    semantic_integrity: float = 0.80
    resonance_entropy_band: str = "balanced"
    mirror_time_cycle_type: str = None
    cause_effect_inversion_band: str = None


@dataclass
class MockMotivationProfile:
    motivation_type: str = "hope_driven"


def hash_value(value):
    """Generate hash of a value for determinism checking."""
    if value is None:
        return None
    json_str = json.dumps(value, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def test_enhanced_smi_determinism(iterations=50):
    """Test Enhanced SMI determinism over 50 iterations."""
    print(f"\n{'='*60}")
    print("Phase 13: Enhanced SMI Determinism Test")
    print(f"{'='*60}")

    inputs = (0.7, 0.5, 0.8, 0.6, 0.4, 0.9)
    results = []
    hashes = []

    for i in range(iterations):
        result = compute_enhanced_smi(*inputs)
        results.append(result)
        hashes.append(hash_value(result))

    unique_results = len(set(results))
    unique_hashes = len(set(hashes))

    print(f"Iterations: {iterations}")
    print(f"Unique results: {unique_results}")
    print(f"Unique hashes: {unique_hashes}")
    print(f"Sample value: {results[0]}")
    print(f"All identical: {unique_results == 1}")

    if unique_results == 1:
        print("✓ PASS: Enhanced SMI is deterministic")
        return True
    else:
        print("✗ FAIL: Enhanced SMI is NOT deterministic")
        print(f"  Found {unique_results} different values across {iterations} runs")
        return False


def test_drift_fusion_determinism(iterations=50):
    """Test Drift Fusion determinism over 50 iterations."""
    print(f"\n{'='*60}")
    print("Phase 19: Drift Fusion Determinism Test")
    print(f"{'='*60}")

    results = []
    hashes = []

    for i in range(iterations):
        snapshot = compute_drift_fusion_snapshot(
            semantic_integrity_score=0.6,
            cognitive_drift_v3=0.4,
            temporal_entropy_diff=0.55,
            temporal_entropy_volatility=0.3,
            coherence_fused=0.7,
        )

        result_dict = {
            'index': snapshot.drift_fusion_index,
            'band': snapshot.drift_risk_band,
            'tags': sorted(snapshot.drift_pattern_tags)
        }

        results.append(result_dict)
        hashes.append(hash_value(result_dict))

    unique_hashes = len(set(hashes))

    print(f"Iterations: {iterations}")
    print(f"Unique hashes: {unique_hashes}")
    print(f"Sample value: {results[0]}")
    print(f"All identical: {unique_hashes == 1}")

    if unique_hashes == 1:
        print("✓ PASS: Drift Fusion is deterministic")
        return True
    else:
        print("✗ FAIL: Drift Fusion is NOT deterministic")
        print(f"  Found {unique_hashes} different values across {iterations} runs")
        return False


def test_apel_determinism(iterations=50):
    """Test APEL determinism over 50 iterations."""
    print(f"\n{'='*60}")
    print("Phase 31: APEL Determinism Test")
    print(f"{'='*60}")

    session_summary = MockSessionSummary(coherence_fused=0.65)
    resonance_map = MockResonanceMap(semantic_integrity=0.75)
    motivation = MockMotivationProfile(motivation_type="hope_driven")

    results = []
    hashes = []

    for i in range(iterations):
        profile = compute_adaptive_persona_echo_profile(
            session_summary=session_summary,
            resonance_map=resonance_map,
            identity_signature=None,
            intent_arc=None,
            motivation_profile=motivation,
            interaction_mode="SMART_INSIGHT",
            domain="therapy",
        )

        result_dict = {
            'enabled': profile.echo_enabled,
            'mode': profile.echo_mode,
            'strength': profile.echo_strength,
            'length_hint': profile.echo_length_hint,
            'focus_tags': sorted(profile.echo_focus_tags),
            'risk_tags': sorted(profile.echo_risk_tags),
        }

        results.append(result_dict)
        hashes.append(hash_value(result_dict))

    unique_hashes = len(set(hashes))

    print(f"Iterations: {iterations}")
    print(f"Unique hashes: {unique_hashes}")
    print(f"Sample value: {results[0]}")
    print(f"All identical: {unique_hashes == 1}")

    if unique_hashes == 1:
        print("✓ PASS: APEL is deterministic")
        return True
    else:
        print("✗ FAIL: APEL is NOT deterministic")
        print(f"  Found {unique_hashes} different values across {iterations} runs")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("DETERMINISM VERIFICATION TEST SUITE")
    print("Phases 13, 19, 31 — 50 Repeated Calculations")
    print("="*60)

    results = {
        "Phase 13 (Enhanced SMI)": test_enhanced_smi_determinism(),
        "Phase 19 (Drift Fusion)": test_drift_fusion_determinism(),
        "Phase 31 (APEL)": test_apel_determinism(),
    }

    print(f"\n{'='*60}")
    print("FINAL DETERMINISM RESULTS")
    print(f"{'='*60}")

    all_passed = all(results.values())

    for phase, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} — {phase}")

    print(f"\n{'='*60}")
    if all_passed:
        print("✓ ALL DETERMINISM TESTS PASSED")
    else:
        print("✗ SOME DETERMINISM TESTS FAILED")
    print(f"{'='*60}\n")
