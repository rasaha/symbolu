"""The outcome vocabulary is closed, total over the authority's reasons, and fails closed."""

from __future__ import annotations

import pytest

from ugence_policy_authority.api import PolicyResolutionReason

from ugence_cloud_scaling_policy_authenticity import (
    REFUSAL_OUTCOMES,
    RESOLUTION_REASON_OUTCOMES,
    TEMPORAL_OUTCOMES,
    PolicyAuthenticityOutcome as O,
    resolution_reason_outcome,
)


@pytest.mark.invariant
def test_exactly_one_member_is_a_success():
    assert REFUSAL_OUTCOMES == frozenset(m for m in O if m is not O.VERIFIED)
    assert O.VERIFIED not in REFUSAL_OUTCOMES
    assert len(REFUSAL_OUTCOMES) == len(list(O)) - 1


@pytest.mark.invariant
def test_the_reason_mapping_is_total_over_the_authority_s_refusals():
    refusals = {r for r in PolicyResolutionReason if r is not PolicyResolutionReason.RESOLVED}
    assert set(RESOLUTION_REASON_OUTCOMES) == refusals


@pytest.mark.invariant
def test_the_reason_mapping_is_injective_so_no_refusal_is_collapsed_into_another():
    values = list(RESOLUTION_REASON_OUTCOMES.values())
    assert len(set(values)) == len(values)


@pytest.mark.adversarial
def test_no_authority_reason_maps_to_the_success_member():
    assert O.VERIFIED not in set(RESOLUTION_REASON_OUTCOMES.values())
    assert PolicyResolutionReason.RESOLVED not in RESOLUTION_REASON_OUTCOMES
    # Including the success reason itself: a lookup is never a route to VERIFIED.
    assert resolution_reason_outcome(PolicyResolutionReason.RESOLVED) is O.INDETERMINATE


@pytest.mark.adversarial
@pytest.mark.parametrize("unknown", ["RESOLVED", None, 0, object(), "A_FUTURE_REASON"])
def test_an_unrecognised_reason_fails_closed(unknown):
    assert resolution_reason_outcome(unknown) is O.INDETERMINATE
    assert O.INDETERMINATE in REFUSAL_OUTCOMES


@pytest.mark.invariant
def test_the_temporal_outcomes_are_named_because_r2_is_open():
    """R-2: whose clock supplies ``as_of`` is unsettled. These are the members it can move."""

    assert TEMPORAL_OUTCOMES <= REFUSAL_OUTCOMES
    assert O.NOT_YET_EFFECTIVE in TEMPORAL_OUTCOMES
    assert O.EXPIRED in TEMPORAL_OUTCOMES
    assert O.REVOKED in TEMPORAL_OUTCOMES


@pytest.mark.invariant
def test_there_is_no_member_meaning_probably_fine():
    forbidden = ("UNCHECKED", "TRUSTED_TRANSPORT", "ASSUMED", "PROBABLY", "SKIPPED", "WARN")
    for member in O:
        for word in forbidden:
            assert word not in member.value


# --------------------------------------------------------------------------- #
# The terminal handler classifies rather than flattens
# --------------------------------------------------------------------------- #
@pytest.mark.invariant
def test_every_typed_error_keeps_its_member_through_the_terminal_handler():
    """"could not run" and "ran, and the artifact is bad" are different facts.

    Flattening every escaping exception to ``VERIFICATION_UNAVAILABLE`` would tell a caller
    the first when what happened was the second. Each of this package's errors already
    carries the member it means, so the terminal consults it.
    """

    from ugence_cloud_scaling_policy_authenticity import (
        PolicyAuthenticityConfigurationError,
        PolicyAuthenticityExactTypeError,
        PolicyAuthenticityFieldError,
        VerifiedPolicyArtifactIntegrityError,
    )
    from ugence_cloud_scaling_policy_authenticity.verification import _terminal_outcome

    expected = {
        PolicyAuthenticityFieldError("f"): O.COORDINATE_MALFORMED,
        PolicyAuthenticityExactTypeError("t"): O.UNSUPPORTED_EXACT_TYPE,
        VerifiedPolicyArtifactIntegrityError("i"): O.INVARIANT_VIOLATION,
        PolicyAuthenticityConfigurationError("c"): O.VERIFICATION_UNAVAILABLE,
    }
    for error, member in expected.items():
        assert _terminal_outcome(error) is member


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("a collaborator failed"),
        ValueError("a stdlib error"),
        KeyError("a programming failure"),
    ],
)
def test_a_foreign_exception_is_unavailable_not_classified(exc):
    from ugence_cloud_scaling_policy_authenticity.verification import _terminal_outcome

    assert _terminal_outcome(exc) is O.VERIFICATION_UNAVAILABLE


@pytest.mark.adversarial
def test_an_exception_claiming_the_success_member_never_becomes_a_success():
    """An ``outcome`` attribute is attacker-influenceable in principle. It cannot say VERIFIED."""

    from ugence_cloud_scaling_policy_authenticity import (
        CloudScalingPolicyAuthenticityError,
    )
    from ugence_cloud_scaling_policy_authenticity.verification import _terminal_outcome

    claiming = CloudScalingPolicyAuthenticityError("mine", O.VERIFIED)
    assert _terminal_outcome(claiming) is O.VERIFICATION_UNAVAILABLE

    class Impostor(CloudScalingPolicyAuthenticityError):
        pass

    impostor = Impostor("mine")
    impostor.outcome = "VERIFIED"  # a bare string, not a member
    assert _terminal_outcome(impostor) is O.VERIFICATION_UNAVAILABLE
