"""Canonical Model Selection package tests — public API surface + minimal deterministic
eligibility/selection workflow. These exercise the package through ``ugence_model_selection``
directly (not the legacy ``execution_gate`` compatibility surface), so they hold on a
canonical-wheel-only install. Behavior parity with the legacy surface is proven separately
by the equivalence harness and by ``execution_gate``'s own suite (run through the shim)."""
from __future__ import annotations

import ugence_model_selection as ms
from ugence_model_selection import api
from ugence_model_selection.api import (
    Candidate,
    EligibilityState,
    Evidence,
    EvidenceSource,
    ExecutableRegistry,
    ExecutionGate,
    ModelRecord,
    PolicyWeights,
    ReasonCode,
    Request,
    Signal,
    fingerprint,
    select,
)

NOW = 1000.0


def _ev(ttl: float = 3600.0) -> Evidence:
    return Evidence(EvidenceSource.LIVE_PROBE, NOW, 1.0, ttl_seconds=ttl)


def _fresh_candidate(provider: str = "anthropic", region: str = "us", latency: float = 500.0) -> Candidate:
    return Candidate(
        provider, f"{provider}-model", provider, region=region, context_limit=200000,
        structured_output=True, tool_use=True, price_in_per_mtok=3.0, price_out_per_mtok=15.0,
        signals={
            "reachable": Signal(True, _ev()), "authenticated": Signal(True, _ev()),
            "network_allowed": Signal(True, _ev()), "model_available": Signal(True, _ev()),
            "billing_active": Signal(True, _ev()), "quota_state": Signal("ok", _ev()),
            "observed_latency_ms": Signal(latency, _ev()), "reliability": Signal(0.99, _ev()),
            "credential_expiry_ts": Signal(NOW + 100000, _ev()),
        },
    )


def test_version_and_policy_version():
    assert ms.__version__ == "0.1.0"
    assert api.POLICY_VERSION == "exec_gate_v1"  # preserved from the legacy default


def test_public_api_surface_complete():
    for name in api.__all__:
        assert hasattr(api, name), f"api missing {name}"


def test_minimal_eligible_and_selected():
    req = Request("r1", context_tokens=1000, approved_providers={"anthropic"})
    gate = ExecutionGate()
    dec = gate.evaluate(_fresh_candidate(), req, NOW)
    assert dec.state is EligibilityState.ELIGIBLE
    reg = ExecutableRegistry(gate)
    reg.upsert(ModelRecord("m1", _fresh_candidate(), observed_latency_ms=500.0))
    selectable, excluded = reg.evaluate(req, NOW)
    sel = select(selectable, req, quality_of=lambda rec: 0.9)
    assert sel.selected is not None and sel.selected.internal_id == "m1"
    assert sel.abstained is False


def test_unapproved_provider_is_ineligible_fail_closed():
    req = Request("r2", context_tokens=1000, approved_providers={"only_this"})
    dec = ExecutionGate().evaluate(_fresh_candidate(provider="anthropic"), req, NOW)
    assert dec.state is EligibilityState.INELIGIBLE
    assert ReasonCode.PROVIDER_NOT_APPROVED in dec.reasons


def test_no_eligible_model_abstains():
    req = Request("r3", context_tokens=1000, approved_providers={"nobody"})
    gate = ExecutionGate()
    reg = ExecutableRegistry(gate)
    reg.upsert(ModelRecord("m1", _fresh_candidate(), observed_latency_ms=500.0))
    selectable, _ = reg.evaluate(req, NOW)
    sel = select(selectable, req, quality_of=lambda rec: 0.9)
    assert sel.selected is None and sel.abstained is True


def test_ineligible_never_selected_despite_high_quality():
    # An ineligible candidate must never win on a higher aggregate score.
    req = Request("r4", context_tokens=1000, approved_providers={"anthropic"})
    gate = ExecutionGate()
    reg = ExecutableRegistry(gate)
    reg.upsert(ModelRecord("ok", _fresh_candidate(provider="anthropic"), observed_latency_ms=500.0))
    reg.upsert(ModelRecord("bad", _fresh_candidate(provider="unapproved"), observed_latency_ms=10.0))
    selectable, _ = reg.evaluate(req, NOW)
    # 'bad' would score highest (lowest latency) but is ineligible → not selectable.
    sel = select(selectable, req, quality_of=lambda rec: 1.0 if rec.internal_id == "bad" else 0.5)
    assert sel.selected is not None and sel.selected.internal_id == "ok"


def test_fingerprint_is_deterministic():
    req = Request("r5", context_tokens=1000, approved_providers={"anthropic"})
    dec = ExecutionGate().evaluate(_fresh_candidate(), req, NOW)
    assert fingerprint(dec.to_dict()) == fingerprint(dec.to_dict())
