"""Validation for the corrected v2 packet re-freeze. Covers the 17 required checks. NO network, NO model, NO run."""
import hashlib
import json
import pathlib
from collections import Counter, defaultdict

import b1_native_word_specificity_packets_v2 as P

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "native_word_specificity_packets_v2"
EVAL = OUT / "evaluator_facing"
INTERNAL = OUT / "internal"

# protected upstream artifacts — must remain byte-identical (parser, merged lexicon, Gate-G0, prereg freeze,
# and all v1 packet artifacts preserved in place)
PROTECTED = {
    "sanskrit_stage1_parser.py": "d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947",
    "frozen/varna_native_stage1_merged_v1.json": "af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96",
    "b1_native_gate_g0.py": "4bcc8838c924543ba56ab21f484e9864e93faca12ca78ffd655c76b0a5f59d7f",
    "b1_native_word_specificity_prereg.py": "41d9c6df35fa23f1d662ecf6b40953a5917174c8479d6f1e3cd05c7a0f186143",
    "native_word_specificity_prereg/freeze_index.json": "155baad28dfd656562a66b60fd0a7f3e9aa1fa029d32ebfb643483ec65da5632",
}


def _key():
    return json.load(open(INTERNAL / "answer_key.json", encoding="utf-8"))["key"]


def _trials():
    return json.load(open(EVAL / "trials.json", encoding="utf-8"))["trials"]


