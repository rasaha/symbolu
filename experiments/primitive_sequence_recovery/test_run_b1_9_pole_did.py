"""Tests for the B1.9 pole diff-in-diff driver + freeze gate. Fake/mock only; NO model, NO network, NO real
generation, NO judging. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import re
import pytest

import run_b1_9_pole_did as D
import build_b1_9_pole_did_scaffold as B


def _valid_decl(tmp_path, **over):
    decl = {"artifact": "b1_9_pole_did_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
            "mode": D.MODE, "representation_version": D.REPRESENTATION, "declared_by": "op",
            "declared_at_utc": "2026-07-12T00:00:00Z", "attestation": D.ATTESTATION,
            **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()}}
    decl.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


# ---- canonical varṇa derivation reproduces the existing 12 -----------------------------
def test_canonical_reproduces_existing_12():
    exist = {x["target_text"]: [(v["varna"] if isinstance(v, dict) else v) for v in x["varna_sequence"]]
             for x in json.load(open("frozen/b1_9_targets.json"))["targets"]}
    mapping = B._bridge()["mapping"]
    for w, ev in exist.items():
        assert B.canonical_varnas(w, mapping) == ev, w

def test_items_all_in_table_and_not_thin():
    idoc = json.load(open("frozen/b1_9_pole_did_items.json"))
    table = set(json.load(open("track_g_varna_polarity_table_v2_named_vritti.json"))["varnas"].keys())
    assert idoc["n_items"] == 24 and idoc["n_liberating"] == 12 and idoc["n_binding"] == 12
    for it in idoc["items"]:
        assert len(it["varna_sequence"]) >= 2
        assert all(v in table for v in it["varna_sequence"])


# ---- freeze gate --------------------------------------------------------------------
def test_gate_blocks_until_classification_approved(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path))
    assert not ok and any("classification NOT approved" in r for r in reasons)

def test_gate_rejects_other_track_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "classification_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="b1_9_pole_sensitivity_probe"))
    assert not ok and any("refused" in r for r in reasons)

def test_gate_accepts_when_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "classification_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path)); assert ok, reasons

def test_gate_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "classification_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, scaffold_sha256="deadbeef"))
    assert not ok and any("scaffold_sha256 mismatch" in r for r in reasons)


# ---- 4-arm structure: pole is the only within-source variable; W′ != W ---------------
def test_four_arms_and_did_structure():
    scaf = D.load_scaffold()
    for it in scaf["items"]:
        assert it["wprime_item_id"] != it["item_id"]                       # W′ != W
        assert {it["CORRECT_POLE"], it["FLIPPED_POLE"]} == {"worldly_binding_distortion", "spiritual_liberating_reading"}
        af = it["ARM_FACETS"]
        # OWN arms use W's varṇas; CONTROL arms use W′'s varṇas
        assert [f["varna"] for f in af["OWN_CORRECT_POLE"]] == [f["varna"] for f in af["OWN_FLIPPED_POLE"]]
        assert [f["varna"] for f in af["CONTROL_CORRECT_POLE"]] == [f["varna"] for f in af["CONTROL_FLIPPED_POLE"]]
        # correct vs flipped differ only by pole text
        assert af["OWN_CORRECT_POLE"] != af["OWN_FLIPPED_POLE"]

def test_all_arms_render_all_items():
    recs = D.build_records(D.load_scaffold())
    assert len(recs) == 24 * 4 and {r["arm"] for r in recs} == set(D.ARMS)


# ---- mock part / merge / blinding ---------------------------------------------------
def test_mock_part_96(tmp_path):
    part = D.run_part(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    assert part["mode"] == "MOCK" and part["n_outputs"] == 96 and part["n_failures"] == 0
    assert part["classification_approved"] is False
    assert (tmp_path / "b1_9_pole_did_part.json").exists()

def test_real_part_refuses_without_declaration():
    with pytest.raises(PermissionError):
        D.run_part(mock=False, adapter=object(), decl_path=None)

def test_mock_two_generator_merge_192_blind(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1"); p2 = D.run_part(mock=True, gen_code="M2")
    res = D.merge_parts([p1, p2], out_dir=tmp_path, write=True)
    assert res["label"] == "B1_9_POLE_DID_DRIVER_READY_MOCK_TESTED"
    m = res["manifest"]
    assert m["n_outputs"] == 192 and m["expected_full"] == 192 and m["per_generator_counts"] == {"M1": 96, "M2": 96}
    jv = (tmp_path / "panel_judge_visible_outputs.jsonl").read_text()
    for line in jv.splitlines():
        assert set(json.loads(line).keys()) == D.ALLOWED_JV_KEYS
    assert not re.search(r"OWN_|CONTROL_|CORRECT_POLE|FLIPPED|binding|liberating|true_arm|wprime|M1|M2", jv)

def test_hidden_has_did_labels(tmp_path):
    D.merge_parts([D.run_part(mock=True, gen_code="M1")], out_dir=tmp_path, write=True)
    hidden = json.loads((tmp_path / "panel_hidden_arm_generator_metadata.json").read_text())
    need = {"blinded_output_id", "true_arm", "item_id", "correct_pole", "flipped_pole", "wprime_item_id"}
    for h in hidden:
        assert need <= set(h.keys())
    assert {h["true_arm"] for h in hidden} == set(D.ARMS)

def test_no_genutility():
    res = D.merge_parts([D.run_part(mock=True, gen_code="M1")])
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
