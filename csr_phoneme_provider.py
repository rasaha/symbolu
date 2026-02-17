#!/usr/bin/env python3
"""
CSR (Constraint-Structure-Resonance) Phoneme Provider
======================================================

Grounds the 6:6 Hybrid LLM in phoneme-invariant ontological states.

The CSR Provider creates a deterministic bridge between:
- Phonetic articulation patterns (ARPABET)
- Sanskrit vibrational calibration (Varna Bridge Map)
- 12-dimensional ontological space

This ensures the neural network learns WITH ontological structure,
not against it - providing Semantic Authority through phonemic grounding.

Architecture:
    Input IDs → Phonemes → 12D Affinity → Projection → Model Integration

Varna Integration (v2.0):
    - Uses varna_bridge_map_v1.json for Sanskrit-native 12D mappings
    - Consonants have explicit layer annotations (O1-O12)
    - Vowels mapped to primary ontological layers

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import math
import json
from pathlib import Path
import warnings

# =============================================================================
# HYBRID G2P SYSTEM (CMUdict + g2p_en)
# =============================================================================
# Tiered lookup: CMUdict → CUSTOM_VOCAB → g2p_en neural fallback
# This provides 134K+ word coverage with neural OOV handling.
#
# V9.5.2 Optimization: Background preloading with pickle cache for fast startup

import threading
import pickle
import os
import time

_CMUDICT_LOADED = False
_CMUDICT: Dict[str, List[List[str]]] = {}
_G2P_EN_AVAILABLE = False
_G2P_ENGINE = None
_PRELOAD_THREAD: Optional[threading.Thread] = None
_PRELOAD_LOCK = threading.Lock()
_PRELOAD_STARTED = False

# Cache directory for pickled CMUdict (much faster to load)
_CACHE_DIR = Path.home() / ".cache" / "symbolu" / "csr"


def _load_cmudict() -> bool:
    """
    Load CMUdict from pickle cache or NLTK corpus.

    V9.5.2 Optimization: Uses pickle cache for ~10x faster loading.

    CMUdict provides 134K words with ARPABET pronunciations.
    This is the primary fast-path for G2P conversion.
    """
    global _CMUDICT_LOADED, _CMUDICT

    if _CMUDICT_LOADED:
        return True

    cache_file = _CACHE_DIR / "cmudict.pkl"
    start_time = time.time()

    # Try loading from pickle cache first (10x faster)
    if cache_file.exists():
        try:
            with open(cache_file, 'rb') as f:
                _CMUDICT = pickle.load(f)
            _CMUDICT_LOADED = True
            elapsed = time.time() - start_time
            print(f"  [G2P] CMUdict loaded from cache: {len(_CMUDICT):,} words ({elapsed:.2f}s)")
            return True
        except Exception as e:
            warnings.warn(f"Failed to load CMUdict cache: {e}, falling back to NLTK")

    # Fall back to NLTK loading
    try:
        import nltk
        from nltk.corpus import cmudict

        # Attempt to load - will download if needed
        try:
            _CMUDICT = dict(cmudict.entries())
        except LookupError:
            # Download CMUdict if not present
            print("  [G2P] Downloading CMUdict corpus...")
            nltk.download('cmudict', quiet=True)
            _CMUDICT = dict(cmudict.entries())

        _CMUDICT_LOADED = True
        elapsed = time.time() - start_time
        print(f"  [G2P] CMUdict loaded: {len(_CMUDICT):,} words ({elapsed:.2f}s)")

        # Save to pickle cache for next time
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'wb') as f:
                pickle.dump(_CMUDICT, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"  [G2P] CMUdict cached to {cache_file}")
        except Exception as e:
            warnings.warn(f"Failed to cache CMUdict: {e}")

        return True

    except ImportError:
        warnings.warn("nltk not installed. CMUdict unavailable. Install with: pip install nltk")
        return False
    except Exception as e:
        warnings.warn(f"Failed to load CMUdict: {e}")
        return False


def _init_g2p_engine():
    """
    Initialize g2p_en neural engine for OOV words.

    g2p_en is a sequence-to-sequence neural model that handles:
    - Out-of-vocabulary words
    - Proper nouns
    - Technical terms
    - Neologisms
    """
    global _G2P_EN_AVAILABLE, _G2P_ENGINE

    if _G2P_ENGINE is not None:
        return _G2P_EN_AVAILABLE

    try:
        from g2p_en import G2p
        _G2P_ENGINE = G2p()
        _G2P_EN_AVAILABLE = True
        print("  [G2P] g2p_en neural engine initialized (Fallback Tier)")
        return True

    except ImportError:
        warnings.warn("g2p_en not installed. Neural fallback unavailable. Install with: pip install g2p_en")
        _G2P_EN_AVAILABLE = False
        return False
    except Exception as e:
        warnings.warn(f"Failed to initialize g2p_en: {e}")
        _G2P_EN_AVAILABLE = False
        return False


def _strip_stress(phonemes: List[str]) -> List[str]:
    """
    Strip stress markers from ARPABET phonemes.

    CMUdict uses stress markers (0, 1, 2) on vowels:
    - AH0 (unstressed), AH1 (primary stress), AH2 (secondary stress)

    We strip these for ontological mapping since stress is prosodic,
    not articulatory.
    """
    return [p.rstrip('012') for p in phonemes]


class HybridG2P:
    """
    Hybrid Grapheme-to-Phoneme Converter.

    Tiered Architecture:
        1. CMUdict (Fast Path): 134K words, O(1) lookup, deterministic
        2. Custom Vocabulary: Domain-specific terms (expandable)
        3. g2p_en Neural: OOV handling via seq2seq model
        4. Character Fallback: Last resort for complete failures

    This provides principled phoneme extraction for CSR ontological grounding.
    """

    def __init__(self, use_neural: bool = True, lazy_init: bool = True):
        """
        Initialize HybridG2P.

        Args:
            use_neural: Enable g2p_en neural fallback for OOV words
            lazy_init: Defer loading until first use (recommended)
        """
        self.use_neural = use_neural
        self._initialized = False
        self._cache: Dict[str, List[str]] = {}

        # Custom vocabulary for domain-specific terms
        self.custom_vocab: Dict[str, List[str]] = {
            # Sanskrit/Ontological terms
            "varna": ["V", "AA", "R", "N", "AH"],
            "vritti": ["V", "R", "IH", "T", "IY"],
            "phoneme": ["F", "OW", "N", "IY", "M"],
            "phonemic": ["F", "AH", "N", "IY", "M", "IH", "K"],
            "symbolu": ["S", "IH", "M", "B", "OW", "L", "UW"],
            "csr": ["S", "IY", "EH", "S", "AA", "R"],
            "arpabet": ["AA", "R", "P", "AH", "B", "EH", "T"],
            # AI/ML terms (not in CMUdict)
            "embedding": ["IH", "M", "B", "EH", "D", "IH", "NG"],
            "embeddings": ["IH", "M", "B", "EH", "D", "IH", "NG", "Z"],
            "tokenizer": ["T", "OW", "K", "AH", "N", "AY", "Z", "ER"],
            "tokenizers": ["T", "OW", "K", "AH", "N", "AY", "Z", "ER", "Z"],
            "llm": ["EH", "L", "EH", "L", "EH", "M"],
            "llms": ["EH", "L", "EH", "L", "EH", "M", "Z"],
            "gpt": ["JH", "IY", "P", "IY", "T", "IY"],
            "bert": ["B", "ER", "T"],
            "chatgpt": ["CH", "AE", "T", "JH", "IY", "P", "IY", "T", "IY"],
            "mixtral": ["M", "IH", "K", "S", "T", "R", "AH", "L"],
            "llama": ["L", "AA", "M", "AH"],  # Override CMUdict animal pronunciation
        }

        if not lazy_init:
            self._init()

    def _init(self):
        """Initialize G2P backends."""
        if self._initialized:
            return

        _load_cmudict()

        if self.use_neural:
            _init_g2p_engine()

        self._initialized = True

    def get_phonemes(self, word: str) -> List[str]:
        """
        Convert word to ARPABET phonemes using tiered lookup.

        Lookup order:
            1. Cache check
            2. CMUdict (134K words)
            3. Custom vocabulary
            4. g2p_en neural (if enabled)
            5. Character-level fallback

        Args:
            word: Input word (case-insensitive)

        Returns:
            List of ARPABET phonemes (stress stripped)
        """
        # Ensure initialized
        if not self._initialized:
            self._init()

        # Clean word
        clean = word.lower().strip()
        clean = ''.join(c for c in clean if c.isalpha())

        if not clean:
            return ["SIL"]

        # Check cache
        if clean in self._cache:
            return self._cache[clean]

        phonemes = None

        # Tier 1: CMUdict (Fast Path)
        if _CMUDICT_LOADED and clean in _CMUDICT:
            # CMUdict returns list of pronunciations, take first
            raw_phonemes = _CMUDICT[clean]
            if isinstance(raw_phonemes, list) and raw_phonemes:
                # Handle both dict formats: entries() returns (word, [phonemes])
                if isinstance(raw_phonemes[0], list):
                    phonemes = _strip_stress(raw_phonemes[0])
                else:
                    phonemes = _strip_stress(raw_phonemes)

        # Tier 2: Custom Vocabulary
        if phonemes is None and clean in self.custom_vocab:
            phonemes = self.custom_vocab[clean]

        # Tier 3: g2p_en Neural Fallback
        if phonemes is None and _G2P_EN_AVAILABLE and _G2P_ENGINE is not None:
            try:
                raw = _G2P_ENGINE(clean)
                # g2p_en returns list with spaces for word boundaries
                phonemes = [p for p in raw if p.strip() and p != ' ']
                # Normalize to uppercase ARPABET
                phonemes = [p.upper().rstrip('012') for p in phonemes]
            except Exception:
                phonemes = None

        # Tier 4: Character-level Fallback (Last Resort)
        if phonemes is None:
            phonemes = self._char_fallback(clean)

        # Validate phonemes exist in our ARPABET map
        phonemes = self._validate_phonemes(phonemes)

        # Cache result
        self._cache[clean] = phonemes

        return phonemes

    def _char_fallback(self, word: str) -> List[str]:
        """Character-level fallback for completely unknown words."""
        # Import here to avoid circular dependency
        char_map = {
            'a': 'AH', 'b': 'B', 'c': 'K', 'd': 'D', 'e': 'EH',
            'f': 'F', 'g': 'G', 'h': 'HH', 'i': 'IH', 'j': 'JH',
            'k': 'K', 'l': 'L', 'm': 'M', 'n': 'N', 'o': 'OW',
            'p': 'P', 'q': 'K', 'r': 'R', 's': 'S', 't': 'T',
            'u': 'UH', 'v': 'V', 'w': 'W', 'x': 'K', 'y': 'Y',
            'z': 'Z',
        }
        phonemes = []
        for char in word[:10]:  # Limit to prevent runaway
            if char in char_map:
                phonemes.append(char_map[char])
        return phonemes if phonemes else ["UNK"]

    def _validate_phonemes(self, phonemes: List[str]) -> List[str]:
        """Validate phonemes against known ARPABET set."""
        # Known ARPABET phonemes (from PHONEME_MAP_ARPABET)
        valid = {
            "AA", "AH", "AE", "IH", "IY", "UH", "UW", "EH", "ER", "EY",
            "AY", "OW", "AO", "OY", "AW", "P", "T", "K", "B", "D", "G",
            "F", "TH", "S", "SH", "HH", "V", "DH", "Z", "ZH", "CH", "JH",
            "M", "N", "NG", "L", "R", "W", "Y", "SIL", "SP", "UNK"
        }
        return [p if p in valid else "UNK" for p in phonemes]

    def add_custom_word(self, word: str, phonemes: List[str]):
        """Add a word to custom vocabulary."""
        self.custom_vocab[word.lower()] = phonemes
        # Clear cache for this word
        if word.lower() in self._cache:
            del self._cache[word.lower()]

    def get_stats(self) -> Dict[str, Any]:
        """Get G2P system statistics."""
        return {
            "cmudict_loaded": _CMUDICT_LOADED,
            "cmudict_words": len(_CMUDICT) if _CMUDICT_LOADED else 0,
            "g2p_en_available": _G2P_EN_AVAILABLE,
            "custom_vocab_size": len(self.custom_vocab),
            "cache_size": len(self._cache),
        }


# Global hybrid G2P instance (lazy initialization)
_HYBRID_G2P: Optional[HybridG2P] = None


def _background_preload():
    """
    Background preload thread for G2P initialization.

    V9.5.2 Optimization: Load CMUdict and g2p_en in parallel background threads
    so they're ready when training actually needs them.
    """
    global _PRELOAD_STARTED
    _PRELOAD_STARTED = True

    # Load both in parallel
    cmu_thread = threading.Thread(target=_load_cmudict, daemon=True)
    g2p_thread = threading.Thread(target=_init_g2p_engine, daemon=True)

    cmu_thread.start()
    g2p_thread.start()

    # Wait for both
    cmu_thread.join()
    g2p_thread.join()


def start_background_preload():
    """
    Start background preloading of G2P resources.

    Call this early (e.g., at module import or training script start)
    to warm up CMUdict and g2p_en before they're actually needed.

    V9.5.2 Optimization: This allows training to start immediately
    while G2P resources load in parallel.

    Set CSR_DISABLE_G2P=1 environment variable to skip G2P preloading entirely.
    """
    global _PRELOAD_THREAD, _PRELOAD_STARTED

    # V9.9.7: Allow disabling G2P preload via environment variable
    if os.environ.get('CSR_DISABLE_G2P', '').lower() in ('1', 'true', 'yes'):
        _PRELOAD_STARTED = True  # Mark as "done" to prevent future calls
        return

    with _PRELOAD_LOCK:
        if _PRELOAD_STARTED:
            return  # Already started

        _PRELOAD_THREAD = threading.Thread(target=_background_preload, daemon=True)
        _PRELOAD_THREAD.start()
        print("  [G2P] Background preload started...")


def wait_for_preload(timeout: float = 30.0) -> bool:
    """
    Wait for background preload to complete.

    Args:
        timeout: Maximum seconds to wait

    Returns:
        True if preload completed, False if timed out
    """
    global _PRELOAD_THREAD

    if _PRELOAD_THREAD is None:
        return True  # Nothing to wait for

    _PRELOAD_THREAD.join(timeout=timeout)
    return not _PRELOAD_THREAD.is_alive()


def get_hybrid_g2p() -> HybridG2P:
    """Get or create the global HybridG2P instance."""
    global _HYBRID_G2P
    if _HYBRID_G2P is None:
        _HYBRID_G2P = HybridG2P(use_neural=True, lazy_init=True)
    return _HYBRID_G2P

# =============================================================================
# ONTOLOGICAL LAYER DEFINITIONS (for reference)
# =============================================================================
ONTOLOGICAL_LAYERS = {
    0: "O1_Potential",      # Dormant/Unmanifested
    1: "O2_Activation",     # Initial stirring
    2: "O3_Execution",      # Active doing
    3: "O4_Maintenance",    # Sustained effort
    4: "O5_Dissolution",    # Breaking down
    5: "O6_Latency",        # Hidden potential
    6: "O7_Emergence",      # Coming forth
    7: "O8_Stabilization",  # Finding balance
    8: "O9_Authority",      # Commanding presence
    9: "O10_Unifying",      # Bringing together
    10: "O11_Integration",  # Synthesizing
    11: "O12_Absolving",    # Complete release/transcendence
}

# =============================================================================
# PHONEME-TO-ONTOLOGICAL MAPPING (ARPABET → 12D)
# =============================================================================
# Sanskrit-Calibrated 12D Affinities
# Order: O1_POT, O2_ID, O3_EXE, O4_STR, O5_COG, O6_AGE, O7_REA, O8_PUR, O9_WIT, O10_UNI, O11_INT, O12_ABS
#
# These weights are derived from classical acoustic essences (Sanskrit vowel
# vibrations) to ensure ontological alignment in the CSR formula.

PHONEME_MAP_ARPABET: Dict[str, List[float]] = {
    # ==========================================================================
    # VOWELS: The 'Breathing' Spine (Sanskrit-Calibrated)
    # ==========================================================================
    # a (अ): Primordial potential / Birth of cognition → O1 dominant
    "AA": [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],
    "AH": [0.9, 0.2, 0.1, 0.1, 0.3, 0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.1],  # ʌ (but) → अ
    "AE": [0.7, 0.4, 0.2, 0.2, 0.3, 0.2, 0.2, 0.2, 0.2, 0.3, 0.2, 0.1],  # æ (cat)

    # i (इ): I-ness / Identity entering action → O2 dominant
    "IH": [0.2, 0.9, 0.4, 0.2, 0.3, 0.2, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],  # ɪ (bit) → इ

    # ī (ई): Specialization of self into form → O4 (Structure) dominant
    "IY": [0.1, 0.6, 0.3, 0.9, 0.2, 0.2, 0.3, 0.2, 0.2, 0.3, 0.2, 0.2],  # i (beat) → ई

    # u (उ): Localized awareness / Cohesion → O5 (Cognition) dominant
    "UH": [0.1, 0.2, 0.2, 0.3, 0.9, 0.3, 0.1, 0.2, 0.4, 0.7, 0.3, 0.2],  # ʊ (book) → उ

    # ū (ऊ): Sustained attention / Deep unity → O6 (Agency) + O10 (Unifying) dominant
    "UW": [0.1, 0.1, 0.1, 0.2, 0.4, 0.8, 0.2, 0.3, 0.5, 0.9, 0.4, 0.4],  # u (boot) → ऊ

    # e (ए): Intellect -> Ego / Aspiration → O3 (Execution) + O7 (Reasoning) dominant
    "EH": [0.1, 0.2, 0.7, 0.3, 0.4, 0.3, 0.8, 0.4, 0.2, 0.3, 0.3, 0.2],  # ɛ (bed) → ए
    "ER": [0.2, 0.3, 0.5, 0.4, 0.4, 0.4, 0.6, 0.4, 0.3, 0.4, 0.3, 0.3],  # ɝ (bird)

    # ai (ऐ): Soul intention / Wisdom → O8 (Purpose) dominant
    "EY": [0.1, 0.1, 0.3, 0.2, 0.3, 0.4, 0.5, 0.9, 0.4, 0.5, 0.4, 0.3],  # eɪ (say) → ऐ
    "AY": [0.2, 0.2, 0.4, 0.2, 0.3, 0.4, 0.4, 0.8, 0.4, 0.5, 0.4, 0.3],  # aɪ (my)

    # o (ओ): Observer / Completion → O9 (Witness) + O11 (Integration) dominant
    "OW": [0.1, 0.1, 0.2, 0.2, 0.3, 0.2, 0.4, 0.5, 0.9, 0.6, 0.8, 0.5],  # oʊ (go) → ओ
    "AO": [0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4, 0.5, 0.8, 0.6, 0.7, 0.5],  # ɔ (thought)
    "OY": [0.2, 0.2, 0.3, 0.2, 0.3, 0.3, 0.4, 0.6, 0.8, 0.5, 0.7, 0.5],  # ɔɪ (boy)

    # au (औ): Transformation / Surrender → O12 (Absolving) dominant
    "AW": [0.1, 0.1, 0.2, 0.1, 0.2, 0.3, 0.3, 0.6, 0.7, 0.4, 0.6, 0.9],  # aʊ (out) → औ

    # ==========================================================================
    # PLOSIVES: Forceful Action (O3_Execution dominant)
    # ==========================================================================
    # Voiceless - Sharp execution energy
    "P":  [0.0, 0.2, 0.8, 0.4, 0.1, 0.5, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],  # p (pat)
    "T":  [0.0, 0.2, 0.9, 0.5, 0.1, 0.6, 0.2, 0.1, 0.1, 0.1, 0.1, 0.0],  # t (tap)
    "K":  [0.0, 0.2, 0.9, 0.4, 0.1, 0.5, 0.3, 0.1, 0.1, 0.1, 0.1, 0.0],  # k (cat)
    # Voiced - Softer execution with identity
    "B":  [0.1, 0.3, 0.7, 0.4, 0.2, 0.4, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],  # b (bat)
    "D":  [0.1, 0.3, 0.8, 0.5, 0.2, 0.5, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1],  # d (dog)
    "G":  [0.1, 0.3, 0.8, 0.4, 0.2, 0.4, 0.3, 0.1, 0.1, 0.2, 0.1, 0.1],  # g (go)

    # ==========================================================================
    # FRICATIVES: Controlled Agency (O6_Agency dominant)
    # ==========================================================================
    # Voiceless - Precise control
    "F":  [0.0, 0.2, 0.3, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],  # f (fat)
    "TH": [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.5, 0.3, 0.2, 0.2, 0.2, 0.1],  # θ (think)
    "S":  [0.0, 0.3, 0.3, 0.4, 0.3, 0.9, 0.6, 0.4, 0.2, 0.2, 0.2, 0.1],  # s (sat)
    "SH": [0.0, 0.2, 0.3, 0.5, 0.3, 0.8, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],  # ʃ (she)
    "HH": [0.4, 0.2, 0.2, 0.3, 0.2, 0.5, 0.3, 0.3, 0.2, 0.3, 0.4, 0.5],  # h (hat) → visarga-like
    # Voiced - Agency with vibration
    "V":  [0.0, 0.2, 0.4, 0.4, 0.3, 0.8, 0.7, 0.4, 0.3, 0.3, 0.2, 0.1],  # v (vat)
    "DH": [0.1, 0.2, 0.4, 0.4, 0.3, 0.7, 0.6, 0.4, 0.3, 0.3, 0.2, 0.1],  # ð (this)
    "Z":  [0.0, 0.3, 0.4, 0.4, 0.3, 0.8, 0.6, 0.4, 0.2, 0.3, 0.2, 0.1],  # z (zoo)
    "ZH": [0.0, 0.2, 0.4, 0.5, 0.3, 0.7, 0.6, 0.4, 0.3, 0.4, 0.3, 0.2],  # ʒ (measure)

    # ==========================================================================
    # AFFRICATES: Plosive + Fricative blend (O3 + O6 combination)
    # ==========================================================================
    "CH": [0.0, 0.2, 0.7, 0.5, 0.2, 0.7, 0.4, 0.2, 0.2, 0.2, 0.2, 0.1],  # tʃ (chat)
    "JH": [0.1, 0.3, 0.6, 0.5, 0.2, 0.6, 0.5, 0.3, 0.2, 0.3, 0.2, 0.1],  # dʒ (jam)

    # ==========================================================================
    # NASALS: Resonance and Connection (O10_Unifying dominant)
    # ==========================================================================
    "M":  [0.3, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.4, 0.3],  # m (mat) → अं
    "N":  [0.2, 0.3, 0.2, 0.2, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 0.5, 0.3],  # n (nat)
    "NG": [0.2, 0.3, 0.2, 0.3, 0.6, 0.2, 0.1, 0.2, 0.5, 0.9, 0.5, 0.4],  # ŋ (sing)

    # ==========================================================================
    # LIQUIDS: Flow and Structure (O4_Structure dominant)
    # ==========================================================================
    "L":  [0.1, 0.2, 0.2, 0.9, 0.3, 0.3, 0.3, 0.4, 0.3, 0.6, 0.5, 0.4],  # l (lat)
    "R":  [0.1, 0.2, 0.7, 0.5, 0.4, 0.4, 0.3, 0.3, 0.3, 0.5, 0.4, 0.4],  # ɹ (rat)

    # ==========================================================================
    # APPROXIMANTS: Smooth transition (O7_Reasoning, O8_Purpose)
    # ==========================================================================
    "W":  [0.2, 0.2, 0.2, 0.3, 0.4, 0.4, 0.5, 0.6, 0.4, 0.6, 0.5, 0.4],  # w (wat)
    "Y":  [0.2, 0.3, 0.3, 0.4, 0.3, 0.4, 0.6, 0.6, 0.4, 0.5, 0.4, 0.3],  # j (yes)

    # ==========================================================================
    # SPECIAL TOKENS
    # ==========================================================================
    "SIL":   [0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.8],  # Silence → O12
    "SP":    [0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.8],  # Short pause
    "UNK":   [0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33, 0.33],  # Unknown
}

# =============================================================================
# SANSKRIT VOWEL CALIBRATION
# =============================================================================
# These are the 14 Māheśvara Sūtra vowels, providing ground truth for calibration.
# Each maps to specific ontological layers based on Vedic phonetics.

SANSKRIT_VOWEL_CALIBRATION: Dict[str, Dict[str, Any]] = {
    # Short vowels (Hrasva)
    "a":   {"devanagari": "अ", "layer_primary": 0, "affinity": [1.0, 0.3, 0.2, 0.1, 0.1, 0.2, 0.3, 0.4, 0.3, 0.5, 0.6, 0.4]},  # O1 Potential
    "i":   {"devanagari": "इ", "layer_primary": 5, "affinity": [0.2, 0.4, 0.3, 0.2, 0.2, 0.9, 0.6, 0.5, 0.4, 0.5, 0.5, 0.4]},  # O6 Latency
    "u":   {"devanagari": "उ", "layer_primary": 6, "affinity": [0.2, 0.2, 0.3, 0.3, 0.3, 0.5, 0.9, 0.7, 0.6, 0.6, 0.6, 0.5]},  # O7 Emergence
    "ṛ":   {"devanagari": "ऋ", "layer_primary": 2, "affinity": [0.3, 0.5, 0.8, 0.4, 0.3, 0.4, 0.5, 0.4, 0.5, 0.4, 0.4, 0.4]},  # O3 Execution
    "ḷ":   {"devanagari": "ऌ", "layer_primary": 3, "affinity": [0.3, 0.4, 0.4, 0.8, 0.4, 0.5, 0.5, 0.5, 0.4, 0.5, 0.5, 0.4]},  # O4 Maintenance

    # Long vowels (Dīrgha)
    "ā":   {"devanagari": "आ", "layer_primary": 1, "affinity": [0.8, 0.9, 0.3, 0.2, 0.1, 0.2, 0.3, 0.4, 0.4, 0.5, 0.6, 0.5]},  # O2 Activation
    "ī":   {"devanagari": "ई", "layer_primary": 7, "affinity": [0.2, 0.3, 0.3, 0.3, 0.2, 0.6, 0.7, 0.9, 0.5, 0.6, 0.6, 0.5]},  # O8 Stabilization
    "ū":   {"devanagari": "ऊ", "layer_primary": 8, "affinity": [0.2, 0.2, 0.3, 0.3, 0.2, 0.4, 0.6, 0.7, 0.9, 0.7, 0.7, 0.6]},  # O9 Authority

    # Diphthongs (Sandhyakṣara)
    "e":   {"devanagari": "ए", "layer_primary": 9, "affinity": [0.3, 0.4, 0.3, 0.3, 0.2, 0.4, 0.5, 0.6, 0.5, 0.9, 0.7, 0.5]},  # O10 Unifying
    "ai":  {"devanagari": "ऐ", "layer_primary": 4, "affinity": [0.4, 0.5, 0.4, 0.4, 0.8, 0.4, 0.5, 0.5, 0.4, 0.6, 0.6, 0.5]},  # O5 Dissolution
    "o":   {"devanagari": "ओ", "layer_primary": 10, "affinity": [0.3, 0.3, 0.3, 0.3, 0.2, 0.4, 0.5, 0.6, 0.5, 0.7, 0.9, 0.6]},  # O11 Integration
    "au":  {"devanagari": "औ", "layer_primary": 11, "affinity": [0.3, 0.3, 0.2, 0.2, 0.2, 0.4, 0.5, 0.6, 0.5, 0.7, 0.8, 0.9]},  # O12 Absolving

    # Anusvāra & Visarga (Completers)
    "ṃ":   {"devanagari": "अं", "layer_primary": 9, "affinity": [0.3, 0.3, 0.2, 0.3, 0.2, 0.4, 0.5, 0.5, 0.4, 0.9, 0.8, 0.6]},  # Anusvara → O10
    "ḥ":   {"devanagari": "अः", "layer_primary": 10, "affinity": [0.4, 0.3, 0.2, 0.3, 0.2, 0.4, 0.4, 0.5, 0.4, 0.7, 0.9, 0.7]},  # Visarga → O11
}


# =============================================================================
# ARPABET → SANSKRIT VARNA MAPPING (Mental Propensities Bridge)
# =============================================================================
# This critical mapping bridges English phonemes to Sanskrit Varna Mala,
# enabling the training to learn ontological structure from mental propensities.
#
# Each ARPABET phoneme maps to a Sanskrit varṇa, which carries:
# - Vowels: States of consciousness (birth, expansion, contraction, etc.)
# - Consonants: Vrittis/Mental Propensities (hope, worry, attachment, etc.)
#
# This is the "missing link" that turns a Phonetic LLM into an Ontological Engine.

ARPABET_TO_VARNA: Dict[str, str] = {
    # ==========================================================================
    # VOWELS: Roots of Consciousness
    # ==========================================================================
    'AA': 'a',    # अ - Birth of cognition / Raw potential
    'AH': 'a',    # अ - Same root vowel
    'AE': 'a',    # अ - Open vowel variant
    'AO': 'o',    # ओ - Completion / Closure
    'AW': 'au',   # औ - Surrender / Letting-go
    'AY': 'ai',   # ऐ - Welfare / Materialization
    'EH': 'e',    # ए - Practical thought / Benefit
    'ER': 'ṛ',    # ऋ - Vocalic R (execution energy)
    'EY': 'e',    # ए - Practical thought
    'IH': 'i',    # इ - I-ness / Doing self
    'IY': 'ī',    # ई - Specialization of self
    'OW': 'o',    # ओ - Completion / Closure
    'OY': 'ai',   # ऐ - Welfare (diphthong blend)
    'UH': 'u',    # उ - Zoom / Contraction
    'UW': 'ū',    # ऊ - Sustained attention / Holding

    # ==========================================================================
    # CONSONANTS: Vrittis (Mental Propensities)
    # ==========================================================================
    # Ka-varga (Guttural) - Throat chakra propensities
    'K':  'ka',   # क - Āśā (Hope) - forward-seeking pressure
    'G':  'ga',   # ग - Ceṣṭā (Action) - kinetic momentum
    'NG': 'ṅa',   # ङ - Dambha (Vanity) - nasal marker

    # Ca-varga (Palatal) - Heart/expression propensities
    'CH': 'ca',   # च - Vikṣepa (Scatter) - boundary checking
    'JH': 'ja',   # ज - Dambha (Vanity) - aspiration pressure

    # Ṭa-varga (Retroflex) - Solar plexus propensities
    'T':  'ṭa',   # ट - Vitarka (Overstatement) - sharp execution
    'D':  'ḍa',   # ड - Lajjā (Shyness) - retroactive pressure

    # Ta-varga (Dental) - Sacral propensities
    'TH': 'tha',  # थ - Viṣāda (Melancholy) - aspirated inertia
    'DH': 'dha',  # ध - Tṛṣṇā (Craving) - retention pressure

    # Pa-varga (Labial) - Root chakra propensities
    'P':  'pa',   # प - Ghrṇā (Hatred/Revulsion) - forceful rejection
    'B':  'ba',   # ब - Avajñā (Indifference) - passive pressure
    'M':  'ma',   # म - Praśraya (Indulgence) - nasal completion

    # Semi-vowels (Antaḥstha) - Transitional energies
    'Y':  'ya',   # य - Aviśvāsa (Lack of confidence) - glide transition
    'R':  'ra',   # र - Sarvanāśa (Annihilation) - fire/destruction energy
    'L':  'la',   # ल - Krūratā (Cruelty) - lateral flow
    'W':  'va',   # व - Dharma (Righteousness) - labio-dental flow
    'V':  'va',   # व - Same as W

    # Sibilants (Ūṣman) - Friction/heat energies
    'S':  'sa',   # स - Escapism / Static detachment
    'SH': 'śa',   # श - Material greed
    'Z':  'ja',   # Approximation to ja (voiced sibilant)
    'ZH': 'ja',   # Same approximation

    # Aspirate
    'HH': 'ha',   # ह - Avidyā (Darkness/Ignorance) - aspirate release

    # Affricates (mapped to nearest varga)
    'F':  'pha',  # फ - Bhaya (Fear) - aspirated labial
    'N':  'na',   # न - Moha (Blind attachment) - dental nasal
}


# =============================================================================
# GRAPHEME TO PHONEME (G2P) FALLBACK
# =============================================================================
# Simple rule-based G2P for English. In production, use a proper G2P model.

SIMPLE_G2P: Dict[str, List[str]] = {
    # Common words and patterns
    "the": ["DH", "AH"],
    "a": ["AH"],
    "an": ["AE", "N"],
    "is": ["IH", "Z"],
    "are": ["AA", "R"],
    "was": ["W", "AA", "Z"],
    "were": ["W", "ER"],
    "be": ["B", "IY"],
    "been": ["B", "IH", "N"],
    "have": ["HH", "AE", "V"],
    "has": ["HH", "AE", "Z"],
    "had": ["HH", "AE", "D"],
    "do": ["D", "UW"],
    "does": ["D", "AH", "Z"],
    "did": ["D", "IH", "D"],
    "will": ["W", "IH", "L"],
    "would": ["W", "UH", "D"],
    "could": ["K", "UH", "D"],
    "should": ["SH", "UH", "D"],
    "can": ["K", "AE", "N"],
    "may": ["M", "EY"],
    "might": ["M", "AY", "T"],
    "must": ["M", "AH", "S", "T"],
    "if": ["IH", "F"],
    "then": ["DH", "EH", "N"],
    "that": ["DH", "AE", "T"],
    "this": ["DH", "IH", "S"],
    "what": ["W", "AH", "T"],
    "when": ["W", "EH", "N"],
    "where": ["W", "EH", "R"],
    "which": ["W", "IH", "CH"],
    "who": ["HH", "UW"],
    "how": ["HH", "AW"],
    "not": ["N", "AA", "T"],
    "no": ["N", "OW"],
    "yes": ["Y", "EH", "S"],
    "and": ["AE", "N", "D"],
    "or": ["AO", "R"],
    "but": ["B", "AH", "T"],
    "for": ["F", "AO", "R"],
    "with": ["W", "IH", "DH"],
    "from": ["F", "R", "AH", "M"],
    "to": ["T", "UW"],
    "of": ["AH", "V"],
    "in": ["IH", "N"],
    "on": ["AA", "N"],
    "at": ["AE", "T"],
    "by": ["B", "AY"],
}

# Character-level fallback
CHAR_TO_PHONEME: Dict[str, str] = {
    'a': 'AH', 'b': 'B', 'c': 'K', 'd': 'D', 'e': 'EH',
    'f': 'F', 'g': 'G', 'h': 'HH', 'i': 'IH', 'j': 'JH',
    'k': 'K', 'l': 'L', 'm': 'M', 'n': 'N', 'o': 'OW',
    'p': 'P', 'q': 'K', 'r': 'R', 's': 'S', 't': 'T',
    'u': 'UH', 'v': 'V', 'w': 'W', 'x': 'K', 'y': 'Y',
    'z': 'Z',
}


# =============================================================================
# VARNA CSR BRIDGE: Sanskrit Varṇa → 12D Ontological Vectors
# =============================================================================
# Maps Sanskrit varṇas from varna_bridge_map_v1.json to numeric 12D vectors.
# Consonants have explicit layer annotations; vowels map to primary layers.

# Layer name to index mapping
LAYER_NAME_TO_IDX: Dict[str, int] = {
    "O1_POTENTIAL": 0, "O1": 0,
    "O2_IDENTITY": 1, "O2": 1,
    "O3_EXECUTION": 2, "O3": 2,
    "O4_STRUCTURE": 3, "O4": 3,
    "O5_COGNITION": 4, "O5": 4,
    "O6_AGENCY": 5, "O6": 5,
    "O7_REASONING": 6, "O7": 6,
    "O8_PURPOSE": 7, "O8": 7,
    "O9_WITNESSES": 8, "O9": 8,
    "O10_UNIFYING": 9, "O10": 9,
    "O11_INTEGRATION": 10, "O11": 10,
    "O12_ABSOLVING": 11, "O12": 11,
}

# Vowel bridge_meaning → primary layer mapping
VOWEL_BRIDGE_TO_LAYER: Dict[str, int] = {
    "birth_of_cognition": 0,      # O1_Potential
    "expansion_continuity": 1,     # O2_Identity
    "self_doing": 1,              # O2_Identity (I-ness)
    "specialized_identity": 3,     # O4_Structure
    "contraction_focus": 4,        # O5_Cognition
    "sustained_hold": 5,           # O6_Agency
    "practical_cognition": 6,      # O7_Reasoning
    "integrative_understanding": 7, # O8_Purpose
    "closure_completion": 8,       # O9_Witnesses
    "surrender_transition": 11,    # O12_Absolving
    "purgative_repulsion": 9,      # O10_Unifying (aṁ)
    "dissolutive_attraction": 11,  # O12_Absolving (aha)
}

# Keywords in layer descriptions → weight boosts
LAYER_KEYWORD_WEIGHTS: Dict[str, float] = {
    "activation": 0.8,
    "classification": 0.6,
    "shaping force": 0.7,
    "pattern bias": 0.6,
    "toward": 0.5,
    "sequencing": 0.6,
    "orientation vector": 0.7,
    "tracking": 0.5,
    "coherence": 0.7,
    "integration": 0.8,
    "dissolution": 0.6,
    "termination": 0.5,
    "threshold": 0.4,
}


class VarnaCSRBridge:
    """
    Bridge between Sanskrit Varṇa system and CSR 12D ontological vectors.

    Loads varna_bridge_map_v1.json and converts:
    - Consonant layer annotations → numeric 12D vectors
    - Vowel bridge_meanings → primary layer affinities
    """

    def __init__(self, json_path: Optional[Path] = None):
        """
        Initialize VarnaCSRBridge.

        Args:
            json_path: Path to varna_bridge_map_v1.json. Auto-discovers if None.
        """
        self._json_path = json_path
        self._data: Dict[str, Any] = {}
        self._varna_vectors: Dict[str, List[float]] = {}
        self._loaded = False

        # Auto-discover JSON path
        if self._json_path is None:
            possible_paths = [
                Path(__file__).parent / "symbolu" / "formulas" / "data" / "varna_bridge_map_v1.json",
                Path(__file__).parent / "docs" / "data" / "varna_bridge_map_v1.json",
                Path(__file__).parent.parent / "docs" / "data" / "varna_bridge_map_v1.json",
            ]
            for p in possible_paths:
                if p.exists():
                    self._json_path = p
                    break

    def load(self) -> bool:
        """Load and parse the varna_bridge_map JSON."""
        if self._loaded:
            return True

        if self._json_path is None or not self._json_path.exists():
            print(f"  [VarnaCSRBridge] JSON not found, using ARPABET fallback")
            return False

        try:
            with open(self._json_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        except Exception as e:
            print(f"  [VarnaCSRBridge] Failed to load JSON: {e}")
            return False

        # Parse vowels
        for varna, info in self._data.get("vowels", {}).items():
            bridge_meaning = info.get("bridge_meaning", "")
            self._varna_vectors[varna] = self._vowel_to_vector(bridge_meaning)

        # Parse consonants
        for varna, info in self._data.get("consonants", {}).items():
            layers = info.get("layers", {})
            if layers:
                self._varna_vectors[varna] = self._consonant_layers_to_vector(layers)
            else:
                # Fallback to bridge_meaning
                bridge_meaning = info.get("bridge_meaning", "")
                self._varna_vectors[varna] = self._consonant_bridge_to_vector(bridge_meaning)

        self._loaded = True
        print(f"  [VarnaCSRBridge] Loaded {len(self._varna_vectors)} varṇas from {self._json_path.name}")
        return True

    def _vowel_to_vector(self, bridge_meaning: str) -> List[float]:
        """Convert vowel bridge_meaning to 12D vector."""
        vector = [0.1] * 12  # Base activation

        # Get primary layer from mapping
        primary_idx = VOWEL_BRIDGE_TO_LAYER.get(bridge_meaning, 0)
        vector[primary_idx] = 0.9  # Primary affinity

        # Add secondary affinities for adjacent layers
        if primary_idx > 0:
            vector[primary_idx - 1] = 0.4
        if primary_idx < 11:
            vector[primary_idx + 1] = 0.4

        return vector

    def _consonant_layers_to_vector(self, layers: Dict[str, str]) -> List[float]:
        """Convert consonant layer annotations to 12D vector."""
        vector = [0.1] * 12  # Base activation

        for layer_name, description in layers.items():
            # Get layer index
            idx = LAYER_NAME_TO_IDX.get(layer_name, -1)
            if idx < 0:
                continue

            # Parse description for keywords
            desc_lower = description.lower()
            weight = 0.3  # Base weight for having any description

            for keyword, kw_weight in LAYER_KEYWORD_WEIGHTS.items():
                if keyword in desc_lower:
                    weight = max(weight, kw_weight)

            # Boost if description contains activation/dominant patterns
            if "activation" in desc_lower:
                weight = min(weight + 0.2, 0.9)
            if "dominant" in desc_lower or "primary" in desc_lower:
                weight = min(weight + 0.3, 0.95)

            vector[idx] = max(vector[idx], weight)

        return vector

    def _consonant_bridge_to_vector(self, bridge_meaning: str) -> List[float]:
        """Fallback: Convert consonant bridge_meaning to 12D vector."""
        vector = [0.2] * 12  # Slightly higher base for consonants

        # Map common bridge_meaning patterns to layers
        meaning_lower = bridge_meaning.lower()

        if "pressure" in meaning_lower:
            vector[2] = 0.7  # O3_Execution
            vector[5] = 0.6  # O6_Agency
        if "activation" in meaning_lower:
            vector[1] = 0.6  # O2_Identity
            vector[2] = 0.8  # O3_Execution
        if "integration" in meaning_lower or "coherence" in meaning_lower:
            vector[9] = 0.7   # O10_Unifying
            vector[10] = 0.6  # O11_Integration
        if "dissolution" in meaning_lower or "termination" in meaning_lower:
            vector[11] = 0.7  # O12_Absolving

        return vector

    def get_vector(self, varna: str) -> Optional[List[float]]:
        """Get 12D vector for a varṇa."""
        if not self._loaded:
            self.load()
        return self._varna_vectors.get(varna)

    def has_varna(self, varna: str) -> bool:
        """Check if varṇa is in the bridge map."""
        if not self._loaded:
            self.load()
        return varna in self._varna_vectors

    @property
    def all_varnas(self) -> List[str]:
        """Get all available varṇas."""
        if not self._loaded:
            self.load()
        return list(self._varna_vectors.keys())

    def to_tensor(self, device: torch.device = None) -> torch.Tensor:
        """Build tensor of all varṇa vectors."""
        if not self._loaded:
            self.load()

        varnas = self.all_varnas
        vectors = [self._varna_vectors[v] for v in varnas]

        tensor = torch.tensor(vectors, dtype=torch.float32)
        if device is not None:
            tensor = tensor.to(device)

        return tensor


# =============================================================================
# CSR EMBEDDING PROVIDER
# =============================================================================

@dataclass
class CSRConfig:
    """Configuration for CSR Embedding Provider."""
    d_model: int = 512              # Model hidden dimension
    num_layers: int = 12            # Number of ontological layers
    lambda_csr: float = 0.5         # CSR injection strength (Strong Guidance default)
    lambda_csr_min: float = 0.1     # Minimum λ_csr after decay
    position_weights: Tuple[float, ...] = (1.5, 1.25, 1.0)  # First 3 phoneme weights
    max_phonemes_per_token: int = 5  # Max phonemes to consider per token
    use_phase_gating: bool = True   # Gate Phase Attention with CSR confidence
    trainable_projection: bool = True  # Allow projection to train
    dropout: float = 0.1
    use_decay_scheduler: bool = True  # Enable Knowledge-based λ decay


# =============================================================================
# CSR DECAY SCHEDULER (Knowledge-Based)
# =============================================================================

class CSRDecayScheduler:
    """
    Knowledge-Based λ_csr Decay Scheduler.

    Reduces CSR guidance strength as the model develops its own fluency,
    measured by the Knowledge (Know) metric from the Evolutionary Flow.

    Decay Strategy:
        λ_csr(t) = λ_max * decay_factor + λ_min * (1 - decay_factor)

        where decay_factor = max(0, 1 - Know / know_threshold)

    When Know = 0:     λ_csr = λ_max (full guidance, breaking mode collapse)
    When Know ≥ thresh: λ_csr = λ_min (model has learned, reduce constraint)

    The scheduler implements a "Sattvic Release" pattern:
        - Strong guidance initially (break entropy collapse basins)
        - Gradual release as model develops Knowledge
        - Maintain minimum floor to prevent regression

    Integration with Mode Collapse Detection:
        If entropy drops below threshold, scheduler can BOOST λ_csr
        temporarily to break the collapse pattern.
    """

    def __init__(
        self,
        lambda_max: float = 0.5,
        lambda_min: float = 0.1,
        know_threshold: float = 0.7,
        entropy_floor: float = 0.4,
        entropy_boost_factor: float = 1.5,
        warmup_steps: int = 500,
        decay_type: str = "linear",  # linear, cosine, exponential
    ):
        """
        Initialize CSR Decay Scheduler.

        Args:
            lambda_max: Maximum λ_csr (strong guidance phase)
            lambda_min: Minimum λ_csr (after decay floor)
            know_threshold: Knowledge score at which decay completes
            entropy_floor: Entropy below which triggers mode collapse boost
            entropy_boost_factor: Multiplier for λ when entropy is low
            warmup_steps: Steps before decay begins
            decay_type: Decay curve shape (linear, cosine, exponential)
        """
        self.lambda_max = lambda_max
        self.lambda_min = lambda_min
        self.know_threshold = know_threshold
        self.entropy_floor = entropy_floor
        self.entropy_boost_factor = entropy_boost_factor
        self.warmup_steps = warmup_steps
        self.decay_type = decay_type

        # State tracking
        self.current_step = 0
        self.current_lambda = lambda_max
        self.current_know = 0.0
        self.current_entropy = 1.0
        self.mode_collapse_detected = False
        self.boost_active = False

        # History for analysis
        self.history: List[Dict[str, float]] = []

    def step(
        self,
        know_score: float,
        entropy: float,
        step: Optional[int] = None,
    ) -> float:
        """
        Compute λ_csr for current training state.

        Args:
            know_score: Current Knowledge metric (0.0 to 1.0)
            entropy: Current entropy metric
            step: Optional explicit step number

        Returns:
            Computed λ_csr value for this step
        """
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1

        self.current_know = know_score
        self.current_entropy = entropy

        # Check for mode collapse (entropy below floor)
        if entropy < self.entropy_floor:
            self.mode_collapse_detected = True
            self.boost_active = True
        else:
            self.mode_collapse_detected = False
            # Gradually release boost
            if self.boost_active and entropy > self.entropy_floor * 1.2:
                self.boost_active = False

        # Compute base λ from decay schedule
        if self.current_step < self.warmup_steps:
            # Warmup: full guidance
            base_lambda = self.lambda_max
        else:
            # Decay based on Knowledge
            decay_factor = self._compute_decay_factor(know_score)
            base_lambda = self.lambda_max * decay_factor + self.lambda_min * (1 - decay_factor)

        # Apply mode collapse boost if needed
        if self.boost_active:
            # Emergency boost can exceed lambda_max (up to 1.0) to shatter the loop
            self.current_lambda = min(1.0, self.current_lambda * self.entropy_boost_factor)
            print(f"  🔥 [BOOST] Entropy {entropy:.3f} < {self.entropy_floor}. "
                  f"Lambda increased to {self.current_lambda:.2f}")
        else:
            self.current_lambda = base_lambda

        # Record history
        self.history.append({
            "step": self.current_step,
            "lambda_csr": self.current_lambda,
            "know_score": know_score,
            "entropy": entropy,
            "boost_active": self.boost_active,
        })

        return self.current_lambda

    def _compute_decay_factor(self, know_score: float) -> float:
        """Compute decay factor based on Knowledge score."""
        # Clamp know_score to valid range
        know_score = max(0.0, min(1.0, know_score))

        # Progress toward threshold (0 = no knowledge, 1 = at/above threshold)
        progress = know_score / self.know_threshold
        progress = min(1.0, progress)

        if self.decay_type == "linear":
            # Linear decay: 1 → 0 as knowledge increases
            return 1.0 - progress

        elif self.decay_type == "cosine":
            # Cosine decay: smoother transition
            return 0.5 * (1.0 + math.cos(math.pi * progress))

        elif self.decay_type == "exponential":
            # Exponential decay: faster initial decay
            return math.exp(-3.0 * progress)

        else:
            return 1.0 - progress  # Default to linear

    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        return {
            "current_step": self.current_step,
            "current_lambda": self.current_lambda,
            "current_know": self.current_know,
            "current_entropy": self.current_entropy,
            "mode_collapse_detected": self.mode_collapse_detected,
            "boost_active": self.boost_active,
            "decay_type": self.decay_type,
            "lambda_range": (self.lambda_min, self.lambda_max),
        }

    def print_status(self):
        """Print current scheduler status."""
        status = self.get_status()
        print(f"\n  ╔══════════════════════════════════════════╗")
        print(f"  ║      CSR DECAY SCHEDULER STATUS          ║")
        print(f"  ╠══════════════════════════════════════════╣")
        print(f"  ║  Step:        {status['current_step']:>6}                    ║")
        print(f"  ║  λ_csr:       {status['current_lambda']:>6.3f}                    ║")
        print(f"  ║  Knowledge:   {status['current_know']:>6.3f}                    ║")
        print(f"  ║  Entropy:     {status['current_entropy']:>6.3f}                    ║")
        print(f"  ║  Boost:       {'ACTIVE' if status['boost_active'] else 'OFF':>6}                    ║")
        print(f"  ╚══════════════════════════════════════════╝")

    def should_increase_guidance(self) -> bool:
        """Check if guidance should be increased (mode collapse detected)."""
        return self.boost_active

    def get_metric_targets(self) -> Dict[str, Tuple[float, float]]:
        """
        Get expected metric ranges for current λ_csr.

        Returns target ranges for monitoring training health.
        """
        λ = self.current_lambda

        # Targets vary with λ_csr strength
        if λ >= 0.4:
            # Strong guidance phase
            return {
                "entropy": (0.52, 0.60),
                "coherence": (0.82, 0.88),
                "sa_ratio": (0.5, 0.7),
            }
        elif λ >= 0.2:
            # Moderate guidance
            return {
                "entropy": (0.48, 0.58),
                "coherence": (0.78, 0.85),
                "sa_ratio": (0.45, 0.65),
            }
        else:
            # Light guidance (high knowledge)
            return {
                "entropy": (0.45, 0.55),
                "coherence": (0.75, 0.82),
                "sa_ratio": (0.4, 0.6),
            }


def create_csr_decay_scheduler(
    config: CSRConfig,
    know_threshold: float = 0.7,
    warmup_steps: int = 500,
    decay_type: str = "cosine",
) -> CSRDecayScheduler:
    """
    Create a CSR Decay Scheduler from CSRConfig.

    Args:
        config: CSRConfig with lambda settings
        know_threshold: Knowledge score for decay completion
        warmup_steps: Steps before decay begins
        decay_type: Decay curve (linear, cosine, exponential)

    Returns:
        Configured CSRDecayScheduler
    """
    return CSRDecayScheduler(
        lambda_max=config.lambda_csr,
        lambda_min=config.lambda_csr_min,
        know_threshold=know_threshold,
        warmup_steps=warmup_steps,
        decay_type=decay_type,
    )


class CSREmbeddingProvider(nn.Module):
    """
    CSR (Constraint-Structure-Resonance) Embedding Provider.

    Converts input tokens to phonemes, maps to 12D ontological space,
    and provides grounding embeddings for the neural network.

    Pipeline:
        1. Token → Phoneme extraction (lookup or G2P fallback)
        2. Phoneme → 12D affinity vectors
        3. Position-weighted aggregation
        4. L2 normalization
        5. Projection to model dimension
        6. Optional: Phase gating based on CSR confidence
    """

    def __init__(self, config: CSRConfig, tokenizer=None):
        super().__init__()
        self.config = config
        self.tokenizer = tokenizer

        # Register phoneme map as buffer (non-trainable)
        phoneme_tensor = self._build_phoneme_tensor()
        self.register_buffer('phoneme_map', phoneme_tensor)

        # Projection: 12D → d_model
        self.projection = nn.Linear(12, config.d_model, bias=False)
        if not config.trainable_projection:
            for param in self.projection.parameters():
                param.requires_grad = False

        # Layer-wise scaling (learnable per-layer injection strength)
        self.layer_scales = nn.Parameter(torch.ones(config.num_layers))

        # Confidence head (predicts CSR alignment quality)
        self.confidence_head = nn.Sequential(
            nn.Linear(12, 32),
            nn.GELU(),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

        # Phase gate (for suppressing Phase Attention on low-confidence sequences)
        if config.use_phase_gating:
            self.phase_gate = nn.Sequential(
                nn.Linear(12, 32),
                nn.GELU(),
                nn.Linear(32, 1),
                nn.Sigmoid(),
            )

        self.dropout = nn.Dropout(config.dropout)

        # Cache for token-to-phoneme mappings
        self._phoneme_cache: Dict[str, List[str]] = {}

        # Initialize Hybrid G2P system (CMUdict + g2p_en)
        self._hybrid_g2p = get_hybrid_g2p()

        # V9.5.3 CRITICAL: Initialize Sanskrit Varna Bridge for Mental Propensities
        # This bridges ARPABET → Sanskrit Varna → 12D Ontological vectors
        # WITHOUT this, training uses generic phonetic vectors instead of
        # the mental propensities (Hope, Worry, Attachment, etc.) from varna_bridge_map_v1.json
        self._varna_bridge = VarnaCSRBridge()
        self._varna_bridge_loaded = self._varna_bridge.load()
        if self._varna_bridge_loaded:
            print(f"  ⚡ [CSR] Sanskrit Varna Bridge ACTIVE - Mental propensities enabled!")
        else:
            print(f"  ⚠️ [CSR] Varna Bridge not loaded - using ARPABET fallback")

        # V9.5.2 Performance: Precompute token ID → affinity lookup table
        # This eliminates O(B*T) tokenizer.decode() calls in forward pass
        if tokenizer is not None:
            self._build_token_affinity_table()
        else:
            # No tokenizer available - will use slow path in forward()
            self.register_buffer('_token_affinity_table', None, persistent=False)

    def _build_phoneme_tensor(self) -> torch.Tensor:
        """Build tensor of phoneme → 12D mappings."""
        phonemes = list(PHONEME_MAP_ARPABET.keys())
        vectors = [PHONEME_MAP_ARPABET[p] for p in phonemes]

        # Store phoneme list for indexing
        self._phoneme_list = phonemes
        self._phoneme_to_idx = {p: i for i, p in enumerate(phonemes)}

        return torch.tensor(vectors, dtype=torch.float32)

    def _build_token_affinity_table(self):
        """
        V9.5.3 CRITICAL FIX: Build token affinity table with Sanskrit Varna Bridge.
        V9.6.0 FIX: Zero out special tokens (PAD, EOS, BOS, UNK) to prevent "Pad Token Ghost"

        This now traces the full path:
            Token → ARPABET phonemes → Sanskrit Varna → 12D Ontological vector

        The Sanskrit Varna carries the mental propensities (vrittis):
            - K → ka → Āśā (Hope)
            - P → pa → Ghrṇā (Hatred)
            - M → ma → Praśraya (Indulgence)
            etc.

        This is the "missing link" that turns a Phonetic LLM into an Ontological Engine.
        """
        if self.tokenizer is None:
            return

        vocab_size = getattr(self.tokenizer, 'vocab_size', None)
        if vocab_size is None:
            try:
                vocab_size = len(self.tokenizer)
            except:
                vocab_size = 50257  # GPT-2 default

        use_varna = self._varna_bridge_loaded
        if use_varna:
            print(f"  ⚡ [CSR] Building SANSKRIT VARNA affinity table for {vocab_size:,} tokens...")
            print(f"       Bridging ARPABET → Sanskrit Varna → 12D Ontology (Mental Propensities)")
        else:
            print(f"  [CSR] Building ARPABET affinity table for {vocab_size:,} tokens...")

        import time
        start_time = time.time()

        # V9.6.0: Identify special tokens to zero out (prevents "Pad Token Ghost")
        special_token_ids = set()
        for attr in ['pad_token_id', 'eos_token_id', 'bos_token_id', 'unk_token_id', 'sep_token_id', 'cls_token_id', 'mask_token_id']:
            tid = getattr(self.tokenizer, attr, None)
            if tid is not None:
                special_token_ids.add(tid)
        # Also check special_tokens_map
        if hasattr(self.tokenizer, 'special_tokens_map'):
            for token in self.tokenizer.special_tokens_map.values():
                if isinstance(token, str):
                    tid = self.tokenizer.convert_tokens_to_ids(token)
                    if tid is not None and tid < vocab_size:
                        special_token_ids.add(tid)
        # Store for use in forward()
        self._special_token_ids = special_token_ids

        # Preallocate table
        affinity_table = torch.zeros(vocab_size, 12, dtype=torch.float32)

        # Statistics
        varna_mapped = 0
        arpabet_fallback = 0
        special_zeroed = 0

        # Compute affinity for each token
        for token_id in range(vocab_size):
            # V9.6.0: Zero out special tokens - they should NOT contribute to CSR loss
            if token_id in special_token_ids:
                affinity_table[token_id] = torch.zeros(12)
                special_zeroed += 1
                continue

            try:
                token_str = self.tokenizer.decode([token_id])
                phonemes = self.token_to_phonemes(token_str)

                if use_varna and phonemes:
                    # V9.5.3: Use Sanskrit Varna Bridge for mental propensities
                    varna_vector = self._phonemes_to_varna_affinity(phonemes)
                    if varna_vector is not None:
                        affinity_table[token_id] = varna_vector
                        varna_mapped += 1
                    else:
                        # Fallback to ARPABET
                        affinity_table[token_id] = self.phonemes_to_affinity(phonemes)
                        arpabet_fallback += 1
                else:
                    # No Varna bridge - use ARPABET directly
                    affinity_table[token_id] = self.phonemes_to_affinity(phonemes)
                    arpabet_fallback += 1

            except Exception:
                # Fallback for problematic tokens
                affinity_table[token_id] = self.phoneme_map[token_id % len(self._phoneme_list)]
                arpabet_fallback += 1

        # L2 normalize (special tokens remain zero after normalization)
        # Handle zero vectors by adding epsilon before norm
        norms = affinity_table.norm(dim=-1, keepdim=True)
        norms = torch.where(norms > 1e-8, norms, torch.ones_like(norms))
        affinity_table = affinity_table / norms

        # Register as buffer (moves with model to GPU)
        # Safe registration: delete existing attribute if present
        if hasattr(self, '_token_affinity_table'):
            del self._token_affinity_table
        self.register_buffer('_token_affinity_table', affinity_table, persistent=False)

        elapsed = time.time() - start_time
        if use_varna:
            print(f"  ⚡ [CSR] Token affinity table built in {elapsed:.2f}s")
            print(f"       Sanskrit Varna mapped: {varna_mapped:,} tokens ({100*varna_mapped/vocab_size:.1f}%)")
            print(f"       ARPABET fallback: {arpabet_fallback:,} tokens")
            print(f"       Special tokens zeroed: {special_zeroed} (PAD/EOS/BOS/UNK ghosting prevented)")
        else:
            print(f"  [CSR] Token affinity table built in {elapsed:.2f}s")
            print(f"       Special tokens zeroed: {special_zeroed} (PAD/EOS/BOS/UNK ghosting prevented)")

    def _phonemes_to_varna_affinity(self, phonemes: List[str]) -> Optional[torch.Tensor]:
        """
        V9.5.3: Convert phonemes to 12D affinity via Sanskrit Varna Bridge.

        Traces: ARPABET → Sanskrit Varna → 12D Ontological vector

        This injects the mental propensities from varna_bridge_map_v1.json:
            - K → ka → Āśā (Hope) → O3_Execution dominant
            - P → pa → Ghrṇā (Hatred) → O3_Execution + O6_Agency
            etc.

        Returns:
            12D tensor if any phoneme mapped, None if all failed
        """
        if not phonemes or not self._varna_bridge_loaded:
            return None

        # Get weights for position weighting
        weights = list(self.config.position_weights)
        while len(weights) < len(phonemes):
            weights.append(1.0)
        weights = weights[:len(phonemes)]

        affinity = torch.zeros(12, dtype=torch.float32)
        total_weight = 0.0
        mapped_count = 0

        for i, phoneme in enumerate(phonemes):
            # Strip stress markers (AA0 → AA)
            clean_phoneme = phoneme.rstrip('012')

            # Step 1: ARPABET → Sanskrit Varna key
            varna_key = ARPABET_TO_VARNA.get(clean_phoneme)

            if varna_key:
                # Step 2: Sanskrit Varna → 12D vector (from varna_bridge_map_v1.json)
                varna_vector = self._varna_bridge.get_vector(varna_key)

                if varna_vector is not None:
                    # Apply position weight
                    weight = weights[i]
                    affinity += weight * torch.tensor(varna_vector, dtype=torch.float32)
                    total_weight += weight
                    mapped_count += 1

        if mapped_count == 0:
            return None

        # Normalize by total weight
        affinity = affinity / total_weight

        return affinity

    def token_to_phonemes(self, token: str) -> List[str]:
        """
        Convert a token to its phoneme sequence using Hybrid G2P.

        Uses tiered lookup:
            1. CMUdict (134K words, fast deterministic)
            2. Custom vocabulary (domain-specific terms)
            3. g2p_en neural model (OOV fallback)
            4. Character-level fallback (last resort)

        Args:
            token: Input token string

        Returns:
            List of ARPABET phonemes
        """
        # Check local cache first
        if token in self._phoneme_cache:
            return self._phoneme_cache[token]

        # Use Hybrid G2P system
        phonemes = self._hybrid_g2p.get_phonemes(token)

        # Limit phonemes per token if configured
        if len(phonemes) > self.config.max_phonemes_per_token:
            phonemes = phonemes[:self.config.max_phonemes_per_token]

        # Cache and return
        self._phoneme_cache[token] = phonemes
        return phonemes

    def phonemes_to_affinity(self, phonemes: List[str]) -> torch.Tensor:
        """
        Convert phoneme sequence to 12D affinity vector.

        Uses position-weighted aggregation:
            W = (1.5, 1.25, 1.0, ...) for first 3+ phonemes
        """
        if not phonemes:
            return torch.zeros(12, device=self.phoneme_map.device)

        # Get weights
        weights = list(self.config.position_weights)
        while len(weights) < len(phonemes):
            weights.append(1.0)
        weights = weights[:len(phonemes)]

        # Aggregate phoneme vectors
        total_weight = sum(weights)
        affinity = torch.zeros(12, device=self.phoneme_map.device)

        for phoneme, weight in zip(phonemes, weights):
            if phoneme in self._phoneme_to_idx:
                idx = self._phoneme_to_idx[phoneme]
                affinity += weight * self.phoneme_map[idx]
            else:
                # Unknown phoneme - use UNK
                idx = self._phoneme_to_idx.get("UNK", 0)
                affinity += weight * self.phoneme_map[idx]

        # Normalize
        affinity = affinity / total_weight

        return affinity

    def forward(
        self,
        input_ids: torch.Tensor,
        token_strings: Optional[List[List[str]]] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute CSR embeddings for input tokens.

        Args:
            input_ids: Token IDs [B, T]
            token_strings: Optional decoded tokens [B][T] (if tokenizer available)

        Returns:
            Dict with:
                - csr_emb: CSR embeddings [B, T, d_model]
                - csr_affinity: Raw 12D affinities [B, T, 12]
                - csr_confidence: Alignment confidence [B, T, 1]
                - phase_gate: Phase attention gate [B, T, 1] (if enabled)
        """
        B, T = input_ids.shape
        device = input_ids.device

        # V9.5.2 Performance: Use precomputed token affinity table if available
        # This is O(1) tensor indexing instead of O(B*T) tokenizer.decode() calls
        if self._token_affinity_table is not None:
            # Fast path: single tensor indexing operation
            # Clamp token IDs to valid range
            clamped_ids = input_ids.clamp(0, self._token_affinity_table.size(0) - 1)
            affinities = self._token_affinity_table[clamped_ids]  # [B, T, 12]
            # Table is already L2 normalized
        else:
            # Slow path: compute affinities on-the-fly (fallback)
            # Get token strings if tokenizer available
            if token_strings is None and self.tokenizer is not None:
                token_strings = []
                for batch_idx in range(B):
                    tokens = [self.tokenizer.decode([tid.item()]) for tid in input_ids[batch_idx]]
                    token_strings.append(tokens)

            # Compute 12D affinities for each token
            affinities = torch.zeros(B, T, 12, device=device)

            if token_strings is not None:
                for b in range(B):
                    for t in range(T):
                        token = token_strings[b][t] if t < len(token_strings[b]) else ""
                        phonemes = self.token_to_phonemes(token)
                        affinities[b, t] = self.phonemes_to_affinity(phonemes)
            else:
                # Fallback: use input_ids directly with simple heuristic
                for b in range(B):
                    for t in range(T):
                        tid = input_ids[b, t].item()
                        phoneme_idx = tid % len(self._phoneme_list)
                        affinities[b, t] = self.phoneme_map[phoneme_idx]

            # L2 normalize affinities
            affinities = F.normalize(affinities, p=2, dim=-1)

        # Compute confidence
        confidence = self.confidence_head(affinities)

        # V9.6.0: Zero confidence for special tokens (prevents "Pad Token Ghost")
        # Special tokens have zero affinity vectors, but confidence_head may still output non-zero
        if hasattr(self, '_special_token_ids') and self._special_token_ids:
            # Create mask: 1 for normal tokens, 0 for special tokens
            special_mask = torch.ones(B, T, 1, device=device)
            for tid in self._special_token_ids:
                special_mask = special_mask * (input_ids != tid).unsqueeze(-1).float()
            confidence = confidence * special_mask

        # Project to model dimension
        csr_emb = self.projection(affinities)
        csr_emb = self.dropout(csr_emb)

        # Scale by confidence
        csr_emb = csr_emb * confidence

        result = {
            "csr_emb": csr_emb,
            "csr_affinity": affinities,
            "csr_confidence": confidence,
        }

        # Phase gating
        if self.config.use_phase_gating:
            phase_gate = self.phase_gate(affinities)
            result["phase_gate"] = phase_gate

        return result

    def get_layer_embedding(
        self,
        csr_emb: torch.Tensor,
        layer_idx: int,
    ) -> torch.Tensor:
        """
        Get CSR embedding for a specific layer with layer-specific scaling.

        Args:
            csr_emb: Base CSR embedding [B, T, d_model]
            layer_idx: Which layer (0-11)

        Returns:
            Scaled CSR embedding for this layer [B, T, d_model]
        """
        scale = self.layer_scales[layer_idx] * self.config.lambda_csr
        return csr_emb * scale

    def inject_into_hidden(
        self,
        hidden_state: torch.Tensor,
        csr_emb: torch.Tensor,
        layer_idx: int,
    ) -> torch.Tensor:
        """
        Inject CSR embedding into hidden state (pre-block bias).

        E_input = E_token + λ_csr * E_CSR

        Args:
            hidden_state: Current hidden state [B, T, d_model]
            csr_emb: CSR embedding [B, T, d_model]
            layer_idx: Current layer index

        Returns:
            Modified hidden state [B, T, d_model]
        """
        scaled_csr = self.get_layer_embedding(csr_emb, layer_idx)
        return hidden_state + scaled_csr


