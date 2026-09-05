"""The §5.4 end-to-end proof: issuance to conformance replay, nothing stubbed.

One flow, across three package boundaries: the family package constructs a
digest-bound constitution; the shared Policy Authority issues it with real
Ed25519 signing and external approval evidence; this distribution's resolver
turns a role reference into that exact signed artifact, fail-closed at every
seam; and the structural verifier reports conformance of presented role facts —
``True`` and ``False`` both proven. Deterministic, clock- and network-free:
every instant is a fixture's.

The composition helper is proven here too, including the property that makes it
more than a convenience: every composition path runs the family package's
`ACC-S1-Q3` registration-time collision guard, so a mis-assembled registry
fails to compose before any request is served.
"""

from __future__ import annotations

import pytest
from _authority_fixtures import approval_evidence, make_authority
from _constitution_conformance_fixtures import (
    ADAPTER,
    CONSTITUTION_REF,
    DISPOSITIONS_BOUND,
    ROLE_REF,
    T_MID,
    TENANT,
    TOOL_SCOPES_BOUND,
    issued_world,
    make_constitution_policy,
    make_facts,
)
from ugence_agent_constitution_conformance import (
    build_constitution_resolver,
    role_facts_conform,
)
from ugence_agent_constitution_conformance.composition import (
    with_agent_constitution_adapter,
)
from ugence_agent_constitution_policy import (
    AGENT_CONSTITUTION_ADAPTER_ID,
    AgentConstitutionFamilyCollisionError,
    AgentConstitutionPolicy,
    agent_constitution_coordinate,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    DenyAllApprovalVerifier,
    PolicyApprovalError,
    PolicyIssuanceError,
    default_uvi_adapters,
    framed_body_digest,
    issue_policy,
)


# --------------------------------------------------------------------------- #
# The whole flow, both directions
# --------------------------------------------------------------------------- #


def test_issue_resolve_and_verify_conforming_facts_end_to_end():
    """Genuine issuance -> fail-closed resolution -> predicate answers True."""

    authority, policy, record, resolver = issued_world()

    resolved = resolver.resolve(
        tenant_id=TENANT,
        role_contract_ref=ROLE_REF,
        as_of=T_MID,
        presented_constitution_ref=CONSTITUTION_REF,
    )
    assert resolved is policy

    # The signed body digest is recomputed independently from the published
    # projection, not read back from the adapter's own output.
    descriptor = ADAPTER.describe(resolved)
    recomputed = framed_body_digest(
        adapter_id=descriptor.adapter_id,
        policy_type=descriptor.policy_type,
        projection=descriptor.canonical_projection,
    )
    assert recomputed == record.policy_body_digest

    assert role_facts_conform(policy=resolved, facts=make_facts()) is True


def test_issue_resolve_and_verify_non_conforming_facts_end_to_end():
    """The same genuine pipeline, answering False — a report, not an error."""

    _, policy, _, resolver = issued_world()
    resolved = resolver.resolve(
        tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID
    )

    outside_every_bound = make_facts(
        tool_scopes=TOOL_SCOPES_BOUND + ("scope.unbounded",)
    )
    assert role_facts_conform(policy=resolved, facts=outside_every_bound) is False


def test_a_new_bound_is_a_new_issuance_and_the_old_facts_verdict_moves_with_it():
    """Digest-bound end to end: widening a bound changes the coordinate, so the
    same facts answer differently only against a different signed artifact."""

    _, narrow_policy, _, narrow_resolver = issued_world()
    facts = make_facts(tool_scopes=("scope.unbounded",))
    resolved_narrow = narrow_resolver.resolve(
        tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID
    )
    assert role_facts_conform(policy=resolved_narrow, facts=facts) is False

    wide_policy = make_constitution_policy(
        tool_scopes_bound=tuple(sorted(TOOL_SCOPES_BOUND + ("scope.unbounded",))),
        version="1.1.0",
    )
    assert (
        wide_policy.metadata.content_digest != narrow_policy.metadata.content_digest
    )
    _, _, _, wide_resolver = issued_world(policy=wide_policy)
    resolved_wide = wide_resolver.resolve(
        tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID
    )
    assert role_facts_conform(policy=resolved_wide, facts=facts) is True


