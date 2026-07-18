#!/usr/bin/env python3
"""Deterministic tests for the Symbol-U bridge core — no models. Run: python -m pytest test_bridge_core.py -q"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bridge_core as B

def test_known_concern_resolves_and_maps():
    r = B.bridge(concern_id="C0016")          # money-concern -> dhana
    assert r["status"] == "OK"
    assert r["sanskrit_word"] == "dhana" and r["iast"] == "dhana"
    assert len(r["mapping_glosses"]) >= 1
    assert all(g["mapping_gloss"] for g in r["mapping_glosses"])

def test_unknown_concern_abstains():
    r = B.bridge(concern_id="C9999")
    assert r["status"] == "NO_APPLICABLE_CONCEPT"
    assert r["mapping_glosses"] == []

def test_direct_concept_word():
    r = B.bridge(concept_word="शान्ति")        # śānti
    assert r["status"] == "OK" and r["iast"] == "śānti"
    assert len(r["mapping_glosses"]) >= 1

def test_tier1_flag_present():
    r = B.bridge(concept_word="द्वेष")          # dveṣa: d and v are B1.12 Tier-1
    tiers = {g["varna"]: g["b1_12_tier1"] for g in r["mapping_glosses"]}
    assert tiers.get("d") is True and tiers.get("v") is True

def test_all_25_concerns_map():
    _, _, concepts, _ = B.load_frozen()
    assert len(concepts) == 25
    for cid in concepts:
        r = B.bridge(concern_id=cid)
        assert r["status"] == "OK", (cid, r["status"])   # every seed concept has >=1 mapped consonant

def test_deterministic():
    a = B.bridge(concern_id="C0001"); b = B.bridge(concern_id="C0001")
    assert a["mapping_glosses"] == b["mapping_glosses"]

def test_provenance_hashes_present():
    r = B.bridge(concern_id="C0025")
    p = r["provenance"]
    assert p["parser_sha256"] == B.EXPECT["parser"]
    assert p["lexicon_v3_sha256"] == B.EXPECT["lexicon"]
