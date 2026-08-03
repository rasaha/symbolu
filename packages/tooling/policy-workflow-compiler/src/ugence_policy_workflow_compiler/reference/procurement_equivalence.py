"""Procurement reference-equivalence harness.

Compares the compiler's interpretation of the Procurement pack against the live
``ugence-procurement`` reference workflow across a frozen scenario matrix. The goal
is **semantic control equivalence**, not generated-code equivalence.

``ugence-procurement`` is imported lazily so the core package installs and runs
without it; the harness raises :class:`ReferenceUnavailable` when it is absent.

Dimensions compared:
  * assessment blocking (fail-closed evidence checks);
  * exact-action authorization classification (EXPIRED / DENIED /
    AUTHORIZED_WITH_CONSTRAINTS / AUTHORIZED), in the reference's evaluation order;
  * recommendation / approval / supplier-outcome / decision-action mappings;
  * reconciliation → compensation (supplier rejection requires compensation).

Each dimension yields one of:
  EQUIVALENT, ADDITIVE_NON_CONFLICTING, MISSING_COMPILER_COVERAGE,
  CONFLICTING_INTERPRETATION, REFERENCE_BEHAVIOR_UNMODELED, INVALID_REFERENCE_PACK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

from ..models.actions import ConstraintKind
from ..models.policy_pack import PolicyPack
from .procurement import APPROVAL_THRESHOLD, HARD_LIMIT, build_procurement_policy_pack

# Equivalence classifications.
EQUIVALENT = "EQUIVALENT"
ADDITIVE_NON_CONFLICTING = "ADDITIVE_NON_CONFLICTING"
MISSING_COMPILER_COVERAGE = "MISSING_COMPILER_COVERAGE"
CONFLICTING_INTERPRETATION = "CONFLICTING_INTERPRETATION"
REFERENCE_BEHAVIOR_UNMODELED = "REFERENCE_BEHAVIOR_UNMODELED"
INVALID_REFERENCE_PACK = "INVALID_REFERENCE_PACK"


class ReferenceUnavailable(RuntimeError):
    """Raised when ugence-procurement is not importable."""


@dataclass(frozen=True)
class DimensionResult:
    dimension: str
    classification: str
    checked: int
    mismatches: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EquivalenceResult:
    classification: str
    dimensions: Tuple[DimensionResult, ...] = field(default_factory=tuple)

    @property
    def equivalent(self) -> bool:
        return self.classification == EQUIVALENT

    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "dimensions": [
                {
                    "dimension": d.dimension,
                    "classification": d.classification,
                    "checked": d.checked,
                    "mismatches": list(d.mismatches),
                }
                for d in self.dimensions
            ],
        }


# -- scenario matrix -----------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    name: str
    supplier_id: str
    budget_id: str
    amount: int
    restricted_suppliers: Tuple[str, ...] = ()
    restricted_budgets: Tuple[str, ...] = ()
    cer_expired: bool = False
    requester: str = "req-1"
    items: int = 1


FROZEN_SCENARIOS: Tuple[Scenario, ...] = (
    Scenario("happy_normal", "sup-1", "bud-1", 500_000),
    Scenario("elevated_threshold", "sup-1", "bud-1", 2_000_000),
    Scenario("at_threshold_boundary", "sup-1", "bud-1", APPROVAL_THRESHOLD),
    Scenario("hard_limit_exceeded", "sup-1", "bud-1", HARD_LIMIT + 1),
    Scenario("at_hard_limit_boundary", "sup-1", "bud-1", HARD_LIMIT),
    Scenario("restricted_supplier", "sup-block", "bud-1", 500_000,
             restricted_suppliers=("sup-block",)),
    Scenario("restricted_budget", "sup-1", "bud-block", 500_000,
             restricted_budgets=("bud-block",)),
    Scenario("expired_cer", "sup-1", "bud-1", 500_000, cer_expired=True),
    Scenario("restricted_and_over_limit", "sup-block", "bud-1", HARD_LIMIT + 1,
             restricted_suppliers=("sup-block",)),
)


# -- reference side ------------------------------------------------------------

def _require_reference():
    try:
        import ugence_procurement  # noqa: F401
    except Exception as exc:  # pragma: no cover - exercised only without the extra
        raise ReferenceUnavailable(
            "ugence-procurement is not installed; install the "
            "'procurement-reference' extra to run the equivalence harness"
        ) from exc


def _reference_authorize(scenario: Scenario) -> str:
    from datetime import timedelta

    from ugence_decision_authority.api.common import utc_now
    from ugence_procurement.policies.budget_authority import BudgetAuthorityAdapter

    adapter = BudgetAuthorityAdapter(
        restricted_suppliers=frozenset(scenario.restricted_suppliers),
        restricted_budgets=frozenset(scenario.restricted_budgets),
    )
    now = utc_now()
    request = SimpleNamespace(
        requested_parameters={
            "supplier_id": scenario.supplier_id,
            "budget_id": scenario.budget_id,
            "amount": str(scenario.amount),
        }
    )
    expires_at = (now - timedelta(hours=1)) if scenario.cer_expired else (now + timedelta(hours=1))
    cer = SimpleNamespace(expires_at=expires_at)
    outcome, _c, _o = adapter._classify(request, cer, now)
    return outcome.value


def _reference_assessment_blocked(scenario: Scenario) -> bool:
    from ugence_procurement.policies.assessment import (
        InMemoryProcurementAssessmentRepository,
        ProcurementAssessmentService,
    )
    from ugence_procurement.requests.contracts import (
        BudgetReference,
        PurchaseItem,
        PurchaseRequest,
        SupplierReference,
    )

    service = ProcurementAssessmentService(InMemoryProcurementAssessmentRepository())
    request = PurchaseRequest(
        request_id="r-1",
        tenant_id="t-1",
        requester=scenario.requester,
        supplier=SupplierReference(supplier_id=scenario.supplier_id),
        items=tuple(
            PurchaseItem(description="widget", quantity=1, unit_cost=scenario.amount)
            for _ in range(max(scenario.items, 1))
        ),
        budget=BudgetReference(budget_id=scenario.budget_id, available_amount=10**12),
    )
    return service.assess(request).blocked


@dataclass(frozen=True)
class RejectionScenario:
    """A fail-closed scenario: the reference rejects it before/at governance."""

    name: str
    supplier_id: str
    budget_id: str
    amount: int
    known_suppliers: Optional[Tuple[str, ...]] = None
    known_budgets: Optional[Tuple[str, ...]] = None


REJECTION_SCENARIOS: Tuple[RejectionScenario, ...] = (
    RejectionScenario("valid_known", "sup-1", "bud-1", 500_000,
                      known_suppliers=("sup-1",), known_budgets=("bud-1",)),
    RejectionScenario("empty_supplier", "", "bud-1", 500_000),
    RejectionScenario("empty_budget", "sup-1", "", 500_000),
    RejectionScenario("non_positive_total", "sup-1", "bud-1", 0),
    RejectionScenario("unknown_supplier", "sup-x", "bud-1", 500_000,
                      known_suppliers=("sup-1",), known_budgets=("bud-1",)),
    RejectionScenario("unknown_budget", "sup-1", "bud-x", 500_000,
                      known_suppliers=("sup-1",), known_budgets=("bud-1",)),
)


def _reference_rejects(rs: RejectionScenario) -> bool:
    """True if the reference rejects the request at contract or request validation."""
    from ugence_procurement.errors import ProcurementError
    from ugence_decision_authority.api.errors import DomainValidationError
    from ugence_procurement.requests.contracts import (
        BudgetReference,
        PurchaseItem,
        PurchaseRequest,
        SupplierReference,
    )
    from ugence_procurement.validation.request_validation import ProcurementRequestValidator

    try:
        request = PurchaseRequest(
            request_id="r-1",
            tenant_id="t-1",
            requester="req-1",
            supplier=SupplierReference(supplier_id=rs.supplier_id),
            items=(PurchaseItem(description="widget", quantity=1, unit_cost=rs.amount),),
            budget=BudgetReference(budget_id=rs.budget_id, available_amount=10**12),
        )
        validator = ProcurementRequestValidator(
            known_suppliers=frozenset(rs.known_suppliers) if rs.known_suppliers is not None else None,
            known_budgets=frozenset(rs.known_budgets) if rs.known_budgets is not None else None,
        )
        validator.validate(request)
        return False
    except (DomainValidationError, ProcurementError):
        return True


def _pack_rejects(pack: PolicyPack, rs: RejectionScenario) -> bool:
    """True if the pack's fail-closed guards (prohibited conditions + BLOCK
    evidence presence) reject the scenario."""
    supplier_known = rs.supplier_id in rs.known_suppliers if rs.known_suppliers is not None else True
    budget_known = rs.budget_id in rs.known_budgets if rs.known_budgets is not None else True
    facts = {
        "total_amount": rs.amount,
        "supplier_known": supplier_known,
        "budget_known": budget_known,
        "supplier_id": bool(rs.supplier_id.strip()),
        "budget_id": bool(rs.budget_id.strip()),
        "required_fields_complete": True,
    }
    for cond in pack.prohibited_conditions:
        if not cond.enabled:
            continue
        if any(_eval_predicate(p, facts) for p in cond.conditions):
            return True
    for ev in pack.required_evidence:
        if ev.on_missing.value == "BLOCK" and not facts.get(ev.fact_key, True):
            return True
    return False


def _eval_predicate(pred, facts) -> bool:
    from ..models.rules import Comparator

    val = facts.get(pred.fact_key)
    c = pred.comparator
    if c is Comparator.IS_TRUE:
        return val is True
    if c is Comparator.IS_FALSE:
        return val is False
    if c is Comparator.LTE:
        return val is not None and val <= pred.value
    if c is Comparator.LT:
        return val is not None and val < pred.value
    if c is Comparator.GTE:
        return val is not None and val >= pred.value
    if c is Comparator.GT:
        return val is not None and val > pred.value
    if c is Comparator.EQ:
        return val == pred.value
    if c is Comparator.NE:
        return val != pred.value
    return False


def _reference_mappings() -> Dict[str, Dict[str, str]]:
    from ugence_procurement.approvals.mappings import (
        APPROVAL_TO_DECISION,
        RECOMMENDATION_TO_PROPOSED,
    )
    from ugence_procurement.suppliers.outcomes import SUPPLIER_TO_BUSINESS

    return {
        "recommendation_to_proposed": {
            k.value: v.value for k, v in RECOMMENDATION_TO_PROPOSED.items()
        },
        "approval_to_decision": {
            k.value: v.value for k, v in APPROVAL_TO_DECISION.items()
        },
        "supplier_to_business": {
            k.value: v.value for k, v in SUPPLIER_TO_BUSINESS.items()
        },
    }


# -- pack-derived side ---------------------------------------------------------

def _pack_authorize(pack: PolicyPack, scenario: Scenario) -> str:
    """Evaluate the pack's CREATE_PURCHASE_ORDER action constraints in order."""
    for c in pack.action_constraints:
        if c.action_type != "CREATE_PURCHASE_ORDER" or not c.enabled:
            continue
        if c.kind is ConstraintKind.ONCE_ONLY and c.parameter == "cer_expiry":
            if scenario.cer_expired:
                return c.violation_reason_code  # EXPIRED
        elif c.kind is ConstraintKind.NOT_MEMBER_OF and c.parameter == "supplier_id":
            if scenario.supplier_id in scenario.restricted_suppliers:
                return c.violation_reason_code  # DENIED
        elif c.kind is ConstraintKind.NOT_MEMBER_OF and c.parameter == "budget_id":
            if scenario.budget_id in scenario.restricted_budgets:
                return c.violation_reason_code  # DENIED
        elif c.kind is ConstraintKind.HARD_LIMIT and c.parameter == "amount":
            if c.max_value is not None and scenario.amount > c.max_value:
                return c.violation_reason_code  # DENIED
        elif c.kind is ConstraintKind.NUMERIC_RANGE and c.parameter == "amount":
            if c.max_value is not None and scenario.amount > c.max_value:
                return c.violation_reason_code  # AUTHORIZED_WITH_CONSTRAINTS
    return "AUTHORIZED"


