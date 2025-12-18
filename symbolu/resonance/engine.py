"""
Phonetic Resonance Engine - Core Algorithms
============================================

Computes ontological vectors from phonemes and measures resonance
between words and phrases.

Key concepts:
- WordVector: 10D ontological projection of a word
- Resonance: Cosine similarity between word vectors
- Phrase Harmony: Aggregate resonance across word pairs
"""

import math
from typing import Tuple, List, Optional

from symbolu.resonance.types import (
    WordVector,
    ResonanceResult,
    PhraseAnalysis,
    LAYER_NAMES,
)
from symbolu.resonance.phoneme_map import (
    get_layer_affinities,
    get_phoneme_profile,
    PHONEME_PROFILES,
)


# =============================================================================
# Constants
# =============================================================================

# Thresholds for harmony/dissonance classification
HARMONY_THRESHOLD = 0.7
DISSONANCE_THRESHOLD = 0.3

# Position weights: early phonemes have more impact (front-loading)
# First phoneme: 1.5x, second: 1.25x, third+: 1.0x
POSITION_WEIGHTS = (1.5, 1.25, 1.0)


# =============================================================================
# Word → Vector Conversion
# =============================================================================

def word_to_vector(word: str, phonemes: Tuple[str, ...]) -> WordVector:
    """
    Convert a word (with its phonemes) to a 10D ontological vector.

    Algorithm:
    1. For each phoneme, get its 10D layer affinities
    2. Apply position weights (front phonemes matter more)
    3. Sum weighted affinities
    4. Normalize to unit vector

    Args:
        word: The original word string
        phonemes: ARPABET phoneme sequence (e.g., ("S", "K", "AY"))

    Returns:
        WordVector with normalized 10D projection
    """
    if not phonemes:
        # Return zero vector for empty input
        zero_vec = tuple(0.0 for _ in range(10))
        return WordVector(
            word=word,
            phonemes=phonemes,
            vector=zero_vec,
            trajectory=(),
            dominant_layer=LAYER_NAMES[0],
            dominant_score=0.0,
        )

    # Accumulate weighted affinities
    accumulated = [0.0] * 10
    trajectory = []

    for i, phoneme in enumerate(phonemes):
        try:
            affinities = get_layer_affinities(phoneme)
        except KeyError:
            # Unknown phoneme - skip it
            trajectory.append(0.0)
            continue

        # Position weight: first phoneme gets 1.5x, second 1.25x, rest 1.0x
        if i < len(POSITION_WEIGHTS):
            weight = POSITION_WEIGHTS[i]
        else:
            weight = POSITION_WEIGHTS[-1]

        # Add weighted affinities
        for j in range(10):
            accumulated[j] += affinities[j] * weight

        # Track trajectory (magnitude at this position)
        magnitude = math.sqrt(sum(a * a for a in affinities))
        trajectory.append(magnitude * weight)

    # Normalize to unit vector
    total_magnitude = math.sqrt(sum(v * v for v in accumulated))
    if total_magnitude > 0:
        normalized = tuple(v / total_magnitude for v in accumulated)
    else:
        normalized = tuple(0.0 for _ in range(10))

    # Find dominant layer
    max_idx = 0
    max_val = normalized[0]
    for i in range(1, 10):
        if normalized[i] > max_val:
            max_val = normalized[i]
            max_idx = i

    return WordVector(
        word=word,
        phonemes=phonemes,
        vector=normalized,
        trajectory=tuple(trajectory),
        dominant_layer=LAYER_NAMES[max_idx],
        dominant_score=max_val,
    )


# =============================================================================
# Resonance Computation
# =============================================================================

def compute_resonance(vec_a: WordVector, vec_b: WordVector) -> ResonanceResult:
    """
    Compute phonetic resonance between two word vectors.

    Uses cosine similarity as the primary measure, plus analysis of
    shared and conflicting dimensions.

    Args:
        vec_a: First word's ontological vector
        vec_b: Second word's ontological vector

    Returns:
        ResonanceResult with similarity score and analysis
    """
    # Cosine similarity
    similarity = _cosine_similarity(vec_a.vector, vec_b.vector)

    # Classify harmony/dissonance
    harmonic = similarity >= HARMONY_THRESHOLD
    dissonant = similarity <= DISSONANCE_THRESHOLD

    # Find shared dimensions (both have high affinity)
    shared = []
    conflicting = []
    high_threshold = 0.3  # Dimension is "active" if above this

    for i in range(10):
        a_val = vec_a.vector[i]
        b_val = vec_b.vector[i]

        if a_val >= high_threshold and b_val >= high_threshold:
            shared.append(LAYER_NAMES[i])
        elif (a_val >= high_threshold and b_val < 0.15) or \
             (b_val >= high_threshold and a_val < 0.15):
            conflicting.append(LAYER_NAMES[i])

    # Trajectory alignment (how well the prosodic shapes match)
    trajectory_alignment = _trajectory_correlation(
        vec_a.trajectory, vec_b.trajectory
    )

    return ResonanceResult(
        word_a=vec_a.word,
        word_b=vec_b.word,
        similarity=similarity,
        harmonic=harmonic,
        dissonant=dissonant,
        shared_dimensions=tuple(shared),
        conflicting_dimensions=tuple(conflicting),
        trajectory_alignment=trajectory_alignment,
    )


