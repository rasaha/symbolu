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
