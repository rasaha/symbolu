"""Resolution semantics: exact mapping, request-derived tenant, and fail closed.

Everything here drives the genuine pipeline — real issuance, real Ed25519
signing, the real registry, real ``resolve_policy``. A resolver proven against a
stubbed authority would prove nothing about the authority it exists to call.

The organising rule is one sentence: **a response is produced only when the
authority answered with a resolution.** Every other outcome raises, which is what
covers the authority's whole reason enumeration by construction rather than by
this module remembering to enumerate it.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from _authority_fixtures import make_signer
from _permission_runtime_fixtures import (
    ADAPTER,
    ADVISORY_INSTANT,
    CASE_REF,
    MULTI,
    POLICY_ID,
    POLICY_VERSION,
    SINGLE,
    STRATEGY_POLICY_REF,
    T_AFTER,
    T_BEFORE,
    TENANT,
    issued_world,
    make_permission_authority,
    make_permission_policy,
    make_request,
    make_resolver,
)
from ugence_agentic_proposer import ReasoningStrategy, StrategyPolicyResponse
from ugence_agentic_proposer_strategy_permission_policy import (
    POLICY_SCOPE_GLOBAL,
    LIFECYCLE_DRAFT,
    StrategyPermissionPolicy,
    strategy_permission_coordinate,
)
from ugence_agentic_proposer_strategy_permission_runtime import (
    HISTORICAL_RESOLUTION,
    PolicyAuthorityStrategyPolicyResolver,
    StrategyPolicyArtifactError,
    StrategyPolicyReferenceBindingError,
    StrategyPolicyTenantScopeError,
    StrategyPolicyUnresolvedError,
    StrategyPolicyVocabularyError,
    StrategyPermissionResolverError,
    UnknownStrategyPolicyReferenceError,
    build_strategy_policy_resolver,
)
from ugence_policy_authority.api import (
    GLOBAL_TENANT,
    HistoricalResolutionRule,
    KeyEntitlement,
    PolicyCoordinate,
    PolicyResolutionReason,
    PolicyRevocationReasonCode,
    revoke_policy,
)

# --------------------------------------------------------------------------- #
# The happy path — the four ratified response fields
# --------------------------------------------------------------------------- #


def test_the_resolver_returns_the_four_ratified_fields():
    _, policy, _, resolver = issued_world()
    response = resolver.resolve(request=make_request())

    assert type(response) is StrategyPolicyResponse
    assert response.strategy_policy_id == policy.metadata.policy_id == POLICY_ID
    assert response.strategy_policy_version == policy.metadata.version == POLICY_VERSION
    assert response.strategy_policy_ref == STRATEGY_POLICY_REF
    assert response.permitted_strategies == (MULTI, SINGLE)


def test_the_version_is_a_string_never_a_number():
    _, _, _, resolver = issued_world()
    version = resolver.resolve(request=make_request()).strategy_policy_version
    assert type(version) is str


def test_the_response_carries_no_verified_boolean():
    """`[R]` None is ratified. A response existing at all is the evidence."""

    _, _, _, resolver = issued_world()
    response = resolver.resolve(request=make_request())
    assert not hasattr(response, "verified")
    assert "verified" not in type(response).model_fields


def test_the_permitted_set_preserves_the_artifact_order():
    _, policy, _, resolver = issued_world(
        permitted=(SINGLE.value, MULTI.value, ReasoningStrategy.REVISED_ADVISORY.value)
    )
    response = resolver.resolve(request=make_request())
    assert [m.value for m in response.permitted_strategies] == list(
        policy.permitted_strategies
    )


def test_the_stamped_identity_is_the_coordinate_the_authority_signed():
    _, policy, record, resolver = issued_world()
    response = resolver.resolve(request=make_request())
    coordinate = strategy_permission_coordinate(policy.metadata)

    assert response.strategy_policy_id == coordinate.policy_id == record.coordinate.policy_id
    assert response.strategy_policy_version == coordinate.version


# --------------------------------------------------------------------------- #
# The mapping — exact only, mints nothing, fails closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "ref",
    [
        STRATEGY_POLICY_REF + "x",
        STRATEGY_POLICY_REF[:-1],
        STRATEGY_POLICY_REF.upper(),
        "policy-authority/strategy-permission",
        "unrelated-reference",
    ],
    ids=["suffix", "prefix", "case", "shorter-prefix", "unrelated"],
)
def test_a_near_miss_reference_fails_closed(ref):
    """No fallback, no prefix match, no newest-version rule."""

    _, _, _, resolver = issued_world()
    with pytest.raises(UnknownStrategyPolicyReferenceError):
        resolver.resolve(request=make_request(strategy_policy_ref=ref))


def test_one_tenant_s_reference_never_reaches_another_tenant_s_coordinate():
    _, _, _, resolver = issued_world()
    with pytest.raises(UnknownStrategyPolicyReferenceError):
        resolver.resolve(request=make_request(tenant_id="tenant-elsewhere"))


def test_the_mapping_is_defensively_copied_at_construction():
    """Mutating the mapping handed in cannot change what the resolver reaches."""

    authority, policy, _, _ = issued_world()
    supplied = {
        (TENANT, STRATEGY_POLICY_REF): strategy_permission_coordinate(policy.metadata)
    }
    resolver = make_resolver(authority, reference_map=supplied)

    supplied[("tenant-attacker", "any-reference")] = strategy_permission_coordinate(
        policy.metadata
    )
    supplied.pop((TENANT, STRATEGY_POLICY_REF))

    assert resolver.resolve(request=make_request()).strategy_policy_id == POLICY_ID
    with pytest.raises(UnknownStrategyPolicyReferenceError):
        resolver.resolve(
            request=make_request(
                tenant_id="tenant-attacker", strategy_policy_ref="any-reference"
            )
        )


def test_the_exposed_mapping_view_is_read_only():
    _, _, _, resolver = issued_world()
    with pytest.raises(TypeError):
        resolver.reference_map[("t", "r")] = None


def test_the_resolver_is_not_rebindable_after_construction():
    _, _, _, resolver = issued_world()
    with pytest.raises(AttributeError):
        resolver._reference_map = {}
    with pytest.raises(AttributeError):
        del resolver._registry


@pytest.mark.parametrize(
    "bad_map",
    [
        {"not-a-tuple": None},
        {(1, "ref"): None},
        {("t", "ref", "extra"): None},
    ],
    ids=["string-key", "non-string-tenant", "three-tuple"],
)
def test_a_malformed_mapping_key_is_refused_at_construction(bad_map):
    authority, policy, _, _ = issued_world()
    key = list(bad_map)[0]
    bad_map[key] = strategy_permission_coordinate(policy.metadata)
    with pytest.raises(TypeError):
        make_resolver(authority, reference_map=bad_map)


def test_a_partial_identity_is_not_a_coordinate():
    """A mapping value must be a complete coordinate, digest included."""

    authority, policy, _, _ = issued_world()
    with pytest.raises(TypeError):
        make_resolver(
            authority,
            reference_map={(TENANT, STRATEGY_POLICY_REF): (POLICY_ID, POLICY_VERSION)},
        )


# --------------------------------------------------------------------------- #
# Tenant handling — request-derived, and non-vacuous
# --------------------------------------------------------------------------- #


def test_the_expected_tenant_is_derived_from_the_request_not_the_coordinate():
    """The authority's own comparison must be able to fail.

    Passing ``coordinate.tenant_id`` would make it vacuous for every coordinate,
    so the value handed over is the request's. A coordinate reachable under a key
    naming a different tenant is refused by this resolver's own pre-check before
    the authority is ever called.
    """

    authority, policy, _, _ = issued_world()
    coordinate = strategy_permission_coordinate(policy.metadata)
    assert coordinate.tenant_id == TENANT

    # A deliberately mis-wired deployment: the key names one tenant, the
    # coordinate another.
    resolver = make_resolver(
        authority,
        reference_map={("tenant-other", STRATEGY_POLICY_REF): coordinate},
    )
    with pytest.raises(StrategyPolicyTenantScopeError):
        resolver.resolve(
            request=make_request(tenant_id="tenant-other")
        )


def test_a_global_scope_coordinate_resolves_under_the_canonical_empty_component():
    policy = make_permission_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="")
    authority = make_permission_authority()
    authority.issue(policy, issued_at=ADVISORY_INSTANT)
    resolver = make_resolver(authority, policy=policy)

    response = resolver.resolve(request=make_request())
    assert response.strategy_policy_id == POLICY_ID
    assert strategy_permission_coordinate(policy.metadata).tenant_id == GLOBAL_TENANT


def test_a_global_scope_coordinate_carrying_a_tenant_is_refused_by_the_pre_check():
    """Constructed directly, because the family itself refuses to build one."""

    authority, policy, _, _ = issued_world()
    malformed = PolicyCoordinate(
        policy_family=strategy_permission_coordinate(policy.metadata).policy_family,
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        content_digest=policy.metadata.content_digest,
        scope=POLICY_SCOPE_GLOBAL,
        tenant_id=TENANT,
    )
    resolver = make_resolver(
        authority, reference_map={(TENANT, STRATEGY_POLICY_REF): malformed}
    )
    with pytest.raises(StrategyPolicyTenantScopeError):
        resolver.resolve(request=make_request())


def test_an_unadmitted_scope_is_refused():
    authority, policy, _, _ = issued_world()
    malformed = dataclasses.replace(
        strategy_permission_coordinate(policy.metadata), scope="REGIONAL"
    )
    resolver = make_resolver(
        authority, reference_map={(TENANT, STRATEGY_POLICY_REF): malformed}
    )
    with pytest.raises(StrategyPolicyTenantScopeError):
        resolver.resolve(request=make_request())


# --------------------------------------------------------------------------- #
# case_ref selects nothing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "case_ref", [CASE_REF, "case-2", "case-entirely-unrelated", "a"]
)
def test_case_ref_is_correlation_context_and_selects_nothing(case_ref):
    """Letting it select would be per-invocation authorization, which is not ratified."""

    _, _, _, resolver = issued_world()
    baseline = resolver.resolve(request=make_request())
    varied = resolver.resolve(request=make_request(case_ref=case_ref))
    assert varied == baseline


def test_case_ref_is_absent_from_every_configured_key():
    _, policy, _, resolver = issued_world()
    for key in resolver.reference_map:
        assert len(key) == 2
        assert CASE_REF not in key


# --------------------------------------------------------------------------- #
# as_of, and the absence of a clock
# --------------------------------------------------------------------------- #


def test_the_caller_s_as_of_is_passed_through_verbatim():
    _, _, _, resolver = issued_world()
    inside = resolver.resolve(request=make_request(as_of=ADVISORY_INSTANT))
    assert inside.strategy_policy_id == POLICY_ID

    for outside in (T_BEFORE, T_AFTER):
        with pytest.raises(StrategyPolicyUnresolvedError):
            resolver.resolve(request=make_request(as_of=outside))


@pytest.mark.parametrize(
    "as_of,expected",
    [
        (T_BEFORE, PolicyResolutionReason.NOT_YET_EFFECTIVE),
        (T_AFTER, PolicyResolutionReason.EXPIRED),
    ],
    ids=["before-window", "after-window"],
)
def test_the_effective_window_is_reported_on_the_reason_attribute(as_of, expected):
    _, _, _, resolver = issued_world()
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request(as_of=as_of))
    assert excinfo.value.reason is expected


# --------------------------------------------------------------------------- #
# Fail closed on everything that is not a resolution
# --------------------------------------------------------------------------- #


def test_a_missing_record_fails_closed():
    policy = make_permission_policy()
    authority = make_permission_authority()  # nothing issued
    resolver = make_resolver(authority, policy=policy)
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is PolicyResolutionReason.NOT_FOUND


def test_a_lifecycle_that_never_issued_fails_closed():
    policy = make_permission_policy(lifecycle_state=LIFECYCLE_DRAFT)
    authority = make_permission_authority()
    resolver = make_resolver(authority, policy=policy)
    with pytest.raises(StrategyPolicyUnresolvedError):
        resolver.resolve(request=make_request())


def test_a_mutated_artifact_under_the_same_coordinate_fails_closed():
    """`§9.4` — a valid signature is required, and a body swap breaks it."""

    authority, policy, _, resolver = issued_world()
    coordinate = strategy_permission_coordinate(policy.metadata)
    tampered = StrategyPermissionPolicy(
        metadata=policy.metadata,
        strategy_policy_ref=policy.strategy_policy_ref,
        permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)),
    )
    assert ADAPTER.describe(tampered).body_digest() != policy.metadata.content_digest
    stored = authority.registry._issued[coordinate]
    authority.registry._issued[coordinate] = dataclasses.replace(
        stored, policy=tampered
    )

    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason in {
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH,
        PolicyResolutionReason.BODY_DIGEST_MISMATCH,
    }


def test_a_forged_issuance_signature_fails_closed():
    authority, policy, _, resolver = issued_world()
    coordinate = strategy_permission_coordinate(policy.metadata)
    stored = authority.registry._issued[coordinate]
    authority.registry._issued[coordinate] = dataclasses.replace(
        stored, signature=b"\x00" * 64
    )
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is PolicyResolutionReason.SIGNATURE_INVALID


def test_an_unknown_signing_key_fails_closed():
    authority, policy, _, _ = issued_world()
    stranger = make_signer(authority_id="attacker.authority", key_id="stranger", seed=9)
    resolver = build_strategy_policy_resolver(
        reference_map={
            (TENANT, STRATEGY_POLICY_REF): strategy_permission_coordinate(
                policy.metadata
            )
        },
        registry=authority.registry,
        signature_verifier=type(authority.key_ring)(
            [stranger.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))]
        ),
        approval_verifier=authority.approval,
        adapters=authority.adapters,
    )
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is PolicyResolutionReason.KEY_UNKNOWN


def test_a_revoked_version_fails_closed_and_no_historical_answer_is_accepted():
    """`§9.5` — historical resolution stays at deny-always."""

    authority, policy, _, resolver = issued_world()
    revoke_policy(
        reference=strategy_permission_coordinate(policy.metadata),
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.ISSUED_IN_ERROR,
        registry=authority.registry,
        adapters=authority.adapters,
        signer=authority.revocation_signer,
        signature_verifier=authority.key_ring,
        revoked_at=ADVISORY_INSTANT + timedelta(days=1),
    )

    assert HISTORICAL_RESOLUTION is HistoricalResolutionRule.DENY_ALWAYS
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is PolicyResolutionReason.REVOKED

    # An as_of strictly before the revocation instant is refused too: a historical
    # answer describes the past and is never accepted at this boundary.
    with pytest.raises(StrategyPolicyUnresolvedError):
        resolver.resolve(
            request=make_request(as_of=ADVISORY_INSTANT - timedelta(seconds=1))
        )


def test_an_unverifiable_revocation_record_is_neither_honoured_nor_ignored():
    authority, policy, _, resolver = issued_world()
    coordinate = strategy_permission_coordinate(policy.metadata)
    revocation = revoke_policy(
        reference=coordinate,
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.ISSUED_IN_ERROR,
        registry=authority.registry,
        adapters=authority.adapters,
        signer=authority.revocation_signer,
        signature_verifier=authority.key_ring,
        revoked_at=ADVISORY_INSTANT + timedelta(days=1),
    )
    authority.registry._revocations[coordinate] = dataclasses.replace(
        revocation, revoking_authority_id="attacker.authority"
    )

    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is (
        PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID
    )


def test_an_approval_withdrawn_after_issuance_invalidates_resolution():
    """`S2B-PF-E=A` — the row that exists only because a verifier is always supplied."""

    from ugence_policy_authority.api import ApprovalVerificationStatus

    authority, policy, _, resolver = issued_world()
    assert resolver.resolve(request=make_request()).strategy_policy_id == POLICY_ID

    authority.approval.status = ApprovalVerificationStatus.REVOKED
    with pytest.raises(StrategyPolicyUnresolvedError) as excinfo:
        resolver.resolve(request=make_request())
    assert excinfo.value.reason is PolicyResolutionReason.APPROVAL_PROOF_INVALID


def test_an_approval_verifier_is_required_at_construction():
    """Without one the row above is unreachable, so it is not optional here."""

    authority, policy, _, _ = issued_world()
    reference_map = {
        (TENANT, STRATEGY_POLICY_REF): strategy_permission_coordinate(policy.metadata)
    }
    for verifier in (None, object()):
        with pytest.raises(TypeError):
            PolicyAuthorityStrategyPolicyResolver(
                reference_map=reference_map,
                registry=authority.registry,
                signature_verifier=authority.key_ring,
                adapters=authority.adapters,
                approval_verifier=verifier,
            )


def test_a_foreign_artifact_under_the_coordinate_is_refused_by_type():
    """The post-check is an exact runtime type test, not ``isinstance``."""

    authority, policy, _, resolver = issued_world()

    class Extended(StrategyPermissionPolicy):
        pass

    coordinate = strategy_permission_coordinate(policy.metadata)
    stored = authority.registry._issued[coordinate]
    sneaky = Extended(
        metadata=policy.metadata,
        strategy_policy_ref=policy.strategy_policy_ref,
        permitted_strategies=policy.permitted_strategies,
    )
    authority.registry._issued[coordinate] = dataclasses.replace(stored, policy=sneaky)

    # The authority refuses first, because no adapter recognizes the subclass; the
    # resolver's own type post-check stands behind that rather than in front of it.
    with pytest.raises(StrategyPermissionResolverError) as excinfo:
        resolver.resolve(request=make_request())
    assert isinstance(
        excinfo.value, (StrategyPolicyUnresolvedError, StrategyPolicyArtifactError)
    )


def test_a_policy_signed_for_another_reference_is_refused():
    """`§5.2` — the caller's value must match a value the authority signed."""

    policy = make_permission_policy(strategy_policy_ref="some/other/reference")
    authority = make_permission_authority()
    authority.issue(policy, issued_at=ADVISORY_INSTANT)
    resolver = make_resolver(authority, policy=policy)

    with pytest.raises(StrategyPolicyReferenceBindingError):
        resolver.resolve(request=make_request(strategy_policy_ref=STRATEGY_POLICY_REF))


