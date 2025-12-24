"""
Phoneme Harmony Engine
=======================

Optimizes text flow by analyzing phoneme transitions at word boundaries.
Uses the Varṇa phoneme system to detect and smooth harsh transitions.

Key Capabilities:
    - Adjacent phoneme analysis at word boundaries
    - Clash detection (harsh consonant clusters)
    - Flow scoring (smooth vs jarring transitions)
    - Euphony suggestions (optional alternative words)

Integration:
    Used by P29 Expression Finalization to polish final text output.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import re

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# TRY IMPORT RESONANCE MODULE
# =============================================================================

try:
    from symbolu.resonance import (
        get_phonemes,
        analyze_word_varna,
        WordVector,
    )
    HAS_RESONANCE = True
except ImportError:
    HAS_RESONANCE = False
    get_phonemes = None
    analyze_word_varna = None
    WordVector = None


# =============================================================================
# ENUMS
# =============================================================================


class TransitionQuality(Enum):
    """Quality of phoneme transition between words."""
    SMOOTH = "smooth"       # Easy, flowing transition
    NEUTRAL = "neutral"     # Neither smooth nor harsh
    ROUGH = "rough"         # Somewhat jarring
    CLASH = "clash"         # Harsh, difficult transition


class PhonemeClass(Enum):
    """Classification of phonemes by articulation."""
    VOWEL = "vowel"
    STOP = "stop"               # p, b, t, d, k, g
    FRICATIVE = "fricative"     # f, v, s, z, sh, th
    NASAL = "nasal"             # m, n, ng
    LIQUID = "liquid"           # l, r
    GLIDE = "glide"             # w, y
    AFFRICATE = "affricate"     # ch, j


# =============================================================================
# PHONEME DATA
# =============================================================================

# Phoneme classification (ARPABET-based)
PHONEME_CLASSES: Dict[str, PhonemeClass] = {
    # Vowels
    "AA": PhonemeClass.VOWEL, "AE": PhonemeClass.VOWEL, "AH": PhonemeClass.VOWEL,
    "AO": PhonemeClass.VOWEL, "AW": PhonemeClass.VOWEL, "AY": PhonemeClass.VOWEL,
    "EH": PhonemeClass.VOWEL, "ER": PhonemeClass.VOWEL, "EY": PhonemeClass.VOWEL,
    "IH": PhonemeClass.VOWEL, "IY": PhonemeClass.VOWEL, "OW": PhonemeClass.VOWEL,
    "OY": PhonemeClass.VOWEL, "UH": PhonemeClass.VOWEL, "UW": PhonemeClass.VOWEL,
    # Stops
    "P": PhonemeClass.STOP, "B": PhonemeClass.STOP, "T": PhonemeClass.STOP,
    "D": PhonemeClass.STOP, "K": PhonemeClass.STOP, "G": PhonemeClass.STOP,
    # Fricatives
    "F": PhonemeClass.FRICATIVE, "V": PhonemeClass.FRICATIVE,
    "S": PhonemeClass.FRICATIVE, "Z": PhonemeClass.FRICATIVE,
    "SH": PhonemeClass.FRICATIVE, "ZH": PhonemeClass.FRICATIVE,
    "TH": PhonemeClass.FRICATIVE, "DH": PhonemeClass.FRICATIVE,
    "HH": PhonemeClass.FRICATIVE,
    # Nasals
    "M": PhonemeClass.NASAL, "N": PhonemeClass.NASAL, "NG": PhonemeClass.NASAL,
    # Liquids
    "L": PhonemeClass.LIQUID, "R": PhonemeClass.LIQUID,
    # Glides
    "W": PhonemeClass.GLIDE, "Y": PhonemeClass.GLIDE,
    # Affricates
    "CH": PhonemeClass.AFFRICATE, "JH": PhonemeClass.AFFRICATE,
}

# Transition difficulty matrix (higher = harder)
# Row = ending phoneme class, Col = starting phoneme class
TRANSITION_DIFFICULTY: Dict[Tuple[PhonemeClass, PhonemeClass], float] = {
    # Stop -> Stop (geminate-like, harsh)
    (PhonemeClass.STOP, PhonemeClass.STOP): 0.8,
    # Fricative -> Fricative (sibilant cluster)
    (PhonemeClass.FRICATIVE, PhonemeClass.FRICATIVE): 0.7,
    # Stop -> Fricative (releasing to friction)
    (PhonemeClass.STOP, PhonemeClass.FRICATIVE): 0.5,
    # Fricative -> Stop (friction to closure)
    (PhonemeClass.FRICATIVE, PhonemeClass.STOP): 0.6,
    # Nasal transitions (generally smooth)
    (PhonemeClass.NASAL, PhonemeClass.VOWEL): 0.1,
    (PhonemeClass.VOWEL, PhonemeClass.NASAL): 0.1,
    # Liquid transitions (very smooth)
    (PhonemeClass.LIQUID, PhonemeClass.VOWEL): 0.1,
    (PhonemeClass.VOWEL, PhonemeClass.LIQUID): 0.1,
    # Vowel -> Vowel (hiatus, can be awkward)
    (PhonemeClass.VOWEL, PhonemeClass.VOWEL): 0.4,
    # Glide transitions (smooth)
    (PhonemeClass.GLIDE, PhonemeClass.VOWEL): 0.0,
    (PhonemeClass.VOWEL, PhonemeClass.GLIDE): 0.2,
}

# Default difficulty for unlisted pairs
DEFAULT_TRANSITION_DIFFICULTY = 0.3


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class WordPhonemes:
    """Phoneme representation of a word."""
    word: str
    phonemes: Tuple[str, ...]
    first_phoneme: Optional[str]
    last_phoneme: Optional[str]
    first_class: Optional[PhonemeClass]
    last_class: Optional[PhonemeClass]


@dataclass(frozen=True)
class WordTransition:
    """Analysis of transition between two adjacent words."""
    word_from: str
    word_to: str
    ending_phoneme: Optional[str]
    starting_phoneme: Optional[str]
    quality: TransitionQuality
    difficulty: float
    position: int  # Position in text (word index)


@dataclass(frozen=True)
class HarmonyAnalysis:
    """Full harmony analysis of text."""
    text: str
    word_count: int
    transitions: Tuple[WordTransition, ...]
    overall_score: float  # 0-1, higher = more harmonious
    clash_count: int
    rough_count: int
    smooth_count: int
    problem_positions: Tuple[int, ...]
    suggestions: Dict[int, List[str]]  # Position -> suggested alternatives

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "word_count": self.word_count,
            "overall_score": self.overall_score,
            "clash_count": self.clash_count,
            "rough_count": self.rough_count,
            "smooth_count": self.smooth_count,
            "problem_positions": list(self.problem_positions),
            "transitions": [
                {
                    "from": t.word_from,
                    "to": t.word_to,
                    "quality": t.quality.value,
                    "difficulty": t.difficulty,
                    "position": t.position,
                }
                for t in self.transitions
            ],
        }


# =============================================================================
# PHONEME HARMONY ENGINE
# =============================================================================


class PhonemeHarmonyEngine:
    """
    Analyzes and optimizes phoneme flow in text.

    Uses Varṇa-based phoneme analysis when available,
    falls back to ARPABET approximation otherwise.
    """

    # Simple letter-to-phoneme approximation (fallback)
    LETTER_TO_PHONEME: Dict[str, str] = {
        'a': 'AH', 'e': 'EH', 'i': 'IH', 'o': 'OW', 'u': 'UH',
        'b': 'B', 'c': 'K', 'd': 'D', 'f': 'F', 'g': 'G',
        'h': 'HH', 'j': 'JH', 'k': 'K', 'l': 'L', 'm': 'M',
        'n': 'N', 'p': 'P', 'q': 'K', 'r': 'R', 's': 'S',
        't': 'T', 'v': 'V', 'w': 'W', 'x': 'K', 'y': 'Y', 'z': 'Z',
    }

    def __init__(
        self,
        clash_threshold: float = 0.7,
        rough_threshold: float = 0.5,
    ):
        """
        Initialize phoneme harmony engine.

        Args:
            clash_threshold: Difficulty threshold for CLASH transitions.
            rough_threshold: Difficulty threshold for ROUGH transitions.
        """
        self.clash_threshold = clash_threshold
        self.rough_threshold = rough_threshold

    def analyze(self, text: str) -> HarmonyAnalysis:
        """
        Analyze phoneme harmony of text.

        Args:
            text: Text to analyze.

        Returns:
            HarmonyAnalysis with transition details.
        """
        # Extract words
        words = self._extract_words(text)
        if len(words) < 2:
            return HarmonyAnalysis(
                text=text,
                word_count=len(words),
                transitions=(),
                overall_score=1.0,
                clash_count=0,
                rough_count=0,
                smooth_count=0,
                problem_positions=(),
                suggestions={},
            )

        # Get phonemes for each word
        word_phonemes = [self._get_word_phonemes(w) for w in words]

        # Analyze transitions
        transitions: List[WordTransition] = []
        for i in range(len(word_phonemes) - 1):
            from_word = word_phonemes[i]
            to_word = word_phonemes[i + 1]
            transition = self._analyze_transition(from_word, to_word, i)
            transitions.append(transition)

        # Compute statistics
        clash_count = sum(1 for t in transitions if t.quality == TransitionQuality.CLASH)
        rough_count = sum(1 for t in transitions if t.quality == TransitionQuality.ROUGH)
        smooth_count = sum(1 for t in transitions if t.quality == TransitionQuality.SMOOTH)
        neutral_count = len(transitions) - clash_count - rough_count - smooth_count

        # Overall score (weighted average)
        if transitions:
            avg_difficulty = sum(t.difficulty for t in transitions) / len(transitions)
            overall_score = 1.0 - avg_difficulty
        else:
            overall_score = 1.0

        # Identify problem positions
        problem_positions = tuple(
            t.position for t in transitions
            if t.quality in (TransitionQuality.CLASH, TransitionQuality.ROUGH)
        )

        # Generate suggestions for problem positions
        suggestions: Dict[int, List[str]] = {}
        for pos in problem_positions:
            if pos < len(words) - 1:
                # Suggest alternatives for the second word in the pair
                alternatives = self._suggest_alternatives(
                    words[pos], words[pos + 1]
                )
                if alternatives:
                    suggestions[pos + 1] = alternatives

        return HarmonyAnalysis(
            text=text,
            word_count=len(words),
            transitions=tuple(transitions),
            overall_score=overall_score,
            clash_count=clash_count,
            rough_count=rough_count,
            smooth_count=smooth_count,
            problem_positions=problem_positions,
            suggestions=suggestions,
        )

    def _extract_words(self, text: str) -> List[str]:
        """Extract words from text."""
        return re.findall(r'\b[a-zA-Z]+\b', text.lower())

    def _get_word_phonemes(self, word: str) -> WordPhonemes:
        """Get phoneme representation of a word."""
        phonemes: Tuple[str, ...] = ()

        # Try Varṇa-based phoneme extraction
        if HAS_RESONANCE and get_phonemes is not None:
            try:
                varna_phonemes = get_phonemes(word)
                if varna_phonemes:
                    phonemes = tuple(varna_phonemes)
            except Exception:
                pass

        # Fallback to letter-based approximation
        if not phonemes:
            phonemes = self._approximate_phonemes(word)

        # Extract first/last phonemes
        first_phoneme = phonemes[0] if phonemes else None
        last_phoneme = phonemes[-1] if phonemes else None

        # Get phoneme classes
        first_class = PHONEME_CLASSES.get(first_phoneme) if first_phoneme else None
        last_class = PHONEME_CLASSES.get(last_phoneme) if last_phoneme else None

        return WordPhonemes(
            word=word,
            phonemes=phonemes,
            first_phoneme=first_phoneme,
            last_phoneme=last_phoneme,
            first_class=first_class,
            last_class=last_class,
        )

    def _approximate_phonemes(self, word: str) -> Tuple[str, ...]:
        """Approximate phonemes from letters (fallback)."""
        phonemes = []
        word_lower = word.lower()
        i = 0
        while i < len(word_lower):
            char = word_lower[i]
            # Handle common digraphs
            if i + 1 < len(word_lower):
                digraph = word_lower[i:i+2]
                if digraph == 'sh':
                    phonemes.append('SH')
                    i += 2
                    continue
                elif digraph == 'ch':
                    phonemes.append('CH')
                    i += 2
                    continue
                elif digraph == 'th':
                    phonemes.append('TH')
                    i += 2
                    continue
                elif digraph == 'ng':
                    phonemes.append('NG')
                    i += 2
                    continue

            # Single letter
            if char in self.LETTER_TO_PHONEME:
                phonemes.append(self.LETTER_TO_PHONEME[char])
            i += 1

        return tuple(phonemes)

    def _analyze_transition(
        self,
        from_word: WordPhonemes,
        to_word: WordPhonemes,
        position: int,
    ) -> WordTransition:
        """Analyze transition between two adjacent words."""
        ending = from_word.last_phoneme
        starting = to_word.first_phoneme

        # Compute difficulty
        if from_word.last_class and to_word.first_class:
            key = (from_word.last_class, to_word.first_class)
            difficulty = TRANSITION_DIFFICULTY.get(key, DEFAULT_TRANSITION_DIFFICULTY)
        else:
            difficulty = DEFAULT_TRANSITION_DIFFICULTY

        # Same phoneme at boundary (potentially awkward)
        if ending and starting and ending == starting:
            difficulty = max(difficulty, 0.6)

        # Determine quality
        if difficulty >= self.clash_threshold:
            quality = TransitionQuality.CLASH
        elif difficulty >= self.rough_threshold:
            quality = TransitionQuality.ROUGH
        elif difficulty <= 0.2:
            quality = TransitionQuality.SMOOTH
        else:
            quality = TransitionQuality.NEUTRAL

        return WordTransition(
            word_from=from_word.word,
            word_to=to_word.word,
            ending_phoneme=ending,
            starting_phoneme=starting,
            quality=quality,
            difficulty=difficulty,
            position=position,
        )

    def _suggest_alternatives(
        self,
        context_word: str,
        problem_word: str,
    ) -> List[str]:
        """
        Suggest alternative words that flow better.

        Note: This is a simple heuristic. In a full implementation,
        this could use a thesaurus or word embedding similarity.
        """
        # Simple synonym suggestions for common words
        SIMPLE_SYNONYMS: Dict[str, List[str]] = {
            "big": ["large", "great", "vast"],
            "small": ["little", "tiny", "minor"],
            "good": ["fine", "nice", "great"],
            "bad": ["poor", "wrong", "ill"],
            "start": ["begin", "launch", "open"],
            "stop": ["end", "halt", "cease"],
            "fast": ["quick", "swift", "rapid"],
            "slow": ["gradual", "gentle", "easy"],
            "think": ["believe", "consider", "feel"],
            "know": ["understand", "realize", "see"],
        }

        alternatives = SIMPLE_SYNONYMS.get(problem_word, [])

        # Filter alternatives that would have smoother transitions
        context_phonemes = self._get_word_phonemes(context_word)
        smooth_alternatives = []

        for alt in alternatives:
            alt_phonemes = self._get_word_phonemes(alt)
            transition = self._analyze_transition(context_phonemes, alt_phonemes, 0)
            if transition.difficulty < self._get_word_phonemes(problem_word).first_phoneme:
                smooth_alternatives.append(alt)

        return smooth_alternatives[:3] if smooth_alternatives else alternatives[:3]


# =============================================================================
# SINGLETON
# =============================================================================

_engine: Optional[PhonemeHarmonyEngine] = None


def get_phoneme_harmony_engine() -> PhonemeHarmonyEngine:
    """Get or create singleton PhonemeHarmonyEngine instance."""
    global _engine
    if _engine is None:
        _engine = PhonemeHarmonyEngine()
    return _engine


def analyze_harmony(text: str) -> HarmonyAnalysis:
    """
    Convenience function to analyze phoneme harmony.

    Args:
        text: Text to analyze.

    Returns:
        HarmonyAnalysis with transition details.
    """
    return get_phoneme_harmony_engine().analyze(text)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "HAS_RESONANCE",
    "TransitionQuality",
    "PhonemeClass",
    "WordPhonemes",
    "WordTransition",
    "HarmonyAnalysis",
    "PhonemeHarmonyEngine",
    "get_phoneme_harmony_engine",
    "analyze_harmony",
]
