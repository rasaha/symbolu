"""Tests for the Layer 3 dictionary-meaning bridge — INSPECTION ONLY (no model, no scoring, no network).

Hermetic: patches the g2p function so no nltk/cmudict is needed. Proves: required label top+bottom;
all four relation labels reachable; missing anchor -> UNRESOLVED; unresolved Layer 2 -> UNRESOLVED;
opposite keyword -> DIVERGES; no numeric score fields; no forbidden meaning/truth/ontology claims;
no ML imports; no generated-answer fields; no result files written; Layer 1/Layer 2 output unchanged;
`love` Layer 2 synthesis byte-identical; sibling frozen files (lexicon, bridge vocab, L5 demo) are not
modified by importing/running Layer 3.

    python3 varna_lens/test_layer3_dictionary_bridge.py
"""
from __future__ import annotations

import io
import contextlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                        # noqa: E402  (g2p lives here)
import sample_text_rule_harness as H          # noqa: E402  (Layer 1/2 producer)
import layer3_dictionary_bridge as L3         # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# fixed g2p (captured once from cmudict) -> hermetic, no nltk needed
_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "mercy": ([("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")], []),
    "anger": ([("V", "a", "AE1"), ("C", "nga", "NG"), ("C", "ga", "G"), ("V", "a", "ER0")], []),
    "peace": ([("C", "pa", "P"), ("V", "ii", "IY1"), ("C", "sa", "S")], []),
}


def _fake(word):
    return _FAKE.get(word.lower(), ([], [f"'{word}' not in cmudict"]))


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


# ---------------------------------------------------------------- label discipline --
def test_label_top_and_bottom():
    out = L3.relate  # touch to ensure import ok
    txt = _with_fake(lambda: L3.render_layer3("mercy"))
    _check("required label present top + bottom", txt.count(L3.LABEL) >= 2)
    _check("label is the exact required string",
           L3.LABEL == "LAYER3_DICTIONARY_BRIDGE — interpretive only, not scored, not evidence")


def test_caveat_present():
    txt = _with_fake(lambda: L3.render_layer3("mercy"))
    _check("mandated caveat present", L3.CAVEAT in txt)
    _check("caveat carries NO_SIGNAL prior", "NO_SIGNAL" in txt)


# ---------------------------------------------------------------- four labels -------
def test_all_four_labels_reachable():
    aligns = L3.relate("mercy", "separative restraint moves toward containment")
    _check("ALIGNS reachable (>=2 anchor hits, no opposite)", aligns["relation"] == L3.ALIGNS)
    partial = L3.relate("mercy", "moves toward restraint")
    _check("PARTIALLY_ALIGNS reachable (exactly 1 anchor hit)",
           partial["relation"] == L3.PARTIALLY_ALIGNS)
    diverges = L3.relate("mercy", "cruelty and harshness")
    _check("DIVERGES reachable (opposite term present)", diverges["relation"] == L3.DIVERGES)
    none = L3.relate("mercy", "banana orange grapefruit")
    _check("UNRESOLVED reachable (no overlap)", none["relation"] == L3.UNRESOLVED)


def test_missing_anchor_unresolved():
    r = L3.relate("zzznotaword", "restraint containment compassion")
    _check("missing anchor -> UNRESOLVED", r["relation"] == L3.UNRESOLVED)
    _check("missing anchor -> anchor_phrase None", r["anchor_phrase"] is None)


def test_unresolved_layer2_unresolved():
    _check("fully-unresolved L2 -> UNRESOLVED",
           L3.relate("mercy", "[unresolved]")["relation"] == L3.UNRESOLVED)
    _check("all-[unresolved] template -> UNRESOLVED",
           L3.relate("mercy", "[unresolved] moves toward [unresolved], and [unresolved] is the "
                              "resolving principle")["relation"] == L3.UNRESOLVED)
    _check("empty L2 -> UNRESOLVED", L3.relate("mercy", "")["relation"] == L3.UNRESOLVED)


