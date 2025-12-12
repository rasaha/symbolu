"""
Test Script for Phonetic Stuttering Evaluation
===============================================

Runs the full phonetic stuttering evaluation:
1. Generates corpus of synthetic outputs (deterministic)
2. Evaluates baseline brokenness and phonetic features
3. Computes correlations
4. Applies phonetic optimizer
5. Re-evaluates and compares

Run with:
    pytest test_phonetic_stutter.py -v -s
    python test_phonetic_stutter.py
"""

import json
import os
from typing import List, Dict
import hashlib

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

from .phonetic_stutter_eval import (
    PhoneticStutterEvaluator,
    BrokennessScore,
    PhoneticFeatures,
    EvaluationResult,
    evaluate_phonetic_stuttering
)


# =============================================================================
# SYNTHETIC OUTPUT GENERATOR
# =============================================================================

class SyntheticOutputGenerator:
    """
    Generates synthetic but realistic text outputs for testing.

    Creates outputs with varying levels of:
    - Brokenness (repetition, fragments, etc.)
    - Phonetic features (sibilants, stops, etc.)
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def generate_corpus(self, prompts: List[str]) -> List[str]:
        """
        Generate synthetic outputs for prompts.

        Args:
            prompts: List of input prompts

        Returns:
            List of synthetic output texts
        """
        outputs = []

        for i, prompt in enumerate(prompts):
            # Use hash for deterministic variation
            hash_val = int(hashlib.md5(f"{self.seed}_{i}_{prompt}".encode()).hexdigest(), 16)

            # Vary brokenness level (0-2: low, 3-5: medium, 6-9: high)
            brokenness_level = hash_val % 10

            if brokenness_level < 3:
                output = self._generate_clean_output(prompt, hash_val)
            elif brokenness_level < 6:
                output = self._generate_medium_output(prompt, hash_val)
            else:
                output = self._generate_broken_output(prompt, hash_val)

            outputs.append(output)

        return outputs

    def _generate_clean_output(self, prompt: str, seed: int) -> str:
        """Generate clean, non-broken output."""
        templates = [
            "{topic} involves multiple interconnected concepts. The fundamental principles include systematic analysis and practical application. Research demonstrates clear benefits across various domains.",
            "Understanding {topic} requires examining core mechanisms. Key factors include structural components and functional relationships. Evidence supports widespread adoption in relevant fields.",
            "{topic} represents a significant advancement. Primary advantages include improved efficiency and enhanced capabilities. Implementation follows established methodologies with proven results.",
        ]

        template_idx = seed % len(templates)
        topic = prompt.replace("What is ", "").replace("?", "").replace("Explain ", "")
        return templates[template_idx].format(topic=topic.strip())

    def _generate_medium_output(self, prompt: str, seed: int) -> str:
        """Generate medium brokenness output (some repetition/fragments)."""
        fragments = ["Consider this: ", "To clarify, ", "That said, ", "It should be noted that "]
        topic = prompt.replace("What is ", "").replace("?", "").replace("Explain ", "").strip()

        fragment_idx = seed % len(fragments)
        fragment = fragments[fragment_idx]

        return (
            f"{fragment}{topic} presents interesting challenges. "
            f"{topic} involves data and analysis. "
            f"{fragment}the approach requires systematic methods. "
            f"Results depend on proper implementation and testing procedures."
        )

    def _generate_broken_output(self, prompt: str, seed: int) -> str:
        """Generate high brokenness output (lots of repetition, fragments, stops)."""
        topic = prompt.replace("What is ", "").replace("?", "").replace("Explain ", "").strip()

        # Heavy repetition, fragments, and stop-ending words
        return (
            f"Consider {topic}. To clarify, {topic} is important. "
            f"That said, {topic} can be complex. Consider the fact that {topic} needs analysis. "
            f"To clarify further, {topic} has been studied. It should be noted that {topic} requires effort. "
            f"The data shows {topic} works. The test proved {topic} is valid. "
            f"The method for {topic} is direct. That said, {topic} must be checked. "
            f"Consider that {topic} can adapt. To clarify once more, {topic} has merit."
        )


# =============================================================================
# TEST CLASS
# =============================================================================

class TestPhoneticStutterEvaluation:
    """Test suite for phonetic stuttering evaluation."""

    def test_brokenness_metrics(self):
        """Test brokenness score computation."""
        evaluator = PhoneticStutterEvaluator()

        # Clean text
        clean_text = "Machine learning involves training algorithms on data. The models learn patterns and make predictions. This approach has proven effective across many domains."
        clean_result = evaluator.evaluate_single_output(clean_text, "clean")

        # Broken text (lots of repetition)
        broken_text = "Consider machine learning. To clarify, machine learning is important. That said, machine learning can be complex. Consider the fact that machine learning needs data. To clarify further, machine learning has been studied extensively."
        broken_result = evaluator.evaluate_single_output(broken_text, "broken")

        # Broken text should have higher brokenness score
        assert broken_result.brokenness.brokenness_score > clean_result.brokenness.brokenness_score
        assert broken_result.brokenness.fragment_indicator_score > clean_result.brokenness.fragment_indicator_score

        print(f"\nClean brokenness: {clean_result.brokenness.brokenness_score:.3f}")
        print(f"Broken brokenness: {broken_result.brokenness.brokenness_score:.3f}")

    def test_phonetic_features(self):
        """Test phonetic feature extraction."""
        evaluator = PhoneticStutterEvaluator()

        # Text with many stop-endings
        stop_heavy = "The test proved the method worked. The fact is direct. The data is set. The result got checked."
        stop_result = evaluator.evaluate_single_output(stop_heavy, "stops")

        # Text with fewer stop-endings
        flow_text = "Machine learning involves training neural networks using large datasets, enabling systems to recognize patterns and make accurate predictions across various applications."
        flow_result = evaluator.evaluate_single_output(flow_text, "flow")

        # Stop-heavy should have higher stop-ending ratio
        assert stop_result.phonetics.stop_ending_ratio > flow_result.phonetics.stop_ending_ratio

        print(f"\nStop-heavy ratio: {stop_result.phonetics.stop_ending_ratio:.3f}")
        print(f"Flow ratio: {flow_result.phonetics.stop_ending_ratio:.3f}")

    def test_corpus_evaluation(self):
        """Test full corpus evaluation."""
        evaluator = PhoneticStutterEvaluator()
        generator = SyntheticOutputGenerator()

        # Generate test corpus
        prompts = evaluator.generate_prompts(count=50)
        outputs = generator.generate_corpus(prompts)

        # Evaluate corpus
        results, correlations = evaluate_phonetic_stuttering(outputs)

        # Should have results for all outputs
        assert len(results) == 50

        # Should have correlation results
        assert len(correlations) > 0

        print(f"\n=== Corpus Evaluation (n={len(results)}) ===")
        print(f"\nBrokenness Statistics:")
        brokenness_scores = [r.brokenness.brokenness_score for r in results]
        print(f"  Mean: {sum(brokenness_scores) / len(brokenness_scores):.3f}")
        print(f"  Min: {min(brokenness_scores):.3f}")
        print(f"  Max: {max(brokenness_scores):.3f}")

        print(f"\nTop Correlations:")
        for i, corr in enumerate(correlations[:5], 1):
            print(f"  {i}. {corr.feature_name}: r={corr.correlation:.3f} ({corr.effect_size})")

    def test_phonetic_optimizer(self):
        """Test phonetic optimizer/reranker."""
        evaluator = PhoneticStutterEvaluator()

        # Broken text with repeated fragments
        broken_text = "Consider machine learning. Consider deep learning. To clarify, these are related. To clarify, they use neural networks. That said, training requires data. That said, results vary."

        # Optimize
        optimized = evaluator.optimize_output(broken_text)

        # Evaluate both
        broken_result = evaluator.evaluate_single_output(broken_text, "broken")
        optimized_result = evaluator.evaluate_single_output(optimized, "optimized")

        # Optimized should have lower fragment score
        assert optimized_result.brokenness.fragment_indicator_score <= broken_result.brokenness.fragment_indicator_score

        print(f"\n=== Optimization Test ===")
        print(f"Original fragment score: {broken_result.brokenness.fragment_indicator_score:.3f}")
        print(f"Optimized fragment score: {optimized_result.brokenness.fragment_indicator_score:.3f}")
        print(f"\nOriginal text: {broken_text[:100]}...")
        print(f"Optimized text: {optimized[:100]}...")


# =============================================================================
# MAIN EVALUATION SCRIPT
# =============================================================================

def run_full_evaluation(corpus_size: int = 200, output_dir: str = "./phonetic_eval_results"):
    """
    Run complete phonetic stuttering evaluation.

    Args:
        corpus_size: Number of outputs to generate
        output_dir: Directory to save results
    """
    print("=" * 80)
    print("PHONETIC STUTTERING HYPOTHESIS EVALUATION")
    print("=" * 80)

    evaluator = PhoneticStutterEvaluator()
    generator = SyntheticOutputGenerator()

    # Step 1: Generate prompts
    print(f"\n[1/6] Generating {corpus_size} deterministic prompts...")
    prompts = evaluator.generate_prompts(count=corpus_size)
    print(f"  ✓ Generated {len(prompts)} prompts")

    # Step 2: Generate synthetic outputs
    print(f"\n[2/6] Generating synthetic outputs...")
    outputs = generator.generate_corpus(prompts)
    print(f"  ✓ Generated {len(outputs)} outputs")

    # Step 3: Baseline evaluation
    print(f"\n[3/6] Running baseline evaluation...")
    baseline_results, baseline_corrs = evaluate_phonetic_stuttering(outputs, use_optimization=False)
    print(f"  ✓ Evaluated {len(baseline_results)} outputs")

    # Step 4: Compute baseline statistics
    print(f"\n[4/6] Computing baseline statistics...")
    baseline_stats = compute_statistics(baseline_results)
    print(f"  ✓ Mean brokenness: {baseline_stats['mean_brokenness']:.3f}")
    print(f"  ✓ High brokenness (>0.7): {baseline_stats['high_brokenness_pct']:.1f}%")

    # Step 5: Optimized evaluation
    print(f"\n[5/6] Running optimized evaluation...")
    optimized_results, optimized_corrs = evaluate_phonetic_stuttering(outputs, use_optimization=True)
    optimized_stats = compute_statistics(optimized_results)
    print(f"  ✓ Mean brokenness: {optimized_stats['mean_brokenness']:.3f}")
    print(f"  ✓ High brokenness (>0.7): {optimized_stats['high_brokenness_pct']:.1f}%")

    # Step 6: Generate report
    print(f"\n[6/6] Generating report...")
    report = generate_report(
        baseline_results, baseline_corrs, baseline_stats,
        optimized_results, optimized_corrs, optimized_stats
    )

    # Save results
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "PHONETIC_STUTTER_REPORT.md")
    with open(report_path, "w") as f:
        f.write(report)

    json_path = os.path.join(output_dir, "evaluation_data.json")
    with open(json_path, "w") as f:
        json.dump({
            "baseline_stats": baseline_stats,
            "optimized_stats": optimized_stats,
            "baseline_correlations": [
                {"feature": c.feature_name, "correlation": c.correlation, "effect_size": c.effect_size}
                for c in baseline_corrs
            ],
            "optimized_correlations": [
                {"feature": c.feature_name, "correlation": c.correlation, "effect_size": c.effect_size}
                for c in optimized_corrs
            ]
        }, f, indent=2)

    print(f"  ✓ Report saved to: {report_path}")
    print(f"  ✓ Data saved to: {json_path}")

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)

    # Print summary
    print(f"\n=== SUMMARY ===\n")
    print(f"Baseline:")
    print(f"  - Mean brokenness: {baseline_stats['mean_brokenness']:.3f}")
    print(f"  - High brokenness outputs: {baseline_stats['high_brokenness_pct']:.1f}%")
    print(f"\nTop Phonetic Correlations:")
    for i, corr in enumerate(baseline_corrs[:5], 1):
        print(f"  {i}. {corr.feature_name}: r={corr.correlation:+.3f} ({corr.effect_size})")

    print(f"\nOptimized:")
    print(f"  - Mean brokenness: {optimized_stats['mean_brokenness']:.3f}")
    print(f"  - High brokenness outputs: {optimized_stats['high_brokenness_pct']:.1f}%")

    delta_mean = optimized_stats['mean_brokenness'] - baseline_stats['mean_brokenness']
    delta_high = optimized_stats['high_brokenness_pct'] - baseline_stats['high_brokenness_pct']

    print(f"\nDeltas:")
    print(f"  - Mean brokenness change: {delta_mean:+.3f}")
    print(f"  - High brokenness change: {delta_high:+.1f}%")

    # Determine if hypothesis is supported
    print(f"\n=== HYPOTHESIS VERDICT ===\n")

    # Check criteria
    significant_correlation = any(abs(c.correlation) > 0.3 for c in baseline_corrs)
    meaningful_improvement = delta_mean < -0.05 and delta_high < -5.0

    if significant_correlation and meaningful_improvement:
        print("✓ HYPOTHESIS SUPPORTED")
        print("  - Found significant correlations between phonetic features and brokenness")
        print("  - Phonetic optimizer produced meaningful improvements")
    elif significant_correlation:
        print("~ HYPOTHESIS PARTIALLY SUPPORTED")
        print("  - Found significant correlations, but optimizer improvements are negligible")
    else:
        print("✗ HYPOTHESIS NOT SUPPORTED")
        print("  - Correlations are weak (all |r| < 0.3)")
        print("  - No evidence that phonetic features predict brokenness")


def compute_statistics(results: List[EvaluationResult]) -> Dict:
    """Compute statistics from evaluation results."""
    brokenness_scores = [r.brokenness.brokenness_score for r in results]
    trigram_rates = [r.brokenness.repeated_trigram_rate for r in results]
    fragment_scores = [r.brokenness.fragment_indicator_score for r in results]

    high_brokenness_count = sum(1 for score in brokenness_scores if score > 0.7)

    return {
        "mean_brokenness": sum(brokenness_scores) / len(brokenness_scores),
        "min_brokenness": min(brokenness_scores),
        "max_brokenness": max(brokenness_scores),
        "high_brokenness_pct": 100 * high_brokenness_count / len(brokenness_scores),
        "mean_trigram_rate": sum(trigram_rates) / len(trigram_rates),
        "mean_fragment_score": sum(fragment_scores) / len(fragment_scores),
        "sample_size": len(results)
    }


def generate_report(
    baseline_results, baseline_corrs, baseline_stats,
    optimized_results, optimized_corrs, optimized_stats
) -> str:
    """Generate markdown report."""
    report = f"""# Phonetic Stuttering Evaluation Report

**Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Corpus Size:** {baseline_stats['sample_size']}
**Hypothesis:** "Phonetic stuttering" is a measurable failure mode correlated with specific phonetic features.

---

## Executive Summary

This evaluation tests whether phonetic features (sibilants, stops, nasals, fricatives, stop-ending ratios)
correlate with text "brokenness" (repetition, fragments, poor flow) in the Symbol-U renderer output.

**Verdict:** """

    # Determine verdict
    significant_correlation = any(abs(c.correlation) > 0.3 for c in baseline_corrs)
    delta_mean = optimized_stats['mean_brokenness'] - baseline_stats['mean_brokenness']
    delta_high = optimized_stats['high_brokenness_pct'] - baseline_stats['high_brokenness_pct']
    meaningful_improvement = delta_mean < -0.05 and delta_high < -5.0

    if significant_correlation and meaningful_improvement:
        verdict = "**HYPOTHESIS SUPPORTED** ✓"
        explanation = "Significant correlations found AND phonetic optimizer produced meaningful improvements."
    elif significant_correlation:
        verdict = "**HYPOTHESIS PARTIALLY SUPPORTED** ~"
        explanation = "Correlations found, but optimizer improvements are negligible."
    else:
        verdict = "**HYPOTHESIS NOT SUPPORTED** ✗"
        explanation = "Correlations are weak. No evidence that phonetic features predict brokenness."

    report += f"{verdict}\n\n{explanation}\n\n"

    report += f"""---

