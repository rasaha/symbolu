"""ShadowRunner: capture predictions and observations independently, with accounting and
safety guards (Phases 12-13).

predict() uses ExecutionGate ONLY (no outcome knowledge). observe() uses an adapter and never
feeds back into prediction. The two are written to separate append-only logs and joined only
at analysis time (metrics.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from execution_gate.gate import ExecutionGate
from execution_gate.model import Candidate, Request
from execution_gate.states import EligibilityState
from execution_gate_shadow.adapters import ProviderAdapter
from execution_gate_shadow.config import SafetyError, ShadowConfig
from execution_gate_shadow.outcomes import ObservedOutcome, normalize
from execution_gate_shadow.records import (AppendOnlyLog, ObservationRecord, PredictionRecord)


@dataclass
class Accounting:
    spend_usd: float = 0.0
    requests: int = 0
    quota_calls: int = 0
    added_latency_ms: float = 0.0

    def charge(self, cfg: ShadowConfig, cost: float, latency: float, live: bool):
        if live:
            self.spend_usd += cost
            self.requests += 1
            self.quota_calls += 1
            if self.spend_usd > cfg.spend_cap_usd:
                raise SafetyError(f"spend cap exceeded (${self.spend_usd:.4f} > ${cfg.spend_cap_usd})")
            if self.requests > cfg.request_cap:
                raise SafetyError("request cap exceeded")
            if self.quota_calls > cfg.quota_cap:
                raise SafetyError("quota cap exceeded")
        self.added_latency_ms += latency
        if latency > cfg.max_added_latency_ms:
            raise SafetyError("added latency exceeds cap")


class ShadowRunner:
    def __init__(self, gate: ExecutionGate, config: ShadowConfig,
                 pred_log: AppendOnlyLog, obs_log: AppendOnlyLog):
        config.assert_runnable()
        self.gate = gate
        self.config = config
        self.pred_log = pred_log
        self.obs_log = obs_log
        self.acct = Accounting()

    def predict(self, request: Request, candidates: List[Candidate], now: float,
                registry_version: str = "shadow_reg_v1") -> Dict[str, PredictionRecord]:
        """Shadow prediction only — no outcome is consulted."""
        out = {}
        for cand in candidates:
            d = self.gate.evaluate(cand, request, now)
            evs = [c.evidence for c in d.conditions]
            rec = PredictionRecord(
                request_id=request.request_id, provider=cand.provider, model_id=cand.model_id,
                predicted_state=d.state.value, reason_codes=[r.value for r in d.reasons],
                evidence_sources=[e.source.value for e in evs],
                evidence_ages_s=[round(now - e.timestamp, 3) for e in evs],
                evidence_timestamps=[e.timestamp for e in evs],
                policy_version=d.policy_version, registry_version=registry_version, predicted_at=now)
            self.pred_log.append(rec)
            out[cand.model_id] = rec
        return out

    def observe(self, request: Request, cand: Candidate, adapter: ProviderAdapter,
                now: float, est_cost: float = 0.0) -> ObservationRecord:
        """Record an observation from normal routing / mock. Independent of prediction."""
        raw = adapter.observe(cand.model_id, {"request_id": request.request_id, "est_cost": est_cost})
        outcome = normalize(raw)
        latency = float(raw.get("latency_ms", 0.0))
        live = getattr(adapter, "is_live", False) and raw.get("attempted", False)
        self.acct.charge(self.config, est_cost if live else 0.0, latency, live)
        rec = ObservationRecord(
            request_id=request.request_id, provider=cand.provider, model_id=cand.model_id,
            outcome=outcome.value, attempted=bool(raw.get("attempted", False)),
            latency_ms=latency, est_cost_usd=(est_cost if live else 0.0), observed_at=now,
            source=("live" if live else "mock"))
        self.obs_log.append(rec)
        return rec