def test_an_alien_token_in_a_forged_artifact_raises_the_vocabulary_error():
    """Hand-forged, because the family refuses to construct such an artifact."""

    authority, policy, _, resolver = issued_world()
    forged = object.__new__(StrategyPermissionPolicy)
    object.__setattr__(forged, "metadata", policy.metadata)
    object.__setattr__(forged, "strategy_policy_ref", policy.strategy_policy_ref)
    object.__setattr__(forged, "permitted_strategies", ("STAGED_DECOMPOSITION",))
    object.__setattr__(forged, "vocabulary_version", policy.vocabulary_version)

    with pytest.raises(StrategyPolicyVocabularyError):
        PolicyAuthorityStrategyPolicyResolver._permitted(forged)


def test_every_failure_descends_from_one_root():
    for error in (
        UnknownStrategyPolicyReferenceError,
        StrategyPolicyTenantScopeError,
        StrategyPolicyUnresolvedError,
        StrategyPolicyArtifactError,
        StrategyPolicyReferenceBindingError,
        StrategyPolicyVocabularyError,
    ):
        assert issubclass(error, StrategyPermissionResolverError)


def test_nothing_degraded_is_ever_returned():
    """Whatever fails, the caller gets an exception rather than a partial answer."""

    authority, policy, _, resolver = issued_world()
    coordinate = strategy_permission_coordinate(policy.metadata)
    authority.registry._issued.pop(coordinate)

    with pytest.raises(StrategyPermissionResolverError):
        resolver.resolve(request=make_request())


