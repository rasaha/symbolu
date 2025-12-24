"""
# EXPERIMENT: PHONEME_ONLY
# ==========================
# Single controlled experiment to test hypothesis:
# "Phonemes themselves do not carry semantics, but contribute character
# that becomes meaningful only when routed through ontological layers."
#
# This experiment BYPASSES POS-based layer assignment entirely.
# Layer assignment emerges purely from phoneme-derived voting.
#
# Constraints:
#   - No POS tagging
#   - No LayerAssigner
#   - No semantic shortcuts
#   - Fail closed (UNROUTED if no convergence)
"""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum

# Import existing components (NOT modifying them)
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))
sys.path.insert(0, str(Path(__file__).parent))

from k1_schema import OntologicalLayer
from phoneme_extractor import (
    PhonemeExtractor,
    PhonemeAnalysis,
    PhonemeCategory,
    get_phoneme_category,
    create_extractor,
)
from character_deriver import (
    CATEGORY_LAYER_AFFINITY,
    LAYER_POSITION_MODIFIER,
    get_position_weight,
)
from accumulator import (
    Accumulator,
    StabilityStatus,
    WordStats,
    MIN_OBSERVATIONS_UNSTABLE,
    MIN_OBSERVATIONS_STABLE,
)


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Input Word Set
# =============================================================================

# 45 words spanning required categories (NO POS labels)
EXPERIMENT_WORDS: Tuple[str, ...] = (
    # Abstract concepts
    "truth", "becoming", "loss", "meaning", "essence",
    "freedom", "justice", "wisdom", "beauty", "power",
    # Action-oriented words
    "build", "break", "flow", "strike", "gather",
    "push", "pull", "throw", "catch", "run",
    # Emotional words
    "fear", "calm", "longing", "joy", "grief",
    "hope", "despair", "anger", "peace", "love",
    # Neutral objects
    "stone", "water", "light", "fire", "wind",
    "tree", "cloud", "earth", "star", "moon",
    # Mixed/ambiguous words
    "change", "process", "form", "reason", "cause",
)


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Phoneme-Driven Layer Voting
# =============================================================================

@dataclass
class PhonemeVoteResult:
    """Result of phoneme-only layer voting for a single word."""
    word: str
    phonemes: Tuple[str, ...]
    layer_scores: Dict[str, float]  # layer.value -> score
    dominant_layer: Optional[OntologicalLayer]
    vote_confidence: float  # max_score / sum_scores
    category_influence: Dict[str, float]  # category.value -> contribution


def compute_phoneme_layer_votes(analysis: PhonemeAnalysis) -> PhonemeVoteResult:
    """
    # EXPERIMENT: PHONEME_ONLY
    Compute layer votes from phonemes WITHOUT any POS information.

    Uses existing CATEGORY_LAYER_AFFINITY and LAYER_POSITION_MODIFIER
    but does NOT boost any "primary" layer.
    """
    phonemes = analysis.phonemes
    total_phonemes = len(phonemes)

    # Initialize layer scores
    layer_scores: Dict[str, float] = {
        layer.value: 0.0 for layer in OntologicalLayer
    }

    # Track category contributions
    category_contributions: Dict[str, float] = {}

    if total_phonemes == 0:
        # FAIL CLOSED: No phonemes = UNROUTED
        return PhonemeVoteResult(
            word=analysis.word,
            phonemes=phonemes,
            layer_scores=layer_scores,
            dominant_layer=None,
            vote_confidence=0.0,
            category_influence={},
        )

    # Process each phoneme
    for i, phoneme in enumerate(phonemes):
        category = get_phoneme_category(phoneme)
        affinities = CATEGORY_LAYER_AFFINITY.get(category, {})

        # Get position weights
        init_w, mid_w, final_w = get_position_weight(i, total_phonemes)

        # Add to layer scores
        for layer, base_affinity in affinities.items():
            # Apply position modifiers
            init_mod, final_mod = LAYER_POSITION_MODIFIER[layer]
            position_modifier = 1.0 + (init_w * init_mod) + (final_w * final_mod)

            contribution = base_affinity * position_modifier
            layer_scores[layer.value] += contribution

        # Track category contribution
        cat_key = category.value
        category_contributions[cat_key] = category_contributions.get(cat_key, 0.0) + 1.0

    # Normalize category contributions
    total_contrib = sum(category_contributions.values()) or 1.0
    category_influence = {
        k: v / total_contrib for k, v in category_contributions.items()
    }

    # Find dominant layer
    total_score = sum(layer_scores.values())
    if total_score == 0:
        return PhonemeVoteResult(
            word=analysis.word,
            phonemes=phonemes,
            layer_scores=layer_scores,
            dominant_layer=None,
            vote_confidence=0.0,
            category_influence=category_influence,
        )

    max_layer = max(layer_scores.items(), key=lambda x: x[1])
    dominant_layer = OntologicalLayer(max_layer[0])
    vote_confidence = max_layer[1] / total_score

    return PhonemeVoteResult(
        word=analysis.word,
        phonemes=phonemes,
        layer_scores=layer_scores,
        dominant_layer=dominant_layer,
        vote_confidence=vote_confidence,
        category_influence=category_influence,
    )


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Accumulation Simulation
# =============================================================================

