"""
LSTB Phoneme CSR Bridge Benchmarks (V11.0)

Tests the CSR phoneme system as a SEMANTIC-EMOTIONAL ENCODER (data plane).

CSR extracts bottom-up signal from phoneme patterns:
    - Vrtti (mental propensity) pressure encoding
    - Emotional tendency / energy polarity
    - Aspect distribution probabilities across 12 resonance channels

CSR is NOT a governance layer. It is analogous to:
    - CNN extracting edges from images
    - Prosody models extracting affect
    - Feature extractors producing distributions for downstream reasoning

The ontological stack (control plane) may OBSERVE CSR output but is never
directly selected or routed by it. Signal != Governance.

Tests:
    1. Phoneme decomposition quality (ARPABET coverage, category distribution)
    2. 12D resonance profiles (emotional pressure, energy concentration, spread)
    3. Resonance scoring (harmonic/neutral/dissonant for FLOP pre-filtering)
    4. Articulatory-semantic discriminability (category separation in 12D space)
    5. Varna emotional pressure coherence (Sanskrit vrtti grounding validation)

CLI Usage::

    python train_hard_probes.py --test-csr-bridge
    python train_hard_probes.py --test-csr-bridge --csr-ablation

References:
    - csr_phoneme_provider.py (PHONEME_MAP_ARPABET — 12D affinities)
    - symbolu/resonance/varna_bridge.py (bridge_meaning vrtti pressures)
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md §6b
"""

import time
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# CSR imports
try:
    from csr_phoneme_provider import (
        CSREmbeddingProvider,
        CSRConfig,
        VarnaCSRBridge,
        PHONEME_MAP_ARPABET,
    )
    CSR_AVAILABLE = True
except ImportError:
    CSR_AVAILABLE = False
    PHONEME_MAP_ARPABET = None


# =============================================================================
# CSR RESONANCE DIMENSIONS (12 semantic-emotional channels)
# =============================================================================
# These are FEATURE ENCODING channels, not governance axes.
# CSR produces aspect distribution probabilities across these channels.
# The ontological stack (control plane) may observe this distribution
# but CSR never routes or selects governance layers.

RESONANCE_DIM = 12


# =============================================================================
# PHONEME ARTICULATORY CATEGORIES
# =============================================================================
# Categorisation is by articulatory manner (how the sound is produced).
# Each category has a distinct SEMANTIC-EMOTIONAL signature:
#   Plosives   — forceful action energy, percussive pressure
#   Fricatives — controlled sustained energy, discriminating pressure
#   Nasals     — connective resonance, integrative flow
#   Liquids    — structural flow, adaptive shaping
#   Approximants — transitional glide, purposeful bridging
#   Vowels     — consciousness states, open vibrational field
#   Diphthongs — transformation energy, directional transition
#   Affricates — compound boundary-setting force