## Methodology

### 1. Brokenness Metrics

**Brokenness Score** is computed from three components:

- **Repeated 3-gram rate** (40% weight): Ratio of unique 3-grams that appear multiple times
- **Fragment indicator score** (35% weight): Frequency of sentence-starting hedges ("Consider", "To clarify", etc.)
- **Stopword + punctuation ratio** (25% weight): Stopword density and abrupt short sentences

**Score range:** [0, 1], where 0 = clean, 1 = maximally broken

### 2. Phonetic Features

Phoneme-proxy features extracted using pattern matching:

- **Sibilants**: s, z, sh sounds (patterns: `\\bs[aeiou]`, `sh`, etc.)
- **Stops**: p, t, k, b, d, g sounds
- **Nasals**: m, n sounds
- **Fricatives**: f, v sounds
- **Stop-ending ratio**: Proportion of words ending in stop consonants

### 3. Corpus

- **{baseline_stats['sample_size']} synthetic outputs** generated deterministically
- Outputs vary in brokenness level (low/medium/high)
- Prompts cover diverse topics (ML, physics, philosophy, etc.)

### 4. Optimization

Phonetic reranker applies two strategies:

1. **Fragment diversification**: Replace repeated sentence starters with synonyms
2. **Stop-ending reduction**: (minimal, to avoid semantic changes)

