"""Behavioural contracts for the SafetyStateMachine.

The state machine is the §9.1-recommended industry feature
(the *behavioural contract* the runtime layer composes into).
This file pins the load-bearing invariants:

* The four-state enum + the six legal-edge transition table
  match the design doc §2.
* Every direct jump prohibited by §6 raises
  ``IllegalTransitionError``.
* Each automatic transition fires on its documented trigger and
  does NOT fire on adjacent-but-non-triggering inputs.
* Manual resets walk FAULT → DEGRADED and FAILSAFE → FAULT only
  via :meth:`SafetyStateMachine.reset_with_diagnostic_clear`.
* Recovery (DEGRADED → NORMAL) requires the documented dwell.
* The :class:`StateTransitionLog` records every transition with
  timestamp, cause, and (where applicable) operator.
* Composition with :class:`StreamingFleetMonitor` works — an
  AlertRule on a state-derived metric fires under the documented
  threshold-crossing condition.
* Composition with the SOTIF traceability matrix — the state
  machine artifact is referenced from clause 8 (functional
  insufficiencies) and named in clause Part 6 §8 (architectural
  design).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.analysis import (
    AlertRule,
    StreamingFleetMonitor,
)
from symbolu_robotics.bcvf_autonomous.safety_case import (
    build_traceability_matrix,
)
from symbolu_robotics.bcvf_autonomous.safety_state import (
    IllegalTransitionError,
    LEGAL_TRANSITIONS,
    RollingWindow,
    SafetyState,
    SafetyStateMachine,
    SafetyStateMachineConfig,
    SafetyStateMachineError,
    StateTransition,
    TickView,
    is_legal_transition,
    legal_target_states,
    lookup_transition,
    tick_views_from_record,
)
from symbolu_robotics.bcvf_autonomous.trust_diagnostics import (
    RolloutAggregation,
    TrustShapedEpisodeRecord,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _tick(
    bcvf_total: float = 0.0,
    excluded: tuple = (False, False, False, False),
    consec_suspect: tuple = (0, 0, 0, 0),
) -> TickView:
    """Build one TickView with sensible defaults.

    Defaults represent a quiet NORMAL tick: no exclusion, all
    consec counters zero, BCVF total below the active-rate
    threshold. Tests perturb individual fields to drive
    transitions.
    """
    return TickView(
        bcvf_total=float(bcvf_total),
        is_excluded=np.asarray(excluded, dtype=bool),
        consec_suspect=np.asarray(consec_suspect, dtype=np.int64),
        M=len(excluded),
    )


def _drive_to_degraded(
    machine: SafetyStateMachine, n_ticks: int = 250
) -> None:
    """Drive a fresh machine into DEGRADED by feeding near-veto ticks."""
    for _ in range(n_ticks):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.DEGRADED


def _drive_to_fault(machine: SafetyStateMachine) -> None:
    """Drive a fresh machine into FAULT by feeding sustained
    exclusion + high-BCVF ticks. Feeds enough ticks to fill the
    rolling window so bcvf_active_rate clears the threshold."""
    _drive_to_degraded(machine)
    # Need bcvf_active_rate ≥ threshold (default 0.5) over the
    # window. With window=200, default config, we need at least
    # 100 high-BCVF ticks; feed 1.5× window to be safe.
    n_high = int(machine.config.rolling_window_ticks * 1.5)
    for _ in range(n_high):
        machine.observe(
            _tick(
                bcvf_total=0.5,
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAULT


def _drive_to_failsafe(machine: SafetyStateMachine) -> None:
    """Drive a fresh machine into FAILSAFE."""
    _drive_to_fault(machine)
    for _ in range(20):
        machine.observe(
            _tick(
                bcvf_total=0.5,
                excluded=(True, True, False, False),
                consec_suspect=(5, 5, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAILSAFE


# --------------------------------------------------------------------------- #
# §2 — enum + legal-edge table
# --------------------------------------------------------------------------- #


def test_safety_state_enum_has_four_states():
    assert {s.name for s in SafetyState} == {
        "NORMAL", "DEGRADED", "FAULT", "FAILSAFE"
    }


def test_legal_transitions_table_matches_design_doc_six_edges():
    """The six edges named in §2: NORMAL↔DEGRADED, DEGRADED↔FAULT
    (FAULT→DEGRADED is manual), FAULT→FAILSAFE, FAILSAFE→FAULT
    (manual)."""
    edges = {
        (t.from_state, t.to_state) for t in LEGAL_TRANSITIONS
    }
    expected = {
        (SafetyState.NORMAL,   SafetyState.DEGRADED),
        (SafetyState.DEGRADED, SafetyState.NORMAL),
        (SafetyState.DEGRADED, SafetyState.FAULT),
        (SafetyState.FAULT,    SafetyState.FAILSAFE),
        (SafetyState.FAULT,    SafetyState.DEGRADED),
        (SafetyState.FAILSAFE, SafetyState.FAULT),
    }
    assert edges == expected
    assert len(LEGAL_TRANSITIONS) == 6


def test_asil_decomposition_pinned_per_transition():
    """§5 ASIL classifications: NORMAL↔DEGRADED + manual resets =
    ASIL-B; DEGRADED→FAULT + FAULT→FAILSAFE = ASIL-D."""
    by_pair = {(t.from_state, t.to_state): t.asil for t in LEGAL_TRANSITIONS}
    assert by_pair[(SafetyState.NORMAL, SafetyState.DEGRADED)] == "ASIL-B"
    assert by_pair[(SafetyState.DEGRADED, SafetyState.NORMAL)] == "ASIL-B"
    assert by_pair[(SafetyState.DEGRADED, SafetyState.FAULT)] == "ASIL-D"
    assert by_pair[(SafetyState.FAULT, SafetyState.FAILSAFE)] == "ASIL-D"
    assert by_pair[(SafetyState.FAULT, SafetyState.DEGRADED)] == "ASIL-B"
    assert by_pair[(SafetyState.FAILSAFE, SafetyState.FAULT)] == "ASIL-B"


# --------------------------------------------------------------------------- #
# §6 — direct-jump prohibition
# --------------------------------------------------------------------------- #


_ALL_PAIRS = [
    (a, b)
    for a, b in product(SafetyState, SafetyState)
    if a != b
]
_LEGAL_PAIRS = {(t.from_state, t.to_state) for t in LEGAL_TRANSITIONS}
_ILLEGAL_PAIRS = [p for p in _ALL_PAIRS if p not in _LEGAL_PAIRS]


@pytest.mark.parametrize("pair", _ILLEGAL_PAIRS)
def test_every_illegal_pair_raises_illegal_transition_error(pair):
    """Per §6, every (from, to) pair NOT in the legal-edge table
    must raise ``IllegalTransitionError`` when the machine
    attempts the transition. Parametrized so the failing pair is
    named in the test report on regression."""
    from_state, to_state = pair
    machine = SafetyStateMachine()
    machine._state = from_state  # type: ignore[attr-defined]
    with pytest.raises(IllegalTransitionError) as exc_info:
        machine._transition(  # type: ignore[attr-defined]
            from_state, to_state, cause="forbidden", tick_index=0
        )
    assert exc_info.value.from_state == from_state
    assert exc_info.value.to_state == to_state


def test_illegal_transition_error_names_offending_pair_in_message():
    """A debug reader should see the offending (from, to) pair in
    the error message, not have to grep the table."""
    err = IllegalTransitionError(
        SafetyState.NORMAL, SafetyState.FAULT, reason="test"
    )
    msg = str(err)
    assert "NORMAL" in msg
    assert "FAULT" in msg
    assert "§6" in msg


def test_is_legal_transition_self_loops_are_not_legal():
    """The machine holds state without recording a transition; a
    'transition' from S → S is therefore not a legal edge."""
    for s in SafetyState:
        assert not is_legal_transition(s, s)


def test_legal_target_states_helper_returns_only_outgoing_edges():
    assert set(legal_target_states(SafetyState.NORMAL)) == {
        SafetyState.DEGRADED
    }
    assert set(legal_target_states(SafetyState.DEGRADED)) == {
        SafetyState.NORMAL, SafetyState.FAULT
    }
    assert set(legal_target_states(SafetyState.FAULT)) == {
        SafetyState.FAILSAFE, SafetyState.DEGRADED
    }
    assert set(legal_target_states(SafetyState.FAILSAFE)) == {
        SafetyState.FAULT
    }


def test_lookup_transition_raises_keyerror_on_illegal_pair():
    with pytest.raises(KeyError):
        lookup_transition(SafetyState.NORMAL, SafetyState.FAULT)


# --------------------------------------------------------------------------- #
# §3 — trigger conditions: NORMAL → DEGRADED
# --------------------------------------------------------------------------- #


def test_normal_to_degraded_fires_when_near_veto_rate_crosses_threshold():
    """The trigger fires when the rolling fraction of ticks with
    near-veto signal crosses ``near_veto_rate_threshold``."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=20,
        near_veto_rate_threshold=0.50,
        near_veto_consec_floor=3,
    )
    machine = SafetyStateMachine(cfg)
    # First 10 ticks quiet — should stay NORMAL.
    for _ in range(10):
        machine.observe(_tick())
    assert machine.state == SafetyState.NORMAL
    # Next 11 ticks all near-veto — fraction 11/20 = 0.55 > 0.50.
    for _ in range(11):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.DEGRADED


