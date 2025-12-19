"""
Phase-14: Phoneme Extractor
===========================

Extracts phonemes from words for phonemic-ontological accumulation.

Architecture:
    1. Lookup in embedded mini-dictionary (common words)
    2. Fallback to rule-based grapheme-to-phoneme conversion
    3. Output: phoneme sequence + PPV estimate

PPV Estimate Derivation:
    From phoneme properties, derive approximate values for 8 PPV dimensions:
    (attack, sustain, brightness, warmth, density, flow, resonance, edge)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


# =============================================================================
# Phoneme Categories
# =============================================================================

class PhonemeCategory(Enum):
    """Categories of phonemes based on articulation."""
    PLOSIVE = "PLOSIVE"           # p, b, t, d, k, g - sudden release
    FRICATIVE = "FRICATIVE"       # f, v, s, z, sh, zh, th - turbulent airflow
    AFFRICATE = "AFFRICATE"       # ch, j - plosive + fricative
    NASAL = "NASAL"               # m, n, ng - nasal resonance
    LIQUID = "LIQUID"             # l, r - flowing
    GLIDE = "GLIDE"               # w, y - semi-vowels
    VOWEL_SHORT = "VOWEL_SHORT"   # short vowels
    VOWEL_LONG = "VOWEL_LONG"     # long vowels/diphthongs


# =============================================================================
# Phoneme Inventory (ARPABET-style)
# =============================================================================

# Map phonemes to categories
PHONEME_CATEGORY: Dict[str, PhonemeCategory] = {
    # Plosives
    "P": PhonemeCategory.PLOSIVE, "B": PhonemeCategory.PLOSIVE,
    "T": PhonemeCategory.PLOSIVE, "D": PhonemeCategory.PLOSIVE,
    "K": PhonemeCategory.PLOSIVE, "G": PhonemeCategory.PLOSIVE,
    # Fricatives
    "F": PhonemeCategory.FRICATIVE, "V": PhonemeCategory.FRICATIVE,
    "S": PhonemeCategory.FRICATIVE, "Z": PhonemeCategory.FRICATIVE,
    "SH": PhonemeCategory.FRICATIVE, "ZH": PhonemeCategory.FRICATIVE,
    "TH": PhonemeCategory.FRICATIVE, "DH": PhonemeCategory.FRICATIVE,
    "HH": PhonemeCategory.FRICATIVE,
    # Affricates
    "CH": PhonemeCategory.AFFRICATE, "JH": PhonemeCategory.AFFRICATE,
    # Nasals
    "M": PhonemeCategory.NASAL, "N": PhonemeCategory.NASAL,
    "NG": PhonemeCategory.NASAL,
    # Liquids
    "L": PhonemeCategory.LIQUID, "R": PhonemeCategory.LIQUID,
    # Glides
    "W": PhonemeCategory.GLIDE, "Y": PhonemeCategory.GLIDE,
    # Short vowels
    "AH": PhonemeCategory.VOWEL_SHORT, "EH": PhonemeCategory.VOWEL_SHORT,
    "IH": PhonemeCategory.VOWEL_SHORT, "UH": PhonemeCategory.VOWEL_SHORT,
    "AE": PhonemeCategory.VOWEL_SHORT, "ER": PhonemeCategory.VOWEL_SHORT,
    # Long vowels / diphthongs
    "AA": PhonemeCategory.VOWEL_LONG, "AO": PhonemeCategory.VOWEL_LONG,
    "AW": PhonemeCategory.VOWEL_LONG, "AY": PhonemeCategory.VOWEL_LONG,
    "EY": PhonemeCategory.VOWEL_LONG, "IY": PhonemeCategory.VOWEL_LONG,
    "OW": PhonemeCategory.VOWEL_LONG, "OY": PhonemeCategory.VOWEL_LONG,
    "UW": PhonemeCategory.VOWEL_LONG,
}


def get_phoneme_category(phoneme: str) -> PhonemeCategory:
    """Get category for a phoneme, defaults to VOWEL_SHORT."""
    # Remove stress markers (0, 1, 2)
    clean = phoneme.rstrip("012")
    return PHONEME_CATEGORY.get(clean, PhonemeCategory.VOWEL_SHORT)


# =============================================================================
# Mini Dictionary (Common Words)
# =============================================================================

# Embedded subset for common words (CMU-style pronunciations)
MINI_DICTIONARY: Dict[str, Tuple[str, ...]] = {
    # Action verbs
    "run": ("R", "AH", "N"),
    "walk": ("W", "AO", "K"),
    "jump": ("JH", "AH", "M", "P"),
    "think": ("TH", "IH", "NG", "K"),
    "make": ("M", "EY", "K"),
    "do": ("D", "UW"),
    "say": ("S", "EY"),
    "go": ("G", "OW"),
    "get": ("G", "EH", "T"),
    "give": ("G", "IH", "V"),
    "take": ("T", "EY", "K"),
    "come": ("K", "AH", "M"),
    "see": ("S", "IY"),
    "know": ("N", "OW"),
    "use": ("Y", "UW", "Z"),
    "find": ("F", "AY", "N", "D"),
    "want": ("W", "AA", "N", "T"),
    "tell": ("T", "EH", "L"),
    "ask": ("AE", "S", "K"),
    "work": ("W", "ER", "K"),
    "feel": ("F", "IY", "L"),
    "try": ("T", "R", "AY"),
    "leave": ("L", "IY", "V"),
    "call": ("K", "AO", "L"),
    "keep": ("K", "IY", "P"),
    "let": ("L", "EH", "T"),
    "begin": ("B", "IH", "G", "IH", "N"),
    "seem": ("S", "IY", "M"),
    "help": ("HH", "EH", "L", "P"),
    "show": ("SH", "OW"),
    "hear": ("HH", "IY", "R"),
    "play": ("P", "L", "EY"),
    "move": ("M", "UW", "V"),
    "live": ("L", "IH", "V"),
    "believe": ("B", "IH", "L", "IY", "V"),
    "hold": ("HH", "OW", "L", "D"),
    "bring": ("B", "R", "IH", "NG"),
    "happen": ("HH", "AE", "P", "AH", "N"),
    "write": ("R", "AY", "T"),
    "provide": ("P", "R", "AH", "V", "AY", "D"),
    "stand": ("S", "T", "AE", "N", "D"),
    "lose": ("L", "UW", "Z"),
    "pay": ("P", "EY"),
    "meet": ("M", "IY", "T"),
    "include": ("IH", "N", "K", "L", "UW", "D"),
    "continue": ("K", "AH", "N", "T", "IH", "N", "Y", "UW"),
    "set": ("S", "EH", "T"),
    "learn": ("L", "ER", "N"),
    "change": ("CH", "EY", "N", "JH"),
    "lead": ("L", "IY", "D"),
    "understand": ("AH", "N", "D", "ER", "S", "T", "AE", "N", "D"),
    "watch": ("W", "AA", "CH"),
    "follow": ("F", "AA", "L", "OW"),
    "stop": ("S", "T", "AA", "P"),
    "create": ("K", "R", "IY", "EY", "T"),
    "speak": ("S", "P", "IY", "K"),
    "read": ("R", "IY", "D"),
    "allow": ("AH", "L", "AW"),
    "add": ("AE", "D"),
    "spend": ("S", "P", "EH", "N", "D"),
    "grow": ("G", "R", "OW"),
    "open": ("OW", "P", "AH", "N"),
    "build": ("B", "IH", "L", "D"),
    "form": ("F", "AO", "R", "M"),
    "act": ("AE", "K", "T"),
    "decide": ("D", "IH", "S", "AY", "D"),
    "return": ("R", "IH", "T", "ER", "N"),
    "fall": ("F", "AO", "L"),
    "cut": ("K", "AH", "T"),
    "reach": ("R", "IY", "CH"),
    "kill": ("K", "IH", "L"),
    "remain": ("R", "IH", "M", "EY", "N"),
    "suggest": ("S", "AH", "JH", "EH", "S", "T"),
    "raise": ("R", "EY", "Z"),
    "pass": ("P", "AE", "S"),
    "sell": ("S", "EH", "L"),
    "require": ("R", "IH", "K", "W", "AY", "R"),
    "report": ("R", "IH", "P", "AO", "R", "T"),
    "pull": ("P", "UH", "L"),
    "develop": ("D", "IH", "V", "EH", "L", "AH", "P"),
    "push": ("P", "UH", "SH"),
    "throw": ("TH", "R", "OW"),
    "catch": ("K", "AE", "CH"),
    "touch": ("T", "AH", "CH"),
    "cause": ("K", "AO", "Z"),
    "produce": ("P", "R", "AH", "D", "UW", "S"),
    "receive": ("R", "IH", "S", "IY", "V"),
    "remember": ("R", "IH", "M", "EH", "M", "B", "ER"),
    "consider": ("K", "AH", "N", "S", "IH", "D", "ER"),
    "appear": ("AH", "P", "IY", "R"),
    "buy": ("B", "AY"),
    "wait": ("W", "EY", "T"),
    "serve": ("S", "ER", "V"),
    "die": ("D", "AY"),
    "send": ("S", "EH", "N", "D"),
    "expect": ("IH", "K", "S", "P", "EH", "K", "T"),
    "stay": ("S", "T", "EY"),
    "pick": ("P", "IH", "K"),
    "plan": ("P", "L", "AE", "N"),
    # Cognitive/abstract
    "reason": ("R", "IY", "Z", "AH", "N"),
    "purpose": ("P", "ER", "P", "AH", "S"),
    "direct": ("D", "ER", "EH", "K", "T"),
    "unify": ("Y", "UW", "N", "AH", "F", "AY"),
    "absolve": ("AH", "B", "Z", "AA", "L", "V"),
    "observe": ("AH", "B", "Z", "ER", "V"),
    "tag": ("T", "AE", "G"),
    # Scientific/technical
    "enzyme": ("EH", "N", "Z", "AY", "M"),
    "catalyze": ("K", "AE", "T", "AH", "L", "AY", "Z"),
    "catalyzes": ("K", "AE", "T", "AH", "L", "AY", "Z", "IH", "Z"),
    "reaction": ("R", "IY", "AE", "K", "SH", "AH", "N"),
    "molecule": ("M", "AA", "L", "AH", "K", "Y", "UW", "L"),
    "protein": ("P", "R", "OW", "T", "IY", "N"),
    "cell": ("S", "EH", "L"),
    "energy": ("EH", "N", "ER", "JH", "IY"),
    "system": ("S", "IH", "S", "T", "AH", "M"),
    "process": ("P", "R", "AA", "S", "EH", "S"),
    "structure": ("S", "T", "R", "AH", "K", "CH", "ER"),
    "function": ("F", "AH", "NG", "K", "SH", "AH", "N"),
    "result": ("R", "IH", "Z", "AH", "L", "T"),
    "effect": ("IH", "F", "EH", "K", "T"),
    "data": ("D", "EY", "T", "AH"),
    "analysis": ("AH", "N", "AE", "L", "AH", "S", "IH", "S"),
    # Common nouns
    "time": ("T", "AY", "M"),
    "year": ("Y", "IY", "R"),
    "people": ("P", "IY", "P", "AH", "L"),
    "way": ("W", "EY"),
    "day": ("D", "EY"),
    "man": ("M", "AE", "N"),
    "woman": ("W", "UH", "M", "AH", "N"),
    "child": ("CH", "AY", "L", "D"),
    "world": ("W", "ER", "L", "D"),
    "life": ("L", "AY", "F"),
    "hand": ("HH", "AE", "N", "D"),
    "part": ("P", "AA", "R", "T"),
    "place": ("P", "L", "EY", "S"),
    "case": ("K", "EY", "S"),
    "week": ("W", "IY", "K"),
    "company": ("K", "AH", "M", "P", "AH", "N", "IY"),
    "group": ("G", "R", "UW", "P"),
    "problem": ("P", "R", "AA", "B", "L", "AH", "M"),
    "fact": ("F", "AE", "K", "T"),
    "question": ("K", "W", "EH", "S", "CH", "AH", "N"),
    "number": ("N", "AH", "M", "B", "ER"),
    "night": ("N", "AY", "T"),
    "point": ("P", "OY", "N", "T"),
    "home": ("HH", "OW", "M"),
    "water": ("W", "AO", "T", "ER"),
    "room": ("R", "UW", "M"),
    "mother": ("M", "AH", "DH", "ER"),
    "area": ("EH", "R", "IY", "AH"),
    "money": ("M", "AH", "N", "IY"),
    "story": ("S", "T", "AO", "R", "IY"),
    "state": ("S", "T", "EY", "T"),
    "idea": ("AY", "D", "IY", "AH"),
    "truth": ("T", "R", "UW", "TH"),
    "beauty": ("B", "Y", "UW", "T", "IY"),
    "justice": ("JH", "AH", "S", "T", "IH", "S"),
    "freedom": ("F", "R", "IY", "D", "AH", "M"),
    "love": ("L", "AH", "V"),
    "peace": ("P", "IY", "S"),
    "power": ("P", "AW", "ER"),
    "knowledge": ("N", "AA", "L", "IH", "JH"),
    "wisdom": ("W", "IH", "Z", "D", "AH", "M"),
    # Adjectives
    "good": ("G", "UH", "D"),
    "new": ("N", "UW"),
    "first": ("F", "ER", "S", "T"),
    "last": ("L", "AE", "S", "T"),
    "long": ("L", "AO", "NG"),
    "great": ("G", "R", "EY", "T"),
    "little": ("L", "IH", "T", "AH", "L"),
    "own": ("OW", "N"),
    "other": ("AH", "DH", "ER"),
    "old": ("OW", "L", "D"),
    "right": ("R", "AY", "T"),
    "big": ("B", "IH", "G"),
    "high": ("HH", "AY"),
    "small": ("S", "M", "AO", "L"),
    "large": ("L", "AA", "R", "JH"),
    "different": ("D", "IH", "F", "ER", "AH", "N", "T"),
    "important": ("IH", "M", "P", "AO", "R", "T", "AH", "N", "T"),
    "possible": ("P", "AA", "S", "AH", "B", "AH", "L"),
    "necessary": ("N", "EH", "S", "AH", "S", "EH", "R", "IY"),
    # Connectors
    "because": ("B", "IH", "K", "AO", "Z"),
    "therefore": ("DH", "EH", "R", "F", "AO", "R"),
    "however": ("HH", "AW", "EH", "V", "ER"),
    "although": ("AO", "L", "DH", "OW"),
    # The/a/is etc.
    "the": ("DH", "AH"),
    "a": ("AH"),
    "is": ("IH", "Z"),
    "are": ("AA", "R"),
    "was": ("W", "AA", "Z"),
    "were": ("W", "ER"),
    "be": ("B", "IY"),
    "been": ("B", "IH", "N"),
    "being": ("B", "IY", "IH", "NG"),
    "have": ("HH", "AE", "V"),
    "has": ("HH", "AE", "Z"),
    "had": ("HH", "AE", "D"),
    "will": ("W", "IH", "L"),
    "would": ("W", "UH", "D"),
    "could": ("K", "UH", "D"),
    "should": ("SH", "UH", "D"),
    "can": ("K", "AE", "N"),
    "may": ("M", "EY"),
    "might": ("M", "AY", "T"),
    "must": ("M", "AH", "S", "T"),
    "that": ("DH", "AE", "T"),
    "this": ("DH", "IH", "S"),
    "these": ("DH", "IY", "Z"),
    "those": ("DH", "OW", "Z"),
    "what": ("W", "AH", "T"),
    "which": ("W", "IH", "CH"),
    "who": ("HH", "UW"),
    "where": ("W", "EH", "R"),
    "when": ("W", "EH", "N"),
    "why": ("W", "AY"),
    "how": ("HH", "AW"),
    "all": ("AO", "L"),
    "each": ("IY", "CH"),
    "every": ("EH", "V", "R", "IY"),
    "both": ("B", "OW", "TH"),
    "few": ("F", "Y", "UW"),
    "more": ("M", "AO", "R"),
    "most": ("M", "OW", "S", "T"),
    "some": ("S", "AH", "M"),
    "any": ("EH", "N", "IY"),
    "no": ("N", "OW"),
    "not": ("N", "AA", "T"),
    "only": ("OW", "N", "L", "IY"),
    "very": ("V", "EH", "R", "IY"),
    "just": ("JH", "AH", "S", "T"),
    "also": ("AO", "L", "S", "OW"),
    "now": ("N", "AW"),
    "here": ("HH", "IY", "R"),
    "there": ("DH", "EH", "R"),
    "then": ("DH", "EH", "N"),
    "so": ("S", "OW"),
    "if": ("IH", "F"),
    "or": ("AO", "R"),
    "and": ("AE", "N", "D"),
    "but": ("B", "AH", "T"),
    "as": ("AE", "Z"),
    "with": ("W", "IH", "TH"),
    "by": ("B", "AY"),
    "for": ("F", "AO", "R"),
    "from": ("F", "R", "AH", "M"),
    "to": ("T", "UW"),
    "of": ("AH", "V"),
    "in": ("IH", "N"),
    "on": ("AA", "N"),
    "at": ("AE", "T"),
    "up": ("AH", "P"),
    "out": ("AW", "T"),
    "about": ("AH", "B", "AW", "T"),
    "into": ("IH", "N", "T", "UW"),
    "over": ("OW", "V", "ER"),
    "after": ("AE", "F", "T", "ER"),
    "before": ("B", "IH", "F", "AO", "R"),
    "between": ("B", "IH", "T", "W", "IY", "N"),
    "under": ("AH", "N", "D", "ER"),
    "again": ("AH", "G", "EH", "N"),
    "still": ("S", "T", "IH", "L"),
    "even": ("IY", "V", "AH", "N"),
    "back": ("B", "AE", "K"),
    "well": ("W", "EH", "L"),
    "down": ("D", "AW", "N"),
    "away": ("AH", "W", "EY"),
    "off": ("AO", "F"),
    "really": ("R", "IY", "L", "IY"),
    "always": ("AO", "L", "W", "EY", "Z"),
    "never": ("N", "EH", "V", "ER"),
    "sometimes": ("S", "AH", "M", "T", "AY", "M", "Z"),
    "often": ("AO", "F", "AH", "N"),
    "usually": ("Y", "UW", "ZH", "AH", "L", "IY"),
}


# =============================================================================
# Grapheme-to-Phoneme Rules (Fallback)
# =============================================================================

# Simple letter-to-phoneme mappings (approximation)
GRAPHEME_RULES: Dict[str, Tuple[str, ...]] = {
    "a": ("AE",), "e": ("EH",), "i": ("IH",), "o": ("AA",), "u": ("AH",),
    "b": ("B",), "c": ("K",), "d": ("D",), "f": ("F",), "g": ("G",),
    "h": ("HH",), "j": ("JH",), "k": ("K",), "l": ("L",), "m": ("M",),
    "n": ("N",), "p": ("P",), "q": ("K",), "r": ("R",), "s": ("S",),
    "t": ("T",), "v": ("V",), "w": ("W",), "x": ("K", "S"), "y": ("Y",),
    "z": ("Z",),
}

# Multi-character patterns (checked first)
DIGRAPH_RULES: Dict[str, Tuple[str, ...]] = {
    "ch": ("CH",), "sh": ("SH",), "th": ("TH",), "ph": ("F",),
    "wh": ("W",), "ck": ("K",), "ng": ("NG",), "qu": ("K", "W"),
    "ee": ("IY",), "ea": ("IY",), "oo": ("UW",), "ai": ("EY",),
    "ay": ("EY",), "ey": ("IY",), "ou": ("AW",), "ow": ("OW",),
    "oi": ("OY",), "oy": ("OY",), "ie": ("IY",), "igh": ("AY",),
    "tion": ("SH", "AH", "N"), "sion": ("ZH", "AH", "N"),
}


def apply_fallback_rules(word: str) -> Tuple[str, ...]:
    """Apply simple grapheme-to-phoneme rules."""
    word_lower = word.lower()
    phonemes: List[str] = []
    i = 0

    while i < len(word_lower):
        matched = False

        # Try multi-character patterns (longest first)
        for length in [4, 3, 2]:
            if i + length <= len(word_lower):
                chunk = word_lower[i:i+length]
                if chunk in DIGRAPH_RULES:
                    phonemes.extend(DIGRAPH_RULES[chunk])
                    i += length
                    matched = True
                    break

        if not matched:
            char = word_lower[i]
            if char in GRAPHEME_RULES:
                phonemes.extend(GRAPHEME_RULES[char])
            # Skip non-alpha characters
            i += 1

    return tuple(phonemes)


# =============================================================================
# PPV Estimate from Phonemes
# =============================================================================

# Category weights for PPV dimensions
# PPV: (attack, sustain, brightness, warmth, density, flow, resonance, edge)
CATEGORY_PPV_WEIGHTS: Dict[PhonemeCategory, Tuple[float, ...]] = {
    # Plosives: high attack, low sustain, medium brightness, low warmth, high density, low flow, low resonance, high edge
    PhonemeCategory.PLOSIVE:     (8.0, 2.0, 5.0, 2.0, 7.0, 2.0, 3.0, 8.0),
    # Fricatives: medium attack, high sustain, high brightness, low warmth, medium density, high flow, medium resonance, high edge
    PhonemeCategory.FRICATIVE:   (5.0, 7.0, 7.0, 2.0, 5.0, 7.0, 4.0, 7.0),
    # Affricates: high attack, medium sustain, high brightness, low warmth, high density, medium flow, medium resonance, very high edge
    PhonemeCategory.AFFRICATE:   (7.0, 5.0, 7.0, 2.0, 7.0, 4.0, 4.0, 9.0),
    # Nasals: low attack, high sustain, low brightness, high warmth, medium density, medium flow, high resonance, low edge
    PhonemeCategory.NASAL:       (2.0, 7.0, 3.0, 7.0, 5.0, 5.0, 8.0, 2.0),
    # Liquids: low attack, high sustain, medium brightness, high warmth, low density, high flow, high resonance, low edge
    PhonemeCategory.LIQUID:      (2.0, 8.0, 4.0, 7.0, 3.0, 8.0, 7.0, 2.0),
    # Glides: low attack, medium sustain, medium brightness, high warmth, low density, high flow, medium resonance, low edge
    PhonemeCategory.GLIDE:       (2.0, 5.0, 4.0, 7.0, 2.0, 7.0, 5.0, 2.0),
    # Short vowels: low attack, medium sustain, medium brightness, high warmth, low density, medium flow, high resonance, low edge
    PhonemeCategory.VOWEL_SHORT: (1.0, 5.0, 4.0, 7.0, 2.0, 5.0, 7.0, 1.0),
    # Long vowels: low attack, high sustain, medium brightness, high warmth, low density, high flow, very high resonance, low edge
    PhonemeCategory.VOWEL_LONG:  (1.0, 8.0, 4.0, 8.0, 2.0, 7.0, 9.0, 1.0),
}


def estimate_ppv(phonemes: Tuple[str, ...]) -> Tuple[int, ...]:
    """
    Estimate PPV from phoneme sequence.

    Returns 8-dimensional tuple: (attack, sustain, brightness, warmth, density, flow, resonance, edge)
    Values 0-10 inclusive.
    """
    if not phonemes:
        return (5, 5, 5, 5, 5, 5, 5, 5)  # Neutral default

    # Accumulate weighted contributions
    sums = [0.0] * 8
    count = 0

    for phoneme in phonemes:
        category = get_phoneme_category(phoneme)
        weights = CATEGORY_PPV_WEIGHTS[category]

        # Initial phonemes have more impact on attack
        position_weight = 1.5 if count == 0 else 1.0

        for i in range(8):
            sums[i] += weights[i] * position_weight

        count += 1

    # Average and clamp to 0-10
    if count > 0:
        result = tuple(
            min(10, max(0, int(round(s / count))))
            for s in sums
        )
    else:
        result = (5, 5, 5, 5, 5, 5, 5, 5)

    return result


# =============================================================================
# Phoneme Analysis Result
# =============================================================================

@dataclass(frozen=True)
class PhonemeAnalysis:
    """Result of phoneme extraction."""
    word: str                         # Original word
    phonemes: Tuple[str, ...]         # Phoneme sequence
    ppv_estimate: Tuple[int, ...]     # 8-dimensional PPV estimate
    source: str                       # "dictionary" or "rules"
    analysis_hash: str                # Deterministic hash

    def phoneme_count(self) -> int:
        """Get number of phonemes."""
        return len(self.phonemes)

    def category_counts(self) -> Dict[PhonemeCategory, int]:
        """Count phonemes by category."""
        counts: Dict[PhonemeCategory, int] = {}
        for phoneme in self.phonemes:
            cat = get_phoneme_category(phoneme)
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def dominant_category(self) -> Optional[PhonemeCategory]:
        """Get most frequent phoneme category."""
        counts = self.category_counts()
        if not counts:
            return None
        return max(counts.items(), key=lambda x: x[1])[0]


def compute_analysis_hash(word: str, phonemes: Tuple[str, ...]) -> str:
    """Compute deterministic hash for analysis."""
    content = f"{word.lower()}|{'_'.join(phonemes)}"
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# =============================================================================
# Phoneme Extractor
# =============================================================================

@dataclass(frozen=True)
class PhonemeExtractor:
    """
    Extracts phonemes from words.

    Uses embedded dictionary first, then fallback rules.
    """
    _dictionary: Dict[str, Tuple[str, ...]]

    def extract(self, word: str) -> PhonemeAnalysis:
        """Extract phonemes from a word."""
        word_clean = word.strip().lower()

        # Try dictionary lookup
        if word_clean in self._dictionary:
            phonemes = self._dictionary[word_clean]
            source = "dictionary"
        else:
            phonemes = apply_fallback_rules(word_clean)
            source = "rules"

        ppv = estimate_ppv(phonemes)
        analysis_hash = compute_analysis_hash(word_clean, phonemes)

        return PhonemeAnalysis(
            word=word_clean,
            phonemes=phonemes,
            ppv_estimate=ppv,
            source=source,
            analysis_hash=analysis_hash,
        )

    def extract_batch(self, words: Tuple[str, ...]) -> Tuple[PhonemeAnalysis, ...]:
        """Extract phonemes from multiple words."""
        return tuple(self.extract(w) for w in words)

    def has_word(self, word: str) -> bool:
        """Check if word is in dictionary."""
        return word.strip().lower() in self._dictionary

    def vocabulary_size(self) -> int:
        """Get dictionary size."""
        return len(self._dictionary)


# =============================================================================
# Factory Functions
# =============================================================================

def create_extractor() -> PhonemeExtractor:
    """Create phoneme extractor with default dictionary."""
    return PhonemeExtractor(_dictionary=dict(MINI_DICTIONARY))


def create_extractor_with_dictionary(
    dictionary: Dict[str, Tuple[str, ...]]
) -> PhonemeExtractor:
    """Create phoneme extractor with custom dictionary."""
    return PhonemeExtractor(_dictionary=dict(dictionary))


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Enums
    "PhonemeCategory",
    # Data classes
    "PhonemeAnalysis",
    # Main class
    "PhonemeExtractor",
    # Functions
    "create_extractor",
    "create_extractor_with_dictionary",
    "get_phoneme_category",
    "estimate_ppv",
    "apply_fallback_rules",
    "compute_analysis_hash",
    # Constants
    "PHONEME_CATEGORY",
    "CATEGORY_PPV_WEIGHTS",
    "MINI_DICTIONARY",
]
