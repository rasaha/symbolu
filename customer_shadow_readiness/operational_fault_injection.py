"""Operational fault injection (M11). Injects operational faults into the shadow pilot and verifies the
runtime fails closed, isolates tenants, and never enforces. Distinct from the pilot's component-fault
injection - these are OPERATIONAL faults (auth, tenant, intake, kill, drift). Deterministic.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from governed_inference_pilot import dataset
from . import pilot_api, security, killswitch, intake, data_controls as dc

OP_FAULTS = ["no_token", "tampered_token", "wrong_tenant_token", "missing_scope_token",
             "cross_tenant_case", "oversize_artifact", "restricted_under_internal_clearance",
             "pilot_kill_tripped", "tenant_kill_tripped", "empty_artifact"]


def _case(tenant="acme"):
    c = asdict(dataset.all_cases()[0]); c["request"]["tenant_id"] = tenant
    return c


def run_fault(fault: str) -> Dict[str, Any]:
    killswitch.restore_pilot()
    for t in ("acme", "globex"):
        killswitch.restore_tenant(t)
    good = security.issue_token("tok-acme-analyst")
    case = _case("acme")

    if fault == "no_token":
        r = pilot_api.submit(None, "acme", case)
    elif fault == "tampered_token":
        r = pilot_api.submit("tok-acme-analyst.deadbeef", "acme", case)
    elif fault == "wrong_tenant_token":
        r = pilot_api.submit(security.issue_token("tok-globex-analyst"), "acme", case)
    elif fault == "missing_scope_token":
        r = pilot_api.submit(security.issue_token("tok-acme-reviewer"), "acme", case)  # reviewer lacks submit
    elif fault == "cross_tenant_case":
        c = _case("globex"); r = pilot_api.submit(good, "acme", c)                     # case tenant != caller
    elif fault == "oversize_artifact":
        c = _case("acme"); c["model_output"] = "x" * (intake.MAX_TEXT_CHARS + 1)
        r = pilot_api.submit(good, "acme", c)
    elif fault == "restricted_under_internal_clearance":
        c = _case("acme"); c["model_output"] = "patient SSN 123-45-6789"
        c["request"]["data_sensitivity"] = "internal"
        r = pilot_api.submit(good, "acme", c)
    elif fault == "pilot_kill_tripped":
        killswitch.trip_pilot(); r = pilot_api.submit(good, "acme", case); killswitch.restore_pilot()
    elif fault == "tenant_kill_tripped":
        killswitch.trip_tenant("acme"); r = pilot_api.submit(good, "acme", case); killswitch.restore_tenant("acme")
    elif fault == "empty_artifact":
        c = _case("acme"); c["model_output"] = "   "
        r = pilot_api.submit(good, "acme", c)
    else:
        r = pilot_api.submit(good, "acme", case)

    return {"fault": fault, "accepted": r.accepted, "enforced": r.enforced,
            "final": r.final_shadow_disposition, "reason_codes": r.reason_codes,
            "fail_closed": not r.accepted or r.final_shadow_disposition != "WOULD_ALLOW"}


def sweep() -> Dict[str, Any]:
    rows = [run_fault(f) for f in OP_FAULTS]
    return {"n_faults": len(rows),
            "all_fail_closed": all(x["fail_closed"] for x in rows),
            "any_enforced": any(x["enforced"] for x in rows),
            "results": rows}