---

## Results

### Baseline Evaluation

**Brokenness Statistics:**

| Metric | Value |
|--------|-------|
| Mean brokenness | {baseline_stats['mean_brokenness']:.3f} |
| Min brokenness | {baseline_stats['min_brokenness']:.3f} |
| Max brokenness | {baseline_stats['max_brokenness']:.3f} |
| Outputs with high brokenness (>0.7) | {baseline_stats['high_brokenness_pct']:.1f}% |
| Mean 3-gram repetition rate | {baseline_stats['mean_trigram_rate']:.3f} |
| Mean fragment score | {baseline_stats['mean_fragment_score']:.3f} |

**Top 5 Phonetic Predictors:**

| Rank | Feature | Correlation (r) | Effect Size |
|------|---------|-----------------|-------------|
"""

    for i, corr in enumerate(baseline_corrs[:5], 1):
        report += f"| {i} | {corr.feature_name} | {corr.correlation:+.3f} | {corr.effect_size} |\n"

    report += f"""
**Analysis:**

"""

    # Analyze top predictors
    top_corr = baseline_corrs[0] if baseline_corrs else None
    if top_corr and abs(top_corr.correlation) > 0.3:
        report += f"- **{top_corr.feature_name}** shows {top_corr.effect_size} correlation (r={top_corr.correlation:+.3f})\n"
    else:
        report += "- All correlations are weak (|r| < 0.3)\n"

    # Check for d-ending and stop-ending
    d_corr = next((c for c in baseline_corrs if "stop_ending" in c.feature_name), None)
    if d_corr:
        report += f"- **Stop-ending ratio** correlation: r={d_corr.correlation:+.3f} ({d_corr.effect_size})\n"

    report += f"""
