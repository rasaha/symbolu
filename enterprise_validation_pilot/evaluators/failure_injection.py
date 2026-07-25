"""Deterministic failure injection at controlled points (Task 111).

A controlled harness that injects each required failure and verifies fail-safe
behavior. No randomness is used. Provider/execution failures are injected via
targeted scenarios; registry/version failures are injected through the framework
API directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from governance_providers.api import (
    ProviderCompatibilityError, ProviderKind, ProviderRegistry, ProviderResolutionError,
    ResolutionRequest, resolve)

from ..runners.workflow import run_scenario
from ..schemas.scenario import (
    ActionPolicy, EvidenceSpec, ExecutionSpec, ExpectedOutcome, HumanReviewSpec,
    ProposedActionSpec, Scenario, TapPolicy)


@dataclass(frozen=True)
class InjectionResult:
    injection: str
    fail_safe: bool
    detail: str


def _ev(n=2):
    return tuple(EvidenceSpec(f"ev-{i}", "record", f"ref/{i}", "excerpt", "caller_supplied")
                 for i in range(1, n + 1))


def _base(scenario_id, *, tap: TapPolicy, action: ActionPolicy,
          execution: ExecutionSpec = ExecutionSpec(), human=None,
          params=None) -> Scenario:
    exp = ExpectedOutcome(tap_outcome=tap.outcome)
    return Scenario(
        scenario_id=scenario_id, domain="injection", assertion_class="FULLY_SUPPORTED",
        action_class="AUTHORIZED", cross_class="BOTH_PROVIDERS_AVAILABLE",
        assertion="injection assertion", assertion_type="claim",
        evidence=_ev(0 if tap.outcome == "INDETERMINATE" and not tap.fail else 2),
        tap_policy=tap, action_policy=action,
        proposed_action=ProposedActionSpec(
            action_type="ACT", parameters=params or {"amount": "10"}, target_system="SYS",
            domain_id="injection", required_fields=("amount",)),
        execution=execution, expected=exp, human_review=human)


def run_failure_injection() -> list[InjectionResult]:
    results: list[InjectionResult] = []

    def add(name, fail_safe, detail):
        results.append(InjectionResult(name, fail_safe, detail))

    sup = TapPolicy(outcome="SUPPORTED", evidence_coverage=1.0,
                    supported_components=("c",), reason_codes=("evidence_supports",))

    # --- TAP failures → INDETERMINATE, no action ---------------------------
    for mode in ("timeout", "unavailable", "malformed"):
        r = run_scenario(_base(f"inj-tap-{mode}",
                               tap=TapPolicy(outcome="INDETERMINATE", fail=mode),
                               action=ActionPolicy(mode="allow")))
        ok = (r.tap_outcome == "INDETERMINATE" and r.tap_failsafe
              and not r.proceeded_to_action and not r.dispatched and not r.error)
        add(f"tap_{mode}", ok, f"tap_outcome={r.tap_outcome} failsafe={r.tap_failsafe} "
            f"dispatched={r.dispatched}")

    # --- ActionGate failures → INDETERMINATE auth, no dispatch -------------
    for mode in ("timeout", "unavailable", "malformed"):
        r = run_scenario(_base(f"inj-ag-{mode}", tap=sup,
                               action=ActionPolicy(mode="allow", fail=mode)))
        ok = (r.actiongate_outcome == "INDETERMINATE" and not r.dispatched and not r.error)
        add(f"actiongate_{mode}", ok,
            f"auth={r.actiongate_outcome} dispatched={r.dispatched}")

    # --- execution failures ------------------------------------------------
    r = run_scenario(_base("inj-exec-timeout", tap=sup, action=ActionPolicy(mode="allow"),
                           execution=ExecutionSpec(timeout=True)))
    add("execution_timeout", r.dispatched and r.reconciliation == "FAILED",
        f"dispatched={r.dispatched} recon={r.reconciliation}")

    r = run_scenario(_base("inj-exec-business", tap=sup, action=ActionPolicy(mode="allow"),
                           execution=ExecutionSpec(business_outcome="REJECTED")))
    add("execution_business_rejection",
        r.dispatched and r.reconciliation == "FAILED"
        and r.compliance_verdict == "NONCOMPLIANT",
        f"recon={r.reconciliation} compliance={r.compliance_verdict}")

    r = run_scenario(_base("inj-exec-transport", tap=sup, action=ActionPolicy(mode="allow"),
                           execution=ExecutionSpec(transport_fail=True)))
    add("execution_transport_failure", r.reconciliation == "FAILED",
        f"recon={r.reconciliation}")

    # --- reconciliation mismatch -------------------------------------------
    r = run_scenario(_base("inj-recon-mismatch", tap=sup, action=ActionPolicy(mode="allow"),
                           execution=ExecutionSpec(observed_overrides={"amount": "999999"})))
    add("reconciliation_mismatch",
        r.reconciliation == "MISMATCHED" and r.compliance_verdict == "NONCOMPLIANT",
        f"recon={r.reconciliation} compliance={r.compliance_verdict}")

    # --- missing obligation evidence (human declines approval) -------------
    r = run_scenario(_base(
        "inj-obligation-missing", tap=sup,
        action=ActionPolicy(mode="constrained", constraints=(("execution_deadline", "3600"),),
                            obligations=(("human_review", ""),)),
        human=HumanReviewSpec(action="decline_action", approver="senior")))
    add("missing_obligation_evidence",
        r.compliance_verdict == "NONCOMPLIANT"
        and any(o.state == "FAILED" for o in r.obligation_records),
        f"compliance={r.compliance_verdict}")

    # --- registry resolution failure ---------------------------------------
    try:
        resolve(ProviderRegistry(), ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
        add("registry_resolution_failure", False, "no error raised for empty registry")
    except ProviderResolutionError:
        add("registry_resolution_failure", True,
            "empty registry raises ProviderResolutionError (no silent selection)")

    # --- incompatible provider version -------------------------------------
    try:
        _register_incompatible()
        add("incompatible_provider_version", False, "incompatible descriptor accepted")
    except ProviderCompatibilityError:
        add("incompatible_provider_version", True,
            "registry rejects an incompatible contract version")

    return results


def _register_incompatible():
    from governance_providers.api import (
        ProviderCapabilities, ProviderCompatibility, ProviderDescriptor)
    reg = ProviderRegistry()
    reg.register(ProviderDescriptor(
        provider_id="bad", kind=ProviderKind.ASSERTION_GOVERNANCE,
        implementation_version="0.1.0",
        compatibility=ProviderCompatibility(contract_version="99.0.0",
                                            compatible_kernel_majors=frozenset({"1"})),
        capabilities=ProviderCapabilities(kind=ProviderKind.ASSERTION_GOVERNANCE,
                                          features=frozenset({"evaluate"})),
        factory=lambda: None))


def failure_injection_passed(results: list[InjectionResult]) -> bool:
    return all(r.fail_safe for r in results)
