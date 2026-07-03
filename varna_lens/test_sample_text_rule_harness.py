"""Tests for the exploratory G2P varṇa-process sample renderer — NO MODEL, NO SCORING, NO NETWORK.

Uses a monkeypatched g2p function (fixed unit lists) so the tests are hermetic and deterministic —
they do NOT depend on nltk/cmudict being installed. Proves: G2P hard-aborts when unavailable or the
word is missing; no roman/hybrid/auto fallback is ever called under --g2p; every output carries the
EXPLORATORY_SAMPLE_ONLY banner; no forbidden bridge/score phrases appear; the user label is printed
only as USER_LABEL_NOT_USED; no scoring fields are emitted; missing units and approximate mapping are
marked.

    python3 varna_lens/test_sample_text_rule_harness.py
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                       # noqa: E402
import sample_text_rule_harness as S         # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# fixed g2p outputs (varṇa keys from the committed lexicon) — no nltk needed
_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "like": ([("C", "la", "L"), ("V", "ai", "AY1"), ("C", "ka", "K")], []),
    "mantra": ([("C", "ma", "M"), ("V", "a", "AE1"), ("C", "na", "N"),
                ("C", "ta", "T"), ("C", "ra", "R"), ("V", "a", "AH0")], []),
}


def _fake_cmudict(word):
    if word.lower() in _FAKE:
        return _FAKE[word.lower()]
    return [], [f"'{word}' not in cmudict"]        # triggers hard abort


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake_cmudict
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


# ------------------------------------------------------------- hard-abort tests -----
def test_g2p_abort_when_nltk_missing():
    def boom(_w):
        raise ModuleNotFoundError("No module named 'nltk'")
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = boom
    try:
        S.g2p_units("love")
    except S.G2PUnavailable as e:
        _check("nltk missing -> G2P_UNAVAILABLE abort", "G2P_UNAVAILABLE" in str(e)); return
    finally:
        V.phonemes_cmudict = orig
    _check("nltk missing -> G2P_UNAVAILABLE abort", False)


def test_g2p_abort_when_word_missing():
    def run():
        try:
            S.g2p_units("zzqxwv")
        except S.G2PUnavailable as e:
            return "G2P_UNAVAILABLE" in str(e) and "no roman" in str(e).lower()
        return False
    _check("word not in cmudict -> abort, no roman fallback", _with_fake(run))


def test_no_g2p_flag_aborts():
    try:
        S.render(text="love", g2p=False)
    except S.G2PUnavailable as e:
        _check("g2p=False -> abort (no fallback)", "G2P-only" in str(e) or "G2P_UNAVAILABLE" in str(e)); return
    _check("g2p=False -> abort (no fallback)", False)


def test_no_roman_or_hybrid_fallback_called():
    # if the harness ever calls roman/hybrid/auto, these explode -> test fails
    def guard(*_a, **_k):
        raise AssertionError("FALLBACK CALLED")
    saved = (V.phonemes_roman, V.phonemes_hybrid, V.auto_phonemes)
    V.phonemes_roman = guard; V.phonemes_hybrid = guard; V.auto_phonemes = guard
    try:
        out = _with_fake(lambda: S.render(text="love", g2p=True))
        _check("no roman/hybrid/auto fallback under --g2p", "EXPLORATORY_SAMPLE_ONLY" in out)
    finally:
        V.phonemes_roman, V.phonemes_hybrid, V.auto_phonemes = saved


# ------------------------------------------------------------- output discipline ----
def test_banner_present_all_modes():
    for kw in ({"text": "love", "mode": "word_profile"},
               {"text": "love", "mode": "raw"},
               {"pair": ["like", "love"], "mode": "shared_seed"},
               {"text": "like love", "mode": "phrase"}):
        out = _with_fake(lambda kw=kw: S.render(g2p=True, **kw))
        _check(f"banner present ({kw.get('mode')})", out.count(S.BANNER) >= 2)  # top + bottom


def test_no_forbidden_phrases():
    out = _with_fake(lambda: S.render(text="love", mode="raw", g2p=True,
                                      show_scramble=True, show_random=True)).lower()
    for bad in S.FORBIDDEN:
        _check(f"no forbidden phrase {bad!r}", bad not in out)


def test_label_only_as_user_label_not_used():
    out = _with_fake(lambda: S.render(text="love", g2p=True, label="a warm happy feeling"))
    _check("label rendered only as USER_LABEL_NOT_USED", "USER_LABEL_NOT_USED: a warm happy feeling" in out)
    # the label text must not appear anywhere except on that one line
    occurrences = out.count("a warm happy feeling")
    _check("label appears exactly once (not fed into rule)", occurrences == 1)


def test_no_scoring_fields():
    out = _with_fake(lambda: S.render(pair=["like", "love"], mode="shared_seed", g2p=True,
                                      show_scramble=True, show_random=True)).lower()
    # NB: the mandated banner contains "not scored", so we check emitted-score forms, not the bare root
    for tok in ("score:", "score=", "verdict", "accuracy", "delta ", "a_vs", "p=0", "real is better"):
        _check(f"no scoring token {tok!r}", tok not in out)


def test_missing_unit_marked():
    # inject a unit whose key is not in the lexicon -> must be marked MISSING, not invented
    V.phonemes_cmudict = lambda w: ([("C", "la", "L"), ("C", "zz_notavarna", "ZZ")], [])
    try:
        out = S.render(text="lz", mode="raw", g2p=True)
        _check("missing unit marked MISSING", "MISSING" in out)
    finally:
        V.phonemes_cmudict = _fake_cmudict  # leave a safe default; restored fully below


def test_approx_marked_and_roles_correct():
    out = _with_fake(lambda: S.render(text="mantra", mode="raw", g2p=True))
    _check("approximate mapping marked", "~approx" in out)
    _check("first consonant is ONSET_SEED", "ONSET_SEED" in out)
    _check("last consonant is TRANSFORMER", "TRANSFORMER" in out)
    _check("internal consonant is INTERNAL_UNRESOLVED", "INTERNAL_UNRESOLVED" in out)


def test_shared_seed_detected():
    out = _with_fake(lambda: S.render(pair=["like", "love"], mode="shared_seed", g2p=True))
    _check("shared onset detected", "SHARED_SEED (la)" in out)


def test_display_variants_are_labeled_not_scored():
    out = _with_fake(lambda: S.render(text="love", mode="word_profile", g2p=True,
                                      show_scramble=True, show_random=True))
    _check("scramble labeled display-only", "DISPLAY_ONLY_SCRAMBLE" in out and "NOT scored" in out)
    _check("random labeled display-only", "DISPLAY_ONLY_RANDOM" in out)


def test_no_ml_libs_imported():
    _check("no torch/transformers imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def main():
    print("sample_text_rule_harness — exploratory renderer tests (no model, no scoring, no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll sample-text renderer tests passed.")


if __name__ == "__main__":
    main()
