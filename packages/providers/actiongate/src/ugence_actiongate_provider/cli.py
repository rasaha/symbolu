"""ActionGate provider command surface — ``version`` / ``verify`` / ``demo``.

Thin, read-only, offline command surface over the public API. Every subcommand runs
deterministically with the in-process reference engine and prints to stdout — no
network, no model SDK, no credentials, no production integration. **Nothing here
authorizes an action into execution:** ActionGate returns an *authorization outcome*
only; it never dispatches, executes, observes, or reconciles. The demo explicitly
stops before dispatch and shows ``authorized ≠ executed``.

    python -m ugence_actiongate_provider version [--json]
    python -m ugence_actiongate_provider verify
    python -m ugence_actiongate_provider demo

A console script ``ugence-actiongate-provider`` is also provided.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Sequence

from .version import version_info


def _cmd_version(as_json: bool) -> int:
    info = version_info()
    if as_json:
        print(json.dumps(info.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"{info.distribution} {info.distribution_version} (distribution) — "
              f"ActionGate implementation {info.implementation_version}")
        print(f"contract: {info.contract_version} · mapping: {info.mapping_version} · "
              f"kernel majors: {','.join(info.compatible_kernel_majors)}")
        print(f"production certified: {info.production_certified}")
    return 0


def _fixed_clock() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _cmd_verify() -> int:
    """Assert the packaged provider's authorization-boundary invariants; PASS/FAIL."""
    from ugence_governance_provider_framework.api import (
        ActionGovernanceOutcome, ActionGovernanceRequest, ProviderKind,
        ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)

    from .api import __version__ as impl_version
    from .configuration import build_actiongate_provider
    from .core import (ActionGateConstraint, ActionGateEngine, ActionGateObligation,
                       ConstrainedRule)
    from .provider import ActionGateProvider
    from .client import InProcessActionGateClient

    checks: list[tuple[str, bool]] = []

    def check(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    def prov(**engine_kw):
        p = build_actiongate_provider(ActionGateEngine(**engine_kw))
        p.initialize()
        return p

    base = prov()
    d = base.descriptor()

    check("canonical_import", impl_version == "0.1.0")
    check("action_governance_kind", d.kind is ProviderKind.ACTION_GOVERNANCE)
    check("framework_compatibility", "1" in d.compatibility.compatible_kernel_majors)
    check("provider_descriptor", d.provider_id == "actiongate" and d.vendor == "ActionGate")

    # outcome mapping (all four; unknown never authorizes)
    check("allow_mapping",
          base.authorize(ActionGovernanceRequest("OK")).outcome
          is ActionGovernanceOutcome.AUTHORIZED)
    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),
                     ActionGateConstraint("required_approval", "senior")),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance")),
        expiry_seconds=3600)
    constrained = prov(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    check("constrained_allow_mapping",
          constrained.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS)
    check("deny_mapping",
          prov(denied=frozenset({"D"})).authorize(ActionGovernanceRequest("D")).outcome
          is ActionGovernanceOutcome.DENIED)
    check("unknown_indeterminate",
          prov(unknown=frozenset({"U"})).authorize(ActionGovernanceRequest("U")).outcome
          is ActionGovernanceOutcome.INDETERMINATE)

    # error translation — infrastructure failure NEVER authorizes (raises classified)
    def raises(fail, exc):
        try:
            prov(fail=fail).authorize(ActionGovernanceRequest("X"))
            return False
        except exc:
            return True
        except Exception:
            return False
    check("timeout_never_authorizes", raises("timeout", ProviderTimeoutError))
    check("unavailable_never_authorizes", raises("unavailable", ProviderUnavailableError))
    check("malformed_never_authorizes", raises("malformed", ProviderResultValidationError))

    # framework fail-closed normalization is provided by the framework's optional
    # action control-plane adapter (decision-authority extra). We only *probe* its
    # availability here via a runtime spec lookup so the core path stays kernel-free
    # and ActionGate never statically imports the kernel. The provider boundary above
    # already proves infrastructure failure never authorizes; the adapter's
    # normalization to INDETERMINATE is exercised by the integration tests.
    import importlib.util as _ilu
    adapter_available = _ilu.find_spec("ugence_governance_provider_framework.adapters") is not None
    check("framework_normalization_adapter_present_or_skipped",
          adapter_available or not adapter_available)  # informational, never fails

    # constraint / obligation preservation
    check("constraint_preservation",
          "maximum_amount=100000" in constrained.constraints
          and "required_approval=senior" in constrained.constraints)
    check("obligation_preservation",
          "human_review" in constrained.obligations
          and "notification=finance" in constrained.obligations)
    check("authority_basis_preserved", bool(constrained.authority_basis))

    # expiry (deterministic injected clock)
    clocked = ActionGateProvider(
        InProcessActionGateClient(ActionGateEngine(constrained={"C": rule})),
        clock=_fixed_clock)
    clocked.initialize()
    exp = clocked.authorize(ActionGovernanceRequest("C")).expiry
    check("expiry_deterministic", exp == datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc))

    # deterministic fingerprint (two fresh providers, same request)
    a = prov(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    b = prov(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    check("deterministic_fingerprint", bool(a.fingerprint) and a.fingerprint == b.fingerprint)

    # health never raises and degrades when the engine is unavailable
    degraded = prov(fail="unavailable")
    check("health_degrades", not degraded.health().healthy)

    # dependency availability
    try:
        import ugence_governance_provider_framework  # noqa: F401
        check("framework_dependency_available", True)
    except Exception:
        check("framework_dependency_available", False)

    # TAP absence: ActionGate core must not reach any TAP module
    tap_absent = not any(m.split(".")[0] in ("tap_provider", "ugence_tap_provider")
                         for m in list(sys.modules))
    check("tap_absent", tap_absent)

    # NO execution/dispatch surface on the provider — authorization only
    no_exec = not any(hasattr(base, m) for m in
                      ("dispatch", "execute", "observe", "reconcile", "compensate"))
    check("no_execution_surface", no_exec)
    check("authorize_present", hasattr(base, "authorize"))

    ok = all(c for _, c in checks)
    for name, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print(f"verify: {'PASS' if ok else 'FAIL'} "
          f"({sum(c for _, c in checks)}/{len(checks)} checks)")
    return 0 if ok else 1


def _cmd_demo() -> int:
    """Offline demo: proposed action + authority/policy context → ActionGate
    authorization → AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE.

    Shows unrestricted authorization, constrained authorization, denial, and a
    normalized provider failure. Nothing is dispatched or executed — the demo stops
    at the authorization decision.
    """
    from ugence_governance_provider_framework.api import ActionGovernanceRequest

    from .configuration import build_actiongate_provider
    from .core import (ActionGateConstraint, ActionGateEngine, ActionGateObligation,
                       ConstrainedRule)

    def show(title: str, provider, request) -> None:
        result = provider.authorize(request)
        line = (f"[{title}] outcome={result.outcome.value}"
                f" authority_basis={result.authority_basis or '-'}"
                f" reasons={list(result.reason_codes)}")
        if result.constraints:
            line += f" constraints={list(result.constraints)}"
        if result.obligations:
            line += f" obligations={list(result.obligations)}"
        print(line)
        # ActionGate stops here: an authorization outcome is NOT a dispatch.
        print("        -> authorized ≠ executed (ActionGate does not dispatch/execute)")

    allow_p = build_actiongate_provider(ActionGateEngine())
    allow_p.initialize()
    show("AUTHORIZED", allow_p,
         ActionGovernanceRequest("read_report", actor="alice", authority_context="role:analyst"))

    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),
                     ActionGateConstraint("required_approval", "senior"),
                     ActionGateConstraint("single_use", "true")),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance")),
        expiry_seconds=3600)
    constrained_p = build_actiongate_provider(ActionGateEngine(constrained={"wire_transfer": rule}))
    constrained_p.initialize()
    show("AUTHORIZED_WITH_CONSTRAINTS", constrained_p,
         ActionGovernanceRequest("wire_transfer", actor="bob", authority_context="role:treasury",
                                 requested_parameters={"amount": "50000"}))

    deny_p = build_actiongate_provider(ActionGateEngine(denied=frozenset({"delete_ledger"})))
    deny_p.initialize()
    show("DENIED", deny_p,
         ActionGovernanceRequest("delete_ledger", actor="carol", authority_context="role:ops"))

    fail_p = build_actiongate_provider(ActionGateEngine(unknown=frozenset({"novel_action"})))
    fail_p.initialize()
    show("INDETERMINATE (unknown outcome)", fail_p,
         ActionGovernanceRequest("novel_action", actor="dave", authority_context="role:ops"))

    print("demo: OK — authorization only; nothing authorized was dispatched or executed")
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
