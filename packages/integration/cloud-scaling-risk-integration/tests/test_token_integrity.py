"""The authenticated token's own content-integrity invariant.

The finding this suite closes. ``AuthenticatedRecommendation`` is the *token* every
downstream consumer trusts: holding one is what entitles a caller to project a
recommendation into a Risk Authority v2 request. But the token could be hand-constructed
with an exact canonical ``CapacityActionRecommendation`` and a **syntactically valid but
incorrect** ``recommendation_digest``, and nothing checked that the digest actually
described the recommendation. A consumer would then accept a token whose name claims a
reconciliation that never happened, and would emit a request bound to a digest of the
attacker's choosing.

The invariant now enforced, at construction **and** at every consumption boundary::

    token.recommendation_digest == token.recommendation.digest()

Why both places, and why the second is the load-bearing one: a frozen dataclass is not a
security boundary. ``object.__new__`` skips ``__post_init__`` entirely,
``object.__setattr__`` rewrites a frozen field afterwards, and a subclass can replace any
field with a property that returns a different object on each read. A construction-time
check alone would stop only the honest mistake.

**What this does and does not establish.** It is *content integrity*: the token's digest
describes the token's content. It is **not** signed producer authenticity — a fully
self-consistent forged recommendation carrying its own matching digest is still
structurally admitted, exactly as before, because no signed provenance chain exists over
the controller's output. That case is asserted below as a deliberate, unchanged
limitation rather than quietly omitted.

Every rejection case asserts more than the error: that the clock was never read, that no
context, binding or v2 request was constructed, that the seam and both Risk Authority
resolvers received zero calls, and that no decision, envelope, ActionGate, credential or
execution object came into existence.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import pytest

from conftest import (
    INSIDE_WINDOW,
    ForbiddenSeam,
    RecordingSeam,
    build_abstention,
    reference_seam,
)
from ugence_cloud_scaling_controller.planning.recommendation import (
    CapacityActionRecommendation,
    RecommendationAbstention,
)

from ugence_cloud_scaling_risk_integration import (
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    ProjectionError,
    AuthenticatedAbstention,
    AuthenticatedRecommendation,
    CloudScalingRiskAdapter,
    RecommendationAuthenticityError,
    UnsupportedRecommendationSourceError,
    authenticate_controller_output,
    project_recommendation,
)
from ugence_cloud_scaling_risk_integration import projection as projection_module

#: Syntactically impeccable — 'sha256:' plus 64 lowercase hex — and completely wrong.
#: This is the whole point: syntax was already checked, and syntax proves nothing.
WRONG_DIGEST = "sha256:" + "9" * 64


# =====================================================================================
# instrumentation: prove the rejection happened before anything else did
# =====================================================================================


class CountingClock:
    """An injected trusted clock that records every read.

    A rejected token must never cause a clock read: reading one is the first step of the
    validity gate, which sits *after* projection. If the counter moves, the rejection
    happened later in the pipeline than claimed.
    """

    def __init__(self, now=INSIDE_WINDOW) -> None:
        self.now = now
        self.reads = 0

    def __call__(self):
        self.reads += 1
        return self.now


@dataclass
class ConstructionWatch:
    """Records every ``SubjectContext``/``SubjectBinding``/request built during a call.

    Patched onto the projection module's own names, so it observes construction on the
    exact path the adapter uses. A rejected token must leave all three at zero: no
    neutral context curated, no binding derived, no v2 request assembled.
    """

    contexts: int = 0
    bindings: int = 0
    requests: int = 0

    @property
    def anything_built(self) -> bool:
        return bool(self.contexts or self.bindings or self.requests)


@pytest.fixture
def watch(monkeypatch) -> ConstructionWatch:
    counters = ConstructionWatch()
    for name, attr in (
        ("SubjectContext", "contexts"),
        ("SubjectBinding", "bindings"),
        ("SubjectRiskEvaluationRequestV2", "requests"),
    ):
        cls = getattr(projection_module, name)
        original = cls.__init__

        def _counting(self, *args, _o=original, _a=attr, **kwargs):
            setattr(counters, _a, getattr(counters, _a) + 1)
            _o(self, *args, **kwargs)

        # Patched on the class rather than on the module name, so the name stays a class
        # and the projection's own ``isinstance`` checks keep working.
        monkeypatch.setattr(cls, "__init__", _counting)
    return counters


class CountingResolverSeam:
    """A seam that also proves the Risk Authority resolvers behind it were never entered.

    The adapter's contract is that a failed gate means Risk Authority observed *nothing*
    — not merely that no decision came back. Counting the seam call alone would not
    distinguish "never called" from "called, and internally declined".
    """

    def __init__(self) -> None:
        self.calls: list = []
        self.policy_resolutions = 0
        self.evidence_resolutions = 0

    def evaluate(self, request):  # pragma: no cover - reaching this IS the failure
        self.calls.append(request)
        raise AssertionError(
            "the evaluation seam was reached with an invalid authenticated token"
        )

    def resolve_policy(self, *args, **kwargs):  # pragma: no cover
        self.policy_resolutions += 1
        raise AssertionError("a policy resolver was reached")

    def resolve_evidence(self, *args, **kwargs):  # pragma: no cover
        self.evidence_resolutions += 1
        raise AssertionError("an evidence resolver was reached")

    def assert_untouched(self) -> None:
        assert self.calls == [], "the seam received a request"
        assert self.policy_resolutions == 0, "a policy resolver was consulted"
        assert self.evidence_resolutions == 0, "an evidence resolver was consulted"


def assert_nothing_happened(seam, clock, watch) -> None:
    """The full negative assertion every invalid-token case must satisfy."""

    seam.assert_untouched()
    assert clock.reads == 0, "the trusted clock was read on a rejected token"
    assert watch.contexts == 0, "a SubjectContext was curated for a rejected token"
    assert watch.bindings == 0, "a SubjectBinding was derived for a rejected token"
    assert watch.requests == 0, "a v2 request was assembled for a rejected token"


def assert_no_authority_object(outcome) -> None:
    """No decision, envelope, ActionGate, credential or execution object exists."""

    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.decision is None
    assert outcome.projection is None
    for flag in (
        "authorization_performed",
        "envelope_issued",
        "actiongate_invoked",
        "credential_issued",
        "actuation_performed",
        "effect_verified",
        "executable",
    ):
        assert getattr(outcome, flag) is False, f"{flag} was not False"
    assert outcome.grants_authority is False


# =====================================================================================
# token factories: every way a mismatched token can come into existence
# =====================================================================================


def valid_token(recommendation) -> AuthenticatedRecommendation:
    """The genuine article, produced by the supported path."""

    token = authenticate_controller_output(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert type(token) is AuthenticatedRecommendation
    return token


def bypassed_token(recommendation, *, digest=WRONG_DIGEST) -> AuthenticatedRecommendation:
    """An **exact** ``AuthenticatedRecommendation`` built without running ``__post_init__``.

    ``object.__new__`` runs neither ``__init__`` nor ``__post_init__``, so the
    construction-time check never executes. ``type()`` still reports the exact class, and
    ``isinstance`` still says yes — which is precisely why a consumer that only checks the
    type is not protected.
    """

    token = object.__new__(AuthenticatedRecommendation)
    object.__setattr__(token, "recommendation", recommendation)
    object.__setattr__(token, "recommendation_digest", digest)
    object.__setattr__(token, "expectation_source", "caller_supplied_expectation")
    for field in fields(AuthenticatedRecommendation):
        if field.name not in ("recommendation", "recommendation_digest", "expectation_source"):
            object.__setattr__(token, field.name, False)
    return token


def mutated_digest_token(recommendation) -> AuthenticatedRecommendation:
    """A validly constructed token whose digest is rewritten afterwards.

    ``frozen=True`` blocks ``token.recommendation_digest = ...``; it does not block
    ``object.__setattr__``, which writes straight into the instance dict.
    """

    token = valid_token(recommendation)
    object.__setattr__(token, "recommendation_digest", WRONG_DIGEST)
    return token


def swapped_recommendation_token(recommendation, other) -> AuthenticatedRecommendation:
    """A validly constructed token whose *recommendation* is replaced afterwards.

    The mirror image of the digest mutation, and the more dangerous direction: the digest
    is genuine and was genuinely reconciled — for a different record.
    """

    token = valid_token(recommendation)
    object.__setattr__(token, "recommendation", other)
    return token


def token_subclass_with_skipped_post_init(recommendation):
    """A token subclass whose own ``__init__`` never reaches ``__post_init__``."""

    class SkippingToken(AuthenticatedRecommendation):
        def __init__(self, rec, digest):  # noqa: D107 - deliberately not the dataclass init
            object.__setattr__(self, "recommendation", rec)
            object.__setattr__(self, "recommendation_digest", digest)
            object.__setattr__(self, "expectation_source", "caller_supplied_expectation")
            for field in fields(AuthenticatedRecommendation):
                if field.name not in (
                    "recommendation",
                    "recommendation_digest",
                    "expectation_source",
                ):
                    object.__setattr__(self, field.name, False)

    return SkippingToken(recommendation, WRONG_DIGEST)


def token_subclass_with_hostile_attribute_access(recommendation, other):
    """A token subclass whose ``recommendation`` is a property returning a *different*
    object on each read.

    This is why exact-type admission on the *token* is load-bearing rather than pedantic.
    Against such a subclass, "validate then use" is not a defence at any level of care:
    the value validated is by construction not the value consumed. The only correction
    that holds is refusing the subclass before reading anything.
    """

    reads: list[int] = []

    class HostileToken(AuthenticatedRecommendation):
        @property
        def recommendation(self):
            reads.append(len(reads))
            # First read (the check) sees the genuine record; every later read (the use)
            # sees the substitute.
            return recommendation if len(reads) == 1 else other

        @property
        def recommendation_digest(self):
            return recommendation.digest()

    token = object.__new__(HostileToken)
    for field in fields(AuthenticatedRecommendation):
        if field.name not in ("recommendation", "recommendation_digest"):
            object.__setattr__(token, field.name, False)
    object.__setattr__(token, "expectation_source", "caller_supplied_expectation")
    return token, reads


def token_with_recommendation_subclass(recommendation):
    """A fabricated token whose embedded record is a *subclass* choosing its own digest."""

    chosen = WRONG_DIGEST

    class HostileRecommendation(CapacityActionRecommendation):
        def digest(self):  # noqa: D102 - the attacker-chosen "recomputation"
            return chosen

    hostile = HostileRecommendation(
        **{f.name: getattr(recommendation, f.name) for f in fields(recommendation)}
    )
    return bypassed_token(hostile, digest=chosen)


@pytest.fixture
def other_recommendation():
    """A *different* genuine recommendation, for substitution attacks."""

    from conftest import build_recommendation

    other = build_recommendation(predicted=12, current=6, recommendation_id="rec-other")
    return other


# =====================================================================================
# 1. supported construction cannot mint a mismatched token
# =====================================================================================


def test_a_mismatched_token_cannot_be_constructed_normally(recommendation):
    """The exact construction the finding described, now refused.

    A canonical recommendation, a syntactically perfect digest, and no relationship
    between the two.
    """

    assert recommendation.digest() != WRONG_DIGEST
    with pytest.raises(RecommendationAuthenticityError, match="does not describe"):
        AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=WRONG_DIGEST,
            expectation_source="caller_supplied_expectation",
        )


def test_the_rejection_names_both_the_carried_and_the_recomputed_digest(recommendation):
    """An audit record must say what was claimed and what the content actually hashes to."""

    with pytest.raises(RecommendationAuthenticityError) as caught:
        AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=WRONG_DIGEST,
            expectation_source="caller_supplied_expectation",
        )
    message = str(caught.value)
    assert WRONG_DIGEST in message
    assert recommendation.digest() in message


def test_a_digest_from_a_different_real_recommendation_is_refused(
    recommendation, other_recommendation
):
    """Not merely nonsense digests: a *real* digest of the *wrong* record is refused."""

    stale = other_recommendation.digest()
    assert stale != recommendation.digest()
    with pytest.raises(RecommendationAuthenticityError, match="does not describe"):
        AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=stale,
            expectation_source="caller_supplied_expectation",
        )


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param("", id="empty"),
        pytest.param("sha256:", id="prefix-only"),
        pytest.param("9" * 64, id="no-prefix"),
        pytest.param("sha256:" + "9" * 63, id="one-char-short"),
        pytest.param("sha256:" + "9" * 65, id="one-char-long"),
        pytest.param("sha256:" + "F" * 64, id="uppercase-hex"),
        pytest.param("sha256:" + "z" * 64, id="non-hex"),
        pytest.param("sha512:" + "9" * 64, id="wrong-algorithm"),
        pytest.param(None, id="none"),
        pytest.param(True, id="bool"),
        pytest.param(123, id="int"),
    ],
)
def test_a_malformed_digest_is_refused_at_construction(recommendation, malformed):
    with pytest.raises(RecommendationAuthenticityError):
        AuthenticatedRecommendation(
            recommendation=recommendation,
            recommendation_digest=malformed,
            expectation_source="caller_supplied_expectation",
        )


def test_a_token_subclass_cannot_be_constructed_through_the_supported_path(recommendation):
    """Subclassing the token is refused at construction, not merely at consumption."""

    class SubclassToken(AuthenticatedRecommendation):
        pass

    with pytest.raises(UnsupportedRecommendationSourceError, match="exactly"):
        SubclassToken(
            recommendation=recommendation,
            recommendation_digest=recommendation.digest(),
            expectation_source="caller_supplied_expectation",
        )


def test_the_correct_digest_still_constructs(recommendation):
    """Positive control: the invariant must not break the legitimate path."""

    token = AuthenticatedRecommendation(
        recommendation=recommendation,
        recommendation_digest=recommendation.digest(),
        expectation_source="caller_supplied_expectation",
    )
    assert token.recommendation_digest == token.recommendation.digest()
    assert type(token.recommendation) is CapacityActionRecommendation


# =====================================================================================
# 2. consumption boundaries: project_recommendation
# =====================================================================================


def _fabrications(recommendation, other):
    """Every unsupported token this suite knows how to build, by name."""

    return {
        "object.__new__ bypass": bypassed_token(recommendation),
        "object.__setattr__ digest mutation": mutated_digest_token(recommendation),
        "post-construction recommendation swap": swapped_recommendation_token(
            recommendation, other
        ),
        "subclass with skipped __post_init__": token_subclass_with_skipped_post_init(
            recommendation
        ),
        "fabricated token holding a recommendation subclass": (
            token_with_recommendation_subclass(recommendation)
        ),
    }


FORGERIES = [
    "object.__new__ bypass",
    "object.__setattr__ digest mutation",
    "post-construction recommendation swap",
    "subclass with skipped __post_init__",
    "fabricated token holding a recommendation subclass",
]


@pytest.fixture(params=FORGERIES)
def forged_token(request, recommendation, other_recommendation):
    return _fabrications(recommendation, other_recommendation)[request.param]


def test_a_forged_token_is_refused_by_direct_projection(forged_token, watch):
    with pytest.raises(
        (ProjectionError, RecommendationAuthenticityError, UnsupportedRecommendationSourceError)
    ):
        project_recommendation(forged_token)
    assert not watch.anything_built, (
        "projection built part of the chain before refusing the token"
    )


def test_a_forged_token_reaches_no_seam_clock_or_resolver_through_the_adapter(
    forged_token, watch
):
    """The adapter's public entry points refuse the token before anything observes it."""

    seam = CountingResolverSeam()
    clock = CountingClock()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=clock)

    # .project raises; .evaluate returns a typed rejection. Both must refuse.
    with pytest.raises(
        (RecommendationAuthenticityError, UnsupportedRecommendationSourceError)
    ):
        adapter.project(forged_token)
    assert_nothing_happened(seam, clock, watch)

    outcome = adapter.evaluate(forged_token)
    assert_no_authority_object(outcome)
    assert_nothing_happened(seam, clock, watch)


