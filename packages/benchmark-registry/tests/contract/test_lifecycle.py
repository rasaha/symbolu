"""The ADR §29 lifecycle relation is closed, and every pair is tested.

The full 4x4 matrix: three admissible arrows and thirteen refusals, each
asserted individually rather than by a rule that could itself be wrong.
"""

from __future__ import annotations

import itertools

import pytest
from ugence_benchmark_registry.api import (
    BENCHMARK_LIFECYCLE_ORDER,
    BENCHMARK_LIFECYCLE_TRANSITIONS,
    BENCHMARK_TERMINAL_LIFECYCLE_STATES,
    BenchmarkLifecycleError,
    BenchmarkLifecycleState,
    BenchmarkRefusalReason,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

_S = BenchmarkLifecycleState

#: The complete ratified relation, written out independently of the package's
#: own constant so the two must agree.
ADMISSIBLE = {
    (_S.AUTHORED, _S.APPROVED),
    (_S.APPROVED, _S.REGISTERED),
    (_S.REGISTERED, _S.REVOKED),
}

ALL_PAIRS = list(itertools.product(_S, _S))


def test_the_vocabulary_is_exactly_the_four_ratified_states():
    assert [m.value for m in _S] == ["AUTHORED", "APPROVED", "REGISTERED", "REVOKED"]


def test_no_superseded_state_exists():
    """§17.12 admits supersession only through a structured successor (DD-4)."""

    assert "SUPERSEDED" not in {m.value for m in _S}
    assert not any("supersede" in m.value.lower() for m in _S)


def test_no_expired_state_exists():
    """Expiry is temporal, not a state — no clock-driven mutation (§22.9)."""

    assert "EXPIRED" not in {m.value for m in _S}


def test_the_declared_order_matches_the_enum_order():
    assert list(BENCHMARK_LIFECYCLE_ORDER) == list(_S)


def test_the_relation_covers_every_state_as_a_key():
    assert set(BENCHMARK_LIFECYCLE_TRANSITIONS) == set(_S)


def test_the_relation_matches_the_independently_written_arrow_set():
    derived = {
        (current, proposed)
        for current, admissible in BENCHMARK_LIFECYCLE_TRANSITIONS.items()
        for proposed in admissible
    }
    assert derived == ADMISSIBLE


@pytest.mark.parametrize("current,proposed", ALL_PAIRS)
def test_every_pair_in_the_matrix(current, proposed):
    expected = (current, proposed) in ADMISSIBLE
    assert is_valid_lifecycle_transition(current, proposed) is expected
    if expected:
        require_valid_lifecycle_transition(current, proposed)
    else:
        with pytest.raises(BenchmarkLifecycleError) as excinfo:
            require_valid_lifecycle_transition(current, proposed)
        assert (
            excinfo.value.reason
            is BenchmarkRefusalReason.BENCHMARK_INVALID_LIFECYCLE_TRANSITION
        )


@pytest.mark.parametrize("state", list(_S))
def test_no_state_transitions_to_itself(state):
    assert is_valid_lifecycle_transition(state, state) is False


def test_the_terminal_set_is_derived_from_the_relation():
    derived = frozenset(
        state
        for state, admissible in BENCHMARK_LIFECYCLE_TRANSITIONS.items()
        if not admissible
    )
    assert derived == BENCHMARK_TERMINAL_LIFECYCLE_STATES
    assert derived == frozenset({_S.REVOKED})


def test_nothing_leaves_revoked():
    for proposed in _S:
        assert is_valid_lifecycle_transition(_S.REVOKED, proposed) is False


def test_the_relation_cannot_be_widened_after_import():
    with pytest.raises(TypeError):
        BENCHMARK_LIFECYCLE_TRANSITIONS[_S.REVOKED] = frozenset({_S.REGISTERED})
    for admissible in BENCHMARK_LIFECYCLE_TRANSITIONS.values():
        assert isinstance(admissible, frozenset)
        with pytest.raises(AttributeError):
            admissible.add(_S.REGISTERED)


@pytest.mark.parametrize("bad", ["AUTHORED", 0, None, object()])
def test_a_lookalike_state_is_refused(bad):
    with pytest.raises(BenchmarkLifecycleError):
        is_valid_lifecycle_transition(bad, _S.APPROVED)
    with pytest.raises(BenchmarkLifecycleError):
        is_valid_lifecycle_transition(_S.AUTHORED, bad)


def test_a_subclassed_state_is_refused():
    class Sneaky(str):
        value = "AUTHORED"

    with pytest.raises(BenchmarkLifecycleError):
        is_valid_lifecycle_transition(Sneaky("AUTHORED"), _S.APPROVED)


def test_the_refusal_message_names_the_admissible_next_states():
    with pytest.raises(BenchmarkLifecycleError) as excinfo:
        require_valid_lifecycle_transition(_S.AUTHORED, _S.REGISTERED)
    assert "APPROVED" in str(excinfo.value)

    with pytest.raises(BenchmarkLifecycleError) as excinfo:
        require_valid_lifecycle_transition(_S.REVOKED, _S.REGISTERED)
    assert "terminal" in str(excinfo.value)


def test_the_relation_reads_no_clock():
    """A pure predicate: the same pair answers the same way, always."""

    for _ in range(3):
        assert is_valid_lifecycle_transition(_S.AUTHORED, _S.APPROVED) is True
        assert is_valid_lifecycle_transition(_S.AUTHORED, _S.REVOKED) is False


def test_the_six_stage_registration_ordering_is_not_implemented_here():
    """§16.2's six stages are BR-2's admission ordering, not BR-1's lifecycle.

    Asserted as an absence: no vocabulary in this package names a registration
    stage, so the two models cannot be confused in code.
    """

    import ugence_benchmark_registry as pkg

    banned = ("STAGE", "ADMISSION", "ORDERING", "STRUCTURAL_VALIDATION",
              "DIGEST_VERIFICATION", "PUBLISHER_VERIFICATION")
    for name in pkg.__all__:
        assert not any(token in name.upper() for token in banned), name
    for state in _S:
        assert not any(token in state.value for token in banned), state
