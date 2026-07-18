"""Tests for EXPERIMENTAL vowel positional polarity — NO MODEL, NO GENERATION, NO SCORING, NO NETWORK.

These tests validate CODE/DATA BEHAVIOR ONLY — that the opt-in `positional_polarity` vowel mode reads
the correct vowel poles directly from lexicon_authoritative.json, that the default `field_only` mode is
preserved byte-for-byte, and that consonants / synthesize() / L3 / L4 / L5 default outputs are
unchanged. They do NOT validate semantic truth, ontology, Sanskrit privilege, generation utility, Track
B, or Track G. Structure, not validated meaning.

Hermetic: patches the g2p function (fixtures captured once from cmudict) so no nltk is needed.

    python3 varna_lens/test_vowel_positional_polarity.py
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                               # noqa: E402  (g2p + lexicon live here)
import sample_text_rule_harness as H                 # noqa: E402
import layer3_dictionary_bridge as L3                # noqa: E402
import layer4_attribute_check as L4                  # noqa: E402
import generation_conditioning_prompt_demo as G      # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# fixtures captured once from real cmudict -> hermetic, no nltk needed
_FAKE = {
    "anger": [("V", "a", "AE1"), ("C", "nga", "NG"), ("C", "ga", "G"), ("V", "a", "ER0")],
    "under": [("V", "a", "AH1"), ("C", "nna", "N"), ("C", "dda", "D"), ("V", "a", "ER0")],
    "over":  [("V", "o", "OW1"), ("C", "va", "V"), ("V", "a", "ER0")],
    "love":  [("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")],
    "mercy": [("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")],
    "peace": [("C", "pa", "P"), ("V", "ii", "IY1"), ("C", "sa", "S")],
}
_VOWEL_INITIAL = ("anger", "under", "over")
_CONS_INITIAL = ("love", "mercy", "peace")


def _fake(word):
    u = _FAKE.get(word.lower())
    return (u, []) if u is not None else ([], [f"'{word}' not in cmudict"])


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


def _lex_vowel(key):
    return V.LEX["vowels"][key]


# ---------------------------------------------------------------- default preserved -
def test_default_is_field_only_and_vowels_are_field():
    def run():
        pf = H.profile("anger")                      # default (no vowel_mode arg)
        pf2 = H.profile("anger", vowel_mode="field_only")
        return pf, pf2
    pf, pf2 = _with_fake(run)
    _check("default profile == explicit field_only",
           [(r["role"], r["pole"], r["term"]) for r in pf["units"]] ==
           [(r["role"], r["pole"], r["term"]) for r in pf2["units"]])
    _check("default: every vowel is FIELD",
           all(r["role"] == "FIELD" for r in pf["units"] if r["type"] == "V"))
    _check("default: no VOWEL_SEED anywhere",
           not any(r["role"] == "VOWEL_SEED" for r in pf["units"]))


def test_default_vowel_term_is_liberating_state():
    pf = _with_fake(lambda: H.profile("anger", vowel_mode="field_only"))
    v0 = pf["units"][0]
    _check("default vowel term == lexicon liberating_state",
           v0["term"] == H._gloss(_lex_vowel("a")["liberating_state"]))


def test_love_l2_byte_identical_default():
    syn = _with_fake(lambda: H.synthesize(H.profile("love"))[0])
    _check("love L2 synthesis byte-identical (default)",
           syn == "separative harshness moves toward compassion/gentleness, "
                  "and order/dharmic relation is the resolving principle")


# ---------------------------------------------------------------- positional variant
def test_vowel_initial_gets_vowel_seed_binding_from_json():
    for w in _VOWEL_INITIAL:
        pf = _with_fake(lambda w=w: H.profile(w, vowel_mode="positional_polarity"))
        v0 = pf["units"][0]
        _check(f"{w}: index-0 vowel role == VOWEL_SEED", v0["role"] == "VOWEL_SEED")
        _check(f"{w}: index-0 pole == worldly(binding)", v0["pole"] == "worldly(binding)")
        _check(f"{w}: index-0 term == lexicon binding_state (read from JSON)",
               v0["term"] == H._gloss(_lex_vowel(v0["key"])["binding_state"]))


def test_later_vowels_remain_field_liberating_in_positional():
    # 'anger' fixture has a second vowel at index 3
    pf = _with_fake(lambda: H.profile("anger", vowel_mode="positional_polarity"))
    later_vowels = [r for r in pf["units"] if r["type"] == "V" and r["i"] != 0]
    _check("anger has a non-initial vowel", len(later_vowels) >= 1)
    for r in later_vowels:
        _check(f"non-initial vowel idx{r['i']} stays FIELD", r["role"] == "FIELD")
        _check(f"non-initial vowel idx{r['i']} pole == active_essence(liberating)",
               r["pole"] == "active_essence(liberating)")
        _check(f"non-initial vowel idx{r['i']} term == lexicon liberating_state",
               r["term"] == H._gloss(_lex_vowel(r["key"])["liberating_state"]))


def test_consonants_unchanged_across_modes():
    for w in _VOWEL_INITIAL + _CONS_INITIAL:
        def run(w=w):
            pf = H.profile(w, vowel_mode="field_only")
            pp = H.profile(w, vowel_mode="positional_polarity")
            return pf, pp
        pf, pp = _with_fake(run)
        cf = [(r["role"], r["pole"], r["term"]) for r in pf["units"] if r["type"] == "C"]
        cp = [(r["role"], r["pole"], r["term"]) for r in pp["units"] if r["type"] == "C"]
        _check(f"{w}: consonant rows identical across modes", cf == cp)


def test_consonant_initial_words_identical_across_modes():
    for w in _CONS_INITIAL:
        def run(w=w):
            pf = H.profile(w, vowel_mode="field_only")
            pp = H.profile(w, vowel_mode="positional_polarity")
            return pf, pp
        pf, pp = _with_fake(run)
        _check(f"{w}: full profile identical across modes (no word-initial vowel)",
               [(r["role"], r["pole"], r["term"]) for r in pf["units"]] ==
               [(r["role"], r["pole"], r["term"]) for r in pp["units"]])


def test_synthesize_identical_across_modes():
    for w in _VOWEL_INITIAL + _CONS_INITIAL:
        def run(w=w):
            sf = H.synthesize(H.profile(w, vowel_mode="field_only"))[0]
            sp = H.synthesize(H.profile(w, vowel_mode="positional_polarity"))[0]
            return sf, sp
        sf, sp = _with_fake(run)
        _check(f"{w}: L2 synthesis identical across modes (synthesize unaffected)", sf == sp)


# ---------------------------------------------------------------- guards ------------
def test_unknown_vowel_mode_raises():
    try:
        _with_fake(lambda: H.profile("love", vowel_mode="banana"))
    except ValueError as e:
        _check("unknown vowel_mode -> ValueError", "unknown vowel_mode" in str(e)); return
    _check("unknown vowel_mode -> ValueError", False)


def test_experimental_label_only_in_positional_mode():
    out_default = _with_fake(lambda: H.render(text="anger", g2p=True))
    out_pos = _with_fake(lambda: H.render(text="anger", g2p=True, vowel_mode="positional_polarity"))
    _check("experimental label absent in field_only render", H.VOWEL_POSITIONAL_LABEL not in out_default)
    _check("experimental label present in positional render", H.VOWEL_POSITIONAL_LABEL in out_pos)
    _check("VOWEL_SEED shown in positional render", "VOWEL_SEED" in out_pos)
    _check("VOWEL_SEED absent in field_only render", "VOWEL_SEED" not in out_default)


def test_no_spelling_or_roman_fallback_used():
    def guard(*_a, **_k):
        raise AssertionError("FALLBACK CALLED")
    saved = (V.phonemes_roman, V.phonemes_hybrid, V.auto_phonemes)
    V.phonemes_roman = guard; V.phonemes_hybrid = guard; V.auto_phonemes = guard
    try:
        out = _with_fake(lambda: H.render(text="anger", g2p=True, mode="raw",
                                          vowel_mode="positional_polarity"))
        _check("no roman/hybrid/auto fallback under positional mode", "EXPLORATORY_SAMPLE_ONLY" in out)
    finally:
        V.phonemes_roman, V.phonemes_hybrid, V.auto_phonemes = saved


def test_missing_pole_marked_not_invented():
    # a vowel key not in the lexicon -> entry missing -> MISSING (never invented), in positional mode
    V.phonemes_cmudict = lambda w: ([("V", "zz_notavowel", "AH1"), ("C", "va", "V")], [])
    try:
        pf = H.profile("zz", vowel_mode="positional_polarity")
        _check("missing word-initial vowel entry -> term MISSING", pf["units"][0]["term"] == "MISSING")
        _check("missing word-initial vowel still labeled VOWEL_SEED", pf["units"][0]["role"] == "VOWEL_SEED")
    finally:
        V.phonemes_cmudict = _fake


# ---------------------------------------------------------------- downstream default
def test_l3_l4_l5_default_outputs_unchanged():
    def run():
        return (L3.render_layer3("love"), L4.render_layer4("love"),
                G.render_demo("Write a gentle message about love.", "love"))
    l3a, l4a, l5a = _with_fake(run)
    l3b, l4b, l5b = _with_fake(run)
    _check("L3 default output deterministic/unchanged", l3a == l3b)
    _check("L4 default output deterministic/unchanged", l4a == l4b)
    _check("L5 default demo deterministic/unchanged", l5a == l5b)
    # they must not carry the experimental vowel label (default path never enables it)
    for name, out in (("L3", l3a), ("L4", l4a), ("L5", l5a)):
        _check(f"{name} default output has no VOWEL_SEED", "VOWEL_SEED" not in out)
        _check(f"{name} default output has no experimental vowel label",
               H.VOWEL_POSITIONAL_LABEL not in out)


def test_lexicon_unchanged():
    before = (HERE / "lexicon_authoritative.json").read_bytes()
    _with_fake(lambda: [H.profile(w, vowel_mode="positional_polarity") for w in _VOWEL_INITIAL])
    _check("lexicon_authoritative.json unchanged",
           (HERE / "lexicon_authoritative.json").read_bytes() == before)


def test_no_result_files_written():
    before = set(p.name for p in HERE.iterdir())
    _with_fake(lambda: H.render(text="anger", g2p=True, vowel_mode="positional_polarity"))
    _check("no files written", set(p.name for p in HERE.iterdir()) == before)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("vowel_positional_polarity — experimental variant tests (no model, no scoring, no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll vowel positional-polarity tests passed.")


if __name__ == "__main__":
    main()
