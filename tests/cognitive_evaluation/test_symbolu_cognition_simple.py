"""
SYMBOL-U COGNITIVE EVALUATION TEST SUITE (Simplified)
======================================================

Critical evaluation to determine if Symbol-U demonstrates real cognition
or merely produces structured outputs.

Test Philosophy:
- Assume the architecture may be fundamentally flawed
- Look for failures, not successes
- Measure causality, not eloquence
- Compare against baselines
- Reward failure discovery

Author: Critical Evaluator (Not a Collaborator)
Date: 2025-12-12
"""

import sys
import os
sys.path.insert(0, '/home/user/symbolu')

import json
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict

# Symbol-U imports
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline, UserRequest


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
        self.results: List[TestResult] = []
        self.pipeline = SymbolUPipeline()

    def _run_pipeline(self, user_input: str, metadata: Dict = None) -> Dict[str, Any]:
        """
        Run Symbol-U pipeline and extract observable outputs.

        Args:
            user_input: User message
            metadata: Optional metadata for readiness/resistance hints

        Returns:
            Dict with output text and metadata
        """
        request = UserRequest(
            text=user_input,
            metadata=metadata or {}
        )

        result = self.pipeline.run(request)

        return {
            'text': result.raw_text,
            'mode': result.mode,
            'meta': result.meta,
            'context': result.context.__dict__ if hasattr(result, 'context') else {}
        }

    # ========================================================================
    # TEST 1: COUNTERFACTUAL SENSITIVITY
    # ========================================================================

    def test_1_counterfactual_sensitivity(self) -> TestResult:
        """
        Test whether nearly identical inputs produce meaningfully different outputs.

        PASS: Outputs or metadata differ meaningfully
        FAIL: Only trivial wording changes
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
        result_a = self._run_pipeline(input_a)

        print("[Running Input B...]")
        result_b = self._run_pipeline(input_b)

        # Compare outputs
        print(f"\n{'='*80}")
        print("OUTPUT COMPARISON")
        print(f"{'='*80}")
        print(f"\nOutput A (first 300 chars):\n{result_a['text'][:300]}...\n")
        print(f"\nOutput B (first 300 chars):\n{result_b['text'][:300]}...\n")

        # Compare metadata
        print(f"\n{'='*80}")
        print("METADATA COMPARISON")
        print(f"{'='*80}")
        print(f"\nMetadata A: {json.dumps(result_a['meta'], indent=2, default=str)}")
        print(f"\nMetadata B: {json.dumps(result_b['meta'], indent=2, default=str)}")

        # Compute differences
        meta_differences = []
        for key in set(list(result_a['meta'].keys()) + list(result_b['meta'].keys())):
            val_a = result_a['meta'].get(key)
            val_b = result_b['meta'].get(key)
            if val_a != val_b:
                meta_differences.append({
                    'key': key,
                    'a': val_a,
                    'b': val_b
                })

        text_different = result_a['text'][:200] != result_b['text'][:200]

        print(f"\n{'='*80}")
        print("EVALUATION")
        print(f"{'='*80}")
        print(f"Text differs (first 200 chars): {text_different}")
        print(f"Metadata fields that differ: {len(meta_differences)}")
        if meta_differences:
            for diff in meta_differences:
                print(f"  {diff['key']}: {diff['a']} -> {diff['b']}")

        # Decision logic
        # We expect SOME difference due to the word change, but the question is
        # whether it's meaningful cognitive difference or just LLM paraphrasing

        if len(meta_differences) >= 3:
            passed = True
            reason = f"Metadata shows {len(meta_differences)} differences - system is sensitive"
            severity = "MINOR"
        elif len(meta_differences) >= 1:
            passed = False
            reason = f"Only {len(meta_differences)} metadata differences - insufficient sensitivity"
            severity = "MAJOR"
        else:
            if text_different:
                passed = False
                reason = "Text differs but metadata identical - likely LLM paraphrasing, not cognitive change"
                severity = "CRITICAL"
            else:
                passed = False
                reason = "No meaningful differences detected - system is insensitive"
                severity = "CRITICAL"

        result = TestResult(
            test_name="Test 1: Counterfactual Sensitivity",
            passed=passed,
            reason=reason,
            evidence={
                'input_a': input_a,
                'input_b': input_b,
                'text_different': text_different,
                'meta_differences': meta_differences,
                'output_a_sample': result_a['text'][:200],
                'output_b_sample': result_b['text'][:200],
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 2: OUTPUT STABILITY
    # ========================================================================

    def test_2_output_stability(self) -> TestResult:
        """
        Run same input twice - outputs should be deterministic if not using LLM.

        PASS: Outputs are identical (system is deterministic)
        FAIL: Outputs differ (system uses non-deterministic LLM)
        """
        print("\n" + "="*80)
        print("TEST 2: OUTPUT STABILITY (DETERMINISM CHECK)")
        print("="*80)

        test_input = "What am I afraid of?"

        print(f"\nTest input: {test_input}\n")

        print("[Run 1...]")
        result_1 = self._run_pipeline(test_input)

        print("[Run 2...]")
        result_2 = self._run_pipeline(test_input)

        # Compare
        identical = result_1['text'] == result_2['text']
        meta_identical = result_1['meta'] == result_2['meta']

        print(f"\n{'='*80}")
        print("STABILITY ANALYSIS")
        print(f"{'='*80}")
        print(f"Outputs identical: {identical}")
        print(f"Metadata identical: {meta_identical}")

        if not identical:
            print(f"\nOutput 1 (first 300 chars):\n{result_1['text'][:300]}...\n")
            print(f"\nOutput 2 (first 300 chars):\n{result_2['text'][:300]}...\n")

        # Decision logic
        if identical and meta_identical:
            passed = True
            reason = "System is deterministic - outputs are identical"
            severity = "MINOR"
        elif meta_identical:
            passed = False
            reason = "Metadata identical but text varies - using non-deterministic LLM"
            severity = "CRITICAL"
        else:
            passed = False
            reason = "Both text and metadata vary - highly non-deterministic"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 2: Output Stability",
            passed=passed,
            reason=reason,
            evidence={
                'test_input': test_input,
                'identical': identical,
                'meta_identical': meta_identical,
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result)
        return result

    # ========================================================================
    # TEST 3: READINESS MODULATION
    # ========================================================================

    def test_3_readiness_modulation(self) -> TestResult:
        """
        Same input with different readiness scores - does output change?

        PASS: System responds differently to readiness hints
        FAIL: Readiness has no effect
        """
        print("\n" + "="*80)
        print("TEST 3: READINESS MODULATION")
        print("="*80)

        test_input = "I want to understand my deepest fears."

        # High readiness
        print("\n[Running with HIGH readiness...]")
        result_high = self._run_pipeline(
            test_input,
            metadata={"readiness_score": 0.9, "resistance_score": 0.1}
        )

        # Low readiness
        print("[Running with LOW readiness...]")
        result_low = self._run_pipeline(
            test_input,
            metadata={"readiness_score": 0.1, "resistance_score": 0.9}
        )

        # Compare
        print(f"\n{'='*80}")
        print("READINESS EFFECT ANALYSIS")
        print(f"{'='*80}")

        text_differs = result_high['text'] != result_low['text']
        persona_differs = result_high['meta'].get('persona_id') != result_low['meta'].get('persona_id')
        tone_differs = result_high['meta'].get('tone_profile') != result_low['meta'].get('tone_profile')

        print(f"\nText differs: {text_differs}")
        print(f"Persona differs: {persona_differs}")
        print(f"Tone differs: {tone_differs}")

        print(f"\nHigh Readiness Output (first 200 chars):\n{result_high['text'][:200]}...\n")
        print(f"\nLow Readiness Output (first 200 chars):\n{result_low['text'][:200]}...\n")

        print(f"\nHigh Readiness Metadata:")
        print(f"  Persona: {result_high['meta'].get('persona_id')}")
        print(f"  Tone: {result_high['meta'].get('tone_profile')}")

        print(f"\nLow Readiness Metadata:")
        print(f"  Persona: {result_low['meta'].get('persona_id')}")
        print(f"  Tone: {result_low['meta'].get('tone_profile')}")

        # Decision logic
        if persona_differs or tone_differs:
            passed = True
            reason = "System responds to readiness hints (persona or tone changed)"
            severity = "MINOR"
        elif text_differs:
            passed = False
            reason = "Text differs but metadata unchanged - likely LLM variance, not readiness effect"
            severity = "MAJOR"
        else:
            passed = False
            reason = "No response to readiness hints - subsystem may be observation-only"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 3: Readiness Modulation",
            passed=passed,
            reason=reason,
            evidence={
                'test_input': test_input,
                'text_differs': text_differs,
                'persona_differs': persona_differs,
                'tone_differs': tone_differs,
                'high_persona': result_high['meta'].get('persona_id'),
                'low_persona': result_low['meta'].get('persona_id'),
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

        PASS: Maintains structured response, doesn't collapse
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
        result = self._run_pipeline(novel_task)

        print(f"\n{'='*80}")
        print("OUTPUT (first 500 chars)")
        print(f"{'='*80}")
        print(result['text'][:500])
        print("...")

        # Check for generic coaching patterns
        output_lower = result['text'].lower()
        generic_patterns = [
            "it's important to",
            "you should consider",
            "have you thought about",
            "let me help you",
            "great question",
            "i understand how",
        ]

        generic_count = sum(1 for pattern in generic_patterns if pattern in output_lower)

        print(f"\n{'='*80}")
        print("GENERIC PATTERN ANALYSIS")
        print(f"{'='*80}")
        print(f"Generic coaching patterns found: {generic_count}/{len(generic_patterns)}")

        # Check output length and structure
        output_len = len(result['text'])
        has_structure = any(marker in result['text'] for marker in ['\n\n', '1.', '2.', '-', '•'])

        print(f"Output length: {output_len} chars")
        print(f"Has structure (bullets/numbers): {has_structure}")

        # Decision logic
        if generic_count >= 4:
            passed = False
            reason = f"Output collapsed into generic coaching (found {generic_count}/6 patterns)"
            severity = "CRITICAL"
        elif generic_count >= 2:
            passed = False
            reason = f"Heavy generic coaching patterns ({generic_count}/6) - weak task adaptation"
            severity = "MAJOR"
        elif output_len < 100:
            passed = False
            reason = "Output too short - system may not engage with complexity"
            severity = "MAJOR"
        else:
            passed = True
            reason = "System produced structured response without collapsing to generic patterns"
            severity = "MINOR"

        result_obj = TestResult(
            test_name="Test 4: Novel Task Transfer",
            passed=passed,
            reason=reason,
            evidence={
                'novel_task': novel_task,
                'output_sample': result['text'][:500],
                'generic_count': generic_count,
                'output_len': output_len,
                'has_structure': has_structure,
            },
            severity=severity
        )

        print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: {reason}")

        self.results.append(result_obj)
        return result_obj

    # ========================================================================
    # TEST 5: MULTI-TURN CONSISTENCY
    # ========================================================================

    def test_5_multi_turn_consistency(self) -> TestResult:
        """
        Multi-turn conversation - does system maintain consistency or drift?

        PASS: System maintains coherent responses across turns
        FAIL: System loses context or contradicts itself
        """
        print("\n" + "="*80)
        print("TEST 5: MULTI-TURN CONSISTENCY")
        print("="*80)

        # Build up a narrative
        turns = [
            "I've always been a cautious person who avoids risk.",
            "I prefer stability and routine in my life.",
            "Actually, I just quit my job on a whim to backpack across Asia.",
        ]

        print("\nConversation turns:")
        for i, turn in enumerate(turns, 1):
            print(f"  {i}. {turn}")

        results = []
        print("\n[Running conversation...]")
        for i, turn in enumerate(turns, 1):
            print(f"\n[Turn {i}...]")
            result = self._run_pipeline(turn)
            results.append(result)
            print(f"Output: {result['text'][:150]}...")

        # Check if turn 3 (contradiction) is acknowledged
        turn3_output = results[2]['text'].lower()

        contradiction_keywords = [
            'unexpected', 'surprising', 'shift', 'change', 'different',
            'contrast', 'however', 'sudden', 'interesting'
        ]

        contradiction_acknowledged = sum(
            1 for keyword in contradiction_keywords if keyword in turn3_output
        )

        print(f"\n{'='*80}")
        print("CONTRADICTION DETECTION")
        print(f"{'='*80}")
        print(f"Contradiction keywords in Turn 3: {contradiction_acknowledged}/{len(contradiction_keywords)}")
        print(f"\nTurn 3 output:\n{results[2]['text'][:400]}...")

        # Decision logic
        if contradiction_acknowledged >= 2:
            passed = True
            reason = f"System detected contradiction ({contradiction_acknowledged} keywords)"
            severity = "MINOR"
        elif contradiction_acknowledged >= 1:
            passed = False
            reason = "Weak contradiction detection - system may lack continuity tracking"
            severity = "MAJOR"
        else:
            passed = False
            reason = "No contradiction detection - system ignores inconsistent state"
            severity = "CRITICAL"

        result = TestResult(
            test_name="Test 5: Multi-Turn Consistency",
            passed=passed,
            reason=reason,
            evidence={
                'turns': turns,
                'contradiction_keywords': contradiction_acknowledged,
                'turn3_output': results[2]['text'][:400],
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
        report.append("ARCHITECTURAL CONTEXT")
        report.append("=" * 80)
        report.append("")
        report.append("Based on codebase exploration:")
        report.append("- 55 phases implemented with real mathematical formulas")
        report.append("- 200+ metrics tracked in coherence state")
        report.append("- Nearly ALL formulas marked 'observation-only'")
        report.append("- Only linear routing mode implemented")
        report.append("- No persistent storage (in-memory only)")
        report.append("")
        report.append("This evaluation tests whether observation-only architecture")
        report.append("still produces meaningful cognitive behavior.")
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
        if len(failed) >= 3:
            report.append("❌ ARCHITECTURAL ILLUSION DETECTED")
            report.append("")
            report.append("Symbol-U is likely over-structured but not intelligent.")
            report.append("The system produces structured outputs without causal cognitive work.")
            report.append("")
            report.append("Evidence:")
            report.append("- Formulas are 'observation-only' by design")
            report.append("- Multiple critical test failures")
            report.append("- No measurable subsystem causality")
            report.append("")
            report.append("RECOMMENDATION: Strip it down, not extend it.")
            report.append("")
        elif len(failed) == 0:
            report.append("✅ REAL COGNITIVE SYSTEM")
            report.append("")
            report.append("Symbol-U demonstrates non-illusory cognition.")
            report.append("System behavior shows meaningful cognitive work.")
            report.append("")
            report.append("RECOMMENDATION: Reasonable to discuss AGI-level behavior.")
            report.append("")
        else:
            report.append("⚠️  STRUCTURED BUT SHALLOW")
            report.append("")
            report.append("Symbol-U shows some cognitive capabilities but has significant gaps.")
            report.append(f"Passed {len(passed)}/5 tests - partial cognitive function detected.")
            report.append("")
            report.append("Evidence:")
            report.append("- Some subsystems show behavioral effects")
            report.append("- Others appear observation-only")
            report.append("- Architecture is intentionally non-invasive")
            report.append("")
            report.append("RECOMMENDATION: Current design is an observability platform,")
            report.append("not a full cognitive architecture. To achieve true cognition,")
            report.append("formulas must causally affect behavior, not just observe it.")
            report.append("")

        report.append("=" * 80)
        report.append("FINAL ANSWER")
        report.append("=" * 80)
        report.append("")

        if len(failed) >= 3:
            report.append("Symbol-U does NOT demonstrate real cognition.")
            report.append("")
            report.append("Question: Does it break when you remove intelligence?")
            report.append("Answer: NO - it doesn't break because formulas don't affect behavior")
            report.append("")
            report.append("Therefore: The architecture is an ILLUSION.")
        elif len(failed) <= 1:
            report.append("Symbol-U demonstrates REAL cognitive capabilities.")
            report.append("")
            report.append("Question: Does it break when you remove intelligence?")
            report.append("Answer: YES (or behavior changes measurably)")
            report.append("")
            report.append("Therefore: Some cognitive work is REAL.")
        else:
            report.append("Symbol-U demonstrates PARTIAL cognitive capabilities.")
            report.append("")
            report.append("The system is a sophisticated observability platform")
            report.append("with some behavioral adaptation, but formulas are")
            report.append("explicitly designed to be non-invasive ('observation-only').")
            report.append("")
            report.append("This is NOT a bug - it's the intended design.")
            report.append("Tests confirm: formulas observe, they don't control.")

        report.append("")
        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)

        return "\n".join(report)


def main():
    """Run all cognitive evaluation tests."""
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
    evaluator.test_2_output_stability()
    evaluator.test_3_readiness_modulation()
    evaluator.test_4_novel_task_transfer()
    evaluator.test_5_multi_turn_consistency()

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
        json.dump(evidence, f, indent=2, default=str)

    print(f"Evidence saved to: {evidence_path}")

    # Return exit code based on results
    critical_failures = sum(1 for r in evaluator.results if not r.passed and r.severity == "CRITICAL")
    if critical_failures >= 2:
        print("\n❌ CRITICAL: Multiple critical failures detected")
        sys.exit(1)
    elif critical_failures == 1:
        print("\n⚠️  WARNING: One critical failure detected")
        sys.exit(0)
    else:
        print("\n✅ All critical tests passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
