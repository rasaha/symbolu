#!/usr/bin/env python3
"""Stage A′ — coverage-only harness (repo-local pools only).

A SEPARATE, VERSIONED substitute L1 front end (NOT the frozen Stage A). It replaces the
raw 14-grapheme chart with a language-aware phoneme/transliteration normalizer + a broader
phoneme inventory, preserving the structural principle  M_σ = expm(Σ_j f_{σ,j} G_j).

Scope (pre-registration PREREG_STAGE_A_PRIME_COVERAGE_ONLY.md): COVERAGE ONLY. This computes
decomposition coverage, constructs operators, and runs operator-sanity + a semantic-leakage
audit. It does NOT touch frozen Stage A, does NOT use any Y / attribute / gloss data, runs NO
F-3 and NO semantic scoring, and declares NO semantic signal.

Inputs are PHONOLOGICAL/ARTICULATORY ONLY. Since no independent Y concept list exists yet,
this can only report a REPO-LOCAL coverage pass with Y_OVERLAP_PENDING — never a full final
Stage A′ pass.

Run:  python3 stage_a_prime_coverage.py
"""
from __future__ import annotations

import json
import pathlib
from typing import Dict, List, Tuple

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent

# terminal labels (must match the pre-registration)
LABELS = (
    "STAGE_A_PRIME_COVERAGE_PASS",
    "STAGE_A_PRIME_COVERAGE_FAIL",
    "STAGE_A_PRIME_OPERATOR_SANITY_PASS",
    "STAGE_A_PRIME_OPERATOR_SANITY_FAIL",
    "STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID",
    "STAGE_A_PRIME_INCONCLUSIVE",
)

# coverage targets (Y-independent subset; the >=100-concepts-overlapping-Y target is PENDING)
RETENTION_TARGET = 0.95
FULL_WORD_TARGET = 0.90

# =====================================================================================
# Phoneme inventory: name -> 4-dim ARTICULATORY vector (place, manner, voicing, sonority),
# each in [-1, 1]. PHONOLOGICAL ONLY — no meaning, no gloss, no attribute.
#   place_frontness : labial/front (-1) ... velar/back/glottal (+1)
#   manner_openness : stop (-1) ... fricative ... approximant ... vowel (+1)
#   voicing         : voiceless (-1) ... voiced (+1)
#   sonority        : low (-1) ... high (+1)
# =====================================================================================
PHONEMES: Dict[str, Tuple[float, float, float, float]] = {
    # stops
    "p": (-1.0, -1.0, -1.0, -0.8), "b": (-1.0, -1.0, +1.0, -0.6),
    "t": (-0.2, -1.0, -1.0, -0.8), "d": (-0.2, -1.0, +1.0, -0.6),
    "k": (+1.0, -1.0, -1.0, -0.8), "g": (+1.0, -1.0, +1.0, -0.6),
    "tr": (+0.4, -1.0, -1.0, -0.8), "dr": (+0.4, -1.0, +1.0, -0.6),   # retroflex ṭ/ḍ
    # affricates
    "ch": (-0.1, -0.6, -1.0, -0.4), "jh": (-0.1, -0.6, +1.0, -0.2),
    # fricatives
    "f": (-0.9, +0.2, -1.0, -0.1), "v": (-0.9, +0.2, +1.0, +0.1),
    "th": (-0.3, +0.2, -1.0, -0.1), "dh": (-0.3, +0.2, +1.0, +0.1),
    "s": (-0.2, +0.2, -1.0, -0.1), "z": (-0.2, +0.2, +1.0, +0.1),
    "sh": (0.0, +0.2, -1.0, 0.0), "zh": (0.0, +0.2, +1.0, +0.1),
    "shr": (+0.4, +0.2, -1.0, -0.05),                                  # retroflex ṣ
    "h": (+1.0, +0.3, -1.0, 0.0),
    # nasals
    "m": (-1.0, +0.4, +1.0, +0.3), "n": (-0.2, +0.4, +1.0, +0.3),
    "nr": (+0.4, +0.4, +1.0, +0.3), "ng": (+1.0, +0.4, +1.0, +0.3),
    "ny": (-0.05, +0.4, +1.0, +0.3),
    # liquids / glides
    "r": (-0.1, +0.7, +1.0, +0.6), "l": (-0.3, +0.7, +1.0, +0.6),
    "y": (-0.7, +0.8, +1.0, +0.7), "w": (-0.9, +0.8, +1.0, +0.7),
    # vowels
    "a": (+0.6, +1.0, +1.0, +1.0), "aa": (+0.6, +1.0, +1.0, +1.0),
    "i": (-0.9, +0.8, +1.0, +1.0), "ii": (-0.9, +0.8, +1.0, +1.0),
    "u": (+0.9, +0.9, +1.0, +1.0), "uu": (+0.9, +0.9, +1.0, +1.0),
    "e": (-0.6, +0.9, +1.0, +1.0), "o": (+0.7, +0.9, +1.0, +1.0),
    "ax": (0.0, +0.9, +1.0, +0.9),                                     # schwa
    "rv": (-0.1, +0.85, +1.0, +0.8),                                   # vocalic ṛ
}
FEATURE_NAMES = ("place_frontness", "manner_openness", "voicing", "sonority")
K = 4


