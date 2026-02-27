"""
LSTB Phoneme CSR Bridge Benchmarks (V11.0)

Tests the Constant Shift Resonance phoneme grounding system:
    1. Phoneme decomposition quality (ARPABET coverage)
    2. 12D ontological affinity vector generation
    3. Resonance scoring (harmonic/neutral/dissonant distribution)
    4. Candidate pre-filtering FLOP reduction
    5. Ontological dimension activation (plosive->O3, nasal->O10, etc.)
    6. Cross-check with Sovereign State Bhava dimensions

The CSR system uses 12D vectors matching the 12 ontological axes:
    O1_POT, O2_ID, O3_EXE, O4_STR, O5_COG, O6_AGE,
    O7_REA, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS

CLI Usage::

    python train_hard_probes.py --test-csr-bridge
    python train_hard_probes.py --test-csr-bridge --csr-ablation

References:
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md §6b
    - csr_phoneme_provider.py (PHONEME_MAP_ARPABET, 12D affinities)
    - PHONEME_TRANSFORMER_HYBRID_ARCHITECTURE.md
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

# JEPA for cross-check
try:
    from symbolu.jepa.state_projector import SovereignStateProjector
    JEPA_AVAILABLE = True
except ImportError:
    JEPA_AVAILABLE = False


# =============================================================================
# 12D ONTOLOGICAL AXES (O1-O12)
# =============================================================================
# Order: O1_POT, O2_ID, O3_EXE, O4_STR, O5_COG, O6_AGE, O7_REA, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS

ONTO_AXIS_NAMES = [
    'O1_POTENTIAL', 'O2_IDENTITY', 'O3_EXECUTION', 'O4_STRUCTURE',
    'O5_COGNITION', 'O6_AGENCY', 'O7_REASONING', 'O8_PURPOSE',
    'O9_WITNESS', 'O10_UNIFYING', 'O11_INTEGRATION', 'O12_ABSOLVING',
]

ONTO_DIM = 12


# =============================================================================
# PHONEME ONTOLOGY MAPPING (from csr_phoneme_provider.py PHONEME_MAP_ARPABET)
# =============================================================================
# Corrected to match actual csr_phoneme_provider.py dominant axes:
#   Plosives   -> O3_EXECUTION dominant
#   Fricatives -> O6_AGENCY dominant
#   Nasals     -> O10_UNIFYING dominant
#   Liquids    -> O4_STRUCTURE dominant
#   Approximants -> O7_REASONING / O8_PURPOSE
#   Short vowels -> O1_POTENTIAL / O2_IDENTITY
#   Long vowels  -> varied (IY->O4, UW->O10, AA->O1)
#   Diphthongs   -> O8_PURPOSE / O9_WITNESS

PHONEME_ONTOLOGY_MAP = {
    'plosive': {
        'phonemes': ['P', 'B', 'T', 'D', 'K', 'G'],
        'primary_axis': 'O3_EXECUTION', 'axis_idx': 2,
    },
    'fricative': {
        'phonemes': ['F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'HH'],
        'primary_axis': 'O6_AGENCY', 'axis_idx': 5,
    },
    'affricate': {
        'phonemes': ['CH', 'JH'],
        'primary_axis': 'O3_EXECUTION', 'axis_idx': 2,  # O3+O6 blend
    },
    'nasal': {
        'phonemes': ['M', 'N', 'NG'],
        'primary_axis': 'O10_UNIFYING', 'axis_idx': 9,
    },
    'liquid': {
        'phonemes': ['L', 'R'],
        'primary_axis': 'O4_STRUCTURE', 'axis_idx': 3,
    },
    'approximant': {
        'phonemes': ['W', 'Y'],
        'primary_axis': 'O7_REASONING', 'axis_idx': 6,
    },
    'short_vowel': {
        'phonemes': ['AE', 'AH', 'EH', 'IH', 'UH'],
        'primary_axis': 'O1_POTENTIAL', 'axis_idx': 0,
    },
    'long_vowel': {
        'phonemes': ['AA', 'AO', 'IY', 'UW', 'ER'],
        'primary_axis': 'O1_POTENTIAL', 'axis_idx': 0,  # AA dominant at O1
    },
    'diphthong': {
        'phonemes': ['AY', 'AW', 'OY', 'EY', 'OW'],
        'primary_axis': 'O8_PURPOSE', 'axis_idx': 7,
    },
}


# =============================================================================
# LOCAL 12D AFFINITY TABLE (fallback when csr_phoneme_provider not available)
# =============================================================================
# Subset of PHONEME_MAP_ARPABET from csr_phoneme_provider.py
# Order: O1_POT, O2_ID, O3_EXE, O4_STR, O5_COG, O6_AGE, O7_REA, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS

LOCAL_PHONEME_12D = {
    # Vowels
    'AA': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],
    'AH': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],
    'AE': [0.7, 0.4, 0.2, 0.2, 0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.2, 0.1],
    'IH': [0.2, 0.9, 0.4, 0.2, 0.3, 0.2, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'IY': [0.1, 0.6, 0.3, 0.9, 0.2, 0.2, 0.3, 0.2, 0.2, 0.3, 0.2, 0.2],
    'UH': [0.1, 0.2, 0.2, 0.3, 0.9, 0.3, 0.1, 0.2, 0.4, 0.7, 0.3, 0.2],
    'UW': [0.1, 0.1, 0.1, 0.2, 0.4, 0.8, 0.2, 0.3, 0.5, 0.9, 0.4, 0.4],
    'EH': [0.1, 0.2, 0.7, 0.3, 0.4, 0.3, 0.8, 0.4, 0.2, 0.3, 0.3, 0.2],
    'ER': [0.2, 0.3, 0.5, 0.4, 0.4, 0.4, 0.6, 0.4, 0.3, 0.4, 0.3, 0.3],
    'EY': [0.1, 0.1, 0.3, 0.2, 0.3, 0.4, 0.5, 0.9, 0.4, 0.5, 0.4, 0.3],
    'AY': [0.2, 0.2, 0.4, 0.2, 0.3, 0.4, 0.4, 0.8, 0.4, 0.5, 0.4, 0.3],
    'OW': [0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.4, 0.5, 0.9, 0.6, 0.8, 0.5],
    'AO': [0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4, 0.5, 0.8, 0.6, 0.7, 0.5],
    'OY': [0.2, 0.2, 0.3, 0.2, 0.3, 0.3, 0.4, 0.6, 0.8, 0.5, 0.7, 0.5],
    'AW': [0.1, 0.1, 0.2, 0.1, 0.2, 0.3, 0.3, 0.6, 0.7, 0.4, 0.6, 0.9],
    # Plosives
    'P':  [0.0, 0.2, 0.8, 0.4, 0.1, 0.5, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'T':  [0.0, 0.2, 0.9, 0.5, 0.1, 0.6, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'K':  [0.0, 0.2, 0.9, 0.4, 0.1, 0.5, 0.3, 0.1, 0.1, 0.1, 0.1, 0.0],
    'B':  [0.1, 0.3, 0.7, 0.4, 0.2, 0.4, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'D':  [0.1, 0.3, 0.8, 0.5, 0.2, 0.5, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'G':  [0.1, 0.3, 0.8, 0.4, 0.2, 0.4, 0.3, 0.1, 0.1, 0.2, 0.1, 0.1],
    # Fricatives
    'F':  [0.0, 0.2, 0.3, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'TH': [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'S':  [0.0, 0.3, 0.3, 0.4, 0.3, 0.9, 0.6, 0.4, 0.2, 0.2, 0.2, 0.1],
    'SH': [0.0, 0.2, 0.3, 0.5, 0.3, 0.8, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'HH': [0.4, 0.2, 0.2, 0.3, 0.2, 0.5, 0.3, 0.3, 0.2, 0.3, 0.4, 0.5],
    'V':  [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.7, 0.4, 0.3, 0.3, 0.2, 0.1],
    'DH': [0.1, 0.2, 0.4, 0.4, 0.3, 0.7, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'Z':  [0.0, 0.3, 0.4, 0.4, 0.3, 0.8, 0.6, 0.4, 0.2, 0.3, 0.2, 0.1],
    'ZH': [0.0, 0.2, 0.4, 0.5, 0.3, 0.7, 0.6, 0.4, 0.3, 0.4, 0.3, 0.2],
    # Affricates
    'CH': [0.0, 0.2, 0.7, 0.5, 0.2, 0.7, 0.4, 0.2, 0.2, 0.2, 0.2, 0.1],
    'JH': [0.1, 0.3, 0.6, 0.5, 0.2, 0.6, 0.5, 0.3, 0.2, 0.3, 0.2, 0.1],
    # Nasals
    'M':  [0.3, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.4, 0.3],
    'N':  [0.2, 0.3, 0.2, 0.2, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 0.5, 0.3],
    'NG': [0.2, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.5, 0.4],
    # Liquids
    'L':  [0.1, 0.2, 0.2, 0.9, 0.3, 0.3, 0.3, 0.4, 0.3, 0.6, 0.5, 0.4],
    'R':  [0.1, 0.2, 0.7, 0.5, 0.4, 0.4, 0.3, 0.3, 0.3, 0.5, 0.4, 0.4],
    # Approximants
    'W':  [0.2, 0.2, 0.2, 0.3, 0.4, 0.4, 0.5, 0.6, 0.4, 0.6, 0.5, 0.4],
    'Y':  [0.2, 0.3, 0.3, 0.4, 0.3, 0.4, 0.6, 0.6, 0.4, 0.5, 0.4, 0.3],
}


def get_phoneme_12d(phoneme: str) -> List[float]:
    """Get 12D affinity for a phoneme, using real CSR map or local fallback."""
    ph = phoneme.rstrip('012')  # Strip stress markers
    if PHONEME_MAP_ARPABET is not None and ph in PHONEME_MAP_ARPABET:
        return PHONEME_MAP_ARPABET[ph]
    if ph in LOCAL_PHONEME_12D:
        return LOCAL_PHONEME_12D[ph]
    return [0.33] * 12  # Unknown fallback


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
    for category, info in PHONEME_ONTOLOGY_MAP.items():
        if ph_clean in info['phonemes']:
            return category
    return 'unknown'


def phonemes_to_12d(phonemes: List[str]) -> torch.Tensor:
    """
    Convert phoneme sequence to 12D ontological affinity vector.

    Uses the real PHONEME_MAP_ARPABET 12D vectors from csr_phoneme_provider.py.
    Each phoneme has a Sanskrit-calibrated 12D affinity:
        [O1_POT, O2_ID, O3_EXE, O4_STR, O5_COG, O6_AGE,
         O7_REA, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS]

    The word-level vector is the mean of per-phoneme vectors.
    """
    if not phonemes:
        return torch.zeros(ONTO_DIM)

    vectors = []
    for ph in phonemes:
        vec = get_phoneme_12d(ph)
        vectors.append(torch.tensor(vec, dtype=torch.float32))

    # Mean aggregation (same as CSREmbeddingProvider)
    return torch.stack(vectors).mean(dim=0)


def compute_resonance_score(vec_12d: torch.Tensor) -> float:
    """
    Compute resonance score from 12D ontological affinity vector.

    Score interpretation (from LSTB §6b):
        >= 0.7: Harmonic (proceed to transformer)
        0.3-0.7: Neutral (route to decision gate)
        <= 0.3: Dissonant (resolve locally, skip transformer)

    The resonance score measures how strongly the phoneme profile activates
    the ontological space — high activation = harmonic, low = dissonant.
    """
    # Overall activation energy: mean of all 12 axes
    mean_activation = vec_12d.mean().item()
    # Peak activation: how strongly the dominant axis fires
    peak_activation = vec_12d.max().item()
    # Spread: how many axes are activated (complexity)
    active_axes = (vec_12d > 0.3).sum().item() / ONTO_DIM

    score = 0.4 * mean_activation + 0.3 * peak_activation + 0.3 * active_axes
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

    for cat in ['plosive', 'nasal', 'fricative', 'diphthong', 'long_vowel',
                'short_vowel', 'liquid', 'approximant', 'affricate']:
        results[f'pct_{cat}'] = category_counts.get(cat, 0) / max(total_phonemes, 1)

    return results


# =============================================================================
# TEST 2: 12D ONTOLOGICAL AFFINITY VECTORS
# =============================================================================

def test_12d_affinity_vectors(device: torch.device) -> Dict[str, float]:
    """Test that 12D affinity vectors capture articulatory-ontological structure."""
    test_cases = {
        'plosive_heavy': ['K', 'T', 'P', 'B', 'D', 'G', 'K', 'T'],
        'nasal_heavy': ['M', 'N', 'NG', 'M', 'N', 'M', 'N', 'NG'],
        'vowel_heavy': ['AA', 'IY', 'UW', 'AO', 'EY', 'OW', 'AY', 'AW'],
        'mixed': ['K', 'AE', 'T', 'S', 'AE', 'T', 'M', 'AE', 'T'],
        'fricative_heavy': ['S', 'Z', 'F', 'V', 'TH', 'SH', 'S', 'Z'],
    }

    results = {}

    for name, phonemes in test_cases.items():
        vec = phonemes_to_12d(phonemes)
        score = compute_resonance_score(vec)
        dominant_idx = vec.argmax().item()

        results[f'{name}_score'] = score
        results[f'{name}_dominant_axis'] = ONTO_AXIS_NAMES[dominant_idx]
        results[f'{name}_dominant_idx'] = dominant_idx
        results[f'{name}_peak_activation'] = vec.max().item()
        results[f'{name}_mean_activation'] = vec.mean().item()

    # Structural checks using actual 12D dominant axes
    # Plosives should peak at O3_EXECUTION (idx=2)
    results['plosive_peaks_O3'] = results['plosive_heavy_dominant_idx'] == 2
    # Nasals should peak at O10_UNIFYING (idx=9)
    results['nasal_peaks_O10'] = results['nasal_heavy_dominant_idx'] == 9
    # Fricatives should peak at O6_AGENCY (idx=5)
    results['fricative_peaks_O6'] = results['fricative_heavy_dominant_idx'] == 5

    # Plosive-heavy should have lower resonance than vowel-heavy
    results['plosive_lower_than_vowel'] = results['plosive_heavy_score'] < results['vowel_heavy_score']

    return results


# =============================================================================
# TEST 3: FLOP REDUCTION VIA PRE-FILTERING
# =============================================================================

def test_flop_reduction(device: torch.device) -> Dict[str, float]:
    """
    Test FLOP savings from phoneme-based candidate pre-filtering.

    LSTB §6b claims 82% FLOP reduction via resonance-based pruning.
    """
    import random
    random.seed(42)

    all_phonemes = []
    for info in PHONEME_ONTOLOGY_MAP.values():
        all_phonemes.extend(info['phonemes'])

    n_candidates = 1000
    scores = []

    for _ in range(n_candidates):
        length = random.randint(2, 8)
        phonemes = random.choices(all_phonemes, k=length)
        vec = phonemes_to_12d(phonemes)
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
# TEST 4: ONTOLOGY ACTIVATION PATTERNS
# =============================================================================

def test_ontology_activation(device: torch.device) -> Dict[str, float]:
    """
    Test that phoneme categories activate correct 12D ontological dimensions.

    Uses actual PHONEME_MAP_ARPABET 12D vectors:
        Plosives (K,T,P) -> O3_EXECUTION (idx 2)
        Fricatives (S,F)  -> O6_AGENCY (idx 5)
        Nasals (M,N)      -> O10_UNIFYING (idx 9)
        Liquids (L)       -> O4_STRUCTURE (idx 3)
    """
    results = {}

    for category, info in PHONEME_ONTOLOGY_MAP.items():
        phonemes = info['phonemes'][:6]
        if len(phonemes) < 3:
            phonemes = phonemes * 3

        vec = phonemes_to_12d(phonemes)
        expected_idx = info['axis_idx']
        actual_dominant_idx = vec.argmax().item()
        target_activation = vec[expected_idx].item()

        results[f'{category}_expected_axis'] = info['primary_axis']
        results[f'{category}_expected_idx'] = expected_idx
        results[f'{category}_actual_dominant'] = ONTO_AXIS_NAMES[actual_dominant_idx]
        results[f'{category}_actual_idx'] = actual_dominant_idx
        results[f'{category}_target_activation'] = target_activation
        results[f'{category}_correct'] = actual_dominant_idx == expected_idx

    correct = sum(1 for k, v in results.items() if k.endswith('_correct') and v)
    total = sum(1 for k in results if k.endswith('_correct'))
    results['activation_accuracy'] = correct / max(total, 1)

    return results


# =============================================================================
# TEST 5: CROSS-CHECK WITH SOVEREIGN STATE
# =============================================================================

def test_sovereign_crosscheck(device: torch.device) -> Dict[str, float]:
    """
    Test that CSR 12D vectors correlate with Sovereign State Bhava[0:12].

    The 12D Bhava space and 12D CSR phoneme space share the SAME
    ontological axes (O1-O12), so there should be alignment.
    """
    if not JEPA_AVAILABLE:
        return {'error': 'JEPA modules not available for cross-check'}

    profiles = {
        'execution': ['K', 'T', 'P', 'B', 'D', 'G'],    # O3
        'agency': ['S', 'Z', 'F', 'V', 'TH', 'SH'],     # O6
        'unifying': ['M', 'N', 'NG', 'M', 'N', 'NG'],    # O10
        'purpose': ['AY', 'AW', 'OY', 'EY', 'OW', 'AY'], # O8
        'witness': ['OW', 'AO', 'OY', 'OW', 'AO', 'OW'], # O9
    }

    phoneme_vecs = []
    for name, phonemes in profiles.items():
        vec = phonemes_to_12d(phonemes)
        phoneme_vecs.append(vec)

    phoneme_mat = torch.stack(phoneme_vecs)  # [5, 12]

    projector = SovereignStateProjector(hidden_dim=768, state_dim=32).to(device)

    with torch.no_grad():
        bridge = torch.randn(12, 768, device=device) * 0.1
        h = phoneme_mat.to(device) @ bridge  # [5, 768]
        S = projector(h)  # [5, 32]
        bhava = S[:, 0:12]  # [5, 12] — same 12 axes as CSR

    expected_bhava_idx = {
        'execution': 2,  # O3
        'agency': 5,     # O6
        'unifying': 9,   # O10
        'purpose': 7,    # O8
        'witness': 8,    # O9
    }

    results = {}
    correct = 0
    for i, (name, exp_idx) in enumerate(expected_bhava_idx.items()):
        actual_max = bhava[i].argmax().item()
        activation = bhava[i, exp_idx].item()
        results[f'{name}_expected_idx'] = exp_idx
        results[f'{name}_actual_max_idx'] = actual_max
        results[f'{name}_target_activation'] = activation
        if actual_max == exp_idx:
            correct += 1

    results['bhava_alignment_accuracy'] = correct / len(expected_bhava_idx)

    return results


# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

def run_csr_bridge_benchmarks(
    args,
    config,
    device: str,
) -> Dict[str, any]:
    """Run comprehensive Phoneme CSR 12D bridge benchmarks."""
    print("\n" + "=" * 70)
    print("V11.0: PHONEME CSR BRIDGE BENCHMARKS (12D Ontological Affinity)")
    print("=" * 70)

    if CSR_AVAILABLE:
        print("  CSR provider: AVAILABLE (using real PHONEME_MAP_ARPABET)")
    else:
        print("  CSR provider: NOT AVAILABLE (using local 12D fallback table)")

    device = torch.device(device)
    results = {}

    # TEST 1: Phoneme Decomposition
    print("\n--- TEST 1: Phoneme Decomposition Quality ---")
    decomp_results = test_phoneme_decomposition(device)
    results['decomposition'] = decomp_results

    print(f"  Total words: {decomp_results['total_words']}")
    print(f"  Total phonemes: {decomp_results['total_phonemes']}")
    print(f"  Classification rate: {decomp_results['classification_rate']:.1%}")
    print(f"  Phonemes/word: {decomp_results['phonemes_per_word']:.1f}")
    for cat in ['plosive', 'fricative', 'nasal', 'liquid', 'short_vowel', 'long_vowel', 'approximant']:
        pct = decomp_results.get(f'pct_{cat}', 0)
        print(f"    {cat:15s}: {pct:.1%}")

    # TEST 2: 12D Affinity Vectors
    print("\n--- TEST 2: 12D Ontological Affinity Vectors ---")
    vec_results = test_12d_affinity_vectors(device)
    results['affinity_vectors'] = vec_results

    for name in ['plosive_heavy', 'nasal_heavy', 'vowel_heavy', 'mixed', 'fricative_heavy']:
        axis = vec_results[f'{name}_dominant_axis']
        score = vec_results[f'{name}_score']
        peak = vec_results[f'{name}_peak_activation']
        print(f"  {name:18s}: dominant={axis:16s} score={score:.3f} peak={peak:.2f}")

    print(f"  Plosive peaks O3: {vec_results['plosive_peaks_O3']}")
    print(f"  Nasal peaks O10:  {vec_results['nasal_peaks_O10']}")
    print(f"  Fricative peaks O6: {vec_results['fricative_peaks_O6']}")

    # TEST 3: FLOP Reduction
    print("\n--- TEST 3: FLOP Reduction via Pre-filtering ---")
    flop_results = test_flop_reduction(device)
    results['flop_reduction'] = flop_results

    print(f"  Distribution ({flop_results['n_candidates']} candidates):")
    print(f"    Harmonic (>= 0.7):  {flop_results['pct_harmonic']:.1%}")
    print(f"    Neutral (0.3-0.7):  {flop_results['pct_neutral']:.1%}")
    print(f"    Dissonant (<0.3):   {flop_results['pct_dissonant']:.1%}")
    print(f"  Estimated FLOP reduction: {flop_results['flop_reduction_estimated']:.1%}")

    # TEST 4: Ontology Activation
    print("\n--- TEST 4: 12D Ontology Activation Patterns ---")
    onto_results = test_ontology_activation(device)
    results['ontology_activation'] = onto_results

    for cat in ['plosive', 'fricative', 'nasal', 'liquid', 'approximant', 'diphthong', 'short_vowel']:
        correct = onto_results.get(f'{cat}_correct', False)
        expected = onto_results.get(f'{cat}_expected_axis', '?')
        actual = onto_results.get(f'{cat}_actual_dominant', '?')
        marker = "OK" if correct else "MISS"
        print(f"  {cat:15s}: expected={expected:16s} actual={actual:16s} [{marker}]")

    print(f"  Activation accuracy: {onto_results['activation_accuracy']:.0%}")

    # TEST 5: Sovereign Cross-check
    print("\n--- TEST 5: Sovereign State Cross-check ---")
    cross_results = test_sovereign_crosscheck(device)
    results['sovereign_crosscheck'] = cross_results

    if 'error' not in cross_results:
        print(f"  Bhava alignment accuracy: {cross_results['bhava_alignment_accuracy']:.1%}")
        print(f"  (Baseline ~8.3%, goal > 50% after training)")
        for name in ['execution', 'agency', 'unifying', 'purpose', 'witness']:
            exp = cross_results.get(f'{name}_expected_idx', -1)
            act = cross_results.get(f'{name}_actual_max_idx', -1)
            print(f"    {name:12s}: expected {ONTO_AXIS_NAMES[exp]:16s}, got {ONTO_AXIS_NAMES[act]:16s}")
    else:
        print(f"  {cross_results['error']}")

    # SUMMARY
    print("\n" + "=" * 70)
    print("CSR BRIDGE BENCHMARK SUMMARY (12D)")
    print("=" * 70)
    print(f"  Classification rate:    {decomp_results['classification_rate']:.1%}")
    print(f"  Plosive->O3 correct:    {vec_results['plosive_peaks_O3']}")
    print(f"  Nasal->O10 correct:     {vec_results['nasal_peaks_O10']}")
    print(f"  Fricative->O6 correct:  {vec_results['fricative_peaks_O6']}")
    print(f"  FLOP reduction:         {flop_results['flop_reduction_estimated']:.1%}")
    print(f"  Activation accuracy:    {onto_results['activation_accuracy']:.0%}")

    return results


def run_csr_bridge_benchmark_integration(args, config):
    """CLI routing wrapper for CSR bridge benchmarks."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_csr_bridge_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
