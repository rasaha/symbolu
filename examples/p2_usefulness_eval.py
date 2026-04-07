#!/usr/bin/env python3
"""
P2 Usefulness Evaluation: Guna → CSR Audit Signal

Determines whether the Phase 2 audit-only energetic feedback signal is:
1. Interpretable — outputs match intuitive expectations
2. Stable — smooth, bounded, no wild swings from small input changes
3. Incrementally valuable — adds explanatory power beyond existing JEPA signals

Run:
    python examples/p2_usefulness_eval.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple

from agentic.agentic_framework.jepa_governance import (
    GovernanceRegime,
    approximate_layer_weights,
    approximate_vritti,
    ontology_vritti_prior,
    build_ontology_signal,
    build_vritti_signal,
    build_jepa_composite,
    build_runtime_process_state,
    compute_residual,
    assess_governance,
)
from agentic.guna_modulation.types import GunaVector, PipelineInputs
from agentic.guna_modulation.guna_derivation import (
    derive_guna_from_values,
    guna_csr_modulation_audit,
)


# =========================================================================
# Scenario definitions
# =========================================================================

@dataclass
class EvalScenario:
    name: str
    # Governance quality signals
    quality: float
    coherence: float
    goal_alignment: float
    overall_confidence: float
    # Runtime context
    action_type: str = "search"
    tool_name: str = "search"
    risk_level: str = "READ_ONLY"
    # CSR inputs for guna derivation
    C_s: float = 0.5   # Structural coherence
    M: float = 0.5     # Motion / transformation
    H: float = 0.5     # Entropy
    # Expected dominant tendency (for interpretability check)
    expected_dominant: Optional[str] = None
    # Descriptive category
    category: str = "general"


SCENARIOS: List[EvalScenario] = [
    # === Sattva-dominant: high coherence, low entropy ===
    EvalScenario(
        "sattva_analytical", quality=0.9, coherence=0.9,
        goal_alignment=0.8, overall_confidence=0.85,
        C_s=0.9, M=0.3, H=0.1,
        expected_dominant="clarify", category="sattva-dominant",
    ),
    EvalScenario(
        "sattva_pure_reasoning", quality=0.95, coherence=0.95,
        goal_alignment=0.5, overall_confidence=0.9,
        C_s=0.95, M=0.2, H=0.05,
        expected_dominant="clarify", category="sattva-dominant",
    ),
    EvalScenario(
        "sattva_high_quality_write", quality=0.9, coherence=0.8,
        goal_alignment=0.7, overall_confidence=0.8,
        action_type="write", tool_name="save_file", risk_level="WRITE",
        C_s=0.85, M=0.4, H=0.15,
        expected_dominant="clarify", category="sattva-dominant",
    ),

    # === Rajas-dominant: high motion, mid-entropy ===
    EvalScenario(
        "rajas_agency", quality=0.5, coherence=0.5,
        goal_alignment=0.9, overall_confidence=0.7,
        action_type="execute", tool_name="deploy", risk_level="DESTRUCTIVE",
        C_s=0.4, M=0.9, H=0.5,
        expected_dominant="agitate", category="rajas-dominant",
    ),
    EvalScenario(
        "rajas_execution_focused", quality=0.6, coherence=0.6,
        goal_alignment=0.8, overall_confidence=0.8,
        action_type="execute", tool_name="run_task", risk_level="EXECUTE",
        C_s=0.5, M=0.85, H=0.45,
        expected_dominant="agitate", category="rajas-dominant",
    ),
    EvalScenario(
        "rajas_moderate_write", quality=0.6, coherence=0.5,
        goal_alignment=0.7, overall_confidence=0.6,
        action_type="write", tool_name="save_draft", risk_level="WRITE",
        C_s=0.45, M=0.8, H=0.5,
        expected_dominant="agitate", category="rajas-dominant",
    ),

    # === Tamas-dominant: high entropy, low coherence ===
    EvalScenario(
        "tamas_low_quality", quality=0.2, coherence=0.2,
        goal_alignment=0.3, overall_confidence=0.3,
        C_s=0.15, M=0.2, H=0.85,
        expected_dominant="dampen", category="tamas-dominant",
    ),
    EvalScenario(
        "tamas_dormant", quality=0.1, coherence=0.1,
        goal_alignment=0.1, overall_confidence=0.1,
        C_s=0.1, M=0.1, H=0.9,
        expected_dominant="dampen", category="tamas-dominant",
    ),
    EvalScenario(
        "tamas_collapse", quality=0.0, coherence=0.0,
        goal_alignment=0.0, overall_confidence=0.0,
        C_s=0.05, M=0.05, H=0.95,
        expected_dominant="dampen", category="tamas-dominant",
    ),

    # === Mixed states ===
    EvalScenario(
        "mixed_balanced", quality=0.5, coherence=0.5,
        goal_alignment=0.5, overall_confidence=0.5,
        C_s=0.5, M=0.5, H=0.5,
        expected_dominant=None, category="mixed",
    ),
    EvalScenario(
        "mixed_sattva_rajas", quality=0.7, coherence=0.7,
        goal_alignment=0.7, overall_confidence=0.7,
        C_s=0.7, M=0.7, H=0.3,
        expected_dominant=None, category="mixed",
    ),
    EvalScenario(
        "mixed_rajas_tamas", quality=0.3, coherence=0.3,
        goal_alignment=0.5, overall_confidence=0.4,
        C_s=0.25, M=0.7, H=0.65,
        expected_dominant=None, category="mixed",
    ),

    # === Edge / extreme ===
    EvalScenario(
        "extreme_all_max", quality=1.0, coherence=1.0,
        goal_alignment=1.0, overall_confidence=1.0,
        C_s=1.0, M=1.0, H=0.0,
        expected_dominant="clarify", category="extreme",
    ),
    EvalScenario(
        "extreme_all_min", quality=0.0, coherence=0.0,
        goal_alignment=0.0, overall_confidence=0.0,
        C_s=0.0, M=0.0, H=1.0,
        expected_dominant="dampen", category="extreme",
    ),

    # === Stagnation-like: low motion, moderate entropy ===
    EvalScenario(
        "stagnation_low_motion", quality=0.4, coherence=0.4,
        goal_alignment=0.3, overall_confidence=0.35,
        C_s=0.35, M=0.1, H=0.6,
        expected_dominant="dampen", category="stagnation",
    ),

    # === Oscillatory-like: mid everything, high motion ===
    EvalScenario(
        "oscillatory_high_motion", quality=0.5, coherence=0.4,
        goal_alignment=0.5, overall_confidence=0.5,
        C_s=0.4, M=0.9, H=0.5,
        expected_dominant="agitate", category="oscillatory",
    ),

    # === High coherence but low quality (sattva-tamas tension) ===
    EvalScenario(
        "tension_coherent_low_quality", quality=0.2, coherence=0.8,
        goal_alignment=0.3, overall_confidence=0.4,
        C_s=0.7, M=0.3, H=0.4,
        expected_dominant="clarify", category="tension",
    ),
]


# =========================================================================
# Evaluation result
# =========================================================================

@dataclass
class EvalResult:
    scenario: str
    category: str
    # Guna state
    guna_s: float
    guna_r: float
    guna_t: float
    # P2 audit signal
    clarify: float
    agitate: float
    dampen: float
    net_coherence: float
    net_entropy: float
    dominant: str
    # JEPA / governance
    regime: str
    recommended_action: str
    alignment: float
    integrated_confidence: float
    residual_magnitude: float
    semantic_consistency: float
    action_state_coherence: float
    confidence_adjustment: float
    primary_vritti: str
    primary_ontology: str
    # Interpretability
    expected_dominant: Optional[str]
    dominant_matches: Optional[bool]


# =========================================================================
# Core evaluation
# =========================================================================

def evaluate_scenario(s: EvalScenario) -> EvalResult:
    """Evaluate a single scenario: compute guna, P2 audit, and JEPA signals."""
    # Derive guna from CSR
    guna = derive_guna_from_values(C_s=s.C_s, M=s.M, H=s.H)
    audit = guna_csr_modulation_audit(guna)

    # Build JEPA composite
    lw = approximate_layer_weights(
        quality=s.quality, coherence=s.coherence,
        goal_alignment=s.goal_alignment, overall_confidence=s.overall_confidence,
    )
    vritti_dist = approximate_vritti(
        quality=s.quality, coherence=s.coherence,
        overall_confidence=s.overall_confidence, layer_weights=lw,
    )
    ontology = build_ontology_signal(layer_weights=lw)
    vritti = build_vritti_signal(vritti_distribution=vritti_dist)
    jepa = build_jepa_composite(ontology, vritti)
    runtime = build_runtime_process_state(
        action_type=s.action_type, tool_name=s.tool_name,
        risk_level=s.risk_level, confidence_score=s.overall_confidence,
    )
    assessment = assess_governance(jepa, runtime)

    dominant_matches = None
    if s.expected_dominant is not None:
        dominant_matches = (audit.dominant_tendency == s.expected_dominant)

    return EvalResult(
        scenario=s.name,
        category=s.category,
        guna_s=guna.sattva,
        guna_r=guna.rajas,
        guna_t=guna.tamas,
        clarify=audit.clarify_delta,
        agitate=audit.agitate_delta,
        dampen=audit.dampen_delta,
        net_coherence=audit.net_coherence_delta,
        net_entropy=audit.net_entropy_delta,
        dominant=audit.dominant_tendency,
        regime=assessment.regime.value,
        recommended_action=assessment.recommended_action,
        alignment=jepa.ontology_vritti_alignment,
        integrated_confidence=jepa.integrated_confidence,
        residual_magnitude=assessment.residual.residual_magnitude,
        semantic_consistency=assessment.residual.semantic_consistency,
        action_state_coherence=assessment.residual.action_state_coherence,
        confidence_adjustment=assessment.confidence_adjustment,
        primary_vritti=jepa.vritti.primary_vritti,
        primary_ontology=jepa.ontology.primary_layer,
        expected_dominant=s.expected_dominant,
        dominant_matches=dominant_matches,
    )


# =========================================================================
# Stability analysis: sensitivity to small perturbations
# =========================================================================

def stability_check(s: EvalScenario, epsilon: float = 0.02) -> Dict[str, float]:
    """Compute max audit signal change from small CSR perturbations."""
    base_guna = derive_guna_from_values(C_s=s.C_s, M=s.M, H=s.H)
    base_audit = guna_csr_modulation_audit(base_guna)

    max_deltas = {"clarify": 0.0, "agitate": 0.0, "dampen": 0.0,
                  "net_coherence": 0.0, "net_entropy": 0.0}

    for param in ("C_s", "M", "H"):
        for direction in (-epsilon, +epsilon):
            perturbed = {
                "C_s": s.C_s, "M": s.M, "H": s.H,
            }
            perturbed[param] = max(0.0, min(1.0, perturbed[param] + direction))
            p_guna = derive_guna_from_values(**perturbed)
            p_audit = guna_csr_modulation_audit(p_guna)
            max_deltas["clarify"] = max(max_deltas["clarify"],
                                        abs(p_audit.clarify_delta - base_audit.clarify_delta))
            max_deltas["agitate"] = max(max_deltas["agitate"],
                                        abs(p_audit.agitate_delta - base_audit.agitate_delta))
            max_deltas["dampen"] = max(max_deltas["dampen"],
                                       abs(p_audit.dampen_delta - base_audit.dampen_delta))
            max_deltas["net_coherence"] = max(max_deltas["net_coherence"],
                                              abs(p_audit.net_coherence_delta - base_audit.net_coherence_delta))
            max_deltas["net_entropy"] = max(max_deltas["net_entropy"],
                                            abs(p_audit.net_entropy_delta - base_audit.net_entropy_delta))
    return max_deltas


# =========================================================================
# Incremental value: correlation with existing signals
# =========================================================================

def _pearson(xs: List[float], ys: List[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / (sx * sy)


def compute_correlations(results: List[EvalResult]) -> Dict[str, float]:
    """Compute correlation of P2 audit signal dimensions with existing signals."""
    correlations = {}

    # net_coherence vs existing signals
    net_coh = [r.net_coherence for r in results]
    correlations["net_coherence_vs_alignment"] = _pearson(
        net_coh, [r.alignment for r in results])
    correlations["net_coherence_vs_integrated_confidence"] = _pearson(
        net_coh, [r.integrated_confidence for r in results])
    correlations["net_coherence_vs_residual_magnitude"] = _pearson(
        net_coh, [r.residual_magnitude for r in results])
    correlations["net_coherence_vs_semantic_consistency"] = _pearson(
        net_coh, [r.semantic_consistency for r in results])

    # clarify-dampen spread vs confidence
    spread = [r.clarify - r.dampen for r in results]
    correlations["clarify_dampen_spread_vs_confidence_adj"] = _pearson(
        spread, [r.confidence_adjustment for r in results])
    correlations["clarify_dampen_spread_vs_alignment"] = _pearson(
        spread, [r.alignment for r in results])

    # agitate vs residual/action_state_coherence
    agitate = [r.agitate for r in results]
    correlations["agitate_vs_residual_magnitude"] = _pearson(
        agitate, [r.residual_magnitude for r in results])
    correlations["agitate_vs_action_state_coherence"] = _pearson(
        agitate, [r.action_state_coherence for r in results])

    return correlations


# =========================================================================
# Case-separation analysis
# =========================================================================

def separation_analysis(results: List[EvalResult]) -> Dict[str, str]:
    """Check whether P2 signal separates cases that JEPA alone cannot."""
    findings = {}

    # Group by regime
    by_regime: Dict[str, List[EvalResult]] = {}
    for r in results:
        by_regime.setdefault(r.regime, []).append(r)

    # Within each regime, check if P2 dominant_tendency varies
    for regime, group in sorted(by_regime.items()):
        tendencies = set(r.dominant for r in group)
        if len(tendencies) > 1:
            cases = [(r.scenario, r.dominant) for r in group]
            findings[f"regime_{regime}_has_varied_tendency"] = (
                f"Cases share regime={regime} but differ in P2 tendency: "
                + ", ".join(f"{s}={d}" for s, d in cases)
            )

    # Check cases with same regime + same vritti but different P2 tendency
    by_regime_vritti: Dict[Tuple[str, str], List[EvalResult]] = {}
    for r in results:
        key = (r.regime, r.primary_vritti)
        by_regime_vritti.setdefault(key, []).append(r)

    for (regime, vritti), group in sorted(by_regime_vritti.items()):
        tendencies = set(r.dominant for r in group)
        if len(tendencies) > 1:
            cases = [(r.scenario, r.dominant, r.net_coherence) for r in group]
            findings[f"same_regime_vritti_{regime}_{vritti}"] = (
                f"Same regime={regime} vritti={vritti} but P2 differs: "
                + ", ".join(f"{s}({d}, nc={nc:+.4f})" for s, d, nc in cases)
            )

    return findings


# =========================================================================
# Main evaluation
# =========================================================================

def run_evaluation():
    print("=" * 90)
    print("P2 USEFULNESS EVALUATION: Guna → CSR Audit Signal")
    print(f"Scenarios: {len(SCENARIOS)}")
    print("=" * 90)

    results = [evaluate_scenario(s) for s in SCENARIOS]

    # === Section 1: Interpretability ===
    print("\n" + "=" * 90)
    print("1. INTERPRETABILITY — Do outputs match expectations?")
    print("=" * 90)

    checked = [r for r in results if r.dominant_matches is not None]
    matches = [r for r in checked if r.dominant_matches]
    mismatches = [r for r in checked if not r.dominant_matches]

    print(f"\n  Scenarios with expected_dominant: {len(checked)}")
    print(f"  Correct dominant tendency:        {len(matches)}/{len(checked)} "
          f"({100*len(matches)/len(checked):.0f}%)" if checked else "")

    if mismatches:
        print(f"\n  MISMATCHES:")
        for r in mismatches:
            print(f"    {r.scenario}: expected={r.expected_dominant}, "
                  f"got={r.dominant} (S={r.guna_s:.3f} R={r.guna_r:.3f} T={r.guna_t:.3f})")
    else:
        print("  All dominant tendencies match expectations.")

    print(f"\n  Per-scenario audit outputs:")
    print(f"  {'Scenario':<30s} {'Cat':<18s} "
          f"{'S':>5s} {'R':>5s} {'T':>5s}  "
          f"{'Clar':>6s} {'Agit':>6s} {'Damp':>6s}  "
          f"{'NetC':>7s} {'NetH':>7s} {'Dom':<8s}")
    print("  " + "-" * 118)
    for r in results:
        print(f"  {r.scenario:<30s} {r.category:<18s} "
              f"{r.guna_s:5.3f} {r.guna_r:5.3f} {r.guna_t:5.3f}  "
              f"{r.clarify:6.4f} {r.agitate:6.4f} {r.dampen:6.4f}  "
              f"{r.net_coherence:+7.4f} {r.net_entropy:+7.4f} {r.dominant:<8s}")

    # === Section 2: Stability ===
    print("\n" + "=" * 90)
    print("2. STABILITY — Sensitivity to small perturbations (eps=0.02)")
    print("=" * 90)

    max_sensitivity = 0.0
    print(f"\n  {'Scenario':<30s} {'MaxΔclar':>9s} {'MaxΔagit':>9s} "
          f"{'MaxΔdamp':>9s} {'MaxΔnc':>9s} {'MaxΔne':>9s}")
    print("  " + "-" * 80)
    for s in SCENARIOS:
        deltas = stability_check(s)
        row_max = max(deltas.values())
        max_sensitivity = max(max_sensitivity, row_max)
        print(f"  {s.name:<30s} {deltas['clarify']:9.6f} {deltas['agitate']:9.6f} "
              f"{deltas['dampen']:9.6f} {deltas['net_coherence']:9.6f} "
              f"{deltas['net_entropy']:9.6f}")

    print(f"\n  Max sensitivity across all scenarios: {max_sensitivity:.6f}")
    if max_sensitivity < 0.01:
        print("  VERDICT: Signal is SMOOTH — small inputs cause proportionally small changes.")
    elif max_sensitivity < 0.05:
        print("  VERDICT: Signal is MODERATELY SMOOTH — acceptable sensitivity.")
    else:
        print("  VERDICT: Signal is NOISY — review needed.")

    # === Section 3: Incremental value ===
    print("\n" + "=" * 90)
    print("3. INCREMENTAL VALUE — Correlation with existing JEPA signals")
    print("=" * 90)

    correlations = compute_correlations(results)
    print()
    for name, corr in sorted(correlations.items()):
        strength = "STRONG" if abs(corr) > 0.7 else "MODERATE" if abs(corr) > 0.4 else "WEAK"
        print(f"  {name:<50s}  r = {corr:+.4f}  [{strength}]")

    # Interpretation
    highly_redundant = [k for k, v in correlations.items() if abs(v) > 0.85]
    novel = [k for k, v in correlations.items() if abs(v) < 0.4]
    print(f"\n  Highly redundant (|r| > 0.85): {len(highly_redundant)}")
    for k in highly_redundant:
        print(f"    {k}: r = {correlations[k]:+.4f}")
    print(f"  Novel / low correlation (|r| < 0.4): {len(novel)}")
    for k in novel:
        print(f"    {k}: r = {correlations[k]:+.4f}")

    # === Section 4: Case separation ===
    print("\n" + "=" * 90)
    print("4. CASE SEPARATION — Does P2 distinguish cases JEPA alone cannot?")
    print("=" * 90)

    sep = separation_analysis(results)
    if sep:
        for key, desc in sorted(sep.items()):
            print(f"\n  {key}:")
            print(f"    {desc}")
    else:
        print("\n  No case separation found — P2 does not distinguish beyond JEPA.")

    # === Section 5: Cross-reference with governance ===
    print("\n" + "=" * 90)
    print("5. CROSS-REFERENCE — P2 audit vs governance regime/action")
    print("=" * 90)

    print(f"\n  {'Scenario':<30s} {'Regime':<16s} {'Action':<10s} "
          f"{'P2 Dom':<10s} {'Align':>6s} {'Conf':>6s} "
          f"{'Resid':>6s} {'ConfAdj':>7s} {'Vritti':<12s}")
    print("  " + "-" * 120)
    for r in results:
        print(f"  {r.scenario:<30s} {r.regime:<16s} {r.recommended_action:<10s} "
              f"{r.dominant:<10s} {r.alignment:6.3f} {r.integrated_confidence:6.3f} "
              f"{r.residual_magnitude:6.3f} {r.confidence_adjustment:+7.3f} "
              f"{r.primary_vritti:<12s}")

    # === Section 6: Boundedness verification ===
    print("\n" + "=" * 90)
    print("6. BOUNDEDNESS VERIFICATION")
    print("=" * 90)

    bounded_ok = True
    for r in results:
        if not (0.0 <= r.clarify <= 0.10):
            print(f"  FAIL: {r.scenario} clarify={r.clarify}")
            bounded_ok = False
        if not (0.0 <= r.agitate <= 0.10):
            print(f"  FAIL: {r.scenario} agitate={r.agitate}")
            bounded_ok = False
        if not (0.0 <= r.dampen <= 0.10):
            print(f"  FAIL: {r.scenario} dampen={r.dampen}")
            bounded_ok = False
        if not (-0.10 <= r.net_coherence <= 0.10):
            print(f"  FAIL: {r.scenario} net_coherence={r.net_coherence}")
            bounded_ok = False
        if not (-0.10 <= r.net_entropy <= 0.10):
            print(f"  FAIL: {r.scenario} net_entropy={r.net_entropy}")
            bounded_ok = False

    if bounded_ok:
        print("  All audit signal values within bounds: PASSED")

    # === Section 7: Determinism verification ===
    print("\n" + "=" * 90)
    print("7. DETERMINISM VERIFICATION")
    print("=" * 90)

    deterministic_ok = True
    for s in SCENARIOS:
        r1 = evaluate_scenario(s)
        r2 = evaluate_scenario(s)
        if (r1.clarify != r2.clarify or r1.agitate != r2.agitate or
                r1.dampen != r2.dampen or r1.dominant != r2.dominant):
            print(f"  FAIL: {s.name} non-deterministic")
            deterministic_ok = False

    if deterministic_ok:
        print("  All scenarios produce identical outputs on re-evaluation: PASSED")

    # === Summary ===
    print("\n" + "=" * 90)
    print("SUMMARY")
    print("=" * 90)

    interp_pct = (100 * len(matches) / len(checked)) if checked else 0
    print(f"\n  Interpretability:     {len(matches)}/{len(checked)} "
          f"({interp_pct:.0f}%) correct dominant tendency")
    print(f"  Stability:            Max sensitivity = {max_sensitivity:.6f} "
          f"({'SMOOTH' if max_sensitivity < 0.01 else 'MODERATE' if max_sensitivity < 0.05 else 'NOISY'})")
    print(f"  Boundedness:          {'PASS' if bounded_ok else 'FAIL'}")
    print(f"  Determinism:          {'PASS' if deterministic_ok else 'FAIL'}")
    print(f"  Highly redundant:     {len(highly_redundant)}/{len(correlations)}")
    print(f"  Novel correlations:   {len(novel)}/{len(correlations)}")
    print(f"  Case separations:     {len(sep)} found")

    print("\nDone.")


if __name__ == "__main__":
    run_evaluation()
