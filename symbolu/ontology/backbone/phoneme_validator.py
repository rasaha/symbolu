"""
Phoneme Validator
=================

Validates events against phoneme ground truth.

The key insight: If the phonemes of the word describing an event
don't match the 10D encoding of what was experienced, it's an anomaly -
a user-specific usage, not a universal pattern.

This closes the validation loop:
    Event → Words describing event → Phoneme analysis → Match experience?
                                                               ↓
                                            YES: Universal pattern (store it)
                                            NO:  Anomaly (discard or flag)

Usage:
    from symbolu.ontology.backbone.phoneme_validator import validate_event

    result = validate_event(
        event_text="The empire was shattered by internal conflict",
        event_words=["shattered", "conflict"],
    )

    if result.is_universal:
        # Safe to store and transfer
        store.add(experiential)
    else:
        # Anomaly - user-specific or metaphorical usage
        log.warning(f"Non-universal: {result.anomaly_reason}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import math

from .encoder import DimensionalVector, Dimension, encode_10d
from .mirror_pairs import tag_events, encode_with_events, TaggedEvent


class ValidationResult(Enum):
    """Result of phoneme validation."""
    UNIVERSAL = "universal"       # Phonemes match experience
    ANOMALY = "anomaly"           # Phonemes don't match
    METAPHORICAL = "metaphorical" # Intentional non-literal usage
    INSUFFICIENT = "insufficient"  # Not enough data to validate


@dataclass(frozen=True)
class PhonemeAlignment:
    """Alignment between a word's phoneme vector and event vector."""
    word: str
    phoneme_vector: Tuple[float, ...]  # 10D from phonemes
    event_vector: Tuple[float, ...]     # 10D from event encoding
    alignment_score: float              # Cosine similarity
    dominant_phoneme_layer: str
    dominant_event_layer: str
    is_aligned: bool                    # Above threshold


@dataclass
class ValidationReport:
    """
    Full validation report for an event description.

    The key output is `is_universal` - if True, this pattern
    can be safely stored and transferred across domains.
    """
    # Core result
    is_universal: bool
    result_type: ValidationResult
    overall_alignment: float  # 0.0 to 1.0

    # Event information
    event_text: str
    tagged_events: List[TaggedEvent]
    event_vector: DimensionalVector

    # Word-by-word analysis
    word_alignments: List[PhonemeAlignment]
    aligned_words: List[str]
    anomalous_words: List[str]

    # Explanation
    anomaly_reason: Optional[str] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_universal": self.is_universal,
            "result_type": self.result_type.value,
            "overall_alignment": self.overall_alignment,
            "event_text": self.event_text,
            "tagged_events": [
                {"type": e.event_type.value, "text": e.trigger_text}
                for e in self.tagged_events
            ],
            "aligned_words": self.aligned_words,
            "anomalous_words": self.anomalous_words,
            "anomaly_reason": self.anomaly_reason,
            "confidence": self.confidence,
        }


# =============================================================================
# Layer Name Mapping
# =============================================================================

# Map between backbone dimension names and resonance layer names
BACKBONE_TO_RESONANCE: Dict[Dimension, int] = {
    Dimension.MIND: 0,          # O1_THINKING
    Dimension.BODY: 1,          # O2_FORMING
    Dimension.ACTION: 2,        # O3_ACTING
    Dimension.IDENTIFICATION: 3, # O4_TAGGING
    Dimension.EGO: 4,           # O5_DIRECTING
    Dimension.INTELLECT: 5,     # O6_REASONING
    Dimension.SOUL: 6,          # O7_PURPOSING
    Dimension.WITNESS: 7,       # O8_META_OBSERVING
    Dimension.SINGULARITY: 8,   # O9_UNIFYING
    Dimension.ABSOLUTE: 9,      # O10_ABSOLVING
}

RESONANCE_LAYER_NAMES = (
    "O1_THINKING",
    "O2_FORMING",
    "O3_ACTING",
    "O4_TAGGING",
    "O5_DIRECTING",
    "O6_REASONING",
    "O7_PURPOSING",
    "O8_META_OBSERVING",
    "O9_UNIFYING",
    "O10_ABSOLVING",
)


# =============================================================================
# Core Validation Functions
# =============================================================================

