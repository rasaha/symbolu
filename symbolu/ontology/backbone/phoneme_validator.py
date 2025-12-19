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
]
