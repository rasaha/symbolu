"""Deterministic, offline behavioral-equivalence capture for the ActionGate provider.

Runs the ActionGate action-governance provider through a fixed battery of
descriptor / request-mapping / result-mapping / native-outcome / error /
health-lifecycle / observability / repeated-request probes and emits a
deterministic JSON fingerprint. The SAME battery is run against multiple import
namespaces so the canonical package and the legacy compatibility facade can be
proven behaviorally identical:

    python scripts/actiongate_equivalence_capture.py ugence_actiongate_provider
    python scripts/actiongate_equivalence_capture.py actiongate_provider

No network, credentials, or model SDK are required — the capture uses the
in-process reference engine with an injected fixed clock so every field is a pure
function of the request and the configured policy. Nothing here authorizes,
dispatches, executes, or reconciles an action: ActionGate evaluates authorization
only, and this capture stops at the authorization outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import sys
from datetime import datetime, timezone


def _bootstrap_path() -> None:
    """Make the provider namespaces importable from a bare source checkout.

    Adds the repo root (legacy facade + ``governance_providers`` shim) and the
    canonical package ``src`` trees to ``sys.path`` so the capture runs without an
    editable install. A no-op when the packages are already importable (installed
    wheels).
    """
    here = pathlib.Path(__file__).resolve()
    repo = here.parents[1]
    candidates = [
        repo,
        repo / "packages" / "providers" / "actiongate" / "src",
        repo / "packages" / "providers" / "tap" / "src",
        repo / "packages" / "governance-provider-framework" / "src",
        repo / "packages" / "governance-contracts" / "src",
        repo / "packages" / "capabilities" / "decision-authority" / "src",
    ]
    for p in candidates:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


_bootstrap_path()


#: A fixed injected clock so expiry timestamps are deterministic across runs.
FIXED_NOW = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _fixed_clock() -> datetime:
    return FIXED_NOW


def _result_dict(result) -> dict:
    """Serialize a neutral ActionGovernanceResult deterministically."""
    expiry = result.expiry
    return {
        "outcome": result.outcome.value,
        "constraints": sorted(result.constraints),
        "obligations": sorted(result.obligations),
        "expiry": expiry.isoformat() if expiry is not None else None,
        "authority_basis": result.authority_basis,
        "reason_codes": list(result.reason_codes),
        "provider_trace_id": result.provider_trace_id,
        "fingerprint": result.fingerprint,
    }


def capture(namespace: str) -> dict:
    api = importlib.import_module(f"{namespace}.api")
    mapping = importlib.import_module(f"{namespace}.mapping")
    fw = importlib.import_module("governance_providers.api")

    ActionGovernanceRequest = fw.ActionGovernanceRequest
    ActionGovernanceOutcome = fw.ActionGovernanceOutcome
    ProviderTimeoutError = fw.ProviderTimeoutError
    ProviderUnavailableError = fw.ProviderUnavailableError
    ProviderResultValidationError = fw.ProviderResultValidationError
    ProviderConfigurationError = fw.ProviderConfigurationError

    ActionGateEngine = api.ActionGateEngine
    ActionGateConstraint = api.ActionGateConstraint
    ActionGateObligation = api.ActionGateObligation
    ConstrainedRule = api.ConstrainedRule
    build = api.build_actiongate_provider
    ActionGateInvocationLog = api.ActionGateInvocationLog
    ActionGateProvider = api.ActionGateProvider
    InProcessActionGateClient = api.InProcessActionGateClient

    def build_clocked(engine, *, invocation_log=None):
        """Provider with the fixed injected clock for deterministic expiry."""
        return ActionGateProvider(InProcessActionGateClient(engine), clock=_fixed_clock,
                                  invocation_log=invocation_log)

    out: dict = {"namespace": namespace}

    # --- descriptor -------------------------------------------------------
    prov = build(ActionGateEngine())
    prov.initialize()
    d = prov.descriptor()
    out["descriptor"] = {
        "provider_id": d.provider_id,
        "kind": d.kind.value,
        "implementation_version": d.implementation_version,
        "compatible_kernel_majors": sorted(d.compatibility.compatible_kernel_majors),
        "contract_version": d.compatibility.contract_version,
        "features": sorted(d.capabilities.features),
        "deterministic": d.capabilities.deterministic,
        "vendor": d.vendor,
        "default": d.default,
        "mode": d.metadata.get("mode", ""),
    }
    out["version"] = {
        "__version__": api.__version__,
        "contract_version": api.CONTRACT_VERSION,
        "mapping_version": api.MAPPING_VERSION,
    }

    # --- request mapping (all neutral fields) ------------------------------
    native = mapping.map_request(ActionGovernanceRequest(
        action_type="ACT", requested_parameters={"k": "v", "amount": "10"}, actor="u",
        authority_context="auth-ctx", target_resource="res:1", policy_refs=("p:1", "p:2"),
        risk_context={"score": "low"}, evidence_refs=("e1", "e2"), decision_refs=("d1",),
        idempotency_key="idem-key", correlation_id="corr-id"))
    out["request_mapping"] = {
        "action_type": native.action_type,
        "parameters": dict(native.parameters),
        "principal": native.principal,
        "authority": native.authority,
        "resource": native.resource,
        "policy_context": list(native.policy_context),
        "risk_context": dict(native.risk_context),
        "evidence_refs": list(native.evidence_refs),
        "decision_refs": list(native.decision_refs),
        "tenant": native.tenant,  # intentionally lossy (documented)
        "correlation_id": native.correlation_id,
        "idempotency_key": native.idempotency_key,
    }

    # --- native outcomes → neutral results (fixed clock) -------------------
    def authorize(engine_kw, request):
        p = build_clocked(ActionGateEngine(**engine_kw))
        p.initialize()
        return p.authorize(request)

    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),
                     ActionGateConstraint("required_approval", "senior"),
                     ActionGateConstraint("ext_custom", "x")),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance"),
                     ActionGateObligation("ext_obl", "y")),
        expiry_seconds=3600)

    out["result_allow"] = _result_dict(authorize({}, ActionGovernanceRequest("OK")))
    out["result_constrained"] = _result_dict(
        authorize({"constrained": {"C": rule}}, ActionGovernanceRequest("C")))
    out["result_denied"] = _result_dict(
        authorize({"denied": frozenset({"D"})}, ActionGovernanceRequest("D")))
    out["result_unknown"] = _result_dict(
        authorize({"unknown": frozenset({"U"})}, ActionGovernanceRequest("U")))

    # zero / negative expiry (documented live semantics)
    out["result_zero_expiry"] = _result_dict(authorize(
        {"constrained": {"Z": ConstrainedRule(constraints=(), obligations=(), expiry_seconds=0)}},
        ActionGovernanceRequest("Z")))
    out["result_negative_expiry"] = _result_dict(authorize(
        {"constrained": {"N": ConstrainedRule(constraints=(), obligations=(), expiry_seconds=-60)}},
        ActionGovernanceRequest("N")))

    # --- errors (native failure → classified provider error) ---------------
    def error_class(fail):
        p = build(ActionGateEngine(fail=fail))
        p.initialize()
        try:
            p.authorize(ActionGovernanceRequest("X"))
            return "NO_ERROR"
        except Exception as exc:  # noqa: BLE001
            return type(exc).__name__

    out["errors"] = {
        "timeout": error_class("timeout"),
        "unavailable": error_class("unavailable"),
        "malformed": error_class("malformed"),
        "config": error_class("config"),
    }

    # invalid configuration
    try:
        api.ActionGateSettings(mode="bogus").validate()
        out["errors"]["invalid_config"] = "NO_ERROR"
    except Exception as exc:  # noqa: BLE001
        out["errors"]["invalid_config"] = type(exc).__name__

    # --- health & lifecycle ------------------------------------------------
    healthy = build(ActionGateEngine())
    healthy.initialize()
    degraded = build(ActionGateEngine(fail="unavailable"))
    degraded.initialize()
    out["health"] = {
        "healthy_ok": healthy.health().healthy,
        "degraded_healthy": degraded.health().healthy,
        "degraded_state": degraded.health().state.value,
    }
    lifecycle = build(ActionGateEngine())
    states = [lifecycle.health().state.value]
    lifecycle.initialize()
    states.append(lifecycle.health().state.value)
    out["lifecycle_states"] = states

    # --- observability -----------------------------------------------------
    log = ActionGateInvocationLog()
    obs = build(ActionGateEngine(constrained={"C": rule}), invocation_log=log)
    obs.initialize()
    obs.authorize(ActionGovernanceRequest("C"))
    failing = build(ActionGateEngine(fail="timeout"), invocation_log=log)
    failing.initialize()
    try:
        failing.authorize(ActionGovernanceRequest("X"))
    except Exception:  # noqa: BLE001
        pass
    records = log.all()
    out["observability"] = [
        {"completed": r.completed, "outcome": r.outcome, "mapping_version": r.mapping_version,
         "mode": r.mode, "compatible": r.compatible, "policy_version": r.policy_version,
         "error_class": r.error_class, "failure_class": r.failure_class,
         "has_trace": bool(r.trace_id)}
        for r in records]

    # --- repeated-request determinism (same clock, same request) ----------
    prov_rep = build_clocked(ActionGateEngine(constrained={"C": rule}))
    prov_rep.initialize()
    a = prov_rep.authorize(ActionGovernanceRequest("C", idempotency_key="idem"))
    b = prov_rep.authorize(ActionGovernanceRequest("C", idempotency_key="idem"))
    out["repeated_request"] = {
        "fingerprint_stable": a.fingerprint == b.fingerprint,
        "outcome_stable": a.outcome is b.outcome,
        "fingerprint": a.fingerprint,
    }

    return out


def capture_hash(payload: dict) -> str:
    # Exclude the top-level namespace label so cross-namespace captures compare equal.
    body = {k: v for k, v in payload.items() if k != "namespace"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("namespace", nargs="?", default="ugence_actiongate_provider")
    parser.add_argument("--out", default=None, help="write JSON capture to this path")
    args = parser.parse_args(argv)

    payload = capture(args.namespace)
    payload["capture_hash"] = capture_hash(payload)
    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
    print(text)
    print(f"capture_hash({args.namespace}) = {payload['capture_hash']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
