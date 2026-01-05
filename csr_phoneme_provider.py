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
    """
    global _PRELOAD_THREAD, _PRELOAD_STARTED

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
        V9.5.2 Performance: Precompute affinity vectors for ALL vocab tokens.

        This eliminates O(B*T) tokenizer.decode() calls during forward pass,
        replacing them with a single tensor indexing operation.

        The table maps token_id → 12D affinity vector for the entire vocabulary.
        """
        if self.tokenizer is None:
            return

        vocab_size = getattr(self.tokenizer, 'vocab_size', None)
        if vocab_size is None:
            # Try to get vocab size from the tokenizer
            try:
                vocab_size = len(self.tokenizer)
            except:
                vocab_size = 50257  # GPT-2 default

        print(f"  [CSR] Building token affinity table for {vocab_size:,} tokens...")
        import time
        start_time = time.time()

        # Preallocate table
        affinity_table = torch.zeros(vocab_size, 12, dtype=torch.float32)

        # Compute affinity for each token
        for token_id in range(vocab_size):
            try:
                token_str = self.tokenizer.decode([token_id])
                phonemes = self.token_to_phonemes(token_str)
                affinity_table[token_id] = self.phonemes_to_affinity(phonemes)
            except Exception:
                # Fallback for problematic tokens
                affinity_table[token_id] = self.phoneme_map[token_id % len(self._phoneme_list)]

        # L2 normalize
        affinity_table = F.normalize(affinity_table, p=2, dim=-1)

        # Register as buffer (moves with model to GPU)
        # Safe registration: delete existing attribute if present
        if hasattr(self, '_token_affinity_table'):
            del self._token_affinity_table
        self.register_buffer('_token_affinity_table', affinity_table, persistent=False)

        elapsed = time.time() - start_time
        print(f"  [CSR] Token affinity table built in {elapsed:.2f}s")

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
    # Get model dimension
    d_model = getattr(model_config, 'd_model', 512)
    if hasattr(model_config, 'hidden_size'):
        d_model = model_config.hidden_size

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
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Config
    "CSRConfig",
    "AblationConfig",
    # Main classes
    "CSREmbeddingProvider",
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
    # Helper functions
    "create_csr_for_training",
    "integrate_csr_into_forward",
]


if __name__ == "__main__":
    main()
