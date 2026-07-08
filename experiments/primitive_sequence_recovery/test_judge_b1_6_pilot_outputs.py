"""Mock tests for the B1.6 blind judging harness. NO real judging, NO generation,
NO ratings freeze on the real path. Uses fabricated judge-visible outputs + a temp
ratings-freeze declaration. Never emits a GENUTILITY_* terminal label."""
import json
import hashlib
import pathlib
import pytest

import judge_b1_6_pilot_outputs as J


def _jv(n=10):
    """Fabricated blinded outputs (blind: no arm names/scaffold/metadata)."""
    out = []
    for i in range(n):
        out.append({
            "item_id": f"b16-{(i % 5) + 1:02d}",
            "target_text": ["river", "balance", "Maya", "lotus", "grief"][i % 5],
            "neutral_context": "A test item.",
            "blinded_output_id": f"G{i+1:04d}",
            "generation_text": f"MOCK_JUDGING_ONLY_DO_NOT_INTERPRET title/interp/bullets/caution {i}",
            "output_format": "Title/Interpretation(120-180w)/2 bullets/Caution",
        })
    return out


def _hidden(jv):
    arms = J.PAIRWISE[0][0], "PLAIN_PROMPT_BASELINE", "GENERIC_STRUCTURED_PROMPT_BASELINE", \
        "RANDOMIZED_SYMBOLU_CONTROL", "SEMANTIC_LLM_BASELINE"
    return [{"blinded_output_id": p["blinded_output_id"], "true_arm": arms[i % 5],
             "item_id": p["item_id"], "prompt_sha256": "x" * 64} for i, p in enumerate(jv)]


def _write_jsonl(p, rows):
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


# ---- Phase A blindness ----------------------------------------------------------------
def test_blind_package_passes_when_clean(tmp_path):
    f = tmp_path / "jv.jsonl"; _write_jsonl(f, _jv())
    rep = J.phase_a_blind_package(f, out_dir=tmp_path / "o", write=True)
    assert rep["blind_ok"] and rep["label"] == "B1_6_PILOT_JUDGING_BLIND_PACKAGE_OK"


def test_blind_package_fails_on_arm_name_key(tmp_path):
    jv = _jv(); jv[0]["arm"] = "SYMBOLU_SCAFFOLD"
    f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    rep = J.phase_a_blind_package(f, out_dir=tmp_path / "o", write=False)
    assert rep["label"] == "B1_6_PILOT_JUDGING_INVALID_BLINDING"
    assert any("arm" in r for r in rep["reasons"])


def test_blind_package_fails_on_scaffold_field(tmp_path):
    jv = _jv(); jv[1]["VARNA_PROFILE_TABLE"] = {"ka": {}}
    f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    rep = J.phase_a_blind_package(f, out_dir=tmp_path / "o", write=False)
    assert rep["label"] == "B1_6_PILOT_JUDGING_INVALID_BLINDING"


def test_blind_package_fails_on_symbolu_kcpr_token_in_text(tmp_path):
    jv = _jv(); jv[2]["generation_text"] = "this reading uses the KCPR dual-pole scaffold"
    f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    rep = J.phase_a_blind_package(f, out_dir=tmp_path / "o", write=False)
    assert rep["label"] == "B1_6_PILOT_JUDGING_INVALID_BLINDING"
    assert any("token" in r for r in rep["reasons"])


def test_blind_package_blocked_when_no_outputs(tmp_path):
    rep = J.phase_a_blind_package(tmp_path / "missing.jsonl", out_dir=tmp_path / "o", write=False)
    assert rep["label"] == "B1_6_PILOT_JUDGING_BLOCKED_NO_GENERATED_OUTPUTS"


# ---- rating schema --------------------------------------------------------------------
def test_complete_rating_validates():
    r = {"blinded_output_id": "G0001"}
    for d in J.POSITIVE_DIMS: r[d] = 5
    for d in J.PENALTY_DIMS: r[d] = 1
    ok, reasons = J.validate_rating(r)
    assert ok, reasons


def test_incomplete_rating_rejected():
    r = {"blinded_output_id": "G0001", "coherence": 5}  # missing most dims
    ok, reasons = J.validate_rating(r)
    assert not ok and len(reasons) >= 1


def test_out_of_range_rating_rejected():
    r = {"blinded_output_id": "G0001"}
    for d in J.POSITIVE_DIMS: r[d] = 5
    for d in J.PENALTY_DIMS: r[d] = 1
    r["coherence"] = 9
    ok, reasons = J.validate_rating(r)
    assert not ok and any("range" in x for x in reasons)


def test_composites_penalty_reduces_score():
    r = {"blinded_output_id": "G", **{d: 6 for d in J.POSITIVE_DIMS},
         **{d: 1 for d in J.PENALTY_DIMS}}
    raw, adj = J.composites(r)
    assert raw == 6.0 and adj == 6.0            # penalty=1 -> no reduction
    r2 = {**r, "overclaim_penalty": 7, "hallucination_penalty": 7}
    raw2, adj2 = J.composites(r2)
    assert raw2 == 6.0 and adj2 < raw2          # penalty raised -> adjusted drops


