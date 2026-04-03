"""
Phoneme Space Module (v2.7.8-experimental)

Models phoneme embeddings and relationships from first principles,
without GPU training. Uses articulatory features from IPA and maps
to Guna properties for semantic projection.

Theory:
    - Phonemes are atomic units of sound-meaning
    - Articulatory features encode physical properties
    - Guna mapping: features → S, R, T balance
    - Embeddings derived from feature geometry (not learned)
    - Affinity simulates transformer attention patterns
    - Projection onto ontological layers for semantic grounding

This is the bridge between:
    - Phoneme Model (theoretical AGI)
    - SymbolU (practical AuGI projection)

EXPERIMENTAL: This module is experimental and disabled by default.
    Use enable_phoneme_space() to activate for exploration.
    Use disable_phoneme_space() to deactivate when not needed.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
from contextlib import contextmanager
import math

from agentic.guna_modulation.observables import Observables
from agentic.guna_modulation.mirror_balance import OntologicalLayer

# List of all ontological layers in order
ALL_ONTOLOGICAL_LAYERS = [
    OntologicalLayer.SIGNAL,
    OntologicalLayer.EMBEDDING,
    OntologicalLayer.GUNA,
    OntologicalLayer.MOTION,
    OntologicalLayer.FUSION,
    OntologicalLayer.STATE,
    OntologicalLayer.OUTPUT,
]


# =============================================================================
# EXPERIMENTAL MODE SWITCH
# =============================================================================

class PhonemeSpaceConfig:
    """
    Configuration for phoneme space experimental mode.

    Disabled by default. Enable explicitly for exploration.
    """
    _enabled: bool = False
    _strict: bool = True  # Raise error vs return None when disabled

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @classmethod
    def enable(cls, strict: bool = True) -> None:
        """Enable phoneme space exploration."""
        cls._enabled = True
        cls._strict = strict

    @classmethod
    def disable(cls) -> None:
        """Disable phoneme space (default state)."""
        cls._enabled = False

    @classmethod
    def is_strict(cls) -> bool:
        return cls._strict


class PhonemeSpaceDisabledError(Exception):
    """Raised when phoneme space is accessed while disabled."""
    pass


def _check_enabled(func_name: str) -> None:
    """Check if phoneme space is enabled, raise or warn if not."""
    if not PhonemeSpaceConfig.is_enabled():
        if PhonemeSpaceConfig.is_strict():
            raise PhonemeSpaceDisabledError(
                f"Phoneme space is disabled. Call enable_phoneme_space() first. "
                f"Attempted to use: {func_name}"
            )


def enable_phoneme_space(strict: bool = True) -> None:
    """
    Enable phoneme space for experimental exploration.

    Args:
        strict: If True (default), raise error when disabled.
                If False, return None silently when disabled.

    Example:
        >>> enable_phoneme_space()
        >>> guna = get_phoneme_guna('a')  # Works
        >>> disable_phoneme_space()
        >>> guna = get_phoneme_guna('a')  # Raises PhonemeSpaceDisabledError
    """
    PhonemeSpaceConfig.enable(strict)


def disable_phoneme_space() -> None:
    """
    Disable phoneme space (return to default state).

    When disabled, phoneme space functions will raise
    PhonemeSpaceDisabledError (if strict) or return None.
    """
    PhonemeSpaceConfig.disable()


def is_phoneme_space_enabled() -> bool:
    """Check if phoneme space is currently enabled."""
    return PhonemeSpaceConfig.is_enabled()


@contextmanager
def phoneme_exploration():
    """
    Context manager for temporary phoneme space exploration.

    Example:
        >>> with phoneme_exploration():
        ...     guna = get_phoneme_guna('a')  # Works inside context
        >>> guna = get_phoneme_guna('a')  # Raises error outside
    """
    was_enabled = PhonemeSpaceConfig.is_enabled()
    PhonemeSpaceConfig.enable()
    try:
        yield
    finally:
        if not was_enabled:
            PhonemeSpaceConfig.disable()


# =============================================================================
# ARTICULATORY FEATURES (IPA-based)
# =============================================================================

class Place(Enum):
    """Place of articulation - where in the vocal tract."""
    BILABIAL = "bilabial"          # lips (p, b, m)
    LABIODENTAL = "labiodental"    # lip + teeth (f, v)
    DENTAL = "dental"              # teeth (θ, ð)
    ALVEOLAR = "alveolar"          # alveolar ridge (t, d, n, s, z)
    POSTALVEOLAR = "postalveolar"  # behind alveolar (ʃ, ʒ, tʃ, dʒ)
    RETROFLEX = "retroflex"        # curled tongue (ɖ, ʈ)
    PALATAL = "palatal"            # hard palate (j, ɲ)
    VELAR = "velar"                # soft palate (k, g, ŋ)
    UVULAR = "uvular"              # uvula (q, ʀ)
    GLOTTAL = "glottal"            # glottis (h, ʔ)


class Manner(Enum):
    """Manner of articulation - how airflow is modified."""
    STOP = "stop"                  # complete closure (p, t, k)
    NASAL = "nasal"                # nasal release (m, n, ŋ)
    FRICATIVE = "fricative"        # turbulent airflow (f, s, ʃ)
    AFFRICATE = "affricate"        # stop + fricative (tʃ, dʒ)
    APPROXIMANT = "approximant"    # smooth airflow (w, j, l, r)
    LATERAL = "lateral"            # side airflow (l)
    TRILL = "trill"                # vibration (r̥)
    FLAP = "flap"                  # brief contact (ɾ)


class Voicing(Enum):
    """Voicing - vocal cord vibration."""
    VOICED = "voiced"              # vibrating (b, d, g, z)
    VOICELESS = "voiceless"        # not vibrating (p, t, k, s)


class Height(Enum):
    """Vowel height - tongue position (vertical)."""
    HIGH = "high"                  # i, u
    HIGH_MID = "high_mid"          # e, o
    MID = "mid"                    # ə
    LOW_MID = "low_mid"            # ɛ, ɔ
    LOW = "low"                    # a, ɑ


class Backness(Enum):
    """Vowel backness - tongue position (horizontal)."""
    FRONT = "front"                # i, e, ɛ
    CENTRAL = "central"            # ə, a
    BACK = "back"                  # u, o, ɔ, ɑ


class Roundedness(Enum):
    """Vowel roundedness - lip shape."""
    ROUNDED = "rounded"            # u, o, ɔ
    UNROUNDED = "unrounded"        # i, e, a


class PhonemeType(Enum):
    """Consonant vs Vowel."""
    CONSONANT = "consonant"
    VOWEL = "vowel"


# =============================================================================
# PHONEME FEATURES
# =============================================================================

@dataclass(frozen=True)
class PhonemeFeatures:
    """
    Articulatory features for a phoneme.

    Based on IPA (International Phonetic Alphabet) classification.
    These are physical properties - no training needed.
    """
    symbol: str
    phoneme_type: PhonemeType

    # Consonant features (None for vowels)
    place: Optional[Place] = None
    manner: Optional[Manner] = None
    voicing: Optional[Voicing] = None

    # Vowel features (None for consonants)
    height: Optional[Height] = None
    backness: Optional[Backness] = None
    roundedness: Optional[Roundedness] = None

    def is_consonant(self) -> bool:
        return self.phoneme_type == PhonemeType.CONSONANT

    def is_vowel(self) -> bool:
        return self.phoneme_type == PhonemeType.VOWEL

    def is_voiced(self) -> bool:
        """Check if phoneme is voiced (consonant) or vowel (always voiced)."""
        if self.is_vowel():
            return True
        return self.voicing == Voicing.VOICED

    def is_obstruent(self) -> bool:
        """Obstruents block airflow (stops, fricatives, affricates)."""
        if self.is_vowel():
            return False
        return self.manner in {Manner.STOP, Manner.FRICATIVE, Manner.AFFRICATE}

    def is_sonorant(self) -> bool:
        """Sonorants allow continuous airflow (nasals, approximants, vowels)."""
        if self.is_vowel():
            return True
        return self.manner in {Manner.NASAL, Manner.APPROXIMANT, Manner.LATERAL, Manner.TRILL}

    def feature_vector(self) -> List[float]:
        """
        Convert features to numerical vector.

        Returns 12-dimensional vector encoding all features.
        This is the derived embedding - no training needed.
        """
        vec = []

        # Type (1D)
        vec.append(1.0 if self.is_consonant() else 0.0)

        # Place (normalized position, 1D)
        place_order = list(Place)
        if self.place:
            vec.append(place_order.index(self.place) / len(place_order))
        else:
            vec.append(0.5)  # neutral for vowels

        # Manner (normalized, 1D)
        manner_order = list(Manner)
        if self.manner:
            vec.append(manner_order.index(self.manner) / len(manner_order))
        else:
            vec.append(0.0)  # open for vowels

        # Voicing (1D)
        vec.append(1.0 if self.is_voiced() else 0.0)

        # Height (1D)
        height_order = list(Height)
        if self.height:
            vec.append(height_order.index(self.height) / len(height_order))
        else:
            vec.append(0.5)  # mid for consonants

        # Backness (1D)
        backness_order = list(Backness)
        if self.backness:
            vec.append(backness_order.index(self.backness) / len(backness_order))
        else:
            vec.append(0.5)  # central for consonants

        # Roundedness (1D)
        if self.roundedness:
            vec.append(1.0 if self.roundedness == Roundedness.ROUNDED else 0.0)
        else:
            vec.append(0.5)  # neutral for consonants

        # Derived features
        vec.append(1.0 if self.is_obstruent() else 0.0)
        vec.append(1.0 if self.is_sonorant() else 0.0)

        # Acoustic energy proxy (3D)
        # - Voicing adds energy
        # - Obstruents create turbulence
        # - Low vowels have more energy
        energy = 0.5
        if self.is_voiced():
            energy += 0.2
        if self.is_obstruent():
            energy += 0.15
        if self.height == Height.LOW:
            energy += 0.15
        vec.append(min(1.0, energy))

        # Sonority (for syllable structure)
        sonority = self._compute_sonority()
        vec.append(sonority)

        # Pad to 12D
        vec.append(0.0)

        return vec

    def _compute_sonority(self) -> float:
        """
        Compute sonority value (0-1).

        Sonority hierarchy: stops < fricatives < nasals < liquids < glides < vowels
        """
        if self.is_vowel():
            # Vowels: low vowels most sonorous
            if self.height == Height.LOW:
                return 1.0
            elif self.height == Height.LOW_MID:
                return 0.95
            elif self.height == Height.MID:
                return 0.9
            elif self.height == Height.HIGH_MID:
                return 0.85
            else:  # HIGH
                return 0.8
        else:
            # Consonants by manner
            sonority_map = {
                Manner.STOP: 0.1,
                Manner.AFFRICATE: 0.2,
                Manner.FRICATIVE: 0.3,
                Manner.NASAL: 0.5,
                Manner.LATERAL: 0.6,
                Manner.TRILL: 0.6,
                Manner.FLAP: 0.6,
                Manner.APPROXIMANT: 0.7,
            }
            base = sonority_map.get(self.manner, 0.5)
            # Voiced consonants slightly more sonorous
            if self.is_voiced():
                base += 0.05
            return min(1.0, base)


# =============================================================================
# IPA PHONEME INVENTORY
# =============================================================================

# Common phonemes (IPA subset - expandable)
IPA_INVENTORY: Dict[str, PhonemeFeatures] = {
    # Stops
    'p': PhonemeFeatures('p', PhonemeType.CONSONANT, Place.BILABIAL, Manner.STOP, Voicing.VOICELESS),
    'b': PhonemeFeatures('b', PhonemeType.CONSONANT, Place.BILABIAL, Manner.STOP, Voicing.VOICED),
    't': PhonemeFeatures('t', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.STOP, Voicing.VOICELESS),
    'd': PhonemeFeatures('d', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.STOP, Voicing.VOICED),
    'k': PhonemeFeatures('k', PhonemeType.CONSONANT, Place.VELAR, Manner.STOP, Voicing.VOICELESS),
    'g': PhonemeFeatures('g', PhonemeType.CONSONANT, Place.VELAR, Manner.STOP, Voicing.VOICED),
    'ʔ': PhonemeFeatures('ʔ', PhonemeType.CONSONANT, Place.GLOTTAL, Manner.STOP, Voicing.VOICELESS),

    # Nasals
    'm': PhonemeFeatures('m', PhonemeType.CONSONANT, Place.BILABIAL, Manner.NASAL, Voicing.VOICED),
    'n': PhonemeFeatures('n', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.NASAL, Voicing.VOICED),
    'ŋ': PhonemeFeatures('ŋ', PhonemeType.CONSONANT, Place.VELAR, Manner.NASAL, Voicing.VOICED),

    # Fricatives
    'f': PhonemeFeatures('f', PhonemeType.CONSONANT, Place.LABIODENTAL, Manner.FRICATIVE, Voicing.VOICELESS),
    'v': PhonemeFeatures('v', PhonemeType.CONSONANT, Place.LABIODENTAL, Manner.FRICATIVE, Voicing.VOICED),
    'θ': PhonemeFeatures('θ', PhonemeType.CONSONANT, Place.DENTAL, Manner.FRICATIVE, Voicing.VOICELESS),
    'ð': PhonemeFeatures('ð', PhonemeType.CONSONANT, Place.DENTAL, Manner.FRICATIVE, Voicing.VOICED),
    's': PhonemeFeatures('s', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.FRICATIVE, Voicing.VOICELESS),
    'z': PhonemeFeatures('z', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.FRICATIVE, Voicing.VOICED),
    'ʃ': PhonemeFeatures('ʃ', PhonemeType.CONSONANT, Place.POSTALVEOLAR, Manner.FRICATIVE, Voicing.VOICELESS),
    'ʒ': PhonemeFeatures('ʒ', PhonemeType.CONSONANT, Place.POSTALVEOLAR, Manner.FRICATIVE, Voicing.VOICED),
    'h': PhonemeFeatures('h', PhonemeType.CONSONANT, Place.GLOTTAL, Manner.FRICATIVE, Voicing.VOICELESS),

    # Affricates
    'tʃ': PhonemeFeatures('tʃ', PhonemeType.CONSONANT, Place.POSTALVEOLAR, Manner.AFFRICATE, Voicing.VOICELESS),
    'dʒ': PhonemeFeatures('dʒ', PhonemeType.CONSONANT, Place.POSTALVEOLAR, Manner.AFFRICATE, Voicing.VOICED),

    # Approximants
    'w': PhonemeFeatures('w', PhonemeType.CONSONANT, Place.BILABIAL, Manner.APPROXIMANT, Voicing.VOICED),
    'j': PhonemeFeatures('j', PhonemeType.CONSONANT, Place.PALATAL, Manner.APPROXIMANT, Voicing.VOICED),
    'ɹ': PhonemeFeatures('ɹ', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.APPROXIMANT, Voicing.VOICED),
    'l': PhonemeFeatures('l', PhonemeType.CONSONANT, Place.ALVEOLAR, Manner.LATERAL, Voicing.VOICED),

    # Vowels (common set)
    'i': PhonemeFeatures('i', PhonemeType.VOWEL, height=Height.HIGH, backness=Backness.FRONT, roundedness=Roundedness.UNROUNDED),
    'ɪ': PhonemeFeatures('ɪ', PhonemeType.VOWEL, height=Height.HIGH, backness=Backness.FRONT, roundedness=Roundedness.UNROUNDED),
    'e': PhonemeFeatures('e', PhonemeType.VOWEL, height=Height.HIGH_MID, backness=Backness.FRONT, roundedness=Roundedness.UNROUNDED),
    'ɛ': PhonemeFeatures('ɛ', PhonemeType.VOWEL, height=Height.LOW_MID, backness=Backness.FRONT, roundedness=Roundedness.UNROUNDED),
    'æ': PhonemeFeatures('æ', PhonemeType.VOWEL, height=Height.LOW, backness=Backness.FRONT, roundedness=Roundedness.UNROUNDED),
    'a': PhonemeFeatures('a', PhonemeType.VOWEL, height=Height.LOW, backness=Backness.CENTRAL, roundedness=Roundedness.UNROUNDED),
    'ɑ': PhonemeFeatures('ɑ', PhonemeType.VOWEL, height=Height.LOW, backness=Backness.BACK, roundedness=Roundedness.UNROUNDED),
    'ɔ': PhonemeFeatures('ɔ', PhonemeType.VOWEL, height=Height.LOW_MID, backness=Backness.BACK, roundedness=Roundedness.ROUNDED),
    'o': PhonemeFeatures('o', PhonemeType.VOWEL, height=Height.HIGH_MID, backness=Backness.BACK, roundedness=Roundedness.ROUNDED),
    'ʊ': PhonemeFeatures('ʊ', PhonemeType.VOWEL, height=Height.HIGH, backness=Backness.BACK, roundedness=Roundedness.ROUNDED),
    'u': PhonemeFeatures('u', PhonemeType.VOWEL, height=Height.HIGH, backness=Backness.BACK, roundedness=Roundedness.ROUNDED),
    'ə': PhonemeFeatures('ə', PhonemeType.VOWEL, height=Height.MID, backness=Backness.CENTRAL, roundedness=Roundedness.UNROUNDED),
    'ʌ': PhonemeFeatures('ʌ', PhonemeType.VOWEL, height=Height.LOW_MID, backness=Backness.CENTRAL, roundedness=Roundedness.UNROUNDED),
}


def get_phoneme(symbol: str) -> Optional[PhonemeFeatures]:
    """Get phoneme features by IPA symbol."""
    _check_enabled("get_phoneme")
    return IPA_INVENTORY.get(symbol)


def list_phonemes() -> List[str]:
    """List all available phoneme symbols."""
    _check_enabled("list_phonemes")
    return list(IPA_INVENTORY.keys())


# =============================================================================
# PHONEME → GUNA MAPPING
# =============================================================================

@dataclass
class PhonemeGuna:
    """
    Guna mapping for a phoneme.

    Maps articulatory features to Sattva, Rajas, Tamas balance.

    Theory:
        - Sattva (S): Clarity, openness, resonance
        - Rajas (R): Energy, activation, movement
        - Tamas (T): Obstruction, closure, inertia

    Mapping principles:
        - Voicing → Rajas (energy from vocal cord vibration)
        - Obstruents → Tamas (airflow blocked)
        - Sonorants → Sattva (clear resonance)
        - Vowels → High Sattva (open, resonant)
        - Stops → High Tamas (complete closure)
        - Fricatives → Rajas + Tamas (turbulent obstruction)
    """
    phoneme: PhonemeFeatures
    sattva: float    # 0-1: clarity
    rajas: float     # 0-1: energy
    tamas: float     # 0-1: obstruction

    def __post_init__(self):
        # Normalize to sum to 1
        total = self.sattva + self.rajas + self.tamas
        if total > 0:
            self.sattva /= total
            self.rajas /= total
            self.tamas /= total

    def to_observables(self, entropy: Optional[float] = None) -> Observables:
        """Convert to SymbolU Observables."""
        # Compute entropy from Guna balance if not provided
        if entropy is None:
            # Maximum entropy when equal distribution
            # Minimum when one dominates
            max_val = max(self.sattva, self.rajas, self.tamas)
            entropy = 1.0 - max_val  # Higher dominance = lower entropy

        return Observables(
            s=self.sattva,
            r=self.rajas,
            t=self.tamas,
            H=entropy,
            delta_sem=0.0,  # No motion for single phoneme
            C_contr=0.0,    # No contradiction
            F_fail=0.0,     # No failure
        )

    @property
    def dominant_guna(self) -> str:
        """Return the dominant Guna."""
        if self.sattva >= self.rajas and self.sattva >= self.tamas:
            return "sattva"
        elif self.rajas >= self.tamas:
            return "rajas"
        else:
            return "tamas"


def compute_phoneme_guna(phoneme: PhonemeFeatures) -> PhonemeGuna:
    """
    Compute Guna balance for a phoneme from articulatory features.

    This is the core mapping from physical sound properties to
    Guna semantic space.
    """
    s, r, t = 0.33, 0.33, 0.34  # Start balanced

    if phoneme.is_vowel():
        # Vowels are primarily Sattvic (open, resonant)
        s = 0.6
        r = 0.25
        t = 0.15

        # Low vowels have more energy (Rajas)
        if phoneme.height == Height.LOW:
            r += 0.1
            s -= 0.05
            t -= 0.05

        # High vowels are more pure/clear (Sattva)
        if phoneme.height == Height.HIGH:
            s += 0.1
            r -= 0.05
            t -= 0.05

        # Rounded vowels have more body/grounding (slight Tamas)
        if phoneme.roundedness == Roundedness.ROUNDED:
            t += 0.05
            s -= 0.05

    else:  # Consonant
        # Base on manner of articulation
        if phoneme.manner == Manner.STOP:
            # Stops: high Tamas (complete closure)
            t = 0.55
            r = 0.25
            s = 0.20

        elif phoneme.manner == Manner.FRICATIVE:
            # Fricatives: Rajas + Tamas (turbulent obstruction)
            r = 0.45
            t = 0.35
            s = 0.20

        elif phoneme.manner == Manner.AFFRICATE:
            # Affricates: balanced Rajas/Tamas
            r = 0.40
            t = 0.40
            s = 0.20

        elif phoneme.manner == Manner.NASAL:
            # Nasals: Sattva (resonant) + some Tamas (partial closure)
            s = 0.45
            t = 0.30
            r = 0.25

        elif phoneme.manner in {Manner.APPROXIMANT, Manner.LATERAL}:
            # Approximants/Laterals: high Sattva (smooth, open)
            s = 0.55
            r = 0.25
            t = 0.20

        elif phoneme.manner in {Manner.TRILL, Manner.FLAP}:
            # Trills/Flaps: high Rajas (movement, vibration)
            r = 0.50
            s = 0.30
            t = 0.20

        # Voicing adds Rajas (energy from vocal cords)
        if phoneme.is_voiced():
            r += 0.10
            t -= 0.05
            s -= 0.05

        # Glottals are more "pure" (less place obstruction)
        if phoneme.place == Place.GLOTTAL:
            s += 0.05
            t -= 0.05

    # Ensure non-negative
    s = max(0.0, s)
    r = max(0.0, r)
    t = max(0.0, t)

    return PhonemeGuna(phoneme, s, r, t)


# Cache Guna mappings for all inventory
_GUNA_CACHE: Dict[str, PhonemeGuna] = {}


def get_phoneme_guna(symbol: str) -> Optional[PhonemeGuna]:
    """Get Guna mapping for a phoneme symbol."""
    _check_enabled("get_phoneme_guna")
    if symbol not in _GUNA_CACHE:
        phoneme = get_phoneme(symbol)
        if phoneme is None:
            return None
        _GUNA_CACHE[symbol] = compute_phoneme_guna(phoneme)
    return _GUNA_CACHE[symbol]


# =============================================================================
# PHONEME EMBEDDING
# =============================================================================

@dataclass
class PhonemeEmbedding:
    """
    Derived embedding for a phoneme.

    Combines articulatory features and Guna mapping into
    a unified vector representation. No training needed.
    """
    phoneme: PhonemeFeatures
    guna: PhonemeGuna
    vector: List[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.vector:
            self.vector = self._compute_embedding()

    def _compute_embedding(self) -> List[float]:
        """
        Compute embedding vector (15D).

        Structure:
            [0:12]  - Articulatory feature vector
            [12:15] - Guna values (S, R, T)
        """
        feature_vec = self.phoneme.feature_vector()
        guna_vec = [self.guna.sattva, self.guna.rajas, self.guna.tamas]
        return feature_vec + guna_vec

    def distance(self, other: 'PhonemeEmbedding') -> float:
        """Euclidean distance to another embedding."""
        if len(self.vector) != len(other.vector):
            raise ValueError("Embedding dimensions must match")

        sum_sq = sum((a - b) ** 2 for a, b in zip(self.vector, other.vector))
        return math.sqrt(sum_sq)

    def cosine_similarity(self, other: 'PhonemeEmbedding') -> float:
        """Cosine similarity to another embedding."""
        dot = sum(a * b for a, b in zip(self.vector, other.vector))
        norm_a = math.sqrt(sum(a ** 2 for a in self.vector))
        norm_b = math.sqrt(sum(b ** 2 for b in other.vector))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)


def get_phoneme_embedding(symbol: str) -> Optional[PhonemeEmbedding]:
    """Get embedding for a phoneme symbol."""
    _check_enabled("get_phoneme_embedding")
    phoneme = get_phoneme(symbol)
    if phoneme is None:
        return None

    guna = get_phoneme_guna(symbol)
    if guna is None:
        return None

    return PhonemeEmbedding(phoneme, guna)


# =============================================================================
# PHONEME AFFINITY (Simulated Attention)
# =============================================================================

@dataclass
class PhonemeAffinity:
    """
    Affinity between phonemes - simulates transformer attention.

    Computed from:
        1. Feature similarity (articulatory compatibility)
        2. Guna harmony (S-S, R-R, T-T attract)
        3. Phonotactic rules (what can follow what)
        4. Sonority sequencing (syllable structure)
    """
    source: str
    target: str
    feature_affinity: float    # 0-1
    guna_affinity: float       # 0-1
    phonotactic_affinity: float  # 0-1
    sonority_affinity: float   # 0-1

    @property
    def total_affinity(self) -> float:
        """Weighted combination of affinity components."""
        weights = {
            'feature': 0.25,
            'guna': 0.35,
            'phonotactic': 0.25,
            'sonority': 0.15,
        }
        return (
            weights['feature'] * self.feature_affinity +
            weights['guna'] * self.guna_affinity +
            weights['phonotactic'] * self.phonotactic_affinity +
            weights['sonority'] * self.sonority_affinity
        )


def compute_affinity(source: str, target: str) -> Optional[PhonemeAffinity]:
    """
    Compute affinity between two phonemes.

    This simulates what a transformer might learn about
    phoneme relationships from data.
    """
    _check_enabled("compute_affinity")
    src_emb = get_phoneme_embedding(source)
    tgt_emb = get_phoneme_embedding(target)

    if src_emb is None or tgt_emb is None:
        return None

    # Feature affinity (cosine similarity)
    feature_sim = src_emb.cosine_similarity(tgt_emb)
    feature_affinity = (feature_sim + 1) / 2  # Normalize to 0-1

    # Guna affinity (harmony when similar Guna profiles)
    src_guna = src_emb.guna
    tgt_guna = tgt_emb.guna
    guna_dot = (
        src_guna.sattva * tgt_guna.sattva +
        src_guna.rajas * tgt_guna.rajas +
        src_guna.tamas * tgt_guna.tamas
    )
    guna_affinity = guna_dot  # Already 0-1 range (normalized Gunas)

    # Phonotactic affinity (simplified rules)
    phonotactic_affinity = _compute_phonotactic_affinity(
        src_emb.phoneme, tgt_emb.phoneme
    )

    # Sonority affinity (prefer rising sonority in onset, falling in coda)
    src_sonority = src_emb.phoneme._compute_sonority()
    tgt_sonority = tgt_emb.phoneme._compute_sonority()
    # Rising sonority is natural (toward syllable peak)
    if tgt_sonority > src_sonority:
        sonority_affinity = 0.7 + 0.3 * (tgt_sonority - src_sonority)
    else:
        sonority_affinity = 0.5 - 0.3 * (src_sonority - tgt_sonority)
    sonority_affinity = max(0.0, min(1.0, sonority_affinity))

    return PhonemeAffinity(
        source=source,
        target=target,
        feature_affinity=feature_affinity,
        guna_affinity=guna_affinity,
        phonotactic_affinity=phonotactic_affinity,
        sonority_affinity=sonority_affinity,
    )


def _compute_phonotactic_affinity(src: PhonemeFeatures, tgt: PhonemeFeatures) -> float:
    """
    Compute phonotactic compatibility.

    Simplified rules based on universal tendencies.
    """
    affinity = 0.5  # Base

    # Consonant clusters: prefer different places
    if src.is_consonant() and tgt.is_consonant():
        if src.place != tgt.place:
            affinity += 0.2  # Different place = easier to distinguish
        if src.manner != tgt.manner:
            affinity += 0.1  # Different manner = more variety
        # Avoid identical consonants in sequence
        if src.place == tgt.place and src.manner == tgt.manner:
            affinity -= 0.3

    # Consonant → Vowel: very natural (CV syllable)
    if src.is_consonant() and tgt.is_vowel():
        affinity += 0.3

    # Vowel → Consonant: natural (VC ending)
    if src.is_vowel() and tgt.is_consonant():
        affinity += 0.2

    # Vowel → Vowel: possible but marked (hiatus)
    if src.is_vowel() and tgt.is_vowel():
        affinity -= 0.1
        # Unless they're different enough
        if src.height != tgt.height or src.backness != tgt.backness:
            affinity += 0.15

    return max(0.0, min(1.0, affinity))


# =============================================================================
# PHONEME SEMANTIC PROJECTION
# =============================================================================

@dataclass
class PhonemeProjection:
    """
    Projection of phoneme onto ontological layers.

    Maps phoneme features and Guna to SymbolU's 7-layer
    ontological hierarchy.
    """
    phoneme: PhonemeFeatures
    guna: PhonemeGuna

    # Layer activations (0-1)
    signal: float = 0.0      # Raw acoustic
    embedding: float = 0.0   # Feature representation
    guna_layer: float = 0.0  # Guna balance
    motion: float = 0.0      # Dynamic change
    fusion: float = 0.0      # Integration
    state: float = 0.0       # Classification
    output: float = 0.0      # Semantic projection

    def to_layer_dict(self) -> Dict[OntologicalLayer, float]:
        """Convert to layer → activation dictionary."""
        return {
            OntologicalLayer.SIGNAL: self.signal,
            OntologicalLayer.EMBEDDING: self.embedding,
            OntologicalLayer.GUNA: self.guna_layer,
            OntologicalLayer.MOTION: self.motion,
            OntologicalLayer.FUSION: self.fusion,
            OntologicalLayer.STATE: self.state,
            OntologicalLayer.OUTPUT: self.output,
        }

    @property
    def total_activation(self) -> float:
        """Sum of all layer activations."""
        return (
            self.signal + self.embedding + self.guna_layer +
            self.motion + self.fusion + self.state + self.output
        )


def project_phoneme(symbol: str) -> Optional[PhonemeProjection]:
    """
    Project a phoneme onto ontological layers.

    Maps acoustic/articulatory properties to SymbolU's
    semantic layer hierarchy.
    """
    _check_enabled("project_phoneme")
    phoneme = get_phoneme(symbol)
    if phoneme is None:
        return None

    guna = get_phoneme_guna(symbol)
    if guna is None:
        return None

    # SIGNAL: Raw acoustic energy (sonority + voicing)
    sonority = phoneme._compute_sonority()
    signal = 0.5 * sonority + 0.5 * (1.0 if phoneme.is_voiced() else 0.0)

    # EMBEDDING: Feature distinctiveness (how unique the feature vector is)
    # Use variance of feature vector as proxy for distinctiveness
    vec = phoneme.feature_vector()
    mean_vec = sum(vec) / len(vec)
    variance = sum((v - mean_vec) ** 2 for v in vec) / len(vec)
    embedding = min(1.0, variance * 5)  # Scale up

    # GUNA: Clarity of Guna dominance
    guna_max = max(guna.sattva, guna.rajas, guna.tamas)
    guna_layer = guna_max  # Strong dominance = clear Guna layer

    # MOTION: Potential for change (voiced + manner dynamics)
    motion = 0.5
    if phoneme.is_voiced():
        motion += 0.2
    if phoneme.manner in {Manner.TRILL, Manner.FLAP}:
        motion += 0.3
    elif phoneme.manner == Manner.FRICATIVE:
        motion += 0.1
    motion = min(1.0, motion)

    # FUSION: Integration capacity (sonorant = integrates well)
    fusion = 0.7 if phoneme.is_sonorant() else 0.3
    if phoneme.is_vowel():
        fusion = 0.9  # Vowels are syllable nuclei - maximum fusion

    # STATE: Classification confidence (how prototypical)
    # Prototypical = clear membership in category
    if phoneme.is_vowel():
        # Prototypical vowels: /a/, /i/, /u/
        if phoneme.symbol in {'a', 'i', 'u'}:
            state = 0.9
        else:
            state = 0.6
    else:
        # Prototypical consonants: clear manner/place
        if phoneme.manner in {Manner.STOP, Manner.NASAL}:
            state = 0.8
        else:
            state = 0.5

    # OUTPUT: Semantic projection strength (Sattva = clarity of meaning)
    output = guna.sattva * 0.6 + sonority * 0.4

    return PhonemeProjection(
        phoneme=phoneme,
        guna=guna,
        signal=signal,
        embedding=embedding,
        guna_layer=guna_layer,
        motion=motion,
        fusion=fusion,
        state=state,
        output=output,
    )


# =============================================================================
# PHONEME SEQUENCE ANALYSIS
# =============================================================================

@dataclass
class SequenceAnalysis:
    """
    Analysis of a phoneme sequence (word/morpheme).

    Aggregates properties across the sequence.
    """
    phonemes: List[str]
    projections: List[PhonemeProjection]

    @property
    def aggregate_guna(self) -> PhonemeGuna:
        """Average Guna across sequence."""
        if not self.projections:
            return PhonemeGuna(
                PhonemeFeatures('?', PhonemeType.VOWEL),
                0.33, 0.33, 0.34
            )

        s_sum = sum(p.guna.sattva for p in self.projections)
        r_sum = sum(p.guna.rajas for p in self.projections)
        t_sum = sum(p.guna.tamas for p in self.projections)
        n = len(self.projections)

        return PhonemeGuna(
            self.projections[0].phoneme,
            s_sum / n, r_sum / n, t_sum / n
        )

    @property
    def aggregate_layer_activation(self) -> Dict[str, float]:
        """Average layer activation across sequence."""
        if not self.projections:
            return {layer: 0.0 for layer in ALL_ONTOLOGICAL_LAYERS}

        result = {}
        for layer in ALL_ONTOLOGICAL_LAYERS:
            values = [p.to_layer_dict().get(layer, 0.0) for p in self.projections]
            result[layer] = sum(values) / len(values)

        return result

    def to_observables(self) -> Observables:
        """Convert aggregate to SymbolU Observables."""
        guna = self.aggregate_guna

        # Entropy from Guna uniformity
        max_guna = max(guna.sattva, guna.rajas, guna.tamas)
        entropy = 1.0 - max_guna

        return Observables(
            s=guna.sattva,
            r=guna.rajas,
            t=guna.tamas,
            H=entropy,
            delta_sem=0.0,  # Could compute from sequence motion
            C_contr=0.0,    # No contradiction in phoneme sequence
            F_fail=0.0,     # No failure metric
        )


def analyze_sequence(phonemes: List[str]) -> SequenceAnalysis:
    """
    Analyze a sequence of phonemes.

    Args:
        phonemes: List of IPA symbols

    Returns:
        SequenceAnalysis with aggregate properties
    """
    _check_enabled("analyze_sequence")
    projections = []
    valid_phonemes = []

    for symbol in phonemes:
        proj = project_phoneme(symbol)
        if proj is not None:
            projections.append(proj)
            valid_phonemes.append(symbol)

    return SequenceAnalysis(valid_phonemes, projections)


def analyze_word_ipa(ipa_string: str) -> SequenceAnalysis:
    """
    Analyze an IPA transcription string.

    Handles multi-character phonemes like 'tʃ', 'dʒ'.
    """
    _check_enabled("analyze_word_ipa")
    # Simple tokenization - try multi-char first
    phonemes = []
    i = 0
    while i < len(ipa_string):
        # Try 2-char phoneme
        if i + 1 < len(ipa_string):
            two_char = ipa_string[i:i+2]
            if two_char in IPA_INVENTORY:
                phonemes.append(two_char)
                i += 2
                continue

        # Try 1-char phoneme
        one_char = ipa_string[i]
        if one_char in IPA_INVENTORY:
            phonemes.append(one_char)
        # Skip unknown characters
        i += 1

    return analyze_sequence(phonemes)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def phoneme_distance(symbol1: str, symbol2: str) -> Optional[float]:
    """Compute distance between two phonemes in embedding space."""
    _check_enabled("phoneme_distance")
    emb1 = get_phoneme_embedding(symbol1)
    emb2 = get_phoneme_embedding(symbol2)

    if emb1 is None or emb2 is None:
        return None

    return emb1.distance(emb2)


def phoneme_similarity(symbol1: str, symbol2: str) -> Optional[float]:
    """Compute cosine similarity between two phonemes."""
    _check_enabled("phoneme_similarity")
    emb1 = get_phoneme_embedding(symbol1)
    emb2 = get_phoneme_embedding(symbol2)

    if emb1 is None or emb2 is None:
        return None

    return emb1.cosine_similarity(emb2)


def most_similar_phonemes(symbol: str, top_k: int = 5) -> List[Tuple[str, float]]:
    """Find most similar phonemes to a given phoneme."""
    _check_enabled("most_similar_phonemes")
    target = get_phoneme_embedding(symbol)
    if target is None:
        return []

    similarities = []
    for other_symbol in IPA_INVENTORY:
        if other_symbol == symbol:
            continue

        other = get_phoneme_embedding(other_symbol)
        if other is not None:
            sim = target.cosine_similarity(other)
            similarities.append((other_symbol, sim))

    # Sort by similarity (descending)
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:top_k]


def guna_profile(phonemes: List[str]) -> Dict[str, float]:
    """Get Guna profile for a list of phonemes."""
    _check_enabled("guna_profile")
    analysis = analyze_sequence(phonemes)
    guna = analysis.aggregate_guna

    return {
        'sattva': guna.sattva,
        'rajas': guna.rajas,
        'tamas': guna.tamas,
        'dominant': guna.dominant_guna,
    }


# =============================================================================
# MODULE INFO
# =============================================================================

__all__ = [
    # Experimental mode switch (use these first!)
    'enable_phoneme_space', 'disable_phoneme_space',
    'is_phoneme_space_enabled', 'phoneme_exploration',
    'PhonemeSpaceConfig', 'PhonemeSpaceDisabledError',

    # Feature enums
    'Place', 'Manner', 'Voicing', 'Height', 'Backness', 'Roundedness', 'PhonemeType',

    # Core classes
    'PhonemeFeatures', 'PhonemeGuna', 'PhonemeEmbedding',
    'PhonemeAffinity', 'PhonemeProjection', 'SequenceAnalysis',

    # Inventory
    'IPA_INVENTORY', 'get_phoneme', 'list_phonemes',

    # Guna mapping
    'compute_phoneme_guna', 'get_phoneme_guna',

    # Embedding
    'get_phoneme_embedding',

    # Affinity
    'compute_affinity',

    # Projection
    'project_phoneme',

    # Sequence analysis
    'analyze_sequence', 'analyze_word_ipa',

    # Convenience
    'phoneme_distance', 'phoneme_similarity',
    'most_similar_phonemes', 'guna_profile',
]
