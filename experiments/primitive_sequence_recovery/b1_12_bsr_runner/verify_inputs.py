#!/usr/bin/env python3
"""Hard input verification. Returns ('OK', details) or ('RUN_INVALID_INPUT_MISMATCH', reasons)."""
from __future__ import annotations
import json, hashlib, pathlib

EXPT = pathlib.Path(__file__).resolve().parent.parent
WORDLIST_DIR = EXPT / "b1_12_symbolic_resonance_wordlist_v1"
WORDLIST_JSON = WORDLIST_DIR / "included_wordlist.json"
PARSER = EXPT / "sanskrit_stage1_parser.py"
LEXICON = EXPT / "frozen" / "varna_native_stage1_merged_v3.json"
PREREG = EXPT / "VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md"
SCOPE = EXPT / "B1_12_SCOPE_UPDATE_AND_CONTROLLING_PREREG.md"
OLD60 = EXPT / "varna_affliction_pilot_run_v1" / "symbolic_resonance_scores.json"

EXPECT_WORDLIST_SHA = "9779384dcb82e0c6d86fa88ed1f000317ed387ea5f227cb32f96f38b95f8a6ba"
EXPECT_PARSER_SHA = "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
EXPECT_LEXICON_SHA = "65116f371aca9f24ba2cce080c458a7a878f9af4ae50562d3f518567e681d33f"
EXPECT_N = 20

def _sha_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def _wordlist_hash(words):
    canon = sorted([{"iast": w["iast"], "dev": w["dev"], "gloss": w["gloss"], "category": w["category"]}
                    for w in words], key=lambda x: x["iast"])
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def verify():
    reasons = []
    for p in (WORDLIST_JSON, PARSER, LEXICON, PREREG, SCOPE):
        if not pathlib.Path(p).exists():
            reasons.append(f"missing_file:{pathlib.Path(p).name}")
    if reasons:
        return "RUN_INVALID_INPUT_MISMATCH", reasons

    wl = json.load(open(WORDLIST_JSON, encoding="utf-8"))
    words = wl["words"]
    # 1. recomputed word-list hash matches the frozen value
    wl_hash = _wordlist_hash(words)
    if wl_hash != EXPECT_WORDLIST_SHA:
        reasons.append(f"wordlist_hash_mismatch:{wl_hash}")
    if wl.get("wordlist_sha256") not in (None, EXPECT_WORDLIST_SHA):
        reasons.append("wordlist_manifest_hash_mismatch")
    # 4. all 20 present/unchanged
    if len(words) != EXPECT_N:
        reasons.append(f"word_count:{len(words)}")
    # 3. parser + v3 mapping-table hashes
    if _sha_file(PARSER) != EXPECT_PARSER_SHA:
        reasons.append("parser_hash_mismatch")
    if _sha_file(LEXICON) != EXPECT_LEXICON_SHA:
        reasons.append("lexicon_v3_hash_mismatch")
    # 5. no word belongs to the old 60-word calibration set
    if OLD60.exists():
        old = {r["word"] for r in json.load(open(OLD60, encoding="utf-8"))}
        overlap = sorted({w["iast"] for w in words} & old)
        if overlap:
            reasons.append(f"old60_overlap:{overlap}")

    if reasons:
        return "RUN_INVALID_INPUT_MISMATCH", reasons
    return "OK", {
        "wordlist_sha256": wl_hash,
        "parser_sha256": _sha_file(PARSER),
        "lexicon_v3_sha256": _sha_file(LEXICON),
        "prereg_sha256": _sha_file(PREREG),
        "scope_sha256": _sha_file(SCOPE),
        "n_words": len(words),
        "words": [w["iast"] for w in words],
    }

if __name__ == "__main__":
    status, details = verify()
    print(status)
    print(json.dumps(details, ensure_ascii=False, indent=2))
