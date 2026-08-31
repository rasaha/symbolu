"""Resolution semantics (§5.2): exact mapping, request-derived tenant, fail closed.

Everything here drives the genuine pipeline — real issuance, real Ed25519
signing, the real registry, real ``resolve_policy``. A resolver proven against a
stubbed authority would prove nothing about the authority it exists to call.

The organising rule is one sentence: **a constitution is returned only when the
authority answered with a resolution and the four post-checks passed.** Every
other outcome raises, which is what covers the authority's whole reason
enumeration by construction rather than by this module remembering to enumerate
it.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from _authority_fixtures import make_signer
from _constitution_conformance_fixtures import (
    ADAPTER,
    CONSTITUTION_REF,
    GOVERNED_ROLE_REFS,
    OTHER_GOVERNED_ROLE_REF,
    POLICY_ID,
    POLICY_VERSION,
    ROLE_REF,
    T_AFTER,
    T_BEFORE,
    T_MID,
    TENANT,
    issued_world,
    make_constitution_authority,
    make_constitution_policy,
    make_resolver,
)
from ugence_agent_constitution_conformance import (
    AgentConstitutionConformanceError,
    ConstitutionArtifactTypeError,
    ConstitutionFactsError,
    ConstitutionReferenceBindingError,
    ConstitutionRoleBindingError,
    ConstitutionTenantScopeError,
    ConstitutionUnresolvedError,
    ConstitutionVocabularyError,
    PolicyAuthorityConstitutionResolver,
    UnknownConstitutionReferenceError,
    build_constitution_resolver,
)

# Internal on the sibling runtime's SURFACE=B precedent, so reached through the
# module that owns it rather than through the package's curated surface.
from ugence_agent_constitution_conformance.resolution import HISTORICAL_RESOLUTION
from ugence_agent_constitution_policy import (
    LIFECYCLE_DRAFT,
    POLICY_SCOPE_GLOBAL,
    AgentConstitutionPolicy,
    agent_constitution_coordinate,
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


def resolve(resolver, **overrides):
    arguments = dict(tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID)
    arguments.update(overrides)
    return resolver.resolve(**arguments)


# --------------------------------------------------------------------------- #
# The happy path — the exact artifact, only on RESOLVED
# --------------------------------------------------------------------------- #


def test_the_resolver_returns_the_exact_resolved_artifact():
    _, policy, _, resolver = issued_world()
    resolved = resolve(resolver)

    assert resolved is policy
    assert type(resolved) is AgentConstitutionPolicy
    assert resolved.metadata.policy_id == POLICY_ID
    assert resolved.metadata.version == POLICY_VERSION
    assert resolved.agent_constitution_ref == CONSTITUTION_REF


def test_every_governed_role_reaches_the_same_constitution_through_its_own_key():
    authority, policy, _, _ = issued_world()
    coordinate = agent_constitution_coordinate(policy.metadata)
    resolver = make_resolver(
        authority,
        reference_map={
            (TENANT, ROLE_REF): coordinate,
            (TENANT, OTHER_GOVERNED_ROLE_REF): coordinate,
        },
    )
    assert resolve(resolver) is policy
    assert resolve(resolver, role_contract_ref=OTHER_GOVERNED_ROLE_REF) is policy


def test_a_presented_constitution_reference_that_matches_is_accepted():
    _, policy, _, resolver = issued_world()
    resolved = resolve(resolver, presented_constitution_ref=CONSTITUTION_REF)
    assert resolved is policy


# --------------------------------------------------------------------------- #
# The mapping — exact only, mints nothing, fails closed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "ref",
    [
        ROLE_REF + "x",
        ROLE_REF[:-1],
        ROLE_REF.upper(),
        "ugence.roles/tenant-1",
        "unrelated-reference",
    ],
    ids=["suffix", "prefix", "case", "shorter-prefix", "unrelated"],
)
def test_a_near_miss_role_reference_fails_closed(ref):
    """No fallback, no prefix match, no newest-version rule."""

    _, _, _, resolver = issued_world()
    with pytest.raises(UnknownConstitutionReferenceError):
        resolve(resolver, role_contract_ref=ref)


def test_one_tenant_s_role_never_reaches_another_tenant_s_coordinate():
    _, _, _, resolver = issued_world()
    with pytest.raises(UnknownConstitutionReferenceError):
        resolve(resolver, tenant_id="tenant-elsewhere")


def test_the_mapping_is_defensively_copied_at_construction():
    """Mutating the mapping handed in cannot change what the resolver reaches."""

    authority, policy, _, _ = issued_world()
    supplied = {(TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)}
    resolver = make_resolver(authority, reference_map=supplied)

    supplied[("tenant-attacker", "any-reference")] = agent_constitution_coordinate(
        policy.metadata
    )
    supplied.pop((TENANT, ROLE_REF))

    assert resolve(resolver) is policy
    with pytest.raises(UnknownConstitutionReferenceError):
        resolve(resolver, tenant_id="tenant-attacker", role_contract_ref="any-reference")


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
    "bad_key",
    ["not-a-tuple", (1, "ref"), ("t", "ref", "extra")],
    ids=["string-key", "non-string-tenant", "three-tuple"],
)
def test_a_malformed_mapping_key_is_refused_at_construction(bad_key):
    authority, policy, _, _ = issued_world()
    bad_map = {bad_key: agent_constitution_coordinate(policy.metadata)}
    with pytest.raises(TypeError):
        make_resolver(authority, reference_map=bad_map)


def test_a_partial_identity_is_not_a_coordinate():
    """A mapping value must be a complete coordinate, digest included."""

    authority, _, _, _ = issued_world()
    with pytest.raises(TypeError):
        make_resolver(
            authority, reference_map={(TENANT, ROLE_REF): (POLICY_ID, POLICY_VERSION)}
        )


def test_one_role_maps_to_at_most_one_coordinate_by_construction():
    """`ACC-S1-Q4`'s enforceable half: the key is the role, so a deployment
    cannot represent two active constitutions for one role at one instant."""

    _, _, _, resolver = issued_world()
    keys = list(resolver.reference_map)
    assert len(keys) == len(set(keys))
    assert all(len(key) == 2 for key in keys)


# --------------------------------------------------------------------------- #
# Tenant handling — request-derived, and non-vacuous
# --------------------------------------------------------------------------- #


def test_the_expected_tenant_is_derived_from_the_request_not_the_coordinate():
    """The authority's own comparison must be able to fail.

    Passing ``coordinate.tenant_id`` would make it vacuous for every coordinate,
    so the value handed over is the request's. A coordinate reachable under a
    key naming a different tenant is refused by this resolver's own pre-check
    before the authority is ever called.
    """

    authority, policy, _, _ = issued_world()
    coordinate = agent_constitution_coordinate(policy.metadata)
    assert coordinate.tenant_id == TENANT

    resolver = make_resolver(
        authority, reference_map={("tenant-other", ROLE_REF): coordinate}
    )
    with pytest.raises(ConstitutionTenantScopeError):
        resolve(resolver, tenant_id="tenant-other")


def test_a_global_scope_coordinate_resolves_under_the_canonical_empty_component():
    policy = make_constitution_policy(scope=POLICY_SCOPE_GLOBAL, tenant_id="")
    authority = make_constitution_authority()
    authority.issue(policy, issued_at=T_MID)
    resolver = make_resolver(authority, policy=policy, tenant="")

    assert resolve(resolver, tenant_id="") is policy
    assert agent_constitution_coordinate(policy.metadata).tenant_id == GLOBAL_TENANT


def test_a_global_scope_coordinate_carrying_a_tenant_is_refused_by_the_pre_check():
    """Constructed directly, because the family itself refuses to build one."""

    authority, policy, _, _ = issued_world()
    malformed = PolicyCoordinate(
        policy_family=agent_constitution_coordinate(policy.metadata).policy_family,
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        content_digest=policy.metadata.content_digest,
        scope=POLICY_SCOPE_GLOBAL,
        tenant_id=TENANT,
    )
    resolver = make_resolver(authority, reference_map={(TENANT, ROLE_REF): malformed})
    with pytest.raises(ConstitutionTenantScopeError):
        resolve(resolver)


def test_an_unadmitted_scope_is_refused():
    authority, policy, _, _ = issued_world()
    malformed = dataclasses.replace(
        agent_constitution_coordinate(policy.metadata), scope="REGIONAL"
    )
    resolver = make_resolver(authority, reference_map={(TENANT, ROLE_REF): malformed})
    with pytest.raises(ConstitutionTenantScopeError):
        resolve(resolver)


# --------------------------------------------------------------------------- #
# as_of, and the absence of a clock
# --------------------------------------------------------------------------- #


def test_the_caller_s_as_of_is_passed_through_verbatim():
    _, policy, _, resolver = issued_world()
    assert resolve(resolver, as_of=T_MID) is policy

    for outside in (T_BEFORE, T_AFTER):
        with pytest.raises(ConstitutionUnresolvedError):
            resolve(resolver, as_of=outside)


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
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver, as_of=as_of)
    assert excinfo.value.reason is expected


def test_the_reason_token_never_appears_in_the_message_text():
    """§5.3: the reason reaches a caller through the attribute and nothing else."""

    _, _, _, resolver = issued_world()
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver, as_of=T_AFTER)
    assert excinfo.value.reason is PolicyResolutionReason.EXPIRED
    assert excinfo.value.reason.name not in str(excinfo.value).upper()


def test_a_naive_as_of_is_refused():
    from datetime import datetime

    _, _, _, resolver = issued_world()
    with pytest.raises(ConstitutionFactsError):
        resolve(resolver, as_of=datetime(2026, 6, 1))


# --------------------------------------------------------------------------- #
# Fail closed on everything that is not a resolution
# --------------------------------------------------------------------------- #


def test_a_missing_record_fails_closed():
    policy = make_constitution_policy()
    authority = make_constitution_authority()  # nothing issued
    resolver = make_resolver(authority, policy=policy)
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason is PolicyResolutionReason.NOT_FOUND


def test_a_lifecycle_that_never_issued_fails_closed():
    policy = make_constitution_policy(lifecycle_state=LIFECYCLE_DRAFT)
    authority = make_constitution_authority()
    resolver = make_resolver(authority, policy=policy)
    with pytest.raises(ConstitutionUnresolvedError):
        resolve(resolver)


def test_a_mutated_artifact_under_the_same_coordinate_fails_closed():
    """A widened bound under the signed coordinate is exactly the attack shape."""

    authority, policy, _, resolver = issued_world()
    coordinate = agent_constitution_coordinate(policy.metadata)
    tampered = AgentConstitutionPolicy(
        metadata=policy.metadata,
        agent_constitution_ref=policy.agent_constitution_ref,
        governed_role_refs=policy.governed_role_refs,
        permitted_candidate_dispositions_bound=policy.permitted_candidate_dispositions_bound,
        permitted_review_actions_bound=policy.permitted_review_actions_bound,
        permitted_tool_scopes_bound=("scope.everything",),
    )
    assert ADAPTER.describe(tampered).body_digest() != policy.metadata.content_digest
    stored = authority.registry._issued[coordinate]
    authority.registry._issued[coordinate] = dataclasses.replace(stored, policy=tampered)

    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason in {
        PolicyResolutionReason.CONTENT_DIGEST_MISMATCH,
        PolicyResolutionReason.BODY_DIGEST_MISMATCH,
    }


def test_a_forged_issuance_signature_fails_closed():
    authority, policy, _, resolver = issued_world()
    coordinate = agent_constitution_coordinate(policy.metadata)
    stored = authority.registry._issued[coordinate]
    authority.registry._issued[coordinate] = dataclasses.replace(
        stored, signature=b"\x00" * 64
    )
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason is PolicyResolutionReason.SIGNATURE_INVALID


def test_an_unknown_signing_key_fails_closed():
    authority, policy, _, _ = issued_world()
    stranger = make_signer(authority_id="attacker.authority", key_id="stranger", seed=9)
    resolver = build_constitution_resolver(
        reference_map={
            (TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)
        },
        registry=authority.registry,
        signature_verifier=type(authority.key_ring)(
            [stranger.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))]
        ),
        approval_verifier=authority.approval,
        adapters=authority.adapters,
    )
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason is PolicyResolutionReason.KEY_UNKNOWN


def test_a_revoked_version_fails_closed_and_no_historical_answer_is_accepted():
    """§5.2 — historical resolution stays at deny-always."""

    authority, policy, _, resolver = issued_world()
    revoke_policy(
        reference=agent_constitution_coordinate(policy.metadata),
        revocation_id="rv-1",
        reason_code=PolicyRevocationReasonCode.ISSUED_IN_ERROR,
        registry=authority.registry,
        adapters=authority.adapters,
        signer=authority.revocation_signer,
        signature_verifier=authority.key_ring,
        revoked_at=T_MID + timedelta(days=1),
    )

    assert HISTORICAL_RESOLUTION is HistoricalResolutionRule.DENY_ALWAYS
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason is PolicyResolutionReason.REVOKED

    # An as_of strictly before the revocation instant is refused too: a
    # historical answer describes the past and is never accepted at this
    # boundary.
    with pytest.raises(ConstitutionUnresolvedError):
        resolve(resolver, as_of=T_MID - timedelta(seconds=1))


def test_an_approval_withdrawn_after_issuance_invalidates_resolution():
    """The row that exists only because a verifier is always supplied."""

    from ugence_policy_authority.api import ApprovalVerificationStatus

    authority, policy, _, resolver = issued_world()
    assert resolve(resolver) is policy

    authority.approval.status = ApprovalVerificationStatus.REVOKED
    with pytest.raises(ConstitutionUnresolvedError) as excinfo:
        resolve(resolver)
    assert excinfo.value.reason is PolicyResolutionReason.APPROVAL_PROOF_INVALID


def test_an_approval_verifier_is_required_at_construction():
    """Without one the row above is unreachable, so it is not optional here."""

    authority, policy, _, _ = issued_world()
    reference_map = {
        (TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)
    }
    for verifier in (None, object()):
        with pytest.raises(TypeError):
            PolicyAuthorityConstitutionResolver(
                reference_map=reference_map,
                registry=authority.registry,
                signature_verifier=authority.key_ring,
                adapters=authority.adapters,
                approval_verifier=verifier,
            )


# --------------------------------------------------------------------------- #
# The four post-checks, each with its own error class
# --------------------------------------------------------------------------- #


def test_post_check_1_a_foreign_artifact_under_the_coordinate_is_refused_by_type():
    """Exact runtime type, not ``isinstance``."""

    authority, policy, _, resolver = issued_world()

    class Extended(AgentConstitutionPolicy):
        pass

    coordinate = agent_constitution_coordinate(policy.metadata)
    stored = authority.registry._issued[coordinate]
    sneaky = Extended(
        metadata=policy.metadata,
        agent_constitution_ref=policy.agent_constitution_ref,
        governed_role_refs=policy.governed_role_refs,
        permitted_candidate_dispositions_bound=policy.permitted_candidate_dispositions_bound,
        permitted_review_actions_bound=policy.permitted_review_actions_bound,
        permitted_tool_scopes_bound=policy.permitted_tool_scopes_bound,
    )
    authority.registry._issued[coordinate] = dataclasses.replace(stored, policy=sneaky)

    # The authority refuses first, because no adapter recognizes the subclass;
    # the resolver's own type post-check stands behind that rather than in
    # front of it.
    with pytest.raises(AgentConstitutionConformanceError) as excinfo:
        resolve(resolver)
    assert isinstance(
        excinfo.value, (ConstitutionUnresolvedError, ConstitutionArtifactTypeError)
    )


def test_post_check_2_a_role_outside_the_signed_role_list_raises():
    """§5.4's named row: the signed-side role binding (`ACC-S1-Q4`)."""

    authority, policy, _, _ = issued_world()
    ungoverned = "ugence.roles/tenant-1/ungoverned/v1"
    assert ungoverned not in GOVERNED_ROLE_REFS
    resolver = make_resolver(
        authority,
        reference_map={
            (TENANT, ungoverned): agent_constitution_coordinate(policy.metadata)
        },
    )
    with pytest.raises(ConstitutionRoleBindingError):
        resolve(resolver, role_contract_ref=ungoverned)


