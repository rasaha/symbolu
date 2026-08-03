"""Deterministic, offline reference demonstration of the Procurement lifecycle.

Exercises a complete representative governance lifecycle and at least one
fail-closed scenario. It uses **no network, no credentials, no external state**,
is fully deterministic, and clearly labels the supplier adapter as an *offline
reference adapter*. It never claims a real purchase order was created.

    happy path : request → validation → assessment → recommendation → human
                 approval → action request (exactly bound) → authorization →
                 explicit supplier dispatch → observed outcome → reconciliation
    fail-closed : a restricted supplier is DENIED at authorization; nothing is
                 dispatched.

Run: ``python -m ugence_procurement demo``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..configuration import ProcurementConfiguration
from ..platform import build_in_memory_platform
from ..requests.contracts import (
    BudgetReference,
    PurchaseItem,
    PurchaseRequest,
    SupplierReference,
)
from ..approvals.mappings import PurchaseApproval, PurchaseRecommendation
from ..routes import ProcurementAPI

_TENANT = "demo-tenant"
_REQUESTER = "demo-requester"
_APPROVER = "demo-approver"


def _make_request(
    request_id: str,
    *,
    supplier_id: str = "sup-approved",
    budget_id: str = "bud-ops",
    unit_cost: int = 100_000,
    quantity: int = 3,
) -> PurchaseRequest:
    return PurchaseRequest(
        request_id=request_id,
        tenant_id=_TENANT,
        requester=_REQUESTER,
        supplier=SupplierReference(supplier_id=supplier_id, name="Reference Supplier Co"),
        items=(PurchaseItem(description="reference widgets", quantity=quantity,
                            unit_cost=unit_cost),),
        budget=BudgetReference(budget_id=budget_id, available_amount=100_000_000),
        justification="deterministic reference demonstration",
    )


def _build_api(config: Optional[ProcurementConfiguration] = None) -> ProcurementAPI:
    platform = build_in_memory_platform(config)
    for actor in (_REQUESTER, _APPROVER):
        platform.identity_provider.register_human(actor)
        platform.policy_adapter.grant_all(actor, _TENANT)
    platform.publish_standard_mappings(actor=_APPROVER, tenant_id=_TENANT)
    return ProcurementAPI(platform)


@dataclass(frozen=True)
class DemoRun:
    """One scenario's observable, deterministic result."""

    scenario: str
    request_id: str
    outcome: str  # e.g. "RECONCILED", "DENIED"
    authorization_outcome: Optional[str]
    reconciliation_status: Optional[str]
    compensation_required: Optional[bool]
    dispatched: bool
    note: str

    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "request_id": self.request_id,
            "outcome": self.outcome,
            "authorization_outcome": self.authorization_outcome,
            "reconciliation_status": self.reconciliation_status,
            "compensation_required": self.compensation_required,
            "dispatched": self.dispatched,
            "note": self.note,
        }


@dataclass(frozen=True)
class DemoResult:
    product_version: str
    runs: tuple[DemoRun, ...]

    def summary(self) -> list[dict]:
        return [r.to_dict() for r in self.runs]


def _run_happy_path() -> DemoRun:
    api = _build_api()
    request = _make_request("demo-pr-approved")
    result = api.run(
        request=request,
        requester=_REQUESTER,
        approver=_APPROVER,
        recommendation=PurchaseRecommendation.APPROVE,
        approval=PurchaseApproval.APPROVED,
    )
    return DemoRun(
        scenario="happy_path",
        request_id=request.request_id,
        outcome=result.reconciliation_status,
        authorization_outcome=result.authorization_outcome,
        reconciliation_status=result.reconciliation_status,
        compensation_required=result.compensation_required,
        dispatched=True,
        note="offline reference supplier adapter; no real purchase order created",
    )


def _run_restricted_supplier_fail_closed() -> DemoRun:
    """A restricted supplier must be DENIED at authorization; nothing dispatches."""
    config = ProcurementConfiguration(restricted_suppliers=frozenset({"sup-restricted"}))
    api = _build_api(config)
    request = _make_request("demo-pr-restricted", supplier_id="sup-restricted")
    case, _assessment = api.submit_and_assess(request, actor=_REQUESTER)
    api.recommend(case_id=case.decision_case_id,
                  recommendation=PurchaseRecommendation.APPROVE, generated_by=_REQUESTER)
    decision = api.decide(case_id=case.decision_case_id,
                          approval=PurchaseApproval.APPROVED, approver=_APPROVER)
    action = api.request_action(decision=decision, request=request, actor=_APPROVER)
    auth = api.authorize(action_request_id=action.action_request_id, actor=_APPROVER)
    # Fail-closed: DENIED, and the demo deliberately does NOT dispatch.
    return DemoRun(
        scenario="fail_closed_restricted_supplier",
        request_id=request.request_id,
        outcome=auth.outcome.value,
        authorization_outcome=auth.outcome.value,
        reconciliation_status=None,
        compensation_required=None,
        dispatched=False,
        note="restricted supplier denied at authorization; nothing dispatched (fail-closed)",
    )


def run_demo() -> DemoResult:
    """Run the deterministic reference demo cohort (happy path + fail-closed)."""
    from .version import PRODUCT_VERSION

    runs = (
        _run_happy_path(),
        _run_restricted_supplier_fail_closed(),
    )
    return DemoResult(product_version=PRODUCT_VERSION, runs=runs)


__all__ = ["DemoRun", "DemoResult", "run_demo"]