# ---- ratings-freeze gate --------------------------------------------------------------
def _valid_freeze(tmp_path, jv_file, ratings_file):
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    decl = {
        "artifact": "b1_6_pilot_RATINGS_FROZEN",
        "ratings_frozen": True,
        "mode": "pilot_judging",
        "judge_visible_outputs_sha256": sha(jv_file),
        "ratings_file_sha256": sha(ratings_file),
        "declared_by": "operator-test",
        "declared_at_utc": "2026-07-08T00:00:00Z",
        "attestation": J.RATINGS_ATTESTATION,
    }
    p = tmp_path / "RATINGS_FROZEN.json"; p.write_text(json.dumps(decl))
    return p


def test_aggregation_refuses_before_freeze(tmp_path):
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    res = J.aggregate(ratings, hm, freeze_path=tmp_path / "nope.json",
                      judge_visible_file=f, ratings_file=tmp_path / "r.json",
                      require_freeze=True)
    assert res["label"] == "B1_6_PILOT_JUDGING_BLOCKED_RATINGS_NOT_FROZEN"


def test_aggregation_succeeds_after_mock_freeze(tmp_path):
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    rf = tmp_path / "ratings.json"; rf.write_text(json.dumps(ratings))
    fz = _valid_freeze(tmp_path, f, rf)
    res = J.aggregate(ratings, hm, freeze_path=fz, judge_visible_file=f,
                      ratings_file=rf, require_freeze=True, out_dir=tmp_path / "o", write=True)
    assert res["label"] == "B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED"
    assert set(res["summary"]["arm_summary"]) <= {
        "SYMBOLU_SCAFFOLD", "PLAIN_PROMPT_BASELINE", "GENERIC_STRUCTURED_PROMPT_BASELINE",
        "RANDOMIZED_SYMBOLU_CONTROL", "SEMANTIC_LLM_BASELINE"}
    # both composites present
    any_arm = next(iter(res["summary"]["arm_summary"].values()))
    assert "mean_raw_composite" in any_arm and "mean_penalty_adjusted_composite" in any_arm


def test_freeze_hash_mismatch_refuses(tmp_path):
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    rf = tmp_path / "ratings.json"; rf.write_text(json.dumps(ratings))
    fz = _valid_freeze(tmp_path, f, rf)
    # mutate ratings after freeze -> hash mismatch
    rf.write_text(json.dumps(ratings) + " ")
    res = J.aggregate(ratings, hm, freeze_path=fz, judge_visible_file=f,
                      ratings_file=rf, require_freeze=True)
    assert res["label"] == "B1_6_PILOT_JUDGING_BLOCKED_RATINGS_NOT_FROZEN"
    assert any("ratings_file_sha256 mismatch" in r for r in res["reasons"])


def test_incomplete_ratings_raise_in_aggregation(tmp_path):
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv)
    bad = [{"blinded_output_id": "G0001", "coherence": 5}]  # incomplete
    with pytest.raises(ValueError):
        J.aggregate(bad, hm, require_freeze=False)


def test_hidden_metadata_only_used_after_freeze(tmp_path):
    # before freeze: no arm mapping in the refusal result
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    res = J.aggregate(ratings, hm, freeze_path=tmp_path / "nope.json",
                      judge_visible_file=f, ratings_file=tmp_path / "r.json", require_freeze=True)
    assert "unblinded" not in res and "summary" not in res


def test_no_genutility_label_emitted(tmp_path):
    jv = _jv(); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    rf = tmp_path / "ratings.json"; rf.write_text(json.dumps(ratings))
    fz = _valid_freeze(tmp_path, f, rf)
    res = J.aggregate(ratings, hm, freeze_path=fz, judge_visible_file=f, ratings_file=rf)
    # no GENUTILITY_* *label/verdict* may be emitted (the disclaimer text may name it)
    assert not res["label"].startswith("GENUTILITY")
    assert res["summary"]["pilot_label"].startswith("B1_6_PILOT_JUDGING")
    assert res["summary"]["terminal_genutility_label_emitted"] is False
    import re
    # no concrete GENUTILITY verdict token (e.g. GENUTILITY_SYMBOLU_BEATS_...) present
    assert not re.search(r"GENUTILITY_[A-Z]", json.dumps(res))


def test_pairwise_contrasts_present(tmp_path):
    jv = _jv(20); f = tmp_path / "jv.jsonl"; _write_jsonl(f, jv)
    hm = _hidden(jv); ratings = J.mock_ratings(jv)
    rf = tmp_path / "ratings.json"; rf.write_text(json.dumps(ratings))
    fz = _valid_freeze(tmp_path, f, rf)
    res = J.aggregate(ratings, hm, freeze_path=fz, judge_visible_file=f, ratings_file=rf)
    pw = res["pairwise"]["pairwise_penalty_adjusted"]
    assert "SYMBOLU_SCAFFOLD_vs_PLAIN_PROMPT_BASELINE" in pw
    assert "SYMBOLU_SCAFFOLD_vs_RANDOMIZED_SYMBOLU_CONTROL" in pw


def test_b1_4b_prime_status_referenced():
    assert J.B1_4B_PRIME_STATUS == "NULL_RETURN_BOTTOM"
