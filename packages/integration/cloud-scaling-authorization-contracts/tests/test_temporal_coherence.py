"""R-12b — the decision must agree with itself about when it expires.

The defect this closes
------------------------
``SubjectRiskDecision`` carries ``expires_at`` **twice**: once as an outer field, and once
inside ``decision_snapshot``. Only the snapshot copy is covered by a digest — Risk Authority
binds ``decision_digest == digest(to_canonical_obj(decision_snapshot))``, and canonical guard
24 re-derives that equality independently. The outer field is covered by nothing.

Phase 5A read the outer field. So a public ``dataclasses.replace`` on the exact frozen type —
no subclass, no ``object.__setattr__``, no fabricated snapshot — moved ``expires_at`` alone:
Risk Authority's own ``__post_init__`` re-ran and passed, the snapshot and its digest were
untouched, every reconciliation check still agreed, and the candidate carried the moved
instant as ``decision_expires_at_fact``.

That field is not inert downstream. Phase 5B's gate 13 decides ``CANDIDATE_DECISION_EXPIRED``
from ``decision_expires_at_fact`` **and from nothing else**, so a decision that died months ago
could be made to verify by editing the one copy nobody hashed.

Canonical guard 35 reconciles the two copies, canonicalizing the outer value with the same
public primitive the snapshot was rendered with so the comparison is byte-for-byte in the
snapshot's own spelling.

What this is not
------------------
It is a **coherence** check, not a freshness one. Phase 5A still holds no clock: a decision
that genuinely expires in an hour and one that genuinely expires in a decade both build a
candidate here, and both carry their true instant forward for Phase 5B to rule on. The two
decision-window cases below mint exactly those — an honest snapshot moved together with its
outer field and its digest re-derived — which is the difference between *stating* a window and
*forging* one.
"""

from __future__ import annotations

import dataclasses
import pathlib
import tempfile
from datetime import timedelta

import pytest
from _mutation_support import guard_condition, mutated_package

from conftest import coordinate_for
from ugence_cloud_scaling_authorization_contracts import (
    AuthorizationCandidateRejectionReason as Reason,
)
from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    ReconciliationError,
    build_capacity_authorization_candidate,
)
from ugence_cloud_scaling_authorization_contracts.canonical import (
    digest_of_snapshot,
    to_canonical_obj,
)

#: The guard under test, and the sibling a reader would most likely credit with its kill.
GUARD_EXPIRY_COHERENCE = 35
#: Guard 24 re-derives ``decision_digest`` over ``decision_snapshot``. It is the obvious
#: suspect and it is the wrong one: the attack never touches the snapshot or the digest, so
#: that equality still holds. Neutralising it must leave the attack refused.
GUARD_SNAPSHOT_REDERIVATION = 24

EXPECTED_CONDITIONS = {
    GUARD_EXPIRY_COHERENCE: (
        "to_canonical_obj(decision_expires_at) != snapshot_expires_at"
    ),
    GUARD_SNAPSHOT_REDERIVATION: "recomputed != d_decision_digest",
}


def test_the_canonical_guard_numbers_still_name_these_conditions():
    """Anchor the inventory before any mutation is aimed by number."""

    for number, condition in EXPECTED_CONDITIONS.items():
        assert guard_condition(number) == condition, (
            f"canonical guard {number} now reads {guard_condition(number)!r}; the "
            "mutations below are aimed at the wrong line"
        )


# ======================================================================================
# Minting decisions: one honest, one forged
# ======================================================================================
def _honest_expiry(decision, moment):
    """A decision that genuinely expires at ``moment`` — both copies moved, digest re-derived.

    This is what a real Risk Authority issuing a shorter- or longer-lived decision produces:
    the snapshot records the instant, ``decision_digest`` covers that snapshot, and the outer
    field restates it. ``dataclasses.replace`` re-runs Risk Authority's ``__post_init__``, so
    the result has passed its own construction checks — including the snapshot/digest binding.
    """

    snapshot = dict(decision.decision_snapshot)
    snapshot["expires_at"] = to_canonical_obj(moment)
    return dataclasses.replace(
        decision,
        expires_at=moment,
        decision_snapshot=snapshot,
        decision_digest=digest_of_snapshot(snapshot),
    )


def _moved_outer_expiry(decision, moment):
    """The R-12b attack: the outer field alone, through the ordinary public constructor."""

    return dataclasses.replace(decision, expires_at=moment)


def _build(projection, decision, attestation, target_scope, policy_binding):
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=attestation,
        policy_binding=policy_binding,
        policy_coordinate_binding=coordinate_for(policy_binding),
        target_scope=target_scope,
    )


# ======================================================================================
# The defect, refused
# ======================================================================================
def test_a_decision_whose_outer_expiry_was_moved_is_refused(
    projection, decision, attestation, target_scope, policy_binding
):
    """R-12b: the outer ``expires_at`` is extended by a decade; nothing else is touched.

    Every check that a reader might expect to fire is asserted to still agree, so the refusal
    can only come from the coherence gate.
    """

    revived = _moved_outer_expiry(decision, decision.expires_at + timedelta(days=3650))

    # The forged decision is internally valid by Risk Authority's own rules.
    assert type(revived) is type(decision)
    assert revived.decision_snapshot == decision.decision_snapshot
    assert revived.decision_digest == decision.decision_digest
    assert revived.decision_digest == digest_of_snapshot(revived.decision_snapshot)
    assert revived.tenant_id == projection.tenant_id
    assert revived.request_digest == projection.request_digest
    assert revived.subject_digest == projection.subject_digest
    assert revived.expires_at != decision.expires_at

    built = "sentinel"
    with pytest.raises(ReconciliationError) as exc:
        built = _build(projection, revived, attestation, target_scope, policy_binding)

    assert built == "sentinel", "the builder returned across a refusal"
    assert not isinstance(built, CapacityAuthorizationCandidate)
    assert exc.value.reason is Reason.DECISION_EXPIRY_MISMATCH
    assert "disagrees with the digest-bound copy" in str(exc.value)
    # The refusal names both instants, so a reader can see which copy was edited.
    assert to_canonical_obj(revived.expires_at) in str(exc.value)
    assert decision.decision_snapshot["expires_at"] in str(exc.value)


