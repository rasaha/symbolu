"""The reference workflow is deterministic and offline."""

from __future__ import annotations

from ugence_procurement.product.demo import run_demo
from ugence_procurement.routes import ProcurementAPI

from ..conftest import APPROVER, REQUESTER, build_platform, make_request


def test_demo_cohort_is_deterministic():
    a = run_demo().summary()
    b = run_demo().summary()
    assert a == b, "demo cohort outcomes must be deterministic across runs"


def test_happy_path_serialized_outcome_is_stable():
    """A frozen expectation over the stable (non-volatile) outcome fields."""
    summary = {r["scenario"]: r for r in run_demo().summary()}
    happy = summary["happy_path"]
    assert happy["outcome"] == "RECONCILED"
    assert happy["authorization_outcome"] == "AUTHORIZED"
    assert happy["reconciliation_status"] == "RECONCILED"
    assert happy["compensation_required"] is False
    assert happy["dispatched"] is True
    denied = summary["fail_closed_restricted_supplier"]
    assert denied["authorization_outcome"] == "DENIED"
    assert denied["dispatched"] is False


def test_two_independent_runs_reconcile_identically():
    r1 = ProcurementAPI(build_platform()).run(
        request=make_request(), requester=REQUESTER, approver=APPROVER)
    r2 = ProcurementAPI(build_platform()).run(
        request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert r1.authorization_outcome == r2.authorization_outcome == "AUTHORIZED"
    assert r1.reconciliation_status == r2.reconciliation_status == "RECONCILED"
    assert r1.compensation_required == r2.compensation_required is False