def _get_phoneme_vector(word: str) -> Optional[Tuple[float, ...]]:
    """
    Get 10D vector for a word via phoneme analysis.

    Returns None if phoneme analysis is not available.
    """
    try:
        from symbolu.resonance import analyze_word
        result = analyze_word(word)
        if result and result.vector:
            # result.vector is already the tuple of 10 floats
            return result.vector
    except ImportError:
        pass
    except Exception:
        pass

    return None


def _dimensional_to_tuple(vec: DimensionalVector) -> Tuple[float, ...]:
    """Convert DimensionalVector to tuple in resonance order."""
    return tuple(
        vec.get(dim) for dim in [
            Dimension.MIND,           # O1
            Dimension.BODY,           # O2
            Dimension.ACTION,         # O3
            Dimension.IDENTIFICATION, # O4
            Dimension.EGO,            # O5
            Dimension.INTELLECT,      # O6
            Dimension.SOUL,           # O7
            Dimension.WITNESS,        # O8
            Dimension.SINGULARITY,    # O9
            Dimension.ABSOLUTE,       # O10
        ]
    )


def _cosine_similarity(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)


def _get_dominant_layer(vector: Tuple[float, ...]) -> str:
    """Get the dominant layer name from a vector."""
    if not vector:
        return "UNKNOWN"
    max_idx = max(range(len(vector)), key=lambda i: vector[i])
    if max_idx < len(RESONANCE_LAYER_NAMES):
        return RESONANCE_LAYER_NAMES[max_idx]
    return "UNKNOWN"


def _extract_key_words(text: str, events: List[TaggedEvent]) -> List[str]:
    """
    Extract key words that describe the events.

    Focus on:
    - Event trigger phrases
    - Verbs and action words
    - Descriptive adjectives
    """
    import re

    words = set()

    # Add trigger text from events
    for event in events:
        phrase_words = re.findall(r'\b[a-zA-Z]+\b', event.trigger_text.lower())
        words.update(phrase_words)

    # Common stop words to filter
    stop_words = {
        'the', 'a', 'an', 'is', 'was', 'were', 'are', 'been', 'be', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'to', 'of', 'in',
        'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'and', 'but', 'or', 'nor', 'so',
        'yet', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'not', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
        'also', 'now', 'here', 'there', 'when', 'where', 'why', 'how', 'all',
        'any', 'both', 'each', 'if', 'which', 'who', 'whom', 'this', 'that',
        'these', 'those', 'what', 'its', 'it', 'they', 'their', 'them', 'he',
        'she', 'his', 'her', 'we', 'our', 'us', 'you', 'your', 'i', 'my', 'me',
    }

    # Filter stop words and short words
    filtered = [w for w in words if w not in stop_words and len(w) > 2]

    return list(filtered)