### Optimized Evaluation

**Brokenness Statistics (After Optimization):**

| Metric | Value | Delta |
|--------|-------|-------|
| Mean brokenness | {optimized_stats['mean_brokenness']:.3f} | {delta_mean:+.3f} |
| Outputs with high brokenness (>0.7) | {optimized_stats['high_brokenness_pct']:.1f}% | {delta_high:+.1f}% |
| Mean 3-gram repetition rate | {optimized_stats['mean_trigram_rate']:.3f} | {optimized_stats['mean_trigram_rate'] - baseline_stats['mean_trigram_rate']:+.3f} |
| Mean fragment score | {optimized_stats['mean_fragment_score']:.3f} | {optimized_stats['mean_fragment_score'] - baseline_stats['mean_fragment_score']:+.3f} |

**Analysis:**

"""

    if abs(delta_mean) > 0.05:
        direction = "decreased" if delta_mean < 0 else "increased"
        report += f"- Mean brokenness {direction} by {abs(delta_mean):.3f} ({abs(delta_mean/baseline_stats['mean_brokenness']*100):.1f}% change)\n"
    else:
        report += "- Mean brokenness change is negligible (<0.05)\n"

    if abs(delta_high) > 5.0:
        direction = "decreased" if delta_high < 0 else "increased"
        report += f"- High-brokenness outputs {direction} by {abs(delta_high):.1f} percentage points\n"
    else:
        report += "- High-brokenness output rate changed minimally (<5%)\n"

    report += f"""
