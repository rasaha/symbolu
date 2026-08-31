"""F-1 remediation: in-process admission is by **exact type**, not ``isinstance``.

The finding. Admission previously used ``isinstance``, so a *subclass* of
``CapacityActionRecommendation`` was accepted. Because every value the adapter goes on to
read is reached through dynamic dispatch, a subclass overriding ``digest()`` had its
attacker-chosen value adopted as the authenticated ``recommendation_digest`` — the one
value the whole authenticity boundary exists to establish.

Why the obvious partial fix is insufficient, and why these tests check *call counts*
rather than only the returned error: calling the base method unbound
(``CapacityActionRecommendation.digest(source)``) still routes through
``self.to_canonical_dict()`` and ``self._digest_payload()``, so an override further down
the chain is reached anyway. The correction is therefore exact-type admission **before
any attribute of the object is touched**, and the only way to demonstrate that is to
prove the overrides were never invoked — an error alone would not distinguish "refused
before dispatch" from "dispatched, then refused".

Every case below therefore asserts both halves: the rejection, and that nothing on the
hostile object ran.
"""

from __future__ import annotations

import pytest

from conftest import INSIDE_WINDOW, RecordingSeam, build_abstention, fixed_clock, reference_seam
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
    RecommendationAbstention,
)

from ugence_cloud_scaling_risk_integration import (
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    AuthenticatedRecommendation,
    CloudScalingRiskAdapter,
    UnsupportedRecommendationSourceError,
    authenticate_controller_output,
)

ATTACKER_DIGEST = "sha256:" + "9" * 64


def _fields(instance):
    return {f.name: getattr(instance, f.name) for f in instance.__dataclass_fields__.values()}


# --- hostile subclasses, each overriding a different dispatch point ---------------------


def make_subclass(recommendation, *, overrides: tuple[str, ...], mode: str = "count"):
    """Build a subclass overriding ``overrides``, recording or reacting to any call.

    ``mode='count'`` records each invocation; ``mode='raise'`` makes any invocation an
    immediate, unmistakable test failure.
    """

    calls: list[str] = []

    def _record(name):
        def _hook(self, *args, **kwargs):
            calls.append(name)
            if mode == "raise":
                raise AssertionError(
                    f"{name} was invoked on a subclass that should have been refused "
                    "before any attribute was touched"
                )
            if name == "digest":
                return ATTACKER_DIGEST
            if name == "to_canonical_dict":
                return {"schema_version": "capacity-action-recommendation-1"}
            return {}

        return _hook

    namespace = {name: _record(name) for name in overrides}
    subclass = type("HostileRecommendation", (CapacityActionRecommendation,), namespace)
    return subclass(**_fields(recommendation)), calls


DISPATCH_POINTS = [
    pytest.param(("digest",), id="digest"),
    pytest.param(("to_canonical_dict",), id="to_canonical_dict"),
    pytest.param(("_digest_payload",), id="digest-payload-helper"),
    pytest.param(("digest", "to_canonical_dict"), id="digest+serializer"),
    pytest.param(
        ("digest", "to_canonical_dict", "_digest_payload"), id="all-three-simultaneously"
    ),
]


@pytest.mark.parametrize("overrides", DISPATCH_POINTS)
def test_a_subclass_is_refused_without_invoking_any_override(recommendation, overrides):
    hostile, calls = make_subclass(recommendation, overrides=overrides)

    with pytest.raises(UnsupportedRecommendationSourceError, match="SUBCLASS"):
        authenticate_controller_output(
            hostile, expected_recommendation_digest=ATTACKER_DIGEST
        )

    assert calls == [], f"the guard dispatched to {calls} before refusing"


@pytest.mark.parametrize("overrides", DISPATCH_POINTS)
def test_an_override_that_raises_is_never_reached(recommendation, overrides):
    """The strongest form: any dispatch at all is an immediate failure."""

    hostile, calls = make_subclass(recommendation, overrides=overrides, mode="raise")

    with pytest.raises(UnsupportedRecommendationSourceError):
        authenticate_controller_output(
            hostile, expected_recommendation_digest=ATTACKER_DIGEST
        )
    assert calls == []


def test_the_attacker_chosen_digest_is_never_adopted(recommendation):
    """The concrete harm F-1 permitted: an attacker-selected recommendation digest."""

    hostile, calls = make_subclass(recommendation, overrides=("digest",))
    assert hostile.digest() == ATTACKER_DIGEST  # the override does work when invoked
    calls.clear()

    with pytest.raises(UnsupportedRecommendationSourceError):
        authenticate_controller_output(
            hostile, expected_recommendation_digest=ATTACKER_DIGEST
        )
    assert calls == []
    # ...and the genuine content digest is a different value entirely.
    assert CapacityActionRecommendation.digest(recommendation) != ATTACKER_DIGEST


