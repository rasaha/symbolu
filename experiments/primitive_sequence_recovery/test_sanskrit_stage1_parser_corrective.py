"""Corrective / adversarial suite for the Stage-1 Sanskrit parser — the post-audit findings.

Kept SEPARATE from the eight official linguistic golden fixtures (test_sanskrit_stage1_parser.py). Covers:
ZWJ/ZWNJ join-control policy, singleton boundary booleans, unsupported-nukta policy, virāma+independent-vowel
warning, the single-token whitespace contract, and the losslessness / provenance invariants.

NO network, NO model. Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL.
"""
import pathlib
import unicodedata

import pytest

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
V = "्"           # virāma
ZWJ, ZWNJ, ZWSP = P.ZWJ, P.ZWNJ, P.ZWSP


def units(w):
    return [u["unit"] for u in P.parse(w)["atomic_varnas"]]


def wclasses(w):
    return [x["class"] for x in P.parse(w)["warnings"]]


# ------------------------------------------------------------------ 1. ZWJ / ZWNJ join-control policy
KSA, KSA_ZWJ, KSA_ZWNJ = "क्ष", "क" + V + ZWJ + "ष", "क" + V + ZWNJ + "ष"


def test_zwj_zwnj_same_atomic_sequence():
    assert units(KSA) == units(KSA_ZWJ) == units(KSA_ZWNJ) == ["k", "ṣ", "a"]


def test_zwj_zwnj_not_emitted_as_varna():
    for w in (KSA_ZWJ, KSA_ZWNJ):
        for u in P.parse(w)["atomic_varnas"]:
            assert u["devanagari"] not in (ZWJ, ZWNJ)
            assert u["type"] != "join_control"


def test_zwj_zwnj_recorded_and_reconstructable():
    for w, ctrl in ((KSA_ZWJ, ZWJ), (KSA_ZWNJ, ZWNJ)):
        r = P.parse(w)
        assert "join_control_in_conjunct" in [x["class"] for x in r["warnings"]]
        # still present in the orthographic layer (akṣara substring) -> reconstructable
        assert ctrl in "".join(a["devanagari"] for a in r["aksharas"])


def test_zwj_zwnj_no_inherent_before_linked_consonant():
    # ष is the final conjunct member -> it legitimately takes inherent अ; क must NOT get one
    for w in (KSA, KSA_ZWJ, KSA_ZWNJ):
        r = P.parse(w)
        k_unit = r["atomic_varnas"][0]
        assert k_unit["unit"] == "k" and k_unit["origin"] == "virama_terminated"


def test_join_control_out_of_context():
    for w in (ZWJ, ZWNJ, ZWJ + "क", "क" + ZWJ):
        r = P.parse(w)
        assert "join_control_out_of_context" in [x["class"] for x in r["warnings"]]
        for u in r["atomic_varnas"]:
            assert u["devanagari"] not in (ZWJ, ZWNJ)


def test_isolated_join_control_no_atomic_unit():
    for w in (ZWJ, ZWNJ):
        assert P.parse(w)["atomic_varnas"] == []


# ------------------------------------------------------------------ 2. singleton boundary booleans
@pytest.mark.parametrize("w,ln", [("क्", 1), ("ऋ", 1), ("क", 2), ("क्ष", 3), ("कमल", 6)])
def test_boundary_booleans(w, ln):
    a = P.parse(w)["atomic_varnas"]
    assert len(a) == ln
    assert a[0]["is_initial"] is True
    assert a[-1]["is_final"] is True
    for k, u in enumerate(a):
        assert u["is_initial"] == (k == 0)
        assert u["is_final"] == (k == len(a) - 1)


def test_singleton_both_true():
    u = P.parse("क्")["atomic_varnas"][0]
    assert u["is_initial"] and u["is_final"]
    assert u["position"] == "onset"       # scalar retained; booleans authoritative


def test_scalar_position_multi():
    a = P.parse("कमल")["atomic_varnas"]
    assert a[0]["position"] == "onset" and a[-1]["position"] == "final"
    assert all(u["position"] == "medial" for u in a[1:-1])


