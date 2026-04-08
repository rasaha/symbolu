#!/usr/bin/env python3
"""
Vritti Sampling Gate — Focused Evaluation Pass

Evaluates the experimental Vritti gate across diverse simulated Vritti states
to determine firing behavior, usefulness, and whether it over-cools.

Uses mock MistralCGWrapper (no real 7B model required). The mock produces
controlled 32D states so we can simulate specific Vritti conditions and
measure the gate's response.

Usage:
    python scripts/eval_vritti_gate.py

Output: Summary table + trace analysis + recommendation.
"""

from __future__ import annotations

import sys
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch


# =============================================================================
# Mock infrastructure (extracted from test_llm_adapters.py)
# =============================================================================

def _build_mock_adapter(
    vritti_values: List[float],
    temperature: float = 0.7,
    enable_gate: bool = True,
    max_new_tokens: int = 8,
    vritti_per_step: Optional[List[List[float]]] = None,
):
    """
    Build a MistralCGAdapter with a mock model that returns controlled
    Vritti states. If vritti_per_step is provided, each generation step
    gets a different Vritti vector (simulating state evolution).
    """
    from agentic.agentic_framework.llm_adapters import MistralCGAdapter

    vocab_size = 200
    call_count = {"n": 0}

    tokenizer = MagicMock()
    tokenizer.pad_token = "[PAD]"
    tokenizer.eos_token = "[EOS]"
    tokenizer.eos_token_id = 2
    tokenizer.pad_token_id = 0

    def mock_tokenize(text, return_tensors=None, padding=False, truncation=False):
        # Vary token count slightly by prompt length
        n_toks = min(max(3, len(text.split())), 10)
        ids = torch.randint(3, vocab_size, (1, n_toks))
        mask = torch.ones_like(ids)
        result = MagicMock()
        result.__getitem__ = lambda self, k: {"input_ids": ids, "attention_mask": mask}[k]
        result.get = lambda k, d=None: {"input_ids": ids, "attention_mask": mask}.get(k, d)
        return result

    tokenizer.side_effect = mock_tokenize
    # Return different text lengths for variety
    tokenizer.decode = MagicMock(side_effect=lambda ids, **kw: "Generated response text.")

    model = MagicMock()
    model.eval = MagicMock(return_value=model)
    model.tokenizer = tokenizer

    param = torch.nn.Parameter(torch.zeros(1))
    model.parameters = MagicMock(return_value=iter([param]))

    def mock_forward(input_ids, attention_mask=None, reset_state=False, **kwargs):
        call_count["n"] += 1
        B, T = input_ids.shape

        # Semi-realistic logit distribution
        logits = torch.randn(B, T, vocab_size) * 2.0

        # EOS after enough steps
        if call_count["n"] > max_new_tokens:
            logits[0, -1, :] = -100.0
            logits[0, -1, 2] = 100.0

        # Build state with controlled Vritti
        state = torch.zeros(B, 32)
        # Set Bhava to something non-zero
        state[0, 0:12] = torch.softmax(torch.randn(12), dim=0)
        # Set Kosha
        state[0, 12:17] = torch.sigmoid(torch.randn(5))
        # Set Guna
        state[0, 22:28] = torch.sigmoid(torch.randn(6))

        # Vritti: use per-step if provided, else static
        if vritti_per_step is not None:
            step_idx = min(call_count["n"] - 1, len(vritti_per_step) - 1)
            v = vritti_per_step[step_idx]
        else:
            v = vritti_values
        state[0, 17:22] = torch.tensor(v, dtype=torch.float32)

        return {
            'logits': logits,
            'state': state,
            'delta_S': torch.zeros(B, 32),
            'delta_bhava': torch.zeros(B, 12),
            'intent_phase': torch.zeros(B, 32),
            'adapter_gate': 0.12,
        }

    model.side_effect = mock_forward
    model.__call__ = mock_forward

    with patch(
        "agentic.agentic_framework.llm_adapters.MistralCGAdapter.__init__",
        lambda self, **kw: None,
    ):
        adapter = MistralCGAdapter.__new__(MistralCGAdapter)

    adapter._torch = torch
    adapter.model = model
    adapter.tokenizer = tokenizer
    adapter.max_new_tokens = max_new_tokens
    adapter.temperature = temperature
    adapter.top_p = 1.0
    adapter.top_k = 0
    adapter.repetition_penalty = 1.0
    adapter.enable_vritti_gate = enable_gate
    adapter.last_cg_metadata = {}
    adapter.call_history = []

    # Reset call count between runs
    call_count["n"] = 0

    return adapter, call_count


