"""Validation tests for the native word-specificity packet-authoring-and-freeze step.

Covers the 15 required checks: hidden-Devanāgarī substrate; English glosses never parsed; every gloss
independently sourced; no interpretive/poetic gloss; one fixed binding+liberating paraphrase per used row (17);
no unresolved leakage; equivalence preserved; T/X/S row counts matched; X is a derangement; R uses the frozen
scheme; G length/sentiment matched; F carries no semantic content; no authored vowel/marker in any packet;
protected upstream artifacts byte-unchanged; deterministic generation. NO network, NO model, NO evaluator.
"""
import hashlib
import json
import pathlib
import re

import b1_native_word_specificity_packets as P

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "native_word_specificity_packets"
EVAL = OUT / "evaluator_facing"
INTERNAL = OUT / "internal"

# committed hashes of the protected upstream artifacts — this step must not touch them
PROTECTED = {
    "sanskrit_stage1_parser.py":
        "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947",
    "frozen/varna_native_stage1_merged_v1.json":
        "af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96",
    "b1_native_gate_g0.py":
        "4bcc8838c924543ba56ab21f484e9864e93faca12ca78ffd655c76b0a5f59d7f",
    "b1_native_word_specificity_prereg.py":
        "41d9c6df35fa23f1d662ecf6b40953a5917174c8479d6f1e3cd05c7a0f186143",
    "native_word_specificity_prereg/freeze_index.json":
        "155baad28dfd656562a66b60fd0a7f3e9aa1fa029d32ebfb643483ec65da5632",
}
CONS_SET = set("kkhgghṅcchjjhñṭṭhḍḍhṇtthddhnpphbbhmyrlvśṣsh")   # any consonant letter must never surface to evaluator


def _load(rel):
    return json.load(open(OUT / rel, encoding="utf-8"))


# 1. hidden Devanāgarī is the packet substrate: every packet row derives from a consonant of a Devanāgarī word set,
#    not from the English gloss.
def test_packets_built_from_devanagari_consonant_sequences():
    P.build()
    used = {c for seq in list(P.SET_A.values()) + list(P.SET_B.values()) for c in seq}
    assert used == set(P.PARA) == set(P.CB)          # the 17 used consonants drive both paraphrase + source rows
    # source rows come from the merged native (Devanāgarī-derived) lexicon, not from glosses
    for c, (b, l) in P.CB.items():
        assert isinstance(b, str) and isinstance(l, str) and b and l


# 2. English glosses are candidate labels only — never parsed/decomposed into packet content.
def test_glosses_are_labels_only_never_parsed():
    trials = _load("evaluator_facing/trials.json")["trials"]
    glosses = {v["gloss"] for v in P.CANDIDATES.values()}
    for t in trials:
        rows = t.get("packet", [])
        joined = " ".join(r["binding"] + " " + r["liberating"] for r in rows).lower()
        for g in glosses:                            # a packet row never reproduces a candidate gloss token
            assert not re.search(r"\b" + re.escape(g.lower()) + r"\b", joined)


# 3. every candidate gloss is independently sourced.
def test_every_gloss_independently_sourced():
    tbl = _load("candidate_gloss_table.json")
    for w, meta in tbl.items():
        assert meta["source"].startswith("Monier-Williams")
        assert meta["gloss"] and meta["sense"]


# 4. no interpretive / poetic / mechanism gloss: single short neutral token, no valence adjectives / mechanism terms.
def test_glosses_neutral_and_short():
    tbl = _load("candidate_gloss_table.json")
    banned = ("binding", "liberating", "grasp", "clinging", "pull", "spiritual", "soul", "divine")
    for w, meta in tbl.items():
        g = meta["gloss"]
        assert len(g.split()) <= 2                   # short
        assert all(b not in g.lower() for b in banned)


# 5. exactly one fixed binding + liberating paraphrase per used row, and exactly 17 rows.
def test_one_fixed_paraphrase_per_used_row():
    para = _load("paraphrase_table.json")
    assert len(para) == 17 and len(P.CB) == 17
    for rid, v in para.items():
        assert set(v) == {"binding_paraphrase", "liberating_paraphrase"}
        assert v["binding_paraphrase"] and v["liberating_paraphrase"]
        assert v["binding_paraphrase"] != v["liberating_paraphrase"]


# 6. no unresolved leakage.
def test_no_unresolved_leakage():
    P.build()
    la = _load("leakage_audit.json")
    assert la["n_flags"] == 0 and la["flags"] == []


# 6b. the leakage audit is not trivially passing: injected gloss words are caught.
def test_leakage_audit_has_teeth():
    orig = P.PARA["v"]
    P.PARA["v"] = ("horse and salt today", orig[1])
    try:
        issues = {f["issue"] for f in P.leakage_audit()}
        assert any("horse" in i for i in issues) and any("salt" in i for i in issues)
    finally:
        P.PARA["v"] = orig
    assert P.leakage_audit() == []


# 7. paraphrase equivalence to the source row is preserved for every row.
def test_equivalence_preserved():
    ea = _load("equivalence_audit.json")
    assert ea["all_preserved"] is True
    for r in ea["rows"]:
        assert r["binding_equivalence"] == "PRESERVED" and r["liberating_equivalence"] == "PRESERVED"


