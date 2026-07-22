#!/usr/bin/env python3
"""Dedicated tests for क्ष / ksha parser normalization.

Policy (authoritative B1.12 `ksha_note`): क्ष is a conjunct, not an atomic varṇa. The parser rewrites
every supported conjunct form to the atomic sequence [ka, ssa] = k + ṣ, in source order, resolving
against the authoritative B1.12 mappings for k and ṣ. No synthetic ksha drive row is invented.

  python varna_lens/test_ksha_normalization.py
  pytest  varna_lens/test_ksha_normalization.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent
_REPO = _VL.parent
sys.path.insert(0, str(_VL))
import varna_lens as V  # noqa: E402

B1_12_SOURCE = _REPO / "experiments" / "primitive_sequence_recovery" / "frozen" / "varna_native_stage1_merged_v3.json"

CANON = [("C", "ka"), ("C", "ssa")]           # the single canonical decomposition of the conjunct
SUPPORTED_FORMS = ["kṣ", "ksh", "x", "kSh"]    # roman/IAST/ITRANS forms the parser converges


def _keys(phonemes):
    return [(t, k) for t, k, _s in phonemes]


def test_all_supported_forms_converge_to_ka_ssa():
    for form in SUPPORTED_FORMS:
        ph, warn = V.phonemes_roman(form)
        assert _keys(ph) == CANON, f"{form!r} → {_keys(ph)}"


def test_same_input_same_sequence_deterministic():
    for form in SUPPORTED_FORMS:
        assert _keys(V.phonemes_roman(form)[0]) == _keys(V.phonemes_roman(form)[0])
    # all forms collapse to ONE canonical sequence
    seqs = {tuple(_keys(V.phonemes_roman(f)[0])) for f in SUPPORTED_FORMS}
    assert seqs == {tuple(CANON)}


def test_source_order_preserved_k_before_ss():
    ph, _ = V.phonemes_roman("kṣamā")
    assert _keys(ph) == [("C", "ka"), ("C", "ssa"), ("V", "a"), ("C", "ma"), ("V", "aa")]


def test_decomposition_uses_authoritative_b1_12_k_and_ss():
    v3 = {r["canonical_parser_unit"]: r for r in json.loads(B1_12_SOURCE.read_text(encoding="utf-8"))["rows"]}
    # ka carries the B1.12 k drive; ssa carries the B1.12 ṣ drive (kāma) — the corrected sibilant.
    assert V.CONS["ka"]["leading_vritti"] == v3["k"]["binding_vritti"]
    assert V.CONS["ssa"]["leading_vritti"] == v3["ṣ"]["binding_vritti"]
    assert "kāma" in V.CONS["ssa"]["leading_vritti"]


def test_no_synthetic_ksha_row_anywhere():
    assert "ksha" not in V.CONS                                # engine has no ksha drive
    lex = json.loads((_VL / "lexicon_b1_12.json").read_text(encoding="utf-8"))
    assert "ksha" not in lex["consonants"]                     # runtime lexicon has no ksha row
    can = json.loads((_VL / "mapping" / "varna_mapping_b1_12_canonical.json").read_text(encoding="utf-8"))
    assert "ksha" not in can["mappings"]                       # canonical mapping has no ksha row
    assert can["unmapped"]["ksha"]["disposition"] == "RESOLVED_BY_PARSER_DECOMPOSITION"


def test_ksha_token_never_reaches_engine():
    for w in ("kṣamā", "kṣatriya", "akṣa", "x", "ksham"):
        ph, _ = V.phonemes_roman(w)
        assert all(k != "ksha" for _t, k, _s in ph), w
        # every consonant token resolves against the lexicon (no '(no lexicon entry)')
        out = V.read(ph, model="op")
        assert "no lexicon entry" not in V.format_reading(w, "roman", out, [])


def test_full_word_produces_nonempty_essence():
    d, src, warn = V.analyze("kṣamā", model="op", roman=True)
    assert d and d["essence_short"]


def test_non_conjunct_words_unchanged():
    # words with no conjunct must tokenize exactly as before (normalization is a no-op)
    for w, exp in (("kāla", [("C", "ka"), ("V", "aa"), ("C", "la"), ("V", "a")]),
                   ("karma", [("C", "ka"), ("V", "a"), ("C", "ra"), ("C", "ma"), ("V", "a")]),
                   ("śānti", [("C", "sha"), ("V", "aa"), ("C", "na"), ("C", "ta"), ("V", "i")])):
        assert _keys(V.phonemes_roman(w)[0]) == exp, w


def test_ksh_did_not_hijack_unrelated_inputs():
    # 'sh' (ś) alone and 'kh' (kha) must be untouched by adding the 'ksh' rule
    assert _keys(V.phonemes_roman("śa")[0]) == [("C", "sha"), ("V", "a")]
    assert _keys(V.phonemes_roman("kha")[0]) == [("C", "kha"), ("V", "a")]
    assert _keys(V.phonemes_roman("sha")[0]) == [("C", "sha"), ("V", "a")]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    fails = []
    for t in tests:
        try:
            t(); print(f"  [PASS] {t.__name__}")
        except Exception as e:  # noqa: BLE001
            fails.append((t.__name__, e)); print(f"  [FAIL] {t.__name__}: {e}")
    print(f"\ntest_ksha_normalization: {'PASS' if not fails else 'FAIL'} ({len(tests) - len(fails)}/{len(tests)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
