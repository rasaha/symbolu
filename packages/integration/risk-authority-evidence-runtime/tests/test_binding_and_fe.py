"""RA authoritative binding re-check (§8) + F-E duplicate preservation (Phase 14).

These exercise the RA leaf's ``domain.binding`` re-check directly — the
defense-in-depth layer RA applies before its non-compensatory gate — and prove
that duplicate results for a mandatory control still fail closed (F-E), including
conflicts across assurance engines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_authority.domain.binding import (
    AdmittedContext,
    CaseBindingContext,
    binding_violations,
    usable_control_results,
)
from risk_authority.domain.controls import (
    ControlResult,
    required_controls_satisfied,
    unsatisfied_controls,
)
from risk_authority.domain.enums import ControlStatus

NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(hours=1)

CTX = CaseBindingContext(
    tenant_id="tenant_123",
    case_id="rdc_1",
    workflow_ir_digest="sha256:wf",
    policy_digest="sha256:pol",
    required_controls=frozenset({"C1", "C2"}),
)
ADMITTED = AdmittedContext(valid_until_by_id={"ev1": LATER, "ev2": LATER})


def _bound(**overrides) -> ControlResult:
    base = dict(
        control_id="C1",
        status=ControlStatus.PASS,
        evidence_ids=("ev1",),
        evaluated_at=NOW,
        valid_until=LATER,
        tenant_id="tenant_123",
        risk_case_id="rdc_1",
        workflow_ir_digest="sha256:wf",
        policy_digest="sha256:pol",
        assurance_engine="tap-control-assurance",
        assurance_version="1",
    )
    base.update(overrides)
    return ControlResult(**base)


def test_fully_bound_result_is_usable():
    assert binding_violations(_bound(), CTX, ADMITTED, NOW) == ()


def test_cross_tenant_result_fails_closed():
    assert binding_violations(_bound(tenant_id="tenant_999"), CTX, ADMITTED, NOW)


def test_cross_case_result_fails_closed():
    assert binding_violations(_bound(risk_case_id="rdc_2"), CTX, ADMITTED, NOW)


def test_wrong_workflow_result_fails_closed():
    assert binding_violations(_bound(workflow_ir_digest="sha256:other"), CTX, ADMITTED, NOW)


def test_wrong_policy_result_fails_closed():
    assert binding_violations(_bound(policy_digest="sha256:other"), CTX, ADMITTED, NOW)


def test_control_not_required_fails_closed():
    assert binding_violations(_bound(control_id="C9"), CTX, ADMITTED, NOW)


def test_evidence_not_admitted_fails_closed():
    assert binding_violations(_bound(evidence_ids=("ev_ghost",)), CTX, ADMITTED, NOW)


def test_stale_backing_evidence_fails_closed():
    stale_admitted = AdmittedContext(valid_until_by_id={"ev1": NOW - timedelta(hours=1)})
    assert binding_violations(_bound(), CTX, stale_admitted, NOW)


def test_result_without_production_bindings_fails_closed():
    # A reference/synthetic result (no bindings) is never usable in production.
    ref = ControlResult(control_id="C1", status=ControlStatus.PASS, evidence_ids=("ev1",))
    assert binding_violations(ref, CTX, ADMITTED, NOW)


def test_usable_filter_drops_out_of_context_results():
    good = _bound()
    bad = _bound(tenant_id="tenant_999")
    kept = usable_control_results((good, bad), CTX, ADMITTED, NOW)
    assert kept == (good,)


# --- F-E: duplicates fail closed both orderings ---------------------------
def test_duplicate_fail_then_pass_denies():
    passing = _bound(control_id="C1", status=ControlStatus.PASS)
    failing = _bound(control_id="C1", status=ControlStatus.FAIL)
    c2 = _bound(control_id="C2", status=ControlStatus.PASS, evidence_ids=("ev2",))
    kept = usable_control_results((failing, passing, c2), CTX, ADMITTED, NOW)
    assert not required_controls_satisfied(("C1", "C2"), kept, NOW)
    assert ("C1", ControlStatus.FAIL) in unsatisfied_controls(("C1", "C2"), kept, NOW)


def test_duplicate_pass_then_fail_denies():
    passing = _bound(control_id="C1", status=ControlStatus.PASS)
    failing = _bound(control_id="C1", status=ControlStatus.FAIL)
    c2 = _bound(control_id="C2", status=ControlStatus.PASS, evidence_ids=("ev2",))
    kept = usable_control_results((passing, failing, c2), CTX, ADMITTED, NOW)
    assert not required_controls_satisfied(("C1", "C2"), kept, NOW)


def test_conflicting_results_from_different_engines_deny():
    # A FAIL from one assurance engine cannot be masked by a PASS from another.
    eng_a_fail = _bound(control_id="C1", status=ControlStatus.FAIL, assurance_engine="engine-a")
    eng_b_pass = _bound(control_id="C1", status=ControlStatus.PASS, assurance_engine="engine-b")
    c2 = _bound(control_id="C2", status=ControlStatus.PASS, evidence_ids=("ev2",))
    kept = usable_control_results((eng_a_fail, eng_b_pass, c2), CTX, ADMITTED, NOW)
    assert not required_controls_satisfied(("C1", "C2"), kept, NOW)