def _rules(pairs: Dict[str, List[str]]) -> List[Tuple[str, List[str]]]:
    # longest source first so digraphs/diacritics win over single chars
    return sorted(pairs.items(), key=lambda kv: -len(kv[0]))


# ---- A_PRIME_SA : IAST/transliteration normalizer (diacritics + aspirated digraphs) ----
_SA_RULES = _rules({
    # aspirated stops -> base + h feature carried by 'h' phoneme (aspiration as a segment)
    "kh": ["k", "h"], "gh": ["g", "h"], "ch": ["ch"], "chh": ["ch", "h"],
    "jh": ["jh"], "ṭh": ["tr", "h"], "ḍh": ["dr", "h"], "th": ["th"], "dh": ["dh"],
    "ph": ["p", "h"], "bh": ["b", "h"],
    # retroflex / palatal / nasals with diacritics
    "ṭ": ["tr"], "ḍ": ["dr"], "ṇ": ["nr"], "ṅ": ["ng"], "ñ": ["ny"],
    "ś": ["sh"], "ṣ": ["shr"], "ṃ": ["m"], "ḥ": ["h"],
    # vowels (long via diacritics, vocalic r)
    "ā": ["aa"], "ī": ["ii"], "ū": ["uu"], "ṛ": ["rv"], "ṝ": ["rv"],
    "ai": ["a", "i"], "au": ["a", "u"], "e": ["e"], "o": ["o"],
    "a": ["a"], "i": ["i"], "u": ["u"],
    # plain consonants
    "c": ["ch"], "j": ["jh"], "y": ["y"], "v": ["v"], "r": ["r"], "l": ["l"],
    "k": ["k"], "g": ["g"], "t": ["t"], "d": ["d"], "p": ["p"], "b": ["b"],
    "m": ["m"], "n": ["n"], "s": ["s"], "h": ["h"],
})

# ---- A_PRIME_EN : rule-based English G2P (coverage-oriented; every letter maps) ----
_EN_RULES = _rules({
    # common digraphs
    "tch": ["ch"], "sch": ["s", "k"],
    "ch": ["ch"], "sh": ["sh"], "th": ["th"], "ph": ["f"], "wh": ["w"],
    "ck": ["k"], "ng": ["ng"], "qu": ["k", "w"], "gh": ["g"],
    "oo": ["uu"], "ee": ["ii"], "ea": ["ii"], "ou": ["a", "u"], "ow": ["o"],
    "ai": ["e"], "ay": ["e"], "oa": ["o"], "oi": ["o", "i"], "oy": ["o", "i"],
    # single letters (every ASCII letter covered -> no silent drop)
    "a": ["a"], "b": ["b"], "c": ["k"], "d": ["d"], "e": ["e"], "f": ["f"],
    "g": ["g"], "h": ["h"], "i": ["i"], "j": ["jh"], "k": ["k"], "l": ["l"],
    "m": ["m"], "n": ["n"], "o": ["o"], "p": ["p"], "q": ["k"], "r": ["r"],
    "s": ["s"], "t": ["t"], "u": ["u"], "v": ["v"], "w": ["w"], "x": ["k", "s"],
    "y": ["y"], "z": ["z"], "'": [], "-": [],
})

TRACKS = {"A_PRIME_EN": _EN_RULES, "A_PRIME_SA": _SA_RULES}