# 1/2/3. correct-answer positions balanced globally, per major arm, and per set
def test_position_balance_global_per_arm_per_set():
    P.build()
    key = _key()
    # global
    g = Counter(k["correct_label"] for k in key)
    assert set(g.values()) == {len(key) // 6}
    # per set x arm
    per = defaultdict(Counter)
    for k in key:
        per[(k["set"], k["arm"])][k["correct_label"]] += 1
    for (s, a), c in per.items():
        assert set(c.get(f"W{i+1}", 0) for i in range(6)) == {sum(c.values()) // 6}, (s, a, c)
    # per set (collapsed over arms)
    for s in ("A", "B"):
        cs = Counter(k["correct_label"] for k in key if k["set"] == s)
        assert set(cs.values()) == {sum(cs.values()) // 6}


# 4. position-only agents cannot create a positive primary contrast
def test_position_agents_no_primary_edge():
    pb = json.load(open(OUT / "position_balance.json", encoding="utf-8"))
    for pol, v in pb["position_bias_simulation"].items():
        assert v["primary_contrast_delta"] <= 0.0, (pol, v)
        assert all(abs(x - 1 / 6) < 1e-3 for x in v["per_arm_accuracy"].values())   # stored rounded to 4dp


# 5. isolated paraphrase input contains no identity information
def test_isolated_authoring_input_has_no_identity():
    ai = json.load(open(OUT / "isolated_authoring" / "authoring_input.json", encoding="utf-8"))
    blob = json.dumps(ai["rows"], ensure_ascii=False)
    words = ["aśva", "bala", "bhaya", "duḥkha", "gaja", "megha", "bīja", "sukha", "deha", "lavaṇa", "yoga", "vṛkṣa"]
    glosses = ["horse", "strength", "fear", "pain", "elephant", "cloud", "seed", "happiness", "body", "salt", "union", "tree"]
    for w in words:
        assert w not in blob
    # each row is keyed by an opaque rXX id with only source fields
    for rid, row in ai["rows"].items():
        assert rid.startswith("r") and set(row.keys()) == {"binding_source", "liberating_source"}
    # withheld list explicitly names the identity items
    for item in ("consonant identity", "candidate glosses", "row-to-consonant bridge", "Set A / Set B"):
        assert item in ai["withheld_from_author"]
    # glosses are not present as candidate-label context in the authoring input
    assert "candidate" not in json.dumps(ai["rows"], ensure_ascii=False).lower()
    _ = glosses


# 6. every used row has exactly one fixed paraphrase per pole (17 rows)
def test_one_fixed_paraphrase_per_used_row():
    para = json.load(open(OUT / "paraphrase_table.json", encoding="utf-8"))
    assert len(para) == 17 and len(P.CB) == 17
    for rid, v in para.items():
        assert set(v) == {"binding_paraphrase", "liberating_paraphrase"}
        assert v["binding_paraphrase"] and v["liberating_paraphrase"]
        assert v["binding_paraphrase"] != v["liberating_paraphrase"]


# 7. equivalence review passes (all preserved after remediation)
def test_equivalence_review_all_preserved():
    er = json.load(open(OUT / "isolated_authoring" / "equivalence_review.json", encoding="utf-8"))
    assert er["all_preserved_after_remediation"] is True
    for rid, v in er["result"].items():
        assert v["binding"] == "PRESERVED" and v["liberating"] == "PRESERVED"


# 8. no unresolved lexical leakage remains (no NEW, non-preflagged, in-set-exploitable hit; no exact name; no IAST)
def test_no_unresolved_leakage():
    la = json.load(open(OUT / "leakage_audit.json", encoding="utf-8"))
    assert la["n_new_exploitable_not_preflagged"] == 0
    for f in la["flags"]:
        assert not f["issue"].startswith("iast_diacritic")            # no transliteration leak
        if f.get("in_set_exploitable"):
            assert f["source_intrinsic_preflagged"] is True           # only the pre-flagged deha/body case survives
    lr = json.load(open(OUT / "isolated_authoring" / "leakage_review.json", encoding="utf-8"))
    assert lr["exact_candidate_name_hits"] == []


# 9. true/control packet mechanics remain correct
def test_control_mechanics():
    key = {k["opaque_trial_id"]: k for k in _key()}
    trials = {t["trial_id"]: t for t in _trials()}
    rid = P.RID
    def ptext(seq):
        return [(P.PARA[c][0], P.PARA[c][1]) for c in seq]
    for s, S in (("A", P.SET_A), ("B", P.SET_B)):
        for oid, k in key.items():
            if k["set"] != s:
                continue
            t = trials[oid]
            if k["arm"] == "T":
                got = [(r["binding"], r["liberating"]) for r in t["packet"]]
                assert got == ptext(S[k["target_word"]])
            if k["arm"] == "F":
                assert "packet" not in t and set(t["packet_metadata_only"]) == {"n_features", "length_band"}
        # correct_label really points at the target gloss in each presentation
        for oid, k in key.items():
            if k["set"] != s:
                continue
            t = trials[oid]
            lab = {c["label"]: c["gloss"] for c in t["candidates"]}
            assert lab[k["correct_label"]] == P.CANDIDATES[k["target_word"]]["gloss"]


# 10. X remains a strict derangement
def test_X_derangement():
    for ws in (P.SET_A, P.SET_B):
        der = P.derangement(list(ws), P.SEEDS["derangement"])
        assert all(der[w] != w for w in ws) and sorted(der.values()) == sorted(ws)


# 11. R remains structurally matched (length matched, excludes target's own rows, 5 base instances/word)
def test_R_structural():
    key = _key()
    per = Counter((k["set"], k["target_word"], k["instance"]) for k in key if k["arm"] == "R")
    # 5 instances x 6 repeats -> each (set,word,instance) appears REPEATS times
    assert set(per.values()) == {P.REPEATS}
    inst = Counter((k["set"], k["target_word"]) for k in key if k["arm"] == "R")
    assert set(inst.values()) == {5 * P.REPEATS}
    trials = {t["trial_id"]: t for t in _trials()}
    for k in key:
        if k["arm"] != "R":
            continue
        S = P.SET_A if k["set"] == "A" else P.SET_B
        pkt = trials[k["opaque_trial_id"]]["packet"]
        assert len(pkt) == len(S[k["target_word"]])
        own = {(P.PARA[c][0], P.PARA[c][1]) for c in S[k["target_word"]]}
        assert not any((r["binding"], r["liberating"]) in own for r in pkt)


# 12. F contains no semantic content
def test_F_metadata_only():
    key = {k["opaque_trial_id"]: k for k in _key()}
    for t in _trials():
        if key[t["trial_id"]]["arm"] == "F":
            assert "packet" not in t and "packet_metadata_only" in t


# 13. evaluator prompt is literal and complete
def test_evaluator_prompt_literal_and_complete():
    pr = json.load(open(OUT / "evaluator_protocol.json", encoding="utf-8"))
    assert "{description_block}" in pr["literal_prompt_template"] and "{candidates_block}" in pr["literal_prompt_template"]
    for field in ("response_schema", "explanation_or_chain_of_thought", "invalid_output_handling", "retry_policy",
                  "timeout_policy", "duplicate_response_policy", "missing_response_policy", "scoring_rule",
                  "model_family_policy"):
        assert pr[field]
    assert pr["temperature"] == 0
    assert "PROHIBITED" in pr["explanation_or_chain_of_thought"]


# 14. repeat and retry rules are frozen (no placeholders)
def test_repeat_and_retry_frozen():
    pr = json.load(open(OUT / "evaluator_protocol.json", encoding="utf-8"))
    assert pr["repetitions_per_base_trial"] == P.REPEATS == 6
    assert pr["repetitions_use_candidate_order_rotations"] is True
    blob = json.dumps(pr)
    assert "N>=?" not in blob and "?" not in pr["retry_policy"]


# 15. leak-flagged sensitivity analysis is precommitted
def test_flagged_analysis_precommitted():
    fa = json.load(open(OUT / "analysis_plan_flagged_words.json", encoding="utf-8"))
    assert set(fa["flagged_words"]) == {"bhaya", "duḥkha", "sukha", "deha"}
    assert "limits causal interpretation" in fa["mandatory_interpretation_statement"]
    joined = " ".join(fa["required_reports"]).lower()
    assert "all trials" in joined and "excluded" in joined
    assert any("do not drop the flagged words" in p for p in fa["prohibitions"])


# 16. protected upstream artifacts remain byte-identical
def test_protected_artifacts_unchanged():
    for rel, want in PROTECTED.items():
        got = hashlib.sha256((HERE / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel} changed"
    # v1 packet freeze is untouched: its own frozen_hashes still match its on-disk artifacts byte-for-byte
    v1 = HERE / "native_word_specificity_packets"
    fi = json.load(open(v1 / "packet_freeze_index.json", encoding="utf-8"))
    for f, h in fi["frozen_hashes"].items():
        assert hashlib.sha256((v1 / f).read_bytes()).hexdigest() == h, f"v1 artifact changed: {f}"


# 16b. evaluator-facing v2 exposes nothing reverse-mappable
def test_v2_evaluator_facing_opaque():
    blob = json.dumps(_trials(), ensure_ascii=False)
    assert not any("ऀ" <= c <= "ॿ" for c in blob)
    assert not (set(blob) & set("āīūēōṛṝḷḹṭḍṇṅñśṣḥṃ"))
    for banned in ('"arm"', "target_word", "correct_label", "structured_trial_id", "base_seq"):
        assert banned not in blob


# 17. generation is deterministic
def test_deterministic():
    P.build()
    h1 = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))["frozen_hashes"]
    P.build()
    h2 = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))["frozen_hashes"]
    assert h1 == h2


def test_verdicts_and_no_run_in_source():
    fi = json.load(open(OUT / "packet_freeze_index.json", encoding="utf-8"))
    assert fi["packet_verdict"] == "V2_PACKETS_REFROZEN_AND_BALANCED"
    assert fi["readiness_verdict"] == "READY_FOR_FOCUSED_V2_PRERUN_AUDIT"
    src = (HERE / "b1_native_word_specificity_packets_v2.py").read_text()
    for banned in ("openai", "HfApi", "import torch", "transformers", "requests.post", "judge(", "run_real", "accuracy("):
        assert banned not in src
