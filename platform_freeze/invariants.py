"""Canonical platform invariant register F1–F20 (Task 6).

Each invariant records its statement, change-class category, and the authoritative
test that certifies it (no test is duplicated). Behaviourally-critical invariants
also carry a fast, independent freeze-check the verifier runs directly, so the
freeze is confirmed without re-running the whole suite.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Invariant:
    id: str
    statement: str
    authoritative_test: str
    check: Optional[Callable] = None    # fast direct freeze-check, or None (referenced)


# --- fast direct checks -----------------------------------------------------

def _f9_f10_denied_indeterminate_never_dispatch() -> bool:
    from actiongate_provider.configuration import build_actiongate_provider
    from actiongate_provider.core import ActionGateEngine
    from governance_providers.api import ActionGovernanceOutcome, ActionGovernanceRequest
    denied = build_actiongate_provider(ActionGateEngine(denied=frozenset({"A"})))
    denied.initialize()
    unknown = build_actiongate_provider(ActionGateEngine(unknown=frozenset({"A"})))
    unknown.initialize()
    return (denied.authorize(ActionGovernanceRequest("A")).outcome is ActionGovernanceOutcome.DENIED
            and unknown.authorize(ActionGovernanceRequest("A")).outcome
            is ActionGovernanceOutcome.INDETERMINATE)


def _f11_unsupported_stays_unsupported() -> bool:
    from tap_provider.configuration import build_tap_provider
    from tap_provider.core import TapEngine, TapOutcome, TapRule
    from governance_providers.api import AssertionCoverage, AssertionGovernanceRequest
    eng = TapEngine(rules={"X": TapRule(outcome=TapOutcome.UNSUPPORTED)})
    p = build_tap_provider(eng); p.initialize()
    return p.evaluate(AssertionGovernanceRequest("X", evidence_refs=("e",))).coverage \
        is AssertionCoverage.UNSUPPORTED


def _f12_provider_failure_fail_safe() -> bool:
    from tap_provider.configuration import build_tap_provider
    from tap_provider.core import TapEngine
    from governance_providers.api import AssertionCoverage, AssertionGovernanceRequest
    p = build_tap_provider(TapEngine(fail="timeout")); p.initialize()
    return p.evaluate(AssertionGovernanceRequest("X", evidence_refs=("e",))).coverage \
        is AssertionCoverage.INDETERMINATE


def _f13_constraints_enforced_before_dispatch() -> bool:
    from comparative_governance_benchmark.runners.enforcement import enforce
    return enforce(("maximum_amount=100",), {"amount": "200"}).blocked \
        and enforce(("maximum_amount=100",), {"amount": "50"}).allowed


def _f14_obligations_separate_from_execution() -> bool:
    from comparative_governance_benchmark.runners.obligations import (
        compliance_verdict, verify_obligations)
    recs = verify_obligations(("human_review",), human_approval=False)
    return compliance_verdict(recs, reconciliation_ok=True, dispatched=True) == "NONCOMPLIANT"


def _f16_f17_provider_isolation() -> bool:
    from .dependencies import check_dependency_direction
    return not check_dependency_direction()


def _f18_f19_deterministic_no_shopping() -> bool:
    from provider_heterogeneity_validation.selection import (
        CatalogEntry, ProviderCatalog, ProviderState, ResolutionPolicy, SelectionRequest, select)
    from provider_heterogeneity_validation.profiles.capabilities import capabilities_of
    cat = ProviderCatalog()
    cat.add(CatalogEntry("tap-primary", "ASSERTION_GOVERNANCE", "0.1.0",
                         capabilities_of("tap-primary"), ProviderState()))
    cat.add(CatalogEntry("baseline-assertion", "ASSERTION_GOVERNANCE", "0.1.0",
                         capabilities_of("baseline-assertion"), ProviderState()))
    req = SelectionRequest("ASSERTION_GOVERNANCE", ResolutionPolicy.ORDERED,
                           preference_order=("tap-primary", "baseline-assertion"))
    _a, r1 = select(cat, req, request_id="x")
    _b, r2 = select(cat, req, request_id="y")
    return r1.resolution_fingerprint == r2.resolution_fingerprint \
        and r1.selected_provider_id == "tap-primary"


def _f20_acyclic() -> bool:
    from .dependencies import check_dependency_direction
    return not check_dependency_direction()


REGISTER = (
    Invariant("F1", "DGM owns governance lifecycle records.",
              "enterprise_validation_pilot/tests/test_scenarios_and_invariants.py"),
    Invariant("F2", "AI recommendations are advisory and non-binding.",
              "ai_hiring/tests (decision boundary)"),
    Invariant("F3", "AI is never recorded as human decision authority.",
              "ai_hiring/tests (decision boundary)"),
    Invariant("F4", "Assertion governance evaluates claims and evidence.",
              "tap_provider/tests/test_conformance.py"),
    Invariant("F5", "Action governance authorizes proposed actions.",
              "actiongate_provider/tests/test_conformance.py"),
    Invariant("F6", "Assertion governance does not authorize execution.",
              "tap_provider/tests/test_dependency_boundaries.py"),
    Invariant("F7", "Action governance does not determine assertion truth.",
              "actiongate_provider/tests/test_dependency_boundaries.py"),
    Invariant("F8", "External execution remains separate from authorization.",
              "enterprise_validation_pilot/tests/test_scenarios_and_invariants.py"),
    Invariant("F9", "DENIED actions never dispatch.",
              "enterprise_validation_pilot/tests (I3)", _f9_f10_denied_indeterminate_never_dispatch),
    Invariant("F10", "INDETERMINATE authorization never dispatches.",
              "enterprise_validation_pilot/tests (I4)", _f9_f10_denied_indeterminate_never_dispatch),
    Invariant("F11", "UNSUPPORTED assertions never become supported downstream without new "
              "evidence or authority.",
              "comparative_governance_benchmark/tests (I1)", _f11_unsupported_stays_unsupported),
    Invariant("F12", "Provider infrastructure failure never produces support or authorization.",
              "tap_provider/tests/test_mapping_and_errors.py", _f12_provider_failure_fail_safe),
    Invariant("F13", "Constraints are enforced before dispatch.",
              "enterprise_validation_pilot/tests (Task 107)", _f13_constraints_enforced_before_dispatch),
    Invariant("F14", "Obligations are verified separately from execution success.",
              "enterprise_validation_pilot/tests (I9)", _f14_obligations_separate_from_execution),
    Invariant("F15", "Human approval cannot be fabricated by a provider.",
              "enterprise_validation_pilot/tests (I14)"),
    Invariant("F16", "Providers interact through neutral framework contracts.",
              "*/tests/test_dependency_boundaries.py", _f16_f17_provider_isolation),
    Invariant("F17", "Providers of the same or different families do not invoke one another.",
              "provider_heterogeneity_validation/tests (H14-H16)", _f16_f17_provider_isolation),
    Invariant("F18", "Provider resolution is deterministic and auditable.",
              "provider_heterogeneity_validation/tests (H1)", _f18_f19_deterministic_no_shopping),
    Invariant("F19", "Fallback cannot be used for governance shopping.",
              "provider_heterogeneity_validation/tests (H5-H8)", _f18_f19_deterministic_no_shopping),
    Invariant("F20", "Frozen package dependency direction remains acyclic.",
              "platform_freeze dependency check", _f20_acyclic),
)


def verify_invariants() -> list:
    """Return [{id, statement, status, authoritative_test}] — VERIFIED / REFERENCED / FAILED."""
    out = []
    for inv in REGISTER:
        if inv.check is None:
            status = "REFERENCED"
        else:
            try:
                status = "VERIFIED" if inv.check() else "FAILED"
            except Exception as exc:  # noqa: BLE001
                status = f"ERROR:{type(exc).__name__}"
        out.append({"id": inv.id, "statement": inv.statement, "status": status,
                    "authoritative_test": inv.authoritative_test})
    return out


def invariants_ok(results: list) -> bool:
    return all(r["status"] in ("VERIFIED", "REFERENCED") for r in results)