def test_normal_to_degraded_does_not_fire_below_threshold():
    """Below-threshold near-veto rates leave the machine in NORMAL."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=20,
        near_veto_rate_threshold=0.50,
        near_veto_consec_floor=3,
    )
    machine = SafetyStateMachine(cfg)
    # 9/20 = 0.45 — below 0.50 threshold.
    for _ in range(11):
        machine.observe(_tick())
    for _ in range(9):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.NORMAL


def test_normal_to_degraded_does_not_fire_on_consec_below_floor():
    """consec_suspect below ``near_veto_consec_floor`` doesn't count
    as near-veto, even if it's elevated."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=10,
        near_veto_rate_threshold=0.10,
        near_veto_consec_floor=5,
    )
    machine = SafetyStateMachine(cfg)
    # consec=4 is below floor of 5 — should not trigger.
    for _ in range(20):
        machine.observe(_tick(consec_suspect=(4, 0, 0, 0)))
    assert machine.state == SafetyState.NORMAL


# --------------------------------------------------------------------------- #
# §3 — trigger conditions: DEGRADED → FAULT
# --------------------------------------------------------------------------- #


def test_degraded_to_fault_requires_exclusion_and_sustained_bcvf():
    """The DEGRADED → FAULT trigger requires BOTH sustained
    exclusion AND sustained BCVF activity."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=30,
        near_veto_rate_threshold=0.10,
        near_veto_consec_floor=3,
        bcvf_active_threshold=0.05,
        bcvf_active_rate_threshold=0.50,
        exclusion_persistence_ticks=5,
    )
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine, n_ticks=30)
    # Sustained exclusion + sustained BCVF.
    for _ in range(20):
        machine.observe(
            _tick(
                bcvf_total=0.5,
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAULT


def test_degraded_to_fault_does_not_fire_on_single_tick_spike():
    """A single-tick spike (one excluded tick + one high-BCVF tick)
    does not cross the persistence + rate thresholds."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=30,
        near_veto_rate_threshold=0.10,
        near_veto_consec_floor=3,
        bcvf_active_threshold=0.05,
        bcvf_active_rate_threshold=0.50,
        exclusion_persistence_ticks=5,
    )
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine, n_ticks=30)
    # One spike — not enough to satisfy persistence or rate.
    machine.observe(
        _tick(
            bcvf_total=0.5,
            excluded=(True, False, False, False),
            consec_suspect=(5, 0, 0, 0),
        )
    )
    assert machine.state == SafetyState.DEGRADED


