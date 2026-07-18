#!/usr/bin/env python3
"""Mock-only tests for run_b1_3_v3_with_b1_1_judges.py. NO real model calls, NO real scoring, NO freeze.
Run: python3 test_run_b1_3_v3_with_b1_1_judges.py"""
import json, pathlib, sys, io, contextlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_b1_3_v3_with_b1_1_judges as RUN

B3 = HERE / "b1_3_revised_layer3"
CONFIG = json.loads((B3 / "b1_3_v3_b1_1_judge_runner_config.json").read_text())


def test_b1_1_judge_config_discovery():
    # the B1.1 execution layer is importable and exposes the declared open-weight panel + validator
    assert hasattr(RUN.J, "LlamaJudgeAdapter") and hasattr(RUN.J, "MockJudgeAdapter")
    assert hasattr(RUN.J, "validate_judge") and hasattr(RUN.J, "DECLARED_JUDGES")
    for jid in CONFIG["judge_model_ids"]:
        assert jid in RUN.J.DECLARED_JUDGES, jid


def test_config_validation():
    assert CONFIG["run_mode_default"] == "probe-only"
    assert CONFIG["evidence_freeze_declared"] is False
    assert set(CONFIG["judge_model_ids"]) == {
        "meta-llama/Llama-3.1-8B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct", "google/gemma-2-9b-it"}
    assert CONFIG["malformed_refusal"]["tie_maps_to_half"] is False


def test_artifact_hash_verification():
    ok, mism, bound = RUN.verify_hashes(B3 / CONFIG["v3_freeze_manifest"])
    assert len(bound) == 16, len(bound)
    assert ok, f"hash mismatches: {mism}"   # v3 artifacts unchanged since manifest was written


def test_packet_blinding():
    rows = [json.loads(l) for l in (B3 / CONFIG["v3_stimuli_path"]).read_text().splitlines() if l.strip()]
    public, private = RUN.build_packets(rows)
    assert len(public) == len(rows) == 371
    for pk in public:
        assert set(pk) == set(RUN.JUDGE_FACING) | {"packet_id"}   # only judge-facing fields
        assert RUN.leak_scan(pk) == [], (pk["packet_id"], RUN.leak_scan(pk))
    # private map holds the truth (arms) and is NOT part of any public packet
    any_pid = public[0]["packet_id"]
    assert "arm_left" in private[any_pid] and "arm_right" in private[any_pid]


def test_ab_parser_rejects_b1_1_tie_semantics():
    assert RUN.parse_ab("A")["selected_option"] == "A"
    assert RUN.parse_ab("B\nconfidence: 4")["selected_option"] == "B"
    assert RUN.parse_ab("B\nconfidence: 4")["confidence"] == 4
    # B1.1 vocabulary must be rejected (no tie->0.5, no output_1/output_2 reuse)
    for tok in ("output_1_better", "output_2_better", "tie_no_preference", "both_bad"):
        r = RUN.parse_ab(tok)
        assert r["invalid_flag"] is True and r["selected_option"] is None, tok
    assert RUN.parse_ab("")["invalid_flag"] is True
    assert RUN.parse_ab("I cannot answer that")["parse_status"] == "refused"


def test_score_frozen_refuses_without_evidence_freeze():
    # no declaration file exists -> score-frozen must refuse (SystemExit)
    assert not (B3 / "b1_3_v3_EVIDENCE_FREEZE_DECLARED.json").exists()
    ok, why = RUN.freeze_declared()
    assert ok is False
    try:
        RUN.mode_score_frozen(CONFIG)
        raise AssertionError("score-frozen did not refuse")
    except SystemExit as e:
        assert "REFUSED" in str(e)


def test_probe_only_synthetic_only_no_real_calls():
    out = RUN.mode_probe_only(CONFIG, real=False, verbose=False)
    assert out["synthetic_only"] is True and out["real_model_call"] is False
    # synthetic probe packets are NOT real B1.3 objects
    real_words = {json.loads(l)["target_word"] for l in
                  (B3 / CONFIG["v3_stimuli_path"]).read_text().splitlines() if l.strip()}
    for pk in RUN.SYNTHETIC_PROBE_PACKETS:
        assert pk["target_word"] not in real_words, pk["target_word"]
    # mock adapter emits compliant A/B for every judge
    for jid, res in out["results"].items():
        assert res["adapter"] == "mock" and res["compliant"] == res["n"] and res["invalid"] == 0


def test_three_model_judging_loop_mock():
    # the actual 3-model x 371-comparison loop, exercised with the MOCK adapter into a TMP dir
    # (no model call, no freeze, nothing written to the repo)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        summ = RUN.build_judge_outputs(CONFIG, real=False, out_dir=td, resume=False, verbose=False)
        assert summ["adapter"] == "mock"
        assert summ["n_models"] == 3 and summ["n_packets"] == 371
        assert summ["expected_total"] == 371 * 3 == summ["n_written"]
        rows = [json.loads(l) for l in open(summ["judge_outputs"]).read().splitlines() if l.strip()]
        assert len(rows) == 1113
        models = {r["model_id"] for r in rows}
        assert models == set(CONFIG["judge_model_ids"])            # all 3 judges present
        for r in rows[:50]:
            assert r["selected_option"] in ("A", "B") and r["invalid_flag"] is False
            assert "arm_left" in r and "arm_right" in r             # truth carried for scoring
        # resume: a second pass writes 0 new rows
        summ2 = RUN.build_judge_outputs(CONFIG, real=False, out_dir=td, resume=True, verbose=False)
        assert summ2["n_written"] == 0


def test_freeze_check_no_scoring():
    out = RUN.mode_freeze_check(CONFIG, verbose=False)
    assert out["scored"] is False
    assert out["v3_source_audit_pass"] is True
    assert out["judge_ids_in_declared_panel"] is True
    assert out["hashes_ok"] is True and out["ready"] is True


def test_no_real_score_output_written():
    # running probe-only + freeze-check must not create any score/judge-output artifact
    before = set(p.name for p in B3.glob("*"))
    RUN.mode_probe_only(CONFIG, real=False, verbose=False)
    RUN.mode_freeze_check(CONFIG, verbose=False)
    after = set(p.name for p in B3.glob("*"))
    created = after - before
    assert not any(("score_report" in n or "judge_outputs" in n) for n in created), created


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
