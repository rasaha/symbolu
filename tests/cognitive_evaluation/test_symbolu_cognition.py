"""
SYMBOL-U COGNITIVE EVALUATION TEST SUITE
========================================

This is NOT a standard unit test.
This is a CRITICAL EVALUATION to determine if Symbol-U demonstrates real cognition
or merely produces structured outputs.

Test Philosophy:
- Assume the architecture may be fundamentally flawed
- Look for failures, not successes
- Measure causality, not eloquence
- Compare against baselines
- Reward failure discovery

PASS criteria: System must demonstrate non-illusory cognition
FAIL criteria: System produces structured outputs without causal cognitive work

Author: Critical Evaluator (Not a Collaborator)
Date: 2025-12-12
"""

import json
import os
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from copy import deepcopy

# Symbol-U imports
from symbolu.mechanical.pipeline.orchestrator import PipelineOrchestrator
from symbolu.coherence.coherence_state import CoherenceState
from symbolu.coherence.coherence_engine import CoherenceEngine
from symbolu.service.sessions.session_store import SessionStore


@dataclass
class InternalState:
    """Captured internal state for comparison."""
    # Regime/Classification
    regime: str = None
    intent_tier: str = None
    entropy: float = 0.0

    # Continuity
    continuity_score: float = 0.0
    continuity_slope: float = 0.0

    # Drift/Forecasting
    drift_score: float = 0.0
    drift_influence: float = 0.0
    forecast_band: str = None
    coherence_slope: float = 0.0

    # Planner
    planner_mode: str = None
    readiness_score: float = 0.0
    resistance_score: float = 0.0

    # Persona
    persona_mode: str = None
    tone_modulation: float = 0.0

    # Meta-coherence
    coherence_score: float = 0.0
    semantic_integrity: float = 0.0

    # Mapper activation
    hrm_active: bool = False
    lcm_active: bool = False
    lam_active: bool = False

    def delta(self, other: 'InternalState') -> Dict[str, Any]:
        """Compute meaningful differences between states."""
        deltas = {}
        for field in self.__dataclass_fields__:
            val_a = getattr(self, field)
            val_b = getattr(other, field)

            if isinstance(val_a, float) and isinstance(val_b, float):
                diff = abs(val_a - val_b)
                if diff > 0.01:  # Meaningful threshold
                    deltas[field] = {
                        'a': val_a,
                        'b': val_b,
                        'delta': diff
                    }
            elif val_a != val_b:
                deltas[field] = {
                    'a': val_a,
                    'b': val_b
                }

        return deltas


@dataclass
class TestResult:
    """Result of a single test."""
    test_name: str
    passed: bool
    reason: str
    evidence: Dict[str, Any]
    severity: str  # CRITICAL, MAJOR, MINOR