def _pack_assessment_blocked(pack: PolicyPack, scenario: Scenario) -> bool:
    """Blocked if any BLOCK required-evidence fact is missing/false."""
    facts = {
        "supplier_id": bool(scenario.supplier_id.strip()),
        "budget_id": bool(scenario.budget_id.strip()),
        "required_fields_complete": bool(scenario.items) and bool(scenario.requester.strip()),
    }
    for ev in pack.required_evidence:
        if ev.on_missing.value == "BLOCK" and not facts.get(ev.fact_key, True):
            return True
    return False


#: The pack author's captured reference mapping expectations (from procurement).
_EXPECTED_MAPPINGS: Dict[str, Dict[str, str]] = {
    "recommendation_to_proposed": {
        "APPROVE": "ADVANCE",
        "REJECT": "REJECT",
        "ESCALATE": "HOLD",
        "NEEDS_REVIEW": "REQUEST_ADDITIONAL_EVIDENCE",
    },
    "approval_to_decision": {
        "APPROVED": "ADVANCE",
        "APPROVED_WITH_CONDITIONS": "ADVANCE",
        "REJECTED": "REJECT",
    },
    "supplier_to_business": {
        "ACCEPTED": "SUCCEEDED",
        "REJECTED": "REJECTED",
        "TIMED_OUT": "UNKNOWN",
        "UNKNOWN": "UNKNOWN",
    },
}


