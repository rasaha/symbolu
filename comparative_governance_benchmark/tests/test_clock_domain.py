"""The benchmark replays scenarios in one time domain — the frozen scenario clock.

``runners.determinism.make_clock`` pins every run to 2026-01-01T00:00:00Z, so a
scenario's CER expires at 2026-01-01T01:00:00Z. Any collaborator left on its own
default clock — the control-plane adapter, the audit service, either validation
service, the execution adapter — stamps or compares ``now_wall`` instead, and
``ExecutionService`` then compares the two against each other: an
``AuthorizationExpiredError`` whose occurrence depends on the date the suite
happens to run.

These guards pin decision D1 in
``Project_documentation/repository/docs/audits/actiongate_vnext/RATIFIED_DECISIONS.md``:
for a replayed scenario the scenario clock is authoritative, and the rule applies
at composition-root granularity — a root that injects a clock into any Decision
Authority or governance-provider-framework collaborator must inject one into
every clock-capable collaborator it wires.

The scan and the skew seam are shared with the other two harness trees and live
in ``enterprise_validation_pilot.tests.clock_domain_guard``, the tree this one
already depends on; what stays here is the benchmark's own replay body.
"""
from __future__ import annotations

from pathlib import Path

from enterprise_validation_pilot.tests.clock_domain_guard import (
    SKEW, assert_no_root_mixes_clock_domains, assert_scan_reaches,
    assert_the_skew_seam_bites, stable, wall_clock_at)

from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy


_TREE = Path(__file__).resolve().parents[1]

# the collaborators the scan must keep reaching; a resolver that silently matched
# nothing would make the scan vacuous
_GUARDED = {
    "ActionGovernanceControlPlaneAdapter", "AuditService", "ExecutionValidationService",
    "ActionRequestValidationService", "build_execution_adapter", "ExecutionService"}


def test_the_scan_reaches_the_collaborators_it_is_meant_to_guard():
    assert_scan_reaches(_TREE, _GUARDED)


def test_no_composition_root_replays_in_two_clock_domains():
    assert_no_root_mixes_clock_domains(_TREE)


def test_the_skew_seam_actually_moves_a_default_clock():
    assert_the_skew_seam_bites()


def test_strategy_outcomes_do_not_move_when_the_wall_clock_moves():
    scenarios = list(load_frozen_dataset().ordered())
    # every strategy, not only the authorizing ones: a default clock reaches the
    # direct-dispatch execution adapter too
    strategies = {sid: build_strategy(sid) for sid in
                  ("no_governance", "assertion_only", "action_only", "full_governance")}
    baseline = {(sid, s.scenario_id): stable(st.run(s))
                for sid, st in strategies.items() for s in scenarios}
    with wall_clock_at(SKEW):
        skewed = {(sid, s.scenario_id): stable(st.run(s))
                  for sid, st in strategies.items() for s in scenarios}
    differing = [k for k in baseline if baseline[k] != skewed[k]]
    assert not differing, (
        "these (strategy, scenario) pairs replayed differently once the wall clock moved, "
        f"so the benchmark is still reading it somewhere: {differing}")
