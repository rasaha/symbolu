#!/usr/bin/env python3
"""Seeded pronounceable PSEUDOWORDS for the Design-B CRS test (PREREG_CRS_POLE_SELECTION.md).

No dictionary meaning by construction — that is the whole point: there is no gloss/valence for the semantic
term S to leak (the non-circularity linchpin). Each pseudoword is a roman string the engine's roman parser
accepts. The inventory spans the sharp(voiceless/high-front) ↔ round(sonorant/low-back) space so an
INDEPENDENT sound-symbolism probe has variance to detect.
"""
import random as _rnd

_ONSET = ["k", "t", "p", "s", "sh", "ch", "m", "n", "l", "r", "v", "b", "d", "g"]
_VOWEL = ["a", "i", "u", "e", "o", "aa", "ee", "oo"]
SEED = 7


def generate(n=80, seed=SEED, min_syl=2, max_syl=3):
    r = _rnd.Random(seed)
    out, seen = [], set()
    while len(out) < n:
        ns = r.randint(min_syl, max_syl)
        w = "".join(r.choice(_ONSET) + r.choice(_VOWEL) for _ in range(ns))
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


if __name__ == "__main__":
    print(" ".join(generate()))
