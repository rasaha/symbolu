"""Mock tests for the B1.6 pilot generation driver. NO real generation, NO judging,
NO evidence freeze. Uses a temp declaration file; never creates the real one."""
import json
import pathlib
import hashlib
import pytest

import run_b1_6_pilot_generation as drv

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _valid_decl():
    return {
        "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED",
        "evidence_freeze_declared": True,
        "mode": "pilot_generation",
        "scaffold_manifest_sha256": _sha(drv.SCAFFOLD_MANIFEST_FILE),
        "target_scaffold_sha256": _sha(drv.TARGETS_FILE),
        "randomized_control_manifest_sha256": _sha(drv.RANDCTL_FILE),
        "prompt_rubric_sha256": _sha(drv.PROMPT_RUBRIC_FILE),
        "declared_by": "operator-test",
        "declared_at_utc": "2026-07-08T00:00:00Z",
        "attestation": drv.ATTESTATION,
    }


def _write_decl(tmp_path, obj):
    p = tmp_path / "decl.json"
    p.write_text(json.dumps(obj))
    return p


# ---- freeze-gate refusals ------------------------------------------------------------
def test_missing_declaration_refuses(tmp_path):
    ok, reasons = drv.verify_freeze_gate(tmp_path / "nope.json")
    assert not ok and any("no EVIDENCE_FREEZE" in r for r in reasons)


def test_wrong_mode_refuses(tmp_path):
    d = _valid_decl(); d["mode"] = "not_pilot"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("mode !=" in r for r in reasons)


def test_missing_field_refuses(tmp_path):
    d = _valid_decl(); del d["declared_by"]
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("declared_by" in r for r in reasons)


def test_scaffold_manifest_hash_mismatch_refuses(tmp_path):
    d = _valid_decl(); d["scaffold_manifest_sha256"] = "deadbeef"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("scaffold_manifest_sha256 mismatch" in r for r in reasons)


def test_target_scaffold_hash_mismatch_refuses(tmp_path):
    d = _valid_decl(); d["target_scaffold_sha256"] = "deadbeef"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("target_scaffold_sha256 mismatch" in r for r in reasons)


def test_randomized_control_hash_mismatch_refuses(tmp_path):
    d = _valid_decl(); d["randomized_control_manifest_sha256"] = "deadbeef"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("randomized_control_manifest_sha256 mismatch" in r for r in reasons)


def test_prompt_rubric_hash_mismatch_refuses(tmp_path):
    d = _valid_decl(); d["prompt_rubric_sha256"] = "deadbeef"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("prompt_rubric_sha256 mismatch" in r for r in reasons)


def test_attestation_mismatch_refuses(tmp_path):
    d = _valid_decl(); d["attestation"] = "wrong"
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, d))
    assert not ok and any("attestation" in r for r in reasons)


def test_valid_declaration_passes(tmp_path):
    ok, reasons = drv.verify_freeze_gate(_write_decl(tmp_path, _valid_decl()))
    assert ok, reasons


def test_run_refuses_without_declaration(tmp_path):
    with pytest.raises(PermissionError):
        drv.run(mock=True, decl_path=tmp_path / "nope.json", out_dir=tmp_path / "o", write=False)


def test_real_mode_requires_adapter(tmp_path):
    decl = _write_decl(tmp_path, _valid_decl())
    with pytest.raises(ValueError):
        drv.run(mock=False, generator=None, decl_path=decl, out_dir=tmp_path / "o", write=False)


# ---- prompt rendering / coverage -----------------------------------------------------
def _run(tmp_path):
    decl = _write_decl(tmp_path, _valid_decl())
    return drv.run(mock=True, decl_path=decl, out_dir=tmp_path / "o", write=True)


def test_prompt_rendering_covers_24x5(tmp_path):
    res = _run(tmp_path)
    assert res["manifest"]["n_targets"] == 24
    assert res["manifest"]["n_arms"] == 5
    assert res["manifest"]["n_prompts"] == 120
    assert len(res["records"]) == 120
    # each item has all five arms
    from collections import Counter
    per_item = Counter(r["item_id"] for r in res["records"])
    assert all(v == 5 for v in per_item.values())


def test_symbolu_prompt_includes_kcpr_dual_pole(tmp_path):
    res = _run(tmp_path)
    sym = [r for r in res["records"] if r["arm"] == "SYMBOLU_SCAFFOLD"]
    assert sym
    for r in sym[:3]:
        assert "worldly/binding pole" in r["prompt"] and "liberating/counter pole" in r["prompt"]


def test_randomized_control_uses_randomized_scaffold(tmp_path):
    res = _run(tmp_path)
    by = {(r["item_id"], r["arm"]): r for r in res["records"]}
    randctl = json.loads(drv.RANDCTL_FILE.read_text())
    rand_by_id = {x["item_id"]: x for x in randctl["randomized_scaffolds"]}
    # for at least one item where the randomized profile differs, prompts differ
    differ = 0
    for item_id, rr in rand_by_id.items():
        sym = by[(item_id, "SYMBOLU_SCAFFOLD")]["prompt"]
        rnd = by[(item_id, "RANDOMIZED_SYMBOLU_CONTROL")]["prompt"]
        if sym != rnd:
            differ += 1
    assert differ > 0, "randomized control identical to real scaffold for every item"


def test_no_csr_stl_or_kosha_in_active_prompts(tmp_path):
    res = _run(tmp_path)
    for r in res["records"]:
        low = r["prompt"].lower()
        assert "csr" not in low and "stl" not in low
        assert "kosha" not in low


# ---- blinding ------------------------------------------------------------------------
def test_judge_visible_is_blind(tmp_path):
    res = _run(tmp_path)
    for pkg in res["judge_visible"]:
        assert "arm" not in pkg and "true_arm" not in pkg
        assert "prompt" not in pkg and "VARNA_PROFILE_TABLE" not in pkg
        assert "blinded_output_id" in pkg and "generation_text" in pkg


def test_no_arm_names_in_judge_visible(tmp_path):
    res = _run(tmp_path)
    blob = json.dumps(res["judge_visible"])
    for arm in drv.ACTIVE_ARMS:
        assert arm not in blob


def test_hidden_metadata_retains_arm_mapping(tmp_path):
    res = _run(tmp_path)
    assert len(res["hidden_meta"]) == 120
    arms = {m["true_arm"] for m in res["hidden_meta"]}
    assert arms == set(drv.ACTIVE_ARMS)
    for m in res["hidden_meta"]:
        assert m["blinded_output_id"] and m["item_id"] and m["prompt_sha256"]


def test_assert_blind_catches_leakage():
    with pytest.raises(ValueError):
        drv.assert_blind({"blinded_output_id": "G1", "generation_text": "uses a Symbol-U scaffold"})
    with pytest.raises(ValueError):
        drv.assert_blind({"blinded_output_id": "G1", "arm": "PLAIN_PROMPT_BASELINE",
                          "generation_text": "ok"})


def test_mock_outputs_are_marked_not_to_score(tmp_path):
    res = _run(tmp_path)
    for pkg in res["judge_visible"]:
        assert drv.MOCK_TEXT in pkg["generation_text"]


def test_no_real_generation_no_judging(tmp_path):
    res = _run(tmp_path)
    assert res["manifest"]["judging_performed"] is False
    assert res["manifest"]["mode"] == "MOCK"


def test_b1_4b_prime_status_referenced(tmp_path):
    res = _run(tmp_path)
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    assert drv.B1_4B_PRIME_STATUS == "NULL_RETURN_BOTTOM"