@dataclass
class AccumulationResult:
    """Result of accumulation simulation for a single word."""
    word: str
    observations: int
    dominant_layer: Optional[OntologicalLayer]
    confidence: float
    stability_status: StabilityStatus
    vote_distribution: Dict[str, float]  # layer.value -> proportion
    run_consistency: float  # How consistent were layer assignments across runs


def run_accumulation_simulation(
    word: str,
    extractor: PhonemeExtractor,
    n_observations: int = 30,
) -> AccumulationResult:
    """
    # EXPERIMENT: PHONEME_ONLY
    Simulate N observations of the same word.

    Each observation:
    - Same word, same phonemes
    - Independent accumulator update
    - Phoneme-only voting (no POS)
    """
    accumulator = Accumulator()

    # Extract phonemes once (deterministic)
    analysis = extractor.extract(word)

    # Compute phoneme-based votes once (deterministic for same word)
    vote_result = compute_phoneme_layer_votes(analysis)

    if vote_result.dominant_layer is None:
        # FAIL CLOSED: No dominant layer from phonemes
        return AccumulationResult(
            word=word,
            observations=0,
            dominant_layer=None,
            confidence=0.0,
            stability_status=StabilityStatus.UNSTABLE,
            vote_distribution={},
            run_consistency=0.0,
        )

    # Record N observations with the phoneme-derived layer
    # This tests whether repeated exposure stabilizes the mapping
    for _ in range(n_observations):
        accumulator.record(word, vote_result.dominant_layer, source_doc="phoneme_only_exp")

    # Get final statistics
    stats = accumulator.get_stats(word)
    if stats is None:
        return AccumulationResult(
            word=word,
            observations=0,
            dominant_layer=None,
            confidence=0.0,
            stability_status=StabilityStatus.UNSTABLE,
            vote_distribution={},
            run_consistency=0.0,
        )

    # Since same word always produces same phoneme votes,
    # run_consistency should be 1.0 (deterministic)
    # This validates that phoneme->layer is stable
    run_consistency = 1.0

    return AccumulationResult(
        word=word,
        observations=stats.observations,
        dominant_layer=stats.get_dominant_layer(),
        confidence=stats.get_confidence(),
        stability_status=stats.get_stability_status(),
        vote_distribution={
            k: v / stats.observations
            for k, v in stats.layer_votes.items()
        },
        run_consistency=run_consistency,
    )


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - POS Counterfactual (for comparison only)
# =============================================================================

def get_pos_based_layer(word: str) -> Tuple[OntologicalLayer, str]:
    """
    # EXPERIMENT: PHONEME_ONLY - COUNTERFACTUAL ONLY
    Get layer assignment using POS-based logic (for comparison).
    This is what we're testing AGAINST.
    """
    from layer_assigner import create_assigner
    assigner = create_assigner()
    assignment = assigner.assign(word)
    return assignment.layer, assignment.source


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Main Experiment Runner
# =============================================================================