def validate_event(
    event_text: str,
    event_words: Optional[List[str]] = None,
    alignment_threshold: float = 0.5,
    min_aligned_ratio: float = 0.6,
) -> ValidationReport:
    """
    Validate that words describing an event match its experiential meaning.

    This is the ground truth check: do the phonemes encode the same
    meaning as the event itself?

    Args:
        event_text: The full text describing the event
        event_words: Specific words to validate (auto-extracted if None)
        alignment_threshold: Minimum cosine similarity for alignment
        min_aligned_ratio: Minimum ratio of aligned words for universal

    Returns:
        ValidationReport with is_universal flag and details
    """
    # Step 1: Encode the event using the 10D backbone
    event_vector, tagged_events, balance = encode_with_events(event_text)
    event_tuple = _dimensional_to_tuple(event_vector)

    # Step 2: Extract key words if not provided
    if event_words is None:
        event_words = _extract_key_words(event_text, tagged_events)

    if not event_words:
        return ValidationReport(
            is_universal=False,
            result_type=ValidationResult.INSUFFICIENT,
            overall_alignment=0.0,
            event_text=event_text,
            tagged_events=tagged_events,
            event_vector=event_vector,
            word_alignments=[],
            aligned_words=[],
            anomalous_words=[],
            anomaly_reason="No key words found to validate",
            confidence=0.0,
        )

    # Step 3: Get phoneme vectors for each word and compare
    alignments: List[PhonemeAlignment] = []
    aligned_words: List[str] = []
    anomalous_words: List[str] = []

    for word in event_words:
        phoneme_vec = _get_phoneme_vector(word)

        if phoneme_vec is None:
            # Can't validate this word - skip but don't count as anomaly
            continue

        # Compute alignment
        similarity = _cosine_similarity(phoneme_vec, event_tuple)

        alignment = PhonemeAlignment(
            word=word,
            phoneme_vector=phoneme_vec,
            event_vector=event_tuple,
            alignment_score=similarity,
            dominant_phoneme_layer=_get_dominant_layer(phoneme_vec),
            dominant_event_layer=_get_dominant_layer(event_tuple),
            is_aligned=similarity >= alignment_threshold,
        )
        alignments.append(alignment)

        if alignment.is_aligned:
            aligned_words.append(word)
        else:
            anomalous_words.append(word)

    # Step 4: Determine overall result
    if not alignments:
        return ValidationReport(
            is_universal=False,
            result_type=ValidationResult.INSUFFICIENT,
            overall_alignment=0.0,
            event_text=event_text,
            tagged_events=tagged_events,
            event_vector=event_vector,
            word_alignments=[],
            aligned_words=[],
            anomalous_words=event_words,
            anomaly_reason="Could not analyze phonemes for any words",
            confidence=0.0,
        )

    # Calculate overall alignment
    overall_alignment = sum(a.alignment_score for a in alignments) / len(alignments)
    aligned_ratio = len(aligned_words) / len(alignments)

    # Determine if universal
    is_universal = aligned_ratio >= min_aligned_ratio and overall_alignment >= alignment_threshold

    # Determine result type
    if is_universal:
        result_type = ValidationResult.UNIVERSAL
        anomaly_reason = None
    elif aligned_ratio > 0.3:
        result_type = ValidationResult.METAPHORICAL
        anomaly_reason = f"Partial alignment ({aligned_ratio:.0%}) suggests metaphorical usage"
    else:
        result_type = ValidationResult.ANOMALY
        anomaly_reason = f"Low alignment ({overall_alignment:.2f}) - phonemes don't match experience"

    # Confidence based on sample size and alignment variance
    alignment_scores = [a.alignment_score for a in alignments]
    variance = sum((s - overall_alignment) ** 2 for s in alignment_scores) / len(alignment_scores)
    confidence = min(1.0, len(alignments) / 5.0) * (1.0 - min(1.0, variance))

    return ValidationReport(
        is_universal=is_universal,
        result_type=result_type,
        overall_alignment=overall_alignment,
        event_text=event_text,
        tagged_events=tagged_events,
        event_vector=event_vector,
        word_alignments=alignments,
        aligned_words=aligned_words,
        anomalous_words=anomalous_words,
        anomaly_reason=anomaly_reason,
        confidence=confidence,
    )


def validate_experiential_before_store(
    content: str,
    threshold: float = 0.5,
) -> Tuple[bool, ValidationReport]:
    """
    Validate content before storing as experiential.

    Returns (should_store, report).
    """
    report = validate_event(content, alignment_threshold=threshold)
    return report.is_universal, report


# =============================================================================
# Batch Validation
# =============================================================================

def validate_batch(
    items: List[str],
    threshold: float = 0.5,
) -> Dict[str, ValidationReport]:
    """
    Validate multiple items and return results.

    Returns dict mapping content to validation report.
    """
    results = {}
    for item in items:
        results[item] = validate_event(item, alignment_threshold=threshold)
    return results


def filter_universal(
    items: List[str],
    threshold: float = 0.5,
) -> List[str]:
    """
    Filter to only universal patterns.

    Returns items that pass phoneme validation.
    """
    universal = []
    for item in items:
        report = validate_event(item, alignment_threshold=threshold)
        if report.is_universal:
            universal.append(item)
    return universal


# =============================================================================
# Semantic Contradiction Check (runs BEFORE phoneme validation)
# =============================================================================

