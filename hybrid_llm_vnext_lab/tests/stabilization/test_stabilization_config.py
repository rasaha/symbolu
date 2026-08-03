"""Stdlib (torch-free) tests for the slot-formation-stabilization pre-registration, boundaries,
classifier logic, and selection rule. Run by scripts/run_stdlib_tests.py and in CI."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

LAB = pathlib.Path(__file__).resolve().parents[2]
EXP = LAB / "experiments" / "slot_formation_stabilization"
sys.path.insert(0, str(EXP))


def _json(name):
    return json.loads((EXP / name).read_text())


# ----------------------------------------------------------------- pre-registration integrity
def test_preregistration_verifier_passes():
    r = subprocess.run([sys.executable, str(EXP / "verify_preregistration.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_config_matches_frozen_architecture():
    mx = _json("EXPERIMENT_MATRIX.json")["frozen_architecture"]
    frozen = json.loads((LAB / "experiments" / "five_seed_slots" / "FROZEN_CONFIG.json").read_text())["config"]
    for k_mx, k_fz in [("hidden_dimension", "hidden_dimension"), ("attention_heads", "attention_heads"),
                       ("layers", "layers"), ("local_window", "local_window"), ("slots", "slot_count"),
                       ("slot_key_dimension", "slot_key_dim"), ("sequence_length", "sequence_length"),
                       ("batch_size", "batch_size"), ("training_steps", "training_steps")]:
        assert mx[k_mx] == frozen[k_fz], f"arch field drift {k_mx}: {mx[k_mx]} != {frozen[k_fz]}"


def test_seed_lists_frozen():
    mx = _json("EXPERIMENT_MATRIX.json")
    assert mx["stage_a"]["diagnostic_seeds"] == [3, 6, 7]
    assert mx["stage_b"]["fresh_seeds"] == [8, 9, 10, 11, 12]


def test_total_steps_1200():
    mx = _json("EXPERIMENT_MATRIX.json")
    assert mx["frozen_architecture"]["training_steps"] == 1200
    assert mx["stage_b"]["budget"].startswith("exactly 1200")


def test_arms_are_the_pre_registered_seven():
    mx = _json("EXPERIMENT_MATRIX.json")
    assert [a["id"] for a in mx["stage_a"]["arms"]] == ["B0", "O1", "O2", "K1", "C1", "R1", "CR1"]


def test_intervention_params_only_touch_allowed_surfaces():
    mx = _json("EXPERIMENT_MATRIX.json")
    arms = {a["id"]: a for a in mx["stage_a"]["arms"]}
    # O1/O2 differ ONLY in slot LR / slot warmup; non-slot untouched
    assert arms["O1"]["slot_lr"] == 1e-3 and arms["O1"]["slot_warmup"] == 180
    assert arms["O2"]["slot_lr"] == 3e-3 and arms["O2"]["slot_warmup"] == 180
    for a in ("O1", "O2"):
        assert arms[a]["nonslot_lr"] == 2e-3 and arms[a]["nonslot_warmup"] == 60
        assert not arms[a]["orthogonal_keys"] and not arms[a]["curriculum"] and not arms[a]["alignment"]
    # K1 differs ONLY in orthogonal keys
    assert arms["K1"]["orthogonal_keys"] and not arms["K1"]["curriculum"] and not arms["K1"]["alignment"]
    assert arms["K1"]["slot_lr"] == 2e-3 and arms["K1"]["slot_warmup"] == 60
    # C1 curriculum only; R1 alignment only; CR1 both
    assert arms["C1"]["curriculum"] and not arms["C1"]["alignment"]
    assert arms["R1"]["alignment"] and not arms["R1"]["curriculum"]
    assert arms["CR1"]["curriculum"] and arms["CR1"]["alignment"]
    # B0 is pure baseline
    assert not any(arms["B0"][k] for k in ("orthogonal_keys", "curriculum", "alignment"))


def test_curriculum_boundaries_and_final_500_original():
    cur = _json("EXPERIMENT_MATRIX.json")["curriculum_C1"]
    assert "1-300" in cur["phase_1_steps"]
    assert "301-700" in cur["phase_2_steps"]
    assert "701-1200" in cur["phase_3_steps"]
    assert cur["final_500_steps_original"] is True


def test_alignment_lambda_zero_after_600_and_formula():
    al = _json("EXPERIMENT_MATRIX.json")["alignment_R1"]
    assert al["lambda_schedule"]["steps_1_300"] == 0.10
    assert al["lambda_schedule"]["steps_601_1200"] == 0.0
    assert "sum_m write_weight[m] * read_weight[m]" in al["objective"]
    assert "-log(mean_overlap" in al["objective"]
    for g in al["guarantees"]:
        pass
    assert any("no N x N" in g for g in al["guarantees"])
    assert any("adds no inference-time" in g for g in al["guarantees"])


# ----------------------------------------------------------------- boundaries (no Phase/KDA/MLA/pkg)
def test_no_forbidden_imports_in_new_sources():
    r = subprocess.run([sys.executable, str(EXP / "complexity_report.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = json.loads((LAB / "artifacts" / "slot_formation_stabilization" / "complexity_report.json").read_text())
    assert rep["ok"] and rep["findings"] == []
    assert rep["no_phase"] and rep["no_kda"] and rep["no_mla"]
    assert rep["no_nxn_sequence_attention"]["global_nxn_softmax_present"] is False
    assert rep["alignment_materializes_pairwise_token_matrix"] is False


def test_no_packaging_files_added():
    for bad in ("pyproject.toml", "setup.py", "setup.cfg"):
        assert not (EXP / bad).exists(), f"packaging file {bad} must not be added"


# ----------------------------------------------------------------- classifier: Stage A eligibility
def _rec(seed, s96, ap96=0.0, ppl=118.0, params=2000104, ab=None, d16=0.9, d220=0.1, ap_d16=0.9, ap_d220=0.05, ap_ppl=140.0, ap_params=2000104):
    S = {"seed": seed, "params": params, "needle_by_dist": {"16": d16, "96": s96, "220": d220},
         "ppl": {"256": ppl, "512": ppl}}
    if ab is not None:
        S["ablation"] = ab
    Ap = {"seed": seed, "params": ap_params, "needle_by_dist": {"16": ap_d16, "96": ap96, "220": ap_d220},
          "ppl": {"256": ap_ppl}}
    return S, Ap


def _good_ablation(base):
    return {"baseline": base, "slots_off": 0.0, "randomized_address": 0.0,
            "shuffle_values": 0.0, "write_gate_zero": 0.0}


# a collapsing ablation dict where post-ablation == base (does not collapse)
def _dead_ablation(base):
    return {"baseline": base, "slots_off": base, "randomized_address": base}


def test_stage_a_eligibility_rescue_and_causal():
    import classify_stage_a as CA
    # arm forms all 3 seeds, rescues 3 and 7, causal collapses -> eligible
    byseed, aplus = {}, {}
    for s, s96 in [(3, 0.30), (6, 0.20), (7, 0.25)]:
        S, Ap = _rec(s, s96, ab=_good_ablation(s96))
        byseed[s] = S; aplus[str(s)] = Ap
    sc = CA.score_arm("O1", byseed, aplus)
    assert sc["n_forming"] == 3 and sc["rescued_nonformers"] == [3, 7]
    assert sc["causal_all_forming"] and sc["eligible"]


def test_stage_a_ineligible_when_no_rescue():
    import classify_stage_a as CA
    # only seed 6 forms (marginal already-former), no non-former rescued -> e2 fails
    byseed, aplus = {}, {}
    for s, s96 in [(3, 0.00), (6, 0.20), (7, 0.00)]:
        S, Ap = _rec(s, s96, ab=_good_ablation(s96) if s96 > 0 else None)
        byseed[s] = S; aplus[str(s)] = Ap
    sc = CA.score_arm("K1", byseed, aplus)
    assert sc["rescued_nonformers"] == [] and not sc["eligible"]


def test_stage_a_ineligible_when_causal_fails():
    import classify_stage_a as CA
    byseed, aplus = {}, {}
    for s, s96 in [(3, 0.30), (6, 0.20), (7, 0.25)]:
        # slots_off does NOT collapse -> causal fails
        ab = {"baseline": s96, "slots_off": s96, "randomized_address": s96}
        S, Ap = _rec(s, s96, ab=ab)
        byseed[s] = S; aplus[str(s)] = Ap
    sc = CA.score_arm("R1", byseed, aplus)
    assert not sc["causal_all_forming"] and not sc["eligible"]


# ----------------------------------------------------------------- selection rule + tie-break
def test_selection_ranks_by_forms_then_rescues_then_margin(tmp_path=None):
    import select_candidate as SC
    per_arm = {
        "O1": {"arm": "O1", "eligible": True, "n_forming": 3, "rescued_nonformers": [3, 7],
               "min_margin": 0.10, "median_margin": 0.15, "ppl_mean_S256": 118.0, "eligibility": {}},
        "K1": {"arm": "K1", "eligible": True, "n_forming": 2, "rescued_nonformers": [3],
               "min_margin": 0.05, "median_margin": 0.08, "ppl_mean_S256": 117.0, "eligibility": {}},
    }
    ranked = sorted((per_arm[a] for a in ["O1", "K1"]), key=SC.rank_key)
    assert ranked[0]["arm"] == "O1"  # more seeds formed wins


def test_selection_tie_breaks_lexicographically():
    import select_candidate as SC
    a = {"arm": "O2", "n_forming": 3, "rescued_nonformers": [3, 7], "min_margin": 0.1,
         "median_margin": 0.1, "ppl_mean_S256": 118.0}
    b = {"arm": "C1", "n_forming": 3, "rescued_nonformers": [3, 7], "min_margin": 0.1,
         "median_margin": 0.1, "ppl_mean_S256": 118.0}
    # different simplicity ranks -> O2 (opt family, rank 0) beats C1 (rank 2)
    ranked = sorted([a, b], key=SC.rank_key)
    assert ranked[0]["arm"] == "O2"


def test_no_candidate_when_none_eligible():
    import select_candidate as SC
    import tempfile, os
    cls = {"eligible_arms": [], "per_arm": {"O1": {"eligible": False, "eligibility": {}}}}
    fd, path = tempfile.mkstemp(suffix=".json"); os.close(fd)
    pathlib.Path(path).write_text(json.dumps(cls))
    out = path + ".out"
    r = subprocess.run([sys.executable, str(EXP / "select_candidate.py"), "--classification", path, "--out", out],
                       capture_output=True, text=True)
    res = json.loads(pathlib.Path(out).read_text())
    assert res["classification"] == "NO_STABILIZATION_CANDIDATE" and res["selected"] is None
    os.unlink(path); os.unlink(out)


# ----------------------------------------------------------------- Stage B gates
def _brec(seed, s96, ap96, ab=None, ppl=118.0, ap_ppl=140.0):
    S = {"seed": seed, "params": 2000104, "needle_by_dist": {"16": 0.9, "96": s96, "220": 0.1},
         "ppl": {"256": ppl, "512": ppl}}
    if ab is not None:
        S["ablation"] = ab
    Ap = {"seed": seed, "params": 2000104, "needle_by_dist": {"16": 0.9, "96": ap96, "220": 0.05},
          "ppl": {"256": ap_ppl}}
    return S, Ap


def test_stage_b_requires_4_of_5_even_with_high_mean():
    import classify_stage_b as CB
    # 3/5 form but with huge margins -> must NOT pass (b1 mandatory)
    cand, aplus, b0 = {}, {}, {}
    forms = {8: 0.9, 9: 0.9, 10: 0.9, 11: 0.0, 12: 0.0}
    for s in CB.FRESH_SEEDS:
        S, Ap = _brec(s, forms[s], 0.0, ab=_good_ablation(forms[s]) if forms[s] > 0 else {"baseline": 0.0, "slots_off": 0.0, "randomized_address": 0.0})
        cand[s] = S; aplus[s] = Ap
        b0[s] = _brec(s, 0.0, 0.0)[0]
    out = CB.classify(cand, aplus, b0, "O1")
    assert out["candidate_formation_count"] == 3
    assert out["gates"]["b1_form_ge4"] is False
    assert out["final_classification"] == "FRESH_HOLDOUT_UNSTABLE"
    assert out["all_gates_pass"] is False


def test_stage_b_provisional_when_all_gates_pass():
    import classify_stage_b as CB
    cand, aplus, b0 = {}, {}, {}
    for s in CB.FRESH_SEEDS:
        S, Ap = _brec(s, 0.30, 0.0, ab=_good_ablation(0.30))
        cand[s] = S; aplus[s] = Ap
        b0[s] = _brec(s, 0.0, 0.0)[0]  # B0 forms 0 -> candidate beats B0
    out = CB.classify(cand, aplus, b0, "O1")
    assert out["candidate_formation_count"] == 5
    assert out["all_gates_pass"] is True
    assert out["final_classification"] == "PROVISIONALLY_STABILIZED"
    assert out["readiness"] == "NOT_READY_FOR_KDA_VALIDATION"


def test_readiness_not_kda_ready_under_provisional():
    import classify_stage_b as CB
    cand, aplus, b0 = {}, {}, {}
    for s in CB.FRESH_SEEDS:
        S, Ap = _brec(s, 0.30, 0.0, ab=_good_ablation(0.30))
        cand[s] = S; aplus[s] = Ap; b0[s] = _brec(s, 0.0, 0.0)[0]
    out = CB.classify(cand, aplus, b0, "O1")
    assert out["readiness"] == "NOT_READY_FOR_KDA_VALIDATION"
