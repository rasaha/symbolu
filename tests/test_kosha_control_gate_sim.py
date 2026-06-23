"""CPU tests for the Kosha control-plane gate SIMULATION harness.
Pre-reg: docs/KOSHA_CONTROL_PLANE_GATE_PREREG.md. No runtime, no prompt change, no GPU, no model, no
generation, no signal claim. Deterministic query-derived p_k only."""
import math
import sys
from pathlib import Path

import pytest

_SCR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

from conscious_generation import simulate_kosha_control_gate as S          # noqa: E402

ONE_HOT = [1.0, 0.0, 0.0, 0.0, 0.0]
UNIFORM = [0.2, 0.2, 0.2, 0.2, 0.2]
PEAKED = [0.97, 0.0075, 0.0075, 0.0075, 0.0075]


# 1. p_k normalization ----------------------------------------------------------------------------
def test_pk_normalization():
    assert abs(sum(S._normalize_pk([2, 2, 2, 2, 2])) - 1.0) < 1e-9
    assert S._normalize_pk([0, 0, 0, 0, 0]) == [0.2] * 5          # degenerate -> uniform
    with pytest.raises(ValueError):
        S._normalize_pk([1, 2, 3])                                # wrong length
    with pytest.raises(ValueError):
        S._normalize_pk([-1, 1, 1, 1, 1])                         # negative


# 2 & 3. entropy bounds ---------------------------------------------------------------------------
def test_entropy_zero_for_one_hot():
    assert S.kosha_entropy(ONE_HOT) == pytest.approx(0.0, abs=1e-12)
    assert S.normalized_entropy(ONE_HOT) == pytest.approx(0.0, abs=1e-12)


def test_entropy_one_normalized_for_uniform():
    assert S.kosha_entropy(UNIFORM) == pytest.approx(math.log(5), abs=1e-9)
    assert S.normalized_entropy(UNIFORM) == pytest.approx(1.0, abs=1e-9)


# 4 & 5. readiness --------------------------------------------------------------------------------
def test_readiness_high_for_peaked_target():
    r = S.kosha_readiness(PEAKED, 0)
    assert r > 0.7                                                # peaked on target -> high readiness


def test_readiness_low_for_uniform():
    assert S.kosha_readiness(UNIFORM, 0) == pytest.approx(0.0, abs=1e-9)   # H_norm=1 -> R_K=0


# 6. emit score monotonic with lower entropy ------------------------------------------------------
def test_emit_score_monotonic_with_lower_entropy():
    e_peaked, _ = S.kosha_emit_score(PEAKED, 0)
    e_mid, _ = S.kosha_emit_score([0.5, 0.2, 0.1, 0.1, 0.1], 0)
    e_uniform, _ = S.kosha_emit_score(UNIFORM, 0)
    assert e_peaked > e_mid > e_uniform                          # lower entropy -> higher emit score


# 7. gate decisions deterministic -----------------------------------------------------------------
def test_gate_decisions_deterministic():
    e, prov = S.kosha_emit_score(PEAKED, 0)
    d1 = S.decide_control(e, prov["R_K"], prov["H_K_norm"])
    d2 = S.decide_control(e, prov["R_K"], prov["H_K_norm"])
    assert d1 == d2
    assert d1[0] == "EMIT" and d1[1] == "DEPTH_CAP_HIGH"         # peaked -> emit + high depth cap
    e2, p2 = S.kosha_emit_score(UNIFORM, 0)
    assert S.decide_control(e2, p2["R_K"], p2["H_K_norm"])[0] in S.EMIT_DECISIONS


# 8. fixed parameters load & report ---------------------------------------------------------------
def test_fixed_parameters_loaded_and_reported():
    p = S.DEFAULTS
    assert (p.tau_K, p.kappa, p.c, p.d, p.tau_emit, p.tau_hedge) == (0.55, 8.0, 1.0, 1.0, 0.55, 0.45)
    assert p.a == 0.0 and p.b == 0.0                             # H_D/H_G terms drop out by design
    traces = [{"query": "Compare A and B, which is better?", "primary_domain": None,
               "expected_passed": True, "expected_findings": ["frame_compliant"]}]
    rep = S.run([S.normalize_row(t) for t in traces])
    assert rep["params"]["tau_K"] == 0.55 and rep["params_are_default"] is True


# 9. random baseline seeded/reproducible ----------------------------------------------------------
def test_random_baseline_seeded_reproducible():
    decs = ["EMIT", "HEDGE", "DEFER", "EMIT", "HEDGE", "DEFER", "EMIT", "EMIT"]
    a = S.random_gate_decisions(decs, seed=7)
    b = S.random_gate_decisions(decs, seed=7)
    c = S.random_gate_decisions(decs, seed=8)
    assert a == b                                                # reproducible
    assert sorted(a) == sorted(decs)                            # same marginal distribution (permutation)
    assert a != c or len(set(decs)) == 1                        # different seed -> (generally) different


# 10. hidden-state p_k path blocked ---------------------------------------------------------------
def test_hidden_pk_blocked():
    rep = S.blocked_hidden_pk_report()
    assert rep["decision"] == "KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED"
    assert rep["blocker"] and any("surface" in b for b in rep["blocker"])
    rc = S.main(["--pk-source", "hidden", "--out", "/tmp/_k_blk.json", "--report", "/tmp/_k_blk.md"])
    assert rc == 0
    import json
    assert json.loads(Path("/tmp/_k_blk.json").read_text())["decision"] == "KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED"


# 11. no runtime / prompt path imported or modified ----------------------------------------------
def test_no_runtime_or_prompt_path():
    src = (Path(S.__file__)).read_text()
    for forbidden in ("build_framed_prompt", "depth_block", "AutoModelForCausalLM", ".generate(",
                      "import torch", "load_in_4bit"):
        assert forbidden not in src, f"sim must not reference runtime/prompt/generation: {forbidden}"
    # the only kosha import is the deterministic scoring selector
    assert "from csr_match_filter.kosha import select_kosha_depth" in src


# 12. outcomes unavailable -> correct label -------------------------------------------------------
def test_outcomes_unavailable_label():
    traces = [S.normalize_row({"query": "What is a doctor? Explain simply.", "primary_domain": "medicine",
                               "slice": "annamaya"}),
              S.normalize_row({"query": "How do I prepare step by step?", "primary_domain": "medicine",
                               "slice": "pranamaya"})]
    assert all(t["outcomes"] is None for t in traces)
    rep = S.run(traces)
    assert rep["decision"] == "KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE"
    assert rep["gate"]["outcomes_available"] is False
    assert rep["gate"]["total"] == 2 and "decision_distribution" in rep["gate"]


# bonus: end-to-end on the real audit trace set is outcome-labelled and deterministic --------------
def test_end_to_end_on_audit_traces_is_outcome_labelled():
    audit = (_SCR / "cg_wrapper_ablation" / "csr_match_filter" / "eval_data" / "answer_audit_eval.jsonl")
    if not audit.exists():
        pytest.skip("audit trace set not present")
    traces = S.load_traces(audit)
    rep = S.run(traces)
    assert rep["gate"]["outcomes_available"] is True
    assert "separation" in rep["gate"]
    assert rep["decision"] in ("KOSHA_CONTROL_SIM_NO_SIGNAL", "KOSHA_CONTROL_SIM_BEATS_BASELINES",
                               "KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS")
    rep2 = S.run(traces)
    assert rep["decision"] == rep2["decision"]                  # deterministic
