"""The pilot replays scenarios in one time domain — the frozen scenario clock.

A replayed scenario issues its CER on ``composition.determinism.make_clock``
(2026-01-01T00:00:00Z, so ``expires_at`` is 2026-01-01T01:00:00Z). Any
collaborator left on its own default clock — the control-plane adapter, the
audit service, either validation service, the execution adapter — stamps or
compares ``now_wall`` instead, and the two instants are then compared against
each other. Whenever they disagree in the wrong direction the pilot collapses
with ``AuthorizationExpiredError``, and whether it does depends on the date the
suite happens to run.

These guards pin decision D1 in
``Project_documentation/repository/docs/audits/actiongate_vnext/RATIFIED_DECISIONS.md``:
for a replayed scenario the scenario clock is authoritative, and the rule applies
at composition-root granularity — a root that injects a clock into any Decision
Authority or governance-provider-framework collaborator must inject one into
every clock-capable collaborator it wires.

The scan and the skew seam are shared with the other two harness trees and live
in ``clock_domain_guard``; what stays here is the pilot's own replay body.
"""
from __future__ import annotations

from pathlib import Path

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.runners.workflow import run_scenario
from enterprise_validation_pilot.tests.clock_domain_guard import (
    SKEW, assert_every_authority_collaborator_is_clocked, assert_no_root_mixes_clock_domains,
    assert_scan_reaches, assert_the_skew_seam_bites, stable, wall_clock_at)


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


def test_every_authority_collaborator_in_the_pilot_is_clocked():
    """The pilot is a declared replay tree: whole-tree uniformity, not just
    composition-root granularity — see ``clock_domain_guard.scan_uniform``."""
    assert_every_authority_collaborator_is_clocked(_TREE)


def test_the_skew_seam_actually_moves_a_default_clock():
    assert_the_skew_seam_bites()


def test_replay_outcomes_do_not_move_when_the_wall_clock_moves():
    scenarios = list(build().ordered())
    baseline = [stable(run_scenario(s)) for s in scenarios]
    with wall_clock_at(SKEW):
        skewed = [stable(run_scenario(s)) for s in scenarios]
    differing = [s.scenario_id for s, b, k in zip(scenarios, baseline, skewed) if b != k]
    assert not differing, (
        "these scenarios replayed differently once the wall clock moved, so the pilot is "
        f"still reading it somewhere: {differing}")