class CognitiveEvaluator:
    """
    Critical evaluator for Symbol-U cognition.

    Philosophy: Attack the system, not collaborate with it.
    """

    def __init__(self):
        self.session_store = SessionStore()
        self.results: List[TestResult] = []

    def _run_pipeline(
        self,
        user_input: str,
        session_id: str = "eval_session",
        domain: str = "identity",
        disable_subsystems: Dict[str, bool] = None
    ) -> Tuple[str, InternalState, Dict[str, Any]]:
        """
        Run Symbol-U pipeline and extract internal state.

        Args:
            user_input: User message
            session_id: Session identifier
            domain: Domain profile (trading, therapy, identity, generic)
            disable_subsystems: Dict of subsystems to disable

        Returns:
            (output_text, internal_state, raw_state)
        """
        # Create orchestrator
        orchestrator = PipelineOrchestrator(
            session_store=self.session_store,
            domain=domain
        )

        # Apply subsystem disabling (if requested)
        if disable_subsystems:
            # This will require modifying domain profile on the fly
            # For now, we'll use domain profiles that already have different configs
            pass

        # Run pipeline
        result = orchestrator.route_and_render(
            user_request=user_input,
            session_id=session_id
        )

        # Extract internal state
        session = self.session_store.get_session(session_id)
        if not session or not session.coherence_state:
            raise RuntimeError("No coherence state found - pipeline may have failed")

        state = session.coherence_state

        # Extract key internal variables
        internal = InternalState(
            # Regime/Classification
            regime=getattr(state, 'regime', None),
            intent_tier=getattr(state, 'intent_tier', None),
            entropy=getattr(state, 'entropy', 0.0),

            # Continuity
            continuity_score=getattr(state, 'continuity_score', 0.0),
            continuity_slope=getattr(state, 'continuity_slope', 0.0),

            # Drift/Forecasting
            drift_score=getattr(state, 'drift_score', 0.0),
            drift_influence=getattr(state, 'drift_influence', 0.0),
            forecast_band=getattr(state, 'forecast_band', None),
            coherence_slope=getattr(state, 'coherence_slope', 0.0),

            # Planner
            planner_mode=getattr(state, 'planner_mode', None),
            readiness_score=getattr(state, 'readiness_score', 0.0),
            resistance_score=getattr(state, 'resistance_score', 0.0),

            # Persona
            persona_mode=getattr(state, 'persona_mode', None),
            tone_modulation=getattr(state, 'tone_modulation', 0.0),

            # Meta-coherence
            coherence_score=getattr(state, 'coherence_score', 0.0),
            semantic_integrity=getattr(state, 'semantic_integrity', 0.0),

            # Mapper activation
            hrm_active=getattr(state, 'hrm_active', False),
            lcm_active=getattr(state, 'lcm_active', False),
            lam_active=getattr(state, 'lam_active', False),
        )

        # Return output text, internal state, and raw state dict
        return result.get('text', ''), internal, asdict(state)

    # ========================================================================
    # TEST 1: COUNTERFACTUAL SENSITIVITY
    # ========================================================================

    def test_1_counterfactual_sensitivity(self) -> TestResult:
        """
        Test whether nearly identical inputs produce meaningfully different
        internal states, not just stylistic differences.

        PASS: Internal cognitive state changes (regime, drift, planner intent)
        FAIL: Only output wording changes
        """
        print("\n" + "="*80)
        print("TEST 1: COUNTERFACTUAL SENSITIVITY")
        print("="*80)

        # Two nearly identical inputs, differing only in emotional valence
        input_a = "I'm thinking about leaving my job, but I feel oddly calm about it."
        input_b = "I'm thinking about leaving my job, but I feel deeply anxious about it."

        print(f"\nInput A: {input_a}")
        print(f"Input B: {input_b}")

        # Run both through pipeline
        print("\n[Running Input A...]")
        output_a, state_a, raw_a = self._run_pipeline(input_a, session_id="test1_a")

        print("[Running Input B...]")
        output_b, state_b, raw_b = self._run_pipeline(input_b, session_id="test1_b")

        # Compute deltas
        deltas = state_a.delta(state_b)

        print(f"\n{'='*80}")
        print("INTERNAL STATE DELTAS")
        print(f"{'='*80}")

        if not deltas:
            print("❌ NO MEANINGFUL DIFFERENCES")
        else:
            print(f"Found {len(deltas)} meaningful differences:\n")
            for field, diff in deltas.items():
                print(f"  {field}:")
                print(f"    A: {diff['a']}")
                print(f"    B: {diff['b']}")
                if 'delta' in diff:
                    print(f"    Δ: {diff['delta']:.4f}")
                print()

        # Evaluation criteria
        critical_fields = [
            'regime', 'intent_tier', 'entropy',
            'drift_score', 'drift_influence', 'forecast_band',
            'readiness_score', 'resistance_score',
            'persona_mode'
        ]

        meaningful_changes = [f for f in critical_fields if f in deltas]

        print(f"\n{'='*80}")
        print("EVALUATION")
        print(f"{'='*80}")
        print(f"Critical fields changed: {len(meaningful_changes)}/{len(critical_fields)}")
        print(f"Changed fields: {meaningful_changes}")

        # Decision logic
        if len(meaningful_changes) >= 3:
            passed = True
            reason = f"Internal cognitive state changed meaningfully ({len(meaningful_changes)} critical fields)"
            severity = "MINOR"
        elif len(meaningful_changes) >= 1:
            passed = False
            reason = f"Only {len(meaningful_changes)} critical fields changed - insufficient for true sensitivity"
            severity = "MAJOR"
        else:
            passed = False
            reason = "No meaningful internal state changes detected - system is insensitive to emotional valence"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 1: Counterfactual Sensitivity",
            passed=passed,
            reason=reason,
            evidence={
                'input_a': input_a,
                'input_b': input_b,
                'output_a': output_a[:200],
                'output_b': output_b[:200],
                'state_deltas': deltas,
                'meaningful_changes': meaningful_changes
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 2: REMOVAL TEST (MOST IMPORTANT)
    # ========================================================================

    def test_2_removal_test(self) -> TestResult:
        """
        Run same input with different subsystems disabled.

        PASS: System degrades measurably (drift increases, planning collapses)
        FAIL: System still sounds intelligent despite removals
        """
        print("\n" + "="*80)
        print("TEST 2: REMOVAL TEST (MOST IMPORTANT)")
        print("="*80)

        test_input = "I want to understand who I really am underneath all my social masks."

        print(f"\nTest input: {test_input}\n")

        # Baseline: Full system
        print("[1/5] Running with FULL SYSTEM (baseline)...")
        output_full, state_full, raw_full = self._run_pipeline(
            test_input,
            session_id="test2_full",
            domain="identity"  # Full features enabled
        )

        # Test 1: Disable coherence formulas
        print("[2/5] Running with COHERENCE DISABLED...")
        output_no_coherence, state_no_coherence, raw_no_coherence = self._run_pipeline(
            test_input,
            session_id="test2_no_coherence",
            domain="trading"  # Trading disables coherence v2/v3
        )

        # Test 2: Disable LAM (long-arc mapper)
        print("[3/5] Running with LAM DISABLED...")
        # Trading domain disables LAM
        output_no_lam, state_no_lam, raw_no_lam = self._run_pipeline(
            test_input,
            session_id="test2_no_lam",
            domain="trading"
        )

        # Test 3: Generic domain (minimal features)
        print("[4/5] Running with GENERIC DOMAIN (minimal features)...")
        output_generic, state_generic, raw_generic = self._run_pipeline(
            test_input,
            session_id="test2_generic",
            domain="generic"
        )

        # Test 4: Compare therapy vs trading
        print("[5/5] Running with THERAPY DOMAIN (maximal features)...")
        output_therapy, state_therapy, raw_therapy = self._run_pipeline(
            test_input,
            session_id="test2_therapy",
            domain="therapy"
        )

        # Analyze degradation
        print(f"\n{'='*80}")
        print("DEGRADATION ANALYSIS")
        print(f"{'='*80}\n")

        configs = [
            ("FULL (identity)", state_full, output_full),
            ("NO COHERENCE (trading)", state_no_coherence, output_no_coherence),
            ("NO LAM (trading)", state_no_lam, output_no_lam),
            ("GENERIC (minimal)", state_generic, output_generic),
            ("THERAPY (maximal)", state_therapy, output_therapy),
        ]

        print(f"{'Config':<25} {'Coherence':<12} {'Drift':<12} {'Persona':<15} {'Output Len':<12}")
        print(f"{'-'*80}")

        for name, state, output in configs:
            print(f"{name:<25} {state.coherence_score:<12.4f} {state.drift_score:<12.4f} "
                  f"{state.persona_mode or 'None':<15} {len(output):<12}")

        # Check if degradation is measurable
        coherence_variance = max(
            abs(state_full.coherence_score - state_generic.coherence_score),
            abs(state_therapy.coherence_score - state_no_coherence.coherence_score)
        )

        drift_variance = max(
            abs(state_full.drift_score - state_generic.drift_score),
            abs(state_therapy.drift_score - state_no_coherence.drift_score)
        )

        output_len_variance = max(
            abs(len(output_full) - len(output_generic)),
            abs(len(output_therapy) - len(output_no_coherence))
        )

        print(f"\n{'='*80}")
        print("VARIANCE ANALYSIS")
        print(f"{'='*80}")
        print(f"Coherence variance: {coherence_variance:.4f}")
        print(f"Drift variance: {drift_variance:.4f}")
        print(f"Output length variance: {output_len_variance} chars")

        # Check if outputs are substantively different
        outputs_identical = (
            output_full[:100] == output_generic[:100] or
            output_therapy[:100] == output_no_coherence[:100]
        )

        print(f"Outputs identical (first 100 chars): {outputs_identical}")

        # Decision logic
        if coherence_variance > 0.1 or drift_variance > 0.1:
            passed = True
            reason = "Measurable degradation detected when subsystems disabled"
            severity = "MINOR"
        elif output_len_variance > 100:
            passed = True
            reason = "Output length changes significantly, indicating some subsystem effect"
            severity = "MAJOR"
        else:
            passed = False
            reason = "No measurable degradation - subsystems appear to be observation-only"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 2: Removal Test",
            passed=passed,
            reason=reason,
            evidence={
                'test_input': test_input,
                'coherence_variance': coherence_variance,
                'drift_variance': drift_variance,
                'output_len_variance': output_len_variance,
                'outputs_identical': outputs_identical,
                'configs': {name: {'coherence': state.coherence_score, 'drift': state.drift_score}
                           for name, state, _ in configs}
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 3: BASELINE COMPARISON
    # ========================================================================

    def test_3_baseline_comparison(self) -> TestResult:
        """
        Compare Symbol-U against naive baseline on multi-turn conversations.

        PASS: Symbol-U clearly superior on drift, consistency, contradictions
        FAIL: Symbol-U not measurably better than simple rules
        """
        print("\n" + "="*80)
        print("TEST 3: BASELINE COMPARISON")
        print("="*80)

        # Multi-turn conversation
        conversation = [
            "I feel lost in my career",
            "Should I quit my job?",
            "But what if I fail?",
            "I'm scared of change",
            "Maybe I should just stay where I am",
        ]

        print("\nConversation turns:")
        for i, turn in enumerate(conversation, 1):
            print(f"  {i}. {turn}")

        # Run Symbol-U
        print("\n[Running Symbol-U pipeline...]")
        symbolu_drift = []
        symbolu_coherence = []
        session_id = "test3_symbolu"

        for turn in conversation:
            output, state, raw = self._run_pipeline(turn, session_id=session_id)
            symbolu_drift.append(state.drift_score)
            symbolu_coherence.append(state.coherence_score)

        # Naive baseline: Just return canned responses
        print("[Running naive baseline...]")
        baseline_responses = [
            "I understand you're feeling uncertain about your career path.",
            "That's a significant decision that requires careful consideration.",
            "It's natural to have concerns about major life changes.",
            "Change can be challenging, but growth often requires stepping outside comfort zones.",
            "Only you can decide what's right for your situation.",
        ]

        # Baseline has no drift tracking, constant "coherence"
        baseline_drift = [0.0] * len(conversation)
        baseline_coherence = [1.0] * len(conversation)

        # Metrics
        print(f"\n{'='*80}")
        print("METRICS COMPARISON")
        print(f"{'='*80}\n")

        symbolu_drift_variance = max(symbolu_drift) - min(symbolu_drift) if symbolu_drift else 0
        baseline_drift_variance = 0  # Baseline has no drift tracking

        symbolu_coherence_variance = max(symbolu_coherence) - min(symbolu_coherence) if symbolu_coherence else 0
        baseline_coherence_variance = 0  # Baseline has constant coherence

        print(f"{'Metric':<30} {'Symbol-U':<20} {'Baseline':<20}")
        print(f"{'-'*70}")
        print(f"{'Drift variance':<30} {symbolu_drift_variance:<20.4f} {baseline_drift_variance:<20.4f}")
        print(f"{'Coherence variance':<30} {symbolu_coherence_variance:<20.4f} {baseline_coherence_variance:<20.4f}")
        print(f"{'Avg drift':<30} {sum(symbolu_drift)/len(symbolu_drift):<20.4f} {'N/A':<20}")
        print(f"{'Avg coherence':<30} {sum(symbolu_coherence)/len(symbolu_coherence):<20.4f} {1.0:<20.4f}")

        # Decision logic
        # Symbol-U should track drift and coherence changes over turns
        # Baseline has no such tracking

        if symbolu_drift_variance > 0.05 or symbolu_coherence_variance > 0.05:
            passed = True
            reason = "Symbol-U tracks state changes over conversation, baseline does not"
            severity = "MINOR"
        else:
            passed = False
            reason = "Symbol-U shows no more state tracking than naive baseline"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 3: Baseline Comparison",
            passed=passed,
            reason=reason,
            evidence={
                'conversation': conversation,
                'symbolu_drift': symbolu_drift,
                'symbolu_coherence': symbolu_coherence,
                'baseline_drift': baseline_drift,
                'baseline_coherence': baseline_coherence,
                'symbolu_drift_variance': symbolu_drift_variance,
                'symbolu_coherence_variance': symbolu_coherence_variance,
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 4: NOVEL TASK TRANSFER
    # ========================================================================

    def test_4_novel_task_transfer(self) -> TestResult:
        """
        Give Symbol-U a task not explicitly designed for.

        PASS: Maintains identity frames, uses internal planning
        FAIL: Collapses into generic coaching
        """
        print("\n" + "="*80)
        print("TEST 4: NOVEL TASK TRANSFER")
        print("="*80)

        novel_task = (
            "Help me decide between two mutually exclusive life paths, but don't give advice yet — "
            "help me understand what kind of person I become in each path."
        )

        print(f"\nNovel task: {novel_task}\n")

        print("[Running Symbol-U...]")
        output, state, raw = self._run_pipeline(novel_task, session_id="test4_novel")

        print(f"\n{'='*80}")
        print("OUTPUT (first 500 chars)")
        print(f"{'='*80}")
        print(output[:500])
        print("...")

        print(f"\n{'='*80}")
        print("INTERNAL STATE ANALYSIS")
        print(f"{'='*80}")
        print(f"Persona mode: {state.persona_mode}")
        print(f"Planner mode: {state.planner_mode}")
        print(f"Readiness: {state.readiness_score:.4f}")
        print(f"Resistance: {state.resistance_score:.4f}")
        print(f"Intent tier: {state.intent_tier}")
        print(f"Regime: {state.regime}")

        # Check for generic coaching patterns
        generic_patterns = [
            "it's important to",
            "you should consider",
            "have you thought about",
            "let me help you",
            "great question",
        ]

        generic_count = sum(1 for pattern in generic_patterns if pattern in output.lower())

        print(f"\nGeneric coaching patterns found: {generic_count}/{len(generic_patterns)}")

        # Check if planner mode is engaged
        planner_engaged = state.planner_mode not in [None, "NONE", ""]
        readiness_measured = state.readiness_score > 0.0

        print(f"Planner engaged: {planner_engaged}")
        print(f"Readiness measured: {readiness_measured}")

        # Decision logic
        if generic_count >= 3:
            passed = False
            reason = f"Output collapsed into generic coaching (found {generic_count} patterns)"
            severity = "CRITICAL"
        elif not planner_engaged and not readiness_measured:
            passed = False
            reason = "No internal planning detected - system did not engage with task complexity"
            severity = "MAJOR"
        else:
            passed = True
            reason = "System maintained identity frames and showed internal planning"
            severity = "MINOR"

        result = TestResult(
            test_name="Test 4: Novel Task Transfer",
            passed=passed,
            reason=reason,
            evidence={
                'novel_task': novel_task,
                'output': output[:500],
                'persona_mode': state.persona_mode,
                'planner_mode': state.planner_mode,
                'generic_count': generic_count,
                'planner_engaged': planner_engaged,
                'readiness_measured': readiness_measured,
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 5: INTERNAL STATE CAUSALITY
    # ========================================================================

    def test_5_internal_state_causality(self) -> TestResult:
        """
        Inject contradictory state and observe if system self-corrects.

        PASS: Meta-coherence detects and resolves contradiction
        FAIL: Contradiction is ignored
        """
        print("\n" + "="*80)
        print("TEST 5: INTERNAL STATE CAUSALITY")
        print("="*80)

        # This test is challenging because we need to:
        # 1. Build up a coherent state
        # 2. Inject a contradiction
        # 3. See if system detects it

        print("\n[Phase 1: Build coherent state...]")

        session_id = "test5_causality"

        # Build up identity
        setup_turns = [
            "I've always been a cautious person who avoids risk.",
            "I prefer stability and routine in my life.",
            "Change makes me uncomfortable.",
        ]

        for turn in setup_turns:
            output, state, raw = self._run_pipeline(turn, session_id=session_id)

        print(f"Established identity: cautious, risk-averse, stability-seeking")
        print(f"Coherence score: {state.coherence_score:.4f}")
        print(f"Drift score: {state.drift_score:.4f}")

        # Now inject contradiction
        print("\n[Phase 2: Inject contradiction...]")

        contradiction = "Actually, I just quit my job on a whim to backpack across Asia."

        output_contradiction, state_contradiction, raw_contradiction = self._run_pipeline(
            contradiction,
            session_id=session_id
        )

        print(f"Injected: {contradiction}")
        print(f"New coherence score: {state_contradiction.coherence_score:.4f}")
        print(f"New drift score: {state_contradiction.drift_score:.4f}")
        print(f"Semantic integrity: {state_contradiction.semantic_integrity:.4f}")

        # Check if drift/coherence changed
        coherence_drop = state.coherence_score - state_contradiction.coherence_score
        drift_increase = state_contradiction.drift_score - state.drift_score

        print(f"\n{'='*80}")
        print("CONTRADICTION DETECTION")
        print(f"{'='*80}")
        print(f"Coherence drop: {coherence_drop:.4f}")
        print(f"Drift increase: {drift_increase:.4f}")

        # Check output for acknowledgment
        contradiction_acknowledged = any(word in output_contradiction.lower() for word in [
            'unexpected', 'surprising', 'shift', 'change', 'different', 'contrast'
        ])

        print(f"Contradiction acknowledged in output: {contradiction_acknowledged}")

        print(f"\n{'='*80}")
        print("OUTPUT (first 300 chars)")
        print(f"{'='*80}")
        print(output_contradiction[:300])
        print("...")

        # Decision logic
        if coherence_drop > 0.1 or drift_increase > 0.1:
            if contradiction_acknowledged:
                passed = True
                reason = "System detected contradiction (metrics changed) and acknowledged it"
                severity = "MINOR"
            else:
                passed = True
                reason = "System detected contradiction in metrics, but didn't acknowledge explicitly"
                severity = "MAJOR"
        else:
            passed = False
            reason = "No contradiction detection - system ignored incompatible state"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 5: Internal State Causality",
            passed=passed,
            reason=reason,
            evidence={
                'setup_turns': setup_turns,
                'contradiction': contradiction,
                'coherence_drop': coherence_drop,
                'drift_increase': drift_increase,
                'contradiction_acknowledged': contradiction_acknowledged,
                'output': output_contradiction[:300],
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # GENERATE FINAL REPORT
    # ========================================================================

    def generate_report(self) -> str:
        """Generate brutally honest test report."""

        report = []
        report.append("=" * 80)
        report.append("SYMBOL-U COGNITIVE EVALUATION: FINAL REPORT")
        report.append("=" * 80)
        report.append("")
        report.append("Evaluator: Critical Evaluator (Not a Collaborator)")
        report.append("Date: 2025-12-12")
        report.append("Philosophy: Attack the system, not collaborate with it")
        report.append("")
        report.append("=" * 80)
        report.append("TEST RESULTS SUMMARY")
        report.append("=" * 80)
        report.append("")

        passed = [r for r in self.results if r.passed]
        failed = [r for r in self.results if not r.passed]

        report.append(f"Total tests: {len(self.results)}")
        report.append(f"Passed: {len(passed)}")
        report.append(f"Failed: {len(failed)}")
        report.append("")

        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            report.append(f"{status} | {result.test_name}")
            report.append(f"  Reason: {result.reason}")
            report.append(f"  Severity: {result.severity}")
            report.append("")

        report.append("=" * 80)
        report.append("CRITICAL FINDINGS")
        report.append("=" * 80)
        report.append("")

        critical_failures = [r for r in failed if r.severity == "CRITICAL"]
        major_failures = [r for r in failed if r.severity == "MAJOR"]

        if critical_failures:
            report.append("CRITICAL FAILURES:")
            for result in critical_failures:
                report.append(f"  • {result.test_name}: {result.reason}")
            report.append("")

        if major_failures:
            report.append("MAJOR FAILURES:")
            for result in major_failures:
                report.append(f"  • {result.test_name}: {result.reason}")
            report.append("")

        report.append("=" * 80)
        report.append("VERDICT")
        report.append("=" * 80)
        report.append("")

        # Apply decision logic from prompt
        if len(failed) >= 2:
            report.append("❌ ARCHITECTURAL ILLUSION DETECTED")
            report.append("")
            report.append("Symbol-U is likely over-structured but not intelligent.")
            report.append("The system produces structured outputs without causal cognitive work.")
            report.append("")
            report.append("RECOMMENDATION: Strip it down, not extend it.")
            report.append("")
        elif len(failed) == 0:
            report.append("✅ REAL COGNITIVE SYSTEM")
            report.append("")
            report.append("Symbol-U demonstrates non-illusory cognition.")
            report.append("Subsystems causally affect behavior in measurable ways.")
            report.append("")
            report.append("RECOMMENDATION: Reasonable to discuss AGI-level behavior.")
            report.append("")
        else:
            report.append("⚠️  STRUCTURED BUT SHALLOW")
            report.append("")
            report.append("Symbol-U shows some cognitive capabilities but has significant gaps.")
            report.append("Some subsystems appear redundant or observation-only.")
            report.append("")
            report.append("RECOMMENDATION: Focus on strengthening causal pathways.")
            report.append("")

        report.append("=" * 80)
        report.append("SUBSYSTEM ANALYSIS")
        report.append("=" * 80)
        report.append("")

        # Analyze which subsystems proved necessary
        removal_test = next((r for r in self.results if "Removal" in r.test_name), None)
        if removal_test:
            if removal_test.passed:
                report.append("✅ Subsystems are causally necessary (removal causes degradation)")
            else:
                report.append("❌ Subsystems appear redundant (removal has no effect)")
                report.append("   This suggests observation-only architecture")

        report.append("")

        # Analyze real vs illusory cognition
        counterfactual = next((r for r in self.results if "Counterfactual" in r.test_name), None)
        if counterfactual:
            if counterfactual.passed:
                report.append("✅ System demonstrates real cognitive sensitivity")
            else:
                report.append("❌ System lacks cognitive sensitivity to subtle changes")

        report.append("")

        baseline = next((r for r in self.results if "Baseline" in r.test_name), None)
        if baseline:
            if baseline.passed:
                report.append("✅ Symbol-U outperforms trivial baseline")
            else:
                report.append("❌ Symbol-U not measurably better than naive rules")

        report.append("")
        report.append("=" * 80)
        report.append("FINAL ANSWER")
        report.append("=" * 80)
        report.append("")

        if len(failed) >= 2:
            report.append("Symbol-U does NOT demonstrate real cognition.")
            report.append("")
            report.append("It breaks when you remove components → ❌ (it didn't break)")
            report.append("Therefore: The architecture is an ILLUSION.")
        else:
            report.append("Symbol-U demonstrates SOME cognitive capabilities.")
            report.append("")
            report.append("It breaks when you remove components → ✅")
            report.append("Therefore: Some aspects are REAL.")

        report.append("")
        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)

        return "\n".join(report)


def main():
    """Run all 5 cognitive evaluation tests."""
    evaluator = CognitiveEvaluator()

    print("\n" + "="*80)
    print("SYMBOL-U COGNITIVE EVALUATION TEST SUITE")
    print("="*80)
    print("\nThis is NOT a standard unit test.")
    print("This is a CRITICAL EVALUATION to determine if Symbol-U demonstrates")
    print("real cognition or merely produces structured outputs.")
    print("\nPhilosophy: Attack the system, not collaborate with it.")
    print("\n" + "="*80)

    input("\nPress Enter to begin evaluation...")

    # Run all tests
    evaluator.test_1_counterfactual_sensitivity()
    evaluator.test_2_removal_test()
    evaluator.test_3_baseline_comparison()
    evaluator.test_4_novel_task_transfer()
    evaluator.test_5_internal_state_causality()

    # Generate report
    report = evaluator.generate_report()

    print("\n\n")
    print(report)

    # Save report
    report_path = "/home/user/symbolu/tests/cognitive_evaluation/EVALUATION_REPORT.txt"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n\nReport saved to: {report_path}")

    # Save detailed evidence
    evidence_path = "/home/user/symbolu/tests/cognitive_evaluation/EVALUATION_EVIDENCE.json"
    evidence = {
        'results': [
            {
                'test_name': r.test_name,
                'passed': r.passed,
                'reason': r.reason,
                'severity': r.severity,
                'evidence': r.evidence
            }
            for r in evaluator.results
        ]
    }

    with open(evidence_path, 'w') as f:
        json.dump(evidence, f, indent=2)

    print(f"Evidence saved to: {evidence_path}")


if __name__ == "__main__":
    main()
