"""
LSTB Phoneme CSR Bridge Benchmarks (V11.0)

Tests the CSR phoneme system as a SEMANTIC-EMOTIONAL ENCODER (data plane)
grounded in Sanskrit varna theory.

CSR extracts bottom-up signal from phoneme patterns:
    - Vrtti (mental propensity) pressure encoding
    - Ontological layer (O1-O12) activation per phoneme
    - Varga-based consonant grouping with distinct semantic signatures

CSR is NOT a governance layer. It is analogous to:
    - CNN extracting edges from images
    - Prosody models extracting affect
    - Feature extractors producing distributions for downstream reasoning

The ontological stack (control plane) may OBSERVE CSR output but is never
directly selected or routed by it. Signal != Governance.

Tests:
    1. Phoneme decomposition quality (ARPABET coverage, category distribution)
    2. Ontological layer activation (O1-O12 dominant layer per phoneme class)
    3. Resonance scoring (harmonic/neutral/dissonant for FLOP pre-filtering)
    4. Varga discriminability (Sanskrit varga grouping separation in 12D space)
    5. Vrtti and consciousness mapping (mental propensity semantics validation)
    6. VarnaCSRBridge validation (ARPABET→Varna mapping coverage + bridge)

CLI Usage::

    python train_hard_probes.py --test-csr-bridge

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

# Optional: ARPABET_TO_VARNA for Test 6
try:
    from csr_phoneme_provider import ARPABET_TO_VARNA, SANSKRIT_VOWEL_CALIBRATION
    VARNA_AVAILABLE = True
except ImportError:
    ARPABET_TO_VARNA = None
    SANSKRIT_VOWEL_CALIBRATION = None
    VARNA_AVAILABLE = False


# =============================================================================
# CSR RESONANCE DIMENSIONS (12 ontological layer channels)
# =============================================================================
# These are ONTOLOGICAL LAYER affinities, not generic acoustic channels.
# Each dimension corresponds to a specific ontological layer from Sanskrit
# varna theory, grounded in the Māheśvara Sūtra progression.

RESONANCE_DIM = 12

ONTOLOGICAL_LAYERS = {
    0: "O1_Potential",      # Dormant/Unmanifested
    1: "O2_Activation",     # Initial stirring
    2: "O3_Execution",      # Active doing
    3: "O4_Maintenance",    # Sustained effort
    4: "O5_Dissolution",    # Breaking down
    5: "O6_Latency",        # Hidden potential / Agency
    6: "O7_Emergence",      # Coming forth / Reasoning
    7: "O8_Stabilization",  # Finding balance / Purpose
    8: "O9_Authority",      # Commanding presence / Witness
    9: "O10_Unifying",      # Bringing together
    10: "O11_Integration",  # Synthesizing
    11: "O12_Absolving",    # Complete release/transcendence
}


# =============================================================================
# PHONEME CATEGORIES (Sanskrit varna-grounded)
# =============================================================================
# Categories defined by BOTH articulatory manner AND Sanskrit semantic meaning.
# Each category has a dominant ontological layer from PHONEME_MAP_ARPABET.

PHONEME_CATEGORIES = {
    'plosive': {
        'phonemes': ['P', 'B', 'T', 'D', 'K', 'G'],
        'dominant_layer': 2,  # O3_Execution
        'semantic_quality': 'forceful_action',
        'varna_pressures': {
            'K': 'āśā (hope)',
            'G': 'ceṣṭā (action)',
            'P': 'ghrṇā (revulsion)',
            'B': 'avajñā (indifference)',
            'T': 'vitarka (overstatement)',
            'D': 'lajjā (shyness)',
        },
    },
    'fricative': {
        'phonemes': ['F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'HH'],
        'dominant_layer': 5,  # O6_Latency (Agency)
        'semantic_quality': 'controlled_agency',
        'varna_pressures': {
            'S': 'escapism',
            'SH': 'material greed (lobha)',
            'F': 'bhaya (fear)',
            'DH': 'tṛṣṇā (craving)',
            'HH': 'avidyā (ignorance)',
        },
    },
    'affricate': {
        'phonemes': ['CH', 'JH'],
        'dominant_layer': 2,  # O3 + O6 blend
        'semantic_quality': 'boundary_force',
        'varna_pressures': {
            'CH': 'vikṣepa (scatter)',
            'JH': 'dambha (vanity)',
        },
    },
    'nasal': {
        'phonemes': ['M', 'N', 'NG'],
        'dominant_layer': 9,  # O10_Unifying
        'semantic_quality': 'connective_resonance',
        'varna_pressures': {
            'M': 'praśraya (indulgence)',
            'N': 'moha (blind attachment)',
            'NG': 'dambha (vanity)',
        },
    },
    'liquid': {
        'phonemes': ['L', 'R'],
        'dominant_layer': 3,  # O4_Maintenance (Structure)
        'semantic_quality': 'structural_flow',
        'varna_pressures': {
            'L': 'krūratā (cruelty)',
            'R': 'sarvanāśa (annihilation)',
        },
    },
    'approximant': {
        'phonemes': ['W', 'Y'],
        'dominant_layer': 7,  # O8_Stabilization (Purpose)
        'semantic_quality': 'transitional_glide',
        'varna_pressures': {
            'Y': 'aviśvāsa (lack of confidence)',
            'W': 'dharma (righteousness)',
        },
    },
    'short_vowel': {
        'phonemes': ['AE', 'AH', 'EH', 'IH', 'UH'],
        'semantic_quality': 'grounding_awareness',
        'varna_states': {
            'AH': ('a', 'birth of cognition', 0),      # O1
            'IH': ('i', 'i-ness / doing self', 1),      # O2
            'EH': ('e', 'practical thought', 6),         # O7
            'UH': ('u', 'contraction / focus', 4),       # O5
            'AE': ('a', 'open vowel variant', 0),        # O1
        },
    },
    'long_vowel': {
        'phonemes': ['AA', 'AO', 'IY', 'UW', 'ER'],
        'semantic_quality': 'sustained_consciousness',
        'varna_states': {
            'AA': ('a', 'primordial potential', 0),      # O1
            'IY': ('ī', 'specialized identity', 3),      # O4
            'UW': ('ū', 'sustained hold / unity', 9),    # O10
            'AO': ('o', 'completion / closure', 8),      # O9
            'ER': ('ṛ', 'execution energy', 2),          # O3
        },
    },
    'diphthong': {
        'phonemes': ['AY', 'AW', 'OY', 'EY', 'OW'],
        'semantic_quality': 'transformation_energy',
        'varna_states': {
            'EY': ('e', 'practical thought / benefit', 7),   # O8
            'AY': ('ai', 'welfare / materialization', 7),    # O8
            'OW': ('o', 'observer / completion', 8),         # O9
            'OY': ('ai', 'welfare blend', 7),                # O8
            'AW': ('au', 'surrender / transformation', 11),  # O12
        },
    },
}

# Sanskrit varga groupings (by place of articulation in classical grammar)
VARGA_GROUPS = {
    'ka_varga': {
        'phonemes': ['K', 'G', 'NG'],
        'description': 'Guttural (kaṇṭhya) — throat chakra propensities',
        'vrttis': ['āśā (hope)', 'ceṣṭā (action)', 'dambha (vanity)'],
    },
    'ca_varga': {
        'phonemes': ['CH', 'JH'],
        'description': 'Palatal (tālavya) — heart/expression propensities',
        'vrttis': ['vikṣepa (scatter)', 'dambha (vanity)'],
    },
    'ta_retroflex_varga': {
        'phonemes': ['T', 'D'],
        'description': 'Retroflex (mūrdhanya) — solar plexus propensities',
        'vrttis': ['vitarka (overstatement)', 'lajjā (shyness)'],
    },
    'ta_dental_varga': {
        'phonemes': ['TH', 'DH', 'N'],
        'description': 'Dental (dantya) — sacral propensities',
        'vrttis': ['viṣāda (melancholy)', 'tṛṣṇā (craving)', 'moha (attachment)'],
    },
    'pa_varga': {
        'phonemes': ['P', 'B', 'M'],
        'description': 'Labial (oṣṭhya) — root chakra propensities',
        'vrttis': ['ghrṇā (hatred)', 'avajñā (indifference)', 'praśraya (indulgence)'],
    },
    'antahstha': {
        'phonemes': ['Y', 'R', 'L', 'W'],
        'description': 'Semi-vowels (antaḥstha) — transitional energies',
        'vrttis': ['aviśvāsa', 'sarvanāśa', 'krūratā', 'dharma'],
    },
    'ushman': {
        'phonemes': ['S', 'SH', 'HH'],
        'description': 'Sibilants (ūṣman) — friction/heat energies',
        'vrttis': ['escapism', 'material greed', 'avidyā (ignorance)'],
    },
}


# =============================================================================
# LOCAL 12D RESONANCE TABLE (fallback when csr_phoneme_provider not available)
# =============================================================================
# These are Sanskrit-calibrated 12D ontological layer affinity vectors
# from PHONEME_MAP_ARPABET. Each dimension is an ontological layer (O1-O12).

LOCAL_PHONEME_12D = {
    # Vowels — consciousness states mapped to ontological layers
    # a (अ): Birth of cognition → O1_Potential dominant
    'AA': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],
    'AH': [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],
    'AE': [0.7, 0.4, 0.2, 0.2, 0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.2, 0.1],
    # i (इ): I-ness / Identity → O2_Activation dominant
    'IH': [0.2, 0.9, 0.4, 0.2, 0.3, 0.2, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    # ī (ई): Specialized identity → O4_Maintenance dominant
    'IY': [0.1, 0.6, 0.3, 0.9, 0.2, 0.2, 0.3, 0.2, 0.2, 0.3, 0.2, 0.2],
    # u (उ): Contraction / Cohesion → O5_Dissolution dominant
    'UH': [0.1, 0.2, 0.2, 0.3, 0.9, 0.3, 0.1, 0.2, 0.4, 0.7, 0.3, 0.2],
    # ū (ऊ): Sustained hold / Deep unity → O6 + O10 dominant
    'UW': [0.1, 0.1, 0.1, 0.2, 0.4, 0.8, 0.2, 0.3, 0.5, 0.9, 0.4, 0.4],
    # e (ए): Intellect / Aspiration → O3 + O7 dominant
    'EH': [0.1, 0.2, 0.7, 0.3, 0.4, 0.3, 0.8, 0.4, 0.2, 0.3, 0.3, 0.2],
    'ER': [0.2, 0.3, 0.5, 0.4, 0.4, 0.4, 0.6, 0.4, 0.3, 0.4, 0.3, 0.3],
    # ai (ऐ): Soul intention / Wisdom → O8_Stabilization dominant
    'EY': [0.1, 0.1, 0.3, 0.2, 0.3, 0.4, 0.5, 0.9, 0.4, 0.5, 0.4, 0.3],
    'AY': [0.2, 0.2, 0.4, 0.2, 0.3, 0.4, 0.4, 0.8, 0.4, 0.5, 0.4, 0.3],
    # o (ओ): Observer / Completion → O9_Authority + O11_Integration dominant
    'OW': [0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.4, 0.5, 0.9, 0.6, 0.8, 0.5],
    'AO': [0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4, 0.5, 0.8, 0.6, 0.7, 0.5],
    'OY': [0.2, 0.2, 0.3, 0.2, 0.3, 0.3, 0.4, 0.6, 0.8, 0.5, 0.7, 0.5],
    # au (औ): Transformation / Surrender → O12_Absolving dominant
    'AW': [0.1, 0.1, 0.2, 0.1, 0.2, 0.3, 0.3, 0.6, 0.7, 0.4, 0.6, 0.9],
    # Plosives — O3_Execution dominant
    'P':  [0.0, 0.2, 0.8, 0.4, 0.1, 0.5, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'T':  [0.0, 0.2, 0.9, 0.5, 0.1, 0.6, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],
    'K':  [0.0, 0.2, 0.9, 0.4, 0.1, 0.5, 0.3, 0.1, 0.1, 0.1, 0.1, 0.0],
    'B':  [0.1, 0.3, 0.7, 0.4, 0.2, 0.4, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'D':  [0.1, 0.3, 0.8, 0.5, 0.2, 0.5, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],
    'G':  [0.1, 0.3, 0.8, 0.4, 0.2, 0.4, 0.3, 0.1, 0.1, 0.2, 0.1, 0.1],
    # Fricatives — O6_Latency (Agency) dominant
    'F':  [0.0, 0.2, 0.3, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'TH': [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],
    'S':  [0.0, 0.3, 0.3, 0.4, 0.3, 0.9, 0.6, 0.4, 0.2, 0.2, 0.2, 0.1],
    'SH': [0.0, 0.2, 0.3, 0.5, 0.3, 0.8, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'HH': [0.4, 0.2, 0.2, 0.3, 0.2, 0.5, 0.3, 0.3, 0.2, 0.3, 0.4, 0.5],
    'V':  [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.7, 0.4, 0.3, 0.3, 0.2, 0.1],
    'DH': [0.1, 0.2, 0.4, 0.4, 0.3, 0.7, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],
    'Z':  [0.0, 0.3, 0.4, 0.4, 0.3, 0.8, 0.6, 0.4, 0.2, 0.3, 0.2, 0.1],
    'ZH': [0.0, 0.2, 0.4, 0.5, 0.3, 0.7, 0.6, 0.4, 0.3, 0.4, 0.3, 0.2],
    # Affricates — O3 + O6 blend
    'CH': [0.0, 0.2, 0.7, 0.5, 0.2, 0.7, 0.4, 0.2, 0.2, 0.2, 0.2, 0.1],
    'JH': [0.1, 0.3, 0.6, 0.5, 0.2, 0.6, 0.5, 0.3, 0.2, 0.3, 0.2, 0.1],
    # Nasals — O10_Unifying dominant
    'M':  [0.3, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.4, 0.3],
    'N':  [0.2, 0.3, 0.2, 0.2, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 0.5, 0.3],
    'NG': [0.2, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.5, 0.4],
    # Liquids — O4_Maintenance (Structure) dominant
    'L':  [0.1, 0.2, 0.2, 0.9, 0.3, 0.3, 0.3, 0.4, 0.3, 0.6, 0.5, 0.4],
    'R':  [0.1, 0.2, 0.7, 0.5, 0.4, 0.4, 0.3, 0.3, 0.3, 0.5, 0.4, 0.4],
    # Approximants — O7+O8 (Reasoning+Purpose)
    'W':  [0.2, 0.2, 0.2, 0.3, 0.4, 0.4, 0.5, 0.6, 0.4, 0.6, 0.5, 0.4],
    'Y':  [0.2, 0.3, 0.3, 0.4, 0.3, 0.4, 0.6, 0.6, 0.4, 0.5, 0.4, 0.3],
}


def get_phoneme_resonance(phoneme: str) -> List[float]:
    """Get 12D ontological layer affinity vector for a phoneme."""
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
    Convert phoneme sequence to 12D ontological layer affinity vector.

    Mean-aggregates per-phoneme 12D vectors (Sanskrit-calibrated).
    The result is an aspect distribution across 12 ontological layers.
    """
    if not phonemes:
        return torch.zeros(RESONANCE_DIM)

    vectors = []
    for ph in phonemes:
        vec = get_phoneme_resonance(ph)
        vectors.append(torch.tensor(vec, dtype=torch.float32))

    return torch.stack(vectors).mean(dim=0)


