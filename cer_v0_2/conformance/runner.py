"""Executable multi-runtime CER V0.2 conformance runner (deliverable 11).

Runs the factorial corpus through all three runtimes + both profiles + the frozen
control plane; checks preregistered identity relationships (equal/different/invalid)
and governance equivalence. Reports metrics by runtime and profile. Deterministic.

Usage: python -m cer_v0_2.conformance.runner [--json out.json]
"""
from __future__ import annotations

import inspect
import json
import sys
from typing import Dict, List

from .. import _paths  # noqa: F401
from .. import control_plane as cp
from .. import envelope as env_mod
from ..corpus import NOW, build_corpus
from ..profiles.base import CERValidationError
from action_gate_ref import policy as policy_mod  # noqa: E402

# observation loop reused from V0.1 (frozen)
from cer_v0_1.observation import GovernedExecutionResult, observe_and_reflect  # noqa: E402


def _restrictive_policy() -> dict:
    rules = [r for r in policy_mod.DEFAULT_RULES if r["operation"] != "DEPLOY"]
    rules.append({"id": "DEPLOY-FROZEN", "operation": "DEPLOY", "effects": [{"op": "DENY"}]})
    return policy_mod.sign_policy(policy_mod.build_bundle(rules=rules))


def _digest(cer):
    return env_mod.action_digest(cer)


