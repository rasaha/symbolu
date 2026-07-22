"""Tests for the Layer 4 synonym-attribute attribution check — INSPECTION ONLY (no model, no scoring).

Hermetic: patches the g2p function so no nltk/cmudict is needed. Proves: required label top+bottom;
missing inventory -> all UNRESOLVED; unresolved Layer 2 -> every attribute UNRESOLVED; SUPPORTED shows
an explicit evidence path; UNSUPPORTED stays UNSUPPORTED with an empty path (not guessed); NO total/
aggregate score and no numeric-score/verdict/signal/accuracy/p=/%/N-over-M fields; no forbidden claims;
no ML imports; no web/runtime lookup; no generated-answer fields; no result files; Layer 1/2 output
unchanged; Layer 3 output unchanged; `love` Layer 2 byte-identical; sibling frozen files unchanged;
and each demo word has >=1 UNSUPPORTED attribute (inventory not target-fit).

    python3 varna_lens/test_layer4_attribute_check.py
"""
from __future__ import annotations
import os as _os, sys as _sys
# RETIRED historical-regression: validates the retired Layer-2 bridge, defined only under the pre-B1.12
# lexicon. Skips under the active B1.12 mapping; runs its original assertions under the old-lexicon
# fixture. See experiments/retired/layer2_bridge/README.md.
if not _os.environ.get("VARNA_LENS_MAPPING", "").endswith("lexicon_authoritative.json"):
    if "pytest" in _sys.modules:
        import pytest as _pytest
        _pytest.skip("retired Layer-2 bridge test (needs old-lexicon fixture)", allow_module_level=True)
    else:
        print("SKIP: retired Layer-2 bridge test (set VARNA_LENS_MAPPING=<repo>/varna_lens/lexicon_authoritative.json to run)")
        raise SystemExit(0)

import json
import re
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V                        # noqa: E402  (g2p lives here)
import sample_text_rule_harness as H          # noqa: E402  (Layer 1/2 producer)
import layer3_dictionary_bridge as L3         # noqa: E402  (only to assert L3 output unchanged)
import layer4_attribute_check as L4           # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


_FAKE = {
    "love": ([("C", "la", "L"), ("V", "a", "AH1"), ("C", "va", "V")], []),
    "mercy": ([("C", "ma", "M"), ("V", "a", "ER1"), ("C", "sa", "S"), ("V", "ii", "IY0")], []),
    "anger": ([("V", "a", "AE1"), ("C", "nga", "NG"), ("C", "ga", "G"), ("V", "a", "ER0")], []),
    "peace": ([("C", "pa", "P"), ("V", "ii", "IY1"), ("C", "sa", "S")], []),
}
_DEMO = ("mercy", "love", "anger", "peace")


def _fake(word):
    return _FAKE.get(word.lower(), ([], [f"'{word}' not in cmudict"]))


def _with_fake(fn):
    orig = V.phonemes_cmudict
    V.phonemes_cmudict = _fake
    try:
        return fn()
    finally:
        V.phonemes_cmudict = orig


def _statuses(kw):
    r = _with_fake(lambda: L4.attribute_check(kw))
    return {row["attribute"]: row["status"] for row in r["attribution"]}


# ---------------------------------------------------------------- label discipline --
def test_label_top_and_bottom():
    txt = _with_fake(lambda: L4.render_layer4("love"))
    _check("required label present top + bottom", txt.count(L4.LABEL) >= 2)
    _check("label is exact required string",
           L4.LABEL == "LAYER4_SYNONYM_ATTRIBUTE_CHECK — not scored, not evidence")


def test_caveat_present():
    txt = _with_fake(lambda: L4.render_layer4("love"))
    _check("mandated caveat present", L4.CAVEAT in txt)
    _check("caveat carries NO_SIGNAL prior", "NO_SIGNAL" in txt)


# ---------------------------------------------------------------- core attribution --
def test_missing_inventory_all_unresolved():
    r = _with_fake(lambda: L4.attribute_check("zzznotaword"))
    _check("missing inventory -> no per-attribute rows", r["attribution"] == [])
    _check("missing inventory -> reason set", bool(r["reason_all"]))
    txt = _with_fake(lambda: L4.render_layer4("zzznotaword"))
    _check("missing inventory render says UNRESOLVED", "UNRESOLVED" in txt)
    _check("missing inventory render shows no SUPPORTED", "status: SUPPORTED" not in txt)