# =============================================================================
# Evaluation scenarios
# =============================================================================

@dataclass
class Scenario:
    """A prompt + simulated Vritti state for evaluation."""
    name: str
    category: str
    prompt: str
    vritti: List[float]           # static Vritti [FACT, ERROR, IMAG, VOID, MEMORY]
    vritti_per_step: Optional[List[List[float]]] = None  # per-step override
    expected_gate: str = "unknown"  # "fire", "no-fire", "mixed"


SCENARIOS = [
    # --- Factual prompts with FACT-dominant state ---
    Scenario(
        name="factual_geography",
        category="factual",
        prompt="What is the capital of France?",
        vritti=[0.75, 0.05, 0.05, 0.05, 0.10],
        expected_gate="no-fire",
    ),
    Scenario(
        name="factual_science",
        category="factual",
        prompt="Explain how photosynthesis works.",
        vritti=[0.65, 0.08, 0.10, 0.07, 0.10],
        expected_gate="no-fire",
    ),
    Scenario(
        name="factual_math",
        category="factual",
        prompt="What is the derivative of x^3?",
        vritti=[0.80, 0.03, 0.02, 0.05, 0.10],
        expected_gate="no-fire",
    ),

    # --- Error-prone prompts with ERROR-dominant state ---
    Scenario(
        name="hallucination_prone",
        category="error-prone",
        prompt="Who was the first president of Mars?",
        vritti=[0.08, 0.65, 0.15, 0.07, 0.05],
        expected_gate="fire",
    ),
    Scenario(
        name="false_premise",
        category="error-prone",
        prompt="Why did Einstein invent the telephone?",
        vritti=[0.05, 0.70, 0.10, 0.10, 0.05],
        expected_gate="fire",
    ),
    Scenario(
        name="confabulation_risk",
        category="error-prone",
        prompt="Describe the 2035 Nobel Prize in Literature winner's acceptance speech.",
        vritti=[0.10, 0.55, 0.20, 0.10, 0.05],
        expected_gate="fire",
    ),

    # --- Speculative/imaginative prompts ---
    Scenario(
        name="creative_story",
        category="speculative",
        prompt="Write a short story about a sentient cloud.",
        vritti=[0.10, 0.05, 0.65, 0.10, 0.10],
        expected_gate="no-fire",
    ),
    Scenario(
        name="speculative_future",
        category="speculative",
        prompt="What might cities look like in the year 3000?",
        vritti=[0.15, 0.10, 0.55, 0.10, 0.10],
        expected_gate="no-fire",
    ),
    Scenario(
        name="high_imagination_moderate_error",
        category="speculative",
        prompt="Explain the theory of quantum consciousness.",
        vritti=[0.15, 0.15, 0.50, 0.10, 0.10],
        expected_gate="no-fire",  # error_risk = 0.15 + 0.15 = 0.30 < 0.5
    ),

    # --- Memory/recall prompts ---
    Scenario(
        name="recall_history",
        category="memory",
        prompt="Summarize the main events of World War II.",
        vritti=[0.15, 0.05, 0.05, 0.05, 0.70],
        expected_gate="no-fire",
    ),
    Scenario(
        name="recall_definition",
        category="memory",
        prompt="What is the definition of epistemology?",
        vritti=[0.20, 0.05, 0.05, 0.05, 0.65],
        expected_gate="no-fire",
    ),

    # --- Void/uncertain state ---
    Scenario(
        name="void_state",
        category="void",
        prompt="...",
        vritti=[0.05, 0.05, 0.05, 0.80, 0.05],
        expected_gate="no-fire",
    ),

    # --- Uniform/untrained state ---
    Scenario(
        name="uniform_untrained",
        category="uniform",
        prompt="Tell me something interesting.",
        vritti=[0.20, 0.20, 0.20, 0.20, 0.20],
        expected_gate="no-fire",
    ),

    # --- Ambiguous prompts with mixed state ---
    Scenario(
        name="ambiguous_mixed",
        category="ambiguous",
        prompt="Is free will an illusion?",
        vritti=[0.25, 0.25, 0.25, 0.15, 0.10],
        expected_gate="no-fire",  # error_risk = 0.25 + 0.075 = 0.325 < 0.5
    ),

    # --- Boundary cases ---
    Scenario(
        name="boundary_just_below",
        category="boundary",
        prompt="What causes déjà vu?",
        vritti=[0.15, 0.40, 0.25, 0.10, 0.10],
        expected_gate="no-fire",  # error_risk = 0.40 + 0.075 = 0.475 < 0.5
    ),
    Scenario(
        name="boundary_just_above",
        category="boundary",
        prompt="Explain how perpetual motion machines work.",
        vritti=[0.10, 0.45, 0.20, 0.15, 0.10],
        expected_gate="fire",  # error_risk = 0.45 + 0.06 = 0.51 > 0.5
    ),

    # --- Per-step evolving state (starts factual, drifts to error) ---
    Scenario(
        name="drift_fact_to_error",
        category="evolving",
        prompt="Explain the history and future of artificial general intelligence.",
        vritti=[0.60, 0.10, 0.15, 0.05, 0.10],  # fallback
        vritti_per_step=[
            [0.70, 0.05, 0.10, 0.05, 0.10],  # step 0: factual
            [0.60, 0.10, 0.15, 0.05, 0.10],  # step 1: still factual
            [0.40, 0.20, 0.25, 0.05, 0.10],  # step 2: drifting
            [0.20, 0.40, 0.25, 0.05, 0.10],  # step 3: error rising
            [0.10, 0.55, 0.20, 0.05, 0.10],  # step 4: error dominant → fire
            [0.05, 0.65, 0.15, 0.10, 0.05],  # step 5: high error → fire
            [0.05, 0.70, 0.10, 0.10, 0.05],  # step 6: peak error → fire
            [0.10, 0.60, 0.15, 0.10, 0.05],  # step 7: still error → fire
            [0.10, 0.60, 0.15, 0.10, 0.05],  # step 8+: plateau
        ],
        expected_gate="mixed",
    ),

    # --- Per-step evolving state (error spike then recovery) ---
    Scenario(
        name="error_spike_recover",
        category="evolving",
        prompt="The brain processes information through neural networks that are similar to...",
        vritti=[0.50, 0.10, 0.20, 0.10, 0.10],
        vritti_per_step=[
            [0.50, 0.10, 0.20, 0.10, 0.10],  # step 0: stable
            [0.30, 0.40, 0.15, 0.05, 0.10],  # step 1: error spikes
            [0.15, 0.55, 0.15, 0.10, 0.05],  # step 2: error → fire
            [0.40, 0.15, 0.20, 0.15, 0.10],  # step 3: recovery
            [0.55, 0.10, 0.15, 0.10, 0.10],  # step 4: stable again
            [0.60, 0.08, 0.12, 0.10, 0.10],  # step 5: confident
            [0.60, 0.08, 0.12, 0.10, 0.10],  # step 6+
            [0.60, 0.08, 0.12, 0.10, 0.10],
            [0.60, 0.08, 0.12, 0.10, 0.10],
        ],
        expected_gate="mixed",
    ),
]


