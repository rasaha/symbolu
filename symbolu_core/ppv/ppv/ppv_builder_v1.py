"""
PPV Builder v1 - Deterministic PPV Construction
=================================================

Builds PPV (Phonemic Propensity Vectors) from Phase-10 artifacts.

PPV is computed ONLY from deterministic artifacts:
    - Phase-1b/Phase-2/Phase-4 units (phoneme sequence identifiers)
    - Phase-10 result with stable references to phoneme groups/spans

PPV does NOT depend on:
    - Dictionaries (lexical lookup)
    - External corpora
    - Time
    - Randomness
    - ML models

Allowed computations ONLY:
    - Counting patterns
    - Adjacency signatures
    - Fold sizes
    - Boundary positions
    - Deterministic mapping tables from phoneme IDs to small integer features

CRITICAL: PPV is NOT "emotion meaning." It is a structural signal only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from symbolu_core.ppv.ppv_contract_v1 import (
    PPV_DIM_COUNT,
    PPV_DIM_ORDER,
    PPV_VALUE_MAX,
    PPV_VALUE_MIN,
    PPVDim,
    PPVVector,
    create_ppv_vector,
)


# =============================================================================
# Version Constant
# =============================================================================

PPV_BUILDER_VERSION = "1.0.0"


# =============================================================================
# Phoneme Feature Table (Deterministic Mapping)
# =============================================================================

# This table maps phoneme identifiers to structural features.
# Features are tuples of 8 ints corresponding to PPV dimensions:
# (edge_tension, edge_release, onset_sharpness, sonority_lift,
#  continuity, discontinuity, rhythmic_impulse, stability_pressure)
#
# These are NOT semantic/emotional values - they are structural phonetic features.
# Values are bounded [0, 7].

PHONEME_FEATURES: Dict[str, Tuple[int, ...]] = {
    # Vowels - generally high sonority, continuity
    "a": (1, 2, 1, 6, 5, 1, 3, 2),
    "e": (1, 2, 1, 5, 5, 1, 3, 2),
    "i": (2, 1, 2, 4, 5, 1, 4, 3),
    "o": (1, 2, 1, 6, 5, 1, 2, 2),
    "u": (1, 2, 1, 5, 5, 1, 2, 2),

    # Consonants - plosives (high edge tension, onset sharpness)
    "p": (5, 3, 6, 1, 1, 5, 5, 4),
    "b": (4, 3, 5, 2, 1, 4, 5, 3),
    "t": (5, 3, 6, 1, 1, 5, 5, 4),
    "d": (4, 3, 5, 2, 1, 4, 5, 3),
    "k": (5, 3, 6, 1, 1, 5, 4, 4),
    "g": (4, 3, 5, 2, 1, 4, 4, 3),

    # Fricatives - moderate tension, continuity
    "f": (3, 2, 4, 2, 4, 2, 3, 3),
    "v": (2, 2, 3, 3, 4, 2, 3, 2),
    "s": (4, 2, 5, 2, 4, 2, 4, 4),
    "z": (3, 2, 4, 3, 4, 2, 4, 3),
    "sh": (3, 2, 4, 2, 4, 2, 3, 3),
    "zh": (2, 2, 3, 3, 4, 2, 3, 2),
    "th": (2, 2, 3, 2, 4, 2, 2, 2),
    "dh": (2, 2, 2, 3, 4, 2, 2, 2),
    "h": (1, 3, 2, 1, 3, 3, 2, 1),

    # Nasals - moderate sonority, continuity
    "m": (2, 3, 2, 4, 5, 2, 3, 3),
    "n": (2, 3, 2, 4, 5, 2, 3, 3),
    "ng": (2, 3, 2, 4, 5, 2, 2, 3),

    # Liquids and glides - high sonority, continuity
    "l": (1, 2, 2, 5, 6, 1, 3, 2),
    "r": (2, 2, 3, 5, 5, 1, 3, 2),
    "w": (1, 2, 1, 5, 6, 1, 2, 2),
    "y": (2, 2, 2, 4, 5, 1, 3, 3),

    # Affricates - combination features
    "ch": (4, 3, 5, 2, 2, 4, 4, 4),
    "j": (3, 3, 4, 3, 2, 4, 4, 3),

    # Diphthongs and special combinations
    "ai": (1, 2, 2, 5, 4, 2, 3, 2),
    "au": (1, 2, 1, 6, 4, 2, 2, 2),
    "oi": (1, 2, 2, 5, 4, 2, 3, 2),
    "ou": (1, 2, 1, 6, 4, 2, 2, 2),

    # Sanskrit-specific phonemes (neutral structural features)
    "sa": (3, 2, 4, 4, 4, 2, 4, 3),
    "ma": (2, 3, 2, 5, 5, 2, 3, 3),
    "na": (2, 3, 2, 5, 5, 2, 3, 3),
    "ta": (4, 3, 5, 4, 2, 4, 4, 4),
    "da": (3, 3, 4, 5, 2, 4, 4, 3),
    "pa": (4, 3, 5, 4, 2, 4, 4, 4),
    "ba": (3, 3, 4, 5, 2, 4, 4, 3),
    "ka": (4, 3, 5, 4, 2, 4, 3, 4),
    "ga": (3, 3, 4, 5, 2, 4, 3, 3),
    "ra": (2, 2, 3, 5, 5, 1, 3, 2),
    "la": (1, 2, 2, 5, 6, 1, 3, 2),
    "va": (2, 2, 3, 5, 4, 2, 3, 2),
    "ya": (2, 2, 2, 5, 5, 1, 3, 3),
    "ha": (1, 3, 2, 5, 3, 3, 2, 2),

    # Additional compound phonemes
    "om": (2, 3, 2, 6, 5, 2, 2, 3),
    "ah": (1, 3, 2, 6, 4, 3, 2, 2),
    "ih": (2, 3, 2, 5, 4, 3, 3, 3),
    "uh": (1, 3, 2, 5, 4, 3, 2, 2),
}

# Default features for unknown phonemes (all zeros)
DEFAULT_PHONEME_FEATURES: Tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0, 0)


# =============================================================================
# PPV Build Context
# =============================================================================


@dataclass(frozen=True)
class PPVBuildContext:
    """
    Context for PPV building from Phase-10 artifacts.

    This captures the deterministic inputs needed for PPV computation.

    Attributes:
        phoneme_ids: Tuple of phoneme identifiers from upstream phases
        adjacency_markers: Tuple of adjacency boundary markers
        span_boundaries: Tuple of span boundary positions
        fold_sizes: Tuple of fold/group sizes
        acoustic_regime: Acoustic regime string from Phase-10
    """
    phoneme_ids: Tuple[str, ...]
    adjacency_markers: Tuple[str, ...]
    span_boundaries: Tuple[int, ...]
    fold_sizes: Tuple[int, ...]
    acoustic_regime: str

    def __post_init__(self) -> None:
        """Validate PPVBuildContext invariants."""
        if not isinstance(self.phoneme_ids, tuple):
            raise ValueError(
                f"phoneme_ids must be tuple, got {type(self.phoneme_ids).__name__}"
            )
        if not isinstance(self.adjacency_markers, tuple):
            raise ValueError(
                f"adjacency_markers must be tuple, got {type(self.adjacency_markers).__name__}"
            )
        if not isinstance(self.span_boundaries, tuple):
            raise ValueError(
                f"span_boundaries must be tuple, got {type(self.span_boundaries).__name__}"
            )
        if not isinstance(self.fold_sizes, tuple):
            raise ValueError(
                f"fold_sizes must be tuple, got {type(self.fold_sizes).__name__}"
            )
        if not isinstance(self.acoustic_regime, str):
            raise ValueError(
                f"acoustic_regime must be str, got {type(self.acoustic_regime).__name__}"
            )


# =============================================================================
# Internal Computation Functions
# =============================================================================


def _get_phoneme_features(phoneme_id: str) -> Tuple[int, ...]:
    """
    Get structural features for a phoneme identifier.

    Args:
        phoneme_id: The phoneme identifier string.

    Returns:
        Tuple of 8 ints representing structural features.
    """
    # Normalize to lowercase
    normalized = phoneme_id.lower().strip()

    # Lookup in table
    if normalized in PHONEME_FEATURES:
        return PHONEME_FEATURES[normalized]

    # Check for partial matches (e.g., "sa1" -> "sa")
    for key in PHONEME_FEATURES:
        if normalized.startswith(key):
            return PHONEME_FEATURES[key]

    # Return default for unknown phonemes
    return DEFAULT_PHONEME_FEATURES


def _clamp_value(val: int) -> int:
    """Clamp value to PPV bounds [0, 7]."""
    if val < PPV_VALUE_MIN:
        return PPV_VALUE_MIN
    if val > PPV_VALUE_MAX:
        return PPV_VALUE_MAX
    return val


def _compute_edge_tension(
    phoneme_features: List[Tuple[int, ...]],
    adjacency_markers: Tuple[str, ...],
) -> int:
    """
    Compute EDGE_TENSION dimension from phoneme sequence.

    Higher tension at edges/boundaries.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        adjacency_markers: Adjacency boundary markers.

    Returns:
        Clamped int value for EDGE_TENSION dimension.
    """
    if not phoneme_features:
        return 0

    # Average edge tension from phoneme features
    tensions = [f[0] for f in phoneme_features]  # Index 0 = edge_tension
    avg_tension = sum(tensions) / len(tensions)

    # Bonus for boundary markers (discontinuities increase tension)
    boundary_bonus = len(adjacency_markers) * 0.5

    raw_value = avg_tension + boundary_bonus
    return _clamp_value(int(round(raw_value)))


def _compute_edge_release(
    phoneme_features: List[Tuple[int, ...]],
    span_boundaries: Tuple[int, ...],
) -> int:
    """
    Compute EDGE_RELEASE dimension from phoneme sequence.

    Higher release at span ends.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        span_boundaries: Span boundary positions.

    Returns:
        Clamped int value for EDGE_RELEASE dimension.
    """
    if not phoneme_features:
        return 0

    # Average edge release from phoneme features
    releases = [f[1] for f in phoneme_features]  # Index 1 = edge_release
    avg_release = sum(releases) / len(releases)

    # Bonus based on span boundary count (more boundaries = more release points)
    boundary_factor = min(len(span_boundaries), 4) * 0.3

    raw_value = avg_release + boundary_factor
    return _clamp_value(int(round(raw_value)))


def _compute_onset_sharpness(
    phoneme_features: List[Tuple[int, ...]],
) -> int:
    """
    Compute ONSET_SHARPNESS dimension from phoneme sequence.

    Higher for plosives and fricatives at onset positions.

    Args:
        phoneme_features: List of feature tuples for each phoneme.

    Returns:
        Clamped int value for ONSET_SHARPNESS dimension.
    """
    if not phoneme_features:
        return 0

    # Average onset sharpness from phoneme features
    sharpness = [f[2] for f in phoneme_features]  # Index 2 = onset_sharpness
    avg_sharpness = sum(sharpness) / len(sharpness)

    # Weight first phoneme more heavily (actual onset)
    if len(phoneme_features) > 0:
        onset_weight = phoneme_features[0][2] * 0.3
        avg_sharpness = avg_sharpness * 0.7 + onset_weight

    return _clamp_value(int(round(avg_sharpness)))


def _compute_sonority_lift(
    phoneme_features: List[Tuple[int, ...]],
) -> int:
    """
    Compute SONORITY_LIFT dimension from phoneme sequence.

    Higher for vowels and sonorants.

    Args:
        phoneme_features: List of feature tuples for each phoneme.

    Returns:
        Clamped int value for SONORITY_LIFT dimension.
    """
    if not phoneme_features:
        return 0

    # Average sonority lift from phoneme features
    lifts = [f[3] for f in phoneme_features]  # Index 3 = sonority_lift
    avg_lift = sum(lifts) / len(lifts)

    return _clamp_value(int(round(avg_lift)))


def _compute_continuity(
    phoneme_features: List[Tuple[int, ...]],
    fold_sizes: Tuple[int, ...],
) -> int:
    """
    Compute CONTINUITY dimension from phoneme sequence.

    Higher for continuous phonemes and longer folds.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        fold_sizes: Fold/group sizes.

    Returns:
        Clamped int value for CONTINUITY dimension.
    """
    if not phoneme_features:
        return 0

    # Average continuity from phoneme features
    continuities = [f[4] for f in phoneme_features]  # Index 4 = continuity
    avg_continuity = sum(continuities) / len(continuities)

    # Bonus for larger folds (longer continuous spans)
    if fold_sizes:
        avg_fold = sum(fold_sizes) / len(fold_sizes)
        fold_bonus = min(avg_fold / 3.0, 2.0)
        avg_continuity += fold_bonus

    return _clamp_value(int(round(avg_continuity)))


def _compute_discontinuity(
    phoneme_features: List[Tuple[int, ...]],
    adjacency_markers: Tuple[str, ...],
    span_boundaries: Tuple[int, ...],
) -> int:
    """
    Compute DISCONTINUITY dimension from phoneme sequence.

    Higher for plosives and many boundaries.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        adjacency_markers: Adjacency boundary markers.
        span_boundaries: Span boundary positions.

    Returns:
        Clamped int value for DISCONTINUITY dimension.
    """
    if not phoneme_features:
        return 0

    # Average discontinuity from phoneme features
    discontinuities = [f[5] for f in phoneme_features]  # Index 5 = discontinuity
    avg_discontinuity = sum(discontinuities) / len(discontinuities)

    # Bonus for boundary markers
    boundary_count = len(adjacency_markers) + len(span_boundaries)
    boundary_bonus = min(boundary_count * 0.3, 2.0)

    raw_value = avg_discontinuity + boundary_bonus
    return _clamp_value(int(round(raw_value)))


def _compute_rhythmic_impulse(
    phoneme_features: List[Tuple[int, ...]],
    fold_sizes: Tuple[int, ...],
) -> int:
    """
    Compute RHYTHMIC_IMPULSE dimension from phoneme sequence.

    Based on alternation patterns and fold regularity.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        fold_sizes: Fold/group sizes.

    Returns:
        Clamped int value for RHYTHMIC_IMPULSE dimension.
    """
    if not phoneme_features:
        return 0

    # Average rhythmic impulse from phoneme features
    impulses = [f[6] for f in phoneme_features]  # Index 6 = rhythmic_impulse
    avg_impulse = sum(impulses) / len(impulses)

    # Bonus for regular fold sizes (rhythm regularity)
    if fold_sizes and len(fold_sizes) >= 2:
        # Check variance in fold sizes
        fold_avg = sum(fold_sizes) / len(fold_sizes)
        variance = sum((f - fold_avg) ** 2 for f in fold_sizes) / len(fold_sizes)
        # Lower variance = more regular = higher impulse
        regularity_bonus = max(0, 2.0 - variance * 0.5)
        avg_impulse += regularity_bonus

    return _clamp_value(int(round(avg_impulse)))


def _compute_stability_pressure(
    phoneme_features: List[Tuple[int, ...]],
    acoustic_regime: str,
) -> int:
    """
    Compute STABILITY_PRESSURE dimension from phoneme sequence.

    Based on phoneme stability and regime.

    Args:
        phoneme_features: List of feature tuples for each phoneme.
        acoustic_regime: Acoustic regime string.

    Returns:
        Clamped int value for STABILITY_PRESSURE dimension.
    """
    if not phoneme_features:
        return 0

    # Average stability pressure from phoneme features
    pressures = [f[7] for f in phoneme_features]  # Index 7 = stability_pressure
    avg_pressure = sum(pressures) / len(pressures)

    # Regime-based modifier (deterministic, no semantic interpretation)
    regime_modifiers = {
        "neutral": 0.0,
        "soft": -0.5,
        "flat": 0.5,
        "restrained": 1.0,
    }
    regime_key = acoustic_regime.lower()
    regime_modifier = regime_modifiers.get(regime_key, 0.0)

    raw_value = avg_pressure + regime_modifier
    return _clamp_value(int(round(raw_value)))


def _compute_source_span_id(context: PPVBuildContext) -> str:
    """
    Compute deterministic span ID for PPV source.

    Args:
        context: The PPVBuildContext.

    Returns:
        16-char hex span ID.
    """
    # Hash over context content
    hash_input = f"{context.phoneme_ids}|{context.adjacency_markers}|{context.acoustic_regime}"
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Main Build Function
# =============================================================================


def build_ppv_from_context(context: PPVBuildContext) -> Optional[PPVVector]:
    """
    Build PPV from a PPVBuildContext.

    This is the core PPV builder function. It computes PPV only from
    deterministic structural features - no ML, no dictionaries, no randomness.

    Args:
        context: The PPVBuildContext with phoneme sequence and metadata.

    Returns:
        PPVVector if inputs are sufficient, None otherwise.
    """
    # Fail closed if no phonemes
    if not context.phoneme_ids:
        return None

    # Extract features for each phoneme
    phoneme_features: List[Tuple[int, ...]] = []
    for phoneme_id in context.phoneme_ids:
        features = _get_phoneme_features(phoneme_id)
        phoneme_features.append(features)

    # If all features are default (unknown phonemes), fail closed
    all_default = all(f == DEFAULT_PHONEME_FEATURES for f in phoneme_features)
    if all_default:
        return None

    # Compute each PPV dimension
    edge_tension = _compute_edge_tension(phoneme_features, context.adjacency_markers)
    edge_release = _compute_edge_release(phoneme_features, context.span_boundaries)
    onset_sharpness = _compute_onset_sharpness(phoneme_features)
    sonority_lift = _compute_sonority_lift(phoneme_features)
    continuity = _compute_continuity(phoneme_features, context.fold_sizes)
    discontinuity = _compute_discontinuity(
        phoneme_features, context.adjacency_markers, context.span_boundaries
    )
    rhythmic_impulse = _compute_rhythmic_impulse(phoneme_features, context.fold_sizes)
    stability_pressure = _compute_stability_pressure(
        phoneme_features, context.acoustic_regime
    )

    # Build values tuple in dimension order
    values = (
        edge_tension,
        edge_release,
        onset_sharpness,
        sonority_lift,
        continuity,
        discontinuity,
        rhythmic_impulse,
        stability_pressure,
    )

    # Compute source span ID
    source_span_id = _compute_source_span_id(context)

    # Create PPV vector
    return create_ppv_vector(
        values=values,
        source_unit_span_ids=(source_span_id,),
        version="1.0",
    )


def build_ppv_for_artifact(
    phase10_result: Any,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[PPVVector]:
    """
    Build PPV for a Phase-10 artifact.

    This is the public API for building PPV from Phase-10 results.
    If required inputs are absent, returns None (fail closed, no partial PPV).

    Args:
        phase10_result: The Phase-10 result object (must have source_data).
        context: Optional additional context dict.

    Returns:
        PPVVector if inputs are sufficient, None otherwise.
    """
    # Extract phoneme_ids from Phase-10 result
    # Try multiple possible locations for phoneme data
    source_data = getattr(phase10_result, "source_data", None)
    if source_data is None:
        source_data = context.get("source_data", {}) if context else {}

    # Try to get phoneme IDs
    phoneme_ids: Tuple[str, ...] = ()

    # Check for phoneme_ids in source_data
    if "phoneme_ids" in source_data:
        raw_ids = source_data["phoneme_ids"]
        if isinstance(raw_ids, (list, tuple)):
            phoneme_ids = tuple(str(p) for p in raw_ids)
    # Check for phoneme_sequence
    elif "phoneme_sequence" in source_data:
        raw_seq = source_data["phoneme_sequence"]
        if isinstance(raw_seq, (list, tuple)):
            phoneme_ids = tuple(str(p) for p in raw_seq)
    # Check for syllables (extract phonemes from syllables)
    elif "syllables" in source_data:
        syllables = source_data["syllables"]
        if isinstance(syllables, (list, tuple)):
            # Flatten syllables to phoneme-like units
            phoneme_ids = tuple(str(s).lower() for s in syllables)
    # Check context for phoneme data
    elif context and "phoneme_ids" in context:
        raw_ids = context["phoneme_ids"]
        if isinstance(raw_ids, (list, tuple)):
            phoneme_ids = tuple(str(p) for p in raw_ids)

    # Fail closed if no phonemes found
    if not phoneme_ids:
        return None

    # Extract adjacency markers
    adjacency_markers: Tuple[str, ...] = ()
    if "adjacency_markers" in source_data:
        raw_markers = source_data["adjacency_markers"]
        if isinstance(raw_markers, (list, tuple)):
            adjacency_markers = tuple(str(m) for m in raw_markers)
    elif context and "adjacency_markers" in context:
        raw_markers = context["adjacency_markers"]
        if isinstance(raw_markers, (list, tuple)):
            adjacency_markers = tuple(str(m) for m in raw_markers)

    # Extract span boundaries
    span_boundaries: Tuple[int, ...] = ()
    if "span_boundaries" in source_data:
        raw_bounds = source_data["span_boundaries"]
        if isinstance(raw_bounds, (list, tuple)):
            span_boundaries = tuple(int(b) for b in raw_bounds if isinstance(b, (int, float)))
    elif context and "span_boundaries" in context:
        raw_bounds = context["span_boundaries"]
        if isinstance(raw_bounds, (list, tuple)):
            span_boundaries = tuple(int(b) for b in raw_bounds if isinstance(b, (int, float)))

    # Extract fold sizes
    fold_sizes: Tuple[int, ...] = ()
    if "fold_sizes" in source_data:
        raw_folds = source_data["fold_sizes"]
        if isinstance(raw_folds, (list, tuple)):
            fold_sizes = tuple(int(f) for f in raw_folds if isinstance(f, (int, float)))
    elif context and "fold_sizes" in context:
        raw_folds = context["fold_sizes"]
        if isinstance(raw_folds, (list, tuple)):
            fold_sizes = tuple(int(f) for f in raw_folds if isinstance(f, (int, float)))

    # Get acoustic regime
    acoustic_regime = getattr(phase10_result, "acoustic_regime", "neutral")
    if not acoustic_regime:
        acoustic_regime = source_data.get("acoustic_regime", "neutral")
    if not acoustic_regime:
        acoustic_regime = context.get("acoustic_regime", "neutral") if context else "neutral"

    # Build context
    build_context = PPVBuildContext(
        phoneme_ids=phoneme_ids,
        adjacency_markers=adjacency_markers,
        span_boundaries=span_boundaries,
        fold_sizes=fold_sizes,
        acoustic_regime=str(acoustic_regime),
    )

    # Build and return PPV
    return build_ppv_from_context(build_context)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PPV_BUILDER_VERSION",
    # Feature table
    "PHONEME_FEATURES",
    "DEFAULT_PHONEME_FEATURES",
    # Context
    "PPVBuildContext",
    # Build functions
    "build_ppv_from_context",
    "build_ppv_for_artifact",
]
