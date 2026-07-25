"""Benchmark orchestrator — runs every strategy and assembles comparative results.

Deterministic: manifest/dataset identity → normal-mode grid + oracle judgements →
per-strategy metrics/cost/safety distribution → failure matrix → fairness,
invariants, paired analysis → a substantive digest over scored outcomes (volatile
ids/durations excluded).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field

from .cost.model import effectiveness, summarize
from .evaluators.fairness import check_fairness
from .evaluators.invariants import check_invariants
from .evaluators.oracle import judge
from .evaluators.paired import paired_analysis
from .failure_injection.matrix import run_matrix
from .metrics.compute import strategy_metrics
from .schemas.dataset import load_frozen_dataset, verify_identity
from .schemas.failure import FailureProfile, REQUIRED_PROFILES
from .strategies import STRATEGY_ORDER, build_strategy


def _substantive(result) -> dict:
    r = result
    def _t(v):
        return sorted(v) if isinstance(v, tuple) else v
    return {
        "scenario_id": r.scenario_id, "strategy_id": r.strategy_id,
        "assertion_outcome": r.assertion_outcome, "assertion_supported": r.assertion_supported,
        "qualifiers_preserved": _t(r.qualifiers_preserved),
        "unsupported_components_preserved": _t(r.unsupported_components_preserved),
        "evidence_provenance_preserved": r.evidence_provenance_preserved,
        "authorization_outcome": r.authorization_outcome,
        "constraints_issued": _t(r.constraints_issued), "constraints_enforced": r.constraints_enforced,
        "obligations_issued": _t(r.obligations_issued), "obligations_verified": r.obligations_verified,
        "dispatched": r.dispatched, "execution_outcome": r.execution_outcome,
        "reconciliation_outcome": r.reconciliation_outcome,
        "final_governance_compliance": r.final_governance_compliance,
        "human_review_requested": r.human_review_requested,
        "provider_failures": r.provider_failures, "cost": {k: r.cost[k] for k in sorted(r.cost)},
    }


@dataclass
class BenchmarkResults:
    dataset_identity: object
    grid: dict                       # strategy_id -> [(scenario, result)]
    judgements: dict                 # strategy_id -> [Judgement]
    metrics: dict                    # strategy_id -> metrics
    metrics_by_domain: dict          # strategy_id -> {domain -> metrics}
    cost: dict                       # strategy_id -> cost summary
    effectiveness: dict              # strategy_id -> effectiveness
    safety_distribution: dict        # strategy_id -> {safety_outcome -> count}
    safety_by_class: dict            # scenario_class -> {strategy_id -> {outcome->count}}
    failure_matrix: list
    fairness: list
    invariants: list
    paired: dict
    substantive_digest: str
    seed: int = 12345
    strategy_ids: tuple = field(default_factory=lambda: STRATEGY_ORDER)

    @property
    def fairness_passed(self):
        return all(c.passed for c in self.fairness)

    @property
    def invariants_passed(self):
        return all(r.passed for r in self.invariants)

    @property
    def overall_pass(self):
        return self.fairness_passed and self.invariants_passed and self.dataset_identity.ok


def _run_grid(dataset, strategies, strategy_ids):
    grid, judgements = {}, {}
    for sid in strategy_ids:
        pairs, judged = [], []
        for scenario in dataset.ordered():
            result = strategies[sid].run(scenario)
            pairs.append((scenario, result))
            judged.append(judge(scenario, result))
        grid[sid] = pairs
        judgements[sid] = judged
    return grid, judgements


def run_benchmark(dataset=None, *, strategy_ids=STRATEGY_ORDER,
                  profiles=REQUIRED_PROFILES, seed: int = 12345,
                  include_failures: bool = True) -> BenchmarkResults:
    # identity is always verified against the canonical frozen dataset; a --domains
    # subset changes only the *run scope*, never the frozen dataset itself.
    identity = verify_identity(load_frozen_dataset())
    dataset = dataset or load_frozen_dataset()
    strategies = {sid: build_strategy(sid) for sid in strategy_ids}

    grid, judgements = _run_grid(dataset, strategies, strategy_ids)

    metrics, metrics_by_domain, cost, safety_dist = {}, {}, {}, {}
    for sid in strategy_ids:
        triples = [(s, r, j) for (s, r), j in zip(grid[sid], judgements[sid])]
        metrics[sid] = strategy_metrics(triples)
        domains = sorted({s.domain for s, _r in grid[sid]})
        metrics_by_domain[sid] = {
            d: strategy_metrics([t for t in triples if t[0].domain == d]) for d in domains}
        cost[sid] = summarize([r for _s, r in grid[sid]], judgements[sid])
        safety_dist[sid] = dict(Counter(j.safety_outcome for j in judgements[sid]))

    # safety by scenario class (cross-provider class)
    classes = sorted({s.cross_class for s, _r in grid[strategy_ids[0]]})
    safety_by_class = {}
    for cls in classes:
        safety_by_class[cls] = {}
        for sid in strategy_ids:
            trip = [(s, r, j) for (s, r), j in zip(grid[sid], judgements[sid])
                    if s.cross_class == cls]
            safety_by_class[cls][sid] = dict(Counter(j.safety_outcome for _s, _r, j in trip))

    from .schemas.safety import UNSAFE_OUTCOMES
    baseline = "no_governance"
    eff = {}
    if baseline in strategy_ids:
        base_unsafe = sum(1 for j in judgements[baseline] if j.safety_outcome in UNSAFE_OUTCOMES)
        for sid in strategy_ids:
            s_unsafe = sum(1 for j in judgements[sid] if j.safety_outcome in UNSAFE_OUTCOMES)
            uns_contained = base_unsafe - s_unsafe
            hr = sum(1 for _s, r in grid[sid] if r.human_review_requested)
            eff[sid] = effectiveness(cost[sid], s_unsafe, cost[baseline], base_unsafe,
                                     max(0, uns_contained), hr)

    matrix = run_matrix(dataset, strategies, profiles) if include_failures else []
    fairness = check_fairness(grid)
    paired = paired_analysis(judgements, seed=seed)

    substantive = sorted(
        (_substantive(r) for pairs in grid.values() for _s, r in pairs),
        key=lambda d: (d["strategy_id"], d["scenario_id"]))
    payload = {"dataset": identity.content_hash, "results": substantive,
               "safety": safety_dist, "metrics": metrics}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def digest_fn():
        return digest

    invariants = check_invariants(grid, matrix, dataset, digest_fn)

    return BenchmarkResults(
        dataset_identity=identity, grid=grid, judgements=judgements, metrics=metrics,
        metrics_by_domain=metrics_by_domain, cost=cost, effectiveness=eff,
        safety_distribution=safety_dist, safety_by_class=safety_by_class,
        failure_matrix=matrix, fairness=fairness, invariants=invariants, paired=paired,
        substantive_digest=digest, seed=seed, strategy_ids=tuple(strategy_ids))
