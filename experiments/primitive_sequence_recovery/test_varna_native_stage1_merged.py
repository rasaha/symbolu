"""Validation for the native Stage-1 merged lexicon + superseding audit. NO network, NO model.

Asserts the operator ruling was applied faithfully: v3.1 consonants preserved, lens vowels/am/ah imported verbatim
and marked authored, missing units explicit, no meaning authored, sources untouched, deterministic.
"""
import hashlib
import json
import pathlib

import build_varna_native_stage1_merged as B
import b1_stage1_native_merged_integration_audit as AUD

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MERGED_PATH = HERE / "frozen" / "varna_native_stage1_merged_v1.json"
LEX = json.load(open(ROOT / "varna_lens" / "lexicon_authoritative_varna.json", encoding="utf-8"))
V31 = json.load(open(HERE / "frozen" / "varna_polarity_table_v3_1_metadata_refreeze.json", encoding="utf-8"))["varnas"]

SRC_HASHES = {
    "frozen/varna_polarity_table_v3.json": "d3ff8efd0775b78c92b66bf11cd5eec75aaf4354015551be1c22d6ba8494d0b3",
    "frozen/varna_polarity_table_v3_1_metadata_refreeze.json": "9ac712a6afab2d9c1497ea5d085ccac28942fb093f355284ffb0ece55bd64b27",
}
LEX_HASH = "81cbf55faa81722262e58d8ff8d87262c49585bef27e1d803d3c2ff9962c09d6"


def _merged():
    B.build()
    return json.load(open(MERGED_PATH, encoding="utf-8"))


def _rows(m):
    return {r["canonical_parser_unit"]: r for r in m["rows"]}


# 1. all v3.1 consonant pole content field-identical in the merged artifact
def test_consonant_pole_content_identical_to_v31():
    m = _merged()
    for r in m["rows"]:
        if r["category"] == "consonant" and r["source_key"]:
            k = r["source_key"]
            assert r["binding_vritti"] == V31[k]["worldly_binding_distortion"]
            assert r["liberating_vritti"] == V31[k]["spiritual_liberating_reading"]
    assert m["consonant_pole_content_hash_matches_v31"] is True


# 2. sha, ssa, ha come from v3.1
def test_sha_ssa_ha_from_v31():
    rows = _rows(_merged())
    for iast, key in (("ś", "sha"), ("ṣ", "ssa"), ("h", "ha")):
        r = rows[iast]
        assert r["source_key"] == key
        assert r["source_artifact"].endswith("v3_1_metadata_refreeze.json")
        assert r["binding_vritti"] == V31[key]["worldly_binding_distortion"]


# 3. all 10 existing vowel identities resolve correctly
def test_ten_vowels_resolve():
    rows = _rows(_merged())
    for u in ("a", "ā", "i", "ī", "u", "ū", "e", "ai", "o", "au"):
        r = rows[u]
        assert r["category"] == "vowel" and r["source_key"] and r["binding_vritti"] and r["liberating_vritti"]
        assert r["binding_pole_provenance"] == "AUTHORED_PROVISIONAL"


# 4. ṃ -> am and ḥ -> ah
def test_anusvara_visarga_bridge():
    rows = _rows(_merged())
    assert rows["ṃ"]["source_key"] == "am" and rows["ṃ"]["category"] == "anusvara"
    assert rows["ḥ"]["source_key"] == "ah" and rows["ḥ"]["category"] == "visarga"


# 5. no parser unit collapses into another (canonical unit is unique)
def test_no_unit_collapse():
    m = _merged()
    units = [r["canonical_parser_unit"] for r in m["rows"]]
    assert len(units) == len(set(units))


# 6. vowel length distinctions remain separate
def test_vowel_length_separate():
    rows = _rows(_merged())
    for short, lng in (("a", "ā"), ("i", "ī"), ("u", "ū")):
        assert rows[short]["source_key"] != rows[lng]["source_key"]
        assert rows[short]["binding_vritti"] != rows[lng]["binding_vritti"]


# 7. missing vocalic sonorants + candrabindu remain explicit
def test_missing_units_explicit():
    rows = _rows(_merged())
    for u in ("ṛ", "ṝ", "l̥", "l̥̄", "m̐"):
        assert rows[u]["activation_scope"] == "MISSING"
        assert rows[u]["binding_vritti"] is None and rows[u]["source_key"] is None


# 8. no new meanings authored (vowels verbatim from lens; consonants verbatim from v3.1)
def test_no_new_meanings_authored():
    rows = _rows(_merged())
    bridge = {"a": "a", "ā": "aa", "i": "i", "ī": "ii", "u": "u", "ū": "uu", "e": "e", "ai": "ai", "o": "o", "au": "au",
              "ṃ": "am", "ḥ": "ah"}
    for u, key in bridge.items():
        e = LEX["vowels"][key]
        assert rows[u]["binding_vritti"] == e["binding_state"]
        assert rows[u]["liberating_vritti"] == e["liberating_state"]
    # authored vowels must NOT be relabelled attested
    for u in bridge:
        assert "ATTESTED" not in rows[u]["binding_pole_provenance"]


# 9. original source artifacts remain byte-identical
def test_sources_unmodified():
    for rel, h in SRC_HASHES.items():
        assert hashlib.sha256((HERE / rel).read_bytes()).hexdigest() == h
    assert hashlib.sha256((ROOT / "varna_lens" / "lexicon_authoritative_varna.json").read_bytes()).hexdigest() == LEX_HASH


# 10. deterministic generation
def test_deterministic():
    B.build(); h1 = hashlib.sha256(MERGED_PATH.read_bytes()).hexdigest()
    B.build(); h2 = hashlib.sha256(MERGED_PATH.read_bytes()).hexdigest()
    assert h1 == h2


# audit-level: coverage concepts distinct + verdicts
def test_audit_two_coverage_concepts_and_verdicts():
    r = AUD.build()
    s = r["coverage"]["structurally_resolvable_coverage"]["token_pct"]
    c = r["coverage"]["confirmatory_eligible_coverage"]["token_pct"]
    assert s > c                                  # structural must exceed confirmatory
    assert r["coverage"]["confirmatory_eligible_coverage"]["word_full_pct"] == 0.0
    assert r["integration_verdict"] == "NATIVE_STAGE1_MERGED_LEXICON_CREATED"
    assert r["readiness_verdict"] == "READY_FOR_NATIVE_WORD_MAPPING_REVIEW_WITH_PROVENANCE_LIMITS"
    assert set(r["unit_level_coverage"]["remaining_missing_units"]) == {"ṛ", "ṝ", "l̥", "l̥̄", "m̐"}
