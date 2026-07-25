"""All scenario classes reproduce ground truth; all safety invariants hold."""
from __future__ import annotations

import pytest

from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.evaluators import check_invariants, evaluate
from enterprise_validation_pilot.pilot import run_pilot
from enterprise_validation_pilot.runners.workflow import run_scenario

_DATASET = build()
_PAIRS = [(s, run_scenario(s)) for s in _DATASET.ordered()]


@pytest.mark.parametrize("scenario,run", _PAIRS, ids=[s.scenario_id for s, _ in _PAIRS])
def test_every_scenario_matches_ground_truth(scenario, run):
    ev = evaluate(scenario, run)
    assert ev.passed, ev.mismatches or ev.error


def test_all_90_scenarios_pass():
    assert sum(1 for s, r in _PAIRS if evaluate(s, r).passed) == 90


@pytest.mark.parametrize("inv", check_invariants(_PAIRS), ids=lambda i: i.id)
def test_safety_invariant(inv):
    assert inv.passed, f"{inv.id} {inv.description}: {inv.offenders} {inv.detail}"


def test_unsupported_and_indeterminate_never_promoted():
    for s, r in _PAIRS:
        if r.tap_outcome in ("UNSUPPORTED", "INDETERMINATE"):
            assert not r.dispatched
            assert r.recommendation_posture != "ADVANCE"


def test_denied_and_indeterminate_actions_never_dispatch():
    for s, r in _PAIRS:
        if r.actiongate_outcome in ("DENIED", "INDETERMINATE"):
            assert not r.dispatched


def test_overall_pilot_passes():
    results = run_pilot(_DATASET)
    assert results.overall_pass
    assert results.scenarios_passed == 90
