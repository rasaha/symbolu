"""Tests for the HARDENED re-issued evidence-freeze declaration (Stage-4 step 4).

Proves: the historical Step-2 declaration stays unchanged AND stale (runner pin drifted); the new hardened
declaration re-pins every input to the hardened code and passes preflight + the full gate to the backend
boundary with NO model call; wrong declaration SHA and wrong items path fail-closed. NO real model, NO network.

Structure, not validated meaning. No GENUTILITY_*, no ONTOLOGICAL_SIGNAL. B1.4b′ NULL_RETURN_BOTTOM; Track B blocked.
"""
import hashlib
import json
import pathlib

import pytest

import run_b1_10_control_ext as R

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
V3_ITEMS = FROZEN / "b1_10_control_ext_items_v3_qwen.json"
HARDENED = FROZEN / "b1_10_control_ext_v3_HARDENED_EVIDENCE_FREEZE_DECLARED.json"
STEP2 = FROZEN / "b1_10_control_ext_v3_EVIDENCE_FREEZE_DECLARED.json"

HARDENED_SHA = "e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181"
STEP2_SHA = "9b1d4d63ecac2d99aa24c7d17f832310a4f25ea485c562efd3288f1669b444a6"
GOOD_SEED = R.DEFAULT_SEED


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


class FakeRealJudge:
    """Judge contract double: is_real=True but NO network/model; rate() would return canned text."""
    def __init__(self, model_id):
        self.is_real = True
        self.model_id = model_id
        self.revision_resolved = "cafef00dcafef00dcafef00dcafef00dcafef00d"
        self.temperature = 0
        self.scale = (0, 6)
        self.rubric = "b1_10_0_6"
        self.n_calls = 0

    def rate(self, prompt):
        self.n_calls += 1
        return "Score: 3\nWhy: canned."


def good_panel():
    return [FakeRealJudge(m) for m in R.ALLOWED_JUDGE_IDS]


# ---------------------------------------------------------------- historical Step-2 stays unchanged + stale
def test_historical_step2_unchanged():
    assert _sha(STEP2) == STEP2_SHA


def test_historical_step2_still_stale_on_runner_pin():
    keys = {m.split(":")[0] for m in R._recompute_pins(json.loads(STEP2.read_text()), HERE)}
    assert keys == {"runner"}, f"only the runner pin should be stale, got {keys}"


# ---------------------------------------------------------------- hardened declaration is valid
def test_hardened_declaration_sha_pinned():
    assert _sha(HARDENED) == HARDENED_SHA


def test_hardened_every_pinned_hash_matches_live():
    assert R._recompute_pins(json.loads(HARDENED.read_text()), HERE) == []


def test_hardened_preflight_passes():
    res = R.preflight_inputs(HARDENED, V3_ITEMS, [GOOD_SEED], expected_decl_sha=HARDENED_SHA)
    assert len(res["cells"]) == 72
    assert res["decl_sha256"] == HARDENED_SHA


def test_hardened_reaches_backend_boundary_no_model_call():
    panel = good_panel()
    plan = R.verify_real_run_preconditions(HARDENED, V3_ITEMS, panel, [GOOD_SEED], expected_decl_sha=HARDENED_SHA)
    assert plan["cleared"] is True and plan["n_cells"] == 72 and plan["expected_total_ratings"] == 216
    assert set(plan["judge_revisions"]) == set(R.ALLOWED_JUDGE_IDS)
    assert sum(j.n_calls for j in panel) == 0        # gate never calls a judge (no model call)


# ---------------------------------------------------------------- fail-closed
def test_hardened_wrong_decl_sha_fails():
    with pytest.raises(R.FreezeGateError, match="declaration SHA256 mismatch"):
        R.preflight_inputs(HARDENED, V3_ITEMS, [GOOD_SEED], expected_decl_sha="beef" * 16)


def test_hardened_wrong_items_path_fails():
    with pytest.raises(R.FreezeGateError, match="wrong items file"):
        R.preflight_inputs(HARDENED, FROZEN / "b1_10_control_ext_items.json", [GOOD_SEED])


# ---------------------------------------------------------------- structure / provenance
def test_hardened_declaration_structure():
    d = json.loads(HARDENED.read_text())
    assert d["evidence_freeze_declared"] is True
    assert d["experiment_identity"]["mode"] == "b1_10_control_ext"
    assert d["run_structure"]["n_cells"] == 72
    assert d["run_structure"]["deterministic_cell_shuffle_seeds"] == [20260712, 20260713]
    ids = [j["model_id"] for j in d["judge_configuration"]["panel"]]
    assert ids == list(R.ALLOWED_JUDGE_IDS)
    # formulas + missing-data + anti-circularity + supersession of the historical record
    assert "increment_over_source_condition(W)" in d["statistics_formulas"]
    assert d["missing_data_rule"]["no_imputation"] is True
    assert d["reissue"]["supersedes_step2_declaration_sha256"] == STEP2_SHA
    assert "anti_circularity_attestation" in d
    assert d["interpretation_lock"]["b1_4b_prime_status"] == "NULL_RETURN_BOTTOM"


def test_no_backend_call_during_preflight():
    # preflight takes no judge objects and imports no real backend
    R.preflight_inputs(HARDENED, V3_ITEMS, [GOOD_SEED])
    src = (HERE / "run_b1_10_control_ext.py").read_text()
    for banned in ("import torch", "import transformers", "openai"):
        assert banned not in src