def test_post_check_3_a_forged_bound_token_raises_the_vocabulary_error():
    """Hand-forged, because the family refuses to construct such an artifact."""

    _, policy, _, _ = issued_world()
    forged = object.__new__(AgentConstitutionPolicy)
    object.__setattr__(forged, "metadata", policy.metadata)
    object.__setattr__(forged, "agent_constitution_ref", policy.agent_constitution_ref)
    object.__setattr__(forged, "governed_role_refs", policy.governed_role_refs)
    object.__setattr__(
        forged, "permitted_candidate_dispositions_bound", ("SOMETHING_NO_ENUM_CONTAINS",)
    )
    object.__setattr__(
        forged, "permitted_review_actions_bound", policy.permitted_review_actions_bound
    )
    object.__setattr__(
        forged, "permitted_tool_scopes_bound", policy.permitted_tool_scopes_bound
    )
    object.__setattr__(
        forged,
        "constitution_vocabulary_version",
        policy.constitution_vocabulary_version,
    )

    with pytest.raises(ConstitutionVocabularyError):
        PolicyAuthorityConstitutionResolver._check_bound_vocabulary(forged)


def test_post_check_4_a_mismatched_presented_reference_raises():
    """A caller-supplied value must match a value the authority signed."""

    _, _, _, resolver = issued_world()
    with pytest.raises(ConstitutionReferenceBindingError):
        resolve(
            resolver,
            presented_constitution_ref="ugence.agent-constitution/tenant-1/other/v1",
        )