def test_a_forged_token_passed_as_a_source_is_an_unsupported_input(forged_token):
    """Handed to the adapter as a *source*, it is refused at admission as a foreign type."""

    seam = CountingResolverSeam()
    clock = CountingClock()
    outcome = CloudScalingRiskAdapter(seam=seam, clock=clock).evaluate(forged_token)
    assert outcome.rejection_reason is AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE
    seam.assert_untouched()
    assert clock.reads == 0


def test_the_hostile_property_token_cannot_win_the_check_use_race(
    recommendation, other_recommendation, watch
):
    """A token subclass whose field changes between validation and use is refused outright.

    Against this shape, checking-then-using cannot be made safe. Exact-type admission is
    the correction: the subclass is refused before its property is ever read twice.
    """

    token, reads = token_subclass_with_hostile_attribute_access(
        recommendation, other_recommendation
    )
    with pytest.raises(
        (ProjectionError, UnsupportedRecommendationSourceError, RecommendationAuthenticityError)
    ):
        project_recommendation(token)
    assert not watch.anything_built
    assert len(reads) <= 1, (
        f"the hostile property was read {len(reads)} times — the substitute was reached"
    )

    seam = CountingResolverSeam()
    clock = CountingClock()
    outcome = CloudScalingRiskAdapter(seam=seam, clock=clock).evaluate(token)
    assert_no_authority_object(outcome)
    assert_nothing_happened(seam, clock, watch)


