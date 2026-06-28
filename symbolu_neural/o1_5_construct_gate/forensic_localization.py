"""Forensic localization (read-only) — WHERE semantic meaning is lost in the reading.

Does NOT modify or improve the reading/gate. Controlled single-variable perturbations,
measured at two pipeline depths: varṇa decomposition (stage B) and final reading (stage D).
    python -m symbolu_neural.o1_5_construct_gate.forensic_localization
"""
from __future__ import annotations

import itertools
import numpy as np

from varna_lens.varna_lens import analyze
from .gate import reading_vector


def varna_keys(word):
    try:
        r, _, _ = analyze(word.lower().strip(".,!?"), model="op")
    except Exception:
        r = {}
    return [it.get("key") for it in (r or {}).get("sequence", []) if it.get("key")]


def jacc_dist(a, b):
    A, B = set(a), set(b)
    return 1 - (len(A & B) / len(A | B) if A | B else 0)


SYNONYMS = [["happy", "joyful", "elated", "glad", "cheerful"],
            ["sad", "sorrowful", "mournful", "miserable", "gloomy"],
            ["calm", "serene", "tranquil", "peaceful", "placid"],
            ["fast", "quick", "rapid", "swift", "speedy"]]
ANTONYMS = [("happy", "sad"), ("calm", "frantic"), ("success", "failure"),
            ("true", "false"), ("safe", "dangerous"), ("win", "lose")]
RHYMES = [("joy", "ploy"), ("hope", "rope"), ("light", "fight"), ("cat", "bat"),
          ("big", "pig"), ("fast", "cast"), ("name", "game")]
ORDER = [("the dog bit the man", "the man bit the dog"),
         ("she helped him", "he helped her"),
         ("profit before people", "people before profit")]


def run():
    corpus = ["happy", "sad", "joyful", "grief", "calm", "urgent", "verified", "guess",
              "safe", "danger", "success", "failure"]
    ref = np.std([reading_vector(t) for t in corpus], 0); ref = np.where(ref < 1e-9, 1, ref)
    rdist = lambda a, b: float(np.linalg.norm((reading_vector(a) - reading_vector(b)) / ref))

    out = {}
    syn_j = [jacc_dist(varna_keys(a), varna_keys(b)) for g in SYNONYMS for a, b in itertools.combinations(g, 2)]
    rnd_j = [jacc_dist(varna_keys(a), varna_keys(b)) for a, b in itertools.combinations(
             ["happy", "calm", "success", "true", "ocean", "table", "quantum", "river"], 2)]
    out["M1_synonym_varna_dist"] = float(np.mean(syn_j))
    out["M1_random_varna_dist"] = float(np.mean(rnd_j))

    out["M2_synonym_reading_dist"] = float(np.mean([rdist(a, b) for g in SYNONYMS for a, b in itertools.combinations(g, 2)]))
    out["M2_antonym_reading_dist"] = float(np.mean([rdist(a, b) for a, b in ANTONYMS]))
    out["M2_rhyme_reading_dist"] = float(np.mean([rdist(a, b) for a, b in RHYMES]))

    out["M3_order"] = [(a, b, jacc_dist(varna_keys(a), varna_keys(b)), rdist(a, b)) for a, b in ORDER]

    pairs = [(a, b) for g in SYNONYMS for a, b in itertools.combinations(g, 2)] + ANTONYMS + RHYMES
    xs = [jacc_dist(varna_keys(a), varna_keys(b)) for a, b in pairs]
    ys = [rdist(a, b) for a, b in pairs]
    out["M5_corr_varna_reading"] = float(np.corrcoef(xs, ys)[0, 1])
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2, default=str))