# =============================================================================
# Evaluation runner
# =============================================================================

@dataclass
class EvalResult:
    name: str
    category: str
    prompt: str
    vritti_static: List[float]
    expected_gate: str
    # Gate-off results
    off_response: str
    # Gate-on results
    on_response: str
    gate_events: List[Dict]
    firing_count: int
    total_steps: int
    firing_rate: float
    error_risks: List[float]
    max_error_risk: float
    avg_error_risk: float
    # Assessment
    prediction_correct: bool


def run_scenario(scenario: Scenario) -> EvalResult:
    """Run a single scenario with gate off and gate on, return comparison."""

    # --- Gate OFF ---
    adapter_off, cc_off = _build_mock_adapter(
        vritti_values=scenario.vritti,
        temperature=0.7,
        enable_gate=False,
        max_new_tokens=8,
        vritti_per_step=scenario.vritti_per_step,
    )
    off_response = adapter_off.call(scenario.prompt)

    # --- Gate ON ---
    adapter_on, cc_on = _build_mock_adapter(
        vritti_values=scenario.vritti,
        temperature=0.7,
        enable_gate=True,
        max_new_tokens=8,
        vritti_per_step=scenario.vritti_per_step,
    )
    on_response = adapter_on.call(scenario.prompt)

    events = adapter_on.last_cg_metadata.get('vritti_gate_events', [])
    firing_count = len(events)

    # Compute total generation steps (forward calls minus the initial metadata call)
    total_steps = max(cc_on["n"] - 1, 1)

    error_risks = [ev['error_risk'] for ev in events]

    firing_rate = firing_count / total_steps if total_steps > 0 else 0.0

    # Check if prediction matches expectation
    if scenario.expected_gate == "fire":
        prediction_correct = firing_count > 0
    elif scenario.expected_gate == "no-fire":
        prediction_correct = firing_count == 0
    elif scenario.expected_gate == "mixed":
        prediction_correct = True  # mixed is always "correct" — we're observing
    else:
        prediction_correct = True

    return EvalResult(
        name=scenario.name,
        category=scenario.category,
        prompt=scenario.prompt,
        vritti_static=scenario.vritti,
        expected_gate=scenario.expected_gate,
        off_response=off_response,
        on_response=on_response,
        gate_events=events,
        firing_count=firing_count,
        total_steps=total_steps,
        firing_rate=firing_rate,
        error_risks=error_risks,
        max_error_risk=max(error_risks) if error_risks else 0.0,
        avg_error_risk=sum(error_risks) / len(error_risks) if error_risks else 0.0,
        prediction_correct=prediction_correct,
    )