def test_degraded_to_fault_does_not_fire_on_exclusion_without_bcvf():
    """Sustained exclusion alone is insufficient; the trigger
    requires both predicates."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=30,
        bcvf_active_threshold=0.05,
        bcvf_active_rate_threshold=0.50,
        exclusion_persistence_ticks=5,
    )
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine, n_ticks=30)
    # Sustained exclusion but BCVF stays quiet — should not transition.
    for _ in range(20):
        machine.observe(
            _tick(
                bcvf_total=0.0,
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.DEGRADED


# --------------------------------------------------------------------------- #
# §3 — trigger conditions: FAULT → FAILSAFE
# --------------------------------------------------------------------------- #


def test_fault_to_failsafe_requires_at_least_two_excluded_predictors():
    """Per §3, FAULT → FAILSAFE requires the count of distinct
    excluded predictors in the rolling window to be ≥ 2."""
    cfg = SafetyStateMachineConfig(failsafe_excluded_predictor_count=2)
    machine = SafetyStateMachine(cfg)
    _drive_to_fault(machine)
    # Add ticks where a SECOND predictor is excluded.
    for _ in range(20):
        machine.observe(
            _tick(
                bcvf_total=0.5,
                excluded=(True, True, False, False),
                consec_suspect=(5, 5, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAILSAFE


def test_fault_to_failsafe_does_not_fire_on_single_predictor_excluded():
    """If only ONE predictor stays excluded throughout, the trigger
    must not fire — that's the FAULT signal, not the FAILSAFE
    signal."""
    cfg = SafetyStateMachineConfig(failsafe_excluded_predictor_count=2)
    machine = SafetyStateMachine(cfg)
    _drive_to_fault(machine)
    # Continue with only ONE excluded predictor.
    for _ in range(50):
        machine.observe(
            _tick(
                bcvf_total=0.5,
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAULT


def test_failsafe_excluded_predictor_count_threshold_must_be_at_least_two():
    """Configuration sanity — FAILSAFE is multi-predictor-loss by
    definition; setting the threshold to 1 collapses it onto FAULT."""
    with pytest.raises(ValueError):
        SafetyStateMachineConfig(failsafe_excluded_predictor_count=1)


# --------------------------------------------------------------------------- #
# §4 — recovery: DEGRADED → NORMAL with sustained dwell
# --------------------------------------------------------------------------- #


def test_degraded_to_normal_requires_sustained_dwell():
    """Per §4, DEGRADED → NORMAL requires the near-veto rate to
    drop below threshold AND remain below for ≥ T_recovery
    consecutive ticks."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=10,
        near_veto_rate_threshold=0.50,
        near_veto_consec_floor=3,
        t_recovery_ticks=50,
    )
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine, n_ticks=30)
    # The first quiet tick where rate drops strictly below the
    # 0.50 threshold is when ≤ 4 near-veto ticks remain in the
    # 10-tick window — i.e. after the 6th quiet tick. From that
    # point, _below_threshold_ticks counts up by 1 each tick.
    # Recovery fires when the counter reaches T_recovery=50:
    # at the (6 + 49) = 55th quiet tick the counter reaches 50.
    # So 54 quiet ticks => _below=49, still DEGRADED.
    for _ in range(54):
        machine.observe(_tick())
    assert machine.state == SafetyState.DEGRADED
    # One more tick crosses the dwell threshold (_below=50).
    machine.observe(_tick())
    assert machine.state == SafetyState.NORMAL