# =====================================================================================
# Normalizer: longest-match tokenizer. NO SILENT FALLBACK — unmatched chars are reported.
# =====================================================================================
def normalize(word: str, track: str) -> Dict:
    rules = TRACKS[track]
    w = word.strip().lower()
    i = 0
    phonemes: List[str] = []
    unsupported: List[str] = []
    consumed = 0
    total = sum(1 for c in w if not c.isspace())
    while i < len(w):
        c = w[i]
        if c.isspace():
            i += 1
            continue
        hit = None
        for src, ph in rules:
            if src and w.startswith(src, i):
                hit = (src, ph)
                break
        if hit is not None:
            phonemes.extend(hit[1])
            consumed += len(hit[0])
            i += len(hit[0])
        else:
            unsupported.append(c)     # reported, never silently dropped
            i += 1
    # every emitted phoneme must be in the inventory (else it's a rule bug, not coverage)
    for p in phonemes:
        if p not in PHONEMES:
            raise ValueError(f"rule emitted unknown phoneme {p!r} for {word!r}")
    retention = (consumed / total) if total else 0.0
    if not phonemes:
        flag = "empty"
    elif unsupported:
        flag = "partial"
    else:
        flag = "full"
    return {"word": word, "track": track, "phonemes": phonemes,
            "unsupported": unsupported, "retention": retention, "flag": flag}


# =====================================================================================
# Operators: local skew generators (Stage A form, redefined here — frozen Stage A NOT imported).
# M_σ = expm(Σ_j f_{σ,j} G_j), orthogonal because generators are skew-symmetric.
# =====================================================================================
def _kron(a, b):
    return np.kron(a, b)


_I2 = np.eye(2)
_J = np.array([[0.0, -1.0], [1.0, 0.0]])
_Z = np.array([[1.0, 0.0], [0.0, -1.0]])
_X = np.array([[0.0, 1.0], [1.0, 0.0]])
GENERATORS = [_kron(_J, _I2), _kron(_I2, _J), _kron(_J, _Z), _kron(_X, _J)]  # all skew 4x4


def expm(A: np.ndarray, terms: int = 20) -> np.ndarray:
    # scaling-and-squaring Taylor series (sufficient for bounded skew inputs)
    norm = np.linalg.norm(A, np.inf)
    s = max(0, int(np.ceil(np.log2(norm + 1e-12))))
    B = A / (2 ** s)
    out = np.eye(A.shape[0]); term = np.eye(A.shape[0])
    for n in range(1, terms + 1):
        term = term @ B / n
        out = out + term
    for _ in range(s):
        out = out @ out
    return out


def phoneme_operator(ph: str) -> np.ndarray:
    f = np.array(PHONEMES[ph], dtype=float)
    A = sum(f[j] * GENERATORS[j] for j in range(K))
    return expm(A)


def operator_sequence(phonemes: List[str]) -> List[np.ndarray]:
    return [phoneme_operator(p) for p in phonemes]


# =====================================================================================
# Semantic-leakage audit: assert Stage A′ consumes ONLY phonological/articulatory inputs.
# =====================================================================================
FORBIDDEN_INPUT_TERMS = (
    "dictionary_anchor", "gloss", "vrtti", "vṛtti", "four_sphere", "sphere",
    "polarity", "kcpr", "binding", "liberating", "attribute", "sentiment", "valence",
    "y_matrix", "meaning", "definition",
)


def semantic_leakage_audit() -> Dict:
    findings = []
    # (a) feature schema is 4 finite floats in [-1,1], purely articulatory
    for name, vec in PHONEMES.items():
        if len(vec) != K or not all(np.isfinite(vec)) or max(abs(x) for x in vec) > 1.0 + 1e-9:
            findings.append(f"phoneme {name} has non-articulatory / out-of-range features")
    # (b) rule outputs reference only inventory phonemes (no meaning tokens)
    for track, rules in TRACKS.items():
        for src, ph in rules:
            for p in ph:
                if p not in PHONEMES:
                    findings.append(f"{track} rule {src!r} emits non-inventory {p!r}")
    # (c) the module source must not READ any forbidden semantic field as input
    src = pathlib.Path(__file__).read_text()
    # allow the terms only inside this audit's own FORBIDDEN list / comments, not as data reads
    for term in ("dictionary_anchor", "attribute_table", "y_matrix"):
        # a forbidden field must never be indexed/loaded: look for '["term"]' style access
        if f'["{term}"]' in src or f"['{term}']" in src:
            findings.append(f"module reads forbidden field {term!r}")
    ok = not findings
    return {"ok": ok, "findings": findings}


