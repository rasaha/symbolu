"""Deterministic behavior capture for procurement equivalence verification.

Produces a normalized, machine-readable snapshot of representative procurement
behavior across the section-4.4 scenario matrix. All volatile identifiers (UUID
suffixes) and timestamps are masked to stable placeholders so the capture is a pure
function of *behavior* — enums, reason codes, statuses, outcomes, constraints,
exception types, and serialized structure — not of run-time randomness.

Import mode is selected by ``PROC_CAPTURE_MODE``:

* ``canonical`` — import from ``ugence_procurement.*`` (the canonical implementation);
* ``legacy``    — import from ``domains.procurement.*`` / ``applications.procurement.*``
                  (the compatibility facades);
* ``before``    — same legacy paths, intended to be run against a checkout of the
                  original pre-extraction source (identical import surface).

The three modes must yield an identical normalized capture (``before == canonical ==
legacy``). Usage:

    PROC_CAPTURE_MODE=canonical python scripts/capture_behavior.py > canonical.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import is_dataclass, asdict
from datetime import datetime
from enum import Enum

MODE = os.environ.get("PROC_CAPTURE_MODE", "canonical")

if MODE == "canonical":
    from ugence_procurement.configuration import ProcurementConfiguration
    from ugence_procurement.platform import build_in_memory_platform
    from ugence_procurement.routes import ProcurementAPI
    from ugence_procurement.requests.contracts import (
        BudgetReference, PurchaseItem, PurchaseRequest, SupplierReference)
    from ugence_procurement.approvals.mappings import PurchaseApproval, PurchaseRecommendation
    from ugence_procurement.actions.mappings import all_mappings, CREATE_PURCHASE_ORDER
    from ugence_procurement.suppliers.outcomes import SupplierOutcome
    from ugence_procurement.policies.assessment import ProcurementAssessmentService, \
        InMemoryProcurementAssessmentRepository
    from ugence_procurement.validation.request_validation import ProcurementRequestValidator
    from ugence_procurement.errors import (
        PurchaseRequestValidationError, SupplierNotKnownError, BudgetNotKnownError)
else:  # legacy / before
    from applications.procurement.configuration import ProcurementConfiguration
    from applications.procurement.platform import build_in_memory_platform
    from applications.procurement.api.routes import ProcurementAPI
    from domains.procurement.requests.contracts import (
        BudgetReference, PurchaseItem, PurchaseRequest, SupplierReference)
    from domains.procurement.approvals.mappings import PurchaseApproval, PurchaseRecommendation
    from domains.procurement.actions.mappings import all_mappings, CREATE_PURCHASE_ORDER
    from domains.procurement.suppliers.outcomes import SupplierOutcome
    from domains.procurement.policies.assessment import ProcurementAssessmentService, \
        InMemoryProcurementAssessmentRepository
    from domains.procurement.validation.request_validation import ProcurementRequestValidator
    from domains.procurement.errors import (
        PurchaseRequestValidationError, SupplierNotKnownError, BudgetNotKnownError)

TENANT, REQUESTER, APPROVER = "t1", "requester-1", "approver-1"

_ID_RE = re.compile(r"^[a-z_]+-[0-9a-f]{8,}$|[0-9a-f]{12,}")


def _norm(value, seen: dict):
    """Recursively normalize a value: mask volatile ids/timestamps, sort keys."""
    if isinstance(value, Enum):
        return {"__enum__": type(value).__name__, "value": value.value}
    if isinstance(value, datetime):
        return "<TS>"
    if isinstance(value, str):
        # Mask id-like strings to stable order-preserving placeholders so structure
        # is captured but random UUIDs do not perturb the hash.
        if _ID_RE.search(value) and any(ch.isdigit() for ch in value):
            key = value
            if key not in seen:
                seen[key] = f"<ID{len(seen)}>"
            return seen[key]
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _norm(v, seen) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_norm(v, seen) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {"__type__": type(value).__name__,
                **{k: _norm(v, seen) for k, v in sorted(asdict(value).items())}}
    if hasattr(value, "model_dump"):
        return {"__type__": type(value).__name__,
                **_norm(value.model_dump(mode="python"), seen)}
    return {"__repr__": type(value).__name__}


def _build_platform(config=None):
    platform = build_in_memory_platform(config)
    for actor in (REQUESTER, APPROVER):
        platform.identity_provider.register_human(actor)
        platform.policy_adapter.grant_all(actor, TENANT)
    platform.publish_standard_mappings(actor=APPROVER, tenant_id=TENANT)
    return platform


def _request(request_id="pr-1", *, unit_cost=100_000, quantity=2, supplier_id="sup-1",
             budget_id="bud-1", available=100_000_000, justification="operational need"):
    return PurchaseRequest(
        request_id=request_id, tenant_id=TENANT, requester=REQUESTER,
        supplier=SupplierReference(supplier_id=supplier_id, name="Acme"),
        items=(PurchaseItem(description="widgets", quantity=quantity, unit_cost=unit_cost),),
        budget=BudgetReference(budget_id=budget_id, available_amount=available),
        justification=justification)


def _err(fn):
    try:
        fn()
        return "NO_ERROR"
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__


def capture() -> dict:
    seen: dict = {}
    out: dict = {}

    # 1. Deterministic assessment for a valid request (checks + blocked flag).
    repo = InMemoryProcurementAssessmentRepository()
    svc = ProcurementAssessmentService(repo)
    a = svc.assess(_request())
    out["assessment_valid"] = _norm(
        {"status": a.status, "blocked": a.blocked, "total_amount": a.total_amount,
         "checks": [(c.check_id, c.passed) for c in a.checks]}, seen)

    # 2. Assessment for budget-insufficient request (blocking check semantics).
    a2 = svc.assess(_request(available=1))
    out["assessment_budget_insufficient"] = _norm(
        {"blocked": a2.blocked, "failed": [c.check_id for c in a2.failed_checks]}, seen)

    # 3-5. Validation error taxonomy (stable exception classes).
    v = ProcurementRequestValidator(
        known_suppliers=frozenset({"sup-1"}), known_budgets=frozenset({"bud-1"}))
    out["validate_unknown_supplier"] = _err(
        lambda: v.validate(_request(supplier_id="ghost")))
    out["validate_unknown_budget"] = _err(lambda: v.validate(_request(budget_id="ghost")))

    # 6. Action mappings (ids, outcomes, permitted action types, required fields).
    out["action_mappings"] = _norm(
        [{"mapping_id": m.mapping_id, "outcome": m.decision_outcome,
          "action_type": m.permitted_action_type,
          "required": list(m.parameter_schema.required_fields)} for m in all_mappings()], seen)

    # 7. Happy-path end-to-end run.
    api = ProcurementAPI(_build_platform())
    r = api.run(request=_request(), requester=REQUESTER, approver=APPROVER)
    out["e2e_happy"] = _norm(
        {"authorization_outcome": r.authorization_outcome,
         "reconciliation_status": r.reconciliation_status,
         "compensation_required": r.compensation_required,
         "recommendation_type": type(r.recommendation).__name__,
         "decision_type": type(r.decision).__name__}, seen)

    # 8. Amount above approval threshold -> AUTHORIZED_WITH_CONSTRAINTS.
    api2 = ProcurementAPI(_build_platform())
    big = _request(request_id="pr-big", unit_cost=2_000_000, quantity=1, available=100_000_000)
    case, _ = api2.submit_and_assess(big, actor=REQUESTER)
    api2.recommend(case_id=case.decision_case_id,
                   recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    dec = api2.decide(case_id=case.decision_case_id,
                      approval=PurchaseApproval.APPROVED, approver=APPROVER)
    act = api2.request_action(decision=dec, request=big, actor=APPROVER)
    auth = api2.authorize(action_request_id=act.action_request_id, actor=APPROVER)
    out["authorize_above_threshold"] = _norm(
        {"outcome": auth.outcome, "constraints": list(auth.constraints),
         "obligations": list(auth.obligations)}, seen)

    # 9. Restricted supplier -> DENIED (fail-closed), not dispatched.
    api3 = ProcurementAPI(_build_platform(
        ProcurementConfiguration(restricted_suppliers=frozenset({"sup-restricted"}))))
    rr = _request(request_id="pr-restr", supplier_id="sup-restricted")
    case3, _ = api3.submit_and_assess(rr, actor=REQUESTER)
    api3.recommend(case_id=case3.decision_case_id,
                   recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    dec3 = api3.decide(case_id=case3.decision_case_id,
                       approval=PurchaseApproval.APPROVED, approver=APPROVER)
    act3 = api3.request_action(decision=dec3, request=rr, actor=APPROVER)
    auth3 = api3.authorize(action_request_id=act3.action_request_id, actor=APPROVER)
    out["authorize_restricted_supplier"] = _norm({"outcome": auth3.outcome}, seen)

    # 10. Amount above hard limit -> DENIED.
    api4 = ProcurementAPI(_build_platform(
        ProcurementConfiguration(hard_limit=1_000_000)))
    hl = _request(request_id="pr-hard", unit_cost=5_000_000, quantity=1)
    case4, _ = api4.submit_and_assess(hl, actor=REQUESTER)
    api4.recommend(case_id=case4.decision_case_id,
                   recommendation=PurchaseRecommendation.APPROVE, generated_by=REQUESTER)
    dec4 = api4.decide(case_id=case4.decision_case_id,
                       approval=PurchaseApproval.APPROVED, approver=APPROVER)
    act4 = api4.request_action(decision=dec4, request=hl, actor=APPROVER)
    auth4 = api4.authorize(action_request_id=act4.action_request_id, actor=APPROVER)
    out["authorize_above_hard_limit"] = _norm({"outcome": auth4.outcome}, seen)

    # 11. Supplier outcome vocabulary mapping.
    out["supplier_outcome_map"] = _norm(
        {o.name: o.value for o in SupplierOutcome}, seen)

    # 12. Audit event sequence for the happy path (types only, ordered).
    events = [e.event_type for e in api._p.audit_service._repo.all()]
    out["audit_event_types"] = _norm(
        [getattr(e, "value", str(e)) for e in events], seen)

    return out


def main() -> int:
    data = capture()
    print(json.dumps({"mode": MODE, "capture": data}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
