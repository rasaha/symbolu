"""Cost/benefit frontier by scenario class (Task 14).

For each scenario class, determines which provider pairs (C1–C4) are *sufficient*
(reproduce the full pair's safe operational outcome without a capability gap), the
lowest-workload sufficient pair, required capabilities, whether bounded fallback is
acceptable, and whether the full pair changes the outcome. Analytical output only —
not a dynamic production router.
"""
from __future__ import annotations

from ..policies.requirements import (
    required_action_capabilities, required_assertion_capabilities)

_PAIRS = ("C1", "C2", "C3", "C4")
_WORKLOAD_ORDER = {"C4": 0, "C2": 1, "C3": 1, "C1": 2}   # baseline pair lightest


def _key(r):
    return (r.dispatched, r.authorization_outcome, r.assertion_outcome)


def frontier_by_class(grid: dict, dataset) -> dict:
    """grid: {config_id: {scenario_id: HeteroResult}}."""
    classes = sorted({s.cross_class for s in dataset.ordered()})
    out = {}
    for cls in classes:
        scen_ids = [s.scenario_id for s in dataset.ordered() if s.cross_class == cls]
        c1 = {sid: _key(grid["C1"][sid]) for sid in scen_ids}
        sufficient = []
        for cfg in _PAIRS:
            if all(_key(grid[cfg][sid]) == c1[sid] for sid in scen_ids):
                sufficient.append(cfg)
        # required capabilities (union across the class)
        req_a, req_b = set(), set()
        for sid in scen_ids:
            s = dataset.by_id(sid)
            req_a |= set(required_assertion_capabilities(s))
            req_b |= set(required_action_capabilities(s))
        lightest = min(sufficient, key=lambda c: _WORKLOAD_ORDER[c]) if sufficient else None
        # bounded fallback acceptable if C5 matches C1 for the class
        fallback_ok = all(_key(grid["C5"][sid]) == c1[sid] for sid in scen_ids)
        out[cls] = {
            "scenarios": len(scen_ids),
            "sufficient_configs": sufficient,
            "lowest_workload_sufficient": lightest,
            "required_assertion_capabilities": sorted(req_a),
            "required_action_capabilities": sorted(req_b),
            "fallback_acceptable": fallback_ok,
            "full_pair_required": sufficient == ["C1"],
            "full_pair_changes_outcome": "C4" not in sufficient,
        }
    return out
