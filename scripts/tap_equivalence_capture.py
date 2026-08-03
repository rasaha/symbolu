#!/usr/bin/env python3
"""Deterministic, network-free behavioral-equivalence capture for the TAP provider.

Captures the observable behavior of the TAP assertion-governance provider through
a chosen public import namespace (``tap_provider`` or ``ugence_tap_provider``) so
the pre-migration baseline can be compared byte-for-byte against the canonical and
legacy post-migration captures.

    python scripts/tap_equivalence_capture.py <namespace> <output.json>

``<namespace>`` defaults to ``tap_provider``; ``<output.json>`` defaults to
``docs/audits/tap_packaging/artifacts/tap_equivalence_<namespace>.json``.

Everything here is deterministic and offline: the reference TAP engine is a pure
function of request + policy, fingerprints are content hashes, and no network,
model SDK, credential, or clock is used. The capture exercises the descriptor,
request mapping, every result/outcome mapping, the full failure taxonomy in both
fail-safe modes, health/lifecycle, configuration validation (including secret
handling), and the observability record.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys


def _api(ns: str):
    return importlib.import_module(ns + ".api")


def _err(fn) -> str:
    try:
        fn()
        return "NO_ERROR"
    except Exception as exc:  # noqa: BLE001 - we are capturing the class name
        return type(exc).__name__


def capture(ns: str) -> dict:
    api = _api(ns)
    # Framework contract types live in the neutral framework API (shared by both
    # namespaces, identical objects), not TAP's own surface.
    fw = importlib.import_module("governance_providers.api")
    AssertionGovernanceRequest = fw.AssertionGovernanceRequest
    AssertionCoverage = fw.AssertionCoverage

    TapEngine = api.TapEngine
    TapRule = api.TapRule
    TapOutcome = api.TapOutcome
    TapConstraint = api.TapConstraint
    TapObligation = api.TapObligation
    build = api.build_tap_provider
    TapSettings = api.TapSettings
    TapInvocationLog = api.TapInvocationLog
    map_request = api.map_request
    translate_error = api.translate_error

    from importlib import import_module
    core = import_module(ns + ".core")

    out: dict = {"namespace": ns}

    # --- provider descriptor ------------------------------------------------
    prov = build(TapEngine())
    prov.initialize()
    d = prov.descriptor()
    out["descriptor"] = {
        "provider_id": d.provider_id,
        "kind": d.kind.value,
        "implementation_version": d.implementation_version,
        "vendor": d.vendor,
        "default": d.default,
        "features": sorted(d.capabilities.features),
        "deterministic": d.capabilities.deterministic,
        "contract_version": d.compatibility.contract_version,
        "compatible_kernel_majors": sorted(d.compatibility.compatible_kernel_majors),
        "config_schema_version": d.compatibility.config_schema_version,
        "metadata": {k: str(v) for k, v in sorted(d.metadata.items())},
    }

    # --- request mapping ----------------------------------------------------
    req = AssertionGovernanceRequest(
        assertion="Supplier X reduced costs", assertion_type="claim",
        evidence_refs=("e1", "e2"), source_identity="src",
        policy_refs=("p:1",), context={"k": "v"}, correlation_id="corr")
    native = map_request(req)
    out["request_mapping"] = {
        "assertion": native.assertion,
        "assertion_type": native.assertion_type,
        "evidence_ids": [e.evidence_id for e in native.evidence],
        "evidence_provenance": [e.provenance for e in native.evidence],
        "evidence_fingerprints_present": [bool(e.fingerprint) for e in native.evidence],
        "source_identity": native.source_identity,
        "policy_references": list(native.policy_references),
        "correlation_id": native.correlation_id,
        "trace_id": native.trace_id,
    }

    # --- result mapping across outcomes ------------------------------------
    def result_dict(r) -> dict:
        return {
            "coverage": r.coverage.value,
            "evidence_coverage": r.evidence_coverage,
            "covered_evidence_refs": list(r.covered_evidence_refs),
            "unsupported_elements": list(r.unsupported_elements),
            "omitted_qualifiers": list(r.omitted_qualifiers),
            "constraints": list(r.constraints),
            "obligations": list(r.obligations),
            "explanation_refs": sorted(r.explanation_refs),
            "provider_trace_id": r.provider_trace_id,
            "fingerprint": r.fingerprint,
        }

    supplier = "Supplier X reduced costs by 20% and has no compliance incidents"
    constrained_rule = TapRule(
        outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.6,
        supported_components=("cost_reduction",),
        unsupported_components=("magnitude_20pct",),
        omitted_qualifiers=("north_america_segment",),
        constraints=(TapConstraint("required_qualifier", "segment_scope"),
                     TapConstraint("maximum_confidence", "0.7")),
        obligations=(TapObligation("include_uncertainty_disclosure"),
                     TapObligation("retain_source_attribution")),
        reason_codes=("scope_expansion", "certainty_inflation"))
    unsupported_rule = TapRule(
        outcome=TapOutcome.UNSUPPORTED, evidence_coverage=0.0,
        unsupported_components=("no_compliance_incidents",),
        reason_codes=("contradicting_evidence",))

    def fresh(**kw):
        p = build(TapEngine(**kw))
        p.initialize()
        return p

    out["result_mapping"] = {
        "supported": result_dict(fresh().evaluate(
            AssertionGovernanceRequest("A", evidence_refs=("e1",)))),
        "indeterminate_no_evidence": result_dict(fresh().evaluate(
            AssertionGovernanceRequest("A", evidence_refs=()))),
        "unsupported": result_dict(fresh(rules={supplier: unsupported_rule}).evaluate(
            AssertionGovernanceRequest(supplier, evidence_refs=("e1",)))),
        "constrained": result_dict(fresh(rules={supplier: constrained_rule}).evaluate(
            AssertionGovernanceRequest(supplier, evidence_refs=("e1", "e2")))),
        "unknown_indeterminate": result_dict(fresh(emit_unknown=True).evaluate(
            AssertionGovernanceRequest("A", evidence_refs=("e1",)))),
    }

    # --- failure mapping (taxonomy + both fail-safe modes) -----------------
    natives = {
        "timeout": core.TapTimeout("t"),
        "unavailable": core.TapUnavailable("u"),
        "config": core.TapConfigError("c"),
        "malformed": core.TapMalformedResult("m"),
        "protocol": core.TapProtocolError("p"),
        "unexpected": ValueError("x"),
    }
    out["error_translation"] = {
        k: type(translate_error(v)).__name__ for k, v in sorted(natives.items())}

    failsafe = {}
    for mode in ("timeout", "unavailable", "config", "malformed", "protocol"):
        p = fresh(fail=mode)
        r = p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
        failsafe[mode] = {"coverage": r.coverage.value, "fingerprint": r.fingerprint,
                          "explanation_refs": sorted(r.explanation_refs)}
    out["failsafe_results"] = failsafe

    # fail-safe OFF: the classified provider error is raised
    raising = {}
    for mode in ("timeout", "unavailable", "config", "malformed", "protocol"):
        p = build(TapEngine(fail=mode), settings=TapSettings(fail_safe=False))
        p.initialize()
        raising[mode] = _err(
            lambda p=p: p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",))))
    out["failsafe_off_exceptions"] = raising

    # --- health & lifecycle -------------------------------------------------
    healthy = fresh()
    h_ok = healthy.health()
    degraded_p = fresh(fail="unavailable")
    h_deg = degraded_p.health()
    out["health"] = {
        "available_healthy": h_ok.healthy,
        "available_state": h_ok.state.value,
        "degraded_healthy": h_deg.healthy,
        "degraded_state": h_deg.state.value,
    }
    # lifecycle transitions on a fresh provider
    lc = build(TapEngine())
    states = [lc.health().state.value]
    lc.initialize()
    states.append(lc.health().state.value)
    lc.shutdown()
    states.append(lc.health().state.value)
    out["lifecycle_states"] = states

    # --- configuration ------------------------------------------------------
    out["configuration"] = {
        "valid_in_process": _err(lambda: TapSettings(mode="in_process").validate()),
        "valid_remote": _err(lambda: TapSettings(mode="remote").validate()),
        "invalid_mode": _err(lambda: TapSettings(mode="nope").validate()),
        "incompatible_contract": _err(lambda: TapSettings(contract_version="2.0.0").validate()),
        "invalid_evidence_resolution": _err(
            lambda: TapSettings(evidence_resolution="nope").validate()),
        "embedded_secret_rejected": _err(
            lambda: TapSettings(secret_refs={"k": "SECRET"}).validate()),
        "secret_reference_accepted": _err(
            lambda: TapSettings(secret_refs={"k": "ref:vault/k"}).validate()),
    }

    # --- observability ------------------------------------------------------
    log = TapInvocationLog()
    obs_p = build(TapEngine(), invocation_log=log)
    obs_p.initialize()
    obs_p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    # a failure record too
    obs_p.evaluate(AssertionGovernanceRequest("A", evidence_refs=()))
    fail_log = TapInvocationLog()
    fail_p = build(TapEngine(fail="timeout"), invocation_log=fail_log)
    fail_p.initialize()
    fail_p.evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    rec = log.all()[0]
    frec = fail_log.all()[0]
    out["observability_success"] = {
        "provider_id": rec.provider_id, "provider_version": rec.provider_version,
        "mapping_version": rec.mapping_version, "mode": rec.mode,
        "compatible": rec.compatible, "completed": rec.completed,
        "outcome": rec.outcome, "evidence_count": rec.evidence_count,
        "evidence_coverage": rec.evidence_coverage,
        "fingerprint_present": bool(rec.fingerprint),
        "error_class": rec.error_class, "failure_class": rec.failure_class,
    }
    out["observability_failure"] = {
        "completed": frec.completed, "outcome": frec.outcome,
        "error_class": frec.error_class, "failure_class": frec.failure_class,
        "evidence_count": frec.evidence_count,
    }
    return out


def main(argv: list[str]) -> int:
    ns = argv[1] if len(argv) > 1 else "tap_provider"
    default_out = (pathlib.Path("docs/audits/tap_packaging/artifacts")
                   / f"tap_equivalence_{ns}.json")
    out_path = pathlib.Path(argv[2]) if len(argv) > 2 else default_out
    data = capture(ns)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    import hashlib
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True).encode()).hexdigest()
    print(f"captured {ns} -> {out_path}")
    print(f"capture_sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
