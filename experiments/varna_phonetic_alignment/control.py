"""Coarse varga place/manner control matrix C (PREREG §5).

C captures the **trivial alphabet grid** the varṇa table is physically laid out
on: the 5-varga place rows × the manner column (unvoiced/voiced × unaspirated/
aspirated × nasal), plus the semivowel / sibilant / aspirate / conjunct classes.

This is standard, frozen Sanskrit phonological class membership — NOT a researcher
choice. The mandatory partial Mantel controls for C so that "the table tracks
sound" is separated from "the table is laid out on the same grid as the phonetics".

No semantics, no fit. C is a dissimilarity in {0,1,2} = number of class dimensions
(place, manner) on which two varṇas differ.
"""
from __future__ import annotations

import numpy as np

# --- FROZEN standard class membership for the 34 consonant varṇas -------------
# place : velar/palatal/retroflex/dental/labial + semivowel/sibilant/aspirate/conjunct
# manner: 1 unvoiced-unaspirated, 2 unvoiced-aspirated, 3 voiced-unaspirated,
#         4 voiced-aspirated, 5 nasal + approximant / sibilant / aspirate / conjunct
PLACE = {
    "ka": "velar", "kha": "velar", "ga": "velar", "gha": "velar", "nga": "velar",
    "ca": "palatal", "cha": "palatal", "ja": "palatal", "jha": "palatal", "nya": "palatal",
    "tta": "retroflex", "ttha": "retroflex", "dda": "retroflex", "ddha": "retroflex", "nna": "retroflex",
    "ta": "dental", "tha": "dental", "da": "dental", "dha": "dental", "na": "dental",
    "pa": "labial", "pha": "labial", "ba": "labial", "bha": "labial", "ma": "labial",
    "ya": "semivowel", "ra": "semivowel", "la": "semivowel", "va": "semivowel",
    "sha": "sibilant", "ssa": "sibilant", "sa": "sibilant",
    "ha": "aspirate", "ksha": "conjunct",
}
MANNER = {
    "ka": "stop1", "kha": "stop2", "ga": "stop3", "gha": "stop4", "nga": "nasal",
    "ca": "stop1", "cha": "stop2", "ja": "stop3", "jha": "stop4", "nya": "nasal",
    "tta": "stop1", "ttha": "stop2", "dda": "stop3", "ddha": "stop4", "nna": "nasal",
    "ta": "stop1", "tha": "stop2", "da": "stop3", "dha": "stop4", "na": "nasal",
    "pa": "stop1", "pha": "stop2", "ba": "stop3", "bha": "stop4", "ma": "nasal",
    "ya": "approximant", "ra": "approximant", "la": "approximant", "va": "approximant",
    "sha": "sibilant", "ssa": "sibilant", "sa": "sibilant",
    "ha": "aspirate", "ksha": "conjunct",
}


def class_labels(keys):
    """Return [(place, manner)] in the order of `keys` (raises on unknown key)."""
    return [(PLACE[k], MANNER[k]) for k in keys]


def control_matrix(keys) -> np.ndarray:
    """Coarse class dissimilarity C[i,j] = #{place differs} + #{manner differs} ∈ {0,1,2}."""
    labs = class_labels(keys)
    n = len(labs)
    C = np.zeros((n, n), float)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            C[i, j] = (labs[i][0] != labs[j][0]) + (labs[i][1] != labs[j][1])
    return C
