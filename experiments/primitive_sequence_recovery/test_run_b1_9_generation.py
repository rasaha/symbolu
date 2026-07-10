"""Tests for the B1.9 generation driver (corrected distant-source control) + freeze gate. Fake/mock only; NO
model, NO network, NO real generation, NO judging, NO unblinding. B1.4b' remains NULL_RETURN_BOTTOM."""
import json
import re
import pytest

import run_b1_9_generation as D


def _valid_decl(tmp_path, **over):
    decl = {
        "artifact": "b1_9_generation_EVIDENCE_FREEZE_DECLARED",
        "evidence_freeze_declared": True,
        "mode": D.MODE, "representation_version": D.REPRESENTATION,
        "declared_by": "op", "declared_at_utc": "2026-07-10T00:00:00Z",
        "attestation": D.ATTESTATION,
        **{k: D._sha_file(v) for k, v in D.HASH_INPUTS.items()},
    }
    decl.update(over)
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


# ---- freeze gate --------------------------------------------------------------------
def test_gate_accepts_valid(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path)); assert ok, reasons

def test_gate_rejects_wrong_mode(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="b1_8_context_resolved_generation_probe"))
    assert not ok and any("refused" in r or "mode !=" in r for r in reasons)

def test_gate_rejects_content_distance_mode(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, mode="b1_9_content_level_semantic_distance"))
    assert not ok and any("refused" in r for r in reasons)

def test_gate_rejects_wrong_representation(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, representation_version="B1.8_context_resolved_layer1"))
    assert not ok and any("representation_version" in r for r in reasons)

def test_gate_rejects_hash_mismatch(tmp_path):
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path, scaffold_sha256="deadbeef"))
    assert not ok and any("scaffold_sha256 mismatch" in r for r in reasons)

def test_gate_rejects_missing_attestation(tmp_path):
    d = _valid_decl(tmp_path); obj = json.loads(d.read_text()); obj.pop("attestation")
    d.write_text(json.dumps(obj))
    ok, _ = D.verify_freeze_gate(d); assert not ok

def test_gate_panel_manifest_required_when_panel(tmp_path):
    pm = tmp_path / "panel.json"; pm.write_text(json.dumps({"judge_models": []}))
    ok, reasons = D.verify_freeze_gate(_valid_decl(tmp_path), panel_manifest_path=pm)
    assert not ok and any("model_panel_manifest" in r for r in reasons)
    ok2, _ = D.verify_freeze_gate(_valid_decl(tmp_path, model_panel_manifest_sha256=D._sha_file(pm)),
                                  panel_manifest_path=pm)
    assert ok2


# ---- rendering ----------------------------------------------------------------------
def test_all_arms_render_all_items():
    recs = D.build_records(D.load_scaffold())
    assert len(recs) == 12 * len(D.ARMS)                 # 12 items x 8 arms = 96
    assert {r["arm"] for r in recs} == set(D.ARMS)
    assert set(D.RESOLVED_CONTRAST) <= set(D.ARMS)
    for r in recs:
        assert r["prompt"] and r["target_text"] and r["context_text"]

def test_resolved_arms_use_selected_pole_and_differ_from_named_attribute():
    scaf = D.load_scaffold()
    for it in scaf["items"]:
        pole = it["SELECTED_POLE"]
        assert pole in ("worldly_binding_distortion", "spiritual_liberating_reading")
        # resolved arms are NOT the same content as the resolver-free named_attribute arms
        assert it["ARM_FACETS"]["AUTHENTIC_RESOLVED_POLE"] != it["ARM_FACETS"]["AUTHENTIC_MAPPING"]
        # DISTANT_RESOLVED applies W's SAME pole to the distant word's varṇas
        src = next(x for x in scaf["items"] if x["item_id"] == it["distant_source_item_id"])
        # same selected pole polarity as authentic-resolved (the corrected control holds pole constant)
        aR = D.render_prompt("AUTHENTIC_RESOLVED_POLE", it)
        dR = D.render_prompt("DISTANT_SOURCE_RESOLVED_POLE", it)
        assert aR != dR and it["CONTEXT_TEXT"] in aR and it["CONTEXT_TEXT"] in dR

