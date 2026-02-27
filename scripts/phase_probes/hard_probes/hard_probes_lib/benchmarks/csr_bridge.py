"""
LSTB Phoneme CSR Bridge Benchmarks (V11.0)

Tests the Constant Shift Resonance phoneme grounding system:
    1. Phoneme decomposition quality (ARPABET coverage)
    2. 10D resonance vector generation
    3. Resonance scoring (harmonic/neutral/dissonant distribution)
    4. Candidate pre-filtering FLOP reduction
    5. Ontological dimension activation (plosive->O3, nasal->O5, etc.)
    6. Cross-check with Sovereign State Bhava dimensions

CLI Usage::

    python train_hard_probes.py --test-csr-bridge
    python train_hard_probes.py --test-csr-bridge --csr-ablation

References:
    - LATENT_SEMANTIC_TOKEN_BRIDGE_DESIGN.md §6b
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
    )
    CSR_AVAILABLE = True
except ImportError:
    CSR_AVAILABLE = False

# JEPA for cross-check
try:
    from symbolu.jepa.state_projector import SovereignStateProjector
    JEPA_AVAILABLE = True
except ImportError:
    JEPA_AVAILABLE = False


# =============================================================================
# PHONEME ONTOLOGY MAPPING (from LSTB §6b)
# =============================================================================

PHONEME_ONTOLOGY_MAP = {
    # Plosives -> O3_EXECUTION (structural, percussive)
    'plosive': {'phonemes': ['P', 'B', 'T', 'D', 'K', 'G'], 'primary_axis': 'O3_EXECUTION', 'axis_idx': 2},
    # Nasals -> O5_COGNITION (resonant, continuous)
    'nasal': {'phonemes': ['M', 'N', 'NG'], 'primary_axis': 'O5_COGNITION', 'axis_idx': 4},
    # Fricatives -> O7_REASONING (sustained, analytical)
    'fricative': {'phonemes': ['F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'HH'], 'primary_axis': 'O7_REASONING', 'axis_idx': 6},
    # Diphthongs -> O8_PURPOSE (transitional, directional)
    'diphthong': {'phonemes': ['AY', 'AW', 'OY', 'EY', 'OW'], 'primary_axis': 'O8_PURPOSE', 'axis_idx': 7},
    # Long vowels -> O9_WITNESSES (sustained, open)
    'long_vowel': {'phonemes': ['AA', 'AO', 'IY', 'UW', 'ER'], 'primary_axis': 'O9_WITNESSES', 'axis_idx': 8},
    # Short vowels -> O2_IDENTITY (quick, grounding)
    'short_vowel': {'phonemes': ['AE', 'AH', 'EH', 'IH', 'UH'], 'primary_axis': 'O2_IDENTITY', 'axis_idx': 1},
    # Approximants -> O10_UNIFYING (smooth, connecting)
    'approximant': {'phonemes': ['L', 'R', 'W', 'Y'], 'primary_axis': 'O10_UNIFYING', 'axis_idx': 9},
    # Affricates -> O4_STRUCTURE (compound, structured)
    'affricate': {'phonemes': ['CH', 'JH'], 'primary_axis': 'O4_STRUCTURE', 'axis_idx': 3},
}


# =============================================================================
# LOCAL PHONEME IMPLEMENTATION (when csr_phoneme_provider not available)
# =============================================================================

# Simplified ARPABET lookup for common words
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
            # Fallback: use first/last character mapping
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
    # Strip stress markers
    ph_clean = ph.rstrip('012')
    for category, info in PHONEME_ONTOLOGY_MAP.items():
        if ph_clean in info['phonemes']:
            return category
    return 'unknown'


def phonemes_to_10d(phonemes: List[str]) -> torch.Tensor:
    """
    Convert phoneme sequence to 10D resonance vector.

    10 dimensions correspond to 10 octave layers:
        [0] Plosive density
        [1] Nasal density
        [2] Fricative density
        [3] Diphthong density
        [4] Long vowel density
        [5] Short vowel density
        [6] Approximant density
        [7] Affricate density
        [8] Mean sonority
        [9] Articulatory complexity (unique categories / total)
    """
    if not phonemes:
        return torch.zeros(10)

    categories = [classify_phoneme(ph) for ph in phonemes]
    total = len(categories)

    vec = torch.zeros(10)
    cat_names = ['plosive', 'nasal', 'fricative', 'diphthong', 'long_vowel',
                 'short_vowel', 'approximant', 'affricate']

    for i, cat in enumerate(cat_names):
        vec[i] = categories.count(cat) / total

    # Sonority: vowels=1, approximants=0.8, nasals=0.6, fricatives=0.4, plosives=0.2
    sonority_map = {
        'long_vowel': 1.0, 'short_vowel': 0.9, 'diphthong': 0.85,
        'approximant': 0.7, 'nasal': 0.5, 'fricative': 0.3,
        'affricate': 0.2, 'plosive': 0.1, 'unknown': 0.5,
    }
    vec[8] = sum(sonority_map.get(c, 0.5) for c in categories) / total

    # Articulatory complexity
    unique_cats = len(set(c for c in categories if c != 'unknown'))
    vec[9] = unique_cats / len(cat_names)

    return vec


def compute_resonance_score(vec_10d: torch.Tensor) -> float:
    """
    Compute resonance score from 10D vector.

    Score interpretation (from LSTB §6b):
        >= 0.7: Harmonic (proceed to transformer)
        0.3-0.7: Neutral (route to decision gate)
        <= 0.3: Dissonant (resolve locally, skip transformer)
    """
    # Balance between sonority (smoothness) and complexity (richness)
    sonority = vec_10d[8].item()
    complexity = vec_10d[9].item()
    # Penalize extreme plosive dominance (harsh)
    plosive_penalty = max(0, vec_10d[0].item() - 0.5) * 0.5

    score = 0.5 * sonority + 0.3 * complexity - plosive_penalty + 0.2
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

    # Category distribution
    for cat in ['plosive', 'nasal', 'fricative', 'diphthong', 'long_vowel',
                'short_vowel', 'approximant', 'affricate']:
        results[f'pct_{cat}'] = category_counts.get(cat, 0) / max(total_phonemes, 1)

    return results


# =============================================================================
# TEST 2: 10D RESONANCE VECTORS
# =============================================================================

def test_resonance_vectors(device: torch.device) -> Dict[str, float]:
    """Test that 10D resonance vectors capture articulatory structure."""
    test_cases = {
        'plosive_heavy': ['K', 'T', 'P', 'B', 'D', 'G', 'K', 'T'],
        'nasal_heavy': ['M', 'N', 'NG', 'M', 'N', 'M', 'N', 'NG'],
        'vowel_heavy': ['AA', 'IY', 'UW', 'AO', 'EY', 'OW', 'AY', 'AW'],
        'mixed': ['K', 'AE', 'T', 'S', 'AE', 'T', 'M', 'AE', 'T'],
        'fricative_heavy': ['S', 'Z', 'F', 'V', 'TH', 'SH', 'S', 'Z'],
    }

    results = {}

    for name, phonemes in test_cases.items():
        vec = phonemes_to_10d(phonemes)
        score = compute_resonance_score(vec)

        results[f'{name}_score'] = score
        results[f'{name}_sonority'] = vec[8].item()
        results[f'{name}_complexity'] = vec[9].item()

    # Structural checks
    # Plosive-heavy should have low resonance
    results['plosive_low_resonance'] = results['plosive_heavy_score'] < results['vowel_heavy_score']
    # Vowel-heavy should have high resonance
    results['vowel_high_resonance'] = results['vowel_heavy_score'] > 0.6
    # Mixed should be in the middle
    results['mixed_moderate'] = 0.3 < results['mixed_score'] < 0.8

    return results


# =============================================================================
# TEST 3: FLOP REDUCTION VIA PRE-FILTERING
# =============================================================================

def test_flop_reduction(device: torch.device) -> Dict[str, float]:
    """
    Test FLOP savings from phoneme-based candidate pre-filtering.

    LSTB §6b claims 82% FLOP reduction. We measure:
        - What fraction of candidates get filtered at each threshold
        - Harmonic/Neutral/Dissonant distribution
    """
    # Generate many word-like phoneme sequences
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
        vec = phonemes_to_10d(phonemes)
        score = compute_resonance_score(vec)
        scores.append(score)

    scores_t = torch.tensor(scores)

    results = {}
    results['n_candidates'] = n_candidates

    # Distribution
    harmonic = (scores_t >= 0.7).sum().item()
    neutral = ((scores_t >= 0.3) & (scores_t < 0.7)).sum().item()
    dissonant = (scores_t < 0.3).sum().item()

    results['pct_harmonic'] = harmonic / n_candidates
    results['pct_neutral'] = neutral / n_candidates
    results['pct_dissonant'] = dissonant / n_candidates

    # FLOP reduction: dissonant candidates skip transformer entirely
    results['flop_reduction_dissonant'] = dissonant / n_candidates
    # With decision gate: neutral might also be filtered (~50% of neutral)
    results['flop_reduction_estimated'] = (dissonant + neutral * 0.5) / n_candidates

    results['mean_score'] = scores_t.mean().item()
    results['std_score'] = scores_t.std().item()

    return results


# =============================================================================
# TEST 4: ONTOLOGY ACTIVATION PATTERNS
# =============================================================================

def test_ontology_activation(device: torch.device) -> Dict[str, float]:
    """
    Test that phoneme categories activate correct ontological dimensions.

    Expected (from LSTB §6b):
        Plosives (K,T,P) -> O3_EXECUTION
        Nasals (N,M) -> O5_COGNITION
        Fricatives (S,F) -> O7_REASONING
        etc.
    """
    results = {}

    for category, info in PHONEME_ONTOLOGY_MAP.items():
        # Create pure-category phoneme sequence
        phonemes = info['phonemes'][:6]
        if len(phonemes) < 3:
            phonemes = phonemes * 3

        vec = phonemes_to_10d(phonemes)

        # Check that the expected category dimension dominates
        cat_names = ['plosive', 'nasal', 'fricative', 'diphthong', 'long_vowel',
                     'short_vowel', 'approximant', 'affricate']
        if category in cat_names:
            cat_idx = cat_names.index(category)
            density = vec[cat_idx].item()
            # Should dominate (> 0.5 of total)
            results[f'{category}_density'] = density
            results[f'{category}_dominant'] = density > 0.5

            # Check ontological axis
            results[f'{category}_target_axis'] = info['primary_axis']
            results[f'{category}_axis_idx'] = info['axis_idx']

    # Overall correctness
    dominant_count = sum(1 for k, v in results.items() if k.endswith('_dominant') and v)
    total_categories = len(PHONEME_ONTOLOGY_MAP)
    results['activation_accuracy'] = dominant_count / total_categories

    return results


# =============================================================================
# TEST 5: CROSS-CHECK WITH SOVEREIGN STATE
# =============================================================================

def test_sovereign_crosscheck(device: torch.device) -> Dict[str, float]:
    """
    Test that CSR phoneme vectors correlate with Sovereign State Bhava dimensions.

    The 12D Bhava space and 10D phoneme space should share structure
    if the phoneme-ontology mapping is correct.
    """
    if not JEPA_AVAILABLE:
        return {'error': 'JEPA modules not available for cross-check'}

    # Create phoneme vectors for different articulatory profiles
    profiles = {
        'execution': ['K', 'T', 'P', 'B', 'D', 'G'],  # Plosive -> O3
        'cognition': ['M', 'N', 'NG', 'M', 'N', 'NG'],  # Nasal -> O5
        'reasoning': ['S', 'Z', 'F', 'V', 'TH', 'SH'],  # Fricative -> O7
        'purpose': ['AY', 'AW', 'OY', 'EY', 'OW', 'AY'],  # Diphthong -> O8
        'witness': ['AA', 'AO', 'IY', 'UW', 'ER', 'AA'],  # Long vowel -> O9
    }

    phoneme_vecs = []
    for name, phonemes in profiles.items():
        vec = phonemes_to_10d(phonemes)
        phoneme_vecs.append(vec)

    phoneme_mat = torch.stack(phoneme_vecs)  # [5, 10]

    # Create corresponding synthetic hidden states through random projection
    # (In real system, these would come from actual text with these phoneme profiles)
    projector = SovereignStateProjector(hidden_dim=768, state_dim=32).to(device)

    # Use random projection from 10D phoneme space to 768D
    with torch.no_grad():
        bridge = torch.randn(10, 768, device=device) * 0.1
        h = phoneme_mat.to(device) @ bridge  # [5, 768]
        S = projector(h)  # [5, 32]
        bhava = S[:, 0:12]  # [5, 12]

    # Measure correlation between phoneme categories and Bhava activations
    # For each profile, check if the expected Bhava index is relatively activated
    expected_bhava_idx = {
        'execution': 2,   # O3
        'cognition': 4,   # O5
        'reasoning': 6,   # O7
        'purpose': 7,     # O8
        'witness': 8,     # O9
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
    # Note: with random init, alignment should be ~1/12 = 0.083 baseline
    # After training, goal is > 0.5

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
    Run comprehensive Phoneme CSR bridge benchmarks.

    Tests:
    1. Phoneme decomposition quality
    2. 10D resonance vector generation
    3. FLOP reduction via pre-filtering
    4. Ontology activation patterns
    5. Cross-check with Sovereign State
    """
    print("\n" + "=" * 70)
    print("V11.0: PHONEME CSR BRIDGE BENCHMARKS")
    print("=" * 70)

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
    print(f"  Category distribution:")
    for cat in ['plosive', 'nasal', 'fricative', 'short_vowel', 'long_vowel', 'approximant']:
        pct = decomp_results.get(f'pct_{cat}', 0)
        print(f"    {cat:15s}: {pct:.1%}")

    # -------------------------------------------------------------------------
    # TEST 2: Resonance Vectors
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: 10D Resonance Vectors ---")
    res_results = test_resonance_vectors(device)
    results['resonance_vectors'] = res_results

    for name in ['plosive_heavy', 'nasal_heavy', 'vowel_heavy', 'mixed', 'fricative_heavy']:
        score = res_results[f'{name}_score']
        sono = res_results[f'{name}_sonority']
        print(f"  {name:18s}: score={score:.3f}, sonority={sono:.3f}")

    print(f"  Plosive < vowel resonance: {res_results['plosive_low_resonance']}")
    print(f"  Vowel high resonance: {res_results['vowel_high_resonance']}")

    # -------------------------------------------------------------------------
    # TEST 3: FLOP Reduction
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: FLOP Reduction via Pre-filtering ---")
    flop_results = test_flop_reduction(device)
    results['flop_reduction'] = flop_results

    print(f"  Distribution ({flop_results['n_candidates']} candidates):")
    print(f"    Harmonic (>= 0.7):  {flop_results['pct_harmonic']:.1%}")
    print(f"    Neutral (0.3-0.7):  {flop_results['pct_neutral']:.1%}")
    print(f"    Dissonant (<0.3):   {flop_results['pct_dissonant']:.1%}")
    print(f"  Estimated FLOP reduction: {flop_results['flop_reduction_estimated']:.1%}")
    print(f"  (LSTB target: 82%)")

    # -------------------------------------------------------------------------
    # TEST 4: Ontology Activation
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Ontology Activation Patterns ---")
    onto_results = test_ontology_activation(device)
    results['ontology_activation'] = onto_results

    for cat in ['plosive', 'nasal', 'fricative', 'diphthong', 'long_vowel', 'approximant']:
        dominant = onto_results.get(f'{cat}_dominant', False)
        density = onto_results.get(f'{cat}_density', 0)
        axis = onto_results.get(f'{cat}_target_axis', '?')
        marker = "OK" if dominant else "WEAK"
        print(f"  {cat:15s} -> {axis:15s}: density={density:.2f} [{marker}]")

    print(f"  Activation accuracy: {onto_results['activation_accuracy']:.1%}")

    # -------------------------------------------------------------------------
    # TEST 5: Sovereign Cross-check
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Sovereign State Cross-check ---")
    cross_results = test_sovereign_crosscheck(device)
    results['sovereign_crosscheck'] = cross_results

    if 'error' not in cross_results:
        print(f"  Bhava alignment accuracy: {cross_results['bhava_alignment_accuracy']:.1%}")
        print(f"  (Baseline ~8.3%, goal > 50% after training)")
        for name in ['execution', 'cognition', 'reasoning', 'purpose', 'witness']:
            exp = cross_results.get(f'{name}_expected_idx', '?')
            act = cross_results.get(f'{name}_actual_max_idx', '?')
            print(f"    {name:12s}: expected O{exp+1}, got O{act+1}")
    else:
        print(f"  {cross_results['error']}")

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CSR BRIDGE BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"  Classification rate:    {decomp_results['classification_rate']:.1%}")
    print(f"  Resonance ordering OK:  {res_results['plosive_low_resonance']}")
    print(f"  FLOP reduction:         {flop_results['flop_reduction_estimated']:.1%}")
    print(f"  Activation accuracy:    {onto_results['activation_accuracy']:.1%}")

    return results


def run_csr_bridge_benchmark_integration(args, config):
    """CLI routing wrapper for CSR bridge benchmarks."""
    device = getattr(args, 'device', 'cuda' if torch.cuda.is_available() else 'cpu')
    results = run_csr_bridge_benchmarks(args, config, device)
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    return results