---

## Conclusions

### Evidence Assessment

"""

    # Detailed conclusions
    if significant_correlation:
        report += f"""
**Correlations Found:**

The analysis identified phonetic features with non-negligible correlations to brokenness:

"""
        for corr in baseline_corrs:
            if abs(corr.correlation) > 0.2:
                report += f"- {corr.feature_name}: r={corr.correlation:+.3f} ({corr.effect_size} effect)\n"

        report += """
This suggests some relationship between phonetic patterns and text quality metrics.
"""
    else:
        report += """
**No Significant Correlations:**

All phonetic features showed weak correlations (|r| < 0.3) with brokenness scores.
This indicates that phonetic patterns (as measured here) do NOT strongly predict text brokenness.
"""

    if meaningful_improvement:
        report += f"""
**Optimization Impact:**

The phonetic reranker produced measurable improvements:
- Reduced mean brokenness by {abs(delta_mean):.3f}
- Reduced high-brokenness outputs by {abs(delta_high):.1f}%

This demonstrates that minimizing phonetic conflicts can improve output quality.
"""
    else:
        report += """
**Optimization Impact:**

The phonetic reranker produced negligible improvements (<5% change).
This suggests that phonetic optimization is NOT an effective intervention.
"""

    report += f"""
### Final Verdict

{verdict}

"""

    if not significant_correlation:
        report += """
**Recommendation:** Do not implement phonetic stuttering mitigation in production.
The hypothesis is not supported by the data. Focus on other quality metrics.
"""
    elif not meaningful_improvement:
        report += """
**Recommendation:** Phonetic features show some correlation, but the optimizer is ineffective.
Further research needed before production implementation.
"""
    else:
        report += """
**Recommendation:** Consider implementing phonetic optimization in production.
The evidence supports the hypothesis and demonstrates measurable improvements.
"""

    report += """
---

## Limitations

1. **Synthetic Data**: Evaluation used synthetic outputs, not real renderer outputs
2. **Phoneme Approximation**: Letter patterns are rough proxies for actual phonemes
3. **Correlation ≠ Causation**: Observed correlations may be spurious
4. **Limited Optimization**: Reranker only addresses fragments, not stop-endings

## Future Work

- Test on real Symbol-U renderer outputs
- Use actual phonetic transcription (IPA) instead of letter patterns
- Implement more sophisticated optimization (synonym substitution, rephrasing)
- Test on human-rated quality scores

---

*This report was generated automatically by the Phonetic Stutter Evaluation Module.*
"""

    return report


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run full evaluation
    run_full_evaluation(corpus_size=200)