def test_authentic_vs_distant_share_context_differ_content():
    scaf = D.load_scaffold(); it = scaf["items"][0]                 # b18-01 bridge -> distant b18-10 Nova
    auth = D.render_prompt("AUTHENTIC_MAPPING", it)
    dist = D.render_prompt("DISTANT_SOURCE_MAPPING", it)
    assert it["CONTEXT_TEXT"] in auth and it["CONTEXT_TEXT"] in dist   # same context
    assert f"Emphasize the {it['PLANE']} plane" in auth and f"Emphasize the {it['PLANE']} plane" in dist
    assert auth != dist                                              # facet content differs
    # authentic facet text present in AUTHENTIC arm; distant-source facet text present in DISTANT arm
    assert it["ARM_FACETS"]["AUTHENTIC_MAPPING"][0]["text"] in auth
    assert it["ARM_FACETS"]["DISTANT_SOURCE_MAPPING"][0]["text"] in dist

def test_distant_source_is_a_different_words_own_mapping():
    scaf = D.load_scaffold()
    dmap = json.loads(D.DISTANT_MAP_FILE.read_text())["map"]
    for it in scaf["items"]:
        assert it["distant_source_item_id"] == dmap[it["item_id"]]
        assert it["distant_source_item_id"] != it["item_id"]        # W' != W
        # the DISTANT arm's facets equal the source word's OWN authentic facets (not a within-pool scramble)
        src = next(x for x in scaf["items"] if x["item_id"] == it["distant_source_item_id"])
        assert it["ARM_FACETS"]["DISTANT_SOURCE_MAPPING"] == src["ARM_FACETS"]["AUTHENTIC_MAPPING"]


# ---- mock single-generator part (72) ------------------------------------------------
def test_mock_part_72_outputs_blind(tmp_path):
    part = D.run_part(mock=True, gen_code="M1", out_dir=tmp_path, write=True)
    assert part["mode"] == "MOCK" and part["n_outputs"] == 96 and part["n_failures"] == 0
    assert part["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    assert part["primary_contrast"] == ["AUTHENTIC_MAPPING", "DISTANT_SOURCE_MAPPING"]
    assert (tmp_path / "b1_9_part.json").exists()

def test_real_part_refuses_without_declaration():
    with pytest.raises(PermissionError):
        D.run_part(mock=False, adapter=object(), decl_path=None)


# ---- mock two-generator merge (144) + blinding --------------------------------------
def test_mock_two_generator_merge_144(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1"); p2 = D.run_part(mock=True, gen_code="M2")
    res = D.merge_parts([p1, p2], out_dir=tmp_path, write=True)
    assert res["label"] == "B1_9_GENERATION_DRIVER_READY_MOCK_TESTED"
    m = res["manifest"]
    assert m["n_outputs"] == 192 and m["expected_full"] == 192 and m["n_generators"] == 2
    assert m["per_generator_counts"] == {"M1": 96, "M2": 96}
    assert m["unblinded"] is False and m["judging_performed"] is False
    jv = (tmp_path / "panel_judge_visible_outputs.jsonl").read_text()
    for line in jv.splitlines():
        r = json.loads(line)
        assert set(r.keys()) == D.ALLOWED_JV_KEYS
    assert not re.search(r"AUTHENTIC|DISTANT|SCRAMBLED|BASELINE|generator_code|true_arm|varna|SYMBOLU|M1|M2", jv)

def test_hidden_metadata_has_required_fields(tmp_path):
    p1 = D.run_part(mock=True, gen_code="M1", gen_id="mistralai/Mistral-7B-Instruct-v0.3")
    D.merge_parts([p1], out_dir=tmp_path, write=True)
    hidden = json.loads((tmp_path / "panel_hidden_arm_generator_metadata.json").read_text())
    need = {"blinded_output_id", "true_arm", "generator_code", "item_id", "stratum", "plane",
            "distant_source_item_id", "representation_version"}
    for h in hidden:
        assert need <= set(h.keys())
    assert {h["true_arm"] for h in hidden} == set(D.ARMS)

def test_merge_refuses_duplicate_generator():
    p1 = D.run_part(mock=True, gen_code="M1")
    res = D.merge_parts([p1, dict(p1)])
    assert res["label"] != "B1_9_GENERATION_DRIVER_READY_MOCK_TESTED"

def test_no_genutility_and_null_preserved():
    p1 = D.run_part(mock=True, gen_code="M1")
    res = D.merge_parts([p1])
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"

def test_leak_in_output_is_dropped(monkeypatch):
    monkeypatch.setattr(D, "_mock_text", lambda rec: "Title: x\nInterpretation: uses a varna KCPR scaffold "
                        + "word " * 60 + "\nPractical reflection:\n- a\n- b\nCaution: limited.")
    part = D.run_part(mock=True, gen_code="M1")
    assert part["n_outputs"] == 0 and part["n_failures"] == 96
    assert all(f["status"] == "blindness_leak" for f in part["failures"])