def test_a_forged_authority_flag_on_a_token_is_rejected_not_normalized(recommendation):
    """A token claiming an executed action is refused, never quietly corrected to False."""

    token = valid_token(recommendation)
    object.__setattr__(token, "executable", True)
    with pytest.raises(RecommendationAuthenticityError, match="executable"):
        project_recommendation(token)
    assert token.executable is True, "the forged flag was normalized instead of refused"


def test_a_token_with_no_fields_at_all_fails_closed_with_a_typed_error(recommendation):
    """``object.__new__`` and nothing else: a controlled rejection, not an AttributeError."""

    empty = object.__new__(AuthenticatedRecommendation)
    with pytest.raises(RecommendationAuthenticityError, match="missing"):
        project_recommendation(empty)


@pytest.fixture
def substitute_recommendation():
    """A genuine recommendation for a *different* subject, with a genuine digest.

    Deliberately self-consistent: its digest really is its own digest, and its subject
    facts really are its own. A projection built from it would reconcile perfectly — it
    would simply describe the wrong workload. That is what makes it the right probe for
    the check-then-use window: no internal-consistency assertion can catch it, only
    comparing against the value the validator actually returned.
    """

    import ph_helpers as H
    from conftest import build_recommendation

    return build_recommendation(
        predicted=12,
        current=6,
        subject=H.subject(workload_id="substituted-workload"),
        recommendation_id="rec-substituted",
    )


