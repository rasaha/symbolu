"""Tests for the B1.9 pole-logic sanity driver: gate + blinding + rating parse + INT aggregation.
Fake/mock only; NO model, NO network, NO generation, NO real judging. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import re
import pytest

import run_b1_9_pole_sanity as D
import build_b1_9_pole_sanity_scaffold as B


def _valid_decl(tmp_path, **over):
    decl = {"artifact": "b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
            "mode": D.MODE, "representation_version": D.REPRESENTATION, "declared_by": "op",
            "declared_at_utc": "2026-07-12T00:00:00Z", "attestation": D.ATTESTATION,
            **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
    decl.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


# ---- scaffold reuses APPROVED pole-DiD packets, all 24 words --------------------------
def test_scaffold_all24_reuses_approved_packets():
    pole = {p["target_text"]: p for p in json.load(open("frozen/b1_9_pole_did_items.json"))["items"]}
    scaf = D.load_scaffold()
    assert scaf["n_items"] == 24
    table = json.load(open("track_g_varna_polarity_table_v2_named_vritti.json"))["varnas"]
    for it in scaf["items"]:
        src = pole[it["target_text"]]
        assert it["varna_sequence"] == src["varna_sequence"]
        assert it["correct_pole"] == src["correct_pole"] and it["flipped_pole"] == src["flipped_pole"]
        # packets are the RAW table text at the two poles
        assert it["correct_packet"] == B._pole_facets(src["varna_sequence"], src["correct_pole"], table)
        assert it["flipped_packet"] == B._pole_facets(src["varna_sequence"], src["flipped_pole"], table)
        roles = {c["role"] for c in it["candidate_pool"]}
        assert "target" in roles


# ---- curated-contrast mode: no opposite-pole-pool fill; tight-sense synonyms -----------
def test_opposites_are_antonyms_not_opposite_pole_pool():
    for it in D.load_scaffold()["items"]:
        for o in it["opposites"]:
            assert o["source"] in ("wordnet_antonym", "operator_curated")   # NOT opposite_pole_pool
    # a liberating word must NOT get the binding item-words as opposites by default
    peace = next(it for it in D.load_scaffold()["items"] if it["target_text"] == "peace")
    assert not ({"anchor", "cage", "chain", "wall"} & {o["word"] for o in peace["opposites"]})

def test_synonyms_are_primary_synset_only_no_cross_sense_noise():
    assert "curl" not in [s["word"] for s in B.harvest_synonyms("lock", set())]      # hair sense excluded
    assert "brat" not in [s["word"] for s in B.harvest_synonyms("terror", set())]    # child sense excluded

def test_needs_manual_flag_present_on_sparse_items():
    idoc = json.load(open("frozen/b1_9_pole_sanity_items.json"))
    assert idoc["n_need_manual"] >= 1 and idoc["coverage_flags"]
    for f in idoc["coverage_flags"]:
        assert f["status"] == "NEEDS_MANUAL_REPLACEMENT" and f["issues"]


# ---- freeze gate ---------------------------------------------------------------------
def test_gate_blocks_until_word_groups_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "word_groups_approved", lambda: False)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path))
    assert not ok and any("table NOT approved" in r for r in reasons)

def test_gate_rejects_other_track_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "word_groups_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="b1_9_pole_did_probe"))
    assert not ok and any("refused" in r for r in reasons)

def test_gate_accepts_when_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "word_groups_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path)); assert ok, reasons

def test_gate_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "word_groups_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, scaffold_sha256="deadbeef"))
    assert not ok and any("scaffold_sha256 mismatch" in r for r in reasons)


# ---- task construction + blinding ----------------------------------------------------
def test_tasks_cover_two_poles_and_all_candidates():
    scaf = D.load_scaffold()
    tasks = D.build_rating_tasks(scaf)
    exp = sum(2 * len(it["candidate_pool"]) for it in scaf["items"])   # 2 packets × candidates
    assert len(tasks) == exp
    assert {t["packet_pole"] for t in tasks} == set(D.PACKET_POLES)
    assert {t["candidate_role"] for t in tasks} == {"target", "synonym", "opposite"}

def test_prepare_blinds_pole_and_role(tmp_path):
    res = D.prepare(D.load_scaffold(), out_dir=tmp_path, write=True)
    jv = (tmp_path / "panel_judge_visible_ratings.jsonl").read_text()
    for line in jv.splitlines():
        pkg = json.loads(line)
        assert set(pkg.keys()) == D.ALLOWED_JV_KEYS               # only rating_id/packet/word/word_meaning
    # no STRUCTURAL pole/role/item labels leak to the judge view (natural English in a gloss is fine — the
    # key-set check above already guarantees no packet_pole/candidate_role/item_id keys reach the judge)
    assert not re.search(r"pd-\d|packet_pole|candidate_role|\bitem_id\b", jv)
    hidden = json.loads((tmp_path / "panel_hidden_metadata.json").read_text())
    for h in hidden:
        assert {"rating_id", "item_id", "packet_pole", "candidate_role"} <= set(h.keys())
    assert res["manifest"]["n_items"] == 24


# ---- rating parse --------------------------------------------------------------------
def test_parse_rating_valid_and_invalid():
    r, reasons = D.parse_rating('sure: {"fit": 6, "describes": "direct"} ok')
    assert r == {"fit": 6, "describes": "direct"} and not reasons
    assert D.parse_rating('{"fit": 9, "describes": "direct"}')[0] is None      # out of range
    assert D.parse_rating('{"fit": 4, "describes": "sideways"}')[0] is None     # bad label
    assert D.parse_rating('no json')[0] is None


# ---- real judge refuses without declaration ------------------------------------------
def test_real_judge_refuses_without_declaration(tmp_path):
    res = D.prepare(D.load_scaffold(), out_dir=tmp_path, write=True)
    with pytest.raises(PermissionError):
        D.run_judge(tmp_path / "panel_judge_visible_ratings.jsonl", "J", mock=False, decl_path=None)


# ---- full mock pipeline: prepare -> 3 judges -> aggregate INT -------------------------
def test_mock_pipeline_and_int(tmp_path):
    res = D.prepare(D.load_scaffold(), out_dir=tmp_path, write=True)
    jvp = tmp_path / "panel_judge_visible_ratings.jsonl"
    hidden = res["hidden"]
    n_tasks = res["manifest"]["n_rating_tasks"]
    jparts = [D.run_judge(jvp, f"JUDGE{i}", mock=True) for i in range(3)]
    for jp in jparts:
        assert jp["n_errors"] == 0 and jp["n_ratings"] == n_tasks
    agg = D.aggregate(jparts, hidden)
    assert agg["label"] == "B1_9_POLE_SANITY_AGGREGATE"
    for k in ("1_correct_fit_to_target_synonyms", "2_flipped_fit_to_target_synonyms",
              "3_flipped_fit_to_opposites", "4_correct_fit_to_opposites"):
        assert agg["reported_cells"][k] is not None
    assert agg["mean_INT"] is not None and agg["INT_bootstrap_CI95"][0] is not None
    # only items that HAVE opposites can form D_opposite/INT (curated-contrast: no pool fill)
    paired_expected = sum(1 for it in D.load_scaffold()["items"]
                          if any(c["role"] == "opposite" for c in it["candidate_pool"]))
    assert agg["n_items_paired"] == paired_expected
    # two PRIMARY diagnostics exposed: INT + Cell ①
    pd = agg["primary_diagnostics"]
    assert pd["1_INT"]["mean"] is not None
    assert pd["2_cell_1_correct_fit_to_target_synonyms"]["mean"] is not None
    assert pd["2_cell_1_correct_fit_to_target_synonyms"]["vs_neutral_midpoint_4"] is not None
    assert "Cell① HIGH" in agg["verdict_logic"]
    assert set(agg["anti_contrastive_audit"]) == {"correct_target_synonyms", "flipped_target_synonyms",
                                                  "flipped_opposites", "correct_opposites"}


def test_aggregate_math_on_synthetic_coherent_item():
    # one item where the poles are perfectly coherent -> D_target>0, D_opposite<0, INT>0
    hidden = [
        {"rating_id": "R1", "item_id": "x", "packet_pole": "correct", "candidate_role": "target"},
        {"rating_id": "R2", "item_id": "x", "packet_pole": "flipped", "candidate_role": "target"},
        {"rating_id": "R3", "item_id": "x", "packet_pole": "correct", "candidate_role": "opposite"},
        {"rating_id": "R4", "item_id": "x", "packet_pole": "flipped", "candidate_role": "opposite"},
    ]
    jp = [{"ratings": [
        {"rating_id": "R1", "judge_id": "J", "fit": 7, "describes": "direct"},   # correct->target high
        {"rating_id": "R2", "judge_id": "J", "fit": 2, "describes": "direct"},   # flipped->target low
        {"rating_id": "R3", "judge_id": "J", "fit": 2, "describes": "direct"},   # correct->opposite low
        {"rating_id": "R4", "judge_id": "J", "fit": 7, "describes": "direct"},   # flipped->opposite high
    ]}]
    agg = D.aggregate(jp, hidden)
    assert agg["mean_D_target"] == 5.0 and agg["mean_D_opposite"] == -5.0 and agg["mean_INT"] == 10.0
    assert agg["reported_cells"]["1_correct_fit_to_target_synonyms"] == 7.0
    assert agg["n_items_paired"] == 1


def test_no_genutility_and_null_bottom(tmp_path):
    res = D.prepare(D.load_scaffold(), out_dir=tmp_path, write=True)
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
