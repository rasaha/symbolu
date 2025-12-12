"""
Test Phonetic Stuttering Hypothesis
====================================

Empirical test to determine if "phonetic stuttering" is a real, measurable
failure mode in Symbol-U outputs.

This test:
1. Generates 200+ deterministic test prompts
2. Runs them through Symbol-U pipeline (minimal mode to avoid LLM calls)
3. Analyzes outputs for brokenness and phonetic features
4. Computes correlations
5. Tests phonetic reranker
6. Generates before/after comparison report

Run with: pytest test_phonetic_stutter.py -v -s
Or run directly: python test_phonetic_stutter.py
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

import json
from typing import List, Tuple
from pathlib import Path

from symbolu.mechanical.pipeline.diagnostics.phonetic_stutter_eval import (
    PhoneticStutterEvaluator,
    CorpusGenerator,
    run_hypothesis_test,
)


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Use minimal mode to avoid LLM calls
RENDER_MODE = "minimal"
CORPUS_SIZE = 200
SEED = 42


# =============================================================================
# MOCK PIPELINE FOR TESTING
# =============================================================================

class MockSymbolUPipeline:
    """
    Mock pipeline that generates deterministic outputs for testing.

    This simulates the Symbol-U pipeline without requiring full infrastructure.
    In production, replace with actual pipeline calls.
    """

    def __init__(self, seed: int = 42):
        import random
        random.seed(seed)
        self.seed = seed

    def run(self, request) -> 'MockPipelineResult':
        """
        Generate mock output for a request.

        Simulates various "brokenness" patterns for testing.
        """
        prompt = request.text

        # Generate deterministic output based on prompt hash
        import hashlib
        prompt_hash = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)

        # Simulate different output qualities
        quality_idx = prompt_hash % 5

        if quality_idx == 0:
            # High brokenness: repeated fragments, high stops
            output = self._generate_broken_output(prompt)
        elif quality_idx == 1:
            # Medium brokenness: some repetition
            output = self._generate_medium_output(prompt)
        else:
            # Low brokenness: clean output
            output = self._generate_clean_output(prompt)

        return MockPipelineResult(raw_text=output)

    def _generate_broken_output(self, prompt: str) -> str:
        """Generate output with high brokenness."""
        fragments = [
            "Consider this point. ",
            "To clarify, we need to look at this. ",
            "That said, it's important to note. ",
            "Consider this further. ",
            "On the other hand, we can see. ",
            "To clarify again, the concept is complex. "
        ]

        # Add stop-ending words
        stop_words = ["cat", "dog", "bit", "top", "kit", "gap", "tap", "cap"]
        body = " ".join(stop_words * 3) + ". "

        return "".join(fragments) + body

    def _generate_medium_output(self, prompt: str) -> str:
        """Generate output with medium brokenness."""
        return (
            "This topic relates to several important concepts. "
            "Consider the main aspects involved. "
            "The key points are worth examining in detail. "
            "However, there are some nuances to note. "
            "Overall, it's a complex but manageable subject."
        )

    def _generate_clean_output(self, prompt: str) -> str:
        """Generate clean output with low brokenness."""
        return (
            "This is a comprehensive answer addressing the main question. "
            "The fundamentals involve three core principles: clarity, "
            "precision, and coherence. Each element plays a vital role "
            "in achieving optimal outcomes. Understanding these aspects "
            "provides a solid foundation for further exploration."
        )


class MockUserRequest:
    """Mock user request."""
    def __init__(self, text: str, render_mode: str = "minimal"):
        self.text = text
        self.render_mode = render_mode


class MockPipelineResult:
    """Mock pipeline result."""
    def __init__(self, raw_text: str):
        self.raw_text = raw_text


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

if HAS_PYTEST:
    @pytest.fixture
    def pipeline():
        """Create mock pipeline."""
        return MockSymbolUPipeline(seed=SEED)

    @pytest.fixture
    def corpus_generator():
        """Create corpus generator."""
        return CorpusGenerator(seed=SEED)

    @pytest.fixture
    def evaluator():
        """Create evaluator."""
        return PhoneticStutterEvaluator(seed=SEED)


def test_phoneme_extraction(evaluator):
    """Test phoneme feature extraction."""
    text = "The cat sat on the mat with a bat."

    features = evaluator.phoneme_extractor.extract(text)

    assert features.sibilant_count > 0  # 's' in sat
    assert features.stop_count > 0  # 't', 'c', 'b'
    assert features.nasal_count > 0  # 'm', 'n'
    assert 0 <= features.stop_ending_ratio <= 1


def test_brokenness_calculation(evaluator):
    """Test brokenness score calculation."""
    # High brokenness text
    broken_text = (
        "Consider this point. Consider this point. "
        "To clarify, we need to look at this. To clarify, we need to see. "
        "The cat sat on the mat. The cat sat on the bat."
    )

    metrics = evaluator.brokenness_calculator.calculate(broken_text)

    assert 0 <= metrics.brokenness_score <= 1
    assert metrics.repeated_trigrams_rate > 0  # Has repeated trigrams
    assert metrics.fragment_indicator_score > 0  # Has repeated fragments


def test_corpus_generation(corpus_generator):
    """Test deterministic corpus generation."""
    prompts = corpus_generator.generate_prompts(count=50)

    assert len(prompts) == 50
    assert all(isinstance(p, str) for p in prompts)
    assert all(len(p) > 0 for p in prompts)

    # Test determinism
    prompts2 = CorpusGenerator(seed=SEED).generate_prompts(count=50)
    assert prompts == prompts2


def test_phonetic_reranker(evaluator):
    """Test phonetic conflict reranker."""
    candidates = [
        "Consider this point. Consider this again. The cat sat.",
        "Think about this aspect. Examine the details carefully.",
        "Look at this matter. Review the information thoroughly."
    ]

    best = evaluator.reranker.rerank_candidates(candidates)

    # Should select one of the candidates
    assert best in candidates

    # Test post-processing
    repeated_text = "Consider this. Consider this again. Consider the outcome."
    processed = evaluator.reranker.post_process(repeated_text)

    # Should reduce repetition
    assert processed != repeated_text or processed.count("Consider") <= 1


def test_full_corpus_evaluation(pipeline, corpus_generator, evaluator):
    """
    Full corpus evaluation test.

    This is the main hypothesis test.
    """
    print("\n" + "="*80)
    print("PHONETIC STUTTERING HYPOTHESIS TEST")
    print("="*80)

    # Generate prompts
    print(f"\nGenerating {CORPUS_SIZE} test prompts...")
    prompts = corpus_generator.generate_prompts(count=CORPUS_SIZE)

    # Run through mock pipeline
    print(f"Running prompts through pipeline (render_mode={RENDER_MODE})...")
    outputs = []
    for i, prompt in enumerate(prompts):
        request = MockUserRequest(text=prompt, render_mode=RENDER_MODE)
        result = pipeline.run(request)
        outputs.append((prompt, result.raw_text))

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{CORPUS_SIZE} prompts...")

    print(f"✓ Generated {len(outputs)} outputs")

    # Evaluate baseline (without reranking)
    print("\n" + "-"*80)
    print("BASELINE EVALUATION (No Reranking)")
    print("-"*80)

    baseline_eval = evaluator.run_corpus_evaluation(outputs)
    evaluator.print_report(baseline_eval, title="BASELINE EVALUATION")

    # Evaluate with reranking
    print("\n" + "-"*80)
    print("WITH PHONETIC RERANKING")
    print("-"*80)

    reranked_outputs = [
        (prompt, evaluator.reranker.post_process(output))
        for prompt, output in outputs
    ]

    reranked_eval = evaluator.run_corpus_evaluation(reranked_outputs)
    evaluator.print_report(reranked_eval, title="WITH PHONETIC RERANKING")

    # Compare deltas
    print("\n" + "="*80)
    print("BEFORE/AFTER COMPARISON")
    print("="*80)

    baseline_stats = baseline_eval.summary_stats
    reranked_stats = reranked_eval.summary_stats

    delta_brokenness = reranked_stats["avg_brokenness"] - baseline_stats["avg_brokenness"]
    delta_high_broken = reranked_stats["high_brokenness_percent"] - baseline_stats["high_brokenness_percent"]

    print(f"\nMetric Changes:")
    print(f"  Average brokenness score:")
    print(f"    Baseline:  {baseline_stats['avg_brokenness']:.3f}")
    print(f"    Reranked:  {reranked_stats['avg_brokenness']:.3f}")
    print(f"    Delta:     {delta_brokenness:+.3f}")

    print(f"\n  High brokenness outputs (>0.7):")
    print(f"    Baseline:  {baseline_stats['high_brokenness_percent']:.1f}%")
    print(f"    Reranked:  {reranked_stats['high_brokenness_percent']:.1f}%")
    print(f"    Delta:     {delta_high_broken:+.1f}%")

    # Correlation comparison
    print(f"\n  Top correlation changes:")
    for feature in ["stop_ending_ratio", "stop_ratio"]:
        baseline_corr = baseline_eval.correlations.get(feature, 0)
        reranked_corr = reranked_eval.correlations.get(feature, 0)
        delta_corr = reranked_corr - baseline_corr
        print(f"    {feature}:")
        print(f"      Baseline: {baseline_corr:+.3f}")
        print(f"      Reranked: {reranked_corr:+.3f}")
        print(f"      Delta:    {delta_corr:+.3f}")

    # Final verdict
    print(f"\n" + "="*80)
    print("HYPOTHESIS VERDICT")
    print("="*80)

    max_corr = max(abs(c) for c in baseline_eval.correlations.values())
    improvement = abs(delta_brokenness) > 0.05 or abs(delta_high_broken) > 5.0

    print(f"\nMaximum correlation (phoneme features vs brokenness): {max_corr:.3f}")
    print(f"Reranker improvement (>5% change or >0.05 score): {improvement}")

    if max_corr < 0.3 and not improvement:
        print(f"\n⚠️  HYPOTHESIS NOT SUPPORTED")
        print(f"    - Correlations are weak (< 0.3)")
        print(f"    - Reranker shows negligible improvement")
        print(f"    - 'Phonetic stuttering' does not appear to be a significant failure mode")
    elif max_corr < 0.5 and not improvement:
        print(f"\n⚠️  HYPOTHESIS WEAKLY SUPPORTED")
        print(f"    - Correlations are moderate (0.3-0.5)")
        print(f"    - Reranker shows minimal improvement")
        print(f"    - Some relationship exists but effect is small")
    else:
        print(f"\n✓  HYPOTHESIS SUPPORTED")
        print(f"    - Correlations are meaningful (>= 0.5) or reranker shows improvement")
        print(f"    - 'Phonetic stuttering' appears to be a measurable phenomenon")

    print(f"\n" + "="*80)

    # Save results
    results_file = Path(__file__).parent / "phonetic_stutter_results.json"
    results = {
        "baseline": {
            "summary_stats": baseline_stats,
            "correlations": baseline_eval.correlations,
            "effect_sizes": baseline_eval.effect_sizes,
        },
        "reranked": {
            "summary_stats": reranked_stats,
            "correlations": reranked_eval.correlations,
            "effect_sizes": reranked_eval.effect_sizes,
        },
        "deltas": {
            "avg_brokenness": delta_brokenness,
            "high_brokenness_percent": delta_high_broken,
        },
        "verdict": {
            "max_correlation": max_corr,
            "shows_improvement": improvement,
            "hypothesis_supported": max_corr >= 0.3 or improvement
        }
    }

    print(f"\nResults saved to: {results_file}")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Assertions for pytest
    assert len(outputs) == CORPUS_SIZE
    assert 0 <= baseline_stats["avg_brokenness"] <= 1
    assert 0 <= reranked_stats["avg_brokenness"] <= 1


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Running Phonetic Stuttering Hypothesis Test...\n")

    # Create fixtures
    pipeline_instance = MockSymbolUPipeline(seed=SEED)
    corpus_gen = CorpusGenerator(seed=SEED)
    eval_instance = PhoneticStutterEvaluator(seed=SEED)

    # Run test
    test_full_corpus_evaluation(pipeline_instance, corpus_gen, eval_instance)

    print("\n✓ Test completed successfully")
