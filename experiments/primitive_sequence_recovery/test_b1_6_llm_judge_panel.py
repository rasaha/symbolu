"""Tests for the B1.6-v2 automated LLM-as-judge panel. FakeJudgeAdapter only; NO model, NO external API,
NO ratings freeze, NO unblinding. Judges read ONLY the blind judge-visible file."""
import json
import hashlib
import copy
import pathlib
import pytest

import b1_6_llm_judge_panel as JP
import judge_b1_6_pilot_outputs as J


def _blind_jv(n=12):
    out = []
    for i in range(n):
        out.append({
            "item_id": f"b16-{(i % 5) + 1:02d}",
            "target_text": ["river", "balance", "Maya", "lotus", "grief"][i % 5],
            "neutral_context": "A test item.",
            "blinded_output_id": f"F{i+1:04d}",
            "generation_text": f"Title: t{i}\nInterpretation: a b c\nPractical reflection:\n- x\n- y\nCaution: limited.",
            "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution",
        })
    return out


def _write_jv(tmp_path, rows, name="panel_judge_visible_outputs.jsonl"):
    f = tmp_path / name
    f.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    return f


JUDGES = JP.REFERENCE_JUDGES
GENERATORS = [{"id": "mistralai/Mistral-7B-Instruct-v0.3", "family": "Mistral"},
              {"id": "Qwen/Qwen2.5-7B-Instruct", "family": "Qwen"}]


# ---- no-same-model rule --------------------------------------------------------------
def test_no_conflict_llama_gemma_vs_mistral_qwen():
    assert JP.detect_judge_generator_conflicts(JUDGES, GENERATORS) == []


def test_same_model_conflict():
    c = JP.detect_judge_generator_conflicts(JUDGES + [GENERATORS[1]], GENERATORS)
    assert any(x["type"] == "SAME_MODEL" for x in c)


def test_same_family_conflict():
    c = JP.detect_judge_generator_conflicts(JUDGES + [{"id": "Qwen/Qwen2.5-0.5B", "family": "Qwen"}], GENERATORS)
    assert any(x["type"] == "SAME_FAMILY" for x in c)


# ---- blindness / hidden-metadata protection ------------------------------------------
def test_run_reads_only_blind_fields(tmp_path):
    f = _write_jv(tmp_path, _blind_jv(6))
    part = JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter(JUDGES[0]["id"]))
    assert part["reads_hidden_metadata"] is False and part["unblinded"] is False
    blob = json.dumps(part)
    assert "true_arm" not in blob and "generator_code" not in blob and "generator_id" not in blob


def test_run_refuses_non_blind_input(tmp_path):
    rows = _blind_jv(4); rows[0]["true_arm"] = "SYMBOLU_SCAFFOLD"    # leaked hidden key
    f = _write_jv(tmp_path, rows)
    with pytest.raises(ValueError):
        JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter())


def test_run_refuses_generator_id_leak(tmp_path):
    rows = _blind_jv(4); rows[1]["generator_id"] = "Qwen/Qwen2.5-7B-Instruct"
    f = _write_jv(tmp_path, rows)
    with pytest.raises(ValueError):
        JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter())


# ---- single judge + parse ------------------------------------------------------------
def test_single_judge_rates_all(tmp_path):
    f = _write_jv(tmp_path, _blind_jv(10))
    part = JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter(JUDGES[0]["id"]))
    assert part["n_ratings"] == 10 and part["n_errors"] == 0
    r = part["ratings"][0]
    assert r["judge_id"] == JUDGES[0]["id"]
    for d in JP.ALL_DIMS:
        assert JP.SCALE_MIN <= r[d] <= JP.SCALE_MAX


def test_malformed_judge_json_detected(tmp_path):
    f = _write_jv(tmp_path, _blind_jv(5))
    part = JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter(malformed=True))
    assert part["n_ratings"] == 0 and part["n_errors"] == 5


def test_parse_out_of_range_rejected():
    dims, reasons = JP.parse_judge_json('{"coherence": 9, ...}')
    assert dims is None and reasons


def test_limit_outputs_smoke(tmp_path):
    f = _write_jv(tmp_path, _blind_jv(12))
    part = JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter(), limit_outputs=3)
    assert part["n_ratings"] == 3


# ---- 3-judge merge -------------------------------------------------------------------
def _three_parts(tmp_path, n=12):
    f = _write_jv(tmp_path, _blind_jv(n))
    return [JP.run_single_judge(j, f, adapter=JP.FakeJudgeAdapter(j["id"])) for j in JUDGES], f


def test_three_judge_merge_count(tmp_path):
    parts, _ = _three_parts(tmp_path, 12)
    res = JP.merge_judge_parts(parts, out_dir=tmp_path / "o", write=True)
    assert res["label"] == "B1_6_V2_LLM_JUDGE_PANEL_READY_MOCK_TESTED"
    m = res["manifest"]
    assert m["n_outputs"] == 12 and m["n_judges"] == 3
    assert m["n_ratings"] == 36 and m["expected_ratings"] == 36     # 12 x 3
    assert (tmp_path / "o" / "llm_judge_ratings_raw.jsonl").exists()