# Known semantic opposites - words that logically contradict
SEMANTIC_OPPOSITES = {
    # Temperature
    'hot': {'cold', 'frozen', 'icy', 'freezing', 'cool', 'chilly'},
    'cold': {'hot', 'warm', 'burning', 'heated', 'fiery'},
    'warm': {'cold', 'frozen', 'icy', 'freezing', 'cool'},
    'cool': {'hot', 'warm', 'burning', 'heated'},
    # Light/Dark
    'light': {'dark', 'dim', 'shadowy', 'black'},
    'dark': {'light', 'bright', 'luminous', 'radiant'},
    'bright': {'dark', 'dim', 'dull', 'shadowy'},
    # State
    'alive': {'dead', 'lifeless', 'deceased'},
    'dead': {'alive', 'living', 'vital'},
    # Size
    'big': {'small', 'tiny', 'little', 'miniature'},
    'small': {'big', 'large', 'huge', 'giant', 'massive'},
    # Speed
    'fast': {'slow', 'sluggish', 'crawling'},
    'slow': {'fast', 'quick', 'rapid', 'swift'},
    # Emotion
    'love': {'hate', 'loathe', 'despise'},
    'hate': {'love', 'adore', 'cherish'},
    'happy': {'sad', 'unhappy', 'miserable', 'depressed'},
    'sad': {'happy', 'joyful', 'elated', 'cheerful'},
    # State of being
    'peace': {'war', 'conflict', 'battle', 'fighting'},
    'war': {'peace', 'harmony', 'tranquility'},
    # Elements
    'fire': {'water', 'ice', 'cold', 'frozen'},
    'water': {'fire', 'flame', 'burning'},
    'ice': {'fire', 'hot', 'burning', 'warm'},
}


@dataclass(frozen=True)
class SemanticCheck:
    """Result of semantic contradiction check."""
    word1: str
    word2: str
    is_contradiction: bool
    contradiction_type: str  # 'opposite', 'incompatible', 'none'
    explanation: str


def check_semantic_contradiction(word1: str, word2: str) -> SemanticCheck:
    """
    Check if two words are semantic contradictions.

    This runs BEFORE phoneme validation to catch logical impossibilities
    like "fire cold" or "dead alive".

    Args:
        word1: First word
        word2: Second word

    Returns:
        SemanticCheck with is_contradiction flag
    """
    w1_lower = word1.lower()
    w2_lower = word2.lower()

    # Check if word2 is in word1's opposite set
    if w1_lower in SEMANTIC_OPPOSITES:
        if w2_lower in SEMANTIC_OPPOSITES[w1_lower]:
            return SemanticCheck(
                word1=word1,
                word2=word2,
                is_contradiction=True,
                contradiction_type='opposite',
                explanation=f"'{word1}' and '{word2}' are semantic opposites"
            )

    # Check reverse direction
    if w2_lower in SEMANTIC_OPPOSITES:
        if w1_lower in SEMANTIC_OPPOSITES[w2_lower]:
            return SemanticCheck(
                word1=word1,
                word2=word2,
                is_contradiction=True,
                contradiction_type='opposite',
                explanation=f"'{word2}' and '{word1}' are semantic opposites"
            )

    return SemanticCheck(
        word1=word1,
        word2=word2,
        is_contradiction=False,
        contradiction_type='none',
        explanation='No semantic contradiction detected'
    )


# =============================================================================
# Word-Pair Entropy Validation
# =============================================================================

@dataclass(frozen=True)
class WordPairHarmony:
    """
    Harmony analysis between two words based on phoneme vectors.

    High harmony = words naturally go together (sky + blue)
    High entropy = words clash experientially (sky + red)
    """
    word1: str
    word2: str
    vector1: Optional[Tuple[float, ...]]
    vector2: Optional[Tuple[float, ...]]
    harmony_score: float          # 0.0 to 1.0 (higher = more natural pairing)
    entropy_flag: bool            # True if high entropy (unnatural pairing)
    dominant_layer1: str
    dominant_layer2: str
    shared_layers: List[str]      # Layers where both words are strong
    conflicting_layers: List[str] # Layers where one is strong, other is weak