def test_unresolved_layer2_all_unresolved():
    # force L2 unresolved by mapping the whole word to non-lexicon varṇa keys
    def run():
        V.phonemes_cmudict = lambda w: ([("C", "zz_x", "L"), ("V", "a", "AH1"), ("C", "zz_y", "V")], [])
        try:
            # temporarily add an inventory entry for this fake word via monkeypatch of INVENTORY
            L4.INVENTORY["fakeword"] = {"attributes": [
                {"attribute": "affection", "support_terms": ["affection"]},
                {"attribute": "trust", "support_terms": ["trust"]}]}
            return L4.attribute_check("fakeword")
        finally:
            L4.INVENTORY.pop("fakeword", None)
    r = _with_fake(run)
    _check("unresolved L2 -> every attribute UNRESOLVED",
           all(row["status"] == L4.UNRESOLVED for row in r["attribution"]) and r["attribution"])
    _check("unresolved L2 -> empty evidence paths",
           all(row["evidence_path"] == [] for row in r["attribution"]))


def test_supported_has_explicit_evidence_path():
    r = _with_fake(lambda: L4.attribute_check("anger"))
    sup = [row for row in r["attribution"] if row["status"] == L4.SUPPORTED]
    _check("anger has >=1 SUPPORTED", len(sup) >= 1)
    for row in sup:
        _check(f"SUPPORTED {row['attribute']!r} has non-empty evidence path", len(row["evidence_path"]) >= 1)
        for frag in row["evidence_path"]:
            _check(f"evidence path traces phrase+role for {row['attribute']!r}",
                   "layer2_phrase:" in frag and "varna_role:" in frag)


def test_unsupported_empty_path_not_guessed():
    r = _with_fake(lambda: L4.attribute_check("love"))
    uns = [row for row in r["attribution"] if row["status"] == L4.UNSUPPORTED]
    _check("love has >=1 UNSUPPORTED", len(uns) >= 1)
    for row in uns:
        _check(f"UNSUPPORTED {row['attribute']!r} has empty evidence path", row["evidence_path"] == [])


def test_each_demo_word_has_an_unsupported_attribute():
    # contamination guard: inventory is NOT target-fit to make everything pass
    for kw in _DEMO:
        st = _statuses(kw)
        _check(f"{kw}: has >=1 UNSUPPORTED attribute (not target-fit)",
               any(v == L4.UNSUPPORTED for v in st.values()))
        _check(f"{kw}: has >=1 SUPPORTED attribute (evidence path exercised)",
               any(v == L4.SUPPORTED for v in st.values()))


# ---------------------------------------------------------------- STRICT score guard
def test_no_total_or_aggregate_score():
    for kw in _DEMO:
        txt = _with_fake(lambda kw=kw: L4.render_layer4(kw)).lower()
        for tok in ("total", "aggregate", "summary score", "overall", "supported:",
                    " of 4", " of 3", "supported/"):
            _check(f"{kw}: no aggregate token {tok!r}", tok not in txt)
        # 'counter' (a varṇa role label) is fine; a standalone 'count' aggregate is not
        _check(f"{kw}: no standalone 'count' aggregate", re.search(r"\bcount\b", txt) is None)


def test_no_numeric_or_metric_fields():
    for kw in _DEMO:
        txt = _with_fake(lambda kw=kw: L4.render_layer4(kw))
        low = txt.lower()
        for tok in ("score:", "score=", "verdict", "signal:", "signal=", " signal ", "accuracy",
                    "p=", "%", "confidence", "rank", "a_vs", "pass/fail", "pass:", "fail:", "0.", "1.0"):
            _check(f"{kw}: no metric token {tok!r}", tok not in low)
        # a genuine score fraction (N/M), excluding the benign "Layer 1/2" layer reference
        scan = re.sub(r"layer\s*\d+\s*/\s*\d+", "", txt, flags=re.IGNORECASE)
        _check(f"{kw}: no N/M score fraction", re.search(r"\d+\s*/\s*\d+", scan) is None)
        _check(f"{kw}: no bare digits used as a score", re.search(r"\bstatus:\s*\d", low) is None)


