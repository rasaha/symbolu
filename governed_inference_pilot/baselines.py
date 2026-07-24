"""Baselines A-Q (Phase 15). Each maps a case to a final shadow disposition, via the orchestrator with
a specific stage set (or a degenerate policy). Not tuned on the evaluation. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import orchestrator

_ALL = set(orchestrator.CONFIGS["FULL_STACK_HIGH_RISK"])


def _run(case, stages, config="FULL_STACK_HIGH_RISK"):
    disabled = _ALL - set(stages)
    return orchestrator.run_case(case, "FULL_STACK_HIGH_RISK", disabled=disabled).final_shadow_disposition


def a_no_governance(c): return "WOULD_ALLOW"
def b_allowlist(c):
    return "WOULD_ALLOW" if any(m.get("eligible", True) for m in c["registry"]) else "EXECUTION_UNAVAILABLE"
def c_exec_only(c): return _run(c, ["execution_gate"])
def d_exec_model(c): return _run(c, ["execution_gate", "model_policy"])
def e_assertion_only(c): return _run(c, ["execution_gate", "model_policy", "assertion_gate"])
def f_action_only(c): return _run(c, ["execution_gate", "model_policy", "action_gate"])
def g_ci_assertion(c): return _run(c, ["execution_gate", "model_policy", "claim_integrity", "assertion_gate"])
def h_ea_assertion(c): return _run(c, ["execution_gate", "model_policy", "evidence_assurance", "assertion_gate"])
def i_full_no_scope(c): return _run(c, list(_ALL - {"scope_integrity"}))
def j_full(c): return _run(c, list(_ALL))
def k_full_no_ea(c): return _run(c, list(_ALL - {"evidence_assurance"}))
def l_full_no_ci(c): return _run(c, list(_ALL - {"claim_integrity"}))
def m_full_forced(c):
    # ambiguous states forced to a decision: map INDETERMINATE-ish to WOULD_QUALIFY (a risk posture)
    f = _run(c, list(_ALL))
    return "WOULD_QUALIFY" if f in ("INDETERMINATE", "EVIDENCE_UNAVAILABLE") else f
def n_full_abstain(c):
    # abstention posture: any non-clean uncertainty -> INDETERMINATE
    f = _run(c, list(_ALL))
    return "INDETERMINATE" if f in ("EVIDENCE_UNAVAILABLE",) else f
def o_mvc(c): return orchestrator.run_case(c, "MINIMUM_VIABLE_CONTROL_PLANE").final_shadow_disposition
def p_oracle(c): return c["expected_final"]
def q_human_upper(c):
    # human-review upper bound: escalate anything the full stack didn't cleanly allow
    f = _run(c, list(_ALL))
    return "WOULD_ESCALATE" if f not in ("WOULD_ALLOW",) else f


BASELINES = {
    "A_no_governance": a_no_governance, "B_allowlist": b_allowlist, "C_exec_only": c_exec_only,
    "D_exec_model": d_exec_model, "E_assertion_only": e_assertion_only, "F_action_only": f_action_only,
    "G_ci_assertion": g_ci_assertion, "H_ea_assertion": h_ea_assertion, "I_full_no_scope": i_full_no_scope,
    "J_full": j_full, "K_full_no_ea": k_full_no_ea, "L_full_no_ci": l_full_no_ci,
    "M_full_forced": m_full_forced, "N_full_abstain": n_full_abstain, "O_mvc": o_mvc,
    "P_oracle": p_oracle, "Q_human_upper": q_human_upper,
}