def test_a_subclass_is_refused_even_with_a_correct_expected_digest(recommendation):
    """Admission does not depend on the caller's expectation being wrong."""

    hostile, calls = make_subclass(recommendation, overrides=("digest",))
    with pytest.raises(UnsupportedRecommendationSourceError):
        authenticate_controller_output(
            hostile,
            expected_recommendation_digest=CapacityActionRecommendation.digest(recommendation),
        )
    assert calls == []


def test_a_plain_subclass_with_no_overrides_is_also_refused(recommendation):
    """The rule is structural — it does not try to guess which subclasses are benign."""

    benign = type("BenignSubclass", (CapacityActionRecommendation,), {})(
        **_fields(recommendation)
    )
    with pytest.raises(UnsupportedRecommendationSourceError, match="SUBCLASS"):
        authenticate_controller_output(
            benign,
            expected_recommendation_digest=CapacityActionRecommendation.digest(recommendation),
        )


def test_a_subclass_that_is_also_a_mapping_cannot_divert_to_the_serialized_path(
    recommendation,
):
    """A Mapping-shaped subclass must not have its own ``get``/``keys`` consulted."""

    calls: list[str] = []

    class MappingSubclass(CapacityActionRecommendation):
        def digest(self):
            calls.append("digest")
            return ATTACKER_DIGEST

        def get(self, key, default=None):
            calls.append("get")
            return default

        def keys(self):
            calls.append("keys")
            return []

        def __getitem__(self, key):
            calls.append("__getitem__")
            raise KeyError(key)

        def __iter__(self):
            calls.append("__iter__")
            return iter(())

        def __len__(self):
            calls.append("__len__")
            return 0

    hostile = MappingSubclass(**_fields(recommendation))
    with pytest.raises(UnsupportedRecommendationSourceError, match="SUBCLASS"):
        authenticate_controller_output(
            hostile, expected_recommendation_digest=ATTACKER_DIGEST
        )
    assert calls == [], f"the guard consulted {calls} on a hostile Mapping-shaped subclass"


def test_an_abstention_subclass_is_refused_the_same_way():
    """The sibling in-process path carries the identical flaw and the identical fix."""

    calls: list[str] = []
    abstention = build_abstention()

    class HostileAbstention(RecommendationAbstention):
        def digest(self):
            calls.append("digest")
            return ATTACKER_DIGEST

        def to_canonical_dict(self, **kwargs):
            calls.append("to_canonical_dict")
            return {}

    hostile = HostileAbstention(**_fields(abstention))
    with pytest.raises(UnsupportedRecommendationSourceError, match="SUBCLASS"):
        authenticate_controller_output(hostile)
    assert calls == []


# --- nothing downstream is constructed or reached ------------------------------------------


def test_no_projection_binding_request_or_seam_call_occurs(recommendation, monkeypatch):
    """Assert non-construction directly, by making construction itself fail loudly."""

    from risk_authority.integrations import (
        SubjectBinding,
        SubjectContext,
        SubjectRiskEvaluationRequestV2,
    )
    from ugence_cloud_scaling_risk_integration import projection as projection_module

    constructed: list[str] = []

    for name, cls in (
        ("SubjectContext", SubjectContext),
        ("SubjectBinding", SubjectBinding),
        ("SubjectRiskEvaluationRequestV2", SubjectRiskEvaluationRequestV2),
    ):
        def _forbidden(*args, _n=name, **kwargs):
            constructed.append(_n)
            raise AssertionError(f"{_n} was constructed for a refused subclass")

        monkeypatch.setattr(projection_module, name, _forbidden)

    seam = RecordingSeam()
    clock_reads: list[int] = []

    def _counting_clock():
        clock_reads.append(1)
        return INSIDE_WINDOW

    adapter = CloudScalingRiskAdapter(seam=seam, clock=_counting_clock)
    hostile, calls = make_subclass(recommendation, overrides=("digest",), mode="raise")

    outcome = adapter.evaluate(hostile, expected_recommendation_digest=ATTACKER_DIGEST)

    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.rejection_reason is AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE
    assert calls == [], "an override was dispatched"
    assert constructed == [], f"downstream contracts were constructed: {constructed}"
    assert not seam.reached, "the evaluation seam was reached"
    assert clock_reads == [], (
        "the trusted clock was read before source admission — admission must precede it"
    )
    assert outcome.decision is None
    assert outcome.projection is None


def test_the_policy_and_evidence_resolvers_receive_zero_calls(recommendation):
    seam = reference_seam(now=INSIDE_WINDOW)
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    hostile, _ = make_subclass(recommendation, overrides=("digest",), mode="raise")

    outcome = adapter.evaluate(hostile, expected_recommendation_digest=ATTACKER_DIGEST)

    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert seam._policy_resolver.last_subject_context == []


