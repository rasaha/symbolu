"""ModelPolicy — the downstream 'should execute?' selector.

Selects the preferred model ONLY from ExecutionGate-eligible candidates. It never
interprets raw provider errors (it consumes reason codes) and never selects an
ineligible model. Utility is a provider-neutral quality/cost/latency trade-off; this
is deliberately simple — the scientific selection engine is the frozen Model Selection
Policy, which this track does not modify.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .model import Request
from .registry import ModelRecord
from .states import EligibilityDecision, EligibilityState


@dataclass
class PolicyWeights:
    quality: float = 1.0
    cost: float = 0.5
    latency: float = 0.35
    conditional_penalty: float = 0.15   # rank CONDITIONALLY_ELIGIBLE below ELIGIBLE


@dataclass
class Selection:
    selected: Optional[ModelRecord]
    ranked: List[Tuple[ModelRecord, float]]
    abstained: bool
    reason: str


def _est_cost(rec: ModelRecord, req: Request) -> float:
    c = rec.candidate
    return (c.price_in_per_mtok * req.context_tokens + c.price_out_per_mtok * req.est_output_tokens) / 1e6


def select(selectable: List[Tuple[ModelRecord, EligibilityDecision]], req: Request,
           quality_of, weights: Optional[PolicyWeights] = None) -> Selection:
    """quality_of(rec) -> capability score in [0,1] (provider-neutral prior).

    INVARIANT: only ELIGIBLE / CONDITIONALLY_ELIGIBLE candidates are ever considered."""
    w = weights or PolicyWeights()
    pool = [(rec, dec) for rec, dec in selectable if dec.selectable]
    if not pool:
        return Selection(None, [], True, "no eligible candidate")
    costs = [_est_cost(r, req) for r, _ in pool] or [1.0]
    lats = [(r.observed_latency_ms or 1000.0) for r, _ in pool] or [1.0]
    cref, lref = max(costs) or 1e-9, max(lats) or 1e-9
    scored = []
    for rec, dec in pool:
        u = (w.quality * quality_of(rec)
             - w.cost * (_est_cost(rec, req) / cref)
             - w.latency * ((rec.observed_latency_ms or 1000.0) / lref))
        if dec.state == EligibilityState.CONDITIONALLY_ELIGIBLE:
            u -= w.conditional_penalty
        scored.append((rec, round(u, 4)))
    scored.sort(key=lambda x: (-x[1], x[0].internal_id))
    return Selection(scored[0][0], scored, False, "selected highest-utility eligible model")
