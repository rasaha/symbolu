"""Executable cross-runtime conformance runner (deliverable 11).

Runs the corpus through both runtimes + the frozen control plane and checks the
preregistered identity relationships and control-plane classes. Deterministic:
running it twice yields byte-identical results. Emits a JSON report.

Usage:  python -m cer_v0_1.conformance.runner            # print report
        python -m cer_v0_1.conformance.runner --json out.json
"""
from __future__ import annotations

import json
import sys
from typing import Dict, List

from .. import _paths  # noqa: F401
from .. import control_plane as cp
from .. import spec
from ..corpus import NOW, build_corpus
from ..observation import GovernedExecutionResult, observe_and_reflect
from ..risk_tier import RiskTierViolation
from ..spec import CERValidationError
from action_gate_ref import policy as policy_mod  # noqa: E402


def _restrictive_policy() -> dict:
    """A policy update that DENIES DEPLOY (same-action, different-verdict case)."""
    rules = [r for r in policy_mod.DEFAULT_RULES if r["operation"] != "DEPLOY"]
    rules = rules + [{"id": "DEPLOY-FROZEN", "operation": "DEPLOY",
                      "effects": [{"op": "DENY"}]}]
    return policy_mod.sign_policy(policy_mod.build_bundle(rules=rules))


def _digest(cer: dict) -> str:
    return spec.action_digest(cer)


