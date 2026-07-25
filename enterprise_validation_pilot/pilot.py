"""Pilot orchestrator — runs the whole validation and assembles results.

Ties the deterministic stages together: manifest validation, per-scenario
workflow execution, evaluation against frozen ground truth, safety invariants,
failure injection, provider independence, and per-layer metrics. Produces a
``PilotResults`` object plus a substantive reproducibility digest that excludes
volatile runtime ids/timestamps (Task 115).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .composition.manifest import ManifestValidation, validate_manifest
from .evaluators.evaluate import ScenarioEvaluation, evaluate
from .evaluators.failure_injection import InjectionResult, run_failure_injection
from .evaluators.independence import (
    IndependenceResult, check_independence, isolation_violation_count)
from .evaluators.invariants import InvariantResult, check_invariants
from .metrics.compute import all_metrics
from .runners.workflow import ScenarioRun, run_scenario
from .schemas.dataset import Dataset


def _substantive(run: ScenarioRun) -> dict:
    return {
        "scenario_id": run.scenario_id,
        "tap_outcome": run.tap_outcome,
        "supported_components": sorted(run.supported_components),
        "unsupported_components": sorted(run.unsupported_components),
        "omitted_qualifiers": sorted(run.omitted_qualifiers),
        "evidence_coverage": run.evidence_coverage,
        "tap_failsafe": run.tap_failsafe,
        "recommendation_posture": run.recommendation_posture,
        "proceeded_to_action": run.proceeded_to_action,
        "actiongate_outcome": run.actiongate_outcome,
        "constraints": sorted(run.constraints),
        "obligations": sorted(run.obligations),
        "action_failsafe": run.action_failsafe,
        "enforcement_allowed": run.enforcement_allowed,
        "enforcement_violations": sorted(run.enforcement_violations),
        "dispatched": run.dispatched,
        "execution_behavior": run.execution_behavior,
        "business_outcome": run.business_outcome,
        "reconciliation": run.reconciliation,
        "obligation_states": sorted((o.obligation_type, o.value, o.state)
                                    for o in run.obligation_records),
        "compliance_verdict": run.compliance_verdict,
        "assertion_provider_id": run.assertion_provider_id,
        "assertion_selection_rule": run.assertion_selection_rule,
        "action_provider_id": run.action_provider_id,
        "action_selection_rule": run.action_selection_rule,
        "trace_complete": run.trace_complete,
        "error": run.error,
    }


@dataclass
class PilotResults:
    dataset_version: str
    dataset_hash: str
    manifest: ManifestValidation
    runs: list[ScenarioRun]
    evaluations: list[ScenarioEvaluation]
    invariants: list[InvariantResult]
    injections: list[InjectionResult]
    independence: list[IndependenceResult]
    metrics: dict
    substantive_digest: str
    pairs: list = field(default_factory=list)

    @property
    def scenarios_passed(self) -> int:
        return sum(1 for e in self.evaluations if e.passed)

    @property
    def all_scenarios_passed(self) -> bool:
        return all(e.passed for e in self.evaluations)

    @property
    def invariants_passed(self) -> bool:
        return all(r.passed for r in self.invariants)

    @property
    def failure_injection_passed(self) -> bool:
        return all(r.fail_safe for r in self.injections)

    @property
    def independence_passed(self) -> bool:
        return all(r.passed for r in self.independence)

    @property
    def manifest_valid(self) -> bool:
        return self.manifest.ok

    @property
    def overall_pass(self) -> bool:
        return (self.all_scenarios_passed and self.invariants_passed
                and self.failure_injection_passed and self.independence_passed
                and self.manifest_valid)


def run_pilot(dataset: Dataset) -> PilotResults:
    manifest = validate_manifest()
    scenarios = list(dataset.ordered())
    runs = [run_scenario(s) for s in scenarios]
    pairs = list(zip(scenarios, runs))
    evaluations = [evaluate(s, r) for s, r in pairs]
    invariants = check_invariants(pairs)
    injections = run_failure_injection()
    independence = check_independence()
    metrics = all_metrics(pairs, isolation_violations=isolation_violation_count(independence))

    substantive = [_substantive(r) for r in runs]
    digest = hashlib.sha256(
        json.dumps(substantive, sort_keys=True, default=str).encode()).hexdigest()

    return PilotResults(
        dataset_version=dataset.version, dataset_hash=dataset.content_hash,
        manifest=manifest, runs=runs, evaluations=evaluations, invariants=invariants,
        injections=injections, independence=independence, metrics=metrics,
        substantive_digest=digest, pairs=pairs)
