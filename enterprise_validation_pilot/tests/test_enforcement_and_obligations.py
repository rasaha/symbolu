"""Constraint enforcement (Task 107) and obligation verification (Task 108)."""
from __future__ import annotations

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.runners.constraint_enforcement import enforce
from enterprise_validation_pilot.runners.obligations import (
    compliance_verdict, verify_obligations)
from enterprise_validation_pilot.runners.workflow import run_scenario


def test_enforce_allows_inside_envelope():
    r = enforce(("maximum_amount=100000",), {"amount": "50000"})
    assert r.allowed and not r.violations


def test_enforce_blocks_outside_envelope():
    r = enforce(("maximum_amount=100000",), {"amount": "200000"})
    assert r.blocked and r.violations


def test_enforce_requires_human_approval():
    assert enforce(("required_approval=senior",), {}, approval_granted=False).blocked
    assert enforce(("required_approval=senior",), {}, approval_granted=True).allowed


def test_enforce_region_and_single_use():
    assert enforce(("allowed_region=domestic",), {"region": "foreign"}).blocked
    assert enforce(("single_use=true",), {}, authorization_used=True).blocked


def test_out_of_envelope_action_is_blocked_before_dispatch():
    # procurement-017: amount exceeds maximum_amount → blocked, never dispatched
    r = run_scenario(build().by_id("procurement-017"))
    assert r.actiongate_outcome == "AUTHORIZED_WITH_CONSTRAINTS"
    assert r.enforcement_allowed is False
    assert not r.dispatched
    assert r.execution_behavior == "DISPATCH_BLOCKED_BY_CONSTRAINT"


def test_obligation_states_are_explicit():
    recs = verify_obligations(("human_review", "logging=audit"), human_approval=False)
    states = {o.obligation_type: o.state for o in recs}
    assert states["human_review"] == "FAILED"
    assert states["logging"] == "SATISFIED"


def test_execution_success_distinct_from_compliance():
    # procurement-025: executes successfully but human-approval obligation fails
    r = run_scenario(build().by_id("procurement-025"))
    assert r.dispatched
    assert r.reconciliation == "RECONCILED"
    assert r.compliance_verdict == "NONCOMPLIANT"


def test_compliance_verdict_not_applicable_when_not_dispatched():
    recs = verify_obligations(("logging=audit",), human_approval=None)
    assert compliance_verdict(recs, reconciliation_ok=False, dispatched=False) == "NOT_APPLICABLE"