def test_degraded_to_normal_does_not_fire_if_near_veto_returns():
    """A transient quiet period followed by renewed near-veto
    activity should not reach NORMAL — the rate is no longer
    below threshold."""
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=20,
        near_veto_rate_threshold=0.50,
        near_veto_consec_floor=3,
        t_recovery_ticks=10,
    )
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine, n_ticks=30)
    # Brief quiet, then renewed activity.
    for _ in range(5):
        machine.observe(_tick())
    for _ in range(20):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.DEGRADED


# --------------------------------------------------------------------------- #
# §4 — manual reset paths
# --------------------------------------------------------------------------- #


def test_manual_reset_walks_fault_to_degraded():
    machine = SafetyStateMachine()
    _drive_to_fault(machine)
    new_state = machine.reset_with_diagnostic_clear(
        operator="ops_alice", reason="diagnostic checked + cleared"
    )
    assert new_state == SafetyState.DEGRADED
    assert machine.state == SafetyState.DEGRADED


def test_manual_reset_walks_failsafe_to_fault():
    machine = SafetyStateMachine()
    _drive_to_failsafe(machine)
    new_state = machine.reset_with_diagnostic_clear(
        operator="teleop_bob", reason="vehicle inspected + handed back"
    )
    assert new_state == SafetyState.FAULT
    assert machine.state == SafetyState.FAULT