def test_no_decision_envelope_actiongate_credential_or_execution_object_exists(
    recommendation,
):
    seam = RecordingSeam()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=fixed_clock(INSIDE_WINDOW))
    hostile, _ = make_subclass(recommendation, overrides=("digest",), mode="raise")

    outcome = adapter.evaluate(hostile, expected_recommendation_digest=ATTACKER_DIGEST)

    assert outcome.decision is None
    assert outcome.projection is None
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "credential_issued", "actuation_performed", "effect_verified",
                 "executable"):
        assert getattr(outcome, flag) is False
    assert outcome.grants_authority is False


# --- the authenticated record itself cannot carry a subclass --------------------------------


def test_the_authenticated_record_refuses_a_subclass_constructed_directly(recommendation):
    """Defence in depth: the token the projection trusts cannot hold a subclass."""

    hostile, _ = make_subclass(recommendation, overrides=("digest",))
    with pytest.raises(UnsupportedRecommendationSourceError, match="exactly"):
        AuthenticatedRecommendation(
            recommendation=hostile,
            recommendation_digest=ATTACKER_DIGEST,
            expectation_source="caller_supplied_expectation",
        )


# --- the positive control ----------------------------------------------------------------


def test_the_exact_canonical_type_still_succeeds(recommendation):
    """The guard must reject subclasses without breaking the legitimate path."""

    expected = recommendation.digest()
    result = authenticate_controller_output(
        recommendation, expected_recommendation_digest=expected
    )
    assert isinstance(result, AuthenticatedRecommendation)
    assert type(result.recommendation) is CapacityActionRecommendation
    assert result.recommendation_digest == expected


def test_the_exact_canonical_type_still_evaluates_end_to_end(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(now=INSIDE_WINDOW), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION


def test_the_serialized_path_reconstructs_the_exact_base_type(recommendation):
    """A legitimate document reconstructs into an exact base instance and re-digests."""

    document = recommendation.to_canonical_dict()
    result = authenticate_controller_output(document)
    assert type(result.recommendation) is CapacityActionRecommendation
    assert result.recommendation_digest == recommendation.digest()
    assert result.recommendation_digest != ATTACKER_DIGEST


def test_calling_the_base_method_unbound_would_NOT_have_been_sufficient(recommendation):
    """Why exact-type admission is the required correction, demonstrated concretely.

    An obvious partial fix is to keep ``isinstance`` admission and defensively recompute
    with the unbound base method, ``CapacityActionRecommendation.digest(source)``. This
    test shows that does not work: the base ``digest()`` calls ``self._digest_payload()``
    → ``self.to_canonical_dict()``, so an override further down the chain is still
    reached through dynamic dispatch and still controls the result.
    """

    hostile, calls = make_subclass(
        recommendation, overrides=("to_canonical_dict",)
    )
    calls.clear()

    # The unbound base call dispatches straight back into the subclass override — and it
    # does not error, it quietly returns a digest computed over attacker-supplied content.
    # A silently wrong digest is worse than a crash: nothing signals that anything failed.
    unbound_digest = CapacityActionRecommendation.digest(hostile)
    assert "to_canonical_dict" in calls, (
        "the premise of this test is that the base method dispatches; if it no longer "
        "does, this rationale needs revisiting"
    )
    assert unbound_digest != recommendation.digest(), (
        "the unbound base call produced a digest over the override's payload, not over "
        "the genuine canonical content — which is exactly why it is not a sufficient fix"
    )

    # ...whereas exact-type admission refuses before any of that can happen.
    calls.clear()
    with pytest.raises(UnsupportedRecommendationSourceError, match="SUBCLASS"):
        authenticate_controller_output(
            hostile, expected_recommendation_digest=ATTACKER_DIGEST
        )
    assert calls == []


def test_even_the_base_serializer_dispatches_so_a_subclass_document_is_untrusted(
    recommendation,
):
    """A subclass-produced *document* is not laundered by using the base serializer.

    ``CapacityActionRecommendation.to_canonical_dict(hostile)`` still calls
    ``self.digest()`` to fill ``evidence_digest``, so the attacker's value lands in the
    document. The serialized path then recomputes from content and rejects the mismatch —
    which is the correct outcome, and shows the two layers are independent.
    """

    from ugence_cloud_scaling_risk_integration import RecommendationAuthenticityError

    hostile, _ = make_subclass(recommendation, overrides=("digest",))
    document = CapacityActionRecommendation.to_canonical_dict(hostile)
    assert document["evidence_digest"] == ATTACKER_DIGEST

    with pytest.raises(RecommendationAuthenticityError, match="digest mismatch"):
        authenticate_controller_output(document)
