"""Core machinery for the synonym-selection pilot (scaffolding; no real fit).

Confirmatory composition (per PREREG_SYNONYM_SELECTION.md §1):
  - EQUAL-WEIGHT, CONSONANT-ONLY profile in the consonant-reading vocabulary.
  - no positional decay, no vowels, no transitions (those are exploratory, not here).

Also provides: cosine selection, scrambled-table null, frequency-baseline interface,
and a homophone-invariance leakage check. All operate on synthetic inputs in tests;
nothing here runs on real synonym data or makes a semantic claim.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats  # noqa: E402  (rng, percentile_gate, permutation_pvalue, bootstrap_ci)


# ---------------------------------------------------------------- composition --
def profile(varna_seq, reading_map, vidx) -> np.ndarray:
    """EQUAL-WEIGHT, CONSONANT-ONLY count vector over the reading vocabulary.

    varna_seq   : [(type,key)] from g2p (vowels ignored — confirmatory is consonant-only)
    reading_map : consonant key -> reading label
    vidx        : reading label -> index
    """
    vec = np.zeros(len(vidx))
    for t, key in varna_seq:
        if t != "C":
            continue
        label = reading_map.get(key)
        if label in vidx:
            vec[vidx[label]] += 1.0          # equal weight (no positional decay)
    return vec


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a, b = _unit(a), _unit(b)
    return float(a @ b)


# ---------------------------------------------------------------- selection ----
def select(cand_profiles, target) -> int:
    """Index of the candidate whose profile is closest (cosine) to the target."""
    sims = [cosine(p, target) for p in cand_profiles]
    return int(np.argmax(sims))


def selection_accuracy(candidate_seqs, targets, truth_idx, reading_map, vidx) -> float:
    """Fraction of sets where the cosine-selected candidate == the ground-truth index.

    candidate_seqs : list of sets; each set = list of varṇa-seqs (one per candidate word)
    targets        : list of target vectors (in the reading vocabulary)
    truth_idx      : list of ground-truth preferred-realization indices
    """
    correct = 0
    for seqs, tgt, truth in zip(candidate_seqs, targets, truth_idx):
        profs = [profile(s, reading_map, vidx) for s in seqs]
        if select(profs, tgt) == truth:
            correct += 1
    return correct / len(truth_idx) if truth_idx else 0.0


# ---------------------------------------------------------------- scramble null -
def scramble_reading_map(reading_map, seed) -> dict:
    """Permute which consonant key gets which reading label (labels set unchanged)."""
    keys = list(reading_map)
    labels = [reading_map[k] for k in keys]
    perm = stats.rng(seed).permutation(len(labels))
    return {keys[i]: labels[perm[i]] for i in range(len(keys))}


def scrambled_null(candidate_seqs, targets, truth_idx, reading_map, vidx,
                   n_scramble=1000, seed=0):
    """Accuracy distribution under n_scramble permuted reading maps (real map untouched)."""
    rng = stats.rng(seed)
    seeds = rng.integers(0, 2**31 - 1, size=n_scramble)
    return np.array([
        selection_accuracy(candidate_seqs, targets, truth_idx,
                            scramble_reading_map(reading_map, int(s)), vidx)
        for s in seeds
    ])


# ---------------------------------------------------------------- baselines ----
def frequency_baseline(candidate_words, freq_lookup) -> int:
    """Interface/placeholder: index of the most frequent candidate.

    freq_lookup : dict word->count OR callable word->count. Real frequency data is NOT
    bundled here; this is the interface the frozen pre-registered run will supply.
    """
    def f(w):
        return freq_lookup(w) if callable(freq_lookup) else freq_lookup.get(w, 0)
    return int(np.argmax([f(w) for w in candidate_words]))


# ---------------------------------------------------------------- leakage check -
def homophone_invariant(word_a, word_b, cmudict, reading_map, vidx) -> bool:
    """Leakage check: two words with IDENTICAL g2p must get IDENTICAL profiles.

    If this ever returns False for a true homophone pair, orthography has leaked into
    a supposedly sound-only pipeline → the run is invalid (PREREG §7).
    """
    from g2p import g2p_word
    sa, _ = g2p_word(word_a, cmudict)
    sb, _ = g2p_word(word_b, cmudict)
    return np.array_equal(profile(sa, reading_map, vidx), profile(sb, reading_map, vidx))
