"""Promotion-integrity tests for Fidelity Bundle v1 (step-12 assertions).

Covers: v3 table active; retroflex works; /θ,ð/->ta (not tha); aspiration EXCLUDED;
dread sequence da,ra,da -> dda,ra,da; historical v2/v1 artifacts byte-unchanged;
prior result records unchanged; guardrails intact.

Resonance / phonetic-fidelity refinement only. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL,
no semantic-truth / ontology / Sanskrit-privilege claim. Structure, not validated meaning.
"""
import hashlib
import json
import pathlib

import varna_bridge_active as AB

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _load(p):
    return json.loads(pathlib.Path(p).read_text())


# ---------------------------------------------------------------- active labels
def test_active_labels():
    lb = AB.labels()
    assert lb["mapping_era"] == "fidelity_bundle_v1"
    assert lb["table"] == "v3"
    assert lb["bridge"] == "bridge_v2_plus_theta_eth_ta"
    assert lb["aspiration_applied"] is False


# ---------------------------------------------------------------- v3 table active
def test_v3_table_active():
    t = _load(FROZEN / "varna_polarity_table_v3.json")
    assert t["status"] == "ACTIVE_APPLIED"
    assert t["applied"] is True
    assert t["mapping_era"] == "fidelity_bundle_v1"
    assert len(t["varnas"]) == 34
    # retroflex keys present in the table
    assert "dda" in t["varnas"] and "tta" in t["varnas"]


# ---------------------------------------------------------------- retroflex works
def test_retroflex_rule():
    assert AB.word_to_varnas("drum") == ["dda", "ra", "ma"]
    assert AB.word_to_varnas("train") == ["tta", "ra", "na"]
    assert AB.word_to_varnas("dread") == ["dda", "ra", "da"]


# ---------------------------------------------------------------- /θ,ð/ -> ta, not tha
def test_theta_eth_maps_to_ta_not_tha():
    for w, expect in [("the", ["ta"]), ("this", ["ta", "sa"]),
                      ("path", ["pa", "ta"]), ("mother", ["ma", "ta", "ra"])]:
        got = AB.word_to_varnas(w)
        assert got == expect, f"{w}: {got} != {expect}"
        assert "tha" not in got, f"{w} introduced aspirated tha"


def test_theta_r_is_not_retroflex():
    # /θr/ (three) must NOT trigger the retroflex t+r rule (that is /tr/); it is th->ta then ra.
    assert AB.word_to_varnas("three") == ["ta", "ra"]


# ---------------------------------------------------------------- aspiration excluded
def test_aspiration_excluded():
    assert AB.ASPIRATION_APPLIED is False
    src = (HERE / "varna_bridge_active.py").read_text()
    # the active bridge does not import or apply any aspiration module/rule
    assert "aspirat" not in src.lower() or "ASPIRATION_APPLIED = False" in src
    # no frozen bundle diagnostic claims aspiration was applied
    for f in ["b1_9_pole_did_items_bundle_v1.json", "b1_9_pole_sanity_items_bundle_v1.json"]:
        assert _load(FROZEN / f)["aspiration_applied"] is False


# ---------------------------------------------------------------- dread sequence delta
def test_dread_sequence_change_in_frozen_items():
    v2 = {x["item_id"]: x for x in _load(FROZEN / "b1_9_pole_did_items.json")["items"]}
    bundle = {x["item_id"]: x for x in _load(FROZEN / "b1_9_pole_did_items_bundle_v1.json")["items"]}
    changed = [(x["target_text"], v2[k]["varna_sequence"], x["varna_sequence"])
               for k, x in bundle.items() if x["varna_sequence"] != v2[k]["varna_sequence"]]
    assert changed == [("dread", ["da", "ra", "da"], ["dda", "ra", "da"])], changed


def test_only_dread_changes_across_both_diagnostics():
    for items_f in ["b1_9_pole_did_items.json", "b1_9_pole_sanity_items.json"]:
        bundle_f = items_f.replace(".json", "_bundle_v1.json")
        v2 = {x["item_id"]: x for x in _load(FROZEN / items_f)["items"]}
        bu = {x["item_id"]: x for x in _load(FROZEN / bundle_f)["items"]}
        changed = [x["target_text"] for k, x in bu.items()
                   if x["varna_sequence"] != v2[k]["varna_sequence"]]
        assert changed == ["dread"], f"{bundle_f}: {changed}"