def test_the_projection_uses_the_validated_pair_and_never_re_reads_the_token(
    monkeypatch, recommendation, substitute_recommendation
):
    """``project_recommendation`` must consume the pair the validator returned.

    The token here is **exactly** an ``AuthenticatedRecommendation``, built normally, so
    the exact-type gate admits it and the validated-pair discipline is what is actually
    under test. A subclass would be refused before this code path is reached and would
    therefore prove nothing about it — which is why the hostile properties are installed
    on the class *after* a legitimate token already exists.

    Each protected field answers honestly on its **first** read and substitutes a
    different, internally self-consistent recommendation on every read after that. A
    consumer that re-reads the token — rather than using the ``(recommendation, digest)``
    pair ``_validate_authenticated_recommendation`` returned — would validate one
    recommendation and project a different one, binding a Risk Authority request to a
    workload nobody authenticated. The window is narrow but real: ``object.__setattr__``
    on a frozen field is all a concurrent caller needs.

    ``monkeypatch`` restores the class even if an assertion below fails, so no state
    leaks into any other test.
    """

    honest, substitute = recommendation, substitute_recommendation
    assert honest.digest() != substitute.digest()
    assert honest.subject.workload_id != substitute.subject.workload_id

    token = authenticate_controller_output(
        honest, expected_recommendation_digest=honest.digest()
    )
    # The reference answer, computed before any hostile property exists.
    expected = project_recommendation(token)

    reads = {"recommendation": 0, "recommendation_digest": 0}

    def _substituting_recommendation(self):
        reads["recommendation"] += 1
        return honest if reads["recommendation"] == 1 else substitute

    def _substituting_digest(self):
        reads["recommendation_digest"] += 1
        if reads["recommendation_digest"] == 1:
            return honest.digest()
        return substitute.digest()  # self-consistent with the substituted record

    # Installed on the exact class, after the token exists: `raising=False` because a
    # dataclass field without a default is not a class attribute, and monkeypatch then
    # removes the property again on teardown — pass or fail.
    monkeypatch.setattr(
        AuthenticatedRecommendation,
        "recommendation",
        property(_substituting_recommendation),
        raising=False,
    )
    monkeypatch.setattr(
        AuthenticatedRecommendation,
        "recommendation_digest",
        property(_substituting_digest),
        raising=False,
    )

    projection = project_recommendation(token)

    # --- the projection describes what was validated, not what was substituted --------
    assert projection.recommendation_digest == honest.digest(), (
        "the projection carries a digest read from the token after validation; consumers "
        "must use the (recommendation, digest) pair the validator returned"
    )
    assert projection.recommendation_digest != substitute.digest()
    assert projection.subject_id == honest.subject.workload_id
    assert projection.subject_id != substitute.subject.workload_id
    assert projection.tenant_id == honest.subject.tenant_id
    assert projection.context.magnitude_after == expected.context.magnitude_after
    assert projection.context_digest == expected.context_digest
    assert projection.subject_digest == expected.subject_digest
    assert projection.request_digest == expected.request_digest
    assert projection.idempotency_key == expected.idempotency_key

    # --- and each protected field was consulted exactly once --------------------------
    assert reads == {"recommendation": 1, "recommendation_digest": 1}, (
        f"the token was re-read after validation: {reads}"
    )


