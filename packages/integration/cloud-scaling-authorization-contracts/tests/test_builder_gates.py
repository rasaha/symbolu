"""F-3: gates in the builder that no earlier test isolated.

The audit found mutation kills attributed to the wrong gate. A test that fails because an
*upstream* gate rejected the input proves nothing about the gate that was removed — remove
the downstream gate and the upstream one still fires, so the mutation looks "killed" while
the real check is unguarded.

Every test here therefore constructs an input that **passes every unrelated gate** and
differs only in the property owned by the gate under test. Each is verified to fail when —
and only when — that exact gate is removed.

The shared technique: gates late in the builder are unreachable through ordinary
construction because an earlier gate or a dataclass ``__post_init__`` already rejected the
input. To reach them, the artifact is built validly and then forced past its own
constructor with ``object.__setattr__``, and any digest that depends on it is rebuilt so the
binding checks still pass. That is not an artificial scenario: it is exactly what a
fabricated or replayed artifact looks like, and the builder's independent re-check is the
only thing standing behind it.

--------------------------------------------------------------------------------------
Mutation-residue disclosure — corrected, and deliberately kept in full
--------------------------------------------------------------------------------------

An earlier revision of this docstring and of the PR body stated that the only package-wide
mutation residues were the ``_require_int`` / ``_require_datetime`` helpers and the
``context_digest`` / ``request_digest`` sibling re-derivation. **That disclosure was
incomplete**, and it is recorded here rather than quietly replaced.

The accurate sequence:

1. The F-3 remediation swept the builder and closed **six** discovered gaps, plus the
   schema-version, candidate exact-type and reconciler re-derivation gates.
2. An **independent closure audit then found two further property lapses** that the sweep
   had not reached — both in ``reconcile_phase4``, both security-relevant:
   the projection-versus-decision **tenant** gate and the projection-versus-decision
   **subject-digest** gate. Removing either allowed a candidate to be built across the
   mismatch, carrying a byte-identical candidate digest.
3. Those two are closed by ``test_a_decision_issued_for_another_tenant_is_refused`` and
   ``test_a_decision_made_about_another_subject_is_refused`` below, each measured to fail
   only for its own gate.

Surviving mutations, classified — a guard may be listed here **only** if its removal
creates no new constructible invalid candidate:

* **Sibling-backed.** ``context_digest`` and ``request_digest`` re-derivation. Each is
  backed by another gate that fires on the same input with the same typed reason, so
  removing one alone is unobservable. The property is enforced twice.
* **Unreachable defence in depth.** ``_require_int`` / ``_require_datetime`` on projected
  magnitudes and timestamps. Those values sit inside the context digest, so tampering trips
  the digest re-derivation first. They guard a route no public entry point can take.
* **Non-security validation.** Message-shaping and formatting guards whose removal changes
  only the text of a refusal, never whether one occurs.

The standing rule, which the closure audit's two findings enforce: **no security-relevant
guard whose removal creates a new constructible invalid candidate may survive without a
focused test.** Gate kills are credited only to tests that exercise the gate itself.
"""

from __future__ import annotations

import pytest

from conftest import (
    build_attestation,
    build_decision,
    build_policy_binding,
    build_projection,
    build_recommendation,
    build_target_scope,
    production_subject,
)
from ugence_cloud_scaling_authorization_contracts import (
    MagnitudeBoundError,
    TargetScopeError,
    build_capacity_authorization_candidate,
)


def _attempt(projection, decision, scope, *, policy=None, attestation=None):
    return build_capacity_authorization_candidate(
        projection=projection,
        decision=decision,
        producer_attestation=(
            attestation
            if attestation is not None
            else build_attestation(recommendation_digest=projection.recommendation_digest)
        ),
        policy_binding=policy if policy is not None else build_policy_binding(scope),
        target_scope=scope,
    )