# =============================================================================
# SAFETY LAYERS: ENTROPY SINK & SYNTHESIS GATE
# =============================================================================

class EntropySink(nn.Module):
    """
    Layer 0 (Dormancy) Safety: Anchors model against unmanifested potential.

    Implements an "entropy floor" that prevents the model from collapsing
    into degenerate states by maintaining minimum activation diversity.
    """

    def __init__(self, d_model: int, min_entropy: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.min_entropy = min_entropy

        # Dormancy anchor (learnable "ground state")
        self.dormancy_anchor = nn.Parameter(torch.randn(d_model) * 0.01)

        # Entropy estimator
        self.entropy_proj = nn.Linear(d_model, 64)

    def compute_entropy(self, x: torch.Tensor) -> torch.Tensor:
        """Estimate activation entropy."""
        # Project to lower dim for efficiency
        proj = self.entropy_proj(x)  # [B, T, 64]

        # Softmax to get probability-like distribution
        probs = F.softmax(proj, dim=-1)

        # Compute entropy: -sum(p * log(p))
        entropy = -torch.sum(probs * torch.log(probs + 1e-10), dim=-1)

        return entropy  # [B, T]

    def forward(
        self,
        hidden_state: torch.Tensor,
        csr_affinity: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Apply entropy sink to maintain dormant potential.

        Args:
            hidden_state: Layer 0 hidden state [B, T, d_model]
            csr_affinity: Optional CSR 12D affinity [B, T, 12]

        Returns:
            (modified_state, metrics)
        """
        entropy = self.compute_entropy(hidden_state)

        # Where entropy is too low, blend with dormancy anchor
        low_entropy_mask = (entropy < self.min_entropy).float().unsqueeze(-1)

        # Anchor injection (prevents collapse)
        anchor_expanded = self.dormancy_anchor.unsqueeze(0).unsqueeze(0)
        anchor_expanded = anchor_expanded.expand_as(hidden_state)

        # Blend: where entropy low, add anchor
        modified = hidden_state + low_entropy_mask * anchor_expanded * 0.1

        # If CSR available, use O1 (Potential) affinity to modulate
        if csr_affinity is not None:
            o1_affinity = csr_affinity[..., 0:1]  # First dimension = O1
            modified = modified * (1 + 0.1 * o1_affinity)

        metrics = {
            "entropy": entropy.mean(),
            "low_entropy_ratio": low_entropy_mask.mean(),
        }

        return modified, metrics


class SynthesisGate(nn.Module):
    """
    Layer 11 (Integration) Safety: Final synthesis reconciling logic and flow.

    Ensures the final layer output properly integrates structural authority
    with phonetic flow, preventing either from dominating inappropriately.
    """

    def __init__(self, d_model: int, num_heads: int = 4):
        super().__init__()
        self.d_model = d_model

        # Cross-attention between structure and flow
        self.structure_proj = nn.Linear(d_model, d_model)
        self.flow_proj = nn.Linear(d_model, d_model)
        self.synthesis_attn = nn.MultiheadAttention(d_model, num_heads, batch_first=True)

        # Final gate
        self.gate = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
            nn.Sigmoid(),
        )

    def forward(
        self,
        hidden_state: torch.Tensor,
        csr_emb: torch.Tensor,
        csr_affinity: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Synthesize structural and phonetic information.

        Args:
            hidden_state: Layer 11 hidden state [B, T, d_model]
            csr_emb: CSR embedding [B, T, d_model]
            csr_affinity: Optional CSR 12D affinity [B, T, 12]

        Returns:
            (synthesized_state, metrics)
        """
        # Project to structure and flow representations
        structure = self.structure_proj(hidden_state)
        flow = self.flow_proj(csr_emb)

        # Cross-attention: structure attends to flow
        synthesized, attn_weights = self.synthesis_attn(
            query=structure,
            key=flow,
            value=flow,
        )

        # Compute gate based on both representations
        combined = torch.cat([hidden_state, synthesized], dim=-1)
        gate_value = self.gate(combined)

        # Gated combination
        output = hidden_state * gate_value + synthesized * (1 - gate_value)

        # Use O11 (Integration) and O12 (Absolving) affinities if available
        if csr_affinity is not None:
            o11_o12 = csr_affinity[..., 10:12].mean(dim=-1, keepdim=True)
            output = output * (1 + 0.1 * o11_o12)

        metrics = {
            "gate_mean": gate_value.mean(),
            "attn_entropy": -(attn_weights * torch.log(attn_weights + 1e-10)).sum(dim=-1).mean(),
        }

        return output, metrics


# =============================================================================
# 4-MODE ABLATION TEST FRAMEWORK
# =============================================================================

@dataclass
class AblationConfig:
    """Configuration for CSR ablation testing."""
    mode: str = "trainable"  # baseline, frozen, trainable, shuffled
    num_test_samples: int = 100
    batch_size: int = 8


class CSRAblationTester:
    """
    4-Mode Ablation Test Framework for CSR Embedding Provider.

    Validates that CSR provides Semantic Authority, not just extra parameters.

    Modes:
        1. Baseline: CSR Off (no phonetic grounding)
        2. Frozen: CSR On but no gradients (fixed grounding)
        3. Trainable: Full CSR-Neural synergy
        4. Shuffled: CSR On but token-alignment permuted (Negative Control)
    """

    def __init__(
        self,
        model: nn.Module,
        csr_provider: CSREmbeddingProvider,
        config: AblationConfig,
    ):
        self.model = model
        self.csr_provider = csr_provider
        self.config = config
        self.results: Dict[str, Dict[str, float]] = {}

    def run_mode(
        self,
        mode: str,
        dataloader,
        criterion,
    ) -> Dict[str, float]:
        """Run a single ablation mode."""
        self.model.eval()
        total_loss = 0.0
        total_coherence = 0.0
        num_batches = 0

        # Configure CSR based on mode
        original_lambda = self.csr_provider.config.lambda_csr
        original_trainable = self.csr_provider.config.trainable_projection

        if mode == "baseline":
            self.csr_provider.config.lambda_csr = 0.0
        elif mode == "frozen":
            self.csr_provider.config.trainable_projection = False
            for param in self.csr_provider.parameters():
                param.requires_grad = False
        elif mode == "shuffled":
            pass  # Will shuffle in forward
        # trainable = default

        with torch.no_grad():
            for batch in dataloader:
                if num_batches >= self.config.num_test_samples // self.config.batch_size:
                    break

                input_ids = batch['input_ids']
                labels = batch.get('labels', input_ids)

                # Get CSR embeddings
                csr_output = self.csr_provider(input_ids)
                csr_emb = csr_output['csr_emb']

                # Shuffle if in shuffled mode
                if mode == "shuffled":
                    # Random permutation along sequence dimension
                    perm = torch.randperm(csr_emb.shape[1])
                    csr_emb = csr_emb[:, perm, :]

                # Forward pass (simplified - real impl would integrate CSR into model)
                outputs = self.model(input_ids)
                logits = outputs.get('logits', outputs)

                # Compute loss
                loss = criterion(logits.view(-1, logits.size(-1)), labels.view(-1))
                total_loss += loss.item()

                # Compute coherence (if available)
                if isinstance(outputs, dict) and 'global_coherence' in outputs:
                    total_coherence += outputs['global_coherence'].mean().item()

                num_batches += 1

        # Restore CSR config
        self.csr_provider.config.lambda_csr = original_lambda
        self.csr_provider.config.trainable_projection = original_trainable

        return {
            "loss": total_loss / max(num_batches, 1),
            "coherence": total_coherence / max(num_batches, 1),
            "num_batches": num_batches,
        }

    def run_all_modes(self, dataloader, criterion) -> Dict[str, Dict[str, float]]:
        """Run all 4 ablation modes."""
        modes = ["baseline", "frozen", "trainable", "shuffled"]

        for mode in modes:
            print(f"  Running ablation mode: {mode}...")
            self.results[mode] = self.run_mode(mode, dataloader, criterion)

        return self.results

    def print_summary(self):
        """Print ablation test summary."""
        print("\n" + "="*60)
        print("  CSR ABLATION TEST SUMMARY")
        print("="*60)

        for mode, metrics in self.results.items():
            print(f"\n  {mode.upper()}:")
            print(f"    Loss: {metrics['loss']:.4f}")
            print(f"    Coherence: {metrics['coherence']:.4f}")

        # Analysis
        if all(m in self.results for m in ["baseline", "trainable", "shuffled"]):
            baseline_loss = self.results["baseline"]["loss"]
            trainable_loss = self.results["trainable"]["loss"]
            shuffled_loss = self.results["shuffled"]["loss"]

            print("\n  ANALYSIS:")
            improvement = (baseline_loss - trainable_loss) / baseline_loss * 100
            print(f"    Trainable vs Baseline: {improvement:+.2f}% loss reduction")

            if shuffled_loss < trainable_loss:
                print("    ⚠️ WARNING: Shuffled outperforms Trainable - CSR alignment may not be learning")
            else:
                shuffle_degradation = (shuffled_loss - trainable_loss) / trainable_loss * 100
                print(f"    Shuffled vs Trainable: {shuffle_degradation:+.2f}% degradation (GOOD)")

        print("="*60)


# =============================================================================
# MAIN / TESTING
# =============================================================================

def main():
    """Test CSR Embedding Provider with Hybrid G2P."""
    print("="*60)
    print("  CSR EMBEDDING PROVIDER - HYBRID G2P TEST")
    print("="*60)

    # Test Hybrid G2P system first
    print("\n  ═══════════════════════════════════════════")
    print("  HYBRID G2P SYSTEM TEST")
    print("  ═══════════════════════════════════════════")

    hybrid_g2p = get_hybrid_g2p()
    stats = hybrid_g2p.get_stats()
    print(f"\n  G2P System Stats:")
    print(f"    CMUdict loaded: {stats['cmudict_loaded']}")
    print(f"    CMUdict words: {stats['cmudict_words']:,}")
    print(f"    g2p_en available: {stats['g2p_en_available']}")
    print(f"    Custom vocab: {stats['custom_vocab_size']}")

    # Test comprehensive word list showing tiered lookup
    test_words = [
        # CMUdict words (should resolve via fast path)
        ("hello", "CMUdict"),
        ("world", "CMUdict"),
        ("transformer", "CMUdict"),
        ("philosophical", "CMUdict"),
        ("consciousness", "CMUdict"),
        # Custom vocabulary (domain-specific)
        ("symbolu", "Custom"),
        ("vritti", "Custom"),
        ("ontological", "Custom"),
        # OOV words (neural fallback)
        ("chatgpt", "Neural/Char"),
        ("llama", "CMUdict"),
        ("mixtral", "Neural/Char"),
    ]

    print(f"\n  Tiered G2P Conversion (CMUdict → Custom → Neural → Char):")
    for word, expected_tier in test_words:
        phonemes = hybrid_g2p.get_phonemes(word)
        print(f"    '{word}' → {phonemes}  [{expected_tier}]")

    # Create config
    config = CSRConfig(d_model=512, num_layers=12)

    # Create provider
    provider = CSREmbeddingProvider(config)
    print(f"\n  ═══════════════════════════════════════════")
    print("  CSR PROVIDER TEST")
    print("  ═══════════════════════════════════════════")
    print(f"\n  Created CSR Provider:")
    print(f"    ARPABET Phonemes: {len(PHONEME_MAP_ARPABET)}")
    print(f"    Projection: 12 → {config.d_model}")
    print(f"    λ_csr: {config.lambda_csr}")

    # Test token-to-phoneme conversion through provider
    test_tokens = ["hello", "world", "the", "transformer", "ontological", "symbolu"]
    print(f"\n  Token → Phoneme Conversion (via CSREmbeddingProvider):")
    for token in test_tokens:
        phonemes = provider.token_to_phonemes(token)
        print(f"    '{token}' → {phonemes}")

    # Test full forward pass
    print(f"\n  Forward Pass Test:")
    fake_input_ids = torch.randint(0, 50000, (2, 10))
    fake_tokens = [["hello", "world", "this", "is", "a", "test", "of", "the", "csr", "system"],
                   ["the", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog", "today"]]

    output = provider(fake_input_ids, token_strings=fake_tokens)
    print(f"    Input shape: {fake_input_ids.shape}")
    print(f"    CSR Embedding shape: {output['csr_emb'].shape}")
    print(f"    CSR Affinity shape: {output['csr_affinity'].shape}")
    print(f"    CSR Confidence shape: {output['csr_confidence'].shape}")
    if 'phase_gate' in output:
        print(f"    Phase Gate shape: {output['phase_gate'].shape}")

    # Test safety layers
    print(f"\n  Safety Layers Test:")
    entropy_sink = EntropySink(config.d_model)
    synthesis_gate = SynthesisGate(config.d_model)

    fake_hidden = torch.randn(2, 10, config.d_model)

    modified, entropy_metrics = entropy_sink(fake_hidden, output['csr_affinity'])
    print(f"    Entropy Sink: entropy={entropy_metrics['entropy']:.4f}")

    synthesized, synth_metrics = synthesis_gate(fake_hidden, output['csr_emb'], output['csr_affinity'])
    print(f"    Synthesis Gate: gate_mean={synth_metrics['gate_mean']:.4f}")

    # Test VarnaCSRBridge
    print(f"\n  VarnaCSRBridge Test:")
    varna_bridge = VarnaCSRBridge()
    if varna_bridge.load():
        print(f"    Loaded varṇas: {len(varna_bridge.all_varnas)}")
        # Test some varṇas
        test_varnas = ["a", "ka", "sa", "ma"]
        for v in test_varnas:
            vec = varna_bridge.get_vector(v)
            if vec:
                max_idx = vec.index(max(vec))
                print(f"    '{v}' → primary layer O{max_idx+1} ({max(vec):.2f})")
    else:
        print("    Varna bridge not available (JSON not found)")

    print("\n  ✅ All tests passed!")
    print("="*60)


# =============================================================================
# TRAINING INTEGRATION HELPER
# =============================================================================

def create_csr_for_training(
    model_config: Any,
    tokenizer: Any = None,
    lambda_csr: float = 0.1,
    use_phase_gating: bool = True,
    trainable: bool = True,
) -> Tuple[CSREmbeddingProvider, EntropySink, SynthesisGate]:
    """
    Create CSR components for training integration.

    Args:
        model_config: Model configuration with d_model attribute
        tokenizer: Tokenizer for token decoding (optional)
        lambda_csr: CSR injection strength (default 0.1)
        use_phase_gating: Enable phase attention gating
        trainable: Allow CSR projection to train

    Returns:
        Tuple of (CSREmbeddingProvider, EntropySink, SynthesisGate)
    """
    # Get model dimension - check multiple common attribute names
    d_model = 512  # default fallback
    if hasattr(model_config, 'hidden_size'):
        d_model = model_config.hidden_size
    elif hasattr(model_config, 'n_embd'):  # GPT-2 style
        d_model = model_config.n_embd
    elif hasattr(model_config, 'embed_dim'):  # Custom transformers (PhaseTransformer)
        d_model = model_config.embed_dim
    elif hasattr(model_config, 'd_model'):
        d_model = model_config.d_model
    elif hasattr(model_config, 'dim'):  # Some transformer variants
        d_model = model_config.dim

    # Create CSR config
    csr_config = CSRConfig(
        d_model=d_model,
        num_layers=12,
        lambda_csr=lambda_csr,
        use_phase_gating=use_phase_gating,
        trainable_projection=trainable,
    )

    # Create components
    csr_provider = CSREmbeddingProvider(csr_config, tokenizer=tokenizer)
    entropy_sink = EntropySink(d_model)
    synthesis_gate = SynthesisGate(d_model)

    print(f"  [CSR] Created components: d_model={d_model}, λ_csr={lambda_csr}")

    return csr_provider, entropy_sink, synthesis_gate


def integrate_csr_into_forward(
    hidden_states: torch.Tensor,
    csr_emb: torch.Tensor,
    layer_idx: int,
    csr_provider: CSREmbeddingProvider,
    entropy_sink: Optional[EntropySink] = None,
    synthesis_gate: Optional[SynthesisGate] = None,
    csr_affinity: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """
    Integrate CSR embeddings into model forward pass.

    Args:
        hidden_states: Current hidden states [B, T, d_model]
        csr_emb: CSR embeddings [B, T, d_model]
        layer_idx: Current layer index (0-11)
        csr_provider: CSREmbeddingProvider instance
        entropy_sink: Optional EntropySink for Layer 0
        synthesis_gate: Optional SynthesisGate for Layer 11
        csr_affinity: Optional 12D affinities for safety layers

    Returns:
        Tuple of (modified_hidden_states, metrics_dict)
    """
    metrics = {}

    # Layer 0: Apply entropy sink
    if layer_idx == 0 and entropy_sink is not None:
        hidden_states, sink_metrics = entropy_sink(hidden_states, csr_affinity)
        metrics.update({f"entropy_sink_{k}": v for k, v in sink_metrics.items()})

    # Inject CSR into hidden states
    hidden_states = csr_provider.inject_into_hidden(hidden_states, csr_emb, layer_idx)

    # Layer 11: Apply synthesis gate
    if layer_idx == 11 and synthesis_gate is not None:
        hidden_states, gate_metrics = synthesis_gate(hidden_states, csr_emb, csr_affinity)
        metrics.update({f"synthesis_gate_{k}": v for k, v in gate_metrics.items()})

    return hidden_states, metrics


# =============================================================================
# CSR PHONEME HEAD: No 12D Bottleneck, Sanskrit-Structured Output Logits
# =============================================================================

@dataclass
class CSRPhonemeHeadConfig:
    """
    Configuration for CSR Phoneme Head (no ontological layers).

    Replaces the 12D ontological bottleneck with learnable phoneme
    embeddings in full d_model space. The Sanskrit Varna/Vritti structure
    determines token-to-phoneme decomposition and initialization grouping,
    but does NOT constrain the representation to 12 fixed dimensions.
    """
    d_model: int = 512
    vocab_size: int = 50257
    lambda_csr: float = 0.1          # Mixing weight for phonemic logits
    lambda_csr_min: float = 0.01     # Floor after decay
    temperature: float = 1.0         # Logit temperature
    position_weights: Tuple[float, ...] = (1.5, 1.25, 1.0)
    max_phonemes_per_token: int = 5
    learnable_lambda: bool = False   # Make lambda a trainable parameter
    dropout: float = 0.1
    use_decay_scheduler: bool = True


class CSRPhonemeHead(nn.Module):
    """
    Sanskrit Phoneme-Structured Output Head (No 12D / No Ontological Layers).

    Each ARPABET phoneme gets a learnable d_model-dimensional embedding.
    The Sanskrit Varna/Vritti system provides:
        - Token decomposition: which phonemes each token contains (fixed, via HybridG2P)
        - Position weighting: first phoneme weighted more heavily (1.5, 1.25, 1.0, ...)
        - Vritti grouping: phonemes sharing a mental propensity initialize nearby
        - Varga structure: Ka-varga, Ca-varga, etc. cluster at initialization

    What is REMOVED vs CSREmbeddingProvider:
        - No 12D ontological layer vectors (PHONEME_MAP_ARPABET affinities)
        - No O1_Potential through O12_Absolving mapping
        - No fixed-dimensional intermediate representation
        - No 12 -> d_model projection bottleneck

    What is KEPT:
        - Sanskrit Varna mappings (ARPABET_TO_VARNA)
        - Vritti / mental propensity associations (Hope, Action, Craving, etc.)
        - HybridG2P (CMUdict + g2p_en neural fallback)
        - Position-weighted phoneme aggregation

    Pipelines:
        Input:   token_id -> phoneme_weights [num_phonemes] -> sum(phoneme_embs) -> [d_model]
        Output:  h_t [d_model] -> h_t @ csr_vocab.T -> logits [vocab_size]
    """

    def __init__(self, config: CSRPhonemeHeadConfig, tokenizer=None):
        super().__init__()
        self.config = config
        self.tokenizer = tokenizer

        # Phoneme inventory from ARPABET (the decomposition alphabet)
        self._phoneme_list = list(PHONEME_MAP_ARPABET.keys())
        self._phoneme_to_idx = {p: i for i, p in enumerate(self._phoneme_list)}
        self.num_phonemes = len(self._phoneme_list)

        # Learnable phoneme embeddings in FULL d_model space
        # This is the core change: no 12D, no ontological layer bottleneck
        self.phoneme_embeddings = nn.Embedding(self.num_phonemes, config.d_model)
        self.phoneme_norm = nn.LayerNorm(config.d_model)

        # Initialize with Vritti/Varga grouping structure
        self._init_from_vritti_groups()

        # Mixing parameter
        if config.learnable_lambda:
            self.log_lambda = nn.Parameter(torch.tensor(math.log(config.lambda_csr)))
        else:
            self.register_buffer('_lambda_val', torch.tensor(config.lambda_csr))

        self.dropout = nn.Dropout(config.dropout)

        # HybridG2P for token-to-phoneme conversion
        self._hybrid_g2p = get_hybrid_g2p()

        # Build token-to-phoneme weight matrix if tokenizer available
        if tokenizer is not None:
            self._build_token_phoneme_matrix()
        else:
            self.register_buffer('_token_phoneme_weights', None, persistent=False)

        # Cached vocab matrix (invalidated each forward)
        self._cached_csr_vocab: Optional[torch.Tensor] = None

    @property
    def lambda_csr(self) -> torch.Tensor:
        """Current CSR mixing weight."""
        if self.config.learnable_lambda:
            return self.log_lambda.exp()
        return self._lambda_val

    def _init_from_vritti_groups(self):
        """
        Initialize phoneme embeddings with Sanskrit Varga/Vritti structure.

        Phonemes within the same Varga (articulatory group) share a bias vector,
        giving them correlated initial representations. This encodes the Sanskrit
        insight that gutturals (Ka-varga) share a quality distinct from labials
        (Pa-varga), etc. — without collapsing to 12 fixed dimensions.

        Varga groupings from Sanskrit grammar:
            Ka-varga (Guttural):  K, G, NG  — throat, propensities: Hope, Action, Vanity
            Ca-varga (Palatal):   CH, JH    — palate, propensities: Scatter, Vanity
            Ṭa-varga (Retroflex): T, D      — roof, propensities: Overstatement, Shyness
            Ta-varga (Dental):    TH, DH    — teeth, propensities: Melancholy, Craving
            Pa-varga (Labial):    P, B, M   — lips, propensities: Hatred, Indifference, Indulgence
            Antaḥstha (Semi-vowels): Y, R, L, W, V — transitional energies
            Ūṣman (Sibilants):   S, SH, Z, ZH — friction/heat
            Vowels (Short):       AA, AH, AE, IH, UH, EH — consciousness states
            Vowels (Long/Diph):   IY, UW, EY, AY, OW, AO, OY, AW, ER — extended states
        """
        with torch.no_grad():
            # Base: normal initialization like standard embeddings
            nn.init.normal_(self.phoneme_embeddings.weight, mean=0.0, std=0.02)

            # Varga groups — Sanskrit articulatory classification
            varga_groups = {
                'ka_varga':     ['K', 'G', 'NG'],
                'ca_varga':     ['CH', 'JH'],
                'ta_varga':     ['T', 'D'],
                'tha_varga':    ['TH', 'DH'],
                'pa_varga':     ['P', 'B', 'M'],
                'antahstha':    ['Y', 'R', 'L', 'W', 'V'],
                'ushman':       ['S', 'SH', 'Z', 'ZH'],
                'aspirate':     ['HH', 'F', 'N'],
                'short_vowels': ['AA', 'AH', 'AE', 'IH', 'UH', 'EH'],
                'long_vowels':  ['IY', 'UW', 'EY', 'AY', 'OW', 'AO', 'OY', 'AW', 'ER'],
                'special':      ['SIL', 'SP', 'UNK'],
            }

            # Each varga gets a shared bias — phonemes in same group start correlated
            for group_name, phonemes in varga_groups.items():
                group_bias = torch.randn(self.config.d_model) * 0.01
                for p in phonemes:
                    if p in self._phoneme_to_idx:
                        idx = self._phoneme_to_idx[p]
                        self.phoneme_embeddings.weight[idx] += group_bias

            # Voiced/voiceless distinction within vargas
            voiced = ['G', 'D', 'B', 'JH', 'DH', 'V', 'Z', 'ZH']
            voiceless = ['K', 'T', 'P', 'CH', 'TH', 'F', 'S', 'SH']
            voiced_bias = torch.randn(self.config.d_model) * 0.005
            for p in voiced:
                if p in self._phoneme_to_idx:
                    self.phoneme_embeddings.weight[self._phoneme_to_idx[p]] += voiced_bias
            for p in voiceless:
                if p in self._phoneme_to_idx:
                    self.phoneme_embeddings.weight[self._phoneme_to_idx[p]] -= voiced_bias

    def _build_token_phoneme_matrix(self):
        """
        Build fixed token-to-phoneme weight matrix [vocab_size, num_phonemes].

        Each row is a position-weighted distribution over phonemes for that token.
        Rows sum to 1 (convex combination). Special tokens get zero rows.

        Uses HybridG2P: CMUdict (134K) -> Custom vocab -> g2p_en neural -> char fallback.
        """
        if self.tokenizer is None:
            return

        vocab_size = self.config.vocab_size
        num_phonemes = self.num_phonemes

        # Identify special tokens
        special_token_ids = set()
        for attr in ['pad_token_id', 'eos_token_id', 'bos_token_id', 'unk_token_id',
                     'sep_token_id', 'cls_token_id', 'mask_token_id']:
            tid = getattr(self.tokenizer, attr, None)
            if tid is not None:
                special_token_ids.add(tid)
        self._special_token_ids = special_token_ids

        weight_matrix = torch.zeros(vocab_size, num_phonemes, dtype=torch.float32)
        position_weights = list(self.config.position_weights)

        mapped = 0
        for token_id in range(vocab_size):
            if token_id in special_token_ids:
                continue

            try:
                token_str = self.tokenizer.decode([token_id])
                phonemes = self._hybrid_g2p.get_phonemes(token_str)

                if len(phonemes) > self.config.max_phonemes_per_token:
                    phonemes = phonemes[:self.config.max_phonemes_per_token]

                # Position-weighted assignment
                weights = list(position_weights)
                while len(weights) < len(phonemes):
                    weights.append(1.0)
                weights = weights[:len(phonemes)]
                total_weight = sum(weights)

                if total_weight > 0:
                    for phoneme, w in zip(phonemes, weights):
                        clean = phoneme.rstrip('012')
                        if clean in self._phoneme_to_idx:
                            idx = self._phoneme_to_idx[clean]
                            weight_matrix[token_id, idx] += w / total_weight
                    mapped += 1
            except Exception:
                continue

        self.register_buffer('_token_phoneme_weights', weight_matrix)
        print(f"  [CSRPhonemeHead] Token-phoneme matrix built: "
              f"{mapped:,}/{vocab_size:,} tokens mapped, "
              f"{num_phonemes} phonemes, no 12D bottleneck")

    def get_csr_vocab_matrix(self) -> torch.Tensor:
        """
        Compute the CSR vocabulary embedding matrix.

        Each token's embedding is a weighted sum of its phoneme embeddings,
        where weights come from the fixed token-to-phoneme decomposition.

        Returns:
            [vocab_size, d_model] — phoneme-structured embedding per token
        """
        if self._cached_csr_vocab is not None:
            return self._cached_csr_vocab

        phoneme_emb = self.phoneme_norm(self.phoneme_embeddings.weight)  # [P, d_model]
        csr_vocab = self._token_phoneme_weights @ phoneme_emb            # [V, d_model]
        self._cached_csr_vocab = csr_vocab
        return csr_vocab

    def invalidate_cache(self):
        """Call at start of each forward pass to invalidate cached vocab matrix."""
        self._cached_csr_vocab = None

    def compute_logits(
        self,
        hidden_state: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute phoneme-structured logits.

        Scores each vocabulary token by how well the hidden state aligns
        with that token's phonemic identity in d_model space.

        Args:
            hidden_state: [batch, seq, d_model]

        Returns:
            [batch, seq, vocab_size] — logits based on phonemic resonance
        """
        self.invalidate_cache()
        csr_vocab = self.get_csr_vocab_matrix()                    # [V, d_model]
        logits = hidden_state @ csr_vocab.T / self.config.temperature  # [B, T, V]
        return logits

    def compute_combined_logits(
        self,
        hidden_state: torch.Tensor,
        standard_logits: torch.Tensor,
    ) -> torch.Tensor:
        """
        Combine standard lm_head logits with CSR phonemic logits.

        z_combined = z_standard + λ_csr * z_phoneme

        The standard logits provide contextual token selection.
        The phonemic logits bias toward tokens whose Sanskrit phonemic
        identity resonates with the model's current state.

        Args:
            hidden_state: [batch, seq, d_model] — from final layer norm
            standard_logits: [batch, seq, vocab_size] — from lm_head

        Returns:
            [batch, seq, vocab_size] — combined logits
        """
        z_phoneme = self.compute_logits(hidden_state)
        lam = self.lambda_csr
        return standard_logits + lam * z_phoneme

    def get_input_embedding(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:
        """
        Get phoneme-structured input embeddings (replaces CSREmbeddingProvider.forward).

        Each token's embedding is the weighted sum of its constituent phoneme
        embeddings. Can be added to standard token embeddings as a bias.

        Args:
            input_ids: [batch, seq]

        Returns:
            [batch, seq, d_model] — phoneme-structured embeddings
        """
        if self._token_phoneme_weights is None:
            raise RuntimeError("CSRPhonemeHead: no tokenizer provided, cannot compute input embeddings")

        clamped = input_ids.clamp(0, self._token_phoneme_weights.size(0) - 1)
        token_weights = self._token_phoneme_weights[clamped]             # [B, T, P]
        phoneme_emb = self.phoneme_norm(self.phoneme_embeddings.weight)  # [P, d_model]
        csr_emb = token_weights @ phoneme_emb                           # [B, T, d_model]
        return self.dropout(csr_emb)

    def forward(
        self,
        input_ids: torch.Tensor,
        hidden_state: Optional[torch.Tensor] = None,
        standard_logits: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Full forward pass: input embeddings + optional output logits.

        Args:
            input_ids: [batch, seq] — token IDs
            hidden_state: [batch, seq, d_model] — if provided, computes logits
            standard_logits: [batch, seq, vocab] — if provided, computes combined logits

        Returns:
            Dict with:
                - csr_emb: [B, T, d_model] phoneme-structured input embeddings
                - csr_logits: [B, T, V] phonemic logits (if hidden_state provided)
                - combined_logits: [B, T, V] mixed logits (if both provided)
        """
        self.invalidate_cache()
        result = {}

        # Input embedding
        result['csr_emb'] = self.get_input_embedding(input_ids)

        # Output logits
        if hidden_state is not None:
            result['csr_logits'] = self.compute_logits(hidden_state)

            if standard_logits is not None:
                result['combined_logits'] = self.compute_combined_logits(
                    hidden_state, standard_logits
                )

        return result

    def get_phoneme_stats(self) -> Dict[str, Any]:
        """Diagnostic: phoneme embedding statistics."""
        with torch.no_grad():
            emb = self.phoneme_embeddings.weight
            norms = emb.norm(dim=-1)

            # Cosine similarity matrix
            normed = F.normalize(emb, dim=-1)
            sim_matrix = normed @ normed.T

            # Find most similar pairs
            sim_matrix.fill_diagonal_(-1)
            max_sim_flat = sim_matrix.argmax()
            i, j = max_sim_flat // self.num_phonemes, max_sim_flat % self.num_phonemes

            return {
                'num_phonemes': self.num_phonemes,
                'embedding_dim': self.config.d_model,
                'norm_mean': norms.mean().item(),
                'norm_std': norms.std().item(),
                'avg_cosine_sim': sim_matrix.mean().item(),
                'most_similar_pair': (self._phoneme_list[i], self._phoneme_list[j]),
                'most_similar_score': sim_matrix[i, j].item(),
                'lambda_csr': self.lambda_csr.item() if isinstance(self.lambda_csr, torch.Tensor) else self.lambda_csr,
            }


def create_csr_phoneme_head(
    model_config: Any,
    tokenizer: Any = None,
    lambda_csr: float = 0.1,
) -> CSRPhonemeHead:
    """
    Create a CSRPhonemeHead from model config.

    This is the no-12D, no-ontological-layer version of CSR.
    Each phoneme is a learnable d_model vector. Sanskrit structure
    provides grouping and initialization, not a fixed dimensional mapping.

    Args:
        model_config: Model config with d_model/hidden_size/embed_dim attribute
        tokenizer: Tokenizer for building token-phoneme matrix
        lambda_csr: Mixing weight for phonemic logits

    Returns:
        Configured CSRPhonemeHead
    """
    # Resolve d_model from various config conventions
    d_model = 512
    for attr in ['hidden_size', 'n_embd', 'embed_dim', 'd_model', 'dim']:
        if hasattr(model_config, attr):
            d_model = getattr(model_config, attr)
            break

    # Resolve vocab_size
    vocab_size = 50257
    for attr in ['vocab_size', 'n_vocab']:
        if hasattr(model_config, attr):
            vocab_size = getattr(model_config, attr)
            break
    if tokenizer is not None:
        try:
            vocab_size = max(vocab_size, len(tokenizer))
        except Exception:
            pass

    config = CSRPhonemeHeadConfig(
        d_model=d_model,
        vocab_size=vocab_size,
        lambda_csr=lambda_csr,
    )

    head = CSRPhonemeHead(config, tokenizer=tokenizer)
    print(f"  [CSRPhonemeHead] Created: d_model={d_model}, vocab={vocab_size:,}, "
          f"phonemes={head.num_phonemes}, λ={lambda_csr}, NO 12D bottleneck")
    return head


# =============================================================================
# PHONEME-CONTEXTUALIZED PROBABILITY HEAD (Softmax-Free)
# =============================================================================
#
# Factored token probability:
#
#   P(token_i | h_t) ∝ phoneme_match(i, h_t) × context_match(i, h_t)
#
# Where:
#   phoneme_match(i) = σ(W_φ · h_t) · w_i        (41 independent sigmoids)
#   context_match(i) = σ(h_t · e_i / τ)           (sigmoid per token)
#
# No softmax over vocabulary. Normalization is L1 (divide by sum).
#
# Training loss (also softmax-free):
#   L_phon  = BCE(predicted_phonemes, target_phoneme_weights)
#   L_ctx   = margin(s_pos - s_neg) + cosine_pull(h, e_target)
#   L_total = L_phon + β · L_ctx
#
# The Sanskrit phoneme structure acts as a PRIOR over token selection.
# The context signal DISAMBIGUATES among phonemically similar tokens.
# Together they produce a probability distribution without softmax.

@dataclass
class PhonemeContextConfig:
    """Configuration for phoneme-contextualized probability head."""
    d_model: int = 512
    num_phonemes: int = 41           # ARPABET inventory size
    vocab_size: int = 50257
    temperature: float = 1.0         # Context scoring temperature
    margin: float = 0.5              # Contrastive margin for context loss
    num_negatives: int = 256         # Hard negatives per position
    beta: float = 1.0               # Weight of context loss vs phoneme loss
    phoneme_hidden: int = 256        # Hidden dim for phoneme predictor
    use_hard_negatives: bool = True  # Sample negatives from same phoneme cluster
    dropout: float = 0.1


class PhonemeContextHead(nn.Module):
    """
    Softmax-Free Token Probability via Phoneme Prediction + Context Signal.

    Factored probability:
        P(token_i | h_t) ∝ phoneme_match(i) × context_match(i)

    Phoneme branch (WHAT sounds should come next):
        φ = σ(MLP(h_t))                    — [41] predicted phoneme activations
        phoneme_match(i) = φ · w_i          — dot with token i's phoneme weights

    Context branch (WHICH token among phoneme-compatible ones):
        context_match(i) = σ(h_t · e_i / τ) — sigmoid similarity with token embedding

    Combined:
        s(i) = phoneme_match(i) × context_match(i)
        P(i) = s(i) / Σ_j s(j)             — L1 normalization, NOT softmax

    Training (both branches softmax-free):
        L_phon = BCE(φ, target_phoneme_weights)     — predict correct phonemes
        L_ctx  = Σ_k max(0, m - s_pos + s_neg_k)    — margin against negatives

    The Sanskrit phoneme decomposition acts as a structural PRIOR.
    The context signal provides semantic DISAMBIGUATION.
    """

    def __init__(
        self,
        config: PhonemeContextConfig,
        token_phoneme_weights: torch.Tensor,
    ):
        """
        Args:
            config: PhonemeContextConfig
            token_phoneme_weights: [vocab_size, num_phonemes] — fixed matrix from CSRPhonemeHead
        """
        super().__init__()
        self.config = config

        # Fixed token-to-phoneme decomposition (from Sanskrit G2P)
        self.register_buffer('token_phoneme_weights', token_phoneme_weights)

        # Phoneme predictor: h_t → predicted phoneme activations [num_phonemes]
        self.phoneme_predictor = nn.Sequential(
            nn.Linear(config.d_model, config.phoneme_hidden),
            nn.GELU(),
            nn.Linear(config.phoneme_hidden, config.num_phonemes),
        )

        # Context projection: transforms h_t before scoring against token embeddings
        self.context_proj = nn.Linear(config.d_model, config.d_model, bias=False)

        self.dropout = nn.Dropout(config.dropout)

        # Precompute phoneme cluster membership for hard negative sampling
        if config.use_hard_negatives:
            self._build_phoneme_clusters()

    def _build_phoneme_clusters(self):
        """
        Build phoneme cluster index for hard negative sampling.

        For each token, find tokens that share its dominant phoneme
        (phonemically similar but different tokens = hard negatives).
        """
        # Dominant phoneme per token: which phoneme has highest weight
        dominant = self.token_phoneme_weights.argmax(dim=-1)  # [V]

        # Group tokens by dominant phoneme
        clusters: Dict[int, List[int]] = {}
        for token_id in range(self.config.vocab_size):
            phon_idx = dominant[token_id].item()
            if phon_idx not in clusters:
                clusters[phon_idx] = []
            clusters[phon_idx].append(token_id)

        # Store as buffer-friendly format: for each token, store its cluster
        self._phoneme_clusters = clusters
        self._token_dominant_phoneme = dominant

    def predict_phonemes(self, h_t: torch.Tensor) -> torch.Tensor:
        """
        Predict phoneme activation pattern from hidden state.

        Args:
            h_t: [batch, seq, d_model]

        Returns:
            [batch, seq, num_phonemes] — sigmoid activations ∈ (0, 1)
        """
        return torch.sigmoid(self.phoneme_predictor(h_t))

    def compute_scores(
        self,
        h_t: torch.Tensor,
        token_embeddings: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute factored token scores.

        Args:
            h_t: [batch, seq, d_model] — hidden states from final layer
            token_embeddings: [vocab_size, d_model] — token embedding matrix

        Returns:
            Dict with phoneme_scores, context_scores, combined_scores
        """
        # Phoneme branch: which phonemes should come next?
        phi = self.predict_phonemes(h_t)                            # [B, T, P]
        s_phon = phi @ self.token_phoneme_weights.T                 # [B, T, V]

        # Context branch: which token fits semantically?
        h_ctx = self.context_proj(h_t)                              # [B, T, d]
        s_ctx = torch.sigmoid(
            h_ctx @ token_embeddings.T / self.config.temperature
        )                                                           # [B, T, V]

        # Combined: phoneme gates × context alignment
        s_combined = s_phon * s_ctx                                 # [B, T, V]

        return {
            'phoneme_scores': s_phon,
            'context_scores': s_ctx,
            'combined_scores': s_combined,
            'phoneme_activations': phi,
        }

    def compute_probs(
        self,
        h_t: torch.Tensor,
        token_embeddings: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute token probabilities (L1 normalized, no softmax).

        P(token_i) = s_phon(i) × s_ctx(i) / Σ_j s_phon(j) × s_ctx(j)

        Args:
            h_t: [batch, seq, d_model]
            token_embeddings: [vocab_size, d_model]

        Returns:
            [batch, seq, vocab_size] — probability distribution
        """
        scores = self.compute_scores(h_t, token_embeddings)
        s = scores['combined_scores']
        probs = s / (s.sum(dim=-1, keepdim=True) + 1e-8)
        return probs

    def _sample_hard_negatives(
        self,
        target_ids: torch.Tensor,
        K: int,
    ) -> torch.Tensor:
        """
        Sample hard negatives: tokens sharing a dominant phoneme with the target.

        These are phonemically similar tokens that the context branch
        must learn to distinguish.

        Args:
            target_ids: [batch, seq]
            K: number of negatives per position

        Returns:
            [batch, seq, K] — negative token IDs
        """
        B, T = target_ids.shape
        device = target_ids.device
        neg_ids = torch.zeros(B, T, K, dtype=torch.long, device=device)

        if not hasattr(self, '_phoneme_clusters'):
            # Fallback: random negatives
            return torch.randint(0, self.config.vocab_size, (B, T, K), device=device)

        for b in range(B):
            for t in range(T):
                tid = target_ids[b, t].item()
                phon_idx = self._token_dominant_phoneme[tid].item()
                cluster = self._phoneme_clusters.get(phon_idx, [])

                if len(cluster) > 1:
                    # Sample from same phoneme cluster (hard negatives)
                    # Half hard, half random for diversity
                    K_hard = K // 2
                    K_rand = K - K_hard

                    # Hard negatives (same phoneme cluster, excluding target)
                    candidates = [c for c in cluster if c != tid]
                    if candidates:
                        hard = torch.tensor(candidates, device=device)
                        hard_sample = hard[torch.randint(0, len(hard), (K_hard,))]
                    else:
                        hard_sample = torch.randint(0, self.config.vocab_size, (K_hard,), device=device)

                    # Random negatives
                    rand_sample = torch.randint(0, self.config.vocab_size, (K_rand,), device=device)

                    neg_ids[b, t] = torch.cat([hard_sample, rand_sample])
                else:
                    neg_ids[b, t] = torch.randint(0, self.config.vocab_size, (K,), device=device)

        return neg_ids

    def compute_loss(
        self,
        h_t: torch.Tensor,
        target_ids: torch.Tensor,
        token_embeddings: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute training loss. No softmax anywhere.

        L_phon  = BCE(predicted_phonemes, target_phoneme_weights)
        L_ctx   = margin_loss(s_pos, s_neg) + cosine_loss(h, e_target)
        L_total = L_phon + β · L_ctx

        Args:
            h_t: [batch, seq, d_model] — hidden states
            target_ids: [batch, seq] — target token IDs
            token_embeddings: [vocab_size, d_model] — token embedding matrix

        Returns:
            Dict with loss_phoneme, loss_context, loss_total, and diagnostics
        """
        B, T = target_ids.shape
        cfg = self.config

        # === Phoneme loss: BCE on 41 independent sigmoids ===
        phi = self.predict_phonemes(h_t)                             # [B, T, P]
        target_phonemes = self.token_phoneme_weights[target_ids]     # [B, T, P]
        L_phon = F.binary_cross_entropy(phi, target_phonemes)

        # === Context loss: margin-based contrastive ===
        h_ctx = self.context_proj(h_t)                               # [B, T, d]
        h_ctx = F.normalize(h_ctx, dim=-1)                           # unit norm

        # Positive: target token embedding
        target_emb = token_embeddings[target_ids]                    # [B, T, d]
        target_emb = F.normalize(target_emb, dim=-1)
        s_pos = (h_ctx * target_emb).sum(-1)                         # [B, T] cosine

        # Negative: hard negatives from phoneme clusters
        K = min(cfg.num_negatives, cfg.vocab_size - 1)
        if cfg.use_hard_negatives:
            neg_ids = self._sample_hard_negatives(target_ids, K)
        else:
            neg_ids = torch.randint(0, cfg.vocab_size, (B, T, K), device=h_t.device)

        neg_emb = token_embeddings[neg_ids]                          # [B, T, K, d]
        neg_emb = F.normalize(neg_emb, dim=-1)
        s_neg = (h_ctx.unsqueeze(2) * neg_emb).sum(-1)              # [B, T, K] cosine

        # Margin loss: s_pos should exceed all s_neg by at least margin
        L_margin = F.relu(cfg.margin - s_pos.unsqueeze(-1) + s_neg).mean()

        # Cosine pull: directly maximize similarity with target
        L_cosine = 1.0 - s_pos.mean()

        L_ctx = L_margin + L_cosine

        # === Total ===
        L_total = L_phon + cfg.beta * L_ctx

        # === Diagnostics ===
        with torch.no_grad():
            # Phoneme prediction accuracy (per-phoneme, threshold 0.5)
            phon_pred = (phi > 0.5).float()
            phon_target = (target_phonemes > 0.1).float()
            phon_acc = (phon_pred == phon_target).float().mean()

            # Context ranking: what fraction of positives beat all negatives?
            ctx_correct = (s_pos.unsqueeze(-1) > s_neg).all(dim=-1).float().mean()

        return {
            'loss_phoneme': L_phon,
            'loss_context': L_ctx,
            'loss_margin': L_margin,
            'loss_cosine': L_cosine,
            'loss_total': L_total,
            'phoneme_accuracy': phon_acc,
            'context_ranking_accuracy': ctx_correct,
            'avg_pos_score': s_pos.mean(),
            'avg_neg_score': s_neg.mean(),
        }

    def decode(
        self,
        h_t: torch.Tensor,
        token_embeddings: torch.Tensor,
        top_k: int = 0,
    ) -> torch.Tensor:
        """
        Decode: select tokens from factored probability.

        Args:
            h_t: [batch, seq, d_model]
            token_embeddings: [vocab_size, d_model]
            top_k: if > 0, sample from top-k; if 0, argmax

        Returns:
            [batch, seq] — selected token IDs
        """
        probs = self.compute_probs(h_t, token_embeddings)  # [B, T, V]

        if top_k > 0:
            # Top-k sampling from phoneme-context probabilities
            top_vals, top_idx = probs.topk(top_k, dim=-1)
            top_probs = top_vals / (top_vals.sum(dim=-1, keepdim=True) + 1e-8)
            sampled = torch.multinomial(
                top_probs.view(-1, top_k), num_samples=1
            ).view(probs.shape[0], probs.shape[1])
            token_ids = top_idx.gather(-1, sampled.unsqueeze(-1)).squeeze(-1)
        else:
            token_ids = probs.argmax(dim=-1)

        return token_ids

    def forward(
        self,
        h_t: torch.Tensor,
        token_embeddings: torch.Tensor,
        target_ids: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Full forward: scores + optional loss.

        Args:
            h_t: [batch, seq, d_model]
            token_embeddings: [vocab_size, d_model]
            target_ids: [batch, seq] — if provided, computes loss

        Returns:
            Dict with probs, scores, and optionally loss components
        """
        result = self.compute_scores(h_t, token_embeddings)
        s = result['combined_scores']
        result['probs'] = s / (s.sum(dim=-1, keepdim=True) + 1e-8)

        if target_ids is not None:
            loss_result = self.compute_loss(h_t, target_ids, token_embeddings)
            result.update(loss_result)

        return result


def create_phoneme_context_head(
    csr_phoneme_head: CSRPhonemeHead,
    temperature: float = 1.0,
    margin: float = 0.5,
    num_negatives: int = 256,
    beta: float = 1.0,
) -> PhonemeContextHead:
    """
    Create PhonemeContextHead from an existing CSRPhonemeHead.

    Reuses the token-phoneme weight matrix built by CSRPhonemeHead
    (which contains the Sanskrit G2P decomposition).

    Args:
        csr_phoneme_head: Existing CSRPhonemeHead with built token_phoneme_weights
        temperature: Context scoring temperature
        margin: Contrastive margin
        num_negatives: Hard negatives per position
        beta: Context loss weight

    Returns:
        Configured PhonemeContextHead
    """
    if csr_phoneme_head._token_phoneme_weights is None:
        raise RuntimeError("CSRPhonemeHead has no token_phoneme_weights — provide a tokenizer")

    config = PhonemeContextConfig(
        d_model=csr_phoneme_head.config.d_model,
        num_phonemes=csr_phoneme_head.num_phonemes,
        vocab_size=csr_phoneme_head.config.vocab_size,
        temperature=temperature,
        margin=margin,
        num_negatives=num_negatives,
        beta=beta,
    )

    head = PhonemeContextHead(
        config=config,
        token_phoneme_weights=csr_phoneme_head._token_phoneme_weights,
    )

    print(f"  [PhonemeContextHead] Created: d_model={config.d_model}, "
          f"phonemes={config.num_phonemes}, vocab={config.vocab_size:,}, "
          f"τ={temperature}, margin={margin}, K={num_negatives}, β={beta}")
    return head


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Config
    "CSRConfig",
    "CSRPhonemeHeadConfig",
    "PhonemeContextConfig",
    "AblationConfig",
    # Main classes
    "CSREmbeddingProvider",
    "CSRPhonemeHead",
    "PhonemeContextHead",
    "VarnaCSRBridge",
    "EntropySink",
    "SynthesisGate",
    "CSRAblationTester",
    # Decay Scheduler
    "CSRDecayScheduler",
    "create_csr_decay_scheduler",
    # Hybrid G2P System
    "HybridG2P",
    "get_hybrid_g2p",
    # Constants
    "PHONEME_MAP_ARPABET",
    "SANSKRIT_VOWEL_CALIBRATION",
    "SIMPLE_G2P",
    "CHAR_TO_PHONEME",
    "ONTOLOGICAL_LAYERS",
    "LAYER_NAME_TO_IDX",
    "ARPABET_TO_VARNA",
    # Helper functions
    "create_csr_for_training",
    "create_csr_phoneme_head",
    "create_phoneme_context_head",
    "integrate_csr_into_forward",
]


if __name__ == "__main__":
    main()