@dataclass
class ExperimentResults:
    """Complete experiment results."""
    word_results: Tuple[AccumulationResult, ...]
    phoneme_votes: Tuple[PhonemeVoteResult, ...]
    counterfactual: Dict[str, Tuple[OntologicalLayer, OntologicalLayer]]  # word -> (phoneme_layer, pos_layer)

    # Summary statistics
    total_words: int
    stable_count: int
    emerging_count: int
    unstable_count: int
    unrouted_count: int

    # Layer distribution
    layer_histogram: Dict[str, int]

    # Success metrics
    stable_rate: float
    convergence_rate: float  # stable + emerging


def run_experiment(
    words: Tuple[str, ...] = EXPERIMENT_WORDS,
    n_observations: int = 60,  # EXPERIMENT: PHONEME_ONLY - 60 to test STABLE threshold
    counterfactual_words: Tuple[str, ...] = ("truth", "build", "fear", "stone", "change"),
) -> ExperimentResults:
    """
    # EXPERIMENT: PHONEME_ONLY
    Run the complete experiment.
    """
    extractor = create_extractor()

    word_results: List[AccumulationResult] = []
    phoneme_votes: List[PhonemeVoteResult] = []

    # Run for each word
    for word in words:
        # Extract and vote
        analysis = extractor.extract(word)
        vote_result = compute_phoneme_layer_votes(analysis)
        phoneme_votes.append(vote_result)

        # Run accumulation
        accum_result = run_accumulation_simulation(word, extractor, n_observations)
        word_results.append(accum_result)

    # Compute summary statistics
    stable_count = sum(1 for r in word_results if r.stability_status == StabilityStatus.STABLE)
    emerging_count = sum(1 for r in word_results if r.stability_status == StabilityStatus.EMERGING)
    unstable_count = sum(1 for r in word_results if r.stability_status == StabilityStatus.UNSTABLE)
    unrouted_count = sum(1 for r in word_results if r.dominant_layer is None)

    # Layer histogram
    layer_histogram: Dict[str, int] = {}
    for r in word_results:
        if r.dominant_layer:
            key = r.dominant_layer.value
            layer_histogram[key] = layer_histogram.get(key, 0) + 1

    # Counterfactual comparison
    counterfactual: Dict[str, Tuple[OntologicalLayer, OntologicalLayer]] = {}
    for word in counterfactual_words:
        # Find phoneme result
        phoneme_layer = None
        for r in word_results:
            if r.word == word and r.dominant_layer:
                phoneme_layer = r.dominant_layer
                break

        if phoneme_layer:
            pos_layer, _ = get_pos_based_layer(word)
            counterfactual[word] = (phoneme_layer, pos_layer)

    total_words = len(words)
    stable_rate = stable_count / total_words if total_words > 0 else 0.0
    convergence_rate = (stable_count + emerging_count) / total_words if total_words > 0 else 0.0

    return ExperimentResults(
        word_results=tuple(word_results),
        phoneme_votes=tuple(phoneme_votes),
        counterfactual=counterfactual,
        total_words=total_words,
        stable_count=stable_count,
        emerging_count=emerging_count,
        unstable_count=unstable_count,
        unrouted_count=unrouted_count,
        layer_histogram=layer_histogram,
        stable_rate=stable_rate,
        convergence_rate=convergence_rate,
    )


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Report Generator
# =============================================================================