# --------------------------------------------------------------------------- #
# The composition helper
# --------------------------------------------------------------------------- #


def test_the_composition_helper_registers_the_family_adapter():
    from ugence_agentic_proposer_strategy_permission_policy import (
        STRATEGY_PERMISSION_ADAPTER_ID,
    )
    from ugence_agentic_proposer_strategy_permission_runtime import (
        with_strategy_permission_adapter,
    )
    from ugence_policy_authority.api import default_uvi_adapters

    registry = with_strategy_permission_adapter(default_uvi_adapters())
    assert STRATEGY_PERMISSION_ADAPTER_ID in {a.adapter_id for a in registry.adapters}

    # Idempotent: the authority refuses a registry holding one id twice.
    assert with_strategy_permission_adapter(registry) is registry
    assert len(with_strategy_permission_adapter(None).adapters) == 1


def test_the_composition_helper_supplies_no_approval_verifier_of_its_own():
    authority, policy, _, _ = issued_world()
    with pytest.raises(TypeError):
        build_strategy_policy_resolver(
            reference_map={
                (TENANT, STRATEGY_POLICY_REF): strategy_permission_coordinate(
                    policy.metadata
                )
            },
            registry=authority.registry,
            signature_verifier=authority.key_ring,
            approval_verifier=None,
        )


def test_a_request_of_the_wrong_shape_is_refused():
    _, _, _, resolver = issued_world()
    with pytest.raises(TypeError):
        resolver.resolve(request={"strategy_policy_ref": STRATEGY_POLICY_REF})
