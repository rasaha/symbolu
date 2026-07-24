"""Pilot eligibility gate (M12). Aggregates the readiness conditions into a single fail-closed decision:
is the runtime eligible to enter a bounded customer shadow pilot? Deterministic. Each condition is a
concrete check, not an assertion.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from governed_inference_pilot import dataset
from . import (security, data_controls as dc, deployment, killswitch, differential_action,
               operational_fault_injection as ofi)


def _actiongate_ok() -> bool:
    d = differential_action.compare()
    return d["unsafe_disagreement"] == 0 and d["real_gate_deterministic"]


def _security_ok() -> bool:
    tok = security.issue_token("tok-acme-analyst")
    return (security.check_access(tok, "shadow:submit", "acme").allowed and
            not security.check_access(tok, "shadow:read", "globex").allowed and
            not security.check_access(None, "shadow:read", "acme").allowed)


def _data_ok() -> bool:
    return (not dc.permitted_use("restricted", "internal") and
            "[SSN]" in dc.redact("123-45-6789"))


def _kill_ok() -> bool:
    killswitch.restore_pilot()
    killswitch.trip_pilot(); tripped = not killswitch.check("acme").active
    killswitch.restore_pilot()
    return tripped


def _fault_ok() -> bool:
    s = ofi.sweep()
    return s["all_fail_closed"] and not s["any_enforced"]


def _deploy_ok() -> bool:
    return deployment.preflight()["deployable"] and deployment.rollback_check()["rollback_safe"]


CONDITIONS = {
    "gap0_actiongate_no_unsafe_disagreement": _actiongate_ok,
    "security_and_tenant_isolation": _security_ok,
    "data_handling_controls": _data_ok,
    "kill_switches": _kill_ok,
    "operational_faults_fail_closed": _fault_ok,
    "deployment_and_rollback": _deploy_ok,
}


def evaluate() -> Dict[str, Any]:
    results = {name: bool(fn()) for name, fn in CONDITIONS.items()}
    eligible = all(results.values())
    failed = [k for k, v in results.items() if not v]
    return {"eligible_for_bounded_shadow_pilot": eligible, "conditions": results,
            "failed_conditions": failed,
            "gate_rule": "fail-closed: ALL conditions must hold"}


def main():
    r = evaluate()
    print("PILOT ELIGIBILITY GATE")
    for k, v in r["conditions"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"\n  ELIGIBLE FOR BOUNDED CUSTOMER SHADOW PILOT: {r['eligible_for_bounded_shadow_pilot']}")


if __name__ == "__main__":
    main()
