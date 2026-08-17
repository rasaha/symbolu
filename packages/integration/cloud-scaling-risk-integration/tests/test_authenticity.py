"""The recommendation authenticity boundary — the security core of Phase 4C.

These tests pin the distinction the ADR insists on and that Phase 4A/4B explicitly did
not establish: *canonical consistency* is not *source authenticity*. The critical
property proved here is that the check is **load-bearing and non-self-referential** — a
payload whose content was altered while its carried digest was left stale reconstructs
cleanly through the controller's own strict path and is then rejected here.
"""

from __future__ import annotations

import pytest

from conftest import build_abstention, build_recommendation
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
)

from ugence_cloud_scaling_risk_integration import (
    CARRIED_DIGEST_FIELD,
    AuthenticatedAbstention,
    AuthenticatedRecommendation,
    DigestExpectationSource,
    MissingIndependentDigestError,
    RecommendationAuthenticityError,
    RecommendationInputError,
    UnsupportedRecommendationSourceError,
    authenticate_controller_output,
)


# --- the carried digest is genuinely independent -------------------------------------


def test_from_dict_ignores_the_carried_digest(recommendation):
    """The premise the whole check rests on: ``from_dict`` never consumes it.

    If the controller ever started validating ``evidence_digest`` inside ``from_dict``,
    the adapter's comparison would become a restatement of a check performed one layer
    down rather than an independent one. This test pins the premise explicitly so that
    change would surface here.
    """

    document = recommendation.to_canonical_dict()
    assert CARRIED_DIGEST_FIELD in document

    tampered = dict(document)
    tampered[CARRIED_DIGEST_FIELD] = "sha256:" + "0" * 64
    # A wrong carried digest does NOT prevent reconstruction — the controller discards it.
    rebuilt = CapacityActionRecommendation.from_dict(tampered)
    assert rebuilt.digest() == document[CARRIED_DIGEST_FIELD]
    # ...which is exactly why the adapter must compare it itself.
    with pytest.raises(RecommendationAuthenticityError):
        authenticate_controller_output(tampered)


def test_serialized_form_authenticates_against_its_carried_digest(recommendation):
    result = authenticate_controller_output(recommendation.to_canonical_dict())
    assert isinstance(result, AuthenticatedRecommendation)
    assert result.recommendation_digest == recommendation.digest()
    assert result.expectation_source == DigestExpectationSource.CARRIED_CANONICAL_FORM


def test_stale_digest_after_content_tampering_is_rejected(recommendation):
    """Partial tampering: alter content, leave the carried digest stale."""

    document = dict(recommendation.to_canonical_dict())
    stale_digest = document[CARRIED_DIGEST_FIELD]
    document["recommendation_id"] = "rec-TAMPERED"

    # It still reconstructs — the record remains internally consistent...
    rebuilt = CapacityActionRecommendation.from_dict(document)
    assert rebuilt.digest() != stale_digest
    # ...and the adapter is the layer that catches it.
    with pytest.raises(RecommendationAuthenticityError, match="digest mismatch"):
        authenticate_controller_output(document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("recommendation_id", "rec-swapped"),
        ("dependency_explanation", "a rewritten rationale"),
        ("reason_codes", ["FORGED_REASON"]),
        ("selected_plan_id", "no_change"),
    ],
)
def test_each_tampered_field_with_a_stale_digest_fails_closed(recommendation, field, value):
    document = dict(recommendation.to_canonical_dict())
    document[field] = value
    with pytest.raises((RecommendationAuthenticityError, RecommendationInputError)):
        authenticate_controller_output(document)


# --- the in-process object path requires an independent expectation --------------------


def test_live_object_without_an_expectation_fails_closed(recommendation):
    """The forbidden self-referential check is refused, not silently performed."""

    with pytest.raises(MissingIndependentDigestError, match="no independent"):
        authenticate_controller_output(recommendation)