# -- the harness ---------------------------------------------------------------

def run_equivalence(pack: Optional[PolicyPack] = None) -> EquivalenceResult:
    """Run the full Procurement equivalence harness and classify the result."""
    _require_reference()
    pack = pack or build_procurement_policy_pack()

    dimensions: List[DimensionResult] = []

    # Authorization classification.
    auth_mismatches = []
    for s in FROZEN_SCENARIOS:
        ref = _reference_authorize(s)
        got = _pack_authorize(pack, s)
        if ref != got:
            auth_mismatches.append(f"{s.name}: reference={ref} pack={got}")
    dimensions.append(
        DimensionResult(
            "authorization",
            EQUIVALENT if not auth_mismatches else CONFLICTING_INTERPRETATION,
            len(FROZEN_SCENARIOS),
            tuple(auth_mismatches),
        )
    )

    # Assessment blocking on valid requests (neither side blocks a valid request).
    assess_mismatches = []
    for s in FROZEN_SCENARIOS:
        ref = _reference_assessment_blocked(s)
        got = _pack_assessment_blocked(pack, s)
        if ref != got:
            assess_mismatches.append(f"{s.name}: reference={ref} pack={got}")
    dimensions.append(
        DimensionResult(
            "assessment_blocking",
            EQUIVALENT if not assess_mismatches else CONFLICTING_INTERPRETATION,
            len(FROZEN_SCENARIOS),
            tuple(assess_mismatches),
        )
    )

    # Fail-closed structural validation (empty/unknown supplier/budget, bad total).
    fc_mismatches = []
    for rs in REJECTION_SCENARIOS:
        ref = _reference_rejects(rs)
        got = _pack_rejects(pack, rs)
        if ref != got:
            fc_mismatches.append(f"{rs.name}: reference_reject={ref} pack_reject={got}")
    dimensions.append(
        DimensionResult(
            "fail_closed_validation",
            EQUIVALENT if not fc_mismatches else CONFLICTING_INTERPRETATION,
            len(REJECTION_SCENARIOS),
            tuple(fc_mismatches),
        )
    )

    # Mapping tables.
    ref_mappings = _reference_mappings()
    map_mismatches = []
    for key, expected in _EXPECTED_MAPPINGS.items():
        if ref_mappings.get(key) != expected:
            map_mismatches.append(
                f"{key}: reference={ref_mappings.get(key)} expected={expected}"
            )
    dimensions.append(
        DimensionResult(
            "vocabulary_mappings",
            EQUIVALENT if not map_mismatches else CONFLICTING_INTERPRETATION,
            len(_EXPECTED_MAPPINGS),
            tuple(map_mismatches),
        )
    )

    # Reconciliation/compensation: supplier REJECTED must not become success.
    recon_ok = ref_mappings["supplier_to_business"].get("REJECTED") == "REJECTED"
    dimensions.append(
        DimensionResult(
            "reconciliation_compensation",
            EQUIVALENT if recon_ok else CONFLICTING_INTERPRETATION,
            1,
            () if recon_ok else ("supplier REJECTED does not map to REJECTED",),
        )
    )

    overall = (
        EQUIVALENT
        if all(d.classification == EQUIVALENT for d in dimensions)
        else CONFLICTING_INTERPRETATION
    )
    return EquivalenceResult(overall, tuple(dimensions))
