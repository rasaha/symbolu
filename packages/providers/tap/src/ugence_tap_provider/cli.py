"""TAP provider command surface — ``version`` / ``verify`` / ``demo``.

Thin, read-only, offline command surface over the public API. Every subcommand
runs deterministically with the in-process reference engine and prints to stdout —
no network, no model SDK, no credentials, no production integration. Nothing here
authorizes, dispatches, executes, or reconciles an action: TAP evaluates assertion
support only.

    python -m ugence_tap_provider version [--json]
    python -m ugence_tap_provider verify
    python -m ugence_tap_provider demo

A console script ``ugence-tap-provider`` is also provided.
"""
from __future__ import annotations

import json
import sys
from typing import Sequence

from .version import version_info


def _cmd_version(as_json: bool) -> int:
    info = version_info()
    if as_json:
        print(json.dumps(info.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"{info.distribution} {info.distribution_version} (distribution) — "
              f"TAP implementation {info.implementation_version}")
        print(f"contract: {info.contract_version} · mapping: {info.mapping_version} · "
              f"kernel majors: {','.join(info.compatible_kernel_majors)}")
        print(f"production certified: {info.production_certified}")
    return 0


def _cmd_verify() -> int:
    """Assert the packaged provider's safety/governance invariants; print PASS/FAIL."""
    from ugence_governance_provider_framework.api import (
        AssertionCoverage, AssertionGovernanceRequest, ProviderKind)

    from .api import __version__ as impl_version
    from .configuration import build_tap_provider
    from .core import TapEngine

    checks: list[tuple[str, bool]] = []

    def check(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    prov = build_tap_provider(TapEngine())
    prov.initialize()
    d = prov.descriptor()

    check("canonical_import", impl_version == "0.1.0")
    check("assertion_governance_kind", d.kind is ProviderKind.ASSERTION_GOVERNANCE)
    check("framework_compatibility", "1" in d.compatibility.compatible_kernel_majors)
    check("provider_descriptor", d.provider_id == "tap" and d.vendor == "TAP")

    supported = prov.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    check("request_result_mapping", supported.coverage is AssertionCoverage.SUPPORTED
          and supported.evidence_coverage == 1.0)

    indeterminate = prov.evaluate(AssertionGovernanceRequest("A", evidence_refs=()))
    check("missing_evidence_indeterminate",
          indeterminate.coverage is AssertionCoverage.INDETERMINATE)

    # fail-safe: infrastructure failure never becomes SUPPORTED
    failsafe_ok = True
    for mode in ("timeout", "unavailable", "malformed", "protocol", "config"):
        p = build_tap_provider(TapEngine(fail=mode))
        p.initialize()
        r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
        failsafe_ok = failsafe_ok and r.coverage is AssertionCoverage.INDETERMINATE
    check("fail_safe_never_supported", failsafe_ok)

    unknown = build_tap_provider(TapEngine(emit_unknown=True))
    unknown.initialize()
    ur = unknown.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    check("unknown_outcome_indeterminate", ur.coverage is AssertionCoverage.INDETERMINATE)

    # health never raises and degrades when the engine is unavailable
    degraded = build_tap_provider(TapEngine(fail="unavailable"))
    degraded.initialize()
    check("health_degrades", not degraded.health().healthy)

    # dependency availability
    try:
        import ugence_governance_provider_framework  # noqa: F401
        check("framework_dependency_available", True)
    except Exception:
        check("framework_dependency_available", False)

    # ActionGate absence: TAP core must not reach any ActionGate module
    ag_absent = not any(m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")
                        for m in list(sys.modules))
    check("actiongate_absent", ag_absent)

    # no execution/authorization surface on the provider
    no_exec = not any(hasattr(prov, m) for m in
                      ("authorize", "dispatch", "execute", "reconcile", "compensate"))
    check("no_execution_surface", no_exec)

    ok = all(c for _, c in checks)
    for name, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print(f"verify: {'PASS' if ok else 'FAIL'} "
          f"({sum(c for _, c in checks)}/{len(checks)} checks)")
    return 0 if ok else 1


def _cmd_demo() -> int:
    """Offline demo: assertion + supplied evidence → TAP evaluation → assessment.

    Shows at least a supported, a constrained/unsupported, and an
    indeterminate (provider-failure) outcome. Nothing is authorized or executed.
    """
    from ugence_governance_provider_framework.api import (
        AssertionAssessmentIntegration, AssertionGovernanceRequest)

    from .configuration import build_tap_provider
    from .core import TapConstraint, TapEngine, TapObligation, TapOutcome, TapRule

    supplier = "Supplier X reduced costs and retains full compliance"
    constrained_rule = TapRule(
        outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.6,
        supported_components=("cost_reduction",),
        unsupported_components=("full_compliance",),
        omitted_qualifiers=("segment_scope",),
        constraints=(TapConstraint("required_qualifier", "segment_scope"),),
        obligations=(TapObligation("include_uncertainty_disclosure"),),
        reason_codes=("scope_expansion",))

    def show(title: str, provider, request) -> None:
        # ``assess`` is fully offline (it does NOT touch the Decision Authority
        # kernel; only the optional LinkedRecord projection would).
        assessment = AssertionAssessmentIntegration(provider).assess(request)
        line = (f"[{title}] coverage={assessment.coverage.value} "
                f"evidence_coverage={assessment.evidence_coverage} "
                f"finalized={assessment.finalized} blocked={assessment.blocked}")
        if assessment.unsupported_elements:
            line += f" unsupported={list(assessment.unsupported_elements)}"
        print(line)

    supported_p = build_tap_provider(TapEngine())
    supported_p.initialize()
    show("SUPPORTED", supported_p,
         AssertionGovernanceRequest("Team shipped the feature", evidence_refs=("e1",)))

    constrained_p = build_tap_provider(TapEngine(rules={supplier: constrained_rule}))
    constrained_p.initialize()
    show("CONSTRAINED", constrained_p,
         AssertionGovernanceRequest(supplier, evidence_refs=("e1", "e2")))

    failing_p = build_tap_provider(TapEngine(fail="timeout"))
    failing_p.initialize()
    show("INDETERMINATE (provider failure)", failing_p,
         AssertionGovernanceRequest("Latency dropped 40%", evidence_refs=("e1",)))

    print("demo: OK — assertion support only; nothing authorized or executed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    positional = [a for a in argv if a != "--json"]
    command = positional[0] if positional else "version"
    if command == "version":
        return _cmd_version(as_json)
    if command == "verify":
        return _cmd_verify()
    if command == "demo":
        return _cmd_demo()
    print(f"unknown command: {command!r} (expected version|verify|demo)", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