def test_live_object_with_a_matching_expectation_authenticates(recommendation):
    result = authenticate_controller_output(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert isinstance(result, AuthenticatedRecommendation)
    assert result.expectation_source == DigestExpectationSource.CALLER_SUPPLIED_EXPECTATION


def test_live_object_with_a_wrong_expectation_fails_closed(recommendation):
    with pytest.raises(RecommendationAuthenticityError, match="digest mismatch"):
        authenticate_controller_output(
            recommendation, expected_recommendation_digest="sha256:" + "a" * 64
        )


def test_expectation_of_another_recommendation_is_rejected(recommendation):
    """Digest substitution: pair one recommendation with another's digest."""

    other = build_recommendation(predicted=12, recommendation_id="rec-other")
    assert other.digest() != recommendation.digest()
    with pytest.raises(RecommendationAuthenticityError):
        authenticate_controller_output(
            recommendation, expected_recommendation_digest=other.digest()
        )


def test_both_expectations_must_agree(recommendation):
    document = recommendation.to_canonical_dict()
    other = build_recommendation(predicted=12, recommendation_id="rec-other")
    with pytest.raises(RecommendationAuthenticityError):
        authenticate_controller_output(
            document, expected_recommendation_digest=other.digest()
        )
    both = authenticate_controller_output(
        document, expected_recommendation_digest=recommendation.digest()
    )
    assert both.expectation_source == DigestExpectationSource.CARRIED_AND_CALLER_SUPPLIED


def test_serialized_form_without_a_carried_digest_and_without_an_expectation(recommendation):
    document = recommendation.to_canonical_dict(include_digest=False)
    assert CARRIED_DIGEST_FIELD not in document
    with pytest.raises(MissingIndependentDigestError):
        authenticate_controller_output(document)
    # ...but a caller-supplied expectation makes the same document authenticatable.
    assert authenticate_controller_output(
        document, expected_recommendation_digest=recommendation.digest()
    ).recommendation_digest == recommendation.digest()


# --- input-type boundary ---------------------------------------------------------------


class DuckTypedRecommendation:
    """A look-alike that answers every question the adapter might ask."""

    schema_version = "capacity-action-recommendation-1"

    def digest(self):
        return "sha256:" + "b" * 64

    def to_canonical_dict(self, include_digest=True):
        return {"schema_version": self.schema_version}


def test_duck_typed_recommendation_is_refused_at_the_type_boundary():
    with pytest.raises(UnsupportedRecommendationSourceError):
        authenticate_controller_output(
            DuckTypedRecommendation(),
            expected_recommendation_digest="sha256:" + "b" * 64,
        )


@pytest.mark.parametrize("source", [None, 42, "a string", [], object()])
def test_foreign_inputs_are_refused(source):
    with pytest.raises(UnsupportedRecommendationSourceError):
        authenticate_controller_output(source)


def test_mapping_without_a_schema_version_is_refused():
    with pytest.raises(UnsupportedRecommendationSourceError, match="schema_version"):
        authenticate_controller_output({"recommendation_id": "rec-1"})


def test_unrecognized_schema_tag_is_refused(recommendation):
    document = dict(recommendation.to_canonical_dict())
    document["schema_version"] = "capacity-action-recommendation-99"
    with pytest.raises(UnsupportedRecommendationSourceError, match="unsupported"):
        authenticate_controller_output(document)


@pytest.mark.parametrize(
    "bad", ["", "sha256:short", "SHA256:" + "a" * 64, "sha256:" + "A" * 64,
            "sha512:" + "a" * 64, 12345, True]
)
def test_malformed_digest_syntax_is_rejected(recommendation, bad):
    with pytest.raises(RecommendationAuthenticityError):
        authenticate_controller_output(
            recommendation, expected_recommendation_digest=bad
        )


# --- abstention authenticity -------------------------------------------------------------


def test_abstention_authenticates_and_stays_a_non_recommendation():
    abstention = build_abstention()
    result = authenticate_controller_output(abstention.to_canonical_dict())
    assert isinstance(result, AuthenticatedAbstention)
    assert not isinstance(result, AuthenticatedRecommendation)
    assert result.abstention_digest == abstention.digest()


def test_tampered_abstention_with_a_stale_digest_fails_closed():
    document = dict(build_abstention().to_canonical_dict())
    document["detail"] = "a rewritten explanation"
    with pytest.raises(RecommendationAuthenticityError):
        authenticate_controller_output(document)


# --- authenticating grants nothing ---------------------------------------------------------


def test_authentication_grants_no_authority(recommendation):
    result = authenticate_controller_output(recommendation.to_canonical_dict())
    for flag in ("risk_evaluated", "authority_granted", "envelope_issued",
                 "actiongate_invoked", "credential_issued", "actuation_performed",
                 "effect_verified", "executable"):
        assert getattr(result, flag) is False