# --------------------------------------------------------------------------- #
# Issuance gates, exercised from this side of the boundary
# --------------------------------------------------------------------------- #


def test_the_shipped_deny_by_default_verifier_refuses_issuance():
    """Approval is external, and unconfigured means no. Permissive verifiers
    exist under tests/ only, and a packaged scan asserts nothing like one ships."""

    authority = make_authority(adapters=AdapterRegistry([ADAPTER]))
    with pytest.raises((PolicyApprovalError, PolicyIssuanceError)):
        issue_policy(
            policy=make_constitution_policy(),
            record_id="rec-deny",
            approval=approval_evidence(),
            approval_verifier=DenyAllApprovalVerifier(),
            signer=authority.signer,
            registry=authority.registry,
            adapters=authority.adapters,
            issued_at=T_MID,
        )
    assert not authority.registry._issued


# --------------------------------------------------------------------------- #
# The composition helper, and the guard it always runs
# --------------------------------------------------------------------------- #


def test_the_composition_helper_registers_the_family_adapter():
    registry = with_agent_constitution_adapter(default_uvi_adapters())
    assert AGENT_CONSTITUTION_ADAPTER_ID in {a.adapter_id for a in registry.adapters}

    # Idempotent on the adapter id, guard-checked in both branches.
    assert with_agent_constitution_adapter(registry) is registry
    assert len(with_agent_constitution_adapter(None).adapters) == 1


def test_a_resolver_composed_from_a_bare_registry_still_resolves():
    """Forgetting the adapter is not a failure mode the helper permits."""

    authority, policy, _, _ = issued_world()
    resolver = build_constitution_resolver(
        reference_map={
            (TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)
        },
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        approval_verifier=authority.approval,
        adapters=None,
    )
    resolved = resolver.resolve(
        tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID
    )
    assert type(resolved) is AgentConstitutionPolicy


def test_every_composition_path_runs_the_acc_s1_q3_collision_guard():
    """A registry in which this family does not answer exactly once fails to
    compose, before any request is served."""

    class _ImpostorRecognizingAdapter:
        @property
        def adapter_id(self) -> str:
            return "impostor.agent-constitution/v9"

        def recognizes(self, artifact: object) -> bool:
            return type(artifact) is AgentConstitutionPolicy

        def describe(self, artifact: object):  # pragma: no cover - never reached
            raise NotImplementedError

        def coordinate_for(self, reference: object):
            return None

    authority, policy, _, _ = issued_world()
    poisoned = AdapterRegistry([_ImpostorRecognizingAdapter()])

    with pytest.raises(AgentConstitutionFamilyCollisionError):
        build_constitution_resolver(
            reference_map={
                (TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)
            },
            registry=authority.registry,
            signature_verifier=authority.key_ring,
            approval_verifier=authority.approval,
            adapters=poisoned,
        )

    # The already-carrying branch is guarded too, not just the appending one.
    carrying_plus_impostor = with_agent_constitution_adapter(None).with_adapter(
        _ImpostorRecognizingAdapter()
    )
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        with_agent_constitution_adapter(carrying_plus_impostor)


def test_the_composition_helper_supplies_no_approval_verifier_of_its_own():
    authority, policy, _, _ = issued_world()
    with pytest.raises(TypeError):
        build_constitution_resolver(
            reference_map={
                (TENANT, ROLE_REF): agent_constitution_coordinate(policy.metadata)
            },
            registry=authority.registry,
            signature_verifier=authority.key_ring,
            approval_verifier=None,
        )


# --------------------------------------------------------------------------- #
# The presented-facts caveat, stated as a test
# --------------------------------------------------------------------------- #


def test_replay_proves_the_presented_facts_only():
    """Two callers presenting different facts for one role get different
    answers from one constitution; nothing here arbitrates which presentation
    equals the live role. That assertion is the caller's, disclosed plainly."""

    _, policy, _, resolver = issued_world()
    resolved = resolver.resolve(
        tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID
    )

    honest = make_facts(dispositions=DISPOSITIONS_BOUND)
    inflated = make_facts(
        dispositions=DISPOSITIONS_BOUND, tool_scopes=("scope.unbounded",)
    )
    assert role_facts_conform(policy=resolved, facts=honest) is True
    assert role_facts_conform(policy=resolved, facts=inflated) is False