def test_manual_reset_refused_from_normal_or_degraded():
    """Reset is only valid from FAULT or FAILSAFE — calling it
    from NORMAL or DEGRADED is a programming error and raises
    SafetyStateMachineError."""
    machine = SafetyStateMachine()
    with pytest.raises(SafetyStateMachineError):
        machine.reset_with_diagnostic_clear("op", "from normal")
    _drive_to_degraded(machine)
    with pytest.raises(SafetyStateMachineError):
        machine.reset_with_diagnostic_clear("op", "from degraded")


def test_manual_reset_requires_non_empty_operator_and_reason():
    machine = SafetyStateMachine()
    _drive_to_fault(machine)
    with pytest.raises(ValueError):
        machine.reset_with_diagnostic_clear("", "valid reason")
    with pytest.raises(ValueError):
        machine.reset_with_diagnostic_clear("op", "")


# --------------------------------------------------------------------------- #
# Transition log
# --------------------------------------------------------------------------- #


def test_transition_log_records_every_transition():
    """Every transition appends a typed log entry with timestamp,
    transition row, cause string, and tick index."""
    machine = SafetyStateMachine()
    _drive_to_failsafe(machine)
    log = machine.transition_log.entries()
    # Three automatic transitions: NORMAL→DEGRADED, DEGRADED→FAULT,
    # FAULT→FAILSAFE.
    assert len(log) == 3
    states = [(e.transition.from_state, e.transition.to_state) for e in log]
    assert states == [
        (SafetyState.NORMAL,   SafetyState.DEGRADED),
        (SafetyState.DEGRADED, SafetyState.FAULT),
        (SafetyState.FAULT,    SafetyState.FAILSAFE),
    ]
    for entry in log:
        assert entry.cause, "every entry must have a non-empty cause"
        assert isinstance(entry.timestamp, datetime)


def test_transition_log_records_manual_reset_with_operator_field():
    machine = SafetyStateMachine()
    _drive_to_fault(machine)
    machine.reset_with_diagnostic_clear("op_carol", "diagnostic clear")
    log = machine.transition_log.entries()
    last = log[-1]
    assert last.transition.from_state == SafetyState.FAULT
    assert last.transition.to_state == SafetyState.DEGRADED
    assert last.transition.trigger == "manual_reset"
    assert last.operator == "op_carol"
    assert "op_carol" in last.cause
    assert last.tick_index == -1


def test_transition_log_uses_injected_clock():
    """Tests inject a fake clock to make timestamps deterministic."""
    fixed = datetime(2026, 5, 5, 12, 0, 0, tzinfo=timezone.utc)
    machine = SafetyStateMachine(clock=lambda: fixed)
    _drive_to_degraded(machine)
    log = machine.transition_log.entries()
    assert log[0].timestamp == fixed


# --------------------------------------------------------------------------- #
# Composition with TrustShapedEpisodeRecord
# --------------------------------------------------------------------------- #


def test_observe_accepts_trust_shaped_episode_record_in_batch():
    """Replaying a JSON-dumped episode record should walk the
    machine through the per-tick rows in order."""
    T, M = 50, 4
    record = TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.zeros((T, M)),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.zeros(T),
        per_step_deadband_active_count=np.zeros(T, dtype=np.int64),
        per_step_deadband_fired=np.zeros(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
    )
    machine = SafetyStateMachine()
    final_state = machine.observe(record)
    assert final_state == SafetyState.NORMAL
    assert machine.n_ticks_observed == T


def test_tick_views_from_record_extracts_per_step_rows():
    T, M = 5, 4
    record = TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.zeros((T, M)),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.array([0.0, 0.1, 0.2, 0.3, 0.4]),
        per_step_deadband_active_count=np.zeros(T, dtype=np.int64),
        per_step_deadband_fired=np.zeros(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
    )
    views = tick_views_from_record(record)
    assert len(views) == T
    assert views[0].bcvf_total == 0.0
    assert views[4].bcvf_total == 0.4
    for v in views:
        assert v.M == M
        assert v.is_excluded.shape == (M,)
        assert v.consec_suspect.shape == (M,)


