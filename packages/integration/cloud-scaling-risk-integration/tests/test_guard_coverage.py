"""Isolating attacks on guards the rest of the suite reaches only incidentally.

Guard-coverage ADR §2 makes a guard **outcome-bearing** when some constructible input
exists for which neutralising it changes the package's own typed outcome. The sweep in
`scripts/cloud_scaling/guard_sweep.py` answers that empirically, one guard at a time, and
a guard it reports SURVIVED is a guard the suite happens not to attack — not a guard that
does nothing.

Every test here exists because a specific inventory index survived a measured sweep. They
are grouped by the shape of the attack rather than by module, because the shape is the
thing worth copying when the next guard is added:

* **forge one field on a genuine object, then re-run the invariant it guards.** The
  frozen dataclasses in `outcomes.py` and `projection.py` check themselves in
  `__post_init__`, and the pipeline never hands them a bad value — which is exactly why
  nothing measured those checks. `dataclasses.replace` would re-enter the constructor and
  the refusal would come from there, so the field is forced with `object.__setattr__` on a
  copy: the way a forged value actually arrives, since the fields have no setter and a
  compromised producer does not need one.
* **call the leaf validator directly.** `_require_identity`, `_require_digest_syntax` and
  friends are reached through several callers, none of which passes them a bad value.
* **drive the public entry point with a hostile argument.** `project()` and
  `CloudScalingRiskAdapter(...)` take caller-supplied values, so a forged token or a
  missing seam is an ordinary input, not an internal patch.

Where a guard has no isolating input at all, it is *not* tested here — it is declared in
`guard_sweep.py`'s `exclusions` with a reason from the closed vocabulary and a pointer to
the test that measures the claim. Those tests live here too, named
`test_..._is_unreachable...` or `test_..._is_equivalent...`.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_risk_integration import (
    CloudScalingRiskAdapter,
    authenticity as _authenticity,
    outcomes as _outcomes,
    projection as _projection,
)
from ugence_cloud_scaling_risk_integration.errors import (
    AdapterConfigurationError,
    NonExecutableInvariantError,
    ProjectionError,
    RecommendationAuthenticityError,
    UnsupportedRecommendationSourceError,
)
from ugence_cloud_scaling_risk_integration.outcomes import (
    AdapterOutcomeStatus,
    AdapterRejectionReason,
    CloudScalingRiskOutcome,
)

from conftest import (
    INSIDE_WINDOW,
    build_recommendation,
    fixed_clock,
    reference_seam,
)


def _forge(instance, **fields):
    """A copy of ``instance`` with fields forced past the constructor.

    ``dataclasses.replace`` re-runs ``__post_init__``, so the refusal would come from the
    constructor rather than from the guard under test. ``object.__setattr__`` reproduces
    how a forged value actually arrives at a frozen dataclass.
    """

    forged = copy.copy(instance)
    for name, value in fields.items():
        object.__setattr__(forged, name, value)
    return forged


def _repost(instance):
    """Re-run the invariant block the forged instance would have failed."""

    type(instance).__post_init__(instance)


@pytest.fixture(scope="module")
def recommendation():
    return build_recommendation()


@pytest.fixture(scope="module")
def token(recommendation):
    return _authenticity.authenticate_controller_output(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )


@pytest.fixture(scope="module")
def projection(token):
    return _projection.project_recommendation(token)


@pytest.fixture(scope="module")
def decision_outcome(recommendation):
    adapter = CloudScalingRiskAdapter(
        seam=reference_seam(INSIDE_WINDOW), clock=fixed_clock(INSIDE_WINDOW)
    )
    outcome = adapter.evaluate(
        recommendation, expected_recommendation_digest=recommendation.digest()
    )
    assert outcome.status is AdapterOutcomeStatus.RISK_DECISION, outcome.detail
    return outcome


@pytest.fixture(scope="module")
def abstention_outcome():
    return CloudScalingRiskOutcome(
        status=AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM,
        abstention_reason="upstream declined",
        detail="upstream declined",
    )


@pytest.fixture(scope="module")
def rejected_outcome():
    return CloudScalingRiskOutcome(
        status=AdapterOutcomeStatus.PROJECTION_REJECTED,
        rejection_reason=AdapterRejectionReason.PROJECTION_FAILED,
        detail="refused",
    )


# --- outcomes.py: the outcome's own shape invariants --------------------------------


def test_a_status_that_is_not_the_typed_enum_is_refused(decision_outcome):
    """`outcomes.py:123`. A string that reads like a status is not a status."""

    forged = _forge(decision_outcome, status="RISK_DECISION")
    with pytest.raises(NonExecutableInvariantError, match="AdapterOutcomeStatus"):
        _repost(forged)


def test_an_outcome_schema_version_that_drifted_is_refused(decision_outcome):
    """`outcomes.py:125`. The schema tag is part of what a consumer relies on."""

    forged = _forge(decision_outcome, schema_version="phase4c-outcome.v0")
    with pytest.raises(NonExecutableInvariantError, match="schema_version"):
        _repost(forged)


def test_a_risk_decision_outcome_without_a_canonical_decision_is_refused(decision_outcome):
    """`outcomes.py:131`. A RISK_DECISION that carries a look-alike carries nothing."""

    forged = _forge(decision_outcome, decision=object())
    with pytest.raises(NonExecutableInvariantError, match="SubjectRiskDecision"):
        _repost(forged)


@pytest.mark.parametrize(
    "field, value",
    [
        ("rejection_reason", AdapterRejectionReason.PROJECTION_FAILED),
        ("abstention_reason", "declined"),
    ],
)
def test_a_risk_decision_outcome_carrying_a_refusal_reason_is_refused(
    decision_outcome, field, value
):
    """`outcomes.py:141`. A decision and a refusal reason are mutually exclusive.

    Both halves of the ``or`` are attacked, because the sweep neutralises the guard as one
    and a test that only supplied a rejection reason would leave the other sub-term — one
    of the twelve the inventory discloses as not separately scored — unmeasured.
    """

    forged = _forge(decision_outcome, **{field: value})
    with pytest.raises(NonExecutableInvariantError, match="rejection or abstention"):
        _repost(forged)


@pytest.mark.parametrize("value", [None, "", 7])
def test_an_abstention_without_the_controllers_typed_reason_is_refused(
    abstention_outcome, value
):
    """`outcomes.py:151`. The abstention path's whole discriminator is that string.

    Guard-coverage ADR §3 makes the controller-supplied ``abstention_reason`` the pair's
    second element on this path, so an abstention that carries none is an outcome with no
    typed identity at all.
    """

    forged = _forge(abstention_outcome, abstention_reason=value)
    with pytest.raises(NonExecutableInvariantError, match="typed reason"):
        _repost(forged)


def test_an_abstention_carrying_an_adapter_rejection_reason_is_refused(abstention_outcome):
    """`outcomes.py:155`. Upstream declining and the adapter refusing are different facts."""

    forged = _forge(
        abstention_outcome, rejection_reason=AdapterRejectionReason.PROJECTION_FAILED
    )
    with pytest.raises(NonExecutableInvariantError, match="not an adapter rejection"):
        _repost(forged)


def test_a_rejection_carrying_an_abstention_reason_is_refused(rejected_outcome):
    """`outcomes.py:168`. The mirror of the guard above, on the rejection path."""

    forged = _forge(rejected_outcome, abstention_reason="declined")
    with pytest.raises(NonExecutableInvariantError, match="not an upstream abstention"):
        _repost(forged)


# --- projection.py: the binding chain's own invariants -------------------------------


def test_a_projection_schema_version_that_drifted_is_refused(projection):
    """`projection.py:131`."""

    forged = _forge(projection, schema_version="phase4c-projection.v0")
    with pytest.raises(ProjectionError, match="schema_version"):
        _repost(forged)


def test_a_projection_whose_request_is_not_the_v2_contract_is_refused(projection):
    """`projection.py:135`."""

    forged = _forge(projection, request=object())
    with pytest.raises(ProjectionError, match="SubjectRiskEvaluationRequestV2"):
        _repost(forged)


def test_a_projection_carrying_an_evaluation_time_is_refused(projection):
    """`projection.py:139`. Trusted evaluation time comes only from RA's injected clock."""

    forged_request = _forge(
        projection.request, evaluation_time=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    forged = _forge(projection, request=forged_request)
    with pytest.raises(ProjectionError, match="evaluation_time"):
        _repost(forged)


@pytest.mark.parametrize(
    "field, message",
    [
        ("context_digest", "context_digest does not match"),
        ("subject_digest", "subject_digest does not match"),
        ("request_digest", "request_digest does not match"),
    ],
)
def test_a_carried_digest_that_does_not_cover_its_object_is_refused(
    projection, field, message
):
    """`projection.py:149`, `:151`, `:153` — the carried half of the chain.

    Each is re-derived rather than trusted, and each is attacked separately: the sweep
    neutralises them one at a time, so one test covering "some digest mismatched" would
    leave two of the three unmeasured.
    """

    forged = _forge(projection, **{field: "sha256:" + "0" * 64})
    with pytest.raises(ProjectionError, match=message):
        _repost(forged)


@pytest.mark.parametrize(
    "carried, digest_field, message",
    [
        ("context", "context_digest", "different context_digest"),
        ("binding", "subject_digest", "different subject_digest"),
    ],
)
def test_a_carried_object_that_disagrees_with_the_request_is_refused(
    projection, token, carried, digest_field, message
):
    """`projection.py:161`, `:163` — the *revalidated* half of the chain.

    Reaching these needs an instance whose carried digests are internally consistent —
    otherwise `:149`/`:151` refuse first — while the request they were supposedly derived
    from says something else. So the carried object is swapped for a different genuine one
    and its digest updated to match: self-consistent, and contradicted only by re-deriving
    from the request, which is precisely what these two guards do.
    """

    other = _projection.project_recommendation(
        _authenticity.authenticate_controller_output(
            build_recommendation(predicted=17, current=4, recommendation_id="rec-other"),
            expected_recommendation_digest=build_recommendation(
                predicted=17, current=4, recommendation_id="rec-other"
            ).digest(),
        )
    )
    swapped = getattr(other, carried)
    forged = _forge(projection, **{carried: swapped, digest_field: swapped.digest()})
    with pytest.raises(ProjectionError, match=message):
        _repost(forged)


def test_a_recommendation_digest_the_request_does_not_carry_is_refused(projection):
    """`projection.py:165`. The last of the three revalidation comparisons.

    `recommendation_digest` has no carried object of its own to re-derive from, so the
    isolating input is the field itself: `:153` proves the *request* still hashes to
    `request_digest`, and this proves the recommendation digest inside that request is the
    one the projection claims.
    """

    forged = _forge(projection, recommendation_digest="sha256:" + "1" * 64)
    with pytest.raises(ProjectionError, match="different recommendation_digest"):
        _repost(forged)


# --- projection.py: the leaf validators ---------------------------------------------


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00Z", 1767225600, None])
def test_an_instant_that_is_not_a_datetime_is_refused(value):
    """`projection.py:202`. A string that parses is still not an instant."""

    with pytest.raises(ProjectionError, match="must be a datetime"):
        _projection._require_utc("valid_from", value)


@pytest.mark.parametrize("value", ["", None, 7, b"tenant"])
def test_an_identity_that_is_not_a_non_empty_string_is_refused(value):
    """`projection.py:213`."""

    with pytest.raises(ProjectionError, match="non-empty string"):
        _projection._require_identity("tenant_id", value)


def test_a_recommendation_without_forecast_evidence_digest_is_refused(recommendation):
    """`projection.py:252`. ADR §6 makes the forecast evidence digest mandatory."""

    forged = _forge(recommendation)
    object.__setattr__(forged, "forecast_evidence_digest", lambda: None)
    with pytest.raises(ProjectionError, match="forecast_evidence_digest is required"):
        _projection._evidence_references(forged)


def test_an_evidence_digest_that_is_not_canonical_is_refused(recommendation):
    """`projection.py:261`. Every reference that enters the chain is a canonical digest."""

    forged = _forge(recommendation)
    object.__setattr__(forged, "cost_evidence_digest", lambda: "not-a-digest")
    with pytest.raises(ProjectionError, match="canonical 'sha256:' digest"):
        _projection._evidence_references(forged)


# --- adapter.py: the public entry points --------------------------------------------


def test_an_adapter_built_without_a_seam_is_refused():
    """`adapter.py:113`. The adapter never builds a seam; a composition root supplies one."""

    with pytest.raises(AdapterConfigurationError, match="never builds one"):
        CloudScalingRiskAdapter(seam=None, clock=fixed_clock(INSIDE_WINDOW))


def test_a_seam_returning_something_that_is_not_a_decision_is_refused(recommendation):
    """`adapter.py:271`. A duck-typed seam is refused, not trusted."""

    class _LookAlike:
        pass

    class _Seam:
        def evaluate(self, request):
            return _LookAlike()

    adapter = CloudScalingRiskAdapter(seam=_Seam(), clock=fixed_clock(INSIDE_WINDOW))
    with pytest.raises(NonExecutableInvariantError, match="canonical SubjectRiskDecision"):
        adapter.evaluate(
            recommendation, expected_recommendation_digest=recommendation.digest()
        )


# --- identifiers.py: the D-4 ratified action set -------------------------------------


def test_a_bare_string_is_not_a_controller_action_kind():
    """`identifiers.py:85`. The pass-through is guarded, not a mapping table."""

    from ugence_cloud_scaling_risk_integration import identifiers as _identifiers

    with pytest.raises(TypeError, match="must be a controller ActionKind"):
        _identifiers.canonical_action_type("scale_up")


def test_an_action_kind_the_controller_renamed_fails_the_import(monkeypatch):
    """`identifiers.py:68`. The import-time drift guard, across a distribution boundary.

    ADR Phase 5 §9.2: a condition that can be true under a dependency resolution the pins
    permit is not an equivalent mutant, however false it is in this checkout. The
    controller is separately versioned under an open-ended pin, so a release that renames
    or adds an action kind is a permitted resolution — and under it this guard is the
    difference between failing to import and binding an unratified value into the Risk
    Authority digest chain. Reproduced by installing exactly that resolution and
    re-executing the module.
    """

    import enum
    import importlib
    import sys

    from ugence_cloud_scaling_controller.planning import candidates as _candidates

    drifted = enum.Enum(
        "ActionKind",
        {kind.name: kind.value for kind in _candidates.ActionKind}
        | {"TELEPORT": "teleport"},
    )
    monkeypatch.setattr(_candidates, "ActionKind", drifted)
    monkeypatch.delitem(
        sys.modules, "ugence_cloud_scaling_risk_integration.identifiers", raising=False
    )
    with pytest.raises(ImportError, match="ActionKind drift"):
        importlib.import_module("ugence_cloud_scaling_risk_integration.identifiers")


def test_every_ratified_action_kind_is_admitted_so_the_value_check_cannot_fire():
    """`identifiers.py:88` — declared `unreachable-behind-earlier-guard`, and measured.

    The value check can only fire for an `ActionKind` member whose value is outside the
    ratified set, and the import-time guard above refuses to import at all when any such
    member exists. `:85` has already established that the argument is a genuine member, so
    between the two there is no input that reaches `:88` with a value it would reject.
    This measures the claim rather than asserting it: every member, every value, admitted.
    """

    from ugence_cloud_scaling_controller.planning.candidates import ActionKind

    from ugence_cloud_scaling_risk_integration import identifiers as _identifiers

    for kind in ActionKind:
        assert _identifiers.canonical_action_type(kind) in (
            _identifiers.CANONICAL_ACTION_TYPES
        )


# --- authenticity.py: token validity, and who may forge a token ----------------------


@pytest.mark.parametrize(
    "value", ["sha256:" + "z" * 64, "sha256:abc", "abc", "SHA256:" + "a" * 64]
)
def test_a_digest_that_is_not_canonical_syntax_is_refused(value):
    """`authenticity.py:276`. 'sha256:' plus exactly 64 lowercase hex, or nothing."""

    with pytest.raises(RecommendationAuthenticityError, match="canonical digest"):
        _authenticity._require_digest_syntax("recommendation_digest", value)


def test_an_authenticated_abstention_minted_with_an_authority_flag_is_refused():
    """`authenticity.py:398`. The abstention token validates itself at construction.

    The flags are ordinary init fields with `False` defaults, so `executable=True` is an
    ordinary construction — which is why deleting the admission call here is observable
    rather than masked by the recommendation-side call.
    """

    from ugence_cloud_scaling_controller.planning.recommendation import (
        RecommendationAbstention,
    )

    from conftest import build_abstention

    abstention = build_abstention()
    assert isinstance(abstention, RecommendationAbstention)
    with pytest.raises(RecommendationAuthenticityError, match="executable"):
        _authenticity.AuthenticatedAbstention(abstention=abstention, executable=True)


def test_a_forged_recommendation_token_is_refused_by_the_shared_validator(token):
    """`authenticity.py:429`. The recommendation arm of the shared re-validation.

    A forged token is a constructible input for this package by its own statement:
    `_assert_no_authority_fields` exists because "the flags have no setter, but
    `object.__setattr__` does not need one, and a forged `True` is rejected rather than
    normalized". So the threat model that motivates the guard is the one that isolates it.
    """

    forged = _forge(token, executable=True)
    with pytest.raises(RecommendationAuthenticityError, match="executable"):
        _authenticity._validate_authenticated_output(forged)


def test_a_forged_abstention_token_is_refused_by_the_shared_validator():
    """`authenticity.py:431`. The abstention arm of the same dispatch."""

    from conftest import build_abstention

    good = _authenticity.AuthenticatedAbstention(abstention=build_abstention())
    forged = _forge(good, actiongate_invoked=True)
    with pytest.raises(RecommendationAuthenticityError, match="actiongate_invoked"):
        _authenticity._validate_authenticated_output(forged)


@pytest.mark.parametrize("value", [object(), None, "AuthenticatedRecommendation"])
def test_a_token_of_an_unrecognised_type_is_refused_not_admitted(value):
    """`authenticity.py:432` — the terminal `else`, D-GC-5's one member.

    Its operator replaces the arm with `pass`, so an unrecognised type would fall through
    the dispatch silently and be treated as validated. That is the admission direction,
    and this is the test that sees it.
    """

    with pytest.raises(UnsupportedRecommendationSourceError, match="expected exactly"):
        _authenticity._validate_authenticated_output(value)


def test_strict_reconstruction_that_yields_a_subclass_is_refused():
    """`authenticity.py:543`. `from_dict` constructs via `cls()` — asserted, not assumed."""

    from ugence_cloud_scaling_controller.planning.recommendation import (
        CapacityActionRecommendation,
    )

    class _Subclass(CapacityActionRecommendation):
        pass

    with pytest.raises(UnsupportedRecommendationSourceError, match="not the exact"):
        _authenticity._require_exact_reconstruction(
            object.__new__(_Subclass), CapacityActionRecommendation
        )


def test_a_malformed_expectation_is_refused_as_syntax_not_as_a_mismatch(recommendation):
    """`authenticity.py:581` and `:582` — the expectation is checked before it is used.

    Neutralising either lets a malformed expectation reach the reconciliation, where it
    fails as a *mismatch*. That is the wrong answer to the wrong question: the caller
    supplied something that is not a digest at all, and telling them their digest did not
    match invites them to go looking for a tampered artifact. So the test asserts the
    syntax diagnosis specifically, not merely that something was refused.
    """

    with pytest.raises(RecommendationAuthenticityError, match="canonical digest"):
        _authenticity.authenticate_controller_output(
            recommendation, expected_recommendation_digest="not-a-digest"
        )


def test_an_abstention_whose_expectation_does_not_match_is_refused():
    """`authenticity.py:621`. An expectation is optional on the abstention path.

    Optional does not mean ignored: when one is supplied it is still reconciled, and
    neutralising the guard would silently accept an abstention that does not hash to what
    the caller said it should.
    """

    from conftest import build_abstention

    abstention = build_abstention()
    with pytest.raises(RecommendationAuthenticityError):
        _authenticity.authenticate_controller_output(
            abstention, expected_recommendation_digest="sha256:" + "b" * 64
        )


def test_a_serialized_artifact_without_a_schema_tag_is_refused(recommendation):
    """`authenticity.py:642`. Which canonical form a mapping claims to be is not guessed."""

    document = dict(recommendation.to_canonical_dict())
    document.pop("schema_version", None)
    with pytest.raises(UnsupportedRecommendationSourceError, match="explicit"):
        _authenticity.authenticate_controller_output(document)


@pytest.mark.parametrize(
    "artifact, base_name, builder",
    [
        ("recommendation", "CapacityActionRecommendation", "recommendation"),
        ("abstention", "RecommendationAbstention", "abstention"),
    ],
)
def test_a_serialized_form_reconstructing_to_a_subclass_is_refused(
    monkeypatch, recommendation, artifact, base_name, builder
):
    """`authenticity.py:665` and `:686`. The serialized path's exactness assertion.

    `from_dict` constructs via `cls(...)` today, so the only way to reach these is to
    install a resolution where it does not — which is exactly the case ADR Phase 5 §9.2
    says is not an equivalent mutant, since the controller is separately versioned under
    an open-ended pin. The resolution is installed here rather than argued about: patch
    the reconstructor to return the subclass a future release could, and the guard is the
    difference between refusing and digesting a non-canonical instance.
    """

    from conftest import build_abstention
    from ugence_cloud_scaling_controller.planning import recommendation as _rec_module

    base = getattr(_rec_module, base_name)

    class _Subclass(base):  # type: ignore[misc, valid-type]
        pass

    source = recommendation if builder == "recommendation" else build_abstention()
    document = dict(source.to_canonical_dict())

    original = base.from_dict

    def _from_dict(payload):
        rebuilt = original(payload)
        # Same field values, subclass type — what a release that specialised `from_dict`
        # would hand back. Constructed rather than shallow-copied so the subclass runs the
        # controller's own `__post_init__` and is a genuinely valid instance: the only
        # thing wrong with it is that it is not the exact canonical base.
        return _Subclass(
            **{
                field.name: getattr(rebuilt, field.name)
                for field in dataclasses.fields(rebuilt)
            }
        )

    monkeypatch.setattr(base, "from_dict", staticmethod(_from_dict))
    with pytest.raises(UnsupportedRecommendationSourceError, match="not the exact"):
        _authenticity.authenticate_controller_output(document)


# --- projection.py: the correlation id ------------------------------------------------


def test_a_correlation_id_that_is_not_a_string_is_refused(token):
    """`projection.py:357`. `None` is allowed; a non-string is not."""

    forecast = token.recommendation.forecast_evidence.forecast
    forged_forecast = _forge(forecast, correlation_id=7)
    forged_evidence = _forge(
        token.recommendation.forecast_evidence, forecast=forged_forecast
    )
    forged_recommendation = _forge(
        token.recommendation, forecast_evidence=forged_evidence
    )
    # The token's digest must keep describing its recommendation, or the authenticity
    # re-check inside `project_recommendation` refuses first and this guard is never
    # reached — the pair of guards is ordered, and the isolating input has to respect it.
    forged_token = _forge(
        token,
        recommendation=forged_recommendation,
        recommendation_digest=forged_recommendation.digest(),
    )
    with pytest.raises(ProjectionError, match="correlation_id must be a string or None"):
        _projection.project_recommendation(forged_token)


def test_a_malformed_expectation_is_refused_before_the_source_is_typed(recommendation):
    """`authenticity.py:581` and `:582`, isolated on the **typed** half, not the message.

    `_reconcile` checks the expectation's syntax too, so on the supported-source path
    neutralising these two produces the same `RecommendationAuthenticityError` with
    different prose — a message-only kill, which §9.1 does not accept as evidence that a
    guard decided anything.

    The isolating input is an *unsupported* source, because these two run **before** the
    exact-type admission below them. With the guard the caller is told their expectation
    is not a digest; without it, control reaches the type dispatch and they are told their
    source is the wrong type. Different exception class, so the kill is attributable to
    the typed refusal.
    """

    with pytest.raises(RecommendationAuthenticityError, match="canonical digest"):
        _authenticity.authenticate_controller_output(
            object(), expected_recommendation_digest="not-a-digest"
        )


# --- Declared unscorable: the tests that measure each exclusion's claim ---------------
#
# Each of these measures a claim made in `guard_sweep.py`'s `exclusions` for this
# package. None of them asserts that a guard is untested — they assert *why* no isolating
# input exists, which is what makes an exclusion checkable rather than an opinion.


def test_no_invalid_authenticated_token_can_exist_to_reach_the_revalidations():
    """`adapter.py:152` and `:186` — `unreachable-behind-earlier-guard`, measured.

    Both re-run `_validate_authenticated_output` on a token
    `authenticate_controller_output` has just produced. Every such token is built by one
    of the two `Authenticated*` constructors, and each runs the same validation in its own
    `__post_init__` (`authenticity.py:216,242`). So an invalid token cannot come into
    existence, and no caller-supplied value reaches either call site: `project` and
    `evaluate` both take a *source*, never a token.

    This is what makes those two different from the guards *inside*
    `_validate_authenticated_output` (`:429`/`:431`/`:432`), which are scored and killed —
    there a forged token is a constructible input, because the function is reachable with
    one.
    """

    from conftest import build_abstention

    recommendation = build_recommendation()
    for kwargs in ({"executable": True}, {"authority_granted": True}):
        with pytest.raises(RecommendationAuthenticityError):
            _authenticity.AuthenticatedRecommendation(
                recommendation=recommendation,
                recommendation_digest=recommendation.digest(),
                expectation_source="caller-supplied-expectation",
                **kwargs,
            )
        with pytest.raises(RecommendationAuthenticityError):
            _authenticity.AuthenticatedAbstention(
                abstention=build_abstention(), **kwargs
            )


def test_projection_raises_neither_input_nor_authenticity_errors_of_its_own(token):
    """`adapter.py:211` and `:222` — `unreachable-behind-earlier-guard`, measured.

    Gate 3 wraps `project_recommendation` in handlers for `RecommendationInputError` and
    `RecommendationAuthenticityError`. Structurally, `projection.py` raises neither: it
    raises `ProjectionError`, and the only route to a `RecommendationAuthenticityError` is
    `_validate_authenticated_recommendation`, which cannot fail on a token that both the
    constructor and gate 1 have already validated.

    Measured two ways rather than argued: no `raise` of either class exists anywhere in
    `projection.py`, and a genuine token projects without either being raised.
    """

    import ast
    import pathlib

    source = pathlib.Path(_projection.__file__).read_text(encoding="utf-8")
    raised = {
        node.exc.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
    }
    assert "RecommendationInputError" not in raised
    assert "RecommendationAuthenticityError" not in raised
    assert _projection.project_recommendation(token) is not None


def test_every_projection_carries_no_evaluation_time(token):
    """`adapter.py:266` — `unreachable-behind-earlier-guard`, measured.

    The adapter re-checks `request.evaluation_time is not None` immediately before
    submission. `projection.py:139` already refuses any projection whose request carries
    one, and the projection has no parameter through which to supply it, so the request
    the adapter re-checks is always the one `projection.py:139` admitted.
    """

    projected = _projection.project_recommendation(token)
    assert projected.request.evaluation_time is None
    forged_request = _forge(
        projected.request, evaluation_time=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    with pytest.raises(ProjectionError, match="evaluation_time"):
        _repost(_forge(projected, request=forged_request))


def test_the_forecast_digest_guard_shares_its_outcome_with_the_loop_below_it(
    recommendation,
):
    """`projection.py:252` — `diagnostic-only`, measured.

    With the guard removed, a missing forecast digest falls through to the `value is None`
    check inside the loop, which raises the **same** `ProjectionError` for the same input.
    Only the prose moves — "required (ADR §6)" becomes "required and must not be None" —
    and §9.1 makes the message prose. Scoring it would need a finer discriminator in the
    pair, not a better test.
    """

    forged = _forge(recommendation)
    object.__setattr__(forged, "forecast_evidence_digest", lambda: None)
    with pytest.raises(ProjectionError) as first:
        _projection._evidence_references(forged)

    # The successor, reached directly by moving the same absence to a later candidate.
    other = _forge(recommendation)
    object.__setattr__(other, "cost_evidence_digest", lambda: None)
    with pytest.raises(ProjectionError) as second:
        _projection._evidence_references(other)

    assert type(first.value) is type(second.value), (
        "the successor produces the same typed outcome, so the guard changes the "
        "diagnosis and not the answer"
    )


def test_the_seam_return_check_shares_its_outcome_with_the_outcome_dataclass(
    recommendation,
):
    """`adapter.py:271` — `diagnostic-only`, measured.

    A duck-typed seam return that gets past this check reaches
    `CloudScalingRiskOutcome.__post_init__`, whose `outcomes.py:131` raises the same
    `NonExecutableInvariantError` for every such value. The guard names the seam as the
    culprit instead of the outcome, which is worth keeping and is not an authorization
    answer.
    """

    class _LookAlike:
        pass

    with pytest.raises(NonExecutableInvariantError, match="requires a canonical"):
        CloudScalingRiskOutcome(
            status=AdapterOutcomeStatus.RISK_DECISION, decision=_LookAlike()
        )