# =====================================================================================
# 3. positive controls — the valid paths are unchanged
# =====================================================================================


def test_a_valid_object_path_token_still_projects(recommendation, watch):
    projection = project_recommendation(valid_token(recommendation))
    assert projection.recommendation_digest == recommendation.digest()
    assert watch.contexts >= 1 and watch.bindings >= 1 and watch.requests >= 1


def test_a_valid_serialized_path_token_still_projects(recommendation):
    token = authenticate_controller_output(recommendation.to_canonical_dict())
    projection = project_recommendation(token)
    assert projection.recommendation_digest == recommendation.digest()


def test_the_object_and_serialized_paths_still_agree_digest_for_digest(recommendation):
    """The invariant must not have perturbed either path's output."""

    from_object = project_recommendation(valid_token(recommendation))
    from_document = project_recommendation(
        authenticate_controller_output(recommendation.to_canonical_dict())
    )
    for attribute in (
        "recommendation_digest",
        "context_digest",
        "subject_digest",
        "request_digest",
        "idempotency_key",
    ):
        assert getattr(from_object, attribute) == getattr(from_document, attribute)


def test_a_valid_token_still_evaluates_end_to_end(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(now=INSIDE_WINDOW), clock=CountingClock()
    )
    outcome = adapter.evaluate(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION
    assert outcome.recommendation_digest == recommendation.digest()


def test_adapter_project_still_returns_a_projection(recommendation):
    adapter = CloudScalingRiskAdapter(seam=ForbiddenSeam(), clock=CountingClock())
    projection = adapter.project(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert projection.recommendation_digest == recommendation.digest()


# =====================================================================================
# 4. the boundary is preserved honestly — what is still admitted
# =====================================================================================


def test_a_fully_self_consistent_forgery_is_still_structurally_admitted(recommendation):
    """The unchanged limitation, asserted rather than left implicit.

    An attacker able to author a complete, internally valid recommendation and to compute
    its genuine digest produces a token that satisfies this invariant — because it *is*
    content-consistent. Detecting it needs signed producer provenance over the
    controller's output, which does not exist in this repository and which this
    correction does not invent. Recording it as a passing test keeps the claim honest:
    the boundary is content integrity, not source authenticity.
    """

    from conftest import build_recommendation

    forged = build_recommendation(predicted=12, current=6, recommendation_id="rec-forged")
    token = AuthenticatedRecommendation(
        recommendation=forged,
        recommendation_digest=forged.digest(),  # genuine — for genuinely forged content
        expectation_source="caller_supplied_expectation",
    )
    projection = project_recommendation(token)
    assert projection.recommendation_digest == forged.digest()


# =====================================================================================
# 5. symmetric treatment of the abstention token
# =====================================================================================


def test_an_abstention_token_cannot_carry_a_mismatched_digest():
    abstention = build_abstention()
    assert abstention.digest() != WRONG_DIGEST
    with pytest.raises(RecommendationAuthenticityError, match="does not describe"):
        AuthenticatedAbstention(abstention=abstention, abstention_digest=WRONG_DIGEST)


def test_an_abstention_token_subclass_is_refused_at_construction():
    abstention = build_abstention()

    class SubclassToken(AuthenticatedAbstention):
        pass

    with pytest.raises(UnsupportedRecommendationSourceError, match="exactly"):
        SubclassToken(abstention=abstention, abstention_digest=abstention.digest())


def test_an_abstention_token_with_a_subclassed_abstention_is_refused():
    abstention = build_abstention()

    class HostileAbstention(RecommendationAbstention):
        def digest(self):  # noqa: D102
            return WRONG_DIGEST

    hostile = HostileAbstention(
        **{f.name: getattr(abstention, f.name) for f in fields(abstention)}
    )
    with pytest.raises(UnsupportedRecommendationSourceError, match="exactly"):
        AuthenticatedAbstention(abstention=hostile, abstention_digest=WRONG_DIGEST)


def test_a_fabricated_abstention_token_never_reaches_the_seam():
    """A bypassed abstention token fails before any outcome is reported."""

    abstention = build_abstention()
    token = object.__new__(AuthenticatedAbstention)
    object.__setattr__(token, "abstention", abstention)
    object.__setattr__(token, "abstention_digest", WRONG_DIGEST)
    object.__setattr__(token, "expectation_source", None)
    for field in fields(AuthenticatedAbstention):
        if field.name not in ("abstention", "abstention_digest", "expectation_source"):
            object.__setattr__(token, field.name, False)

    seam = CountingResolverSeam()
    clock = CountingClock()
    adapter = CloudScalingRiskAdapter(seam=seam, clock=clock)
    outcome = adapter.evaluate(token)
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_REJECTED
    assert outcome.abstention_reason is None, (
        "a fabricated abstention token reported an upstream non-evaluation"
    )
    seam.assert_untouched()
    assert clock.reads == 0


def test_a_valid_abstention_token_is_unchanged():
    """Positive control: genuine abstentions still carry through as non-evaluations."""

    abstention = build_abstention()
    seam = CountingResolverSeam()
    clock = CountingClock()
    outcome = CloudScalingRiskAdapter(seam=seam, clock=clock).evaluate(
        abstention.to_canonical_dict()
    )
    assert outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM
    assert outcome.abstention_reason == abstention.reason.value
    assert outcome.recommendation_digest is None
    seam.assert_untouched()


# =====================================================================================
# 6. the validation routine is not new public API
# =====================================================================================


def test_the_validation_routine_is_not_publicly_exported():
    """The invariant is enforced, not exposed: no new name enters the public surface."""

    import ugence_cloud_scaling_risk_integration as package
    from ugence_cloud_scaling_risk_integration import authenticity

    assert "_validate_authenticated_recommendation" not in package.__all__
    assert "_validate_authenticated_recommendation" not in authenticity.__all__
    assert not hasattr(package, "_validate_authenticated_recommendation")
    private = [
        name
        for name in package.__all__
        if name.startswith("_") and not name.startswith("__")
    ]
    assert private == []