# ------------------------------------------------------------------ 3. unsupported nukta policy
@pytest.mark.parametrize("w", ["क़", "क़ि", "क" + V + "ज़", "ड़"])
def test_nukta_unsupported_no_inherent_no_invented_consonant(w):
    r = P.parse(w)
    assert r["inherent_vowel_insertions"]["count"] == 0 or all(
        u["origin"] != "unresolved_nukta_base" or not u["inherent_inserted"] for u in r["atomic_varnas"])
    nukta_units = [u for u in r["atomic_varnas"] if u["origin"] == "unresolved_nukta_base"]
    assert nukta_units, "nukta base must be represented"
    for u in nukta_units:
        assert u["type"] == "unsupported"
        assert u["inherent_inserted"] is False
        assert u["unit"] not in P.CONSONANTS.values()  # no invented recognized consonant identity
    assert "non_classical_nukta" in [x["class"] for x in r["warnings"]]


def test_nukta_dependent_vowel_retained_as_metadata_not_varna():
    r = P.parse("क़ि")
    # the ि is retained in the unit's devanagari and in the warning metadata, NOT emitted as a resolved vowel
    assert not any(u["type"] == "vowel" for u in r["atomic_varnas"])
    w = [x for x in r["warnings"] if x["class"] == "non_classical_nukta"][0]
    assert w["dependent_vowel_metadata"] == "i"
    assert "ि" in r["atomic_varnas"][0]["devanagari"]


def test_nukta_precomposed_and_decomposed_equivalent():
    # क़ as precomposed U+0958 vs decomposed क + ़ — NFC unifies them
    pre = P.parse("क़")
    dec = P.parse("क़")
    assert P.canonical_structure(pre) == P.canonical_structure(dec)


def test_nukta_in_conjunct_no_inherent_on_prior_member():
    r = P.parse("क" + V + "ज़")  # k + halant + ja-nukta
    assert r["atomic_varnas"][0]["unit"] == "k"
    assert r["atomic_varnas"][0]["origin"] == "virama_terminated"
    assert r["inherent_vowel_insertions"]["count"] == 0


# ------------------------------------------------------------------ 4. virāma + independent vowel
def test_virama_before_independent_vowel_warns():
    r = P.parse("क" + V + "आ")
    assert "virama_before_independent_vowel" in [x["class"] for x in r["warnings"]]
    assert units("क" + V + "आ") == ["k", "ā"]   # deterministic structure preserved, no repair


# ------------------------------------------------------------------ 5. single-token whitespace contract
def test_empty_input():
    r = P.parse("")
    assert r["atomic_varnas"] == []
    assert "empty_input" in [x["class"] for x in r["warnings"]]


def test_whitespace_only():
    r = P.parse("   ")
    assert all(u["unit"] != " " for u in r["atomic_varnas"])
    assert all(x["class"] == "leading_trailing_whitespace" for x in r["warnings"])


def test_leading_and_trailing_whitespace():
    assert "leading_trailing_whitespace" in wclasses(" क")
    assert "leading_trailing_whitespace" in wclasses("क ")


def test_two_word_input_flagged_not_split():
    r = P.parse("क म")
    assert "multiple_tokens_or_whitespace" in [x["class"] for x in r["warnings"]]
    assert all(u["unit"] != " " for u in r["atomic_varnas"])   # not emitted as varṇa


def test_whitespace_never_atomic_varna():
    for w in (" ", "क ", " क", "क\tम", "क\nम"):
        assert all(u["type"] not in ("consonant", "vowel") or u["unit"] != " "
                   for u in P.parse(w)["atomic_varnas"])
        assert all(u["unit"] != " " for u in P.parse(w)["atomic_varnas"])


def test_zwsp_retained_and_warned():
    r = P.parse(ZWSP + "क")
    assert "zero_width_space_retained" in [x["class"] for x in r["warnings"]]
    assert all(u["devanagari"] != ZWSP for u in r["atomic_varnas"])


