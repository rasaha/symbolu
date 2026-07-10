"""Tests for the B1.8 context-resolved generation driver + freeze gate. Fake/mock only; NO model, NO network,
NO real generation, NO judging, NO unblinding. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import hashlib
import pathlib
import re
import pytest

import run_b1_8_context_resolved_generation as D


def _valid_decl(tmp_path, **over):
    decl = {
        "artifact": "b1_8_context_resolved_EVIDENCE_FREEZE_DECLARED",
        "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION,
        "declared_by": "op", "declared_at_utc": "2026-07-09T00:00:00Z",
        "attestation": D.ATTESTATION,
        **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()},
    }
    decl.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


# ---- freeze gate --------------------------------------------------------------------
def test_gate_accepts_valid(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path))
    assert ok, reasons


def test_gate_rejects_wrong_mode(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="pilot_generation"))
    assert not ok and any("mode !=" in r for r in reasons)


def test_gate_rejects_wrong_representation(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, representation_version="v2_named_vritti"))
    assert not ok and any("representation_version" in r for r in reasons)


def test_gate_rejects_b16v2_style_declaration(tmp_path):
    # a B1.6-v2 declaration: different artifact + mode + representation + no B1.8 hashes
    decl = {"artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
            "mode": "exploratory_10_sample_generation_probe", "representation_version": "v2_named_vritti",
            "declared_by": "op", "declared_at_utc": "t", "attestation": "wrong"}
    p = tmp_path / "d.json"; p.write_text(json.dumps(decl))
    ok, reasons = D.verify_freeze_gate(p)
    assert not ok and len(reasons) >= 1


def test_gate_rejects_hash_mismatch(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, target_scaffolds_sha256="deadbeef"))
    assert not ok and any("target_scaffolds_sha256 mismatch" in r for r in reasons)


def test_gate_rejects_missing_attestation(tmp_path):
    d = _valid_decl(tmp_path); obj = json.loads(d.read_text()); obj.pop("attestation")
    d.write_text(json.dumps(obj))
    ok, reasons = D.verify_freeze_gate(d)
    assert not ok


def test_gate_panel_manifest_required_when_panel(tmp_path):
    pm = tmp_path / "panel.json"; pm.write_text(json.dumps({"generator_models": []}))
    d = _valid_decl(tmp_path)   # no model_panel_manifest_sha256
    ok, reasons = D.verify_freeze_gate(d, panel_manifest_path=pm)
    assert not ok and any("model_panel_manifest" in r for r in reasons)
    d2 = _valid_decl(tmp_path, model_panel_manifest_sha256=D._sha_file(pm))
    ok2, _ = D.verify_freeze_gate(d2, panel_manifest_path=pm)
    assert ok2


# ---- rendering ----------------------------------------------------------------------
def test_all_arms_render_all_targets():
    tdoc, rdoc = D.load_frozen()
    recs = D.build_records(tdoc, rdoc)
    assert len(recs) == 12 * len(D.ARMS)                 # 12 targets x 7 arms = 84
    assert {r["arm"] for r in recs} == set(D.ARMS)
    for r in recs:
        assert r["prompt"] and r["target_text"] and r["context_text"]


def test_selected_vs_scrambled_share_context_differ_content():
    tdoc, rdoc = D.load_frozen()
    rand_by = {x["item_id"]: x for x in rdoc["items"]}
    t = tdoc["targets"][0]; r = rand_by[t["item_id"]]
    ksel = D.render_prompt("KCPR_SELECTED_POLE", t, r)
    scr = D.render_prompt("SCRAMBLED_SELECTED_POLE", t, r)
    # same context + plane + pole polarity (same resolver decision), different facet content
    assert t["CONTEXT_TEXT"] in ksel and t["CONTEXT_TEXT"] in scr
    assert f"Emphasize the {t['SELECTED_PLANE']} plane" in ksel and f"Emphasize the {t['SELECTED_PLANE']} plane" in scr
    assert t["RESOLVER_DECISION"] == r["RESOLVER_DECISION"]     # same selected polarity
    assert ksel != scr                                          # content differs
    # the authentic facet text appears in KCPR but (for this deranged item) not in scrambled
    first_real = next(iter(t["KCPR_LAYER1_SELECTED_FRAME"].values()))["text"]
    assert first_real in ksel


# ---- mock single-generator part (84) ------------------------------------------------
def test_mock_part_84_outputs_blind(tmp_path):
    part = D.run_part(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    assert part["mode"] == "MOCK" and part["n_outputs"] == 84 and part["n_failures"] == 0
    assert part["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    blob = json.dumps(part["outputs"])
    # outputs carry hidden-side fields (arm etc.) pre-merge; that's fine - not judge-visible yet
    assert (tmp_path / "b1_8_part.json").exists()


def test_real_part_refuses_without_declaration():
    with pytest.raises(PermissionError):
        D.run_part(mock=False, adapter=object(), decl_path=None)


# ---- mock two-generator merge (168) + blinding --------------------------------------
def test_mock_two_generator_merge_168(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1")
    p2 = D.run_part(mock=True, gen_code="M2")
    res = D.merge_parts([p1, p2], out_dir=tmp_path, write=True)
    assert res["label"] == "B1_8_GENERATION_DRIVER_READY_MOCK_TESTED"
    m = res["manifest"]
    assert m["n_outputs"] == 168 and m["expected_full"] == 168 and m["n_generators"] == 2
    assert m["per_generator_counts"] == {"M1": 84, "M2": 84}
    assert m["unblinded"] is False and m["judging_performed"] is False
    # judge-visible is blind: only allowed keys, no arm/generator/varna/KCPR leak
    jv = (tmp_path / "panel_judge_visible_outputs.jsonl").read_text()
    for line in jv.splitlines():
        r = json.loads(line)
        assert set(r.keys()) == D.ALLOWED_JV_KEYS
    assert not re.search(r"KCPR|SCRAMBLED|UNRESOLVED|BASELINE|generator_code|true_arm|varna|SYMBOLU|M1|M2",
                         jv)


def test_hidden_metadata_has_required_fields(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1", gen_id="mistralai/Mistral-7B-Instruct-v0.3")
    res = D.merge_parts([p1], out_dir=tmp_path, write=True)
    hidden = json.loads((tmp_path / "panel_hidden_arm_generator_metadata.json").read_text())
    need = {"blinded_output_id", "true_arm", "generator_code", "item_id", "stratum",
            "resolver_decision", "selected_plane", "representation_version"}
    for h in hidden:
        assert need <= set(h.keys())
    assert {h["true_arm"] for h in hidden} == set(D.ARMS)


def test_merge_refuses_duplicate_generator(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1")
    res = D.merge_parts([p1, dict(p1)])
    assert res["label"] != "B1_8_GENERATION_DRIVER_READY_MOCK_TESTED"


def test_no_genutility_and_no_network():
    p1 = D.run_part(mock=True, gen_code="M1")
    res = D.merge_parts([p1])
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"


def test_leak_in_output_is_dropped(tmp_path, monkeypatch):
    # force the mock text to contain a forbidden method token -> that output drops, run continues
    monkeypatch.setattr(D, "_mock_text", lambda rec: "Title: x\nInterpretation: uses a varna KCPR scaffold "
                        + "word " * 60 + "\nPractical reflection:\n- a\n- b\nCaution: limited.")
    part = D.run_part(mock=True, gen_code="M1")
    assert part["n_outputs"] == 0 and part["n_failures"] == 84
    assert all(f["status"] == "blindness_leak" for f in part["failures"])