# =====================================================================================
# Pools (repo-local ONLY) + coverage computation.
# =====================================================================================
def load_pool_sanskrit() -> List[str]:
    d = json.loads((HERE / "frozen" / "word_list.json").read_text())
    return [w["spelling"] for w in d["words"] if not w.get("exclude_flag")]


def load_pool_english() -> List[str]:
    d = json.loads((HERE / "b1_3_revised_layer3" /
                    "b1_3_human_modulation_concrete_object_candidate_wordlist.json").read_text())
    # extract ONLY the word field (never dictionary_anchor / meaning fields)
    return [it["word"] for it in d["items"] if "word" in it]


def coverage_for_pool(words: List[str], track: str) -> Dict:
    recs = [normalize(w, track) for w in words]
    n = len(recs)
    full = sum(1 for r in recs if r["flag"] == "full")
    partial = sum(1 for r in recs if r["flag"] == "partial")
    empty = sum(1 for r in recs if r["flag"] == "empty")
    char_ret = float(np.mean([r["retention"] for r in recs])) if recs else 0.0
    unsupported = {}
    for r in recs:
        for c in r["unsupported"]:
            unsupported[c] = unsupported.get(c, 0) + 1
    full_frac = full / n if n else 0.0
    targets_met = (char_ret >= RETENTION_TARGET) and (full_frac >= FULL_WORD_TARGET)
    label = "STAGE_A_PRIME_COVERAGE_PASS" if targets_met else "STAGE_A_PRIME_COVERAGE_FAIL"
    return {"track": track, "n": n, "full": full, "partial": partial, "empty": empty,
            "char_retention": round(char_ret, 4), "full_fraction": round(full_frac, 4),
            "unsupported_counts": dict(sorted(unsupported.items(), key=lambda kv: -kv[1])),
            "targets_met_repo_local": targets_met, "coverage_label": label,
            "y_overlap": "Y_OVERLAP_PENDING"}


# =====================================================================================
# Operator sanity over the full inventory.
# =====================================================================================
def operator_sanity() -> Dict:
    findings = []
    for name in PHONEMES:
        M = phoneme_operator(name)
        M2 = phoneme_operator(name)                       # determinism
        if not np.array_equal(M, M2):
            findings.append(f"{name}: non-deterministic operator")
        if not np.all(np.isfinite(M)):
            findings.append(f"{name}: non-finite / NaN operator")
        if M.shape != (4, 4):
            findings.append(f"{name}: wrong shape {M.shape}")
        if not np.allclose(M @ M.T, np.eye(4), atol=1e-8):
            findings.append(f"{name}: not orthogonal (skew-generator invariant violated)")
    # generators are skew-symmetric
    for j, G in enumerate(GENERATORS):
        if not np.allclose(G, -G.T, atol=1e-12):
            findings.append(f"generator {j} not skew-symmetric")
    ok = not findings
    return {"ok": ok, "findings": findings,
            "label": "STAGE_A_PRIME_OPERATOR_SANITY_PASS" if ok else "STAGE_A_PRIME_OPERATOR_SANITY_FAIL"}


def run_all() -> Dict:
    leak = semantic_leakage_audit()
    if not leak["ok"]:
        return {"overall": "STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID", "leakage": leak}
    sanity = operator_sanity()
    pools = {
        "sanskrit_A_PRIME_SA": coverage_for_pool(load_pool_sanskrit(), "A_PRIME_SA"),
        "english_A_PRIME_EN": coverage_for_pool(load_pool_english(), "A_PRIME_EN"),
    }
    cov_pass = all(p["targets_met_repo_local"] for p in pools.values())
    return {
        "leakage": leak,
        "operator_sanity": sanity,
        "pools": pools,
        # repo-local coverage only; Y-overlap target is PENDING -> never a full final pass
        "repo_local_coverage_label": ("STAGE_A_PRIME_COVERAGE_PASS" if cov_pass
                                      else "STAGE_A_PRIME_COVERAGE_FAIL"),
        "y_overlap": "Y_OVERLAP_PENDING",
        "final_pass": False,   # cannot be a full Stage A′ pass without independent Y overlap
    }


if __name__ == "__main__":
    import pprint
    res = run_all()
    pprint.pp(res)
    print("\nNOTE: repo-local coverage only; Y_OVERLAP_PENDING -> NOT a full final Stage A′ pass.")
    print("No Y, no F-3, no semantic scoring. Frozen Stage A untouched. Track B blocked.")
