"""R-12 — the attestation's instant must cohere with the Phase 4 facts beside it.

What this closes, and what it does not
--------------------------------------
Gate 13 (5B-2) compares each of the candidate's six carried instants against an injected
``as_of`` and **never against another**. So an attestation stamped a year before the subject
assertion it attests to reached ``VERIFIED``: every instant was individually consistent with
the moment of verification, and the pair was inconsistent with itself. Internal incoherence
is not staleness, no downstream instant can reveal it, and the builder is the only place that
holds all six — so the refusal is a construction-time one.

**This is not a freshness gate and it reads no clock.** Both sides of each comparison are
facts the builder already holds. ``test_time_authority.py`` still proves the package imports
no clock, accepts no ``now`` and refuses nothing for being old — including, positively, that
a decision which expired a decade ago still builds a candidate.

Why exactly two comparisons
----------------------------
Every other ordering among the six is already an invariant of the source that produces it,
and duplicating an upstream invariant here would create a second, drift-prone definition of
it:

* ``valid_from <= asserted_at <= valid_until`` — refused by Risk Authority's
  ``SubjectContext.__post_init__`` (``risk_authority/integrations/evaluation_contracts.py``),
  and the cloud-scaling adapter sets ``valid_from`` *equal* to ``asserted_at``
  (``ugence_cloud_scaling_risk_integration/projection.py``) over a strictly positive
  ``validity_seconds`` (``ugence_cloud_scaling_controller/planning/recommendation.py``).
* ``valid_from <= evaluated_at <= valid_until`` — the v2 seam refuses the request as
  ``EXPIRED_SUBJECT`` outside that window *before* stamping the decision it returns, so the
  instant that becomes ``evaluated_at`` is the one that passed the gate
  (``risk_authority/api/evaluation_seam.py``).
* ``evaluated_at < expires_at`` — Decision Authority issues ``expires_at = now + ttl`` over a
  positive default TTL (``risk_authority/services/decision_authority.py``).

``attestation.issued_at`` is the one instant **no** upstream contract relates to any other:
5B-0A §11 declines to judge it at all, carrying it forward for a later phase to bound. That
is precisely why it is the instant a candidate can state incoherently, and why the two
ratified comparisons are the whole of R-12.

The third pair the owner was offered — ``issued_at <= subject_valid_until`` — was declined,
and ``test_the_declined_pair_is_already_implied`` records that the ratified evaluation bound
subsumes it in every chain the seam admits.
"""

from __future__ import annotations

import inspect
import pathlib
import tempfile

import pytest

from conftest import build_attestation, coordinate_for

from _mutation_support import mutated_package

from ugence_cloud_scaling_authorization_contracts import (
    AuthorizationCandidateRejectionReason as Reason,
)
from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    ProducerAttestationError,
    build_capacity_authorization_candidate,
)

#: The canonical guard inventory's numbers for the two R-12 comparisons, and the sibling a
#: reader might otherwise credit with their kills. Asserted below rather than trusted.
GUARD_BEFORE_ASSERTION = 36
GUARD_AFTER_EVALUATION = 37
GUARD_ATTESTATION_BINDING = 35

EXPECTED_CONDITIONS = {
    GUARD_BEFORE_ASSERTION: "a_issued_at < facts.subject_asserted_at",
    GUARD_AFTER_EVALUATION: "a_issued_at > facts.decision_evaluated_at",
    GUARD_ATTESTATION_BINDING: "a_recommendation_digest != facts.recommendation_digest",
}


def test_the_canonical_guard_numbers_still_name_these_conditions():
    """Anchor the inventory before any mutation below is aimed by number."""

    from _mutation_support import guard_condition

    for number, condition in EXPECTED_CONDITIONS.items():
        assert guard_condition(number) == condition, (
            f"canonical guard {number} now reads {guard_condition(number)!r}; the mutations "
            f"below are aimed at the wrong line"
        )


def _refused(projection, decision, target_scope, policy_binding, *, issued_at):
    """Submit an otherwise-perfect candidate whose attestation instant is the only fault."""

    attestation = build_attestation(
        recommendation_digest=projection.recommendation_digest, issued_at=issued_at
    )
    # Nothing else can absorb the refusal: the attestation binds this very recommendation,
    # so the sibling gate above it cannot fire, and the instant is genuinely signed over —
    # ``build_attestation`` signs the canonical payload including ``issued_at``.
    assert attestation.recommendation_digest == projection.recommendation_digest
    assert attestation.issued_at == issued_at

    built = "sentinel"
    with pytest.raises(ProducerAttestationError) as exc:
        built = build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=attestation,
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )

    assert built == "sentinel", "the builder returned across a refusal"
    assert not isinstance(built, CapacityAuthorizationCandidate)
    assert exc.value.reason is Reason.ATTESTATION_INSTANT_INCOHERENT
    # The refusal is not the recommendation-binding one, which shares the input artifact.
    assert exc.value.reason is not Reason.PRODUCER_ATTESTATION_CONTENT_MISMATCH
    assert "binds a different recommendation_digest" not in str(exc.value)
    # No clock could have entered: the builder has no parameter through which one arrives.
    assert set(inspect.signature(build_capacity_authorization_candidate).parameters) == {
        "projection", "decision", "producer_attestation", "policy_binding",
        "policy_coordinate_binding", "target_scope",
    }
    return exc.value