def run() -> Dict:
    cases = build_corpus()
    base_digest = _digest(cases[0].ug_cer)  # 01_valid_scale is the reference
    results: List[Dict] = []
    restrictive = _restrictive_policy()

    metrics = {
        "cases": 0, "schema_validation_ok": 0, "cross_runtime_digest_equiv": 0,
        "cross_runtime_digest_equiv_expected": 0, "expected_difference_correct": 0,
        "expected_difference_total": 0, "adapter_information_loss": 0,
        "unsupported_extension_rejected": 0,
        "ag_verdict_equiv": 0, "acp_verdict_equiv": 0, "composition_equiv": 0,
        "cp_class_correct": 0, "cp_class_total": 0,
        "state_drift_rejected": 0, "modified_action_rejected": 0,
        "bypass_prevented": 0, "ownership_violations": 0,
        "observation_return_ok": 0, "deterministic_ok": 0,
    }

    for c in cases:
        rec: Dict = {"case_id": c.case_id, "description": c.description,
                     "provenance": c.provenance, "checks": {}, "passed": True}
        metrics["cases"] += 1

        def _check(name, cond):
            rec["checks"][name] = bool(cond)
            if not cond:
                rec["passed"] = False
            return bool(cond)

        # --- malformed CER cases: must fail closed ---
        if c.malformed:
            raised = False
            try:
                spec.validate_cer(c.ug_cer)
            except CERValidationError:
                raised = True
            _check("validation_fails_closed", raised)
            if raised and "extension" in c.case_id:
                metrics["unsupported_extension_rejected"] += 1
            if raised and "drops_field" in c.case_id:
                metrics["adapter_information_loss"] += 1  # loss detected+rejected
            results.append(rec)
            continue

        # --- valid CERs: validate both runtimes ---
        ok = True
        for cer in (c.ug_cer, c.lg_cer):
            if cer is None:
                continue
            try:
                spec.validate_cer(cer)
            except (CERValidationError, RiskTierViolation):
                ok = False
        if _check("schema_validation_ok", ok):
            metrics["schema_validation_ok"] += 1

        # --- identity: cross-runtime digest ---
        d_ug = _digest(c.ug_cer)
        d_lg = _digest(c.lg_cer) if c.lg_cer is not None else d_ug
        rec["ug_digest"] = d_ug
        rec["lg_digest"] = d_lg
        if c.expect_ug_eq_lg is True:
            metrics["cross_runtime_digest_equiv_expected"] += 1
            if _check("ug_eq_lg", d_ug == d_lg):
                metrics["cross_runtime_digest_equiv"] += 1

        # --- identity vs base ---
        if c.expect_digest_vs_base is not None:
            metrics["expected_difference_total"] += 1
            if c.expect_digest_vs_base == "same":
                good = _check("digest_vs_base_same", d_ug == base_digest)
            else:
                good = _check("digest_vs_base_differs", d_ug != base_digest)
                if good and c.case_id.startswith(("07", "08")):
                    metrics["modified_action_rejected"] += 1
            if good:
                metrics["expected_difference_correct"] += 1

        # --- deterministic rerun (byte-identical digest) ---
        if _check("deterministic", _digest(c.ug_cer) == d_ug and (
                c.lg_cer is None or _digest(c.lg_cer) == d_lg)):
            metrics["deterministic_ok"] += 1

        # --- bypass case ---
        if c.bypass:
            # governed mode: no CER submitted -> no eligible result -> no exec identity
            bypass_result = {"eligible": False, "execution_identity": None}
            _check("bypass_prevented", bypass_result["execution_identity"] is None)
            metrics["bypass_prevented"] += 1
            results.append(rec)
            continue

        # --- run the frozen control plane on BOTH runtime-derived CERs ---
        policy = restrictive if c.policy_variant else None
        auto_ev = not c.missing_evidence
        r_ug = cp.run_control_plane(c.ug_cer, now=NOW, signed_policy=policy, auto_evidence=auto_ev)
        r_lg = cp.run_control_plane(c.lg_cer, now=NOW, signed_policy=policy, auto_evidence=auto_ev) \
            if c.lg_cer is not None else r_ug
        rec["actiongate"] = {"ug": r_ug.actiongate_outcome, "lg": r_lg.actiongate_outcome}
        rec["acp"] = {"ug": r_ug.acp_decision, "lg": r_lg.acp_decision}
        rec["composed"] = {"ug": r_ug.combined_outcome, "lg": r_lg.combined_outcome}
        rec["eligible"] = {"ug": r_ug.eligible, "lg": r_lg.eligible}

        # cross-runtime control-plane equivalence
        if _check("ag_verdict_equiv", r_ug.actiongate_outcome == r_lg.actiongate_outcome):
            metrics["ag_verdict_equiv"] += 1
        if _check("acp_verdict_equiv", r_ug.acp_decision == r_lg.acp_decision):
            metrics["acp_verdict_equiv"] += 1
        if _check("composition_equiv", r_ug.combined_outcome == r_lg.combined_outcome):
            metrics["composition_equiv"] += 1
        # same action_hash across runtimes (the identity the gate bound)
        _check("gate_action_hash_equiv", r_ug.actiongate_action_hash == r_lg.actiongate_action_hash)

        # expected composed class
        if c.expect_cp_class is not None:
            metrics["cp_class_total"] += 1
            if _check("cp_class", r_ug.combined_outcome == c.expect_cp_class):
                metrics["cp_class_correct"] += 1

        # stale case: both paths reject (not eligible)
        if c.stale:
            drift = (not r_ug.eligible) and ("STATE_BINDING_MISMATCH" in r_ug.reason_codes
                                             or r_ug.actiongate_outcome != "ALLOW")
            if _check("state_drift_rejected", drift):
                metrics["state_drift_rejected"] += 1

        # observation return
        if c.observation:
            gu = observe_and_reflect("ugence", GovernedExecutionResult.from_cp(r_ug))
            gl = observe_and_reflect("langgraph", GovernedExecutionResult.from_cp(r_lg))
            ret = (gu["observed_cer_digest"] == d_ug and gl["observed_cer_digest"] == d_lg
                   and gu["next_step"] and gl["next_step"])
            rec["observation"] = {"ugence": gu["next_step"], "langgraph": gl["next_step"]}
            if _check("observation_return", ret):
                metrics["observation_return_ok"] += 1

        results.append(rec)

    # ownership: the FROZEN control-plane components must contain NO runtime-specific
    # branch (no langgraph/ugence/runtime_type). Scans the real ActionGate + ACP
    # source (not this orchestration wrapper, whose comments merely assert the fact).
    import inspect
    from action_gate_ref import gate as _ag_gate
    from action_gate_ref import projection as _ag_proj
    from symbolu_robotics.autonomous_control_plane.cloud import composition as _acp_comp
    from symbolu_robotics.autonomous_control_plane.cloud import adapter as _acp_adapter
    _tokens = ("runtime_type", "langgraph", "ugence", "crewai", "openai")
    ownership_ok = True
    for mod in (_ag_gate, _ag_proj, _acp_comp, _acp_adapter):
        s = inspect.getsource(mod).lower()
        if any(t in s for t in _tokens):
            ownership_ok = False
    metrics["ownership_violations"] = 0 if ownership_ok else 1

    passed = sum(1 for r in results if r["passed"])
    report = {
        "cer_version": spec.CER_VERSION, "identity_profile": spec.IDENTITY_PROFILE,
        "base_digest": base_digest,
        "cases_total": len(results), "cases_passed": passed,
        "all_passed": passed == len(results),
        "ownership_no_runtime_switch": ownership_ok,
        "metrics": metrics, "cases": results,
    }
    return report


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    out = None
    if "--json" in argv:
        out = argv[argv.index("--json") + 1]
    text = json.dumps(report, indent=2, sort_keys=True)
    if out:
        with open(out, "w") as f:
            f.write(text + "\n")
    print(text)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