# ------------------------------------------------------------------ 6. losslessness / provenance invariants
CORPUS = ["कमल", "शान्ति", "शक्ति", "दुःख", "संस्कृत", "बुद्धि", "क्षमा", "अग्नि", "धर्म",
          "कार्त्स्न्य", "क्", "तत्", KSA, KSA_ZWJ, KSA_ZWNJ, "क़", "क़ि", "क" + V + "आ",
          "क म", " क ", ZWJ, ZWSP + "क", "ॐक", "अं", "अः", "अँ", "तत्त्व"]


@pytest.mark.parametrize("w", CORPUS)
def test_inv1_akshara_reconstructs_nfc(w):
    r = P.parse(w)
    assert "".join(a["devanagari"] for a in r["aksharas"]) == unicodedata.normalize("NFC", w)


@pytest.mark.parametrize("w", CORPUS)
def test_inv2_full_span_coverage(w):
    r = P.parse(w)
    spans = [a["source_span"] for a in r["aksharas"]]
    nfc = unicodedata.normalize("NFC", w)
    if not spans:
        assert nfc == ""
    else:
        assert spans[0][0] == 0 and spans[-1][1] == len(nfc)
        assert all(spans[k][1] == spans[k + 1][0] for k in range(len(spans) - 1))


@pytest.mark.parametrize("w", CORPUS)
def test_inv4_no_join_control_in_atomic(w):
    for u in P.parse(w)["atomic_varnas"]:
        assert u["devanagari"] not in (ZWJ, ZWNJ)


@pytest.mark.parametrize("w", CORPUS)
def test_inv5_atomic_units_map_to_valid_akshara(w):
    r = P.parse(w)
    n_ak = len(r["aksharas"])
    for u in r["atomic_varnas"]:
        assert 0 <= u["source_akshara_index"] < n_ak


@pytest.mark.parametrize("w", CORPUS)
def test_inv6_slices_ordered_nonoverlapping_complete(w):
    r = P.parse(w)
    covered = []
    for a in r["aksharas"]:
        covered.extend(a["atomic_varna_indices"])
    assert covered == list(range(len(r["atomic_varnas"])))


@pytest.mark.parametrize("w", CORPUS)
def test_inv7_deterministic(w):
    assert P.serialize(P.parse(w)) == P.serialize(P.parse(w))


@pytest.mark.parametrize("w", CORPUS)
def test_inv8_nfc_idempotent(w):
    nfc = unicodedata.normalize("NFC", w)
    assert unicodedata.normalize("NFC", nfc) == nfc
    assert P.parse(w)["normalized_devanagari"] == nfc


@pytest.mark.parametrize("w", ["शान्ति", "क़", "कमल", "दुःख"])
def test_inv9_nfc_nfd_canonical_structure_equal(w):
    nfd = unicodedata.normalize("NFD", w)
    rc, rd = P.parse(w), P.parse(nfd)
    # canonical structural projection identical...
    assert P.canonical_structure(rc) == P.canonical_structure(rd)
    assert rc["normalized_devanagari"] == rd["normalized_devanagari"]
    # ...while original-input echo + normalization metadata are faithful to each input
    assert rd["word_devanagari"] == nfd
    assert rd["normalization"]["changed"] == (nfd != rd["normalized_devanagari"])


def test_inv3_zwj_zwnj_reconstructable():
    for w, ctrl in ((KSA_ZWJ, ZWJ), (KSA_ZWNJ, ZWNJ)):
        r = P.parse(w)
        assert ctrl in "".join(a["devanagari"] for a in r["aksharas"])


# ------------------------------------------------------------------ semantic firewall still holds
def test_firewall_still_clean():
    src = (HERE / "sanskrit_stage1_parser.py").read_text()
    for banned in ("varna_polarity", "control_ext", "track_g", "VARNA_PLAIN", "word_to_varnas",
                   "import torch", "transformers", "g2p", "polarity_table"):
        assert banned not in src
    blob = P.serialize(P.parse("क्ष"))
    for banned in ("binding", "liberating", "pole", "facet", "GENUTILITY", "score"):
        assert banned not in blob
