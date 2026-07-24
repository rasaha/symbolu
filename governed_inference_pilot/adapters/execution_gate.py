"""ExecutionGate adapter (read-only). Constructs a fully-signalled Candidate for eligible registry
entries (all signals fresh/pass) or a failed critical signal for ineligible ones, then calls the FROZEN
ExecutionGate.evaluate."""
from __future__ import annotations

from typing import Any, Dict, List

from execution_gate.gate import (ExecutionGate, Candidate, Request, Signal, Evidence, EvidenceSource,
                                  EligibilityState)
from .base import AdapterResult

_STAGE = "execution_gate"
_SIGNALS_TRUE = {"reachable": True, "authenticated": True, "network_allowed": True,
                 "model_available": True, "billing_active": True, "degraded": False,
                 "quota_state": "ok", "reliability": 0.99, "observed_latency_ms": 100.0,
                 "credential_expiry_ts": 1e12}


def _ev(now=0.0):
    return Evidence(source=EvidenceSource.CONFIG, timestamp=now, confidence=1.0, ttl_seconds=1e9)


def _candidate(entry: Dict[str, Any], eligible: bool) -> Candidate:
    sigs = {}
    for k, v in _SIGNALS_TRUE.items():
        if not eligible and k == "reachable":
            sigs[k] = Signal(value=False, evidence=_ev(), reason_hint="DNS_FAILURE")
        else:
            sigs[k] = Signal(value=v, evidence=_ev())
    return Candidate(provider=entry["provider"], model_id=entry["model_id"], family=entry["family"],
                     signals=sigs)


def run(registry: List[Dict[str, Any]], request: Dict[str, Any]) -> AdapterResult:
    eg = ExecutionGate()
    req = Request(request_id=request.get("request_id", "r"))
    eligible_models, states = [], {}
    for entry in registry:
        cand = _candidate(entry, entry.get("eligible", True))
        dec = eg.evaluate(cand, req, 0.0)
        states[entry["model_id"]] = dec.state.value if hasattr(dec.state, "value") else str(dec.state)
        if dec.state == EligibilityState.ELIGIBLE:
            eligible_models.append(entry["model_id"])
    any_eligible = bool(eligible_models)
    local = "ELIGIBLE" if any_eligible else "INELIGIBLE"
    return AdapterResult(
        stage=_STAGE, component_version="exec_gate_v1", local_disposition=local,
        reason_codes=["EXEC.ELIGIBLE" if any_eligible else "EXEC.NONE_ELIGIBLE"],
        source_repr={"states": states},
        transformed_repr={"eligible_models": eligible_models},
        extra={"eligible_models": eligible_models})
