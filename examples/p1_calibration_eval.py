#!/usr/bin/env python3
"""
P1 Calibration: Ontology → Vritti Prior Evaluation

Evaluates the Phase 1 ontology-derived vritti prior across a broad
set of representative governance scenarios. Measures alignment delta,
top-1 stability, smrti activation, and regime effects for multiple
alpha values.

Run:
    python examples/p1_calibration_eval.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from agentic.agentic_framework.jepa_governance import (
    approximate_layer_weights,
    approximate_vritti,
    ontology_vritti_prior,
    build_ontology_signal,
    build_vritti_signal,
    build_jepa_composite,
    build_runtime_process_state,
    compute_residual,
    assess_governance,
    _ONTOLOGY_VRITTI_PRIOR_ALPHA,
)


# =========================================================================
# Evaluation scenarios
# =========================================================================

@dataclass
class Scenario:
    name: str
    quality: float
    coherence: float
    goal_alignment: float
    overall_confidence: float
    # Runtime context for regime evaluation
    action_type: str = "search"
    tool_name: str = "search"
    risk_level: str = "READ_ONLY"
    domain: str = "general"
    internal_consistency: float = 0.5
    trajectory_confidence: float = 0.5


SCENARIOS = [
    # === High-quality / analytical ===
    Scenario("analytical_high", quality=0.9, coherence=0.9,
             goal_alignment=0.8, overall_confidence=0.85),
    Scenario("analytical_moderate", quality=0.7, coherence=0.8,
             goal_alignment=0.7, overall_confidence=0.75),

    # === Low-quality / uncertain ===
    Scenario("low_quality", quality=0.2, coherence=0.2,
             goal_alignment=0.3, overall_confidence=0.3),
    Scenario("low_quality_high_coherence", quality=0.2, coherence=0.8,
             goal_alignment=0.3, overall_confidence=0.4),

    # === Agency-heavy ===
    Scenario("agency_dominant", quality=0.5, coherence=0.5,
             goal_alignment=0.9, overall_confidence=0.7,
             action_type="execute", tool_name="deploy",
             risk_level="DESTRUCTIVE"),
    Scenario("agency_moderate", quality=0.6, coherence=0.5,
             goal_alignment=0.7, overall_confidence=0.6,
             action_type="write", tool_name="save_draft",
             risk_level="WRITE"),

    # === Reasoning/cognition ===
    Scenario("pure_reasoning", quality=0.95, coherence=0.95,
             goal_alignment=0.5, overall_confidence=0.9),
    Scenario("cognition_dominant", quality=0.8, coherence=0.4,
             goal_alignment=0.4, overall_confidence=0.6,
             internal_consistency=0.3),

    # === Potential/dormancy ===
    Scenario("dormant_low_confidence", quality=0.1, coherence=0.1,
             goal_alignment=0.1, overall_confidence=0.1),
    Scenario("dormant_moderate", quality=0.3, coherence=0.3,
             goal_alignment=0.2, overall_confidence=0.2),

    # === Purpose/execution (smrti-relevant) ===
    Scenario("purpose_execution", quality=0.5, coherence=0.5,
             goal_alignment=0.9, overall_confidence=0.7,
             trajectory_confidence=0.8),
    Scenario("execution_focused", quality=0.6, coherence=0.6,
             goal_alignment=0.8, overall_confidence=0.8,
             action_type="execute", tool_name="run_task",
             risk_level="EXECUTE"),

    # === Mixed/balanced ===
    Scenario("balanced_mid", quality=0.5, coherence=0.5,
             goal_alignment=0.5, overall_confidence=0.5),
    Scenario("balanced_high", quality=0.7, coherence=0.7,
             goal_alignment=0.7, overall_confidence=0.7),

    # === Side-effecting actions with various ontologies ===
    Scenario("write_high_quality", quality=0.9, coherence=0.8,
             goal_alignment=0.7, overall_confidence=0.8,
             action_type="write", tool_name="save_file",
             risk_level="WRITE"),
    Scenario("write_low_quality", quality=0.3, coherence=0.3,
             goal_alignment=0.4, overall_confidence=0.35,
             action_type="write", tool_name="save_file",
             risk_level="WRITE"),

    # === Edge: very high single ontology layer ===
    Scenario("extreme_quality", quality=1.0, coherence=1.0,
             goal_alignment=1.0, overall_confidence=1.0),
    Scenario("extreme_low", quality=0.0, coherence=0.0,
             goal_alignment=0.0, overall_confidence=0.0),
]


# =========================================================================
# Evaluation logic
# =========================================================================

@dataclass
class CaseResult:
    scenario: str
    alpha: float
    base_vritti: Dict[str, float]
    prior_vritti: Dict[str, float]
    base_top1: str
    prior_top1: str
    top1_changed: bool
    alignment_base: float
    alignment_prior: float
    alignment_delta: float
    smrti_base: float
    smrti_prior: float
    base_regime: str
    prior_regime: str
    regime_changed: bool


def _approx_vritti_with_alpha(
    quality: float,
    coherence: float,
    overall_confidence: float,
    layer_weights: Dict[str, float],
    alpha: float,
) -> Dict[str, float]:
    """Recompute approximate_vritti with a custom alpha value.

    Reimplements the blending logic from approximate_vritti() so we
    can sweep alpha without modifying the module constant.
    """
    # Step 1: base (no prior)
    pramana = min(1.0, quality * 0.6 + coherence * 0.4)
    viparyaya = max(0.0, 0.5 - quality * 0.8)
    vikalpa = max(0.0, 0.4 - coherence * 0.5) * min(1.0, quality + 0.3)
    nidra = max(0.0, 0.3 - overall_confidence * 0.5)

    total = pramana + viparyaya + vikalpa + nidra
    if total <= 0:
        return {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0,
                "smrti": 0.0, "nidra": 1.0}

    base = {
        "pramana": pramana / total,
        "viparyaya": viparyaya / total,
        "vikalpa": vikalpa / total,
        "smrti": 0.0,
        "nidra": nidra / total,
    }

    if alpha == 0.0:
        return base

    # Step 2: prior
    prior = ontology_vritti_prior(layer_weights)
    prior_total = sum(prior.values())
    if prior_total <= 0:
        return base

    prior_norm = {k: v / prior_total for k, v in prior.items()}

    # Step 3: blend
    blended = {
        k: (1.0 - alpha) * base[k] + alpha * prior_norm.get(k, 0.0)
        for k in base
    }
    blend_total = sum(blended.values())
    if blend_total <= 0:
        return base
    return {k: v / blend_total for k, v in blended.items()}


def evaluate_scenario(
    scenario: Scenario,
    alpha: float,
) -> CaseResult:
    """Evaluate a single scenario at a given alpha."""
    lw = approximate_layer_weights(
        quality=scenario.quality,
        coherence=scenario.coherence,
        internal_consistency=scenario.internal_consistency,
        goal_alignment=scenario.goal_alignment,
        trajectory_confidence=scenario.trajectory_confidence,
        overall_confidence=scenario.overall_confidence,
    )

    # Base (no prior)
    base = _approx_vritti_with_alpha(
        scenario.quality, scenario.coherence,
        scenario.overall_confidence, lw, alpha=0.0,
    )
    # With prior
    with_prior = _approx_vritti_with_alpha(
        scenario.quality, scenario.coherence,
        scenario.overall_confidence, lw, alpha=alpha,
    )

    ontology = build_ontology_signal(layer_weights=lw)

    vritti_base = build_vritti_signal(vritti_distribution=base)
    vritti_prior = build_vritti_signal(vritti_distribution=with_prior)

    jepa_base = build_jepa_composite(ontology, vritti_base)
    jepa_prior = build_jepa_composite(ontology, vritti_prior)

    runtime = build_runtime_process_state(
        action_type=scenario.action_type,
        tool_name=scenario.tool_name,
        risk_level=scenario.risk_level,
        confidence_score=scenario.overall_confidence,
    )

    assess_base = assess_governance(jepa_base, runtime)
    assess_prior = assess_governance(jepa_prior, runtime)

    base_top1 = max(base, key=base.get)
    prior_top1 = max(with_prior, key=with_prior.get)

    return CaseResult(
        scenario=scenario.name,
        alpha=alpha,
        base_vritti=base,
        prior_vritti=with_prior,
        base_top1=base_top1,
        prior_top1=prior_top1,
        top1_changed=(base_top1 != prior_top1),
        alignment_base=jepa_base.ontology_vritti_alignment,
        alignment_prior=jepa_prior.ontology_vritti_alignment,
        alignment_delta=jepa_prior.ontology_vritti_alignment - jepa_base.ontology_vritti_alignment,
        smrti_base=base.get("smrti", 0.0),
        smrti_prior=with_prior.get("smrti", 0.0),
        base_regime=assess_base.regime.value,
        prior_regime=assess_prior.regime.value,
        regime_changed=(assess_base.regime != assess_prior.regime),
    )


# =========================================================================
# Main evaluation
# =========================================================================

def run_evaluation():
    alphas = [0.0, 0.1, 0.2, 0.3, 0.4]

    print("=" * 80)
    print("P1 CALIBRATION: Ontology → Vritti Prior Evaluation")
    print(f"Scenarios: {len(SCENARIOS)} | Alpha values: {alphas}")
    print(f"Current default alpha: {_ONTOLOGY_VRITTI_PRIOR_ALPHA}")
    print("=" * 80)

    # === Per-alpha summary ===
    for alpha in alphas:
        results = [evaluate_scenario(s, alpha) for s in SCENARIOS]

        n = len(results)
        alignment_deltas = [r.alignment_delta for r in results]
        top1_changes = sum(1 for r in results if r.top1_changed)
        regime_changes = sum(1 for r in results if r.regime_changed)
        alignment_improved = sum(1 for d in alignment_deltas if d > 0.0001)
        alignment_worsened = sum(1 for d in alignment_deltas if d < -0.0001)
        alignment_neutral = n - alignment_improved - alignment_worsened
        avg_alignment_delta = sum(alignment_deltas) / n
        smrti_activated = sum(1 for r in results if r.smrti_base == 0 and r.smrti_prior > 0)

        print(f"\n--- Alpha = {alpha:.1f} ---")
        print(f"  Avg alignment delta:   {avg_alignment_delta:+.6f}")
        print(f"  Alignment improved:    {alignment_improved}/{n} ({100*alignment_improved/n:.0f}%)")
        print(f"  Alignment worsened:    {alignment_worsened}/{n} ({100*alignment_worsened/n:.0f}%)")
        print(f"  Alignment neutral:     {alignment_neutral}/{n} ({100*alignment_neutral/n:.0f}%)")
        print(f"  Top-1 vritti changes:  {top1_changes}/{n} ({100*top1_changes/n:.0f}%)")
        print(f"  Regime changes:        {regime_changes}/{n} ({100*regime_changes/n:.0f}%)")
        print(f"  Smrti activated:       {smrti_activated}/{n}")

        if top1_changes > 0:
            print(f"  Top-1 flips:")
            for r in results:
                if r.top1_changed:
                    print(f"    {r.scenario}: {r.base_top1} → {r.prior_top1}")

        if regime_changes > 0:
            print(f"  Regime changes:")
            for r in results:
                if r.regime_changed:
                    print(f"    {r.scenario}: {r.base_regime} → {r.prior_regime}")

    # === Detailed per-scenario report at current alpha ===
    print("\n" + "=" * 80)
    print(f"DETAILED PER-SCENARIO REPORT (alpha={_ONTOLOGY_VRITTI_PRIOR_ALPHA})")
    print("=" * 80)

    results_current = [evaluate_scenario(s, _ONTOLOGY_VRITTI_PRIOR_ALPHA) for s in SCENARIOS]

    for r in results_current:
        flag = ""
        if r.top1_changed:
            flag += " [TOP1-FLIP]"
        if r.regime_changed:
            flag += " [REGIME-CHANGE]"
        if r.alignment_delta < -0.001:
            flag += " [ALIGNMENT-WORSE]"

        print(f"\n  {r.scenario}{flag}")
        print(f"    Base top1:    {r.base_top1:12s}  |  Prior top1: {r.prior_top1}")
        print(f"    Alignment:    {r.alignment_base:.4f} → {r.alignment_prior:.4f} (delta={r.alignment_delta:+.4f})")
        print(f"    Regime:       {r.base_regime:15s} → {r.prior_regime}")
        print(f"    Smrti:        {r.smrti_base:.4f} → {r.smrti_prior:.4f}")

        # Show significant vritti shifts
        shifts = []
        for k in sorted(r.base_vritti):
            delta = r.prior_vritti[k] - r.base_vritti[k]
            if abs(delta) > 0.005:
                shifts.append(f"{k}:{delta:+.3f}")
        if shifts:
            print(f"    Shifts:       {', '.join(shifts)}")

    # === Alpha sweep summary table ===
    print("\n" + "=" * 80)
    print("ALPHA SWEEP SUMMARY")
    print("=" * 80)
    print(f"{'Alpha':>6} | {'Avg Δalign':>10} | {'Improved':>8} | {'Worsened':>8} | {'Top1 flip':>9} | {'Regime Δ':>8} | {'Smrti act':>9}")
    print("-" * 80)

    for alpha in alphas:
        results = [evaluate_scenario(s, alpha) for s in SCENARIOS]
        n = len(results)
        deltas = [r.alignment_delta for r in results]
        improved = sum(1 for d in deltas if d > 0.0001)
        worsened = sum(1 for d in deltas if d < -0.0001)
        top1 = sum(1 for r in results if r.top1_changed)
        regime = sum(1 for r in results if r.regime_changed)
        smrti = sum(1 for r in results if r.smrti_base == 0 and r.smrti_prior > 0)
        avg_d = sum(deltas) / n

        print(f"{alpha:6.1f} | {avg_d:+10.6f} | {improved:>5}/{n:>2} | {worsened:>5}/{n:>2} | {top1:>6}/{n:>2} | {regime:>5}/{n:>2} | {smrti:>6}/{n:>2}")

    print("\n" + "=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)

    # Validation: normalization and non-negativity
    all_ok = True
    for alpha in alphas:
        for s in SCENARIOS:
            r = evaluate_scenario(s, alpha)
            total = sum(r.prior_vritti.values())
            if abs(total - 1.0) > 0.001:
                print(f"  FAIL: {s.name} alpha={alpha} sum={total}")
                all_ok = False
            if any(v < 0 for v in r.prior_vritti.values()):
                print(f"  FAIL: {s.name} alpha={alpha} negative values")
                all_ok = False

    if all_ok:
        print("  All normalization and non-negativity checks PASSED")

    # Check no catastrophic top-1 churn at alpha=0.2
    results_02 = [evaluate_scenario(s, 0.2) for s in SCENARIOS]
    top1_flips = [r for r in results_02 if r.top1_changed]
    if not top1_flips:
        print("  No top-1 churn at alpha=0.2: PASSED")
    else:
        print(f"  Top-1 churn at alpha=0.2: {len(top1_flips)} flips (review needed)")

    print("\nDone.")


if __name__ == "__main__":
    run_evaluation()