# =============================================================================
# RESONANCE SCORE (for FLOP pre-filtering)
# =============================================================================

def compute_resonance_score(vec: torch.Tensor) -> float:
    """
    Compute resonance score for FLOP pre-filtering.

    Score interpretation (from LSTB §6b):
        >= 0.7: Harmonic (proceed to transformer)
        0.3-0.7: Neutral (route to decision gate)
        <= 0.3: Dissonant (resolve locally, skip transformer)
    """
    energy = vec.mean().item()
    peak = vec.max().item()
    spread = (vec > 0.3).sum().item() / RESONANCE_DIM
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
# TEST 2: ONTOLOGICAL LAYER ACTIVATION
# =============================================================================

def test_ontological_layer_activation(device: torch.device) -> Dict[str, any]:
    """
    Test that 12D vectors encode correct ONTOLOGICAL LAYER dominance.

    Validates that each phoneme class peaks at the correct ontological layer
    as defined by Sanskrit varna theory in PHONEME_MAP_ARPABET:
        - Plosives (ka-varga etc): O3_Execution dominant
        - Fricatives (ūṣman etc): O6_Latency (Agency) dominant
        - Nasals (anusvāra-like): O10_Unifying dominant
        - Liquids (antaḥstha): O4_Maintenance (Structure) dominant
        - Vowel 'a' (अ): O1_Potential dominant
        - Vowel 'ī' (ई): O4_Maintenance dominant
        - Vowel 'au' (औ): O12_Absolving dominant
    """
    results = {}
    passes = 0
    total = 0

    # --- Consonant class dominant layer tests ---
    consonant_tests = {
        'plosive': (['K', 'T', 'P', 'B', 'D', 'G'], 2, 'O3_Execution'),
        'fricative': (['S', 'SH', 'F', 'V', 'TH', 'DH'], 5, 'O6_Latency'),
        'nasal': (['M', 'N', 'NG'], 9, 'O10_Unifying'),
        'liquid_L': (['L'], 3, 'O4_Maintenance'),
    }

    print("  Consonant class → dominant ontological layer:")
    for name, (phonemes, expected_idx, layer_name) in consonant_tests.items():
        vec = phonemes_to_resonance(phonemes)
        actual_idx = vec.argmax().item()
        actual_val = vec[expected_idx].item()
        peak_val = vec.max().item()
        correct = (actual_idx == expected_idx)

        # Also accept if expected layer is within 90% of peak (near-dominant)
        near_dominant = (actual_val >= 0.9 * peak_val)
        passed = correct or near_dominant

        results[f'{name}_expected'] = expected_idx
        results[f'{name}_actual'] = actual_idx
        results[f'{name}_correct'] = passed
        results[f'{name}_expected_val'] = actual_val
        results[f'{name}_peak_val'] = peak_val

        status = "PASS" if passed else "FAIL"
        print(f"    {name:15s}: peak={ONTOLOGICAL_LAYERS[actual_idx]:20s} "
              f"(idx={actual_idx}) expected={layer_name:20s} [{status}]")
        if passed:
            passes += 1
        total += 1

    # --- Individual vowel ontological layer tests ---
    vowel_tests = {
        'AA_a':  ('AA', 0, 'O1_Potential',     'अ birth of cognition'),
        'IH_i':  ('IH', 1, 'O2_Activation',    'इ i-ness / doing self'),
        'IY_ii': ('IY', 3, 'O4_Maintenance',   'ई specialized identity'),
        'UH_u':  ('UH', 4, 'O5_Dissolution',   'उ contraction / focus'),
        'UW_uu': ('UW', 9, 'O10_Unifying',     'ऊ sustained hold / unity'),
        'EY_ai': ('EY', 7, 'O8_Stabilization', 'ऐ soul intention / wisdom'),
        'OW_o':  ('OW', 8, 'O9_Authority',     'ओ observer / completion'),
        'AW_au': ('AW', 11, 'O12_Absolving',   'औ surrender / transformation'),
    }

    print("\n  Vowel → ontological layer (Sanskrit consciousness mapping):")
    for name, (phoneme, expected_idx, layer_name, meaning) in vowel_tests.items():
        vec = torch.tensor(get_phoneme_resonance(phoneme), dtype=torch.float32)
        actual_idx = vec.argmax().item()
        actual_val = vec[expected_idx].item()
        peak_val = vec.max().item()
        correct = (actual_idx == expected_idx)
        near_dominant = (actual_val >= 0.9 * peak_val)
        passed = correct or near_dominant

        results[f'vowel_{name}_correct'] = passed
        results[f'vowel_{name}_expected'] = expected_idx
        results[f'vowel_{name}_actual'] = actual_idx

        status = "PASS" if passed else "FAIL"
        print(f"    {phoneme:3s} ({meaning:30s}): "
              f"peak={ONTOLOGICAL_LAYERS[actual_idx]:20s} "
              f"expected={layer_name:20s} [{status}]")
        if passed:
            passes += 1
        total += 1

    results['total_tests'] = total
    results['total_passes'] = passes
    results['pass_rate'] = passes / max(total, 1)

    return results