# ---------------------------------------------------------------- packets all regenerate under v3
def test_all_facet_packets_regenerated():
    v2 = {x["item_id"]: x for x in _load(FROZEN / "b1_9_pole_sanity_items.json")["items"]}
    bu = _load(FROZEN / "b1_9_pole_sanity_items_bundle_v1.json")["items"]
    changed = sum(1 for x in bu if x["correct_pole_facets"] != v2[x["item_id"]].get("correct_pole_facets"))
    assert changed == len(bu) == 24


# ---------------------------------------------------------------- fresh approval gates reset
def test_approval_gates_reset_under_bundle():
    assert _load(FROZEN / "b1_9_pole_did_items_bundle_v1.json")["classification_approved"] is False
    assert _load(FROZEN / "b1_9_pole_sanity_items_bundle_v1.json")["word_groups_approved"] is False


# ---------------------------------------------------------------- historical byte-unchanged
HISTORICAL = {
    "track_g_varna_polarity_table_v2_named_vritti.json": "7bc0b7c8c11c68c80d76ac974657611946e076a839f2a053bce9f639cd4a2694",
    "frozen/b1_6_phoneme_to_varna_bridge_manifest.json": "d1851c4abd431ead6ded545e1d2a6ecea29b0638d7f1c34394957439342d87ed",
    "frozen/b1_9_pole_did_items.json": "ea8e41d405f8c8aeb3264f778429a66db2df1cbdaa1372f8290970017fe068f1",
    "frozen/b1_9_pole_did_scaffold.json": "862b19c21bfaa6182732b1d60d20839859f96a364fa801d6328c86efeb792182",
    "frozen/b1_9_pole_sanity_items.json": "dae9497455e648860e50264a83e4924299801a94e737634a17d2d64b4fd79bab",
    "frozen/b1_9_pole_sanity_scaffold.json": "1c3674cf7438f4df3afae474c137b71e5d5a38b672604a663d0e025885bcfc12",
}


def test_historical_v2_v1_byte_unchanged():
    for rel, want in HISTORICAL.items():
        assert _sha(HERE / rel) == want, f"HISTORICAL DRIFT: {rel}"


def test_g2p_decomposer_unchanged():
    assert _sha(HERE / "stage_a_prime_coverage.py") == \
        "217c9ec98fc876bc585bba006741886b202f192f3c6009f05ff833f5b7a9e2cd"


# ---------------------------------------------------------------- prior result records unchanged
def test_prior_result_records_remain_v2_era():
    # v2-era items still declare their v2-era provenance (no bundle labels leaked back).
    v2 = _load(FROZEN / "b1_9_pole_did_items.json")
    assert v2.get("mapping_era", None) != "fidelity_bundle_v1"


# ---------------------------------------------------------------- guardrails intact
def test_guardrails_in_bundle_artifacts():
    for f in ["b1_9_pole_did_items_bundle_v1.json", "b1_9_pole_sanity_items_bundle_v1.json"]:
        blob = (FROZEN / f).read_text()
        assert "GENUTILITY" not in blob
        assert "ONTOLOGICAL_SIGNAL" not in blob
        d = _load(FROZEN / f)
        assert d["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    man = _load(FROZEN / "fidelity_bundle_v1_manifest.json")
    assert man["aspiration_applied"] is False
    assert man["result_interpretation"]["b1_4b_prime_status"].startswith("NULL_RETURN_BOTTOM")
    assert man["result_interpretation"]["track_b_status"] == "BLOCKED"


# ---------------------------------------------------------------- non-cluster words identical to base
def test_non_cluster_words_unchanged_vs_base():
    import varna_bridge_v2 as V2
    base = V2.base_mapping()

    def base_seq(word):
        import stage_a_prime_coverage as A
        ph = A.normalize(word, "A_PRIME_EN")["phonemes"]
        return [base[p] for p in ph if p in base]

    for w in ["peace", "calm", "love", "anger"]:
        assert AB.word_to_varnas(w) == base_seq(w), w
