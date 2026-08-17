"""The ratified ADR §28 evidence lifecycle relation.

Exhaustive over the full 5x5 state product: every admissible arrow is accepted
and every one of the remaining pairs is refused, so the relation is proved
closed rather than sampled.
"""

from __future__ import annotations

import itertools

import pytest
from _builders import identity
from ugence_trusted_evidence_authority.api import (
    EVIDENCE_LIFECYCLE_TRANSITIONS,
    EvidenceLifecycleState,
    TrustedEvidenceLifecycleError,
    TrustedEvidenceRefusalReason,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

S = EvidenceLifecycleState

ADMISSIBLE = {
    (S.PRODUCED, S.SUBMITTED),
    (S.PRODUCED, S.EXPIRED),
    (S.PRODUCED, S.REVOKED),
    (S.SUBMITTED, S.RETAINED),
    (S.SUBMITTED, S.EXPIRED),
    (S.SUBMITTED, S.REVOKED),
    (S.RETAINED, S.EXPIRED),
    (S.RETAINED, S.REVOKED),
}

ALL_PAIRS = set(itertools.product(S, S))


@pytest.mark.parametrize("pair", sorted(ALL_PAIRS, key=lambda p: (p[0].value, p[1].value)))
def test_the_transition_relation_is_exactly_the_ratified_set(pair):
    current, proposed = pair
    expected = pair in ADMISSIBLE
    assert is_valid_lifecycle_transition(current, proposed) is expected


@pytest.mark.parametrize("pair", sorted(ALL_PAIRS - ADMISSIBLE, key=lambda p: (p[0].value, p[1].value)))
def test_every_inadmissible_transition_raises_with_the_typed_reason(pair):
    current, proposed = pair
    with pytest.raises(TrustedEvidenceLifecycleError) as excinfo:
        require_valid_lifecycle_transition(current, proposed)
    assert (
        excinfo.value.reason
        is TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION
    )


@pytest.mark.parametrize("pair", sorted(ADMISSIBLE, key=lambda p: (p[0].value, p[1].value)))
def test_every_admissible_transition_is_accepted(pair):
    require_valid_lifecycle_transition(*pair)


@pytest.mark.parametrize("state", list(S))
def test_no_state_transitions_to_itself(state):
    assert is_valid_lifecycle_transition(state, state) is False


@pytest.mark.parametrize("terminal", [S.EXPIRED, S.REVOKED])
def test_terminal_states_have_no_outgoing_arrows(terminal):
    assert EVIDENCE_LIFECYCLE_TRANSITIONS[terminal] == frozenset()
    for proposed in S:
        assert is_valid_lifecycle_transition(terminal, proposed) is False


def test_revoked_cannot_be_undone():
    for proposed in (S.PRODUCED, S.SUBMITTED, S.RETAINED):
        with pytest.raises(TrustedEvidenceLifecycleError):
            require_valid_lifecycle_transition(S.REVOKED, proposed)


def test_the_relation_mapping_is_read_only():
    with pytest.raises(TypeError):
        EVIDENCE_LIFECYCLE_TRANSITIONS[S.REVOKED] = frozenset({S.RETAINED})
    for value in EVIDENCE_LIFECYCLE_TRANSITIONS.values():
        assert isinstance(value, frozenset)
        with pytest.raises(AttributeError):
            value.add(S.PRODUCED)


def test_the_relation_covers_every_state():
    assert set(EVIDENCE_LIFECYCLE_TRANSITIONS) == set(S)


# --------------------------------------------------------------------------- #
# The vocabulary itself
# --------------------------------------------------------------------------- #

def test_the_lifecycle_vocabulary_is_exactly_the_ratified_states():
    assert [s.value for s in S] == [
        "PRODUCED",
        "SUBMITTED",
        "RETAINED",
        "EXPIRED",
        "REVOKED",
    ]


def test_there_is_no_verified_lifecycle_state():
    """ADR §10.2 — a ``VERIFIED`` label on the artifact is an enumerated non-proof."""

    assert not any("VERIF" in s.value for s in S)
    assert not hasattr(S, "VERIFIED")


def test_there_is_no_supersession_lifecycle_state():
    """The ratified *evidence* lifecycle (§28) has no supersession arrow."""

    assert not any("SUPERSED" in s.value for s in S)
    assert not any(
        "SUPERSED" in r.value for r in TrustedEvidenceRefusalReason
    ), "no evidence-supersession refusal code may exist without a ratified arrow"


def test_state_values_are_unique_and_uppercase():
    values = [s.value for s in S]
    assert len(set(values)) == len(values)
    assert all(v == v.upper() for v in values)


# --------------------------------------------------------------------------- #
# States on the artifact
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("state", list(S))
def test_every_state_is_constructible_for_audit_including_revoked(state):
    """Being representable is not being admissible."""

    ident = identity(lifecycle_state=state)
    assert ident.lifecycle_state is state
    # ... and carrying any label still proves nothing.
    assert ident.authenticity_verified is False
    assert ident.unestablished_trust_stages


def test_the_lifecycle_state_is_load_bearing_in_the_digest():
    digests = {identity(lifecycle_state=s).canonical_digest() for s in S}
    assert len(digests) == len(list(S))


def test_a_lookalike_state_is_refused_by_the_relation():
    class Fake:
        value = "PRODUCED"

    with pytest.raises(TrustedEvidenceLifecycleError):
        is_valid_lifecycle_transition(Fake(), S.SUBMITTED)
    with pytest.raises(TrustedEvidenceLifecycleError):
        is_valid_lifecycle_transition(S.PRODUCED, "SUBMITTED")