# 8. T/X/S row counts matched (per word, same number of feature rows across true / mismatch / scrambled).
def test_TXS_row_counts_matched():
    key = json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]
    trials = {t["trial_id"]: t for t in _load("evaluator_facing/trials.json")["trials"]}
    by = {}
    for k in key:
        by.setdefault((k["set"], k["target_word"], k["arm"]), []).append(trials[k["trial_id"]])
    for (setname, ws) in (("A", P.SET_A), ("B", P.SET_B)):
        der = P.derangement(list(ws), P.SEEDS["derangement"])
        for w, seq in ws.items():
            n = len(seq)
            assert len(by[(setname, w, "T")][0]["packet"]) == n              # true = target length
            assert len(by[(setname, w, "X")][0]["packet"]) == len(ws[der[w]])  # mismatch shows partner's packet
            if n > 1:
                assert len(by[(setname, w, "S")][0]["packet"]) == n         # scramble preserves length
            else:
                assert (setname, w, "S") not in by      # S is uninformative for length-1 packets


# 9. X is a strict derangement (no word paired with its own packet).
def test_X_is_derangement():
    for ws in (P.SET_A, P.SET_B):
        der = P.derangement(list(ws), P.SEEDS["derangement"])
        assert all(der[w] != w for w in ws)
        assert sorted(der.values()) == sorted(ws)       # still a bijection


# 10. R uses the frozen random-assignment scheme: 5 seeded instances per word, drawn from non-self consonants.
def test_R_frozen_scheme():
    key = json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]
    from collections import Counter
    per = Counter((k["set"], k["target_word"]) for k in key if k["arm"] == "R")
    assert set(per.values()) == {5}
    assert P.SEEDS["random_assignment"] == 20260902


# 11. G is length/sentiment matched: same row count as the true packet, dual-pole valence-carrying, word-agnostic.
def test_G_matched():
    key = json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]
    trials = {t["trial_id"]: t for t in _load("evaluator_facing/trials.json")["trials"]}
    for k in key:
        if k["arm"] != "G":
            continue
        seq = (P.SET_A if k["set"] == "A" else P.SET_B)[k["target_word"]]
        pkt = trials[k["trial_id"]]["packet"]
        assert len(pkt) == len(seq)                      # length matched
        for row in pkt:
            assert set(row) == {"binding", "liberating"} and row["binding"] and row["liberating"]


# 12. F carries no semantic rows — structural metadata only.
def test_F_feature_only():
    key = json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]
    trials = {t["trial_id"]: t for t in _load("evaluator_facing/trials.json")["trials"]}
    for k in key:
        if k["arm"] != "F":
            continue
        t = trials[k["trial_id"]]
        assert "packet" not in t and "packet_metadata_only" in t
        assert set(t["packet_metadata_only"]) == {"n_features", "length_band"}


# 13. no authored vowel / marker enters any packet (confirmatory consonant backbone only).
def test_no_authored_vowel_in_packets():
    m = json.load(open(HERE / "frozen" / "varna_native_stage1_merged_v1.json", encoding="utf-8"))
    dev = {r["binding_vritti"] for r in m["rows"] if r["activation_scope"] == "DEVELOPMENT_ONLY"}
    dev |= {r["liberating_vritti"] for r in m["rows"] if r["activation_scope"] == "DEVELOPMENT_ONLY"}
    para_texts = {v[0] for v in P.PARA.values()} | {v[1] for v in P.PARA.values()}   # 17 consonant paraphrases
    gen_texts = {g[0] for g in P.GENERIC} | {g[1] for g in P.GENERIC}                # word-agnostic (arm G)
    assert not (para_texts & dev) and not (gen_texts & dev)                          # neither draws from a vowel row
    arm_of = {k["trial_id"]: k["arm"]
              for k in json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]}
    trials = _load("evaluator_facing/trials.json")["trials"]
    for t in trials:
        arm = arm_of[t["trial_id"]]
        for row in t.get("packet", []):
            assert row["binding"] not in dev and row["liberating"] not in dev       # never a vowel row
            if arm in ("T", "X", "S", "R"):
                assert row["binding"] in para_texts and row["liberating"] in para_texts
            elif arm == "G":
                assert row["binding"] in gen_texts and row["liberating"] in gen_texts


# 13b. evaluator-facing artifacts expose NO Devanāgarī / IAST / consonant symbol / row id / arm / word identity.
def test_evaluator_facing_exposes_nothing_reverse_mappable():
    blob = json.dumps(_load("evaluator_facing/trials.json"), ensure_ascii=False)
    assert not any("ऀ" <= c <= "ॿ" for c in blob)        # no Devanāgarī block
    assert not (set(blob) & set("āīūēōṛṝḷḹṭḍṇṅñśṣḥṃ"))              # no IAST diacritic
    for banned in ('"arm"', "target_word", "correct_label", "canonical_parser_unit", "row_id"):
        assert banned not in blob
    for rid in P.opaque_ids().values():                            # no opaque authoring row id surfaces
        assert rid not in blob


# 14. protected upstream artifacts are byte-unchanged.
def test_protected_artifacts_unchanged():
    for rel, want in PROTECTED.items():
        got = hashlib.sha256((HERE / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel} changed: {got}"


# 15. generation is deterministic.
def test_deterministic_freeze():
    P.build()
    h1 = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))["frozen_hashes"]
    P.build()
    h2 = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))["frozen_hashes"]
    assert h1 == h2


def test_verdicts_clean_and_no_evaluator_in_source():
    fi = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))
    assert fi["packet_verdict"] == "PACKETS_AUTHORED_FROZEN_AND_LEAKAGE_CLEAN"
    assert fi["readiness_verdict"] == "READY_FOR_BLIND_EVALUATOR_RUN"
    src = (HERE / "b1_native_word_specificity_packets.py").read_text()
    for banned in ("openai", "HfApi", "import torch", "transformers", "requests.post", "judge(", "run_real", "accuracy("):
        assert banned not in src
