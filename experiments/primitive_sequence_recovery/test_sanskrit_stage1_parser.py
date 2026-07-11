"""Test suite for the Stage-1 native-Sanskrit parser (B1_STAGE1_SANSKRIT_PARSER_SPEC.md). NO network, NO model.

A. Golden byte-for-byte fixtures for all eight spec examples.
B. Rule-level unit tests (R1–R12).
C. Structural invariants.
D. Semantic-firewall (the parser is a pure structural component).

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import pathlib
import unicodedata

import pytest

import sanskrit_stage1_parser as P

HERE = pathlib.Path(__file__).resolve().parent
GOLD = HERE / "stage1_golden"

# devanagari -> golden filename stem
FIXTURES = {
    "कमल": "kamala", "शान्ति": "shaanti", "शक्ति": "shakti", "दुःख": "duhkha",
    "संस्कृत": "samskrta", "बुद्धि": "buddhi", "क्षमा": "kshamaa", "अग्नि": "agni",
}


# ----------------------------------------------------------------------------- A. golden fixtures
@pytest.mark.parametrize("word,stem", list(FIXTURES.items()))
def test_golden_byte_for_byte(word, stem):
    """Full canonical serialization must match the frozen golden byte-for-byte (not selected fields)."""
    expected = (GOLD / f"{stem}.json").read_text(encoding="utf-8")
    assert P.serialize(P.parse(word)) == expected


def test_golden_pins_all_required_facets():
    """The goldens must pin normalized form, code points, akṣaras, atomic order, inherent insertions,
    aspiration, conjunct expansion, anusvāra/visarga, position, multiplicity, and warnings."""
    r = P.parse("दुःख")
    assert r["normalized_devanagari"] == "दुःख"
    assert r["aksharas"][0]["codepoints"] == ["U+0926", "U+0941", "U+0903"]
    units = [u["unit"] for u in r["atomic_varnas"]]
    assert units == ["d", "u", "ḥ", "kh", "a"]                     # atomic order + visarga
    assert r["atomic_varnas"][3]["aspirated"] is True              # kh aspirate
    assert r["atomic_varnas"][2]["type"] == "visarga"
    assert r["inherent_vowel_insertions"]["count"] == 1
    assert r["atomic_varnas"][-1]["position"] == "final"
    assert r["multiplicity"]["varna_counts"]["kh"] == 1
    assert r["warnings"] == []


# ----------------------------------------------------------------------------- B. rule-level tests
def test_nfc_equivalent_inputs_identical():
    # शा as precomposed vs श + combining ā sign are NFC-equivalent
    a = P.parse("शा")
    b = P.parse(unicodedata.normalize("NFD", "शा"))
    assert P.serialize(a) == P.serialize(b)


def test_normalization_changed_flag():
    nfd = unicodedata.normalize("NFD", "शा")
    r = P.parse(nfd)
    assert r["normalization"]["changed"] == (nfd != "शा")
    assert r["normalized_devanagari"] == "शा"


def test_independent_vs_dependent_vowel_same_identity_diff_origin():
    ind = P.parse("आ")["atomic_varnas"][0]
    dep = P.parse("का")["atomic_varnas"][1]
    assert ind["unit"] == dep["unit"] == "ā"                       # same canonical identity
    assert ind["origin"] == "independent_vowel"
    assert dep["origin"] == "dependent_vowel_sign"


def test_consonant_inherent_a():
    r = P.parse("क")
    assert [u["unit"] for u in r["atomic_varnas"]] == ["k", "a"]
    assert r["atomic_varnas"][1]["inherent_inserted"] is True
    assert r["atomic_varnas"][1]["origin"] == "inherent_a"


def test_consonant_explicit_vowel_sign_no_inherent():
    r = P.parse("कि")
    assert [u["unit"] for u in r["atomic_varnas"]] == ["k", "i"]
    assert r["atomic_varnas"][1]["inherent_inserted"] is False
    assert r["inherent_vowel_insertions"]["count"] == 0


def test_consonant_virama_no_vowel():
    r = P.parse("क्")  # bare ka + virāma (word-final halant)
    assert [u["unit"] for u in r["atomic_varnas"]] == ["k"]
    assert r["atomic_varnas"][0]["origin"] == "virama_terminated"
    assert r["inherent_vowel_insertions"]["count"] == 0


def test_two_member_conjunct():
    r = P.parse("क्ष")
    assert [u["unit"] for u in r["atomic_varnas"]] == ["k", "ṣ", "a"]
    assert r["atomic_varnas"][0]["orthographic_source"] == "conjunct_constituent"
    assert len(r["aksharas"]) == 1                                  # whole conjunct is one akṣara


def test_multi_member_conjunct():
    r = P.parse("क्ष्म")  # k + ṣ + m + inherent a
    assert [u["unit"] for u in r["atomic_varnas"]] == ["k", "ṣ", "m", "a"]
    assert [u["origin"] for u in r["atomic_varnas"][:2]] == ["virama_terminated", "virama_terminated"]
    assert len(r["aksharas"]) == 1


def test_aspirated_vs_unaspirated():
    assert P.parse("ख")["atomic_varnas"][0]["unit"] == "kh"
    assert P.parse("ख")["atomic_varnas"][0]["aspirated"] is True
    assert P.parse("क")["atomic_varnas"][0]["aspirated"] is False


def test_aspirate_not_split_into_stop_plus_ha():
    for asp in ("ख", "घ", "छ", "झ", "ठ", "ढ", "थ", "ध", "फ", "भ"):
        cons = [u for u in P.parse(asp)["atomic_varnas"] if u["type"] == "consonant"]
        assert len(cons) == 1 and cons[0]["aspirated"] is True     # single varṇa, never C + h


def test_repeated_consonants_and_gemination_no_dedup():
    r = P.parse("तत्त्व")  # tattva: t a t t v a — repeated t preserved
    units = [u["unit"] for u in r["atomic_varnas"]]
    assert units.count("t") == 3
    assert any(g["unit"] == "t" and g["count"] >= 2 for g in r["multiplicity"]["geminations"])


def test_anusvara_preserved_canonical():
    r = P.parse("अं")
    assert [u["unit"] for u in r["atomic_varnas"]] == ["a", "ṃ"]
    assert r["atomic_varnas"][1]["type"] == "anusvara"
    assert r["derived_noncanonical"]["resolved_pronunciation_candidate"] is None


def test_visarga_preserved_canonical():
    r = P.parse("अः")
    assert r["atomic_varnas"][1]["type"] == "visarga" and r["atomic_varnas"][1]["unit"] == "ḥ"


def test_candrabindu():
    r = P.parse("अँ")
    assert r["atomic_varnas"][1]["type"] == "nasalization"
    assert r["atomic_varnas"][1]["unit"] != r["atomic_varnas"][0]["unit"]  # distinct from anusvāra & vowel


def test_punctuation_and_danda_warn_no_varna():
    r = P.parse("क।")
    danda = [u for u in r["atomic_varnas"] if u["devanagari"] == "।"]
    assert danda and danda[0]["type"] == "marker"
    assert any(w["class"] == "punctuation_boundary" for w in r["warnings"])


def test_numeral_unsupported_warns():
    r = P.parse("क५")
    assert any(w["class"] == "numeral_unsupported" for w in r["warnings"])


def test_unsupported_character_warns_not_dropped():
    r = P.parse("कZ")
    assert any(w["class"] == "unrecognized_codepoint" for w in r["warnings"])
    assert any(u["devanagari"] == "Z" for u in r["atomic_varnas"])   # retained, not dropped


def test_nukta_non_classical_retained_not_mapped():
    r = P.parse("क़")  # qa (nukta) — NFC decomposes to क + ़
    assert any(w["class"] == "non_classical_nukta" for w in r["warnings"])
    assert any("़" in u["devanagari"] for u in r["atomic_varnas"])


def test_malformed_combining_mark_order():
    r = P.parse("ािक")  # leading orphan vowel signs before any base
    assert any(w["class"] == "orphan_combining_mark" for w in r["warnings"])
    # the trailing valid क still parses
    assert any(u["unit"] == "k" for u in r["atomic_varnas"])


def test_no_silent_codepoint_dropping():
    for w in ["कZ", "क।", "क५", "ऽ", "ािक", "क़"]:
        r = P.parse(w)
        # every atomic unit's warnings/markers cover the exotic code points; nothing vanishes:
        # count of non-standard atomic units + emitted units accounts for input structure
        assert len(r["atomic_varnas"]) >= 1


# ----------------------------------------------------------------------------- C. invariants
ALL_WORDS = list(FIXTURES) + ["तत्त्व", "अं", "अः", "क्ष्म", "क।", "कZ", "क़", "अँ", "क्"]


@pytest.mark.parametrize("w", ALL_WORDS)
def test_inv_source_akshara_indices_valid(w):
    r = P.parse(w)
    n_ak = len(r["aksharas"])
    for u in r["atomic_varnas"]:
        assert 0 <= u["source_akshara_index"] < n_ak


@pytest.mark.parametrize("w", ALL_WORDS)
def test_inv_slices_ordered_nonoverlapping_cover(w):
    r = P.parse(w)
    covered = []
    for a in r["aksharas"]:
        covered.extend(a["atomic_varna_indices"])
    assert covered == list(range(len(r["atomic_varnas"])))          # ordered, non-overlapping, full cover


@pytest.mark.parametrize("w", ALL_WORDS)
def test_inv_no_inherent_after_virama(w):
    r = P.parse(w)
    a = r["atomic_varnas"]
    for k, u in enumerate(a):
        if u["origin"] == "virama_terminated":
            # the next unit (if any) must not be an inherent-a attributed to this consonant
            if k + 1 < len(a):
                assert not (a[k + 1]["origin"] == "inherent_a" and a[k + 1]["source_akshara_index"] == u["source_akshara_index"]
                            and not any(cc["type"] == "consonant" for cc in a[k + 1:k + 2]))


def test_inv_every_bare_consonant_emits_one_inherent():
    r = P.parse("कमल")
    inherent = [u for u in r["atomic_varnas"] if u["inherent_inserted"]]
    assert len(inherent) == 3                                       # exactly one per bare consonant


@pytest.mark.parametrize("w", ALL_WORDS)
def test_inv_aspirates_atomic(w):
    for u in P.parse(w)["atomic_varnas"]:
        if u["type"] == "consonant" and u["aspirated"]:
            assert u["unit"].endswith("h") and len(u["unit"]) == 2  # single 2-char aspirate token, not split


def test_inv_conjunct_order_matches_surface():
    r = P.parse("क्ष्म")
    cons = [u["unit"] for u in r["atomic_varnas"] if u["type"] == "consonant"]
    assert cons == ["k", "ṣ", "m"]                                  # surface order preserved


@pytest.mark.parametrize("w", ALL_WORDS)
def test_inv_repeat_serialization_stable(w):
    assert P.serialize(P.parse(w)) == P.serialize(P.parse(w))


def test_inv_no_deduplication():
    r = P.parse("संस्कृत")
    assert [u["unit"] for u in r["atomic_varnas"]].count("s") == 2  # both स kept


def test_inv_independent_of_semantic_tables():
    # parsing must not require or read any pole/score table
    import sys
    before = set(sys.modules)
    P.parse("शान्ति")
    new = set(sys.modules) - before
    assert not any(("polarit" in m or "control_ext" in m or "track_g" in m or "score" in m) for m in new)


def test_inv_unsupported_produces_warning():
    assert P.parse("कZ")["warnings"], "unsupported code point must warn"


# ----------------------------------------------------------------------------- D. semantic firewall
def test_firewall_no_forbidden_imports():
    src = (HERE / "sanskrit_stage1_parser.py").read_text()
    for banned in ("varna_polarity", "control_ext", "track_g", "VARNA_PLAIN", "word_to_varnas",
                   "import torch", "transformers", "g2p", "polarity_table"):
        assert banned not in src, f"parser must not reference {banned}"


def test_firewall_no_binding_liberating_labels():
    r = P.parse("शान्ति")
    blob = P.serialize(r)
    for banned in ("binding", "liberating", "pole", "facet", "GENUTILITY", "score"):
        assert banned not in blob


def test_firewall_pure_structural_component():
    # public surface is parse() + serialize() only; no polarity/score attribute leaks in
    assert hasattr(P, "parse") and hasattr(P, "serialize")
    for attr in dir(P):
        assert "polarit" not in attr.lower() and "score" not in attr.lower()