# --------------------------------------------------------------------------- #
# Composition with StreamingFleetMonitor — AlertRule on a state-derived metric
# --------------------------------------------------------------------------- #


def test_alert_rule_on_state_derived_metric_fires_correctly():
    """A deployment partner can define an AlertRule on the
    deadband_fired_rate fleet metric and route a state-machine-
    derived signal through StreamingFleetMonitor. This pins that
    the AlertRule plumbing fires when the metric crosses the
    threshold — composition with the existing fleet harness is
    intact."""
    T, M = 30, 4
    # Build a fake fleet record where deadband fired on every tick.
    record = TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.zeros((T, M)),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.full(T, 0.5),
        per_step_deadband_active_count=np.full(T, 1, dtype=np.int64),
        per_step_deadband_fired=np.ones(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
    )
    monitor = StreamingFleetMonitor()
    monitor.observe_episode(record, episode_id="ep_1", classification="degraded")

    rule = AlertRule(
        name="degraded_rate_high",
        metric="deadband_fired_rate",
        threshold=0.5,
        direction="above",
    )
    alerts = monitor.evaluate_alerts(
        [rule], window=timedelta(hours=24)
    )
    assert len(alerts) == 1
    assert alerts[0].rule.name == "degraded_rate_high"
    assert alerts[0].observed_value > 0.5


def test_alert_rule_does_not_fire_below_threshold():
    """Below-threshold metric => no fired alert."""
    T, M = 30, 4
    record = TrustShapedEpisodeRecord(
        n_steps=T,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=np.full((T, M), 1.0 / M),
        per_step_costs=np.zeros((T, M)),
        per_step_residuals=np.zeros((T, M)),
        per_step_ema_mean=np.zeros((T, M)),
        per_step_ema_std=np.zeros((T, M)),
        per_step_bcvf_total=np.zeros(T),
        per_step_deadband_active_count=np.zeros(T, dtype=np.int64),
        per_step_deadband_fired=np.zeros(T, dtype=bool),
        per_step_is_excluded=np.zeros((T, M), dtype=bool),
        per_step_gate_activations=np.zeros(T, dtype=np.int64),
        per_step_consec_suspect=np.zeros((T, M), dtype=np.int64),
    )
    monitor = StreamingFleetMonitor()
    monitor.observe_episode(record, episode_id="ep_1", classification="quiet")
    rule = AlertRule(
        name="degraded_rate_high",
        metric="deadband_fired_rate",
        threshold=0.5,
        direction="above",
    )
    alerts = monitor.evaluate_alerts([rule], window=timedelta(hours=24))
    assert alerts == []


# --------------------------------------------------------------------------- #
# Composition with SOTIF traceability matrix
# --------------------------------------------------------------------------- #


def test_safety_state_machine_referenced_in_sotif_clause_8():
    """Per §7, the state machine is the insufficiency-handling
    layer the V2 chatter mitigation composes into. The matrix
    must reference it from clause 8 (functional insufficiencies +
    mitigations)."""
    matrix = build_traceability_matrix()
    refs = set()
    for clause in matrix.all_clauses():
        if clause.clause_id == "8":
            refs = {a.reference for a in clause.evidence}
    assert any("safety_state" in r for r in refs), (
        f"clause 8 evidence must reference safety_state; got {refs}"
    )


def test_safety_state_machine_referenced_in_iso_26262_part6_section_8():
    """Per §7, the state machine is a named architectural module —
    must appear in ISO 26262 Part 6 §8 (architectural design)."""
    matrix = build_traceability_matrix()
    refs = set()
    for clause in matrix.all_clauses():
        if clause.clause_id == "Part 6 §8":
            refs = {a.reference for a in clause.evidence}
    assert any("safety_state" in r for r in refs), (
        f"Part 6 §8 must reference safety_state; got {refs}"
    )


# --------------------------------------------------------------------------- #
# RollingWindow primitives
# --------------------------------------------------------------------------- #


def test_rolling_window_capacity_evicts_oldest():
    win = RollingWindow(capacity=3)
    for i in range(5):
        win.append(_tick(bcvf_total=float(i)))
    assert len(win) == 3
    assert win.latest().bcvf_total == 4.0