def validate_word_pair(
    word1: str,
    word2: str,
    harmony_threshold: float = 0.6,
    conflict_threshold: float = 0.3,
) -> WordPairHarmony:
    """
    Validate if two words naturally go together based on phoneme harmony.

    The validation pipeline:
    1. FIRST: Check for semantic contradictions (fire+cold = immediate fail)
    2. THEN: Check phoneme harmony (do sounds match combined meaning?)

    The key insight: Encode the COMBINED phrase as an event, then check if
    each word's phonemes align with that combined meaning. Natural pairs
    will have both words aligning with their combined meaning.

    Args:
        word1: First word (e.g., "sky")
        word2: Second word (e.g., "blue" or "red")
        harmony_threshold: Minimum harmony for natural pairing
        conflict_threshold: Below this = high entropy

    Returns:
        WordPairHarmony with entropy_flag = True if unnatural pairing

    Example:
        >>> validate_word_pair("sky", "blue")
        WordPairHarmony(harmony_score=0.85, entropy_flag=False, ...)

        >>> validate_word_pair("sky", "red")
        WordPairHarmony(harmony_score=0.42, entropy_flag=True, ...)

        >>> validate_word_pair("fire", "cold")
        WordPairHarmony(entropy_flag=True, ...)  # Semantic contradiction!
    """
    # STEP 1: Check semantic contradiction FIRST
    # This catches logical impossibilities before phoneme analysis
    semantic_check = check_semantic_contradiction(word1, word2)
    if semantic_check.is_contradiction:
        # Immediate failure - logical contradiction detected
        vec1 = _get_phoneme_vector(word1)
        vec2 = _get_phoneme_vector(word2)
        return WordPairHarmony(
            word1=word1,
            word2=word2,
            vector1=vec1,
            vector2=vec2,
            harmony_score=0.0,  # Semantic contradiction = zero harmony
            entropy_flag=True,  # Always high entropy for contradictions
            dominant_layer1=_get_dominant_layer(vec1) if vec1 else "UNKNOWN",
            dominant_layer2=_get_dominant_layer(vec2) if vec2 else "UNKNOWN",
            shared_layers=[],
            conflicting_layers=["SEMANTIC_CONTRADICTION"],
        )

    # STEP 2: Proceed with phoneme analysis
    vec1 = _get_phoneme_vector(word1)
    vec2 = _get_phoneme_vector(word2)

    if vec1 is None or vec2 is None:
        return WordPairHarmony(
            word1=word1,
            word2=word2,
            vector1=vec1,
            vector2=vec2,
            harmony_score=0.0,
            entropy_flag=True,
            dominant_layer1="UNKNOWN",
            dominant_layer2="UNKNOWN",
            shared_layers=[],
            conflicting_layers=[],
        )

    # KEY INSIGHT: Encode the combined phrase as an event
    # Then check if each word's phonemes match the combined meaning
    combined_phrase = f"{word1} {word2}"
    combined_event_vector, _, _ = encode_with_events(combined_phrase)
    combined_tuple = _dimensional_to_tuple(combined_event_vector)

    # How well does each word's phonemes match the COMBINED meaning?
    word1_to_combined = _cosine_similarity(vec1, combined_tuple)
    word2_to_combined = _cosine_similarity(vec2, combined_tuple)

    # Natural pairs: BOTH words phonetically match their combined meaning
    # Unnatural pairs: One or both words don't match the combined meaning
    combined_alignment = (word1_to_combined + word2_to_combined) / 2.0

    # Get dominant layers
    dom1 = _get_dominant_layer(vec1)
    dom2 = _get_dominant_layer(vec2)

    # Find shared and conflicting layers
    shared = []
    conflicting = []
    HIGH_THRESHOLD = 0.35
    LOW_THRESHOLD = 0.20

    for i in range(min(len(vec1), len(vec2), len(RESONANCE_LAYER_NAMES))):
        v1, v2 = vec1[i], vec2[i]
        layer = RESONANCE_LAYER_NAMES[i]

        if v1 >= HIGH_THRESHOLD and v2 >= HIGH_THRESHOLD:
            shared.append(layer)
        elif (v1 >= HIGH_THRESHOLD and v2 < LOW_THRESHOLD) or \
             (v2 >= HIGH_THRESHOLD and v1 < LOW_THRESHOLD):
            conflicting.append(layer)

    # Structural similarity between the two words
    structural_sim = _cosine_similarity(vec1, vec2)

    # KEY INSIGHT: UNIFYING layer (O9, index 8) indicates natural harmony
    # Words with high UNIFYING create more natural pairings
    # "blue" has high UNIFYING (0.42), "red" has lower (0.31)
    UNIFYING_INDEX = 8  # O9_UNIFYING
    unifying_score1 = vec1[UNIFYING_INDEX] if len(vec1) > UNIFYING_INDEX else 0.0
    unifying_score2 = vec2[UNIFYING_INDEX] if len(vec2) > UNIFYING_INDEX else 0.0

    # Combined unifying indicates natural pairing potential
    combined_unifying = (unifying_score1 + unifying_score2) / 2.0

    # Final harmony score combines:
    # 1. Combined alignment (do phonemes match combined meaning?) - PRIMARY
    # 2. Structural similarity (do words have similar phoneme structure?)
    # 3. UNIFYING layer presence (natural harmony indicator) - NEW
    harmony_score = (combined_alignment * 0.5) + (structural_sim * 0.2) + (combined_unifying * 0.3)

    # Bonus for shared purpose layers
    purpose_layers = {"O3_ACTING", "O2_FORMING", "O7_PURPOSING", "O9_UNIFYING"}
    purpose_shared = len([l for l in shared if l in purpose_layers])
    harmony_score += purpose_shared * 0.02

    # Penalty for conflicting layers
    harmony_score -= len(conflicting) * 0.05

    harmony_score = max(0.0, min(1.0, harmony_score))

    # Determine entropy flag using tiered UNIFYING thresholds
    # KEY: The modifier word (word2) should have sufficient UNIFYING for natural pairing
    #
    # Tiers based on UNIFYING score:
    #   >= 0.35: NATURAL (blue=0.42, orange=0.43, clear=0.34) - default states
    #   0.25-0.35: ACCEPTABLE (white=0.28, grey=0.33, red=0.31) - common variants
    #   < 0.25: EXCEPTIONAL (pink=0.22, purple=0.30) - rare/unusual states
    #
    UNIFYING_EXCEPTIONAL_THRESHOLD = 0.25  # Below this = truly high entropy
    UNIFYING_NATURAL_THRESHOLD = 0.35      # Above this = definitely natural

    modifier_is_exceptional = unifying_score2 < UNIFYING_EXCEPTIONAL_THRESHOLD
    modifier_is_natural = unifying_score2 >= UNIFYING_NATURAL_THRESHOLD

    # High entropy only if:
    # 1. Modifier word is truly exceptional (UNIFYING < 0.25), OR
    # 2. Too many conflicting layers
    entropy_flag = modifier_is_exceptional or len(conflicting) > 2

    return WordPairHarmony(
        word1=word1,
        word2=word2,
        vector1=vec1,
        vector2=vec2,
        harmony_score=harmony_score,
        entropy_flag=entropy_flag,
        dominant_layer1=dom1,
        dominant_layer2=dom2,
        shared_layers=shared,
        conflicting_layers=conflicting,
    )


def validate_phrase_harmony(
    words: List[str],
    harmony_threshold: float = 0.6,
) -> Tuple[float, List[Tuple[str, str, bool]]]:
    """
    Validate harmony across all word pairs in a phrase.

    Returns:
        Tuple of (overall_harmony, list of (word1, word2, is_harmonic))
    """
    if len(words) < 2:
        return 1.0, []

    pairs = []
    total_harmony = 0.0
    count = 0

    for i in range(len(words)):
        for j in range(i + 1, len(words)):
            result = validate_word_pair(words[i], words[j], harmony_threshold)
            pairs.append((words[i], words[j], not result.entropy_flag))
            total_harmony += result.harmony_score
            count += 1

    overall = total_harmony / count if count > 0 else 0.0
    return overall, pairs


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ValidationResult",
    "PhonemeAlignment",
    "ValidationReport",
    "validate_event",
    "validate_experiential_before_store",
    "validate_batch",
    "filter_universal",
    # Semantic contradiction check
    "SemanticCheck",
    "check_semantic_contradiction",
    "SEMANTIC_OPPOSITES",
    # Word-pair entropy validation
    "WordPairHarmony",
    "validate_word_pair",
    "validate_phrase_harmony",
]