def test_post_check_4_is_skipped_only_when_no_reference_is_presented():
    """Optional until the amendment round lands; empty means not presented."""

    _, policy, _, resolver = issued_world()
    assert resolve(resolver, presented_constitution_ref="") is policy


# --------------------------------------------------------------------------- #
# Taxonomy discipline
# --------------------------------------------------------------------------- #


def test_every_failure_descends_from_one_root():
    for error in (
        ConstitutionFactsError,
        UnknownConstitutionReferenceError,
        ConstitutionTenantScopeError,
        ConstitutionUnresolvedError,
        ConstitutionArtifactTypeError,
        ConstitutionRoleBindingError,
        ConstitutionVocabularyError,
        ConstitutionReferenceBindingError,
    ):
        assert issubclass(error, AgentConstitutionConformanceError)


def test_the_reason_attribute_exists_on_the_root_and_defaults_to_none():
    assert AgentConstitutionConformanceError.reason is None
    assert ConstitutionRoleBindingError("x").reason is None


def test_nothing_degraded_is_ever_returned():
    """Whatever fails, the caller gets an exception rather than a partial answer."""

    authority, policy, _, resolver = issued_world()
    coordinate = agent_constitution_coordinate(policy.metadata)
    authority.registry._issued.pop(coordinate)

    with pytest.raises(AgentConstitutionConformanceError):
        resolve(resolver)


def test_a_request_of_the_wrong_shape_is_refused():
    _, _, _, resolver = issued_world()
    with pytest.raises(ConstitutionFactsError):
        resolve(resolver, role_contract_ref=b"role")
    with pytest.raises(ConstitutionFactsError):
        resolve(resolver, tenant_id=42)
    with pytest.raises(ConstitutionFactsError):
        resolve(resolver, presented_constitution_ref=42)