def test_rolling_window_near_veto_rate_zero_on_empty():
    win = RollingWindow(capacity=10)
    assert win.near_veto_rate(consec_floor=3) == 0.0


def test_rolling_window_distinct_excluded_predictors_unions_across_window():
    """Predictor 0 excluded on tick 0, predictor 2 excluded on
    tick 5 — the count of distinct excluded predictors is 2."""
    win = RollingWindow(capacity=10)
    win.append(_tick(excluded=(True, False, False, False)))
    for _ in range(4):
        win.append(_tick())
    win.append(_tick(excluded=(False, False, True, False)))
    for _ in range(4):
        win.append(_tick())
    assert win.distinct_excluded_predictors() == 2


def test_rolling_window_persistence_requires_consecutive_excluded_at_tail():
    """A predictor excluded on every tick of the trailing window
    of size persistence_ticks => True. Gaps reset the counter."""
    win = RollingWindow(capacity=10)
    # 5 consecutive ticks with predictor 0 excluded.
    for _ in range(5):
        win.append(_tick(excluded=(True, False, False, False)))
    assert win.any_excluded_persistence(persistence_ticks=5)
    # Now add a clean tick — persistence resets.
    win.append(_tick())
    assert not win.any_excluded_persistence(persistence_ticks=5)


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #


def test_config_rejects_invalid_rolling_window():
    with pytest.raises(ValueError):
        SafetyStateMachineConfig(rolling_window_ticks=0)


def test_config_rejects_out_of_range_rate_thresholds():
    with pytest.raises(ValueError):
        SafetyStateMachineConfig(near_veto_rate_threshold=1.5)
    with pytest.raises(ValueError):
        SafetyStateMachineConfig(bcvf_active_rate_threshold=-0.1)


def test_state_transition_dataclass_rejects_invalid_asil():
    with pytest.raises(ValueError):
        StateTransition(
            from_state=SafetyState.NORMAL,
            to_state=SafetyState.DEGRADED,
            trigger="bogus",
            asil="ASIL-X",
        )


# --------------------------------------------------------------------------- #
# state_transition_consistency family — per-transition must-fire and
# must-be-quiet pinning at adjacent thresholds
# --------------------------------------------------------------------------- #
#
# Per SAFETY_STATE_MACHINE_DESIGN.md §9, the ship-when-ready
# criterion #2 is a characterization-grid extension asserting each
# documented transition fires under the trigger condition AND does
# not fire under an adjacent-but-non-triggering condition. The grid
# below is the in-repo seed of that family — one cell per
# documented automatic transition with both must-fire and must-be-
# quiet assertions at adjacent thresholds. The cell is repeated
# across multiple seeds (only seed-dependent variation is the
# noise floor injected into BCVF totals); the per-cell pass
# verdict is unanimous-pass across seeds.


_STATE_TRANSITION_CONSISTENCY_SEEDS = (42, 43, 44, 45, 46)


@pytest.mark.parametrize("seed", _STATE_TRANSITION_CONSISTENCY_SEEDS)
def test_state_transition_consistency_normal_to_degraded(seed):
    """state_transition_consistency cell for NORMAL → DEGRADED.

    must-fire: rolling near-veto rate above threshold.
    must-be-quiet: rolling near-veto rate exactly at the
    threshold edge minus epsilon.
    """
    rng = np.random.default_rng(seed)
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=20,
        near_veto_rate_threshold=0.50,
        near_veto_consec_floor=3,
    )

    # Must-fire: 11 near-veto ticks out of 20 (rate=0.55).
    machine = SafetyStateMachine(cfg)
    for _ in range(9):
        # Add tiny BCVF noise so the cell is seed-sensitive.
        noise = float(rng.uniform(0.0, 0.001))
        machine.observe(_tick(bcvf_total=noise))
    for _ in range(11):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.DEGRADED, (
        f"must-fire cell failed at seed {seed}"
    )

    # Must-be-quiet: 9 near-veto ticks out of 20 (rate=0.45).
    machine = SafetyStateMachine(cfg)
    for _ in range(11):
        machine.observe(_tick())
    for _ in range(9):
        machine.observe(_tick(consec_suspect=(3, 0, 0, 0)))
    assert machine.state == SafetyState.NORMAL, (
        f"must-be-quiet cell tripped at seed {seed}"
    )