def test_expected_100x3(tmp_path):
    # 100 outputs x 3 judges = 300 ratings
    parts, _ = _three_parts(tmp_path, 100)
    res = JP.merge_judge_parts(parts)
    assert res["manifest"]["expected_ratings"] == 300 and res["manifest"]["n_ratings"] == 300


def test_merge_refuses_duplicate_judge(tmp_path):
    parts, _ = _three_parts(tmp_path, 6)
    res = JP.merge_judge_parts([parts[0], copy.deepcopy(parts[0])])
    assert res["label"] == "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT"
    assert any("duplicate judge_id" in r for r in res["reasons"])


def test_merge_refuses_incomplete_grid(tmp_path):
    parts, _ = _three_parts(tmp_path, 6)
    parts[2] = copy.deepcopy(parts[2]); parts[2]["ratings"] = parts[2]["ratings"][:-2]   # drop 2
    res = JP.merge_judge_parts(parts)
    assert res["label"] == "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT"
    assert any("missing" in r for r in res["reasons"])


def test_merge_refuses_judge_errors(tmp_path):
    f = _write_jv(tmp_path, _blind_jv(6))
    good = [JP.run_single_judge(JUDGES[0], f, adapter=JP.FakeJudgeAdapter(JUDGES[0]["id"])),
            JP.run_single_judge(JUDGES[1], f, adapter=JP.FakeJudgeAdapter(JUDGES[1]["id"]))]
    bad = JP.run_single_judge(JUDGES[2], f, adapter=JP.FakeJudgeAdapter(malformed=True))
    res = JP.merge_judge_parts(good + [bad])
    assert res["label"] == "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT"


def test_merge_refuses_different_packages(tmp_path):
    f1 = _write_jv(tmp_path, _blind_jv(6), "panel_judge_visible_outputs.jsonl")
    f2 = _write_jv(tmp_path, _blind_jv(7), "other.jsonl")
    p1 = JP.run_single_judge(JUDGES[0], f1, adapter=JP.FakeJudgeAdapter(JUDGES[0]["id"]))
    p2 = JP.run_single_judge(JUDGES[1], f2, adapter=JP.FakeJudgeAdapter(JUDGES[1]["id"]))
    res = JP.merge_judge_parts([p1, p2])
    assert res["label"] == "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT"


# ---- scorer accepts the merged ratings (after a ratings-freeze MOCK) ------------------
def _panel_hidden(jv):
    arms = ("SYMBOLU_SCAFFOLD", "PLAIN_PROMPT_BASELINE", "GENERIC_STRUCTURED_PROMPT_BASELINE",
            "RANDOMIZED_SYMBOLU_CONTROL", "SEMANTIC_LLM_BASELINE")
    return [{"blinded_output_id": p["blinded_output_id"], "true_arm": arms[i % 5],
             "item_id": p["item_id"], "generator_code": "M1" if i % 2 == 0 else "M2",
             "generator_id": "gen"} for i, p in enumerate(jv)]


def test_scorer_accepts_merged_ratings_after_mock_freeze(tmp_path):
    jv = _blind_jv(10); f = _write_jv(tmp_path, jv)
    parts = [JP.run_single_judge(j, f, adapter=JP.FakeJudgeAdapter(j["id"])) for j in JUDGES]
    merged = JP.merge_judge_parts(parts)["ratings"]
    rf = tmp_path / "ratings.jsonl"; rf.write_text("\n".join(json.dumps(r) for r in merged))
    # mock ratings-freeze declaration for the scorer's gate
    def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    fz = {"artifact": "b1_6_pilot_RATINGS_FROZEN", "ratings_frozen": True, "mode": "pilot_judging",
          "judge_visible_outputs_sha256": sha(f), "ratings_file_sha256": sha(rf),
          "declared_by": "op", "declared_at_utc": "2026-07-08T00:00:00Z",
          "attestation": J.RATINGS_ATTESTATION}
    fzp = tmp_path / "frozen.json"; fzp.write_text(json.dumps(fz))
    hm = _panel_hidden(jv)
    res = J.aggregate(merged, hm, freeze_path=fzp, judge_visible_file=f, ratings_file=rf,
                      representation_version="v2_named_vritti")
    assert res["label"] == "B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED"
    assert res["summary"]["representation_version"] == "v2_named_vritti"
    assert set(res["summary"]["generator_summary"].keys()) == {"M1", "M2"}


def test_no_genutility_and_status(tmp_path):
    parts, _ = _three_parts(tmp_path, 6)
    res = JP.merge_judge_parts(parts)
    import re
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))
    assert res["manifest"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"
    assert res["manifest"]["unblinded"] is False