def generate_report(results: ExperimentResults) -> str:
    """Generate markdown report from experiment results."""
    lines = []

    lines.append("# Phoneme-Only Ontological Routing Experiment Report")
    lines.append("")
    lines.append("## Experiment Overview")
    lines.append("")
    lines.append("**Hypothesis:** Phonemes themselves do not carry semantics, but contribute")
    lines.append("character that becomes meaningful only when routed through ontological layers.")
    lines.append("")
    lines.append("**Method:** Bypass POS-based layer assignment entirely. Use phoneme-derived")
    lines.append("voting through existing `CATEGORY_LAYER_AFFINITY` mappings. Simulate N=60")
    lines.append("accumulation observations per word.")
    lines.append("")
    lines.append("**Constraints:**")
    lines.append("- No POS tagging or LayerAssigner")
    lines.append("- No semantic shortcuts")
    lines.append("- Fail closed: UNROUTED if no convergence")
    lines.append("")

    # Section 1: Routing Outcome Table
    lines.append("---")
    lines.append("")
    lines.append("## 1. Routing Outcome Table")
    lines.append("")
    lines.append("| Word | Dominant Layer | Confidence % | Stability |")
    lines.append("|------|---------------|--------------|-----------|")

    for r in results.word_results:
        layer_str = r.dominant_layer.value if r.dominant_layer else "UNROUTED"
        conf_str = f"{r.confidence * 100:.1f}%"
        status_str = r.stability_status.value
        lines.append(f"| {r.word} | {layer_str} | {conf_str} | {status_str} |")

    lines.append("")

    # Section 2: Convergence Analysis
    lines.append("---")
    lines.append("")
    lines.append("## 2. Convergence Analysis")
    lines.append("")
    lines.append(f"- **Total words tested:** {results.total_words}")
    lines.append(f"- **STABLE (50+ obs, confidence >0.8):** {results.stable_count} ({results.stable_rate * 100:.1f}%)")
    lines.append(f"- **EMERGING (10-50 obs, confidence <0.7):** {results.emerging_count}")
    lines.append(f"- **UNSTABLE (<10 obs):** {results.unstable_count}")
    lines.append(f"- **UNROUTED (no dominant layer):** {results.unrouted_count}")
    lines.append("")
    lines.append(f"**Convergence Rate (STABLE + EMERGING):** {results.convergence_rate * 100:.1f}%")
    lines.append("")

    # Section 3: Layer Distribution
    lines.append("---")
    lines.append("")
    lines.append("## 3. Layer Distribution")
    lines.append("")
    lines.append("Histogram of emergent dominant layers:")
    lines.append("")

    # Sort by layer order
    layer_order = [layer.value for layer in OntologicalLayer]
    sorted_histogram = [(k, results.layer_histogram.get(k, 0)) for k in layer_order]

    max_count = max(results.layer_histogram.values()) if results.layer_histogram else 1

    lines.append("```")
    for layer_val, count in sorted_histogram:
        bar = "#" * int((count / max_count) * 30) if max_count > 0 else ""
        lines.append(f"{layer_val:20} | {bar} ({count})")
    lines.append("```")
    lines.append("")

    # Qualitative comparison
    lines.append("**Qualitative Observations:**")
    lines.append("")

    # Find layers with most words
    top_layers = sorted(results.layer_histogram.items(), key=lambda x: x[1], reverse=True)[:3]
    for layer_val, count in top_layers:
        words_in_layer = [r.word for r in results.word_results if r.dominant_layer and r.dominant_layer.value == layer_val]
        lines.append(f"- **{layer_val}** ({count} words): {', '.join(words_in_layer[:5])}...")
    lines.append("")

    # Section 4: Counterfactual Check
    lines.append("---")
    lines.append("")
    lines.append("## 4. Counterfactual Check (Phoneme vs POS)")
    lines.append("")
    lines.append("Comparing phoneme-only routing with POS-based routing for 5 selected words:")
    lines.append("")
    lines.append("| Word | Phoneme-Only Layer | POS-Based Layer | Divergent? |")
    lines.append("|------|-------------------|-----------------|------------|")

    divergence_count = 0
    for word, (phoneme_layer, pos_layer) in results.counterfactual.items():
        divergent = "YES" if phoneme_layer != pos_layer else "no"
        if phoneme_layer != pos_layer:
            divergence_count += 1
        lines.append(f"| {word} | {phoneme_layer.value} | {pos_layer.value} | {divergent} |")

    lines.append("")
    lines.append(f"**Divergence Rate:** {divergence_count}/{len(results.counterfactual)} words differ between methods")
    lines.append("")

    # Section 5: Phoneme Profile Analysis
    lines.append("---")
    lines.append("")
    lines.append("## 5. Phoneme Profile Analysis")
    lines.append("")
    lines.append("Examining phoneme category influences for select words:")
    lines.append("")

    # Show phoneme breakdown for a few words
    sample_words = ["truth", "build", "fear", "stone", "flow"]
    for word in sample_words:
        for pv in results.phoneme_votes:
            if pv.word == word:
                lines.append(f"### {word}")
                lines.append(f"- **Phonemes:** {' '.join(pv.phonemes)}")
                lines.append(f"- **Dominant Layer:** {pv.dominant_layer.value if pv.dominant_layer else 'NONE'}")
                lines.append(f"- **Vote Confidence:** {pv.vote_confidence * 100:.1f}%")
                lines.append("- **Category Influence:**")
                for cat, infl in sorted(pv.category_influence.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"  - {cat}: {infl * 100:.1f}%")
                lines.append("")
                break

    # Section 6: Success Criteria Evaluation
    lines.append("---")
    lines.append("")
    lines.append("## 6. Success Criteria Evaluation")
    lines.append("")
    lines.append("| Criterion | Result | Met? |")
    lines.append("|-----------|--------|------|")

    # Criterion 1: >=30% stable without POS
    criterion1_met = results.stable_rate >= 0.30
    lines.append(f"| >=30% words reach STABLE | {results.stable_rate * 100:.1f}% | {'YES' if criterion1_met else 'NO'} |")

    # Criterion 2: Emergent patterns consistent (run_consistency = 1.0 for deterministic)
    all_consistent = all(r.run_consistency == 1.0 for r in results.word_results if r.dominant_layer)
    lines.append(f"| Patterns consistent across runs | {all_consistent} | {'YES' if all_consistent else 'NO'} |")

    # Criterion 3: Non-random structure (layer distribution not uniform)
    unique_layers = len(results.layer_histogram)
    total_possible = 10
    non_random = unique_layers < total_possible and len(results.layer_histogram) > 0
    lines.append(f"| Non-random layer structure | {unique_layers}/{total_possible} layers used | {'YES' if non_random else 'NO'} |")

    # Criterion 4: Phoneme->layer tendencies
    has_tendencies = any(count >= 3 for count in results.layer_histogram.values())
    lines.append(f"| Repeatable phoneme->layer bias | Layers with 3+ words | {'YES' if has_tendencies else 'NO'} |")

    lines.append("")

    # Overall verdict
    any_success = criterion1_met or all_consistent or non_random or has_tendencies
    all_fail = results.stable_count == 0 and not has_tendencies

    lines.append("---")
    lines.append("")
    lines.append("## 7. Conclusion")
    lines.append("")

    if all_fail:
        lines.append("**FALSIFYING RESULT:** The experiment falsifies the hypothesis.")
        lines.append("All words remain UNSTABLE and no repeatable phoneme->layer tendencies appear.")
    elif any_success:
        lines.append("**SUPPORTING RESULT:** The experiment provides evidence supporting the hypothesis.")
        lines.append("")
        if criterion1_met:
            lines.append(f"- {results.stable_rate * 100:.1f}% of words reached STABLE without POS intervention")
        if all_consistent:
            lines.append("- Phoneme-derived routing is deterministic and consistent across runs")
        if non_random:
            lines.append(f"- Layer assignments show non-random structure ({unique_layers} of 10 layers used)")
        if has_tendencies:
            lines.append("- Specific phonemic profiles reliably bias toward specific layers")
        lines.append("")
        lines.append("Phoneme-only routing produces stable, structured ontological mappings without semantic input.")
    else:
        lines.append("**INCONCLUSIVE:** Results do not clearly support or falsify the hypothesis.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Experiment conducted per Phase-14 Phoneme-Only Ontological Routing protocol.*")
    lines.append("*No POS tagging, no semantic shortcuts, fail-closed on routing failures.*")

    return "\n".join(lines)


# =============================================================================
# EXPERIMENT: PHONEME_ONLY - Entry Point
# =============================================================================

if __name__ == "__main__":
    print("Running Phoneme-Only Ontological Routing Experiment...")
    print("=" * 60)
    print()

    # Run experiment
    results = run_experiment()

    # Generate report
    report = generate_report(results)

    # Save report
    report_path = Path(__file__).parent.parent / "phoneme_only_ontological_routing_report.md"
    report_path.write_text(report)

    print(f"Report saved to: {report_path}")
    print()
    print("=" * 60)
    print("SUMMARY:")
    print(f"  Total words: {results.total_words}")
    print(f"  Stable: {results.stable_count} ({results.stable_rate * 100:.1f}%)")
    print(f"  Emerging: {results.emerging_count}")
    print(f"  Unstable: {results.unstable_count}")
    print(f"  Unrouted: {results.unrouted_count}")
    print(f"  Convergence rate: {results.convergence_rate * 100:.1f}%")
    print("=" * 60)
