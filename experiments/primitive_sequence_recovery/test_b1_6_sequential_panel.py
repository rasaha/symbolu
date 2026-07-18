"""Tests for the B1.6-v2 sequential single-GPU panel path. FakeAdapters only; NO model, NO external API,
NO judging. Verifies partial counts, merge count, re-blinding, no leakage, and mismatch refusals."""
import json
import hashlib
import copy
import pathlib
import pytest

import b1_6_model_panel as P
import b1_6_llm_adapter as A
import run_b1_6_pilot_generation as drv


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _decl(tmp_path, mode=drv.EXPLORATORY_MODE, representation="v2_named_vritti"):
    r = drv.REPRESENTATIONS[representation]
    decl = {
        "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True, "mode": mode,
        "representation_version": representation,
        "scaffold_manifest_sha256": _sha(r["manifest"]),
        "target_scaffold_sha256": _sha(r["targets"]),
        "randomized_control_manifest_sha256": _sha(r["randctl"]),
        "prompt_rubric_sha256": _sha(drv.PROMPT_RUBRIC_FILE),
        "declared_by": "operator-test", "declared_at_utc": "2026-07-08T00:00:00Z",
        "attestation": drv.ATTESTATIONS[mode],
    }
    p = tmp_path / "decl.json"; p.write_text(json.dumps(decl))
    return p


def _panel():
    return {
        "generator_models": [
            {"id": "mistralai/Mistral-7B-Instruct-v0.3", "family": "Mistral", "revision": "r1"},
            {"id": "Qwen/Qwen2.5-7B-Instruct", "family": "Qwen", "revision": "r2"},
        ],
        "judge_models": [
            {"id": "meta-llama/Llama-3.1-8B-Instruct", "family": "Llama", "revision": "r3"},
            {"id": "meta-llama/Meta-Llama-3-8B-Instruct", "family": "Llama", "revision": "r4"},
            {"id": "google/gemma-2-9b-it", "family": "Gemma", "revision": "r5"},
        ],
    }


def _part(tmp_path, idx):
    decl = _decl(tmp_path)
    return P.run_single_generator_panel_part(
        _panel(), gen_index=idx, adapter_factory=lambda g: A.FakeAdapter(), mock=False,
        mode=drv.EXPLORATORY_MODE, limit_items=10, representation="v2_named_vritti",
        decl_path=decl, out_dir=tmp_path / f"partial_M{idx+1}", write=True)


def test_m1_partial_50(tmp_path):
    part = _part(tmp_path, 0)
    assert part["generator_code"] == "M1" and part["n_outputs"] == 50
    assert part["representation_version"] == "v2_named_vritti"
    assert (tmp_path / "partial_M1" / "panel_part.json").exists()


def test_m2_partial_50(tmp_path):
    part = _part(tmp_path, 1)
    assert part["generator_code"] == "M2" and part["n_outputs"] == 50


def test_merge_produces_100(tmp_path):
    p1, p2 = _part(tmp_path, 0), _part(tmp_path, 1)
    res = P.merge_panel_parts([p1, p2], out_dir=tmp_path / "generation", write=True)
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_READY_MOCK_TESTED"
    m = res["panel_manifest"]
    assert m["n_outputs"] == 100 and m["per_generator_counts"] == {"M1": 50, "M2": 50}
    assert m["orchestration"] == "SEQUENTIAL_MERGE" and m["representation_version"] == "v2_named_vritti"
    assert (tmp_path / "generation" / "panel_judge_visible_outputs.jsonl").exists()


def test_merge_reblinds_fresh_ids(tmp_path):
    res = P.merge_panel_parts([_part(tmp_path, 0), _part(tmp_path, 1)])
    ids = [p["blinded_output_id"] for p in res["judge_visible"]]
    assert ids == sorted(ids) and ids[0] == "F0001" and ids[-1] == "F0100" and len(ids) == 100
    codes = [h["generator_code"] for h in res["hidden_meta"]]
    assert codes[:50] != ["M1"] * 50          # generators interleaved by re-blind, not blocked


def test_no_generator_or_arm_leak_in_judge_visible(tmp_path):
    res = P.merge_panel_parts([_part(tmp_path, 0), _part(tmp_path, 1)])
    blob = json.dumps(res["judge_visible"])
    assert "Mistral" not in blob and "Qwen" not in blob
    assert "generator_code" not in blob and "generator_id" not in blob and "true_arm" not in blob
    for pkg in res["judge_visible"]:
        assert set(pkg.keys()) == {"item_id", "target_text", "neutral_context",
                                   "blinded_output_id", "generation_text", "output_format"}
    hm = res["hidden_meta"]
    assert all("generator_code" in h and "true_arm" in h for h in hm)


def test_sequential_matches_simultaneous_panel(tmp_path):
    # same seed => sequential merge yields the same final ids/order as the all-at-once panel
    seq = P.merge_panel_parts([_part(tmp_path, 0), _part(tmp_path, 1)], reblind_seed=20260708)
    sim = P.run_panel(_panel(), adapter_factory=lambda g: A.FakeAdapter(), mock=False,
                      mode=drv.EXPLORATORY_MODE, limit_items=10, decl_path=_decl(tmp_path),
                      reblind_seed=20260708)
    seq_map = {p["blinded_output_id"]: p["generation_text"] for p in seq["judge_visible"]}
    sim_map = {p["blinded_output_id"]: p["generation_text"] for p in sim["judge_visible"]}
    assert seq_map == sim_map


def test_merge_refuses_representation_mismatch(tmp_path):
    p1, p2 = _part(tmp_path, 0), _part(tmp_path, 1)
    p2 = copy.deepcopy(p2); p2["representation_version"] = "v1_directional"
    res = P.merge_panel_parts([p1, p2])
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE"
    assert any("representation_version mismatch" in r for r in res["reasons"])


def test_merge_refuses_target_subset_mismatch(tmp_path):
    p1, p2 = _part(tmp_path, 0), _part(tmp_path, 1)
    p2 = copy.deepcopy(p2); p2["item_ids"] = p2["item_ids"][:-1] + ["b16-99"]
    res = P.merge_panel_parts([p1, p2])
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE"
    assert any("subset" in r for r in res["reasons"])


def test_merge_refuses_declaration_hash_mismatch(tmp_path):
    p1, p2 = _part(tmp_path, 0), _part(tmp_path, 1)
    p2 = copy.deepcopy(p2); p2["declaration_sha256"] = "deadbeef"
    res = P.merge_panel_parts([p1, p2])
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE"
    assert any("declaration_sha256 mismatch" in r for r in res["reasons"])


def test_merge_refuses_duplicate_generator(tmp_path):
    p1 = _part(tmp_path, 0)
    res = P.merge_panel_parts([p1, copy.deepcopy(p1)])
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE"
    assert any("duplicate generator_code" in r for r in res["reasons"])


def test_merge_refuses_single_part(tmp_path):
    res = P.merge_panel_parts([_part(tmp_path, 0)])
    assert res["label"] == "B1_6_V2_SEQUENTIAL_PANEL_GENERATION_BLOCKED_MERGE"


def test_part_refuses_without_declaration(tmp_path):
    with pytest.raises(PermissionError):
        P.run_single_generator_panel_part(_panel(), gen_index=0,
                                          adapter_factory=lambda g: A.FakeAdapter(), mock=False,
                                          decl_path=tmp_path / "nope.json")


def test_load_part_roundtrip(tmp_path):
    _part(tmp_path, 0)
    loaded = P.load_part(tmp_path / "partial_M1")
    assert loaded["generator_code"] == "M1" and loaded["n_outputs"] == 50