def test_no_forbidden_claims():
    for kw in _DEMO:
        txt = _with_fake(lambda kw=kw: L4.render_layer4(kw)).lower()
        for bad in ("therefore means", "the word means", "therefore the word", "true meaning",
                    "proves", "semantic truth", "ontolog", "sanskrit proves", "track b support",
                    "validat"):
            _check(f"{kw}: no forbidden claim {bad!r}", bad not in txt)


def test_no_generated_answer_fields():
    txt = _with_fake(lambda: L4.render_layer4("love")).lower()
    for tok in ("answer:", "response:", "generated text:", "completion:", "assistant:"):
        _check(f"no generated-answer marker {tok!r}", tok not in txt)
    _check("explicit no-generation confirmation present", "no_generated_answer_produced: true" in txt)
    _check("explicit no-model confirmation present", "no_model_called: true" in txt)


# ---------------------------------------------------------------- independence ------
def test_does_not_import_layer3():
    import inspect
    src = inspect.getsource(L4)
    _check("L4 source does not import layer3", "import layer3" not in src and "layer3_dictionary" not in src)


# ---------------------------------------------------------------- L1/L2/L3 untouched
def test_love_layer2_byte_identical():
    def run():
        return H.synthesize(H.profile("love"))[0]
    _check("love Layer 2 synthesis byte-identical",
           _with_fake(run) == "separative harshness moves toward compassion/gentleness, "
                              "and order/dharmic relation is the resolving principle")


def test_layer4_does_not_alter_layer2_or_layer3():
    def run():
        l2_before = H.synthesize(H.profile("mercy"))[0]
        l3_before = L3.render_layer3("mercy")
        L4.render_layer4("mercy")                       # inspect
        l2_after = H.synthesize(H.profile("mercy"))[0]
        l3_after = L3.render_layer3("mercy")
        return l2_before, l2_after, l3_before, l3_after
    l2b, l2a, l3b, l3a = _with_fake(run)
    _check("Layer 2 output unchanged after L4", l2b == l2a)
    _check("Layer 3 output unchanged after L4", l3b == l3a)


def test_sibling_frozen_files_unchanged():
    # layer2_bridge_vocab.json archived to experiments/retired/layer2_bridge/ on Layer-2 retirement.
    targets = ["lexicon_authoritative.json",
               "layer3_dictionary_anchors.json", "generation_conditioning_prompt_demo.py"]
    before = {t: (HERE / t).read_bytes() for t in targets}
    _with_fake(lambda: [L4.render_layer4(w) for w in _DEMO])
    for t in targets:
        _check(f"{t} unchanged by L4", (HERE / t).read_bytes() == before[t])


def test_no_result_files_written():
    before = set(p.name for p in HERE.iterdir())
    _with_fake(lambda: L4.render_layer4("mercy"))
    _check("L4 writes no files", set(p.name for p in HERE.iterdir()) == before)


def test_no_ml_libs_imported():
    _check("no torch/transformers/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def test_inventory_meta_warning_present():
    meta = json.loads((HERE / "layer4_attribute_inventory.json").read_text(encoding="utf-8"))["_meta"]
    w = meta.get("warning", "").lower()
    for phrase in ("inspection-only", "not scored", "not evidence", "not semantic proof",
                   "not tuned to make the demo words pass"):
        _check(f"inventory meta warns {phrase!r}", phrase in w)
    _check("inventory flagged not-for-evaluation", meta.get("used_for_evaluation") is False)
    _check("inventory flagged not-for-prereg-execution", meta.get("used_for_prereg_execution") is False)
    _check("inventory flagged not-tuned", meta.get("tuned_to_pass_demo_words") is False)


def main():
    print("layer4_attribute_check — inspection-only tests (no model, no scoring, no aggregate)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Layer 4 attribute-check tests passed.")


if __name__ == "__main__":
    main()
