"""Strategy behaviour + oracle classification (Tasks 5, 7, 9)."""
from __future__ import annotations

import pytest

from comparative_governance_benchmark.evaluators.oracle import judge
from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy

_DS = load_frozen_dataset()
_STRAT = {sid: build_strategy(sid) for sid in
          ("no_governance", "action_only", "assertion_only", "full_governance")}


def _run(sid, scid):
    return _STRAT[sid].run(_DS.by_id(scid))


def test_no_governance_dispatches_unsupported_assertion():
    # unsupported assertion + authorizable action → no-gov and action-only dispatch (unsafe)
    assert _run("no_governance", "procurement-003").dispatched
    assert _run("action_only", "procurement-003").dispatched
    # TAP-bearing strategies block it
    assert not _run("assertion_only", "procurement-003").dispatched
    assert not _run("full_governance", "procurement-003").dispatched


def test_only_actiongate_blocks_denied_action():
    # supported assertion + denied action → assertion-only and no-gov dispatch (unsafe)
    assert _run("no_governance", "procurement-013").dispatched
    assert _run("assertion_only", "procurement-013").dispatched
    assert not _run("action_only", "procurement-013").dispatched
    assert not _run("full_governance", "procurement-013").dispatched


def test_only_actiongate_enforces_envelope():
    # out-of-envelope amount → only constraint-enforcing strategies block
    assert _run("no_governance", "procurement-017").dispatched
    assert _run("assertion_only", "procurement-017").dispatched
    assert not _run("action_only", "procurement-017").dispatched
    assert not _run("full_governance", "procurement-017").dispatched


def test_obligation_failure_visible_only_with_actiongate():
    # executes but obligation unmet → only ActionGate-bearing strategies flag noncompliance
    assert _run("action_only", "procurement-025").final_governance_compliance == "NONCOMPLIANT"
    assert _run("full_governance", "procurement-025").final_governance_compliance == "NONCOMPLIANT"
    assert _run("assertion_only", "procurement-025").final_governance_compliance == "NOT_APPLICABLE"


def test_full_governance_never_unsafe():
    from comparative_governance_benchmark.schemas.safety import UNSAFE_OUTCOMES
    strat = _STRAT["full_governance"]
    for s in _DS.ordered():
        assert judge(s, strat.run(s)).safety_outcome not in UNSAFE_OUTCOMES, s.scenario_id


@pytest.mark.parametrize("sid,expected_unsafe", [
    ("no_governance", 27), ("action_only", 6), ("assertion_only", 15), ("full_governance", 0)])
def test_unsafe_totals_match_expected(sid, expected_unsafe):
    from comparative_governance_benchmark.schemas.safety import UNSAFE_OUTCOMES
    strat = _STRAT[sid]
    unsafe = sum(1 for s in _DS.ordered()
                 if judge(s, strat.run(s)).safety_outcome in UNSAFE_OUTCOMES)
    assert unsafe == expected_unsafe
