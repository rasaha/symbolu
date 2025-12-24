"""
Name Resonance System - Structural Projection
==============================================

Layer 3: Project extracted signals into 12D domain-agnostic structural space.

Tier: Core/Substrate (Tier 1)
Determinism: FULL (same signals → same profile)
"""

from typing import Tuple, List

from symbolu.name_resonance.types import (
    ExtractedSignals,
    StructuralProfile,
    DIMENSION_NAMES,
)


# =============================================================================
# Signal → Dimension Mapping Rules
# =============================================================================

# Each dimension is computed as a weighted sum of signal-derived values.
# All weights are explicit and deterministic.

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))


def _safe_ratio(numerator: float, denominator: float, default: float = 0.5) -> float:
    """Compute ratio safely."""
    if denominator == 0:
        return default
    return numerator / denominator


# =============================================================================
# Dimension Computation Functions
# =============================================================================

def _compute_force(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute FORCE dimension: Low (flowing) to High (forceful).

    High force: plosives, strong initiation, stress
    Low force: liquids, glides, unstressed
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Plosive ratio contributes to force (weight: 0.40)
    plosive_ratio = signals.plosive_count / total_phonemes
    plosive_contrib = plosive_ratio * 0.40
    contributions.append(("force", "plosive_ratio", plosive_contrib))

    # Fricative ratio adds moderate force (weight: 0.25)
    fricative_ratio = signals.fricative_count / total_phonemes
    fricative_contrib = fricative_ratio * 0.25
    contributions.append(("force", "fricative_ratio", fricative_contrib))

    # Initial plosive adds force (weight: 0.20)
    initial_plosive = 1.0 if signals.initial_category == "plosive" else 0.0
    initial_contrib = initial_plosive * 0.20
    contributions.append(("force", "initial_plosive", initial_contrib))

    # Stress on first syllable adds force (weight: 0.15)
    first_stressed = 1.0 if (signals.stress_pattern and signals.stress_pattern[0] == 1) else 0.0
    stress_contrib = first_stressed * 0.15
    contributions.append(("force", "first_stressed", stress_contrib))

    total = plosive_contrib + fricative_contrib + initial_contrib + stress_contrib
    # Scale to reasonable range
    scaled = _clamp(total * 1.8 + 0.3, 0.0, 1.0)

    return scaled, contributions


def _compute_stability(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute STABILITY dimension: Variable to Constant.

    High stability: regular syllable structure, consistent patterns
    Low stability: irregular, many clusters
    """
    contributions = []

    # Syllable regularity: 2-3 syllables is most stable
    syllable_score = 1.0 if signals.syllable_count in (2, 3) else 0.6
    syllable_contrib = syllable_score * 0.35
    contributions.append(("stability", "syllable_regularity", syllable_contrib))

    # Low cluster count = more stable
    cluster_penalty = (signals.onset_cluster_size + signals.coda_cluster_size) / 4.0
    cluster_score = max(0.0, 1.0 - cluster_penalty)
    cluster_contrib = cluster_score * 0.30
    contributions.append(("stability", "cluster_regularity", cluster_contrib))

    # Balanced vowel/consonant ratio (around 0.4) = stable
    vc_ratio = signals.vowel_consonant_ratio
    balance_score = 1.0 - abs(vc_ratio - 0.4) * 2.0
    balance_contrib = max(0.0, balance_score) * 0.20
    contributions.append(("stability", "vc_balance", balance_contrib))

    # Stress regularity
    if signals.stress_pattern:
        stress_variance = sum(1 for i, s in enumerate(signals.stress_pattern)
                              if (i % 2 == 0 and s != 1) or (i % 2 == 1 and s != 0))
        stress_score = 1.0 - stress_variance / max(len(signals.stress_pattern), 1)
    else:
        stress_score = 0.5
    stress_contrib = stress_score * 0.15
    contributions.append(("stability", "stress_regularity", stress_contrib))

    total = syllable_contrib + cluster_contrib + balance_contrib + stress_contrib
    scaled = _clamp(total * 1.3 + 0.2, 0.0, 1.0)

    return scaled, contributions


def _compute_duration(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute DURATION dimension: Brief to Sustained.

    High duration: long vowels, many syllables, diphthongs
    Low duration: short vowels, few syllables
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # More syllables = longer duration (weight: 0.40)
    syllable_score = min(signals.syllable_count / 4.0, 1.0)
    syllable_contrib = syllable_score * 0.40
    contributions.append(("duration", "syllable_count", syllable_contrib))

    # Higher vowel ratio = longer (weight: 0.30)
    vowel_contrib = signals.vowel_consonant_ratio * 0.30
    contributions.append(("duration", "vowel_ratio", vowel_contrib))

    # Liquid/nasal presence extends duration (weight: 0.30)
    resonant_ratio = (signals.liquid_count + signals.nasal_count) / total_phonemes
    resonant_contrib = resonant_ratio * 0.30
    contributions.append(("duration", "resonant_ratio", resonant_contrib))

    total = syllable_contrib + vowel_contrib + resonant_contrib
    scaled = _clamp(total * 1.5 + 0.1, 0.0, 1.0)

    return scaled, contributions


def _compute_initiation(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute INITIATION dimension: Gradual to Explosive.

    High initiation: plosive start, consonant cluster onset
    Low initiation: vowel start, glide start
    """
    contributions = []

    # Initial plosive = explosive (weight: 0.40)
    initial_plosive = 1.0 if signals.initial_category == "plosive" else 0.0
    plosive_contrib = initial_plosive * 0.40
    contributions.append(("initiation", "initial_plosive", plosive_contrib))

    # Onset cluster size (weight: 0.30)
    onset_score = min(signals.onset_cluster_size / 2.0, 1.0)
    onset_contrib = onset_score * 0.30
    contributions.append(("initiation", "onset_cluster", onset_contrib))

    # Fricative start = moderate (weight: 0.15)
    initial_fric = 0.7 if signals.initial_category == "fricative" else 0.0
    fric_contrib = initial_fric * 0.15
    contributions.append(("initiation", "initial_fricative", fric_contrib))

    # Vowel start = gradual (inverted, weight: 0.15)
    initial_vowel = 0.2 if signals.initial_category == "vowel" else 0.5
    vowel_contrib = initial_vowel * 0.15
    contributions.append(("initiation", "initial_vowel_inv", vowel_contrib))

    total = plosive_contrib + onset_contrib + fric_contrib + vowel_contrib
    scaled = _clamp(total * 1.4 + 0.2, 0.0, 1.0)

    return scaled, contributions


def _compute_flow(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute FLOW dimension: Interrupted to Continuous.

    High flow: liquids, nasals, glides
    Low flow: plosives, consonant clusters
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Liquid ratio promotes flow (weight: 0.35)
    liquid_ratio = signals.liquid_count / total_phonemes
    liquid_contrib = liquid_ratio * 0.35
    contributions.append(("flow", "liquid_ratio", liquid_contrib))

    # Nasal ratio promotes flow (weight: 0.30)
    nasal_ratio = signals.nasal_count / total_phonemes
    nasal_contrib = nasal_ratio * 0.30
    contributions.append(("flow", "nasal_ratio", nasal_contrib))

    # Glide ratio promotes flow (weight: 0.20)
    glide_ratio = signals.glide_count / total_phonemes
    glide_contrib = glide_ratio * 0.20
    contributions.append(("flow", "glide_ratio", glide_contrib))

    # Plosive clusters interrupt flow (negative, weight: -0.15)
    cluster_penalty = (signals.onset_cluster_size + signals.coda_cluster_size) / 4.0
    cluster_contrib = -cluster_penalty * 0.15
    contributions.append(("flow", "cluster_penalty", cluster_contrib))

    total = liquid_contrib + nasal_contrib + glide_contrib + cluster_contrib
    scaled = _clamp(total * 2.0 + 0.4, 0.0, 1.0)

    return scaled, contributions


def _compute_termination(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute TERMINATION dimension: Fading to Abrupt.

    High termination: plosive end, consonant cluster coda
    Low termination: vowel end, liquid end
    """
    contributions = []

    # Final plosive = abrupt (weight: 0.40)
    final_plosive = 1.0 if signals.final_category == "plosive" else 0.0
    plosive_contrib = final_plosive * 0.40
    contributions.append(("termination", "final_plosive", plosive_contrib))

    # Coda cluster = abrupt (weight: 0.30)
    coda_score = min(signals.coda_cluster_size / 2.0, 1.0)
    coda_contrib = coda_score * 0.30
    contributions.append(("termination", "coda_cluster", coda_contrib))

    # Final fricative = moderate (weight: 0.15)
    final_fric = 0.6 if signals.final_category == "fricative" else 0.0
    fric_contrib = final_fric * 0.15
    contributions.append(("termination", "final_fricative", fric_contrib))

    # Vowel/liquid end = fading (inverted, weight: 0.15)
    soft_end = 0.2 if signals.final_category in ("vowel", "liquid") else 0.5
    soft_contrib = soft_end * 0.15
    contributions.append(("termination", "soft_ending_inv", soft_contrib))

    total = plosive_contrib + coda_contrib + fric_contrib + soft_contrib
    scaled = _clamp(total * 1.3 + 0.15, 0.0, 1.0)

    return scaled, contributions


def _compute_complexity(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute COMPLEXITY dimension: Simple to Complex.

    High complexity: many unique phonemes, varied structure
    Low complexity: repetitive, simple patterns
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Unique phoneme ratio (weight: 0.40)
    unique_phonemes = len(set(signals.phoneme_sequence))
    unique_ratio = unique_phonemes / total_phonemes
    unique_contrib = unique_ratio * 0.40
    contributions.append(("complexity", "unique_ratio", unique_contrib))

    # Phoneme count (more = complex) (weight: 0.30)
    phoneme_score = min(total_phonemes / 8.0, 1.0)
    phoneme_contrib = phoneme_score * 0.30
    contributions.append(("complexity", "phoneme_count", phoneme_contrib))

    # Category variety (weight: 0.30)
    unique_categories = len(set(signals.phoneme_categories))
    category_score = min(unique_categories / 5.0, 1.0)
    category_contrib = category_score * 0.30
    contributions.append(("complexity", "category_variety", category_contrib))

    total = unique_contrib + phoneme_contrib + category_contrib
    scaled = _clamp(total * 1.2 + 0.1, 0.0, 1.0)

    return scaled, contributions


def _compute_density(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute DENSITY dimension: Sparse to Dense.

    High density: consonant-heavy, clusters
    Low density: vowel-heavy, open syllables
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Consonant ratio (weight: 0.45)
    consonant_ratio = 1.0 - signals.vowel_consonant_ratio
    consonant_contrib = consonant_ratio * 0.45
    contributions.append(("density", "consonant_ratio", consonant_contrib))

    # Cluster count (weight: 0.30)
    cluster_score = (signals.onset_cluster_size + signals.coda_cluster_size) / 4.0
    cluster_contrib = min(cluster_score, 1.0) * 0.30
    contributions.append(("density", "cluster_density", cluster_contrib))

    # Phonemes per syllable (weight: 0.25)
    phonemes_per_syllable = total_phonemes / max(signals.syllable_count, 1)
    density_score = min(phonemes_per_syllable / 4.0, 1.0)
    density_contrib = density_score * 0.25
    contributions.append(("density", "phonemes_per_syllable", density_contrib))

    total = consonant_contrib + cluster_contrib + density_contrib
    scaled = _clamp(total * 1.2 + 0.2, 0.0, 1.0)

    return scaled, contributions


def _compute_balance(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute BALANCE dimension: Asymmetric to Symmetric.

    High balance: even syllable structure, regular patterns
    Low balance: uneven, lopsided
    """
    contributions = []

    # Syllable count symmetry (2 or 4 = most balanced) (weight: 0.35)
    if signals.syllable_count in (2, 4):
        syllable_sym = 1.0
    elif signals.syllable_count == 3:
        syllable_sym = 0.7
    else:
        syllable_sym = 0.5
    syllable_contrib = syllable_sym * 0.35
    contributions.append(("balance", "syllable_symmetry", syllable_contrib))

    # Onset/coda similarity (weight: 0.30)
    onset_coda_diff = abs(signals.onset_cluster_size - signals.coda_cluster_size)
    edge_balance = 1.0 - min(onset_coda_diff / 2.0, 1.0)
    edge_contrib = edge_balance * 0.30
    contributions.append(("balance", "edge_balance", edge_contrib))

    # Vowel/consonant balance (around 0.4 vowels is ideal) (weight: 0.35)
    vc_balance = 1.0 - abs(signals.vowel_consonant_ratio - 0.4) * 2.5
    vc_contrib = max(0.0, vc_balance) * 0.35
    contributions.append(("balance", "vc_balance", vc_contrib))

    total = syllable_contrib + edge_contrib + vc_contrib
    scaled = _clamp(total * 1.2 + 0.2, 0.0, 1.0)

    return scaled, contributions


def _compute_openness(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute OPENNESS dimension: Closed to Open.

    High openness: vowel-rich, vowel endings
    Low openness: consonant-rich, consonant endings
    """
    contributions = []

    # Vowel ratio (weight: 0.45)
    vowel_contrib = signals.vowel_consonant_ratio * 0.45
    contributions.append(("openness", "vowel_ratio", vowel_contrib))

    # Final vowel (weight: 0.30)
    final_vowel = 1.0 if signals.final_category == "vowel" else 0.0
    final_contrib = final_vowel * 0.30
    contributions.append(("openness", "final_vowel", final_contrib))

    # Low density = more open (weight: 0.25)
    total_phonemes = len(signals.phoneme_sequence)
    if total_phonemes > 0:
        open_structure = 1.0 - (signals.plosive_count / total_phonemes)
    else:
        open_structure = 0.5
    open_contrib = open_structure * 0.25
    contributions.append(("openness", "open_structure", open_contrib))

    total = vowel_contrib + final_contrib + open_contrib
    scaled = _clamp(total * 1.3 + 0.15, 0.0, 1.0)

    return scaled, contributions


def _compute_depth(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute DEPTH dimension: Surface to Deep.

    High depth: back consonants (k, g), nasals, low vowels
    Low depth: front consonants (t, s), high vowels
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Back consonants (K, G, NG) add depth (weight: 0.35)
    back_consonants = sum(1 for p in signals.phoneme_sequence
                          if p.rstrip("012") in ("K", "G", "NG", "HH"))
    back_ratio = back_consonants / total_phonemes
    back_contrib = back_ratio * 0.35
    contributions.append(("depth", "back_consonants", back_contrib))

    # Nasals add resonant depth (weight: 0.35)
    nasal_ratio = signals.nasal_count / total_phonemes
    nasal_contrib = nasal_ratio * 0.35
    contributions.append(("depth", "nasal_depth", nasal_contrib))

    # Low vowels (AA, AO, AH) add depth (weight: 0.30)
    low_vowels = sum(1 for p in signals.phoneme_sequence
                     if p.rstrip("012") in ("AA", "AO", "AH", "AW"))
    low_ratio = low_vowels / total_phonemes
    low_contrib = low_ratio * 0.30
    contributions.append(("depth", "low_vowels", low_contrib))

    total = back_contrib + nasal_contrib + low_contrib
    scaled = _clamp(total * 2.0 + 0.35, 0.0, 1.0)

    return scaled, contributions


def _compute_connectivity(signals: ExtractedSignals) -> Tuple[float, List[Tuple[str, str, float]]]:
    """
    Compute CONNECTIVITY dimension: Isolated to Connected.

    High connectivity: nasals (M, N), liquids (L, R), glides (W, Y)
    Low connectivity: plosives, isolated sounds
    """
    contributions = []
    total_phonemes = len(signals.phoneme_sequence)

    if total_phonemes == 0:
        return 0.5, []

    # Nasal ratio (M, N connect) (weight: 0.40)
    nasal_ratio = signals.nasal_count / total_phonemes
    nasal_contrib = nasal_ratio * 0.40
    contributions.append(("connectivity", "nasal_ratio", nasal_contrib))

    # Liquid ratio (L, R flow) (weight: 0.35)
    liquid_ratio = signals.liquid_count / total_phonemes
    liquid_contrib = liquid_ratio * 0.35
    contributions.append(("connectivity", "liquid_ratio", liquid_contrib))

    # Glide ratio (W, Y transition) (weight: 0.25)
    glide_ratio = signals.glide_count / total_phonemes
    glide_contrib = glide_ratio * 0.25
    contributions.append(("connectivity", "glide_ratio", glide_contrib))

    total = nasal_contrib + liquid_contrib + glide_contrib
    scaled = _clamp(total * 2.5 + 0.2, 0.0, 1.0)

    return scaled, contributions


# =============================================================================
# Main Projection Function
# =============================================================================

def project_to_structural_profile(signals: ExtractedSignals) -> StructuralProfile:
    """
    Project extracted signals to 12D structural profile.

    This is fully deterministic: same signals → same profile.

    Args:
        signals: ExtractedSignals from Layer 2

    Returns:
        StructuralProfile with all 12 dimensions
    """
    all_contributions: List[Tuple[str, str, float]] = []

    # Compute each dimension
    force, force_contrib = _compute_force(signals)
    all_contributions.extend(force_contrib)

    stability, stability_contrib = _compute_stability(signals)
    all_contributions.extend(stability_contrib)

    duration, duration_contrib = _compute_duration(signals)
    all_contributions.extend(duration_contrib)

    initiation, initiation_contrib = _compute_initiation(signals)
    all_contributions.extend(initiation_contrib)

    flow, flow_contrib = _compute_flow(signals)
    all_contributions.extend(flow_contrib)

    termination, termination_contrib = _compute_termination(signals)
    all_contributions.extend(termination_contrib)

    complexity, complexity_contrib = _compute_complexity(signals)
    all_contributions.extend(complexity_contrib)

    density, density_contrib = _compute_density(signals)
    all_contributions.extend(density_contrib)

    balance, balance_contrib = _compute_balance(signals)
    all_contributions.extend(balance_contrib)

    openness, openness_contrib = _compute_openness(signals)
    all_contributions.extend(openness_contrib)

    depth, depth_contrib = _compute_depth(signals)
    all_contributions.extend(depth_contrib)

    connectivity, connectivity_contrib = _compute_connectivity(signals)
    all_contributions.extend(connectivity_contrib)

    return StructuralProfile(
        force=force,
        stability=stability,
        duration=duration,
        initiation=initiation,
        flow=flow,
        termination=termination,
        complexity=complexity,
        density=density,
        balance=balance,
        openness=openness,
        depth=depth,
        connectivity=connectivity,
        signal_contributions=tuple(all_contributions),
    )
