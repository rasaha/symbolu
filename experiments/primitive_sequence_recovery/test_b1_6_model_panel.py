"""Tests for B1.6 multi-model panel orchestration. FakeAdapters only; NO model, NO external API,
NO judging. Verifies output counts, blinding (generator id hidden), conflict detection, manifest hash."""
import json
import hashlib
import pathlib
import pytest

import b1_6_model_panel as P
import b1_6_llm_adapter as A
import run_b1_6_pilot_generation as drv


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _decl(tmp_path, mode, representation="v2_named_vritti"):
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


def _clean_panel():
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


def test_validate_clean_panel():
    ok, reasons = P.validate_panel(_clean_panel())
    assert ok, reasons


def test_validate_rejects_missing_generators():
    ok, reasons = P.validate_panel({"generator_models": [], "judge_models": _clean_panel()["judge_models"]})
    assert not ok and any("generator" in r for r in reasons)


def test_no_conflict_on_distinct_families():
    assert P.detect_same_model_conflicts(_clean_panel()) == []


def test_same_model_conflict_detected():
    panel = _clean_panel()
    panel["judge_models"].append({"id": "Qwen/Qwen2.5-7B-Instruct", "family": "Qwen", "revision": "rx"})
    conflicts = P.detect_same_model_conflicts(panel)
    assert any(c["type"] == "SAME_MODEL" for c in conflicts)


def test_same_family_conflict_detected():
    panel = _clean_panel()
    panel["generator_models"].append({"id": "google/gemma-2-2b-it", "family": "Gemma", "revision": "rg"})
    conflicts = P.detect_same_model_conflicts(panel)
    assert any(c["type"] == "SAME_FAMILY" and c["family"] == "Gemma" for c in conflicts)


def test_two_generators_10_sample_output_count(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), adapter_factory=lambda g: A.FakeAdapter(),
                      mock=False, mode=drv.EXPLORATORY_MODE, limit_items=10, decl_path=decl,
                      out_dir=tmp_path / "o", write=True)
    m = res["panel_manifest"]
    assert m["expected_outputs"] == 100          # 10 targets x 5 arms x 2 generators
    assert m["n_outputs"] == 100
    assert m["per_generator_counts"] == {"M1": 50, "M2": 50}
    assert m["representation_version"] == "v2_named_vritti"   # panel defaults to v2


def test_mock_panel_count(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), mock=True, mode=drv.EXPLORATORY_MODE, limit_items=10,
                      decl_path=decl, out_dir=tmp_path / "o", write=False)
    assert res["panel_manifest"]["n_outputs"] == 100


def test_generator_id_only_in_hidden_not_judge_visible(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), adapter_factory=lambda g: A.FakeAdapter(),
                      mock=False, mode=drv.EXPLORATORY_MODE, limit_items=10, decl_path=decl,
                      out_dir=tmp_path / "o", write=False)
    jv_blob = json.dumps(res["judge_visible"])
    # no generator model id or opaque code or arm in judge-visible
    assert "Mistral" not in jv_blob and "Qwen" not in jv_blob
    assert "generator_code" not in jv_blob and "generator_id" not in jv_blob
    for pkg in res["judge_visible"]:
        assert set(pkg.keys()) == {"item_id", "target_text", "neutral_context",
                                   "blinded_output_id", "generation_text", "output_format"}
    # hidden metadata retains generator + arm mapping
    hm = res["hidden_meta"]
    assert all("generator_code" in h and "true_arm" in h for h in hm)
    assert {h["generator_code"] for h in hm} == {"M1", "M2"}


def test_reblind_hides_generator_grouping(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), adapter_factory=lambda g: A.FakeAdapter(),
                      mock=False, mode=drv.EXPLORATORY_MODE, limit_items=10, decl_path=decl,
                      out_dir=tmp_path / "o", write=False)
    ids = [p["blinded_output_id"] for p in res["judge_visible"]]
    assert ids == sorted(ids) and ids[0] == "F0001" and len(ids) == 100
    # generator codes are interleaved across the re-blinded order (not blocked M1 then M2)
    codes = [h["generator_code"] for h in res["hidden_meta"]]
    assert codes[:50] != ["M1"] * 50


def test_panel_manifest_hash_recorded(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), mock=True, mode=drv.EXPLORATORY_MODE, limit_items=10,
                      decl_path=decl, out_dir=tmp_path / "o", write=False)
    m = res["panel_manifest"]
    assert len(m["panel_sha256"]) == 64
    assert m["generator_codes"] == {"M1": "mistralai/Mistral-7B-Instruct-v0.3",
                                    "M2": "Qwen/Qwen2.5-7B-Instruct"}


def test_no_genutility_and_no_judging(tmp_path):
    decl = _decl(tmp_path, drv.EXPLORATORY_MODE)
    res = P.run_panel(_clean_panel(), mock=True, mode=drv.EXPLORATORY_MODE, limit_items=10,
                      decl_path=decl, out_dir=tmp_path / "o", write=False)
    blob = json.dumps(res)
    import re
    assert not re.search(r"GENUTILITY_[A-Z]", blob)
    assert res["panel_manifest"]["judging_performed"] is False
    assert res["panel_manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"


def test_panel_refuses_without_declaration(tmp_path):
    with pytest.raises(PermissionError):
        P.run_panel(_clean_panel(), mock=True, mode=drv.EXPLORATORY_MODE, limit_items=10,
                    decl_path=tmp_path / "nope.json", out_dir=tmp_path / "o", write=False)
