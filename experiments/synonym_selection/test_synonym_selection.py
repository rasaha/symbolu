"""Synthetic tests for the synonym-selection scaffolding (NO real fit, no network).

Verifies the MACHINERY only: g2p→varṇa via the frozen map, equal-weight consonant-only
composition, cosine selection, the scrambled-table null discriminating signal from noise,
the homophone-invariance leakage check, and the frequency-baseline interface. Candidate
sets / targets / ground truth are all SYNTHETIC. No semantic claim is made.

    python3 experiments/synonym_selection/test_synonym_selection.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))          # local modules
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))      # common/
from g2p import g2p_word, arpabet_to_varnas, ARPA_C, ARPA_V                # noqa: E402
from lexicon import load_readings, vocab_index                            # noqa: E402
import selection as S                                                     # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# tiny SYNTHETIC cmudict: spelling -> ARPABET (note two spellings share phones = homophones)
SYN_CMU = {
    "cat":  ["K", "AE1", "T"],
    "kat":  ["K", "AE1", "T"],     # homophone of "cat" (different spelling, same sound)
    "dog":  ["D", "AO1", "G"],
    "rat":  ["R", "AE1", "T"],
    "tar":  ["T", "AA1", "R"],
}

# tiny SYNTHETIC reading map over a SYNTHETIC vocabulary (NOT the real lexicon)
SYN_MAP = {"ka": "alpha", "tta": "beta", "dda": "gamma", "ga": "delta",
           "ra": "epsilon", "va": "zeta", "la": "eta", "sa": "theta"}
SYN_VOCAB = sorted(set(SYN_MAP.values()))
SYN_VIDX = {l: i for i, l in enumerate(SYN_VOCAB)}


def test_g2p_frozen_map():
    seq, warn = g2p_word("cat", SYN_CMU)
    _check("g2p cat -> [C ka, V a, C tta]", seq == [("C", "ka"), ("V", "a"), ("C", "tta")])
    _check("g2p no warnings on cat", warn == [])
    # frozen dialect rule: English T -> retroflex tta (not dental ta)
    _check("frozen rule: ARPABET T -> tta (retroflex)", ARPA_C["T"] == "tta")
    _check("frozen rule: ARPABET TH -> ta (dental)", ARPA_C["TH"] == "ta")


def test_profile_equal_weight_consonant_only():
    seq, _ = g2p_word("cat", SYN_CMU)                 # ka, a, tta
    p = S.profile(seq, SYN_MAP, SYN_VIDX)
    _check("profile dim == vocab size", p.shape[0] == len(SYN_VOCAB))
    _check("vowel excluded; only ka,tta counted", p.sum() == 2.0)
    _check("equal weight: ka=1", p[SYN_VIDX["alpha"]] == 1.0)
    _check("equal weight: tta=1", p[SYN_VIDX["beta"]] == 1.0)
    # repeated consonant counts twice (equal weight, no decay)
    seq2 = [("C", "ka"), ("C", "ka")]
    _check("repeat consonant -> count 2", S.profile(seq2, SYN_MAP, SYN_VIDX)[SYN_VIDX["alpha"]] == 2.0)


def test_cosine_selection_planted():
    # three candidates; target aligned to candidate 1's profile -> candidate 1 selected
    seqs = [g2p_word("dog", SYN_CMU)[0], g2p_word("cat", SYN_CMU)[0], g2p_word("tar", SYN_CMU)[0]]
    profs = [S.profile(s, SYN_MAP, SYN_VIDX) for s in seqs]
    target = profs[1].copy()
    _check("selection picks the aligned candidate", S.select(profs, target) == 1)


def test_scrambled_null_discriminates():
    # PLANTED: target == the truth candidate's real profile -> real accuracy = 1, scrambled ~ chance
    words = ["dog", "cat", "tar", "rat"]
    seqs = [g2p_word(w, SYN_CMU)[0] for w in words]
    sets = [seqs, seqs, seqs]                          # 3 sets, same 4 candidates
    truth = [0, 1, 2]                                  # different truth per set
    targets = [S.profile(seqs[t], SYN_MAP, SYN_VIDX) for t in truth]
    real = S.selection_accuracy(sets, targets, truth, SYN_MAP, SYN_VIDX)
    null = S.scrambled_null(sets, targets, truth, SYN_MAP, SYN_VIDX, n_scramble=200, seed=1)
    _check("planted: real accuracy = 1.0", real == 1.0)
    _check("planted: real > scrambled mean", real > null.mean())
    _check("planted: real > scrambled 95th pct", real > np.percentile(null, 95))

    # NULL: random targets unrelated to candidates -> real ~ scrambled (no advantage)
    rng = np.random.default_rng(7)
    rnd_targets = [rng.standard_normal(len(SYN_VOCAB)) for _ in sets]
    real0 = S.selection_accuracy(sets, rnd_targets, truth, SYN_MAP, SYN_VIDX)
    null0 = S.scrambled_null(sets, rnd_targets, truth, SYN_MAP, SYN_VIDX, n_scramble=200, seed=2)
    _check("null: real not above scrambled 95th pct", real0 <= np.percentile(null0, 95) + 1e-9)


def test_homophone_invariance_leakage_check():
    # "cat" and "kat" share ARPABET -> identical profile (sound only, no spelling leak)
    ok = S.homophone_invariant("cat", "kat", SYN_CMU, SYN_MAP, SYN_VIDX)
    _check("homophones get identical profiles (no orthographic leak)", ok is True)
    # different-sounding words must NOT be invariant (sanity)
    diff = S.homophone_invariant("cat", "dog", SYN_CMU, SYN_MAP, SYN_VIDX)
    _check("non-homophones differ (control)", diff is False)


def test_frequency_baseline_interface():
    cands = ["dog", "cat", "tar"]
    _check("freq baseline picks max (dict)", S.frequency_baseline(cands, {"dog": 1, "cat": 9, "tar": 3}) == 1)
    _check("freq baseline picks max (callable)",
           S.frequency_baseline(cands, lambda w: {"dog": 5, "cat": 2, "tar": 1}[w]) == 0)


def test_scramble_determinism():
    a = S.scramble_reading_map(SYN_MAP, 5)
    b = S.scramble_reading_map(SYN_MAP, 5)
    _check("scramble deterministic by seed", a == b)
    _check("scramble preserves label set", sorted(a.values()) == sorted(SYN_MAP.values()))


def test_real_lexicon_loads():
    # loads the curated table (NOT a fit; just verifies the loader + space dimension)
    cons, vow, vocab = load_readings()
    _check("lexicon: 34 consonants", len(cons) == 34)
    _check("lexicon: 12 vowels", len(vow) == 12)
    _check("lexicon: consonant reading vocab non-empty", len(vocab) > 0)
    # spot-check a flip is present in the curated table (ca -> aviveka, not viveka)
    _check("curated table used (ca binding = lack of discrimination)",
           "discrimination" in cons["ca"].lower())


def main():
    print("synonym_selection scaffolding — synthetic tests (no real fit, no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll synonym_selection scaffolding tests passed.")


if __name__ == "__main__":
    main()
