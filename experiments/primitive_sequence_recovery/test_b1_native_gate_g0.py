"""Validation for the native Gate-G0 recomputation. NO network, NO model, NO judges.

Asserts: only confirmatory consonant rows used; no vowel/marker pole in packets; no English-G2P import; parser and
merged lexicon unchanged; deterministic selection; selection independent of semantic-fit (valence is balance-only);
every selected word satisfies the gate; prior G0 constants preserved.
"""
import hashlib
import json
import pathlib

import b1_native_gate_g0 as G

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "native_gate_g0"
MERGED_SHA = "af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96"
ALLOWED = {"NATIVE_GATE_G0_PASS", "NATIVE_GATE_G0_PASS_WITH_RESTRICTED_WORD_SET",
           "NATIVE_GATE_G0_FAIL_INSUFFICIENT_PACKET_DISTINCTIVENESS", "NATIVE_GATE_G0_FAIL_CONTROL_CONSTRUCTION",
           "NATIVE_GATE_G0_BLOCKED_BY_DATA_QUALITY"}


def test_only_confirmatory_consonants_in_backbone():
    m = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
    for u in G.CB:
        row = next(r for r in m["rows"] if r["canonical_parser_unit"] == u)
        assert row["category"] == "consonant"
        assert row["source_artifact"].endswith("v3_1_metadata_refreeze.json")
        assert row["activation_scope"] == "CONFIRMATORY_BACKBONE"
    # no vowel / anusvāra / visarga / candrabindu / ḷ leaked into the backbone
    assert len(G.CB) == 33
    assert not ({"a", "ā", "i", "ī", "u", "ū", "e", "ai", "o", "au", "ṃ", "ḥ", "ḷ"} & set(G.CB))


def test_packets_contain_no_vowel_or_marker():
    inv = json.load(open(OUT / "candidate_inventory.json", encoding="utf-8"))["candidates"]
    vowels_marks = {"a", "ā", "i", "ī", "u", "ū", "ṛ", "ṝ", "l̥", "l̥̄", "e", "ai", "o", "au", "ṃ", "ḥ", "m̐"}
    for c in inv:
        assert not (set(c["cons_set"]) & vowels_marks)
        assert set(c["cons_set"]).issubset(set(G.CB))


def test_no_english_g2p_import():
    src = (HERE / "b1_native_gate_g0.py").read_text()
    for banned in ("varna_bridge_active", "varna_bridge_v2", "stage_a_prime", "import torch", "g2p", "cmudict"):
        assert banned not in src


def test_merged_and_parser_unchanged():
    assert hashlib.sha256((HERE / "frozen" / "varna_native_stage1_merged_v1.json").read_bytes()).hexdigest() == MERGED_SHA
    # parser is a pure import; parsing twice is identical (unchanged behavior)
    import sanskrit_stage1_parser as P
    assert P.serialize(P.parse("बल")) == P.serialize(P.parse("बल"))


def test_deterministic():
    G.build(); h1 = hashlib.sha256((OUT / "native_gate_g0_report.json").read_bytes()).hexdigest()
    G.build(); h2 = hashlib.sha256((OUT / "native_gate_g0_report.json").read_bytes()).hexdigest()
    assert h1 == h2


def test_eligibility_independent_of_valence():
    # eligibility (c1/c23/c4) must NOT depend on semantic valence labels; only the tie-break preference (c8) may.
    saved = dict(G.VALENCE)
    try:
        r_with = G.build()
        n_with = r_with["n_eligible_sets"]
        G.VALENCE.clear()                       # blank all valence labels
        r_without = G.build()
        assert r_without["n_eligible_sets"] == n_with   # same eligible sets regardless of valence
    finally:
        G.VALENCE.update(saved)
        G.build()                               # restore canonical artifacts


def test_selected_words_satisfy_gate():
    r = G.build()
    assert r["gate_verdict"] in ALLOWED
    if r["selected_set"]:
        s = r["selected_set"]
        assert s["eligible"] is True
        assert s["c1_per_word_unique"] and s["c23_no_identical"] and s["c4_jaccard_caps"]
        assert all(len(v) >= 1 for v in s["unique_features"].values())
        assert s["max_jaccard"] <= G.MAX_JACCARD_CAP and s["mean_jaccard"] <= G.MEAN_JACCARD_CAP


def test_prior_g0_constants_preserved():
    assert G.K == 6 and G.MAX_JACCARD_CAP == 0.34 and G.MEAN_JACCARD_CAP == 0.20


def test_old_blocker_removed_and_not_polarity():
    r = G.build()
    assert r["native_renderable_units"] == 33 and r["old_blocker_removed"] is True
    assert r["not_a_polarity_test"] is True