def test_target_scope_naming_another_tenant_is_refused(projection, decision):
    """G-1: the builder's cross-tenant target-scope gate, isolated.

    Everything reconciles: the projection and the decision agree on the tenant, the
    attestation binds the right recommendation, the policy binds this exact scope, the
    action and magnitudes match, the placement fields match. **Only**
    ``ExecutionTargetScope.tenant_id`` names a different tenant.

    Without this gate a candidate would be issued whose execution target belongs to
    somebody else's tenant while every Phase 4 digest reconciles perfectly — the projection
    and decision never see the scope, so nothing upstream can catch it.
    """

    scope = build_target_scope(projection, tenant_id="tenant-victim")
    # The policy binds the tampered scope by digest, so the policy/target gate passes and
    # cannot absorb the failure.
    policy = build_policy_binding(scope)
    assert scope.tenant_id != projection.tenant_id
    assert policy.target_scope_digest == scope.digest()

    with pytest.raises(TargetScopeError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "tenant_mismatch"


def test_target_scope_misstating_the_starting_magnitude_is_refused(projection, decision):
    """G-2: the builder's ``magnitude_before`` gate, isolated.

    This one was found by an exhaustive guard sweep, not by inspection — the existing
    substitution tests parametrized over placement fields (region, zone, cluster, resource,
    environment) and never varied the starting magnitude, so nothing exercised it.

    It matters because ``magnitude_before`` is what the *delta* is measured from. A scope
    that overstates its starting point understates the change it is asking for: the same
    absolute target looks like a smaller step and slides under a delta ceiling. The scope's
    own ``__post_init__`` cannot catch it — its arithmetic is self-consistent — so only the
    builder's comparison against the reconciled Phase 4 facts can.
    """

    understated = projection.context.magnitude_before + 1
    scope = build_target_scope(projection, magnitude_before=understated)
    policy = build_policy_binding(scope)
    # Self-consistent, and the requested target is unchanged — only the origin moved.
    assert scope.requested_magnitude == projection.context.magnitude_after
    assert scope.requested_delta < abs(
        projection.context.magnitude_after - projection.context.magnitude_before
    )

    with pytest.raises(TargetScopeError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "target_substitution"


def test_target_scope_requesting_a_different_target_magnitude_is_refused(
    projection, decision
):
    """G-3: the builder's ``requested_magnitude`` gate, isolated.

    Also surfaced by the guard sweep rather than by inspection. The scope asks for a
    *different final capacity* than the one the decision was made about, while starting from
    the same origin and staying inside its own delta ceiling — so neither the scope's
    ``__post_init__`` nor the policy binding notices.

    This is the most direct form of the attack the whole package exists to prevent: a risk
    decision granted for scaling to N, carried into a request to scale to N+1.
    """

    inflated = projection.context.magnitude_after + 1
    scope = build_target_scope(projection, requested_magnitude=inflated)
    policy = build_policy_binding(scope)
    assert scope.magnitude_before == projection.context.magnitude_before
    assert scope.requested_magnitude != projection.context.magnitude_after

    with pytest.raises(TargetScopeError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "target_substitution"


def test_a_scope_forced_past_its_own_account_check_is_refused(projection, decision):
    """G-4: the builder's independent account-binding gate, isolated.

    ``ExecutionTargetScope.__post_init__`` refuses an empty ``account_id``, so an ordinary
    caller cannot reach the builder's own check. A fabricated scope — one forced past its
    constructor — can, and this is the gate that catches it. Without it, an unaccounted
    execution target reaches a candidate.
    """

    scope = build_target_scope(projection)
    object.__setattr__(scope, "account_id", "")  # forced past __post_init__
    policy = build_policy_binding(scope)  # binds the tampered scope's digest

    with pytest.raises(TargetScopeError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "missing_account_binding"


def test_a_scope_forced_past_its_own_magnitude_ceiling_is_refused(projection, decision):
    """G-5: the builder's independent magnitude-bound gate, isolated.

    The scope's own ``__post_init__`` enforces ``requested <= max``, and the builder
    separately requires the scope's maxima to equal the policy's. Both are satisfied here:
    the ceiling is lowered *after* construction and the policy is issued against the
    lowered ceiling, so the bounds agree and only the requested magnitude exceeds them.

    This is the check that stops a fabricated scope from carrying a request above the
    ceiling the policy actually grants.
    """

    scope = build_target_scope(projection)
    ceiling = projection.context.magnitude_after - 1
    object.__setattr__(scope, "max_permitted_magnitude", ceiling)  # forced past __post_init__
    policy = build_policy_binding(scope, max_magnitude=ceiling)
    assert policy.max_permitted_magnitude == scope.max_permitted_magnitude
    assert scope.requested_magnitude > policy.max_permitted_magnitude

    with pytest.raises(MagnitudeBoundError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "requested_magnitude_above_maximum"


def test_a_scope_forced_past_its_own_delta_ceiling_is_refused(projection, decision):
    """G-6: the builder's independent delta-bound gate, isolated.

    Same construction as G-5, against the delta ceiling. The delta compared here is the one
    derived from the **reconciled Phase 4 facts**, not from the scope — so a fabricated
    scope cannot understate its own delta to slip under the bound.
    """

    scope = build_target_scope(projection)
    delta = abs(projection.context.magnitude_after - projection.context.magnitude_before)
    object.__setattr__(scope, "max_permitted_delta", delta - 1)
    policy = build_policy_binding(scope, max_delta=delta - 1)
    assert policy.max_permitted_delta == scope.max_permitted_delta

    with pytest.raises(MagnitudeBoundError) as exc:
        _attempt(projection, decision, scope, policy=policy)
    assert exc.value.reason.value == "delta_above_maximum"


def test_none_of_these_gates_is_reached_by_a_well_formed_request(projection, decision):
    """The control: the same construction path succeeds when nothing is tampered.

    Without this, a test above could be passing because the builder rejects *everything*.
    """

    scope = build_target_scope(projection)
    candidate = _attempt(projection, decision, scope)
    assert candidate.target_scope.tenant_id == projection.tenant_id
    assert candidate.grants_authority is False


@pytest.mark.parametrize(
    "label",
    ["cross_tenant_scope", "understated_origin", "inflated_target",
     "forced_account", "forced_magnitude", "forced_delta"],
)
def test_no_candidate_and_no_collaborator_on_any_isolated_gate(
    projection, decision, label
):
    """Every isolated gate fails closed: no candidate, and nothing downstream is reached."""

    scope = build_target_scope(projection)
    if label == "cross_tenant_scope":
        scope = build_target_scope(projection, tenant_id="tenant-victim")
        policy = build_policy_binding(scope)
    elif label == "understated_origin":
        scope = build_target_scope(
            projection, magnitude_before=projection.context.magnitude_before + 1
        )
        policy = build_policy_binding(scope)
    elif label == "inflated_target":
        scope = build_target_scope(
            projection, requested_magnitude=projection.context.magnitude_after + 1
        )
        policy = build_policy_binding(scope)
    elif label == "forced_account":
        object.__setattr__(scope, "account_id", "")
        policy = build_policy_binding(scope)
    elif label == "forced_magnitude":
        ceiling = projection.context.magnitude_after - 1
        object.__setattr__(scope, "max_permitted_magnitude", ceiling)
        policy = build_policy_binding(scope, max_magnitude=ceiling)
    else:
        delta = abs(projection.context.magnitude_after - projection.context.magnitude_before)
        object.__setattr__(scope, "max_permitted_delta", delta - 1)
        policy = build_policy_binding(scope, max_delta=delta - 1)

    built = None
    with pytest.raises((TargetScopeError, MagnitudeBoundError)):
        built = _attempt(projection, decision, scope, policy=policy)
    assert built is None


# ======================================================================================
# Schema-version gates — surfaced by the remediated guard sweep
# ======================================================================================


def test_unsupported_schema_version_is_refused_on_every_artifact(
    projection, decision, attestation, target_scope, policy_binding
):
    """G-7: each artifact's schema-version gate, with its own typed reason.

    Also a sweep finding. Removing any of these gates does not make the artifact
    *accepted* — the schema tag is inside the canonical payload, so a wrong tag fails the
    digest check instead — but it changes a precise ``unsupported_schema_version`` refusal
    into a generic digest failure. The reason code is what an operator reads, so it is part
    of the contract, and a test that never asserts it lets the gate rot.
    """

    import dataclasses

    from ugence_cloud_scaling_authorization_contracts import (
        CandidateConstructionError,
        CapacityAuthorizationCandidate,
    )

    for artifact in (attestation, target_scope, policy_binding):
        with pytest.raises(CandidateConstructionError) as exc:
            dataclasses.replace(artifact, schema_version="some-other-schema-1")
        assert exc.value.reason.value == "unsupported_schema_version", (
            f"{type(artifact).__name__} did not report unsupported_schema_version"
        )

    candidate = _attempt(projection, decision, target_scope, policy=policy_binding)
    fields = {f: getattr(candidate, f) for f in candidate.__dataclass_fields__}
    fields["schema_version"] = "some-other-schema-1"
    with pytest.raises(CandidateConstructionError) as exc:
        CapacityAuthorizationCandidate(**fields)
    assert exc.value.reason.value == "unsupported_schema_version"


def test_the_schema_tag_is_inside_the_candidate_digest(candidate):
    """Defence in depth behind the gate above: the tag is covered by the digest too."""

    assert candidate.digest_payload()["schema_version"] == candidate.schema_version


def test_candidate_post_init_refuses_a_wrong_typed_carried_artifact(candidate):
    """G-8: the candidate's own exact-type gate on its three carried artifacts.

    The builder already type-checks its arguments, so this gate is only reachable when a
    ``CapacityAuthorizationCandidate`` is constructed **directly** — which is a public,
    supported thing to do (deserialization, reconstruction from an audit record). Without
    it, a duck-typed look-alike would be carried and only fail later, on digest
    computation, with a confusing error.
    """

    from ugence_cloud_scaling_authorization_contracts import ExactTypeError

    class LooksLikeAScope:
        def to_canonical_dict(self):
            return candidate.target_scope.to_canonical_dict()

        def digest(self):
            return candidate.target_scope_digest

    for field in ("target_scope", "policy_binding", "producer_attestation"):
        fields = {f: getattr(candidate, f) for f in candidate.__dataclass_fields__}
        fields[field] = LooksLikeAScope()
        with pytest.raises(ExactTypeError) as exc:
            type(candidate)(**fields)
        assert exc.value.reason.value == "unsupported_exact_type", field


def test_a_tampered_context_magnitude_is_rejected_before_reconciliation_completes(
    projection, decision
):
    """The *property*, stated honestly — not a claim about a specific gate.

    The reconciler also carries a ``_require_int`` guard on the projected magnitudes. That
    guard is **unreachable through the public entry point**: the magnitudes are inside the
    context digest, so any tampering trips the context-digest re-derivation first. Removing
    ``_require_int`` therefore does *not* make this test fail, and claiming it does would be
    exactly the misattribution this module exists to avoid — a downstream failure sold as
    coverage of an upstream gate.

    So this test asserts only what it actually proves: a fabricated context with a
    non-integer or negative magnitude never yields reconciled facts. ``_require_int``
    remains as defence in depth for any future caller that reaches
    ``ReconciledPhase4Facts`` by another route, and is documented as unreachable rather
    than covered.
    """

    from ugence_cloud_scaling_authorization_contracts import (
        ReconciliationError,
        reconcile_phase4,
    )

    original = projection.context.magnitude_after
    for bad in (9.5, True, -1):
        object.__setattr__(projection.context, "magnitude_after", bad)
        try:
            with pytest.raises(ReconciliationError):
                reconcile_phase4(projection, decision)
        finally:
            object.__setattr__(projection.context, "magnitude_after", original)


# ======================================================================================
# Reconciler re-derivation gates — isolated via a projection that skipped its constructor
# ======================================================================================


def _fabricated_projection(projection, **overrides):
    """An EXACT ``CapacityRiskSubjectProjection`` that never ran ``__post_init__``.

    ``object.__new__`` produces a genuine instance of the exact type, so Phase 5A's
    exact-type admission accepts it — correctly, because it *is* the type. What it has not
    done is pass Phase 4C's own constructor checks. That is the whole reason Phase 5A
    re-derives the chain instead of trusting it.
    """

    fake = type(projection).__new__(type(projection))
    for field in type(projection).__dataclass_fields__:
        object.__setattr__(fake, field, getattr(projection, field))
    for field, value in overrides.items():
        object.__setattr__(fake, field, value)
    return fake


#: Only the two digests whose re-derivation gate was **measured** to be individually
#: load-bearing. ``context_digest`` and ``request_digest`` were measured too and are NOT
#: listed: each is backed by a sibling gate that fires on the same input with the same typed
#: reason (``p_context.digest() != p_context_digest`` for the first, the projection-versus-
#: decision ``request_digest`` comparison for the second), so removing either one alone is
#: not observable. The property is enforced twice; the individual gate is not isolatable.
#: Listing them here would count a sibling-gate failure as coverage — the exact defect the
#: audit raised — so they are documented instead of claimed.
@pytest.mark.parametrize(
    "field,reason",
    [
        ("subject_digest", "subject_digest_mismatch"),
        ("recommendation_digest", "recommendation_mismatch"),
    ],
)
def test_a_fabricated_projection_with_a_tampered_digest_is_refused(
    projection, decision, field, reason
):
    """G-10: the reconciler's independent re-derivation, isolated.

    These guards duplicate checks that ``CapacityRiskSubjectProjection.__post_init__``
    already performs, so a *legitimately constructed* projection can never reach them — which
    is why an ordinary mutation of them looks survivable. They are not redundant: a
    projection built through ``object.__new__`` skips that constructor entirely while
    remaining the exact admitted type, and then **only** Phase 5A's own re-derivation stands
    between a forged digest chain and a candidate.

    Phase 5A's stated design is to re-derive rather than trust. This is the test that makes
    that claim mean something.
    """

    from ugence_cloud_scaling_authorization_contracts import (
        ReconciliationError,
        reconcile_phase4,
    )

    fake = _fabricated_projection(projection, **{field: "sha256:" + "0" * 64})
    assert type(fake) is type(projection)  # the exact-type gate admits it

    with pytest.raises(ReconciliationError) as exc:
        reconcile_phase4(fake, decision)
    assert exc.value.reason.value == reason


def test_a_fabricated_projection_yields_no_candidate(
    projection, decision, attestation, target_scope, policy_binding
):
    """And the full production entry point refuses it too — no candidate, no partial."""

    from ugence_cloud_scaling_authorization_contracts import ReconciliationError

    fake = _fabricated_projection(projection, context_digest="sha256:" + "0" * 64)
    built = None
    with pytest.raises(ReconciliationError):
        built = build_capacity_authorization_candidate(
            projection=fake,
            decision=decision,
            producer_attestation=attestation,
            policy_binding=policy_binding,
            target_scope=target_scope,
        )
    assert built is None


# ======================================================================================
# F-A: the projection-versus-decision binding gates, isolated
# ======================================================================================
#
# The independent closure audit found that neither of these gates was exercised by any
# test, and that removing either one lets a candidate be built across the mismatch.
#
# Nothing caught them because the existing cross-tenant and cross-subject tests build two
# *different projections* and evaluate each separately. That makes the decision disagree
# with the projection on `request_digest` too, so the request-digest gate — which sits
# between these two — fires first and the kill was credited to the wrong check.
#
# The isolation technique here is different and much sharper: take the genuine decision
# for THIS projection and change exactly one field on it. `dataclasses.replace` re-runs
# `SubjectRiskDecision.__post_init__`, so the result is an internally valid decision — its
# snapshots still bind, its digests still reconcile, every unrelated fact still matches.
# Only the single disputed field differs.
#
# Both lapses were reproduced before these tests were written. In each case a candidate was
# constructed across the mismatch **carrying the unchanged frozen candidate digest**, because
# the candidate takes its tenant and subject from the *projection* — so a decision issued for
# another tenant or another workload leaves no trace at all downstream. That is what makes
# these gates security-relevant rather than tidy: they are the only place the disagreement
# is observable.


def _decision_variant(decision, **overrides):
    """A genuine, internally valid ``SubjectRiskDecision`` differing in one field.

    ``dataclasses.replace`` re-runs ``__post_init__``, so the returned decision has passed
    Risk Authority's own construction checks — snapshot/digest binding included. This is not
    a fabricated object: it is exactly the artifact a mis-routed or replayed evaluation would
    hand to Phase 5A.
    """

    import dataclasses

    return dataclasses.replace(decision, **overrides)


def test_a_decision_issued_for_another_tenant_is_refused(
    projection, decision, attestation, target_scope, policy_binding
):
    """F-A/1: the projection-versus-decision **tenant** gate, isolated.

    The decision is internally valid and agrees with the projection on everything —
    `request_digest`, `subject_digest`, the decision snapshot, the recommendation, the
    action, the policy binding, the attestation and the target scope. Its own `tenant_id`
    names a different tenant, and that is the only disagreement.

    Without this gate a candidate is built for the projection's tenant on the authority of a
    risk decision issued for somebody else's, and — because the candidate takes its tenant
    from the projection — the resulting candidate digest is byte-identical to a legitimate
    one. There is no downstream artifact in which the substitution could later be noticed.
    """

    from ugence_cloud_scaling_authorization_contracts import (
        AuthorizationCandidateRejectionReason as Reason,
    )
    from ugence_cloud_scaling_authorization_contracts import ReconciliationError

    foreign = _decision_variant(decision, tenant_id="tenant-victim")
    # Everything that could otherwise absorb the failure is asserted to still agree.
    assert foreign.tenant_id != projection.tenant_id
    assert foreign.request_digest == projection.request_digest
    assert foreign.subject_digest == projection.subject_digest
    assert foreign.decision_digest == decision.decision_digest
    assert foreign.decision_snapshot["tenant_id"] == projection.tenant_id

    built = None
    with pytest.raises(ReconciliationError) as exc:
        built = build_capacity_authorization_candidate(
            projection=projection,
            decision=foreign,
            producer_attestation=attestation,
            policy_binding=policy_binding,
            target_scope=target_scope,
        )

    assert built is None, "no candidate may exist after a tenant mismatch"
    assert exc.value.reason is Reason.TENANT_MISMATCH
    # Attribution: the *direct* projection-vs-decision comparison, not the decision-snapshot
    # tenant check further down, which shares this reason code. The snapshot still names the
    # projection's tenant (asserted above), so that sibling gate cannot be the source — and
    # the message names both sides of the direct comparison.
    assert "vs decision" in str(exc.value)
    assert "tenant-victim" in str(exc.value)


def test_a_decision_made_about_another_subject_is_refused(
    projection, decision, attestation, target_scope, policy_binding
):
    """F-A/2: the projection-versus-decision **subject-digest** gate, isolated.

    Same construction, one field: the decision carries the `subject_digest` of a *different
    real workload*, produced by projecting a genuine recommendation for that workload rather
    than by inventing a digest-shaped string.

    Tenant, request digest, decision snapshot and every Phase 5 binding still agree, so
    neither the tenant gate above nor the request-digest gate between them can fire. Without
    this gate, a risk decision made about one workload authorises a capacity action against
    another — again under a byte-identical candidate digest.
    """

    from ugence_cloud_scaling_authorization_contracts import (
        AuthorizationCandidateRejectionReason as Reason,
    )
    from ugence_cloud_scaling_authorization_contracts import ReconciliationError

    other = build_projection(
        build_recommendation(subject=production_subject(workload_id="payments-api"))
    )
    assert other.subject_digest != projection.subject_digest

    foreign = _decision_variant(decision, subject_digest=other.subject_digest)
    assert foreign.tenant_id == projection.tenant_id          # tenant gate cannot fire
    assert foreign.request_digest == projection.request_digest  # request gate cannot fire
    assert foreign.decision_digest == decision.decision_digest

    built = None
    with pytest.raises(ReconciliationError) as exc:
        built = build_capacity_authorization_candidate(
            projection=projection,
            decision=foreign,
            producer_attestation=attestation,
            policy_binding=policy_binding,
            target_scope=target_scope,
        )

    assert built is None, "no candidate may exist after a subject mismatch"
    assert exc.value.reason is Reason.SUBJECT_MISMATCH
    assert "subject_digest" in str(exc.value)


@pytest.mark.parametrize("field", ["tenant_id", "subject_digest"])
def test_the_projection_decision_binding_reaches_no_later_authority(
    projection, decision, attestation, target_scope, policy_binding, field
):
    """Both mismatches fail closed before anything downstream is touched.

    Reconciliation runs before any part of a candidate is constructed, so a mismatch here
    cannot produce a partial artifact — and there is no collaborator to reach in any case:
    the builder takes no resolver, issuer, gate, broker, executor or clock.
    """

    import inspect

    from ugence_cloud_scaling_authorization_contracts import ReconciliationError

    other = build_projection(
        build_recommendation(subject=production_subject(workload_id="payments-api"))
    )
    value = "tenant-victim" if field == "tenant_id" else other.subject_digest
    foreign = _decision_variant(decision, **{field: value})

    with pytest.raises(ReconciliationError):
        build_capacity_authorization_candidate(
            projection=projection, decision=foreign, producer_attestation=attestation,
            policy_binding=policy_binding, target_scope=target_scope,
        )

    assert set(inspect.signature(build_capacity_authorization_candidate).parameters) == {
        "projection", "decision", "producer_attestation", "policy_binding", "target_scope",
    }