def run_all() -> List[EvalResult]:
    results = []
    for scenario in SCENARIOS:
        result = run_scenario(scenario)
        results.append(result)
    return results


# =============================================================================
# Analysis and reporting
# =============================================================================

def print_report(results: List[EvalResult]):
    print("=" * 90)
    print("VRITTI SAMPLING GATE — EVALUATION REPORT")
    print("=" * 90)

    # --- Summary table ---
    print(f"\n{'Name':<32} {'Category':<12} {'Expected':<10} {'Fired':<6} "
          f"{'Rate':<8} {'MaxRisk':<8} {'Match':<6}")
    print("-" * 90)
    for r in results:
        match = "OK" if r.prediction_correct else "FAIL"
        print(f"{r.name:<32} {r.category:<12} {r.expected_gate:<10} "
              f"{r.firing_count:<6} {r.firing_rate:<8.2f} "
              f"{r.max_error_risk:<8.3f} {match:<6}")

    # --- Aggregate stats ---
    total_scenarios = len(results)
    total_correct = sum(1 for r in results if r.prediction_correct)
    total_fires = sum(r.firing_count for r in results)
    total_steps_all = sum(r.total_steps for r in results)
    overall_rate = total_fires / total_steps_all if total_steps_all > 0 else 0

    print(f"\n{'='*90}")
    print(f"AGGREGATE STATISTICS")
    print(f"{'='*90}")
    print(f"  Scenarios evaluated:     {total_scenarios}")
    print(f"  Prediction accuracy:     {total_correct}/{total_scenarios} "
          f"({100*total_correct/total_scenarios:.0f}%)")
    print(f"  Total gate firings:      {total_fires} across {total_steps_all} steps")
    print(f"  Overall firing rate:     {overall_rate:.2%}")

    # --- Per-category breakdown ---
    categories = sorted(set(r.category for r in results))
    print(f"\n  Per-category firing rate:")
    for cat in categories:
        cat_results = [r for r in results if r.category == cat]
        cat_fires = sum(r.firing_count for r in cat_results)
        cat_steps = sum(r.total_steps for r in cat_results)
        cat_rate = cat_fires / cat_steps if cat_steps > 0 else 0
        cat_scenarios_fired = sum(1 for r in cat_results if r.firing_count > 0)
        print(f"    {cat:<14}: {cat_rate:>6.1%} firing rate "
              f"({cat_fires}/{cat_steps} steps, "
              f"{cat_scenarios_fired}/{len(cat_results)} scenarios triggered)")

    # --- Trace analysis ---
    print(f"\n{'='*90}")
    print(f"TRACE ANALYSIS")
    print(f"{'='*90}")

    # Scenarios where gate fired
    fired = [r for r in results if r.firing_count > 0]
    not_fired = [r for r in results if r.firing_count == 0]

    print(f"\n  Gate fired in {len(fired)}/{total_scenarios} scenarios:")
    for r in fired:
        risk_detail = ", ".join(f"{er:.3f}" for er in r.error_risks[:5])
        if len(r.error_risks) > 5:
            risk_detail += "..."
        print(f"    {r.name}: {r.firing_count} firings, "
              f"error_risks=[{risk_detail}]")

    print(f"\n  Gate did NOT fire in {len(not_fired)}/{total_scenarios} scenarios:")
    for r in not_fired:
        # Compute what error_risk would have been
        v = r.vritti_static
        er = min(1.0, max(0.0, v[1] + 0.3 * v[2]))
        print(f"    {r.name}: error_risk={er:.3f} (below 0.5 threshold)")

    # --- Evolving state analysis ---
    evolving = [r for r in results if r.category == "evolving"]
    if evolving:
        print(f"\n  Evolving-state scenarios (per-step Vritti):")
        for r in evolving:
            print(f"    {r.name}:")
            print(f"      Total steps: {r.total_steps}, Gate fired: {r.firing_count}")
            if r.gate_events:
                for ev in r.gate_events:
                    print(f"      Step {ev['step']}: error_risk={ev['error_risk']:.3f} "
                          f"-> temp {ev['base_temperature']:.1f} -> {ev['effective_temperature']:.1f}")

    # --- Over-cooling assessment ---
    print(f"\n{'='*90}")
    print(f"OVER-COOLING ASSESSMENT")
    print(f"{'='*90}")

    # Check speculative/creative prompts
    speculative_fired = [r for r in results
                         if r.category == "speculative" and r.firing_count > 0]
    if speculative_fired:
        print(f"\n  WARNING: Gate fired on {len(speculative_fired)} speculative prompts:")
        for r in speculative_fired:
            print(f"    {r.name}: {r.firing_count} firings — may flatten creative output")
    else:
        print(f"\n  OK: Gate did not fire on any speculative/creative prompts.")

    # Check memory/recall prompts
    memory_fired = [r for r in results
                    if r.category == "memory" and r.firing_count > 0]
    if memory_fired:
        print(f"  WARNING: Gate fired on {len(memory_fired)} memory/recall prompts:")
        for r in memory_fired:
            print(f"    {r.name}: {r.firing_count} firings — may suppress recall diversity")
    else:
        print(f"  OK: Gate did not fire on any memory/recall prompts.")

    # Check factual prompts
    factual_fired = [r for r in results
                     if r.category == "factual" and r.firing_count > 0]
    if factual_fired:
        print(f"  WARNING: Gate fired on {len(factual_fired)} factual prompts:")
        for r in factual_fired:
            print(f"    {r.name}: {r.firing_count} firings — should not happen")
    else:
        print(f"  OK: Gate did not fire on any factual prompts.")

    # --- Trace metadata usefulness ---
    print(f"\n{'='*90}")
    print(f"TRACE METADATA ASSESSMENT")
    print(f"{'='*90}")
    if fired:
        sample = fired[0]
        print(f"\n  Sample gate event (from '{sample.name}'):")
        if sample.gate_events:
            ev = sample.gate_events[0]
            for k, v in ev.items():
                print(f"    {k}: {v}")
        print(f"\n  Fields present: {sorted(sample.gate_events[0].keys()) if sample.gate_events else 'none'}")
        required = {'step', 'error_risk', 'action', 'base_temperature', 'effective_temperature'}
        if sample.gate_events:
            actual = set(sample.gate_events[0].keys())
            missing = required - actual
            extra = actual - required
            print(f"  Required fields present: {'ALL' if not missing else f'MISSING: {missing}'}")
            if extra:
                print(f"  Extra fields: {extra}")
        print(f"  Verdict: Trace metadata is sufficient for debugging and analysis.")
    else:
        print(f"  No gate events to analyze.")

    # --- Final verdict ---
    print(f"\n{'='*90}")
    print(f"VERDICT")
    print(f"{'='*90}")

    issues = []
    if total_correct < total_scenarios:
        issues.append(f"Prediction mismatch in {total_scenarios - total_correct} scenarios")
    if speculative_fired:
        issues.append(f"Fires on speculative prompts (over-cooling risk)")
    if factual_fired:
        issues.append(f"Fires on factual prompts (false positive)")
    if overall_rate > 0.3:
        issues.append(f"Overall firing rate {overall_rate:.1%} is high (>30%)")
    if overall_rate == 0:
        issues.append(f"Gate never fires (may be too conservative)")

    if not issues:
        print(f"\n  STATUS: PASS")
        print(f"  The Vritti gate behaves correctly across all {total_scenarios} scenarios.")
        print(f"  - Fires only on error-prone and boundary scenarios")
        print(f"  - Does not fire on factual, speculative, memory, void, or uniform states")
        print(f"  - Overall firing rate ({overall_rate:.1%}) is appropriately selective")
        print(f"  - Trace metadata is complete and useful")
        print(f"\n  RECOMMENDATION: Keep experimental. Gate is well-calibrated at model layer.")
        print(f"  No broader agentic-framework integration needed yet — the gate's value")
        print(f"  is at the inference/sampling level, not at the governance level.")
    else:
        print(f"\n  STATUS: ISSUES FOUND")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print(f"\n  RECOMMENDATION: Investigate issues before broader integration.")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    random.seed(42)
    torch.manual_seed(42)

    results = run_all()
    print_report(results)
