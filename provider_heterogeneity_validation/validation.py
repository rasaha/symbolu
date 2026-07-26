"""Heterogeneity validation orchestrator.

Runs all six configurations across all 90 frozen scenarios (normal mode) plus the
required failure profiles across a deterministic representative scenario subset,
then computes resolution/governance/provider metrics, the cost/benefit frontier,
invariants, a configuration comparison, and a stable substantive digest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset, verify_identity

from .evaluators.frontier import frontier_by_class
from .evaluators.invariants import check_invariants
from .failure_injection.profiles import FailureProfile, REQUIRED_PROFILES, kind_of
from .metrics.compute import governance_metrics, provider_metrics, resolution_metrics
from .schemas.config import CONFIGURATIONS, CONFIG_ORDER
from .runners.workflow import run

#: deterministic representative subset for the failure matrix (fast + covers classes)
_FAILURE_SUBSET = tuple(
    f"{d}-{i:03d}" for d in ("procurement", "finance_operations", "refund_operations")
    for i in (1, 3, 6, 13, 17))


def _unsafe(r) -> bool:
    from comparative_governance_benchmark.evaluators.expectation import derive
    exp = derive(load_frozen_dataset().by_id(r.scenario_id))
    return (r.dispatched and not exp.should_dispatch
            and not exp.failing_component and not exp.is_execution_failure)


def _substantive(r) -> dict:
    return {
        "scenario_id": r.scenario_id, "configuration_id": r.configuration_id,
        "assertion_provider": r.assertion_provider_id, "assertion_outcome": r.assertion_outcome,
        "assertion_fallback": r.assertion_fallback_used,
        "no_valid_assertion": r.no_valid_assertion_provider,
        "action_provider": r.action_provider_id, "authorization_outcome": r.authorization_outcome,
        "action_fallback": r.action_fallback_used, "no_valid_action": r.no_valid_action_provider,
        "constraints": sorted(r.constraints), "obligations": sorted(r.obligations),
        "dispatched": r.dispatched, "execution_outcome": r.execution_outcome,
        "reconciliation": r.reconciliation_outcome, "compliance": r.final_governance_compliance,
        "assertion_fingerprint": r.assertion_selection.resolution_fingerprint if r.assertion_selection else "",
        "action_fingerprint": r.action_selection.resolution_fingerprint if r.action_selection else "",
    }


@dataclass
class FailureCell:
    configuration_id: str
    profile: str
    applicable: bool
    scenarios: int
    fail_safe: int
    unsafe: int
    fallbacks: int
    no_valid_provider: int


@dataclass
class ValidationResults:
    dataset_identity: object
    grid: dict                       # config_id -> {scenario_id -> HeteroResult}
    resolution: dict                 # config_id -> resolution metrics
    governance: dict                 # config_id -> governance metrics
    providers: dict                  # global provider metrics
    frontier: dict
    configuration_comparison: dict
    failure_matrix: list
    invariants: list
    selection_records: list
    substantive_digest: str
    config_order: tuple = field(default_factory=lambda: CONFIG_ORDER)

    @property
    def invariants_passed(self):
        return all(i.passed for i in self.invariants)

    @property
    def overall_pass(self):
        return self.invariants_passed and self.dataset_identity.ok


def _config_applies(profile: FailureProfile, config) -> bool:
    if profile is FailureProfile.NORMAL:
        return True
    if profile.value in ("REGISTRY_DUPLICATE_ID", "NO_COMPATIBLE_PROVIDER", "NO_CAPABILITY_MATCH"):
        return True
    kind = kind_of(profile)
    target = {"tap-primary", "baseline-assertion"} if kind == "ASSERTION_GOVERNANCE" \
        else {"actiongate-primary", "baseline-action"}
    members = set(config.assertion_providers) | set(config.action_providers)
    return bool(target & members)


def run_validation(dataset=None, *, config_ids=CONFIG_ORDER,
                   profiles=REQUIRED_PROFILES, failure_subset=_FAILURE_SUBSET) -> ValidationResults:
    identity = verify_identity(load_frozen_dataset())
    dataset = dataset or load_frozen_dataset()
    scenarios = list(dataset.ordered())

    grid: dict = {}
    for cid in config_ids:
        grid[cid] = {s.scenario_id: run(s, CONFIGURATIONS[cid]) for s in scenarios}

    flat = [r for cid in config_ids for r in grid[cid].values()]
    resolution = {cid: resolution_metrics(list(grid[cid].values())) for cid in config_ids}
    governance = {cid: governance_metrics(list(grid[cid].values())) for cid in config_ids}
    providers = provider_metrics(flat)
    frontier = frontier_by_class(grid, dataset)

    comparison = {}
    for cid in config_ids:
        rs = list(grid[cid].values())
        comparison[cid] = {
            "description": CONFIGURATIONS[cid].description,
            "unsafe_outcomes": sum(1 for r in rs if _unsafe(r)),
            "dispatched": sum(1 for r in rs if r.dispatched),
            "false_blocks": sum(1 for r in rs if not r.dispatched
                                and _dispatch_expected(r) and not r.no_valid_assertion_provider),
            "assertion_fallbacks": sum(1 for r in rs if r.assertion_fallback_used),
            "action_fallbacks": sum(1 for r in rs if r.action_fallback_used),
            "no_valid_provider": sum(1 for r in rs
                                     if r.no_valid_assertion_provider or r.no_valid_action_provider),
        }

    # failure matrix over the representative subset
    subset = [dataset.by_id(sid) for sid in failure_subset]
    failure_matrix, failure_flat = [], []
    for profile in profiles:
        if profile is FailureProfile.NORMAL:
            continue
        for cid in config_ids:
            cfg = CONFIGURATIONS[cid]
            if not _config_applies(profile, cfg):
                failure_matrix.append(FailureCell(cid, profile.value, False, 0, 0, 0, 0, 0))
                continue
            rs = [run(s, cfg, profile) for s in subset]
            failure_flat.extend(rs)
            failure_matrix.append(FailureCell(
                cid, profile.value, True, len(rs),
                sum(1 for r in rs if not _unsafe(r)), sum(1 for r in rs if _unsafe(r)),
                sum(1 for r in rs if r.assertion_fallback_used or r.action_fallback_used),
                sum(1 for r in rs if r.no_valid_assertion_provider or r.no_valid_action_provider)))

    invariants = check_invariants(flat + failure_flat)

    # sample of selection records (deterministic, first per config)
    selection_records = []
    for cid in config_ids:
        r = grid[cid][scenarios[0].scenario_id]
        if r.assertion_selection:
            selection_records.append(_record_dict(r.assertion_selection))
        if r.action_selection:
            selection_records.append(_record_dict(r.action_selection))

    substantive = sorted((_substantive(r) for r in flat),
                         key=lambda d: (d["configuration_id"], d["scenario_id"]))
    payload = {"dataset": identity.content_hash, "results": substantive,
               "resolution": resolution, "governance": governance}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    return ValidationResults(
        dataset_identity=identity, grid=grid, resolution=resolution, governance=governance,
        providers=providers, frontier=frontier, configuration_comparison=comparison,
        failure_matrix=failure_matrix, invariants=invariants,
        selection_records=selection_records, substantive_digest=digest,
        config_order=tuple(config_ids))


def _dispatch_expected(r) -> bool:
    from comparative_governance_benchmark.evaluators.expectation import derive
    exp = derive(load_frozen_dataset().by_id(r.scenario_id))
    return exp.should_dispatch and not exp.failing_component


def _record_dict(rec) -> dict:
    return {
        "request_id": rec.request_id, "provider_kind": rec.provider_kind,
        "resolution_policy": rec.resolution_policy,
        "candidate_provider_ids": list(rec.candidate_provider_ids),
        "candidate_versions": rec.candidate_versions, "candidate_health": rec.candidate_health,
        "candidate_compatibility": rec.candidate_compatibility,
        "required_capabilities": list(rec.required_capabilities),
        "rejection_reasons": rec.rejection_reasons,
        "selected_provider_id": rec.selected_provider_id,
        "selected_provider_version": rec.selected_provider_version,
        "fallback_used": rec.fallback_used, "fallback_reason": rec.fallback_reason,
        "resolution_fingerprint": rec.resolution_fingerprint,
    }
