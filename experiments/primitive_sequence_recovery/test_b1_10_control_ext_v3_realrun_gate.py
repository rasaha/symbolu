"""Fail-closed real-run gate tests for the B1.10 control-ext v3 runner (Stage-4 step 3 hardening).

Proves every abort path AND that valid inputs reach the backend boundary WITHOUT any real model call.
Uses an in-test CONSISTENT declaration (pins recomputed to the live files, i.e. a 're-issued' freeze) so the
tests do not depend on the committed Step-2 declaration (whose runner pin is intentionally stale after this
hardening). A FakeRealJudge test double satisfies the judge contract with NO network/torch.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib
import shutil

import pytest

import run_b1_10_control_ext as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_ITEMS = FROZEN / "b1_10_control_ext_items_v3_qwen.json"
COMMITTED_DECL = FROZEN / "b1_10_control_ext_v3_EVIDENCE_FREEZE_DECLARED.json"
GOOD_SEED = R.DEFAULT_SEED           # 20260712 (a declared seed)


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def build_consistent_decl(tmp_path, mutate=None) -> pathlib.Path:
    """Re-pin the committed declaration to the LIVE files (a consistent 're-issued' freeze), optionally
    mutate the dict, and write to a temp path."""
    d = json.loads(COMMITTED_DECL.read_text())
    for key, rec in d["pinned_input_hashes"].items():
        if "path" in rec:
            rec["sha256"] = _sha(HERE / rec["path"])
    md = (HERE / "B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md").read_text()
    block = md.split("```")[1].strip("\n") + "\n"
    d["pinned_input_hashes"]["approved_canonical_12_sentence_block"]["sha256"] = \
        hashlib.sha256(block.encode()).hexdigest()
    if mutate:
        mutate(d)
    p = tmp_path / "decl.json"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    return p


class FakeRealJudge:
    """Test double satisfying the gate's judge contract. is_real=True (so the gate accepts it) but it makes
    NO network/model call — rate() returns a canned score. Used to prove plumbing without a real backend."""
    def __init__(self, model_id, revision_resolved="cafef00dcafef00dcafef00dcafef00dcafef00d",
                 temperature=0, scale=(0, 6), rubric="b1_10_0_6"):
        self.is_real = True
        self.model_id = model_id
        self.revision_resolved = revision_resolved
        self.temperature = temperature
        self.scale = scale
        self.rubric = rubric
        self.n_calls = 0

    def rate(self, prompt):
        self.n_calls += 1
        return "Score: 3\nWhy: canned mock rating (no model)."


def good_panel():
    return [FakeRealJudge(m) for m in R.ALLOWED_JUDGE_IDS]


# ---------------------------------------------------------------- backend boundary (valid inputs)
def test_valid_inputs_reach_backend_boundary_no_model_call(tmp_path):
    panel = good_panel()
    plan = R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, panel, [GOOD_SEED])
    assert plan["cleared"] is True
    assert plan["n_cells"] == 72
    assert plan["expected_total_ratings"] == 216
    assert set(plan["judge_revisions"]) == set(R.ALLOWED_JUDGE_IDS)
    # boundary only: the gate itself never calls a judge
    assert sum(j.n_calls for j in panel) == 0


# ---------------------------------------------------------------- fail-closed aborts
def test_altered_pinned_file_aborts(tmp_path):
    def corrupt(d):
        d["pinned_input_hashes"]["v3_polarity_table"]["sha256"] = "0" * 64
    with pytest.raises(R.FreezeGateError, match="pinned input hash mismatch"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path, corrupt), V3_ITEMS, good_panel(), [GOOD_SEED])


def test_declaration_sha_mismatch_aborts(tmp_path):
    with pytest.raises(R.FreezeGateError, match="declaration SHA256 mismatch"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, good_panel(), [GOOD_SEED],
                                        expected_decl_sha="dead" * 16)


def test_wrong_items_path_aborts(tmp_path):
    with pytest.raises(R.FreezeGateError, match="wrong items file"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path),
                                        FROZEN / "b1_10_pole_context_microtest_items.json", good_panel(), [GOOD_SEED])


def test_excluded_context_items_refused(tmp_path):
    # the ORIGINAL excluded-development-context items file must be rejected
    with pytest.raises(R.FreezeGateError, match="wrong items file"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path),
                                        FROZEN / "b1_10_control_ext_items.json", good_panel(), [GOOD_SEED])


def test_wrong_judge_id_aborts(tmp_path):
    panel = [FakeRealJudge("meta-llama/Llama-3.1-8B-Instruct"),
             FakeRealJudge("meta-llama/Llama-2-7b-chat-hf"),           # not in the allowed panel
             FakeRealJudge("google/gemma-2-9b-it")]
    with pytest.raises(R.FreezeGateError, match="judge panel must be EXACTLY"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, panel, [GOOD_SEED])


def test_forbidden_judge_family_aborts(tmp_path):
    panel = [FakeRealJudge("meta-llama/Llama-3.1-8B-Instruct"),
             FakeRealJudge("Qwen/Qwen2.5-7B-Instruct"),                # forbidden family
             FakeRealJudge("google/gemma-2-9b-it")]
    with pytest.raises(R.FreezeGateError, match="forbidden judge family"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, panel, [GOOD_SEED])


def test_unresolved_revision_aborts(tmp_path):
    panel = good_panel()
    panel[1].revision_resolved = "main"                                # unresolved
    with pytest.raises(R.FreezeGateError, match="unresolved judge revision"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, panel, [GOOD_SEED])


def test_wrong_seed_aborts(tmp_path):
    with pytest.raises(R.FreezeGateError, match="not one of the declared seeds"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, good_panel(), [20260714])


def test_non_real_backend_aborts(tmp_path):
    with pytest.raises(R.FreezeGateError, match="real judge backend required"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS,
                                        [R.FakeJudge(), R.FakeJudge(), R.FakeJudge()], [GOOD_SEED])


def test_wrong_temperature_aborts(tmp_path):
    panel = good_panel()
    panel[0].temperature = 0.7                                          # not greedy
    with pytest.raises(R.FreezeGateError, match="greedy decoding"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path), V3_ITEMS, panel, [GOOD_SEED])


def test_missing_declaration_aborts():
    with pytest.raises(R.FreezeGateError, match="declaration missing"):
        R.verify_real_run_preconditions(None, V3_ITEMS, good_panel(), [GOOD_SEED])


def test_duplicate_missing_cell_aborts(tmp_path, monkeypatch):
    # build a malformed items file (one word dropped -> 60 cells) and point the approved-items enforcement at it
    items = json.loads(V3_ITEMS.read_text())
    items["words"] = items["words"][:-1]                               # drop 'doubt' -> 5 words
    bad = tmp_path / "bad_items.json"
    bad.write_text(json.dumps(items, ensure_ascii=False, indent=2))
    monkeypatch.setattr(R, "APPROVED_ITEMS_FILE", bad)

    def repin(d):
        # point the pin at the malformed file so hash-check (step 2) passes and the cell-count guard (step 3) fires
        d["pinned_input_hashes"]["rebuilt_v3_items_file"]["path"] = str(bad)
        d["pinned_input_hashes"]["rebuilt_v3_items_file"]["sha256"] = _sha(bad)
    with pytest.raises(R.FreezeGateError, match="not 72 unique"):
        R.verify_real_run_preconditions(build_consistent_decl(tmp_path, repin), bad, good_panel(), [GOOD_SEED])


# ---------------------------------------------------------------- run_real_gated gating
def test_run_real_gated_requires_run_id(tmp_path):
    with pytest.raises(R.FreezeGateError, match="run_id is required"):
        R.run_real_gated(build_consistent_decl(tmp_path), good_panel(), seed=GOOD_SEED, run_id=None)


def test_run_real_gated_refuses_non_gitignored_dir(tmp_path):
    # tmp_path is NOT git-ignored -> must refuse to write outputs there
    with pytest.raises(R.FreezeGateError, match="not git-ignored"):
        R.run_real_gated(build_consistent_decl(tmp_path), good_panel(), seed=GOOD_SEED,
                         run_id="pytest_nogitignore", run_root=tmp_path)


def test_run_real_gated_end_to_end_plumbing_no_real_model(tmp_path):
    # full 216-rating plumbing with FakeRealJudge into the git-ignored runs/ dir; NO real model call
    run_id = "pytest_gate_plumbing"
    run_dir = R.RUN_ROOT / f"b1_10_control_ext_v3_run_{run_id}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    try:
        panel = good_panel()
        man = R.run_real_gated(build_consistent_decl(tmp_path), panel, seed=GOOD_SEED, run_id=run_id)
        assert man["n_ratings_collected"] == 216 and man["n_cells"] == 72 and man["n_judges"] == 3
        assert set(man["judge_revisions"]) == set(R.ALLOWED_JUDGE_IDS)
        # no verdict label anywhere in the run manifest
        blob = json.dumps(man)
        for v in ("PASS", "FAIL", "VALIDATED", "PROVES", "GENUTILITY", "ONTOLOGICAL_SIGNAL"):
            assert v not in blob
        assert (run_dir / "aggregation_inputs.json").exists()
        assert sum(j.n_calls for j in panel) == 216
    finally:
        if run_dir.exists():
            shutil.rmtree(run_dir)


# ---------------------------------------------------------------- no real backend imported; history intact
def test_runner_has_no_real_backend_imports():
    src = (HERE / "run_b1_10_control_ext.py").read_text()
    for banned in ("import torch", "import transformers", "openai", "\nimport requests"):
        assert banned not in src


def test_historical_artifacts_unchanged():
    assert _sha(FROZEN / "b1_10_control_ext_items.json") == \
        "df76b7feb1aa8534f5bd62c57b429478f8ea523911ad0bd6bb38f556f2a00ba9"
    assert _sha(FROZEN / "b1_10_pole_context_microtest_items.json") == \
        "9d70bb863f49ba06b84dd2eb5463b04d95755fe0b7b371c1d2ebcd3b1832b3bd"
    assert _sha(FROZEN / "b1_10_EVIDENCE_FREEZE_DECLARED.json") == \
        "e34b21735785ac0dd8a4444fbfcbfa0857082f92f2d429b5b09e1db8aadf6b1a"
    assert _sha(COMMITTED_DECL) == \
        "9b1d4d63ecac2d99aa24c7d17f832310a4f25ea485c562efd3288f1669b444a6"