def test_the_attack_works_in_both_directions(
    projection, decision, attestation, target_scope, policy_binding
):
    """Shortening the outer field is refused too.

    Extending it revives a dead decision, which is the dangerous direction. Shortening it
    would let a caller retire a live one early. Neither is the decision Risk Authority made,
    and the gate is an equality rather than an ordering so it does not have to choose.
    """

    retired = _moved_outer_expiry(decision, decision.expires_at - timedelta(seconds=1))
    with pytest.raises(ReconciliationError) as exc:
        _build(projection, retired, attestation, target_scope, policy_binding)
    assert exc.value.reason is Reason.DECISION_EXPIRY_MISMATCH


def test_the_coherence_gate_is_the_only_thing_refusing_it(tmp_path, projection, decision):
    """Attribution: removing guard 35 admits; removing the digest re-derivation does not.

    The first half is the finding itself, made executable — with the coherence gate gone, the
    attack reaches candidate construction and the candidate carries the revived instant into
    the field Phase 5B's gate 13 reads. The second half rules out the sibling: guard 24 is
    intact throughout the admission, so the digest re-derivation never had a chance of
    catching this, and neutralising *it* instead leaves the attack refused.
    """

    revived_at = decision.expires_at + timedelta(days=3650)
    revived = _moved_outer_expiry(decision, revived_at)

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_EXPIRY_COHERENCE)
        candidate = mp.build(projection, revived)
    assert type(candidate).__name__ == "CapacityAuthorizationCandidate"
    # The admission is the dangerous part: the candidate carries the revived instant, and
    # nothing downstream of it can tell that the snapshot says otherwise.
    assert candidate.decision_expires_at_fact == revived_at
    assert candidate.decision_snapshot_digest == decision.decision_digest

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_SNAPSHOT_REDERIVATION)
        with pytest.raises(Exception) as exc:
            mp.build(projection, revived)
    assert "guard neutralised" not in str(exc.value)
    # Compared by value: the mutated copy has its own enum class, so identity would be
    # False even for the same member.
    assert getattr(getattr(exc.value, "reason", None), "value", None) == (
        Reason.DECISION_EXPIRY_MISMATCH.value
    )


# ======================================================================================
# The two decision windows, minted honestly
# ======================================================================================
def test_an_honestly_shortened_decision_window_still_builds(
    projection, decision, attestation, target_scope, policy_binding
):
    """A decision that genuinely expires a second after it was evaluated is admitted.

    Phase 5A holds no clock, so "nearly expired" is not its question. What it enforces is that
    the window the candidate carries forward is the window the decision actually states — and
    here it is, in the snapshot the digest covers.
    """

    short_at = decision.evaluated_at + timedelta(seconds=1)
    short = _honest_expiry(decision, short_at)
    assert short.decision_snapshot["expires_at"] == to_canonical_obj(short_at)
    assert short.decision_digest != decision.decision_digest, "an honest mint moves the digest"

    candidate = _build(projection, short, attestation, target_scope, policy_binding)
    assert candidate.decision_expires_at_fact == short_at
    assert candidate.decision_snapshot_digest == short.decision_digest
    # And Phase 5A still endorses nothing about it.
    assert candidate.grants_authority is False


def test_an_honestly_extended_decision_window_still_builds(
    projection, decision, attestation, target_scope, policy_binding
):
    """The same decade the forged attack asks for, stated honestly, is admitted.

    This is the pair the gate turns on: the instant is identical to the one refused above, and
    the only difference is whether the decision's own digest-bound record says it. A window
    Risk Authority states is Phase 5B's to judge; a window a caller invents is not a window.
    """

    long_at = decision.expires_at + timedelta(days=3650)
    honest = _honest_expiry(decision, long_at)
    forged = _moved_outer_expiry(decision, long_at)
    assert honest.expires_at == forged.expires_at

    candidate = _build(projection, honest, attestation, target_scope, policy_binding)
    assert candidate.decision_expires_at_fact == long_at
    assert candidate.decision_snapshot_digest == honest.decision_digest


def test_the_gate_compares_instants_not_spellings(
    projection, decision, attestation, target_scope, policy_binding
):
    """The same instant in another timezone is the same instant, and is admitted.

    ``to_canonical_obj`` normalizes to UTC before formatting, so an outer field carrying
    ``+02:00`` still renders as the snapshot's bytes. The gate must not become an accidental
    tzinfo check — that job belongs to guard 3, which has its own attribution proof.
    """

    from datetime import timezone

    elsewhere = decision.expires_at.astimezone(timezone(timedelta(hours=2)))
    assert elsewhere.utcoffset() != decision.expires_at.utcoffset()
    shifted = _moved_outer_expiry(decision, elsewhere)

    candidate = _build(projection, shifted, attestation, target_scope, policy_binding)
    assert candidate.decision_expires_at_fact == decision.expires_at