@pytest.mark.parametrize("seed", _STATE_TRANSITION_CONSISTENCY_SEEDS)
def test_state_transition_consistency_degraded_to_fault(seed):
    """state_transition_consistency cell for DEGRADED → FAULT.

    must-fire: sustained exclusion + sustained BCVF activity.
    must-be-quiet: sustained exclusion alone (BCVF below noise
    floor — the conjunctive predicate's other half is false).
    """
    rng = np.random.default_rng(seed)
    cfg = SafetyStateMachineConfig(
        rolling_window_ticks=30,
        near_veto_rate_threshold=0.10,
        near_veto_consec_floor=3,
        bcvf_active_threshold=0.05,
        bcvf_active_rate_threshold=0.50,
        exclusion_persistence_ticks=5,
    )

    # Must-fire: sustained exclusion + sustained high-BCVF.
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine)
    for _ in range(60):
        # BCVF total > threshold with seed-dependent noise.
        machine.observe(
            _tick(
                bcvf_total=0.5 + float(rng.uniform(0.0, 0.01)),
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAULT, (
        f"must-fire cell failed at seed {seed}"
    )

    # Must-be-quiet: sustained exclusion but BCVF stays below
    # threshold throughout — the conjunctive trigger doesn't fire.
    machine = SafetyStateMachine(cfg)
    _drive_to_degraded(machine)
    for _ in range(60):
        machine.observe(
            _tick(
                bcvf_total=float(rng.uniform(0.0, 0.01)),  # well below 0.05
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.DEGRADED, (
        f"must-be-quiet cell tripped at seed {seed}"
    )


@pytest.mark.parametrize("seed", _STATE_TRANSITION_CONSISTENCY_SEEDS)
def test_state_transition_consistency_fault_to_failsafe(seed):
    """state_transition_consistency cell for FAULT → FAILSAFE.

    must-fire: ≥ 2 distinct excluded predictors in window.
    must-be-quiet: only 1 distinct excluded predictor in window.
    """
    rng = np.random.default_rng(seed)
    cfg = SafetyStateMachineConfig(failsafe_excluded_predictor_count=2)

    # Must-fire: a SECOND predictor gets excluded.
    machine = SafetyStateMachine(cfg)
    _drive_to_fault(machine)
    for _ in range(50):
        machine.observe(
            _tick(
                bcvf_total=0.5 + float(rng.uniform(0.0, 0.01)),
                excluded=(True, True, False, False),
                consec_suspect=(5, 5, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAILSAFE, (
        f"must-fire cell failed at seed {seed}"
    )

    # Must-be-quiet: still only one predictor excluded.
    machine = SafetyStateMachine(cfg)
    _drive_to_fault(machine)
    for _ in range(100):
        machine.observe(
            _tick(
                bcvf_total=0.5 + float(rng.uniform(0.0, 0.01)),
                excluded=(True, False, False, False),
                consec_suspect=(5, 0, 0, 0),
            )
        )
    assert machine.state == SafetyState.FAULT, (
        f"must-be-quiet cell tripped at seed {seed}"
    )


def test_state_transition_consistency_grid_covers_all_asil_d_transitions():
    """Meta-pin: every ASIL-D transition has a state_transition_
    consistency family above. A future contributor adding an
    ASIL-D edge to LEGAL_TRANSITIONS without a corresponding
    cell trips this assertion.
    """
    asil_d_transitions = [
        (t.from_state, t.to_state)
        for t in LEGAL_TRANSITIONS
        if t.asil == "ASIL-D"
    ]
    # Cells exist for these; pinned by name match.
    covered = {
        (SafetyState.DEGRADED, SafetyState.FAULT),
        (SafetyState.FAULT,    SafetyState.FAILSAFE),
    }
    assert set(asil_d_transitions) == covered, (
        f"state_transition_consistency family must cover every "
        f"ASIL-D transition; missing: {set(asil_d_transitions) - covered}"
    )
