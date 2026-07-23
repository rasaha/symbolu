"""Routing baselines (Phase 7). Each returns an ordered attempt sequence of model_ids
(plus gate decisions where applicable). The harness simulates the sequence against ground
truth. Do not assume the gate wins.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from gate import ExecutionGate
from model import GateConfig
from policy import PolicyWeights, select as policy_select
from registry import ExecutableRegistry, ExecStatus, ModelRecord
from scenarios import Scenario, T0
from states import EligibilityDecision

STATIC_ALLOWLIST_PROVIDERS = {"anthropic", "google"}   # a plausible manual config


def _utility_order(scn: Scenario, model_ids: List[str]) -> List[str]:
    """Order by capability desc, then est cost asc, then id — the policy preference."""
    def key(mid):
        cand = next(c for c in scn.candidates if c.model_id == mid)
        q = scn.quality.get(mid, 0.5)
        cost = cand.price_in_per_mtok * scn.request.context_tokens / 1e6
        return (-q, cost, mid)
    return sorted(model_ids, key=key)


def _all_ids(scn): return [c.model_id for c in scn.candidates]


def _registry(scn: Scenario, cfg: Optional[GateConfig] = None) -> ExecutableRegistry:
    reg = ExecutableRegistry(ExecutionGate(cfg))
    for c in scn.candidates:
        reg.upsert(ModelRecord(c.model_id, c, ExecStatus.ENUMERATED,
                               observed_latency_ms=(c.signals.get("observed_latency_ms").value
                                                    if "observed_latency_ms" in c.signals else None)))
    return reg


def base_no_eligibility(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Static assumption: all available. Pick best by policy, NO retry (single attempt)."""
    return _utility_order(scn, _all_ids(scn))[:1], False, None


def base_retry_only(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Route by policy order; retry next on failure until success or exhausted."""
    return _utility_order(scn, _all_ids(scn)), False, None


def base_provider_health(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Exclude coarsely-unhealthy providers (degraded signal), then retry over the rest."""
    healthy = [c.model_id for c in scn.candidates
               if not (c.signals.get("degraded") and c.signals["degraded"].value is True)]
    return _utility_order(scn, healthy), (len(healthy) == 0), None


def base_static_allowlist(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Manual allowlist of providers; retry over allowlisted in policy order."""
    allowed = [c.model_id for c in scn.candidates if c.provider in STATIC_ALLOWLIST_PROVIDERS]
    return _utility_order(scn, allowed), (len(allowed) == 0), None


def _gate_eligible(scn: Scenario, cfg: Optional[GateConfig] = None
                   ) -> Tuple[List[Tuple[ModelRecord, EligibilityDecision]], Dict[str, EligibilityDecision]]:
    reg = _registry(scn, cfg)
    selectable, excluded = reg.evaluate(scn.request, T0)
    decisions = {rec.candidate.model_id: dec for rec, dec in selectable + excluded}
    return selectable, decisions


def base_execution_gate(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Eligibility filter, then attempt eligibles by cheapest-first (no policy optimization)."""
    selectable, decisions = _gate_eligible(scn)
    ids = [rec.candidate.model_id for rec, _ in selectable]
    ordered = sorted(ids, key=lambda m: next(c for c in scn.candidates if c.model_id == m).price_in_per_mtok)
    return ordered, (len(ids) == 0), decisions


def base_execution_gate_policy(scn: Scenario) -> Tuple[List[str], bool, Optional[Dict]]:
    """Eligibility filter, then ModelPolicy utility selection order among eligibles."""
    selectable, decisions = _gate_eligible(scn)
    sel = policy_select(selectable, scn.request, lambda rec: scn.quality.get(rec.candidate.model_id, 0.5),
                        PolicyWeights())
    if sel.abstained:
        return [], True, decisions
    ordered = [rec.internal_id for rec, _ in sel.ranked]
    return ordered, False, decisions


BASELINES = {
    "no_eligibility": base_no_eligibility,
    "retry_only": base_retry_only,
    "provider_health": base_provider_health,
    "static_allowlist": base_static_allowlist,
    "execution_gate": base_execution_gate,
    "execution_gate_policy": base_execution_gate_policy,
}

# per-eligibility-check overhead (ms) charged to gate baselines (probe/evaluate cost)
GATE_OVERHEAD_MS = {"execution_gate": 15.0, "execution_gate_policy": 18.0}
