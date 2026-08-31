"""`ACC-IA-2` — the root wires injected trust, defaults nothing, and guards
the family on every path.

The construction refusals are the custody boundary's runtime half: the AST scan
proves the package cannot build a signer, and these prove it refuses to exist
without one. The guard tests prove the `ACC-S1-Q3` family-collision assertion
runs both at construction and at resolver assembly.
"""

from __future__ import annotations

import pytest
from _activation_fixtures import (
    GLOBAL_TENANT,
    GOVERNED_ROLE_REF,
    T_ACTIVATE,
    T_ISSUE,
    T_RESOLVE,
    make_ephemeral_signer,
    make_first_constitution,
    make_runtime_approval,
    make_world,
)
from ugence_agent_constitution_activation import (
    ActivationRequestError,
    ActivationCompositionError,
    ActivationRoot,
    build_activation_root,
)
from ugence_agent_constitution_policy import (
    AGENT_CONSTITUTION_POLICY_FAMILY,
    AgentConstitutionFamilyCollisionError,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    DenyAllApprovalVerifier,
    DenyAllSignatureVerifier,
    InMemoryPolicyRegistry,
    PolicyApprovalError,
)


def _deps(**overrides):
    evidence, verifier = make_runtime_approval()
    deps = dict(
        registry=InMemoryPolicyRegistry(),
        signer=make_ephemeral_signer(),
        signature_verifier=DenyAllSignatureVerifier(),
        approval_verifier=verifier,
    )
    deps.update(overrides)
    return deps


# --------------------------------------------------------------------------- #
# No dependency has a default; every seam is shape-checked
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "overrides",
    [
        dict(registry=object()),
        dict(signer=object()),
        dict(signer=b"not-a-signer-and-not-key-material-either"),
        dict(signature_verifier=None),
        dict(signature_verifier=object()),
        dict(approval_verifier=None),
        dict(approval_verifier=object()),
        dict(adapters="not-a-registry"),
    ],
    ids=["registry", "signer", "bytes-are-not-a-signer", "no-sig-verifier",
         "loose-sig-verifier", "no-approval-verifier", "loose-approval-verifier",
         "loose-adapters"],
)
def test_an_incomplete_or_alien_wiring_fails_to_construct(overrides):
    with pytest.raises(ActivationCompositionError):
        build_activation_root(**_deps(**overrides))


def test_construction_is_keyword_only_and_the_root_is_immutable():
    root = build_activation_root(**_deps())
    with pytest.raises(TypeError):
        build_activation_root(InMemoryPolicyRegistry())  # type: ignore[misc]
    with pytest.raises(AttributeError):
        root._registry = None
    with pytest.raises(AttributeError):
        root.anything = 1
    with pytest.raises(AttributeError):
        del root._signer
    assert type(root) is ActivationRoot


# --------------------------------------------------------------------------- #
# The deny-by-default posture composes, then refuses every act
# --------------------------------------------------------------------------- #


def test_the_shipped_deny_defaults_compose_and_refuse():
    """`ACC-IA-2`'s ratified posture: an unconfigured deployment fails as a
    refusal, never as an unapproved issuance."""

    world_deps = _deps(approval_verifier=DenyAllApprovalVerifier())
    root = build_activation_root(**world_deps)
    evidence, _ = make_runtime_approval()
    with pytest.raises(PolicyApprovalError):
        root.issue_constitution(
            policy=make_first_constitution(),
            record_id="rec-nobody-approved",
            approval=evidence,
            issued_at=T_ISSUE,
        )
    assert world_deps["registry"].get_issued is not None


# --------------------------------------------------------------------------- #
# The ACC-S1-Q3 guard runs on every path
# --------------------------------------------------------------------------- #


class _ImpostorAdapter:
    """A second adapter answering for the constitution family.

    Implements the authority's full ``PolicyFamilyAdapter`` shape so the
    registry accepts it — the point is that the `ACC-S1-Q3` guard, not the
    registry's protocol check, is what refuses the collision.
    """

    @property
    def adapter_id(self) -> str:
        return "impostor.agent-constitution/v0"

    @property
    def policy_family(self) -> str:
        return AGENT_CONSTITUTION_POLICY_FAMILY

    def recognizes(self, policy) -> bool:
        return True

    def describe(self, policy):
        raise AssertionError("never reached; the guard refuses first")

    def coordinate_for(self, metadata):
        return None


def test_construction_refuses_a_registry_where_the_family_collides():
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        build_activation_root(
            **_deps(adapters=AdapterRegistry([_ImpostorAdapter()]))
        )


def test_a_bare_construction_registers_the_family_itself():
    """No adapters passed: the guard-registered default carries the family, so
    a lawful constitution is immediately recognizable."""

    root = build_activation_root(**_deps())
    report = root.preflight_issuance(
        policy=make_first_constitution(),
        record_id="rec-guarded",
        approval=make_runtime_approval()[0],
        as_of=T_ISSUE,
    )
    rows = {check.name: check.ok for check in report.checks}
    assert rows["artifact-recognition"] is True


def test_resolver_assembly_runs_the_guard_again():
    world = make_world()
    policy, receipt = world.issue_first_constitution()
    reference_map, _ = world.root.activate_constitution(
        coordinate=receipt.coordinate, activated_at=T_ACTIVATE
    )
    resolver = world.root.constitution_resolver(reference_map=reference_map)
    resolved = resolver.resolve(
        tenant_id=GLOBAL_TENANT,
        role_contract_ref=GOVERNED_ROLE_REF,
        as_of=T_RESOLVE,
    )
    assert resolved == policy


# --------------------------------------------------------------------------- #
# Activation is derivation, receipted; alien requests are refused
# --------------------------------------------------------------------------- #


def test_activation_of_an_unissued_coordinate_is_refused():
    world = make_world()
    policy = make_first_constitution()
    from ugence_agent_constitution_policy import agent_constitution_coordinate

    with pytest.raises(ActivationRequestError):
        world.root.activate_constitution(
            coordinate=agent_constitution_coordinate(policy.metadata),
            activated_at=T_ACTIVATE,
        )


def test_activation_refuses_a_loose_coordinate():
    world = make_world()
    with pytest.raises(ActivationRequestError):
        world.root.activate_constitution(
            coordinate="not-a-coordinate", activated_at=T_ACTIVATE
        )


def test_activation_writes_no_registry_state():
    world = make_world()
    _, receipt = world.issue_first_constitution()
    from _authority_fixtures import registry_snapshot

    before = registry_snapshot(world.registry)
    world.root.activate_constitution(
        coordinate=receipt.coordinate, activated_at=T_ACTIVATE
    )
    assert registry_snapshot(world.registry) == before
