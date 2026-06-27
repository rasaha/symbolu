"""SymbolUEngine — deterministic wrapper over the REAL Symbol-U mappers.

This is the front end for the complementarity probe. It computes the Symbol-U
variable `U` for a word or sentence using the *actual* patent computation that
already lives in `symbolu_core.formulas` — not a re-implementation, and not the
lexicon approximation used in the older clean_softmax detector files.

The core patent rule is phonological: every character maps to a `SoundClass`
(stop / fricative / nasal / liquid / glide / vowel / …) and each SoundClass maps
to one of the 5 Vritti energy states (INERTIA / ACTIVATION / OSCILLATION /
TENSION / RELEASE) via `SOUND_CLASS_VRITTI_MAP`. A word's Vritti vector is the
normalized histogram of its characters' Vritti states; a sentence pools its
words. We also expose a SoundClass histogram as an extended descriptor.

This module is intentionally torch-free and transformers-free: it runs anywhere,
which keeps the cheapest experiment (synonym invariance, no LLM) fully offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from symbolu_core.formulas.vritti_mapper import (  # REAL mappers
    VrittiType,
    SoundClass,
    SOUND_CLASS_VRITTI_MAP,
    _get_consonant_sound_class,
)

VOWELS = frozenset("aeiou")

VRITTI_ORDER: List[VrittiType] = [
    VrittiType.INERTIA,
    VrittiType.ACTIVATION,
    VrittiType.OSCILLATION,
    VrittiType.TENSION,
    VrittiType.RELEASE,
]
VRITTI_INDEX: Dict[VrittiType, int] = {v: i for i, v in enumerate(VRITTI_ORDER)}
VRITTI_NAMES: List[str] = [v.name for v in VRITTI_ORDER]

SOUNDCLASS_ORDER: List[SoundClass] = [
    SoundClass.VOWEL,
    SoundClass.STOP,
    SoundClass.FRICATIVE,
    SoundClass.NASAL,
    SoundClass.LIQUID,
    SoundClass.GLIDE,
    SoundClass.AFFRICATE,
]
SOUNDCLASS_INDEX: Dict[SoundClass, int] = {s: i for i, s in enumerate(SOUNDCLASS_ORDER)}


def char_sound_class(ch: str) -> SoundClass:
    """Deterministic SoundClass for a single character (the real patent path)."""
    ch = ch.lower()
    if ch in VOWELS:
        return SoundClass.VOWEL
    return _get_consonant_sound_class(ch)


def char_vritti(ch: str):
    """The Vritti state a character contributes, or None for non-letters."""
    if not ch.isalpha():
        return None
    return SOUND_CLASS_VRITTI_MAP.get(char_sound_class(ch), VrittiType.INERTIA)


@dataclass
class WordEncoding:
    word: str
    vritti: List[float]            # length-5 distribution over VRITTI_ORDER
    soundclass: List[float]        # length-7 distribution over SOUNDCLASS_ORDER
    sound_classes: List[str]       # per-letter SoundClass names
    n_letters: int
    active_components: List[str] = field(default_factory=list)


class SymbolUEngine:
    """Deterministic Symbol-U encoder over the real phonological mappers."""

    vritti_order = VRITTI_ORDER
    vritti_names = VRITTI_NAMES
    # Dimensionality of the default U vector (vritti ++ soundclass).
    dim = len(VRITTI_ORDER) + len(SOUNDCLASS_ORDER)

    def encode_word(self, word: str) -> WordEncoding:
        vc = [0.0] * len(VRITTI_ORDER)
        sc = [0.0] * len(SOUNDCLASS_ORDER)
        classes: List[str] = []
        n = 0
        for ch in word:
            v = char_vritti(ch)
            if v is None:
                continue
            vc[VRITTI_INDEX[v]] += 1.0
            cls = char_sound_class(ch)
            if cls in SOUNDCLASS_INDEX:
                sc[SOUNDCLASS_INDEX[cls]] += 1.0
            classes.append(cls.name)
            n += 1
        if sum(vc) > 0:
            vc = [c / sum(vc) for c in vc]
        if sum(sc) > 0:
            sc = [c / sum(sc) for c in sc]
        return WordEncoding(
            word=word, vritti=vc, soundclass=sc, sound_classes=classes,
            n_letters=n, active_components=["vritti_mapper", "sound_class_map"],
        )

    def vritti_vec(self, text: str) -> List[float]:
        """Mean-pooled Vritti distribution for a word or sentence (length 5)."""
        toks = _tokenize(text)
        if not toks:
            return [0.0] * len(VRITTI_ORDER)
        acc = [0.0] * len(VRITTI_ORDER)
        for w in toks:
            wv = self.encode_word(w).vritti
            for i in range(len(acc)):
                acc[i] += wv[i]
        return [a / len(toks) for a in acc]

    def encode(self, text: str) -> List[float]:
        """Default U vector for a word/sentence: vritti(5) ++ soundclass(7)."""
        toks = _tokenize(text)
        if not toks:
            return [0.0] * self.dim
        v = [0.0] * len(VRITTI_ORDER)
        s = [0.0] * len(SOUNDCLASS_ORDER)
        for w in toks:
            e = self.encode_word(w)
            for i in range(len(v)):
                v[i] += e.vritti[i]
            for i in range(len(s)):
                s[i] += e.soundclass[i]
        v = [x / len(toks) for x in v]
        s = [x / len(toks) for x in s]
        return v + s


def _tokenize(text: str) -> List[str]:
    return [t for t in "".join(c if c.isalpha() else " " for c in text.lower()).split() if t]


if __name__ == "__main__":
    eng = SymbolUEngine()
    print(f"U dim = {eng.dim}  (vritti {len(VRITTI_ORDER)} + soundclass {len(SOUNDCLASS_ORDER)})")
    for w in ["happy", "glad", "joyful", "cheerful", "merry"]:
        e = eng.encode_word(w)
        vec = ", ".join(f"{x:.2f}" for x in e.vritti)
        print(f"{w:10} vritti=[{vec}]  classes={e.sound_classes}")
    print("active:", eng.encode_word("happy").active_components)
