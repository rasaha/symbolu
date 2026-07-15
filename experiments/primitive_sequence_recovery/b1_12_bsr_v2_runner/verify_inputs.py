#!/usr/bin/env python3
"""V2 hard input verification. Returns ('OK', details) or ('RUN_INVALID_INPUT_MISMATCH', reasons).
Gates the frozen V2 prereg hash, parser, v3 mapping, the fresh v2 word list, and no-reuse of the v1 BSR words."""
from __future__ import annotations
import json, hashlib, pathlib

EXPT = pathlib.Path(__file__).resolve().parent.parent
WORDLIST_DIR = EXPT / "b1_12_symbolic_resonance_wordlist_v2"
WORDLIST_JSON = WORDLIST_DIR / "included_wordlist.json"
PARSER = EXPT / "sanskrit_stage1_parser.py"
LEXICON = EXPT / "frozen" / "varna_native_stage1_merged_v3.json"
PREREG = EXPT / "VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md"
FREEZE = EXPT / "B1_12_V2_PREREG_FREEZE.md"
V1_WORDLIST = EXPT / "b1_12_symbolic_resonance_wordlist_v1" / "included_wordlist.json"

EXPECT_WORDLIST_SHA = "7a558008a22151a48f7770790bbfb01cdef190b64d3ae6feb8677b0b360457b4"
EXPECT_PARSER_SHA = "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947"
EXPECT_LEXICON_SHA = "65116f371aca9f24ba2cce080c458a7a878f9af4ae50562d3f518567e681d33f"
EXPECT_PREREG_SHA = "831e48ecc409140f64a943c0331242043424045c703d01be1cd4c55dcfb59550"
EXPECT_N = 20

def _sha_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

def _wordlist_hash(words):
    canon = sorted([{"iast": w["iast"], "dev": w["dev"], "gloss": w["gloss"], "category": w["category"]}
                    for w in words], key=lambda x: x["iast"])
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def verify():
    reasons = []
    for p in (WORDLIST_JSON, PARSER, LEXICON, PREREG, FREEZE):
        if not pathlib.Path(p).exists():
            reasons.append(f"missing_file:{pathlib.Path(p).name}")
    if reasons:
        return "RUN_INVALID_INPUT_MISMATCH", reasons

    wl = json.load(open(WORDLIST_JSON, encoding="utf-8"))
    words = wl["words"]
    wl_hash = _wordlist_hash(words)
    if wl_hash != EXPECT_WORDLIST_SHA:
        reasons.append(f"wordlist_hash_mismatch:{wl_hash}")
    if wl.get("wordlist_sha256") not in (None, EXPECT_WORDLIST_SHA):
        reasons.append("wordlist_manifest_hash_mismatch")
    if len(words) != EXPECT_N:
        reasons.append(f"word_count:{len(words)}")
    if _sha_file(PARSER) != EXPECT_PARSER_SHA:
        reasons.append("parser_hash_mismatch")
    if _sha_file(LEXICON) != EXPECT_LEXICON_SHA:
        reasons.append("lexicon_v3_hash_mismatch")
    if _sha_file(PREREG) != EXPECT_PREREG_SHA:
        reasons.append("prereg_v2_hash_mismatch")
    # no reuse of the v1 BSR words
    if V1_WORDLIST.exists():
        v1 = {w["iast"] for w in json.load(open(V1_WORDLIST, encoding="utf-8"))["words"]}
        overlap = sorted({w["iast"] for w in words} & v1)
        if overlap:
            reasons.append(f"v1_reuse_overlap:{overlap}")

    if reasons:
        return "RUN_INVALID_INPUT_MISMATCH", reasons
    return "OK", {
        "wordlist_sha256": wl_hash,
        "parser_sha256": _sha_file(PARSER),
        "lexicon_v3_sha256": _sha_file(LEXICON),
        "prereg_v2_sha256": _sha_file(PREREG),
        "freeze_record_sha256": _sha_file(FREEZE),
        "n_words": len(words),
        "words": [w["iast"] for w in words],
    }

if __name__ == "__main__":
    status, details = verify()
    print(status)
    print(json.dumps(details, ensure_ascii=False, indent=2))