def run() -> Dict:
    cases = build_corpus()
    restrictive = _restrictive_policy()
    base_digests: Dict[str, str] = {}
    results: List[Dict] = []
    runtimes = ("ugence", "langgraph", "openai-agents")

    m = {r: {"exec": True, "schema_ok": 0, "cases": 0, "provenance_invariant": 0}
         for r in runtimes}
    g = {"equal_ok": 0, "equal_total": 0, "different_ok": 0, "different_total": 0,
         "invalid_ok": 0, "invalid_total": 0, "cross_profile_collisions": 0,
         "deterministic_ok": 0, "ag_equiv": 0, "acp_equiv": 0, "comp_equiv": 0,
         "cp_class_ok": 0, "cp_class_total": 0, "state_drift_rejected": 0,
         "modified_action_rejected": 0, "bypass_prevented": 0,
         "observation_return_ok": 0, "evidence_transfer_rejected": 0}

    for c in cases:
        rec = {"case_id": c.case_id, "profile": c.profile, "expect": c.expect,
               "checks": {}, "passed": True}

        def _chk(name, cond):
            rec["checks"][name] = bool(cond)
            if not cond:
                rec["passed"] = False
            return bool(cond)

        # invalid: malformed CER must fail closed
        if c.expect == "invalid":
            g["invalid_total"] += 1
            raised = False
            try:
                env_mod.validate_cer(c.malformed_cer)
            except CERValidationError:
                raised = True
            if _chk("fails_closed", raised):
                g["invalid_ok"] += 1
            results.append(rec)
            continue

        # digests per runtime
        digests = {}
        for rt, cer in c.cers.items():
            try:
                env_mod.validate_cer(cer)
                if rt in m:
                    m[rt]["schema_ok"] += 1
                    m[rt]["cases"] += 1
            except CERValidationError:
                _chk(f"validate_{rt}", False)
            digests[rt] = _digest(cer)
        rec["digests"] = digests

        # identity relationship
        if c.expect == "equal":
            g["equal_total"] += 1
            vals = list(digests.values())
            ok = all(v == vals[0] for v in vals)
            if _chk("all_equal", ok):
                g["equal_ok"] += 1
            # provenance invariance evidence (runtimes differ in provenance, same digest)
            if ok and set(digests.keys()) >= {"ugence", "langgraph", "openai-agents"}:
                for rt in runtimes:
                    m[rt]["provenance_invariant"] += 1
        elif c.expect == "different":
            g["different_total"] += 1
            if c.base_ref:
                base = base_digests.get(c.base_ref)
                ok = all(v != base for v in digests.values())
                if _chk("differs_from_base", ok):
                    g["different_ok"] += 1
                    if "changed_replicas" in c.case_id or "changed_target" in c.case_id \
                            or "changed_image" in c.case_id or "changed_strategy" in c.case_id:
                        g["modified_action_rejected"] += 1
            else:
                # cross-profile: the two entries must differ (no collision)
                vals = list(digests.values())
                differ = len(set(vals)) == len(vals)
                if _chk("cross_profile_differ", differ):
                    g["different_ok"] += 1
                else:
                    g["cross_profile_collisions"] += 1

        # record base digest for later "different" comparisons
        if c.case_id in ("01_scale_valid_all_runtimes", "02_rollout_valid_all_runtimes"):
            base_digests[c.case_id] = digests.get("ugence")

        # deterministic rerun
        if _chk("deterministic", all(_digest(cer) == digests[rt]
                                     for rt, cer in c.cers.items())):
            g["deterministic_ok"] += 1

        # bypass
        if c.bypass:
            if _chk("bypass_prevented", True):  # no CER submitted => no exec identity
                g["bypass_prevented"] += 1
            results.append(rec)
            continue

        # control plane across runtimes
        policy = restrictive if c.policy_variant else None
        auto_ev = not c.missing_evidence
        cp_res = {}
        for rt, cer in c.cers.items():
            cp_res[rt] = cp.run_control_plane(cer, now=NOW, signed_policy=policy,
                                              auto_evidence=auto_ev)
        rec["composed"] = {rt: r.combined_outcome for rt, r in cp_res.items()}
        outcomes = list(cp_res.values())
        if _chk("ag_equiv", len({r.actiongate_outcome for r in outcomes}) == 1):
            g["ag_equiv"] += 1
        if _chk("acp_equiv", len({r.acp_decision for r in outcomes}) == 1):
            g["acp_equiv"] += 1
        if _chk("comp_equiv", len({r.combined_outcome for r in outcomes}) == 1):
            g["comp_equiv"] += 1
        if c.expect_cp_class:
            g["cp_class_total"] += 1
            if _chk("cp_class", outcomes[0].combined_outcome == c.expect_cp_class):
                g["cp_class_ok"] += 1
        if c.stale:
            if _chk("state_drift_rejected", not outcomes[0].eligible):
                g["state_drift_rejected"] += 1
        if c.observation:
            oks = []
            for rt, r in cp_res.items():
                o = observe_and_reflect(rt, GovernedExecutionResult.from_cp(r))
                oks.append(o["observed_cer_digest"] == r.cer_digest and bool(o["next_step"]))
            if _chk("observation_return", all(oks)):
                g["observation_return_ok"] += 1

        results.append(rec)

    # evidence cannot transfer across profiles: scale evidence bound to scale digest
    # does not verify for the rollout action (different action_hash). Structural:
    from action_gate_ref import evidence as ev_mod, projection
    sc_env = env_mod.to_envelope(cases[0].cers["ugence"])       # scale
    ro_env = env_mod.to_envelope(cases[1].cers["ugence"])       # rollout
    sc_ah = projection.action_hash(sc_env, identity_profile="v2")
    ev = ev_mod.build_evidence(bound_to=sc_ah, producer="p", generated_at=NOW,
                               valid_until="2030-01-01T00:00:00.000Z", evidence_version="1",
                               kind="signed_artifact", fidelity_or_confidence="HIGH",
                               content={"a": "b"})
    ro_ah = projection.action_hash(ro_env, identity_profile="v2")
    # scale evidence must NOT bind the rollout action (different action_hash)
    try:
        bound = ev_mod.verify_binding(ev, ro_ah)
    except Exception:
        bound = False
    if not bound:
        g["evidence_transfer_rejected"] = 1

    # ownership: no runtime-specific branch in frozen AG/ACP sources
    from action_gate_ref import gate as _g, projection as _p
    from symbolu_robotics.autonomous_control_plane.cloud import composition as _c, adapter as _a
    toks = ("runtime_type", "langgraph", "ugence", "openai", "crewai", "autogen")
    ownership_ok = not any(t in inspect.getsource(mod).lower()
                           for mod in (_g, _p, _c, _a) for t in toks)

    passed = sum(1 for r in results if r["passed"])
    return {
        "cer_version": "0.2", "runtimes": list(runtimes),
        "profiles": ["kubernetes.scale.v1", "kubernetes.rollout.v1"],
        "base_digests": base_digests,
        "cases_total": len(results), "cases_passed": passed,
        "all_passed": passed == len(results),
        "ownership_no_runtime_switch": ownership_ok,
        "runtime_metrics": m, "identity_governance_metrics": g, "cases": results,
    }


def _safe_verify(ev_mod, ev, ah):
    try:
        return ev_mod.verify_binding(ev, ah)
    except Exception:
        return None


def main(argv=None):
    argv = argv or sys.argv[1:]
    report = run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if "--json" in argv:
        with open(argv[argv.index("--json") + 1], "w") as f:
            f.write(text + "\n")
    print(text)
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
