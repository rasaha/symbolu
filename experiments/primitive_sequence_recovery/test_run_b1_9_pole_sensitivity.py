"""Tests for the B1.9 pole-sensitivity driver (Q2) + freeze gate. Fake/mock only; NO model, NO network, NO real
generation, NO judging. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import re
import pytest

import run_b1_9_pole_sensitivity as D


def _valid_decl(tmp_path, **over):
    decl = {
        "artifact": "b1_9_pole_sensitivity_EVIDENCE_FREEZE_DECLARED",
        "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION,
        "declared_by": "op", "declared_at_utc": "2026-07-11T00:00:00Z",
        "attestation": D.ATTESTATION,
        **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()},
    }
    decl.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


# ---- freeze gate --------------------------------------------------------------------
def test_gate_blocks_until_classification_approved(tmp_path):
    # DRAFT classification (classification_approved=false) must block even a perfect declaration
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path))
    assert not ok and any("classification NOT approved" in r for r in reasons)

def test_gate_rejects_wrong_mode(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="b1_9_generation_corrected_control_probe"))
    assert not ok and any("refused" in r or "mode !=" in r for r in reasons)

def test_gate_rejects_wrong_representation(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, representation_version="B1.9_generation_corrected_control"))
    assert not ok and any("representation_version" in r for r in reasons)

def test_gate_rejects_hash_mismatch_and_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "classification_approved", lambda: True)   # simulate sign-off
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, scaffold_sha256="deadbeef"))
    assert not ok and any("scaffold_sha256 mismatch" in r for r in reasons)

def test_gate_accepts_when_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "classification_approved", lambda: True)
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path))
    assert ok, reasons


# ---- pole flip is the only variable -------------------------------------------------
def test_correct_and_flipped_share_everything_but_pole():
    scaf = D.load_scaffold()
    for it in scaf["items"]:
        assert it["CORRECT_POLE"] != it["FLIPPED_POLE"]
        assert {it["CORRECT_POLE"], it["FLIPPED_POLE"]} == {"worldly_binding_distortion", "spiritual_liberating_reading"}
        # same varṇas underlie both pole facet sets (only the pole text differs)
        cv = [f["varna"] for f in it["ARM_FACETS"]["POLE_CORRECT"]]
        fv = [f["varna"] for f in it["ARM_FACETS"]["POLE_FLIPPED"]]
        assert cv == fv
        c = D.render_prompt("POLE_CORRECT", it); f = D.render_prompt("POLE_FLIPPED", it)
        assert c != f and it["CONTEXT_TEXT"] in c and it["CONTEXT_TEXT"] in f
        assert f"Emphasize the {it['PLANE']} plane" in c and f"Emphasize the {it['PLANE']} plane" in f

def test_all_arms_render_all_items():
    recs = D.build_records(D.load_scaffold())
    assert len(recs) == 12 * len(D.ARMS)             # 12 x 4 = 48
    assert {r["arm"] for r in recs} == set(D.ARMS)
    assert D.PRIMARY_CONTRAST == ("POLE_CORRECT", "POLE_FLIPPED")


# ---- mock part / merge / blinding ---------------------------------------------------
def test_mock_part_48(tmp_path):
    part = D.run_part(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    assert part["mode"] == "MOCK" and part["n_outputs"] == 48 and part["n_failures"] == 0
    assert part["classification_approved"] is False       # DRAFT
    assert (tmp_path / "b1_9_pole_part.json").exists()

def test_real_part_refuses_without_declaration():
    with pytest.raises(PermissionError):
        D.run_part(mock=False, adapter=object(), decl_path=None)

def test_mock_two_generator_merge_96_blind(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1"); p2 = D.run_part(mock=True, gen_code="M2")
    res = D.merge_parts([p1, p2], out_dir=tmp_path, write=True)
    assert res["label"] == "B1_9_POLE_SENSITIVITY_DRIVER_READY_MOCK_TESTED"
    m = res["manifest"]
    assert m["n_outputs"] == 96 and m["expected_full"] == 96 and m["per_generator_counts"] == {"M1": 48, "M2": 48}
    jv = (tmp_path / "panel_judge_visible_outputs.jsonl").read_text()
    for line in jv.splitlines():
        assert set(json.loads(line).keys()) == D.ALLOWED_JV_KEYS
    assert not re.search(r"POLE_CORRECT|POLE_FLIPPED|binding|liberating|true_arm|M1|M2", jv)

def test_hidden_has_pole_labels(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1")
    D.merge_parts([p1], out_dir=tmp_path, write=True)
    hidden = json.loads((tmp_path / "panel_hidden_arm_generator_metadata.json").read_text())
    need = {"blinded_output_id", "true_arm", "item_id", "correct_pole", "flipped_pole", "representation_version"}
    for h in hidden:
        assert need <= set(h.keys())
    assert {h["true_arm"] for h in hidden} == set(D.ARMS)

def test_no_genutility():
    res = D.merge_parts([D.run_part(mock=True, gen_code="M1")])
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