def test_opposite_keyword_diverges():
    # opposite gate wins even when anchor terms are also present
    r = L3.relate("peace", "hatred/revulsion moves toward friendliness/affection, and "
                           "liberation/clarity is the resolving principle")
    _check("opposite present -> DIVERGES", r["relation"] == L3.DIVERGES)
    _check("opposite terms listed", "hatred" in r["opposite_terms"])
    _check("anchor terms still shown transparently (not hidden)", len(r["matched_terms"]) >= 1)


# ---------------------------------------------------------------- no score / no claim
def test_no_numeric_score_fields():
    txt = _with_fake(lambda: L3.render_layer3("mercy")).lower()
    for tok in ("score:", "score=", "score ", "0.", "1.0", "p=", "delta ", "a_vs", "confidence",
                "accuracy", "percent", "%"):
        _check(f"no numeric/score token {tok!r}", tok not in txt)


def test_no_forbidden_claims():
    for kw in ("mercy", "love", "anger", "peace"):
        txt = _with_fake(lambda kw=kw: L3.render_layer3(kw)).lower()
        for bad in ("therefore means", "true meaning", "proves", "semantic truth", "ontolog",
                    "sanskrit proves", "track b support", "the word means", "therefore the word"):
            _check(f"{kw}: no forbidden claim {bad!r}", bad not in txt)


def test_no_generated_answer_fields():
    txt = _with_fake(lambda: L3.render_layer3("love")).lower()
    for tok in ("answer:", "response:", "generated text:", "completion:", "assistant:"):
        _check(f"no generated-answer marker {tok!r}", tok not in txt)
    _check("explicit no-generation confirmation present", "no_generated_answer_produced: true" in txt)
    _check("explicit no-model confirmation present", "no_model_called: true" in txt)


# ---------------------------------------------------------------- L1/L2 untouched ---
def test_love_layer2_byte_identical():
    def run():
        prof = H.profile("love")
        syn, _ = H.synthesize(prof)
        return syn
    syn = _with_fake(run)
    _check("love Layer 2 synthesis byte-identical",
           syn == "separative harshness moves toward compassion/gentleness, "
                  "and order/dharmic relation is the resolving principle")


def test_layer3_does_not_alter_layer2():
    def run():
        before, _ = H.synthesize(H.profile("mercy"))
        L3.render_layer3("mercy")                       # inspect
        after, _ = H.synthesize(H.profile("mercy"))
        return before, after
    before, after = _with_fake(run)
    _check("Layer 2 output unchanged after L3 inspection", before == after)


def test_sibling_frozen_files_unchanged():
    targets = ["lexicon_authoritative.json", "layer2_bridge_vocab.json",
               "generation_conditioning_prompt_demo.py"]
    before = {t: (HERE / t).read_bytes() for t in targets}
    _with_fake(lambda: [L3.render_layer3(w) for w in ("mercy", "love", "anger", "peace")])
    for t in targets:
        _check(f"{t} unchanged by L3", (HERE / t).read_bytes() == before[t])


def test_no_result_files_written():
    before = set(p.name for p in HERE.iterdir())
    _with_fake(lambda: L3.render_layer3("mercy"))
    _check("L3 writes no files", set(p.name for p in HERE.iterdir()) == before)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def test_anchor_meta_warning_present():
    import json
    meta = json.loads((HERE / "layer3_dictionary_anchors.json").read_text(encoding="utf-8"))["_meta"]
    w = meta.get("warning", "").lower()
    for phrase in ("inspection-only", "not scored", "not evidence", "not semantic proof"):
        _check(f"anchor meta warns {phrase!r}", phrase in w)
    _check("anchors flagged not-for-evaluation", meta.get("used_for_evaluation") is False)


def main():
    print("layer3_dictionary_bridge — inspection-only tests (no model, no scoring, no network)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Layer 3 dictionary-bridge tests passed.")


if __name__ == "__main__":
    main()