PHONEME_CATEGORIES = {
    'plosive': {
        'phonemes': ['P', 'B', 'T', 'D', 'K', 'G'],
        'semantic_quality': 'forceful_action',
        'varna_pressures': ['hope', 'worry', 'action', 'attachment'],
    },
    'fricative': {
        'phonemes': ['F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'HH'],
        'semantic_quality': 'controlled_agency',
        'varna_pressures': ['material_greed', 'lust_confusion', 'escape', 'external_dharma'],
    },
    'affricate': {
        'phonemes': ['CH', 'JH'],
        'semantic_quality': 'boundary_force',
        'varna_pressures': ['conscience', 'ego'],
    },
    'nasal': {
        'phonemes': ['M', 'N', 'NG'],
        'semantic_quality': 'connective_resonance',
        'varna_pressures': ['indulgence', 'attachment', 'envy'],
    },
    'liquid': {
        'phonemes': ['L', 'R'],
        'semantic_quality': 'structural_flow',
        'varna_pressures': ['cruelty', 'destruction'],
    },
    'approximant': {
        'phonemes': ['W', 'Y'],
        'semantic_quality': 'transitional_glide',
        'varna_pressures': ['distrust'],
    },
    'short_vowel': {
        'phonemes': ['AE', 'AH', 'EH', 'IH', 'UH'],
        'semantic_quality': 'grounding_awareness',
        'varna_states': ['birth_of_cognition', 'self_doing', 'contraction_focus'],
    },
    'long_vowel': {
        'phonemes': ['AA', 'AO', 'IY', 'UW', 'ER'],
        'semantic_quality': 'sustained_consciousness',
        'varna_states': ['expansion_continuity', 'specialized_identity', 'sustained_hold'],
    },
    'diphthong': {
        'phonemes': ['AY', 'AW', 'OY', 'EY', 'OW'],
        'semantic_quality': 'transformation_energy',
        'varna_states': ['integrative_understanding', 'surrender_transition', 'closure_completion'],
    },
}


# =============================================================================
# LOCAL 12D RESONANCE TABLE (fallback when csr_phoneme_provider not available)
# =============================================================================
# These are Sanskrit-calibrated 12D semantic-emotional resonance vectors
# from PHONEME_MAP_ARPABET. Each dimension is a resonance channel encoding
# aspect distribution — NOT an ontological governance axis.

LOCAL_PHONEME_12D = {
    # Vowels — consciousness states, open vibrational fields
    'AA': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],  # primordial potential
    'AH': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],  # birth of cognition
    'AE': [0.7, 0.4, 0.2, 0.2, 0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.2, 0.1],
    'IH': [0.2, 0.9, 0.4, 0.2, 0.3, 0.2, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],  # I-ness / self_doing
    'IY': [0.1, 0.6, 0.3, 0.9, 0.2, 0.2, 0.3, 0.2, 0.2, 0.3, 0.2, 0.2],  # specialized identity
    'UH': [0.1, 0.2, 0.2, 0.3, 0.9, 0.3, 0.1, 0.2, 0.4, 0.7, 0.3, 0.2],  # contraction / cohesion
    'UW': [0.1, 0.1, 0.1, 0.2, 0.4, 0.8, 0.2, 0.3, 0.5, 0.9, 0.4, 0.4],  # sustained hold / deep unity
    'EH': [0.1, 0.2, 0.7, 0.3, 0.4, 0.3, 0.8, 0.4, 0.2, 0.3, 0.3, 0.2],  # intellect / aspiration
    'ER': [0.2, 0.3, 0.5, 0.4, 0.4, 0.4, 0.6, 0.4, 0.3, 0.4, 0.3, 0.3],
    'EY': [0.1, 0.1, 0.3, 0.2, 0.3, 0.4, 0.5, 0.9, 0.4, 0.5, 0.4, 0.3],  # soul intention / wisdom
    'AY': [0.2, 0.2, 0.4, 0.2, 0.3, 0.4, 0.4, 0.8, 0.4, 0.5, 0.4, 0.3],
    'OW': [0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.4, 0.5, 0.9, 0.6, 0.8, 0.5],  # observer / completion
    'AO': [0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4, 0.5, 0.8, 0.6, 0.7, 0.5],
    'OY': [0.2, 0.2, 0.3, 0.2, 0.3, 0.3, 0.4, 0.6, 0.8, 0.5, 0.7, 0.5],
    'AW': [0.1, 0.1, 0.2, 0.1, 0.2, 0.3, 0.3, 0.6, 0.7, 0.4, 0.6, 0.9],  # transformation / surrender
    # Plosives — forceful action, percussive pressure
    'P':  [0.0, 0.2, 0.8, 0.4, 0.1, 0.5, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'T':  [0.0, 0.2, 0.9, 0.5, 0.1, 0.6, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'K':  [0.0, 0.2, 0.9, 0.4, 0.1, 0.5, 0.3, 0.1, 0.1, 0.1, 0.1, 0.0],
    'B':  [0.1, 0.3, 0.7, 0.4, 0.2, 0.4, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'D':  [0.1, 0.3, 0.8, 0.5, 0.2, 0.5, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'G':  [0.1, 0.3, 0.8, 0.4, 0.2, 0.4, 0.3, 0.1, 0.1, 0.2, 0.1, 0.1],
    # Fricatives — controlled sustained energy, discriminating pressure
    'F':  [0.0, 0.2, 0.3, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'TH': [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'S':  [0.0, 0.3, 0.3, 0.4, 0.3, 0.9, 0.6, 0.4, 0.2, 0.2, 0.2, 0.1],
    'SH': [0.0, 0.2, 0.3, 0.5, 0.3, 0.8, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'HH': [0.4, 0.2, 0.2, 0.3, 0.2, 0.5, 0.3, 0.3, 0.2, 0.3, 0.4, 0.5],
    'V':  [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.7, 0.4, 0.3, 0.3, 0.2, 0.1],
    'DH': [0.1, 0.2, 0.4, 0.4, 0.3, 0.7, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'Z':  [0.0, 0.3, 0.4, 0.4, 0.3, 0.8, 0.6, 0.4, 0.2, 0.3, 0.2, 0.1],
    'ZH': [0.0, 0.2, 0.4, 0.5, 0.3, 0.7, 0.6, 0.4, 0.3, 0.4, 0.3, 0.2],
    # Affricates — compound boundary force (plosive + fricative blend)
    'CH': [0.0, 0.2, 0.7, 0.5, 0.2, 0.7, 0.4, 0.2, 0.2, 0.2, 0.2, 0.1],
    'JH': [0.1, 0.3, 0.6, 0.5, 0.2, 0.6, 0.5, 0.3, 0.2, 0.3, 0.2, 0.1],
    # Nasals — connective resonance, integrative flow
    'M':  [0.3, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.4, 0.3],
    'N':  [0.2, 0.3, 0.2, 0.2, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 0.5, 0.3],
    'NG': [0.2, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.5, 0.4],
    # Liquids — structural flow, adaptive shaping
    'L':  [0.1, 0.2, 0.2, 0.9, 0.3, 0.3, 0.3, 0.4, 0.3, 0.6, 0.5, 0.4],
    'R':  [0.1, 0.2, 0.7, 0.5, 0.4, 0.4, 0.3, 0.3, 0.3, 0.5, 0.4, 0.4],
    # Approximants — transitional glide, purposeful bridging
    'W':  [0.2, 0.2, 0.2, 0.3, 0.4, 0.4, 0.5, 0.6, 0.4, 0.6, 0.5, 0.4],
    'Y':  [0.2, 0.3, 0.3, 0.4, 0.3, 0.4, 0.6, 0.6, 0.4, 0.5, 0.4, 0.3],
}


def get_phoneme_resonance(phoneme: str) -> List[float]:
    """Get 12D resonance vector for a phoneme (real CSR map or local fallback)."""
    ph = phoneme.rstrip('012')  # Strip stress markers
    if PHONEME_MAP_ARPABET is not None and ph in PHONEME_MAP_ARPABET:
        return PHONEME_MAP_ARPABET[ph]
    if ph in LOCAL_PHONEME_12D:
        return LOCAL_PHONEME_12D[ph]
    return [0.33] * RESONANCE_DIM  # Unknown: uniform low activation


# =============================================================================
# LOCAL PHONEME IMPLEMENTATION (when csr_phoneme_provider not available)
# =============================================================================

SIMPLE_G2P = {
    'the': ['DH', 'AH'], 'cat': ['K', 'AE', 'T'], 'sat': ['S', 'AE', 'T'],
    'on': ['AA', 'N'], 'mat': ['M', 'AE', 'T'], 'dog': ['D', 'AO', 'G'],
    'and': ['AE', 'N', 'D'], 'looked': ['L', 'UH', 'K', 'T'],
    'at': ['AE', 'T'], 'ran': ['R', 'AE', 'N'], 'fast': ['F', 'AE', 'S', 'T'],
    'big': ['B', 'IH', 'G'], 'small': ['S', 'M', 'AO', 'L'],
    'think': ['TH', 'IH', 'NG', 'K'], 'know': ['N', 'OW'],
    'beautiful': ['B', 'Y', 'UW', 'T', 'AH', 'F', 'AH', 'L'],
    'science': ['S', 'AY', 'AH', 'N', 'S'], 'music': ['M', 'Y', 'UW', 'Z', 'IH', 'K'],
    'running': ['R', 'AH', 'N', 'IH', 'NG'], 'jumping': ['JH', 'AH', 'M', 'P', 'IH', 'NG'],
    'quickly': ['K', 'W', 'IH', 'K', 'L', 'IY'],
}


def simple_text_to_phonemes(text: str) -> List[str]:
    """Simple word-level phoneme lookup."""
    phonemes = []
    for word in text.lower().split():
        word_clean = ''.join(c for c in word if c.isalpha())
        if word_clean in SIMPLE_G2P:
            phonemes.extend(SIMPLE_G2P[word_clean])
        else:
            for ch in word_clean:
                if ch in 'aeiou':
                    phonemes.append('AH')
                elif ch in 'bpdtkg':
                    phonemes.append(ch.upper())
                elif ch in 'mnl':
                    phonemes.append(ch.upper())
                elif ch in 'szf':
                    phonemes.append(ch.upper())
                elif ch == 'r':
                    phonemes.append('R')
                else:
                    phonemes.append('AH')
    return phonemes


def classify_phoneme(ph: str) -> str:
    """Classify phoneme into articulatory category."""
    ph_clean = ph.rstrip('012')
    for category, info in PHONEME_CATEGORIES.items():
        if ph_clean in info['phonemes']:
            return category
    return 'unknown'


def phonemes_to_resonance(phonemes: List[str]) -> torch.Tensor:
    """
    Convert phoneme sequence to 12D semantic-emotional resonance vector.

    Mean-aggregates per-phoneme 12D resonance vectors (Sanskrit-calibrated).
    The result is an aspect distribution across 12 resonance channels —
    a feature encoding, not a governance signal.
    """
    if not phonemes:
        return torch.zeros(RESONANCE_DIM)

    vectors = []
    for ph in phonemes:
        vec = get_phoneme_resonance(ph)
        vectors.append(torch.tensor(vec, dtype=torch.float32))

    return torch.stack(vectors).mean(dim=0)


# =============================================================================
# RESONANCE PROFILE METRICS (semantic-emotional properties)
# =============================================================================

def resonance_energy(vec: torch.Tensor) -> float:
    """Total resonance energy: mean activation across all channels."""
    return vec.mean().item()


def resonance_peak(vec: torch.Tensor) -> float:
    """Peak resonance: maximum activation in any single channel."""
    return vec.max().item()


def resonance_spread(vec: torch.Tensor, threshold: float = 0.3) -> float:
    """Resonance spread: fraction of channels activated above threshold.
    High spread = distributed emotional energy (vowels, nasals).
    Low spread = concentrated pressure (plosives)."""
    return (vec > threshold).sum().item() / RESONANCE_DIM


def energy_concentration(vec: torch.Tensor) -> float:
    """How concentrated the energy is in few channels (inverse of entropy).
    High = percussive/focused pressure. Low = diffuse/open resonance."""
    # Normalise to distribution
    p = F.softmax(vec, dim=0)
    entropy = -(p * p.log()).sum().item()
    max_entropy = math.log(RESONANCE_DIM)
    return 1.0 - (entropy / max_entropy)  # 0=uniform, 1=single-channel


def compute_resonance_score(vec: torch.Tensor) -> float:
    """
    Compute resonance score for FLOP pre-filtering.

    Score interpretation (from LSTB §6b):
        >= 0.7: Harmonic (proceed to transformer)
        0.3-0.7: Neutral (route to decision gate)
        <= 0.3: Dissonant (resolve locally, skip transformer)

    This is a data-plane signal for the decision gate.
    The ontological stack may observe this score but CSR does NOT
    route governance — the decision gate does.
    """
    energy = resonance_energy(vec)
    peak = resonance_peak(vec)
    spread = resonance_spread(vec)

    score = 0.4 * energy + 0.3 * peak + 0.3 * spread
    return max(0.0, min(1.0, score))


# =============================================================================
# TEST 1: PHONEME DECOMPOSITION QUALITY
# =============================================================================

def test_phoneme_decomposition(device: torch.device) -> Dict[str, float]:
    """Test phoneme decomposition coverage and correctness."""
    test_texts = [
        "The cat sat on the mat",
        "Scientists discovered a new species",
        "She played the piano beautifully",
        "Running quickly through the forest",
        "Think about the beautiful music",
    ]

    results = {}
    total_words = 0
    total_phonemes = 0
    total_classified = 0
    category_counts = {}

    for text in test_texts:
        phonemes = simple_text_to_phonemes(text)
        total_words += len(text.split())
        total_phonemes += len(phonemes)

        for ph in phonemes:
            cat = classify_phoneme(ph)
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if cat != 'unknown':
                total_classified += 1

    results['total_words'] = total_words
    results['total_phonemes'] = total_phonemes
    results['classification_rate'] = total_classified / max(total_phonemes, 1)
    results['phonemes_per_word'] = total_phonemes / max(total_words, 1)

    for cat in ['plosive', 'fricative', 'nasal', 'liquid',
                'short_vowel', 'long_vowel', 'diphthong', 'approximant', 'affricate']:
        results[f'pct_{cat}'] = category_counts.get(cat, 0) / max(total_phonemes, 1)

    return results


# =============================================================================
# TEST 2: SEMANTIC-EMOTIONAL RESONANCE PROFILES
# =============================================================================

def test_resonance_profiles(device: torch.device) -> Dict[str, float]:
    """
    Test that 12D resonance vectors encode correct semantic-emotional properties.

    Validates the CSR feature encoder's output characteristics:
        - Plosives: concentrated pressure, low spread (percussive force)
        - Vowels: high energy, high spread (open vibrational field)
        - Nasals: high spread, connective resonance (integrative flow)
        - Fricatives: moderate concentration, sustained energy (controlled agency)

    These are SIGNAL properties, not governance signals.
    """
    test_profiles = {
        'plosive_heavy': ['K', 'T', 'P', 'B', 'D', 'G', 'K', 'T'],
        'nasal_heavy': ['M', 'N', 'NG', 'M', 'N', 'M', 'N', 'NG'],
        'vowel_heavy': ['AA', 'IY', 'UW', 'AO', 'EY', 'OW', 'AY', 'AW'],
        'fricative_heavy': ['S', 'Z', 'F', 'V', 'TH', 'SH', 'S', 'Z'],
        'mixed': ['K', 'AE', 'T', 'S', 'AE', 'T', 'M', 'AE', 'T'],
    }

    results = {}

    for name, phonemes in test_profiles.items():
        vec = phonemes_to_resonance(phonemes)
        results[f'{name}_energy'] = resonance_energy(vec)
        results[f'{name}_peak'] = resonance_peak(vec)
        results[f'{name}_spread'] = resonance_spread(vec)
        results[f'{name}_concentration'] = energy_concentration(vec)
        results[f'{name}_score'] = compute_resonance_score(vec)

    # --- Semantic-emotional structural assertions ---

    # Vowels have higher resonance energy than plosives (open vs percussive)
    results['vowel_energy_gt_plosive'] = (
        results['vowel_heavy_energy'] > results['plosive_heavy_energy']
    )

    # Vowels have higher spread than plosives (distributed vs concentrated)
    results['vowel_spread_gt_plosive'] = (
        results['vowel_heavy_spread'] > results['plosive_heavy_spread']
    )

    # Plosives have higher concentration than vowels (focused pressure)
    results['plosive_more_concentrated'] = (
        results['plosive_heavy_concentration'] > results['vowel_heavy_concentration']
    )

    # Nasals have higher spread than plosives (connective vs percussive)
    results['nasal_spread_gt_plosive'] = (
        results['nasal_heavy_spread'] > results['plosive_heavy_spread']
    )

    # Fricatives have higher energy than plosives (sustained vs burst)
    results['fricative_energy_gt_plosive'] = (
        results['fricative_heavy_energy'] > results['plosive_heavy_energy']
    )

    return results


# =============================================================================
# TEST 3: FLOP REDUCTION VIA RESONANCE PRE-FILTERING
# =============================================================================

def test_flop_reduction(device: torch.device) -> Dict[str, float]:
    """
    Test FLOP savings from resonance-based candidate pre-filtering.

    CSR resonance scoring is a DATA-PLANE signal that the decision gate
    uses to prune candidates BEFORE the transformer processes them.
    This is constraint elimination, not governance.
    """
    import random
    random.seed(42)

    all_phonemes = []
    for info in PHONEME_CATEGORIES.values():
        all_phonemes.extend(info['phonemes'])

    n_candidates = 1000
    scores = []

    for _ in range(n_candidates):
        length = random.randint(2, 8)
        phonemes = random.choices(all_phonemes, k=length)
        vec = phonemes_to_resonance(phonemes)
        score = compute_resonance_score(vec)
        scores.append(score)

    scores_t = torch.tensor(scores)

    results = {}
    results['n_candidates'] = n_candidates

    harmonic = (scores_t >= 0.7).sum().item()
    neutral = ((scores_t >= 0.3) & (scores_t < 0.7)).sum().item()
    dissonant = (scores_t < 0.3).sum().item()

    results['pct_harmonic'] = harmonic / n_candidates
    results['pct_neutral'] = neutral / n_candidates
    results['pct_dissonant'] = dissonant / n_candidates
    results['flop_reduction_dissonant'] = dissonant / n_candidates
    results['flop_reduction_estimated'] = (dissonant + neutral * 0.5) / n_candidates
    results['mean_score'] = scores_t.mean().item()
    results['std_score'] = scores_t.std().item()

    return results


# =============================================================================
# TEST 4: ARTICULATORY-SEMANTIC DISCRIMINABILITY
# =============================================================================

def test_discriminability(device: torch.device) -> Dict[str, float]:
    """
    Test that different articulatory categories produce DISTINGUISHABLE
    12D resonance signatures.

    A good semantic-emotional encoder should separate categories:
        - Within-category similarity should be HIGH (coherent signal)
        - Between-category similarity should be LOWER (distinct signals)

    This validates that CSR extracts meaningful features, not noise.
    """
    # Build resonance vectors for each phoneme
    category_vectors = {}
    for cat_name, info in PHONEME_CATEGORIES.items():
        vecs = []
        for ph in info['phonemes']:
            vec = torch.tensor(get_phoneme_resonance(ph), dtype=torch.float32)
            vecs.append(vec)
        if vecs:
            category_vectors[cat_name] = torch.stack(vecs)

    results = {}

    # Within-category mean cosine similarity
    within_sims = []
    for cat_name, vecs in category_vectors.items():
        if vecs.shape[0] < 2:
            continue
        # Pairwise cosine similarity
        norms = F.normalize(vecs, dim=1)
        sim_matrix = norms @ norms.T
        # Upper triangle (exclude diagonal)
        n = sim_matrix.shape[0]
        mask = torch.triu(torch.ones(n, n, dtype=torch.bool), diagonal=1)
        pairwise = sim_matrix[mask]
        mean_sim = pairwise.mean().item()
        results[f'{cat_name}_within_sim'] = mean_sim
        within_sims.append(mean_sim)

    # Between-category mean cosine similarity
    between_sims = []
    cat_names = list(category_vectors.keys())
    for i in range(len(cat_names)):
        for j in range(i + 1, len(cat_names)):
            vecs_a = F.normalize(category_vectors[cat_names[i]], dim=1)
            vecs_b = F.normalize(category_vectors[cat_names[j]], dim=1)
            cross_sim = (vecs_a @ vecs_b.T).mean().item()
            between_sims.append(cross_sim)

    results['mean_within_similarity'] = sum(within_sims) / max(len(within_sims), 1)
    results['mean_between_similarity'] = sum(between_sims) / max(len(between_sims), 1)

    # Discriminability ratio: within / between > 1 means categories are separable
    if results['mean_between_similarity'] > 0:
        results['discriminability_ratio'] = (
            results['mean_within_similarity'] / results['mean_between_similarity']
        )
    else:
        results['discriminability_ratio'] = float('inf')

    # Categories are separable if within-category > between-category
    results['categories_separable'] = (
        results['mean_within_similarity'] > results['mean_between_similarity']
    )

    return results


# =============================================================================
# TEST 5: VARNA EMOTIONAL PRESSURE COHERENCE
# =============================================================================

def test_varna_pressure_coherence(device: torch.device) -> Dict[str, float]:
    """
    Test that resonance profiles match Sanskrit varna emotional pressures.

    The varna bridge maps consonants to vrtti (mental propensity) pressures:
        ka → hope_pressure    (forward-seeking)
        pha → fear_pressure   (contraction)
        ra → destruction_pressure (decomposition)
        ma → indulgence_pressure  (saturation)

    Vowels map to states of consciousness:
        a → birth_of_cognition   (primordial potential)
        o → closure_completion   (observer / witness)
        au → surrender_transition (transformation)

    This test validates that the 12D resonance vectors correctly encode
    these EMOTIONAL qualities — distinct pressure profiles for each
    articulatory manner.
    """
    results = {}

    # --- Emotional pressure ordering (from Sanskrit acoustic tradition) ---

    # 1. Plosives = HIGH pressure, LOW openness
    #    Vowels = LOW pressure, HIGH openness
    plosive_vec = phonemes_to_resonance(['K', 'T', 'P', 'B', 'D', 'G'])
    vowel_vec = phonemes_to_resonance(['AA', 'IY', 'UW', 'AO', 'EY', 'OW'])

    results['plosive_concentration'] = energy_concentration(plosive_vec)
    results['vowel_concentration'] = energy_concentration(vowel_vec)
    results['pressure_vs_openness'] = (
        energy_concentration(plosive_vec) > energy_concentration(vowel_vec)
    )

    # 2. Nasals = connective (high spread, smooth distribution)
    #    Plosives = percussive (concentrated, sharp distribution)
    nasal_vec = phonemes_to_resonance(['M', 'N', 'NG'])
    results['nasal_spread'] = resonance_spread(nasal_vec)
    results['plosive_spread'] = resonance_spread(plosive_vec)
    results['nasal_more_connective'] = (
        resonance_spread(nasal_vec) > resonance_spread(plosive_vec)
    )

    # 3. Diphthongs = transitional energy (moderate spread + high peak)
    #    indicating directional transformation, not static state
    diphthong_vec = phonemes_to_resonance(['AY', 'AW', 'OY', 'EY', 'OW'])
    short_vowel_vec = phonemes_to_resonance(['AE', 'AH', 'IH', 'UH', 'EH'])

    results['diphthong_energy'] = resonance_energy(diphthong_vec)
    results['short_vowel_energy'] = resonance_energy(short_vowel_vec)
    results['diphthong_higher_energy'] = (
        resonance_energy(diphthong_vec) > resonance_energy(short_vowel_vec)
    )

    # 4. Fricatives = sustained controlled energy (moderate-high energy, moderate spread)
    fricative_vec = phonemes_to_resonance(['S', 'Z', 'F', 'V', 'TH', 'SH'])
    results['fricative_energy'] = resonance_energy(fricative_vec)
    results['fricative_spread'] = resonance_spread(fricative_vec)
    results['fricative_sustained'] = (
        resonance_energy(fricative_vec) > resonance_energy(plosive_vec)
    )

    # 5. Approximants = smooth bridging energy (high spread, moderate energy)
    approx_vec = phonemes_to_resonance(['W', 'Y'])
    results['approximant_energy'] = resonance_energy(approx_vec)
    results['approximant_spread'] = resonance_spread(approx_vec)
    results['approximant_high_spread'] = resonance_spread(approx_vec) > 0.5

    # Overall coherence: count how many emotional pressure orderings hold
    pressure_checks = [
        results['pressure_vs_openness'],
        results['nasal_more_connective'],
        results['diphthong_higher_energy'],
        results['fricative_sustained'],
        results['approximant_high_spread'],
    ]
    results['pressure_coherence'] = sum(pressure_checks) / len(pressure_checks)

    return results


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_csr_bridge_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """
    Run CSR phoneme semantic-emotional encoder benchmarks.

    Tests CSR as a DATA PLANE feature extractor:
        Signal properties, emotional pressure encoding, discriminability.
    Does NOT test governance routing or ontological layer activation.
    """
    print("\n" + "=" * 70)
    print("V11.0: PHONEME CSR BRIDGE — SEMANTIC-EMOTIONAL ENCODER BENCHMARKS")
    print("=" * 70)
    print("  CSR role: Semantic-emotional feature encoder (data plane)")
    print("  CSR is NOT a governance layer — Signal != Governance")

    if CSR_AVAILABLE:
        print("  CSR provider: AVAILABLE (using real PHONEME_MAP_ARPABET)")
    else:
        print("  CSR provider: NOT AVAILABLE (using local 12D fallback)")

    device = torch.device(device)
    results = {}

    # -------------------------------------------------------------------------
    # TEST 1: Phoneme Decomposition
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Phoneme Decomposition Quality ---")
    decomp_results = test_phoneme_decomposition(device)
    results['decomposition'] = decomp_results

    print(f"  Total words: {decomp_results['total_words']}")
    print(f"  Total phonemes: {decomp_results['total_phonemes']}")
    print(f"  Classification rate: {decomp_results['classification_rate']:.1%}")
    print(f"  Phonemes/word: {decomp_results['phonemes_per_word']:.1f}")
    for cat in ['plosive', 'fricative', 'nasal', 'liquid', 'short_vowel',
                'long_vowel', 'diphthong', 'approximant']:
        pct = decomp_results.get(f'pct_{cat}', 0)
        print(f"    {cat:15s}: {pct:.1%}")

    # -------------------------------------------------------------------------
    # TEST 2: Semantic-Emotional Resonance Profiles
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Semantic-Emotional Resonance Profiles ---")
    res_results = test_resonance_profiles(device)
    results['resonance_profiles'] = res_results

    for name in ['plosive_heavy', 'nasal_heavy', 'vowel_heavy', 'fricative_heavy', 'mixed']:
        energy = res_results[f'{name}_energy']
        spread = res_results[f'{name}_spread']
        conc = res_results[f'{name}_concentration']
        score = res_results[f'{name}_score']
        print(f"  {name:18s}: energy={energy:.3f} spread={spread:.2f} "
              f"concentration={conc:.3f} score={score:.3f}")

    print(f"  Vowel energy > plosive:     {res_results['vowel_energy_gt_plosive']}")
    print(f"  Vowel spread > plosive:     {res_results['vowel_spread_gt_plosive']}")
    print(f"  Plosive more concentrated:  {res_results['plosive_more_concentrated']}")
    print(f"  Nasal spread > plosive:     {res_results['nasal_spread_gt_plosive']}")
    print(f"  Fricative energy > plosive: {res_results['fricative_energy_gt_plosive']}")

    # -------------------------------------------------------------------------
    # TEST 3: FLOP Reduction
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: FLOP Reduction via Resonance Pre-filtering ---")
    flop_results = test_flop_reduction(device)
    results['flop_reduction'] = flop_results

    print(f"  Distribution ({flop_results['n_candidates']} candidates):")
    print(f"    Harmonic (>= 0.7):  {flop_results['pct_harmonic']:.1%}")
    print(f"    Neutral (0.3-0.7):  {flop_results['pct_neutral']:.1%}")
    print(f"    Dissonant (<0.3):   {flop_results['pct_dissonant']:.1%}")
    print(f"  Estimated FLOP reduction: {flop_results['flop_reduction_estimated']:.1%}")

    # -------------------------------------------------------------------------
    # TEST 4: Articulatory-Semantic Discriminability
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Articulatory-Semantic Discriminability ---")
    disc_results = test_discriminability(device)
    results['discriminability'] = disc_results

    print(f"  Within-category similarity:  {disc_results['mean_within_similarity']:.3f}")
    print(f"  Between-category similarity: {disc_results['mean_between_similarity']:.3f}")
    print(f"  Discriminability ratio:      {disc_results['discriminability_ratio']:.3f}")
    print(f"  Categories separable:        {disc_results['categories_separable']}")

    for cat in ['plosive', 'fricative', 'nasal', 'short_vowel', 'long_vowel', 'diphthong']:
        sim = disc_results.get(f'{cat}_within_sim', 0)
        print(f"    {cat:15s} within-sim: {sim:.3f}")

    # -------------------------------------------------------------------------
    # TEST 5: Varna Emotional Pressure Coherence
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Varna Emotional Pressure Coherence ---")
    varna_results = test_varna_pressure_coherence(device)
    results['varna_pressure'] = varna_results

    print(f"  Plosive concentration:  {varna_results['plosive_concentration']:.3f} (focused pressure)")
    print(f"  Vowel concentration:    {varna_results['vowel_concentration']:.3f} (open resonance)")
    print(f"  Pressure > openness:    {varna_results['pressure_vs_openness']}")
    print(f"  Nasal spread:           {varna_results['nasal_spread']:.2f} (connective)")
    print(f"  Plosive spread:         {varna_results['plosive_spread']:.2f} (percussive)")
    print(f"  Nasal more connective:  {varna_results['nasal_more_connective']}")
    print(f"  Diphthong > short vowel energy: {varna_results['diphthong_higher_energy']}")
    print(f"  Fricative sustained:    {varna_results['fricative_sustained']}")
    print(f"  Pressure coherence:     {varna_results['pressure_coherence']:.0%}")

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CSR SEMANTIC-EMOTIONAL ENCODER SUMMARY")
    print("=" * 70)
    print(f"  Classification rate:      {decomp_results['classification_rate']:.1%}")
    print(f"  Vowel > plosive energy:   {res_results['vowel_energy_gt_plosive']}")
    print(f"  Categories separable:     {disc_results['categories_separable']}")
    print(f"  Discriminability ratio:   {disc_results['discriminability_ratio']:.3f}")
    print(f"  Pressure coherence:       {varna_results['pressure_coherence']:.0%}")
    print(f"  FLOP reduction:           {flop_results['flop_reduction_estimated']:.1%}")
    print("  ---")
    print("  CSR = data plane signal. Ontology = control plane (separate).")

    return results


def run_csr_bridge_benchmark_integration(args, config):
    """CLI routing wrapper for CSR bridge benchmarks."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_csr_bridge_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