# ======================================================================================
# The refusals
# ======================================================================================


def test_an_attestation_issued_before_the_subject_assertion_is_refused(
    projection, decision, attestation, target_scope, policy_binding
):
    """R-12 verbatim: the year-early attestation the 5B-2 review found reaching VERIFIED.

    An attestation is a statement *about* a recommendation. One signed a year before that
    recommendation existed is not evidence for it under any clock, which is what makes this
    readable at construction rather than a question for Phase 5B.
    """

    from datetime import timedelta

    year_early = projection.asserted_at - timedelta(days=365)
    error = _refused(
        projection, decision, target_scope, policy_binding, issued_at=year_early
    )
    assert "before the subject was asserted" in str(error)
    assert year_early.isoformat() in str(error)
    assert projection.asserted_at.isoformat() in str(error)


def test_an_attestation_issued_after_the_decision_evaluation_is_refused(
    projection, decision, attestation, target_scope, policy_binding
):
    """The other end. The producer signs at the Controller output boundary, upstream of the
    evaluation; an attestation minted after the decision was evaluated cannot be the evidence
    that evaluation saw, whatever it says about the recommendation.
    """

    from datetime import timedelta

    too_late = decision.evaluated_at + timedelta(seconds=1)
    error = _refused(projection, decision, target_scope, policy_binding, issued_at=too_late)
    assert "after the decision was evaluated" in str(error)
    assert decision.evaluated_at.isoformat() in str(error)


@pytest.mark.parametrize("guard", [GUARD_BEFORE_ASSERTION, GUARD_AFTER_EVALUATION])
def test_each_refusal_belongs_to_its_own_guard_and_to_no_other(
    tmp_path, projection, decision, guard
):
    """Admission and misattribution proof, from the real source with one ``if`` removed.

    With the guard under test neutralised — and nothing else changed — the incoherent pair
    reaches candidate construction, so the test above really measures that comparison. With
    the *sibling* attestation gate neutralised instead, the same pair is still refused, so
    the kill cannot be credited to the recommendation-binding check beside it.
    """

    from datetime import timedelta

    incoherent = (
        projection.asserted_at - timedelta(days=365)
        if guard == GUARD_BEFORE_ASSERTION
        else decision.evaluated_at + timedelta(seconds=1)
    )

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), guard)
        candidate = mp.build(projection, decision, attestation_issued_at=incoherent)
    assert type(candidate).__name__ == "CapacityAuthorizationCandidate"
    assert candidate.attestation_issued_at_fact == incoherent

    with tempfile.TemporaryDirectory(dir=tmp_path) as td:
        mp = mutated_package(pathlib.Path(td), GUARD_ATTESTATION_BINDING)
        with pytest.raises(Exception) as exc:
            mp.build(projection, decision, attestation_issued_at=incoherent)
    assert "guard neutralised" not in str(exc.value)
    # By value, not identity: the mutated copy is a separate module with its own enum class.
    assert exc.value.reason.value == Reason.ATTESTATION_INSTANT_INCOHERENT.value


# ======================================================================================
# The admissions — the gate refuses incoherence and nothing else
# ======================================================================================


def test_the_bounds_are_inclusive_at_the_assertion_instant(
    projection, decision, target_scope, policy_binding
):
    """``issued_at == asserted_at`` is coherent, and is what the real chain produces: the
    adapter takes ``asserted_at`` from ``recommendation_time``, and the producer signs that
    same recommendation at the Controller's output boundary. A strict comparison here would
    refuse the ordinary case.
    """

    candidate = build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=build_attestation(
            recommendation_digest=projection.recommendation_digest,
            issued_at=projection.asserted_at,
        ),
        policy_binding=policy_binding,
        policy_coordinate_binding=coordinate_for(policy_binding),
        target_scope=target_scope,
    )
    assert candidate.attestation_issued_at_fact == projection.asserted_at
    assert candidate.grants_authority is False


def test_the_bounds_are_inclusive_at_the_evaluation_instant(
    projection, decision, target_scope, policy_binding
):
    """``issued_at == evaluated_at`` is coherent: signing and evaluating in the same instant
    is a race the ordering does not forbid, and forbidding it would be a claim about clock
    resolution that nothing ratifies.
    """

    candidate = build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=build_attestation(
            recommendation_digest=projection.recommendation_digest,
            issued_at=decision.evaluated_at,
        ),
        policy_binding=policy_binding,
        policy_coordinate_binding=coordinate_for(policy_binding),
        target_scope=target_scope,
    )
    assert candidate.attestation_issued_at_fact == decision.evaluated_at


def test_the_declined_pair_is_already_implied(projection, decision):
    """Ruling 3 — ``issued_at <= subject_valid_until`` — was declined, and loses nothing.

    The v2 seam admits an evaluation only *inside* the subject window, so in every chain
    Phase 5A can receive, ``evaluated_at <= valid_until``. The ratified evaluation bound is
    therefore at least as tight as the declined one at all times, and a candidate that
    violates the declined pair violates the ratified one first. Recorded as a test so a
    later reader does not re-open the pair believing it left a hole.
    """

    assert projection.asserted_at <= decision.evaluated_at <= projection.valid_until