def _cosine_similarity(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have same dimension")

    dot_product = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def _trajectory_correlation(
    traj_a: Tuple[float, ...],
    traj_b: Tuple[float, ...]
) -> float:
    """
    Compute correlation between prosodic trajectories.

    Returns value from -1 (opposite shapes) to +1 (same shape).
    """
    if not traj_a or not traj_b:
        return 0.0

    # Pad shorter trajectory with zeros
    max_len = max(len(traj_a), len(traj_b))
    a = list(traj_a) + [0.0] * (max_len - len(traj_a))
    b = list(traj_b) + [0.0] * (max_len - len(traj_b))

    # Mean-center
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    centered_a = [x - mean_a for x in a]
    centered_b = [x - mean_b for x in b]

    # Correlation
    numerator = sum(x * y for x, y in zip(centered_a, centered_b))
    denom_a = math.sqrt(sum(x * x for x in centered_a))
    denom_b = math.sqrt(sum(y * y for y in centered_b))

    if denom_a == 0 or denom_b == 0:
        return 0.0

    return numerator / (denom_a * denom_b)


# =============================================================================
# Phrase Analysis
# =============================================================================

def analyze_phrase_vectors(
    word_vectors: Tuple[WordVector, ...]
) -> PhraseAnalysis:
    """
    Analyze phonetic harmony across a set of word vectors.

    Computes pairwise resonance and aggregate metrics.

    Args:
        word_vectors: Sequence of WordVectors for content words

    Returns:
        PhraseAnalysis with harmony/dissonance prediction
    """
    if not word_vectors:
        return PhraseAnalysis(
            phrase="",
            words=(),
            pairwise_resonance=(),
            overall_harmony=0.0,
            overall_dissonance=0.0,
            prediction="NEUTRAL",
            key_resonances=(),
        )

    # Reconstruct phrase
    phrase = " ".join(wv.word for wv in word_vectors)

    # Compute all pairwise resonances
    pairwise: List[ResonanceResult] = []
    for i in range(len(word_vectors)):
        for j in range(i + 1, len(word_vectors)):
            res = compute_resonance(word_vectors[i], word_vectors[j])
            pairwise.append(res)

    if not pairwise:
        # Single word - no pairs to compare
        return PhraseAnalysis(
            phrase=phrase,
            words=word_vectors,
            pairwise_resonance=(),
            overall_harmony=1.0,  # Single word is self-harmonic
            overall_dissonance=0.0,
            prediction="HARMONIC",
            key_resonances=(),
        )

    # Aggregate metrics
    similarities = [r.similarity for r in pairwise]
    overall_harmony = sum(similarities) / len(similarities)

    # Dissonance = variance in vectors (conflict)
    mean_vec = [0.0] * 10
    for wv in word_vectors:
        for i in range(10):
            mean_vec[i] += wv.vector[i]
    mean_vec = [v / len(word_vectors) for v in mean_vec]

    # Compute variance from mean
    variance = 0.0
    for wv in word_vectors:
        for i in range(10):
            diff = wv.vector[i] - mean_vec[i]
            variance += diff * diff
    overall_dissonance = variance / (len(word_vectors) * 10)

    # Prediction
    if overall_harmony >= HARMONY_THRESHOLD:
        prediction = "HARMONIC"
    elif overall_harmony <= DISSONANCE_THRESHOLD:
        prediction = "DISSONANT"
    else:
        prediction = "NEUTRAL"

    # Key resonances: most extreme (high or low)
    sorted_pairs = sorted(pairwise, key=lambda r: abs(r.similarity - 0.5), reverse=True)
    key_resonances = tuple(sorted_pairs[:3])

    return PhraseAnalysis(
        phrase=phrase,
        words=word_vectors,
        pairwise_resonance=tuple(pairwise),
        overall_harmony=overall_harmony,
        overall_dissonance=overall_dissonance,
        prediction=prediction,
        key_resonances=key_resonances,
    )


# =============================================================================
# Comparison
# =============================================================================

def compare_phrases(
    analysis_a: PhraseAnalysis,
    analysis_b: PhraseAnalysis
) -> dict:
    """
    Compare two phrase analyses and determine which is more harmonic.

    Args:
        analysis_a: First phrase analysis
        analysis_b: Second phrase analysis

    Returns:
        Dict with comparison results
    """
    harmony_diff = analysis_a.overall_harmony - analysis_b.overall_harmony

    if abs(harmony_diff) < 0.05:
        more_harmonic = "EQUAL"
        insight = "Both phrases have similar phonetic harmony."
    elif harmony_diff > 0:
        more_harmonic = analysis_a.phrase
        insight = f"'{analysis_a.phrase}' has stronger phonetic resonance."
    else:
        more_harmonic = analysis_b.phrase
        insight = f"'{analysis_b.phrase}' has stronger phonetic resonance."

    return {
        "phrase_a": analysis_a.phrase,
        "phrase_b": analysis_b.phrase,
        "harmony_a": analysis_a.overall_harmony,
        "harmony_b": analysis_b.overall_harmony,
        "harmony_difference": harmony_diff,
        "more_harmonic": more_harmonic,
        "insight": insight,
    }