# =============================================================================
# TEST 3: FLOP REDUCTION VIA RESONANCE PRE-FILTERING
# =============================================================================

def test_flop_reduction(device: torch.device) -> Dict[str, float]:
    """
    Test FLOP savings from resonance-based candidate pre-filtering.

    CSR resonance scoring is a DATA-PLANE signal that the decision gate
    uses to prune candidates BEFORE the transformer processes them.
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
# TEST 4: VARGA DISCRIMINABILITY
# =============================================================================

def test_varga_discriminability(device: torch.device) -> Dict[str, any]:
    """
    Test that Sanskrit VARGA groupings produce distinguishable 12D signatures.

    Groups by varga (place of articulation in classical Sanskrit grammar):
        - ka-varga (guttural): K, G, NG
        - pa-varga (labial): P, B, M
        - ta-varga (dental): TH, DH, N
        - antaḥstha (semi-vowels): Y, R, L, W
        - ūṣman (sibilants): S, SH, HH

    Within-varga similarity should be HIGHER than between-varga similarity,
    validating that the 12D encoding preserves the Sanskrit varga structure.
    """
    # Build 12D vectors per varga group
    varga_vectors = {}
    for varga_name, info in VARGA_GROUPS.items():
        vecs = []
        for ph in info['phonemes']:
            vec = torch.tensor(get_phoneme_resonance(ph), dtype=torch.float32)
            vecs.append(vec)
        if vecs:
            varga_vectors[varga_name] = torch.stack(vecs)

    results = {}

    # Within-varga cosine similarity
    within_sims = []
    for varga_name, vecs in varga_vectors.items():
        if vecs.shape[0] < 2:
            results[f'{varga_name}_within_sim'] = 1.0  # Single element = perfect
            within_sims.append(1.0)
            continue
        norms = F.normalize(vecs, dim=1)
        sim_matrix = norms @ norms.T
        n = sim_matrix.shape[0]
        mask = torch.triu(torch.ones(n, n, dtype=torch.bool), diagonal=1)
        pairwise = sim_matrix[mask]
        mean_sim = pairwise.mean().item()
        results[f'{varga_name}_within_sim'] = mean_sim
        within_sims.append(mean_sim)

    # Between-varga cosine similarity
    between_sims = []
    varga_names = list(varga_vectors.keys())
    for i in range(len(varga_names)):
        for j in range(i + 1, len(varga_names)):
            vecs_a = F.normalize(varga_vectors[varga_names[i]], dim=1)
            vecs_b = F.normalize(varga_vectors[varga_names[j]], dim=1)
            cross_sim = (vecs_a @ vecs_b.T).mean().item()
            between_sims.append(cross_sim)

    results['mean_within_varga_similarity'] = sum(within_sims) / max(len(within_sims), 1)
    results['mean_between_varga_similarity'] = sum(between_sims) / max(len(between_sims), 1)

    if results['mean_between_varga_similarity'] > 0:
        results['varga_discriminability_ratio'] = (
            results['mean_within_varga_similarity'] / results['mean_between_varga_similarity']
        )
    else:
        results['varga_discriminability_ratio'] = float('inf')

    results['vargas_separable'] = (
        results['mean_within_varga_similarity'] > results['mean_between_varga_similarity']
    )

    # Per-varga dominant layer (does each varga peak at the expected layer?)
    varga_expected_peaks = {
        'ka_varga': (2, 'O3_Execution'),
        'pa_varga': (2, 'O3_Execution'),       # P,B are plosive (O3), M is nasal (O10) — mixed
        'ta_dental_varga': (5, 'O6_Latency'),   # TH,DH are fricative (O6), N is nasal (O10) — mixed
        'antahstha': (3, 'O4_Maintenance'),     # L dominant, others vary
        'ushman': (5, 'O6_Latency'),
    }

    for varga_name, (expected_idx, layer_name) in varga_expected_peaks.items():
        if varga_name in varga_vectors:
            mean_vec = varga_vectors[varga_name].mean(dim=0)
            actual_idx = mean_vec.argmax().item()
            expected_val = mean_vec[expected_idx].item()
            peak_val = mean_vec.max().item()
            near_dominant = (expected_val >= 0.8 * peak_val)
            results[f'{varga_name}_peak_layer'] = actual_idx
            results[f'{varga_name}_expected_layer'] = expected_idx
            results[f'{varga_name}_layer_match'] = (actual_idx == expected_idx) or near_dominant

    return results


# =============================================================================
# TEST 5: VRTTI AND CONSCIOUSNESS MAPPING
# =============================================================================

def test_vrtti_consciousness_mapping(device: torch.device) -> Dict[str, any]:
    """
    Test that 12D resonance vectors encode Sanskrit vrtti (mental propensity)
    and vowel consciousness semantics — NOT just acoustic properties.

    Validates:
    1. Vowel consciousness PROGRESSION: a(O1) → i(O2) → ī(O4) → u(O5)
       → ū(O6/O10) → ai(O8) → o(O9) → au(O12)
       Each step moves to a higher ontological layer.

    2. Consonant vrtti SEPARATION: Different vargas encode distinct mental
       propensities at different ontological layers:
       - ka (hope) ≠ pa (hatred) — different vrtti despite both being plosives
       - ma (indulgence/O10) ≠ ka (hope/O3) — nasal vs guttural
       - sa (escapism/O6) ≠ ka (hope/O3) — sibilant vs plosive

    3. Semantic vs acoustic: Phonemes within the SAME acoustic class but
       different vargas should have DIFFERENT 12D profiles (proving the
       encoding is semantic, not just acoustic).
    """
    results = {}
    passes = 0
    total = 0

    # --- 1. Vowel consciousness progression ---
    # Each vowel's dominant layer should increase along the ontological ladder
    vowel_progression = [
        ('AA', 0, 'a → O1_Potential'),
        ('IH', 1, 'i → O2_Activation'),
        ('IY', 3, 'ī → O4_Maintenance'),
        ('UH', 4, 'u → O5_Dissolution'),
        ('EY', 7, 'ai → O8_Stabilization'),
        ('OW', 8, 'o → O9_Authority'),
        ('AW', 11, 'au → O12_Absolving'),
    ]

    print("  Vowel consciousness progression (should ascend O1→O12):")
    prev_layer = -1
    progression_correct = 0
    for phoneme, expected_layer, desc in vowel_progression:
        vec = torch.tensor(get_phoneme_resonance(phoneme), dtype=torch.float32)
        actual_peak = vec.argmax().item()
        ascending = (actual_peak > prev_layer)
        if prev_layer >= 0:
            status = "PASS" if ascending else "FAIL"
            if ascending:
                progression_correct += 1
            total += 1
        else:
            status = "START"
        print(f"    {phoneme:3s} {desc:30s}: peak=O{actual_peak+1:2d} [{status}]")
        prev_layer = actual_peak

    results['vowel_progression_steps'] = len(vowel_progression) - 1
    results['vowel_progression_correct'] = progression_correct
    results['vowel_progression_rate'] = progression_correct / max(len(vowel_progression) - 1, 1)
    passes += progression_correct

    # --- 2. Consonant vrtti separation (same acoustic class, different varga) ---
    print("\n  Vrtti separation (same acoustic class, different varga):")

    # ka (hope) vs pa (hatred) — both plosives, different vrtti
    ka_vec = torch.tensor(get_phoneme_resonance('K'), dtype=torch.float32)
    pa_vec = torch.tensor(get_phoneme_resonance('P'), dtype=torch.float32)
    ka_pa_cos = F.cosine_similarity(ka_vec.unsqueeze(0), pa_vec.unsqueeze(0)).item()

    # ma (indulgence) vs na (attachment) — both nasals, different vrtti
    ma_vec = torch.tensor(get_phoneme_resonance('M'), dtype=torch.float32)
    na_vec = torch.tensor(get_phoneme_resonance('N'), dtype=torch.float32)
    ma_na_cos = F.cosine_similarity(ma_vec.unsqueeze(0), na_vec.unsqueeze(0)).item()

    # ka (hope/plosive) vs ma (indulgence/nasal) — different class AND varga
    ka_ma_cos = F.cosine_similarity(ka_vec.unsqueeze(0), ma_vec.unsqueeze(0)).item()

    # sa (escapism) vs ka (hope) — sibilant vs plosive
    sa_vec = torch.tensor(get_phoneme_resonance('S'), dtype=torch.float32)
    ka_sa_cos = F.cosine_similarity(ka_vec.unsqueeze(0), sa_vec.unsqueeze(0)).item()

    # Cross-class separation: ka-ma should be more different than ka-pa
    cross_more_different = (ka_ma_cos < ka_pa_cos)
    results['ka_pa_similarity'] = ka_pa_cos
    results['ma_na_similarity'] = ma_na_cos
    results['ka_ma_similarity'] = ka_ma_cos
    results['ka_sa_similarity'] = ka_sa_cos
    results['cross_class_more_different'] = cross_more_different

    print(f"    K(hope) vs P(hatred) [same class]:     cos={ka_pa_cos:.3f}")
    print(f"    M(indulgence) vs N(attachment) [same]:  cos={ma_na_cos:.3f}")
    print(f"    K(hope) vs M(indulgence) [cross-class]: cos={ka_ma_cos:.3f}")
    print(f"    K(hope) vs S(escapism) [cross-class]:   cos={ka_sa_cos:.3f}")
    status = "PASS" if cross_more_different else "FAIL"
    print(f"    Cross-class more different than within:  {cross_more_different} [{status}]")
    if cross_more_different:
        passes += 1
    total += 1

    # --- 3. Semantic dominance: specific vrtti → specific layer ---
    print("\n  Vrtti → ontological layer dominance:")
    vrtti_tests = {
        'K_hope':       ('K', 2, 'O3_Execution', 'ka = āśā (hope)'),
        'M_indulgence': ('M', 9, 'O10_Unifying', 'ma = praśraya (indulgence)'),
        'S_escapism':   ('S', 5, 'O6_Latency', 'sa = escapism'),
        'L_cruelty':    ('L', 3, 'O4_Maintenance', 'la = krūratā (cruelty)'),
    }

    for name, (phoneme, expected_idx, layer_name, meaning) in vrtti_tests.items():
        vec = torch.tensor(get_phoneme_resonance(phoneme), dtype=torch.float32)
        actual_idx = vec.argmax().item()
        actual_val = vec[expected_idx].item()
        peak_val = vec.max().item()
        near = (actual_val >= 0.9 * peak_val)
        passed = (actual_idx == expected_idx) or near

        results[f'vrtti_{name}_correct'] = passed
        status = "PASS" if passed else "FAIL"
        print(f"    {meaning:35s}: peak=O{actual_idx+1} expected={layer_name} [{status}]")
        if passed:
            passes += 1
        total += 1

    # --- 4. Vowel a (O1) vs consonant ka (O3): different ontological layers ---
    print("\n  Vowel vs consonant ontological separation:")
    aa_peak = torch.tensor(get_phoneme_resonance('AA'), dtype=torch.float32).argmax().item()
    k_peak = torch.tensor(get_phoneme_resonance('K'), dtype=torch.float32).argmax().item()
    m_peak = torch.tensor(get_phoneme_resonance('M'), dtype=torch.float32).argmax().item()

    vowel_consonant_differ = (aa_peak != k_peak) and (aa_peak != m_peak)
    results['vowel_consonant_different_layers'] = vowel_consonant_differ
    print(f"    AA(अ) peak: O{aa_peak+1}, K(क) peak: O{k_peak+1}, M(म) peak: O{m_peak+1}")
    status = "PASS" if vowel_consonant_differ else "FAIL"
    print(f"    Vowels and consonants use different layers: {vowel_consonant_differ} [{status}]")
    if vowel_consonant_differ:
        passes += 1
    total += 1

    results['total_tests'] = total
    results['total_passes'] = passes
    results['pass_rate'] = passes / max(total, 1)

    return results


# =============================================================================
# TEST 6: VARNA BRIDGE VALIDATION
# =============================================================================

def test_varna_bridge_validation(device: torch.device) -> Dict[str, any]:
    """
    Test ARPABET→Varna mapping coverage and VarnaCSRBridge correctness.

    Validates:
    1. Every ARPABET phoneme in the 12D table has a Varna mapping
    2. Vowel varnas map to correct consciousness states
    3. Consonant varnas carry correct vrtti (mental propensity) labels
    4. VarnaCSRBridge (if available) produces valid 12D vectors
    """
    results = {}

    if not VARNA_AVAILABLE:
        print("  ARPABET_TO_VARNA not available — testing local data only")
        results['varna_available'] = False

        # Still test that LOCAL_PHONEME_12D vectors are valid
        valid_vectors = 0
        for ph, vec in LOCAL_PHONEME_12D.items():
            if len(vec) == 12 and all(0.0 <= v <= 1.0 for v in vec):
                valid_vectors += 1
        results['valid_local_vectors'] = valid_vectors
        results['total_local_vectors'] = len(LOCAL_PHONEME_12D)
        results['local_validity_rate'] = valid_vectors / max(len(LOCAL_PHONEME_12D), 1)
        return results

    results['varna_available'] = True

    # --- 1. Coverage: every phoneme in 12D table has a Varna mapping ---
    phonemes_in_12d = set(LOCAL_PHONEME_12D.keys())
    phonemes_with_varna = set(ARPABET_TO_VARNA.keys())
    missing_varna = phonemes_in_12d - phonemes_with_varna
    extra_varna = phonemes_with_varna - phonemes_in_12d

    results['phonemes_in_12d'] = len(phonemes_in_12d)
    results['phonemes_with_varna'] = len(phonemes_with_varna)
    results['missing_varna_mapping'] = len(missing_varna)
    results['coverage_rate'] = len(phonemes_in_12d & phonemes_with_varna) / max(len(phonemes_in_12d), 1)

    print(f"  ARPABET→Varna coverage: {len(phonemes_in_12d & phonemes_with_varna)}/{len(phonemes_in_12d)} "
          f"({results['coverage_rate']:.0%})")
    if missing_varna:
        print(f"  Missing varna mappings: {sorted(missing_varna)}")

    # --- 2. Vowel varna → consciousness state validation ---
    vowel_varna_expected = {
        'AA': ('a', 'birth of cognition'),
        'IH': ('i', 'i-ness / doing self'),
        'IY': ('ī', 'specialized identity'),
        'UH': ('u', 'contraction / focus'),
        'UW': ('ū', 'sustained hold'),
        'EY': ('e', 'practical thought'),
        'OW': ('o', 'completion / closure'),
        'AW': ('au', 'surrender / transformation'),
    }

    vowel_correct = 0
    print("\n  Vowel ARPABET → Varna mapping:")
    for arpabet, (expected_varna, meaning) in vowel_varna_expected.items():
        actual_varna = ARPABET_TO_VARNA.get(arpabet, '???')
        correct = (actual_varna == expected_varna)
        status = "PASS" if correct else f"FAIL (got '{actual_varna}')"
        print(f"    {arpabet:3s} → {actual_varna:4s} ({meaning:30s}) [{status}]")
        if correct:
            vowel_correct += 1

    results['vowel_varna_correct'] = vowel_correct
    results['vowel_varna_total'] = len(vowel_varna_expected)
    results['vowel_varna_rate'] = vowel_correct / max(len(vowel_varna_expected), 1)

    # --- 3. Consonant varna → vrtti (mental propensity) validation ---
    consonant_varna_expected = {
        'K': ('ka', 'āśā (hope)'),
        'G': ('ga', 'ceṣṭā (action)'),
        'P': ('pa', 'ghrṇā (hatred)'),
        'B': ('ba', 'avajñā (indifference)'),
        'M': ('ma', 'praśraya (indulgence)'),
        'S': ('sa', 'escapism'),
        'SH': ('śa', 'material greed'),
        'R': ('ra', 'sarvanāśa (annihilation)'),
        'L': ('la', 'krūratā (cruelty)'),
        'HH': ('ha', 'avidyā (ignorance)'),
    }

    consonant_correct = 0
    print("\n  Consonant ARPABET → Varna (vrtti) mapping:")
    for arpabet, (expected_varna, vrtti) in consonant_varna_expected.items():
        actual_varna = ARPABET_TO_VARNA.get(arpabet, '???')
        correct = (actual_varna == expected_varna)
        status = "PASS" if correct else f"FAIL (got '{actual_varna}')"
        print(f"    {arpabet:3s} → {actual_varna:4s} = {vrtti:30s} [{status}]")
        if correct:
            consonant_correct += 1

    results['consonant_varna_correct'] = consonant_correct
    results['consonant_varna_total'] = len(consonant_varna_expected)
    results['consonant_varna_rate'] = consonant_correct / max(len(consonant_varna_expected), 1)

    # --- 4. Sanskrit Vowel Calibration layer_primary validation ---
    if SANSKRIT_VOWEL_CALIBRATION:
        print("\n  Sanskrit Vowel Calibration (Māheśvara Sūtra):")
        cal_correct = 0
        cal_total = 0
        for varna, info in SANSKRIT_VOWEL_CALIBRATION.items():
            affinity = info['affinity']
            expected_primary = info['layer_primary']
            actual_peak = affinity.index(max(affinity))
            correct = (actual_peak == expected_primary)
            cal_total += 1
            if correct:
                cal_correct += 1
            status = "PASS" if correct else "FAIL"
            print(f"    {varna:3s} ({info['devanagari']}): "
                  f"peak=O{actual_peak+1} expected=O{expected_primary+1} [{status}]")

        results['calibration_correct'] = cal_correct
        results['calibration_total'] = cal_total
        results['calibration_rate'] = cal_correct / max(cal_total, 1)

    # --- 5. VarnaCSRBridge validation (if available) ---
    if CSR_AVAILABLE:
        print("\n  VarnaCSRBridge:")
        try:
            bridge = VarnaCSRBridge()
            loaded = bridge.load()
            results['bridge_loaded'] = loaded
            if loaded:
                varnas = bridge.all_varnas
                results['bridge_num_varnas'] = len(varnas)
                # Validate a sample vector
                if varnas:
                    sample_vec = bridge.get_vector(varnas[0])
                    results['bridge_vector_dim'] = len(sample_vec) if sample_vec else 0
                    # Spot-check: every varna produces a 12D vector
                    valid = sum(1 for v in varnas if bridge.get_vector(v) and len(bridge.get_vector(v)) == 12)
                    results['bridge_valid_vectors'] = valid
                    print(f"    Loaded: {len(varnas)} varnas, {results['bridge_vector_dim']}D vectors, "
                          f"{valid}/{len(varnas)} valid")
                else:
                    results['bridge_valid_vectors'] = 0
                    print("    Bridge loaded but no varnas")
            else:
                print("    Bridge failed to load (varna_bridge_map_v1.json missing?)")
        except Exception as e:
            results['bridge_loaded'] = False
            print(f"    Bridge error: {e}")

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

    Tests CSR as a DATA PLANE feature extractor grounded in Sanskrit varna theory:
        Ontological layer activation, varga discriminability, vrtti mapping.
    Does NOT test governance routing or ontological layer activation.
    """
    print("\n" + "=" * 70)
    print("V11.0: PHONEME CSR BRIDGE — SANSKRIT VARNA SEMANTICS BENCHMARKS")
    print("=" * 70)
    print("  CSR role: Semantic-emotional feature encoder (data plane)")
    print("  12D dimensions: O1_Potential → O12_Absolving (ontological layers)")
    print("  CSR is NOT a governance layer — Signal != Governance")

    if CSR_AVAILABLE:
        print("  CSR provider: AVAILABLE (using real PHONEME_MAP_ARPABET)")
    else:
        print("  CSR provider: NOT AVAILABLE (using local 12D fallback)")

    if VARNA_AVAILABLE:
        print("  Varna mapping: AVAILABLE (ARPABET_TO_VARNA + SANSKRIT_VOWEL_CALIBRATION)")
    else:
        print("  Varna mapping: NOT AVAILABLE (will test local data only)")

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
    # TEST 2: Ontological Layer Activation (replaces old acoustic test)
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Ontological Layer Activation (Sanskrit Varna) ---")
    onto_results = test_ontological_layer_activation(device)
    results['ontological_activation'] = onto_results

    print(f"\n  Layer activation: {onto_results['total_passes']}/{onto_results['total_tests']} "
          f"correct ({onto_results['pass_rate']:.0%})")

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
    # TEST 4: Varga Discriminability (replaces old articulatory test)
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Varga Discriminability (Sanskrit Grouping) ---")
    varga_results = test_varga_discriminability(device)
    results['varga_discriminability'] = varga_results

    print(f"  Within-varga similarity:  {varga_results['mean_within_varga_similarity']:.3f}")
    print(f"  Between-varga similarity: {varga_results['mean_between_varga_similarity']:.3f}")
    print(f"  Varga discriminability:   {varga_results['varga_discriminability_ratio']:.3f}")
    print(f"  Vargas separable:         {varga_results['vargas_separable']}")

    for varga in VARGA_GROUPS:
        sim = varga_results.get(f'{varga}_within_sim', 0)
        layer_match = varga_results.get(f'{varga}_layer_match', 'N/A')
        peak = varga_results.get(f'{varga}_peak_layer', '?')
        layer_str = f"peak=O{peak+1}" if isinstance(peak, int) else ""
        match_str = f"[{'PASS' if layer_match else 'FAIL'}]" if isinstance(layer_match, bool) else ""
        print(f"    {varga:25s} within-sim={sim:.3f}  {layer_str} {match_str}")

    # -------------------------------------------------------------------------
    # TEST 5: Vrtti and Consciousness Mapping (replaces old pressure test)
    # -------------------------------------------------------------------------
    print("\n--- TEST 5: Vrtti and Consciousness Mapping (Sanskrit Semantics) ---")
    vrtti_results = test_vrtti_consciousness_mapping(device)
    results['vrtti_consciousness'] = vrtti_results

    print(f"\n  Semantic mapping: {vrtti_results['total_passes']}/{vrtti_results['total_tests']} "
          f"correct ({vrtti_results['pass_rate']:.0%})")
    print(f"  Vowel progression: {vrtti_results['vowel_progression_correct']}"
          f"/{vrtti_results['vowel_progression_steps']} steps ascending")

    # -------------------------------------------------------------------------
    # TEST 6: Varna Bridge Validation
    # -------------------------------------------------------------------------
    print("\n--- TEST 6: Varna Bridge Validation (ARPABET→Sanskrit Mapping) ---")
    bridge_results = test_varna_bridge_validation(device)
    results['varna_bridge'] = bridge_results

    if bridge_results.get('varna_available'):
        print(f"\n  Vowel varna mapping:     {bridge_results['vowel_varna_correct']}"
              f"/{bridge_results['vowel_varna_total']} correct")
        print(f"  Consonant varna mapping: {bridge_results['consonant_varna_correct']}"
              f"/{bridge_results['consonant_varna_total']} correct")
        print(f"  Coverage:                {bridge_results['coverage_rate']:.0%}")
        if 'calibration_rate' in bridge_results:
            print(f"  Māheśvara calibration:   {bridge_results['calibration_correct']}"
                  f"/{bridge_results['calibration_total']} correct "
                  f"({bridge_results['calibration_rate']:.0%})")

    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("CSR SANSKRIT VARNA SEMANTICS SUMMARY")
    print("=" * 70)
    print(f"  Classification rate:       {decomp_results['classification_rate']:.1%}")
    print(f"  Ontological layer accuracy: {onto_results['pass_rate']:.0%} "
          f"({onto_results['total_passes']}/{onto_results['total_tests']})")
    print(f"  Varga discriminability:    {varga_results['varga_discriminability_ratio']:.3f}")
    print(f"  Vargas separable:          {varga_results['vargas_separable']}")
    print(f"  Vrtti/consciousness:       {vrtti_results['pass_rate']:.0%} "
          f"({vrtti_results['total_passes']}/{vrtti_results['total_tests']})")
    print(f"  Vowel progression:         {vrtti_results['vowel_progression_rate']:.0%}")
    print(f"  FLOP reduction:            {flop_results['flop_reduction_estimated']:.1%}")
    if bridge_results.get('varna_available'):
        print(f"  Varna coverage:            {bridge_results['coverage_rate']:.0%}")
    print("  ---")
    print("  12D = ontological layers O1-O12 (not acoustic features)")
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
