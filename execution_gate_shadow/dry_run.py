"""Mock-only dry run (Phase 15): 8 scenarios exercising the shadow pipeline end to end.

Implementation validation only — NOT live scientific evidence. No credentials, no network.
Produces: shadow audit logs (prediction + observation JSONL), normalized outcomes, a metric
report, a spend/quota report, a manifest, and a dry-run report.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Tuple

from execution_gate.gate import ExecutionGate
from execution_gate.model import Candidate, Request, Signal
from execution_gate.states import Evidence, EvidenceSource
from execution_gate_shadow.adapters import MockProviderAdapter
from execution_gate_shadow.config import ShadowConfig
from execution_gate_shadow.metrics import compute
from execution_gate_shadow.records import AppendOnlyLog

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
T0 = 2_000_000.0


def _sig(value, source=EvidenceSource.LIVE_PROBE, age=0.0, ttl=900.0, reason=None):
    return Signal(value, Evidence(source, T0 - age, 0.95, ttl), reason_hint=reason)


def _healthy(**over):
    s = dict(reachable=_sig(True), network_allowed=_sig(True), authenticated=_sig(True),
             credential_expiry_ts=_sig(T0 + 1e9), billing_active=_sig(True), quota_state=_sig("ok"),
             model_available=_sig(True), observed_latency_ms=_sig(800.0), reliability=_sig(0.99),
             degraded=_sig(False))
    s.update(over)
    return s


def _cand(provider, model_id, family, signals, region="global", approved=True):
    return Candidate(provider, model_id, family, family, region, 200000, True, True, 1.0, 4.0, signals)


def scenarios() -> List[Tuple[str, Request, List[Candidate], Dict[str, dict]]]:
    S = []
    # 1 healthy
    S.append(("healthy", Request("r1"), [_cand("anthropic", "m_ok", "claude", _healthy())],
              {"m_ok": {"attempted": True, "http": 200, "text_valid": True, "policy_permitted": True, "latency_ms": 800}}))
    # 2 network denial
    S.append(("network_denial", Request("r2"),
              [_cand("mistral", "m_net", "mistral", _healthy(network_allowed=_sig(False, reason="NETWORK_BLOCKED")))],
              {"m_net": {"attempted": True, "http": None, "error_kind": "NETWORK_FAILURE", "latency_ms": 120}}))
    # 3 quota exhaustion
    S.append(("quota_exhaustion", Request("r3"),
              [_cand("google", "m_quota", "gemini", _healthy(quota_state=_sig("exhausted")))],
              {"m_quota": {"attempted": True, "http": 429, "latency_ms": 120}}))
    # 4 provider degradation (works but excluded -> false-ineligible)
    S.append(("degradation", Request("r4"),
              [_cand("anthropic", "m_deg", "claude", _healthy(degraded=_sig(True)))],
              {"m_deg": {"attempted": True, "http": 200, "text_valid": True, "policy_permitted": True, "latency_ms": 1500}}))
    # 5 recovery: stale cache says down, actually recovered -> indeterminate -> false-ineligible
    S.append(("recovery_stale", Request("r5"),
              [_cand("google", "m_rec", "gemini",
                     _healthy(billing_active=_sig(False, source=EvidenceSource.CACHE, age=7200, ttl=900),
                              quota_state=_sig("exhausted", source=EvidenceSource.CACHE, age=7200, ttl=900)))],
              {"m_rec": {"attempted": True, "http": 200, "text_valid": True, "policy_permitted": True, "latency_ms": 650}}))
    # 6 policy-prohibited but technically successful -> gate excludes -> TN, zero critical FE
    req6 = Request("r6", approved_providers={"anthropic", "google"})
    S.append(("policy_prohibited_success", req6,
              [_cand("unapproved_vendor", "m_bad", "vendorx", _healthy())],
              {"m_bad": {"attempted": True, "http": 200, "text_valid": True, "policy_permitted": False,
                         "critical_kind": "POLICY_PROHIBITED", "latency_ms": 400}}))
    # 7 stale evidence false-eligible risk: stale cache says ok, actually 429 -> gate INDETERMINATE
    S.append(("stale_false_eligible_risk", Request("r7"),
              [_cand("google", "m_stale", "gemini",
                     _healthy(billing_active=_sig(True, source=EvidenceSource.CACHE, age=7200, ttl=900)))],
              {"m_stale": {"attempted": True, "http": 429, "latency_ms": 120}}))
    # 8 no eligible candidate (fail fast; not attempted)
    S.append(("no_eligible", Request("r8"),
              [_cand("mistral", "m_none", "mistral", _healthy(network_allowed=_sig(False, reason="NETWORK_BLOCKED")))],
              {"m_none": {"attempted": False}}))
    return S


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def run(creation_timestamp: str = "2026-07-23T00:00:00Z") -> Dict:
    os.makedirs(RESULTS, exist_ok=True)
    pred_path = os.path.join(RESULTS, "shadow_predictions.jsonl")
    obs_path = os.path.join(RESULTS, "shadow_observations.jsonl")
    for p in (pred_path, obs_path):
        if os.path.exists(p):
            os.remove(p)   # fresh deterministic run
    cfg = ShadowConfig(live_calls_enabled=False, protocol_version="live_shadow_pilot_v1")
    gate = ExecutionGate()
    from execution_gate_shadow.runner import ShadowRunner
    pred_log, obs_log = AppendOnlyLog(pred_path), AppendOnlyLog(obs_path)
    runner = ShadowRunner(gate, cfg, pred_log, obs_log)

    scns = scenarios()
    for name, req, cands, gt in scns:
        adapter = MockProviderAdapter(cands[0].provider if cands else "mock", gt)
        runner.predict(req, cands, T0)
        # Observation reflects the TRUE outcome that normal routing / controlled validation
        # would produce for each candidate (the ground truth), captured INDEPENDENTLY of the
        # prediction. Scenario 8 carries attempted:False (genuinely NOT_ATTEMPTED).
        for cand in cands:
            adp = MockProviderAdapter(cand.provider, gt)
            runner.observe(req, cand, adp, T0)

    predictions = pred_log.read_all()
    observations = obs_log.read_all()
    report = compute(predictions, observations)

    manifest = {
        "artifact": "live_shadow_dry_run", "mode": "MOCK_ONLY",
        "protocol_version": cfg.protocol_version, "creation_timestamp": creation_timestamp,
        "live_calls_enabled": cfg.live_calls_enabled, "scenario_count": len(scns),
        "prediction_count": len(predictions), "observation_count": len(observations),
        "spend_usd": runner.acct.spend_usd, "live_requests": runner.acct.requests,
        "quota_calls": runner.acct.quota_calls,
        "prediction_log_sha256": _sha(pred_path), "observation_log_sha256": _sha(obs_path),
        "metrics": report,
        "note": "Mock-only implementation validation; NOT live scientific evidence.",
    }
    json.dump(manifest, open(os.path.join(RESULTS, "dry_run_manifest.json"), "w"),
              indent=2, sort_keys=True)
    open(os.path.join(RESULTS, "dry_run_manifest.json"), "a").write("\n")
    return manifest


if __name__ == "__main__":
    m = run()
    print(json.dumps(m["metrics"], indent=2, sort_keys=True))
    print("spend:", m["spend_usd"], "live_requests:", m["live_requests"], "scenarios:", m["scenario_count"])
