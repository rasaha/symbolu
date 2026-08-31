"""The `ACC-S1-Q3` registration-time family-collision guard, proven.

`[V]` The authority's existing collision surface is the duplicate-``adapter_id``
refusal alone: two adapters under **distinct** ids claiming the same
``policy_family`` value pass registration and would collide only
coordinate-by-coordinate, after issuance. The ruled guard closes exactly that
gap at this family's own boundary, with no authority change, and this suite
proves it in both directions: the assembled registries a composition root should
build pass, and each collision shape the ruling names is refused.

The pinned-value collision test at the bottom compares the ratified family value
against the repository's real registered family constants — imported, not
copied — so a later family addition that collides is caught here rather than in
production wiring.
"""

from __future__ import annotations

import pytest
from _agent_constitution_fixtures import ADAPTER, TENANT, T_MID, make_constitution_policy
from _authority_fixtures import make_authority
from ugence_agent_constitution_policy import (
    AGENT_CONSTITUTION_ADAPTER_ID,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    AgentConstitutionFamilyCollisionError,
    AgentConstitutionFieldError,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyMetadata,
    agent_constitution_coordinate,
    assert_agent_constitution_family_registration,
    register_agent_constitution_policy_family,
)
from ugence_policy_authority.api import (
    AdapterRegistry,
    PolicyAuthorityRequestError,
    PolicyResolutionStatus,
    default_uvi_adapters,
)


class _ImpostorRecognizingAdapter:
    """A second adapter, under a distinct id, that claims this family's artifact.

    Exactly the shape the core's duplicate-id refusal cannot catch: its
    ``adapter_id`` is unique, so ``AdapterRegistry`` admits it, and only the
    ruled guard notices that two adapters now answer for one family.
    """

    @property
    def adapter_id(self) -> str:
        return "impostor.agent-constitution/v9"

    def recognizes(self, artifact: object) -> bool:
        return type(artifact) is AgentConstitutionPolicy

    def describe(self, artifact: object):  # pragma: no cover - never reached
        raise NotImplementedError

    def coordinate_for(self, reference: object):
        if isinstance(reference, AgentConstitutionPolicyMetadata):
            return agent_constitution_coordinate(reference)
        return None


class _ImpostorAdvertisingAdapter:
    """An adapter that advertises this family's value while claiming no artifact.

    It would never route a request, but its advertised family value is a
    declaration of intent to occupy this family's coordinate space; the guard
    refuses the value collision itself.
    """

    @property
    def adapter_id(self) -> str:
        return "impostor.agent-constitution/quiet/v1"

    @property
    def policy_family(self) -> str:
        return AGENT_CONSTITUTION_POLICY_FAMILY

    def recognizes(self, artifact: object) -> bool:
        return False

    def describe(self, artifact: object):  # pragma: no cover - never reached
        raise NotImplementedError

    def coordinate_for(self, reference: object):
        return None


# --------------------------------------------------------------------------- #
# The registration helper — the path a composition root takes
# --------------------------------------------------------------------------- #


def test_register_appends_the_adapter_and_the_result_issues_and_resolves():
    assembled = register_agent_constitution_policy_family(default_uvi_adapters())

    assert isinstance(assembled, AdapterRegistry)
    assert AGENT_CONSTITUTION_ADAPTER_ID in {a.adapter_id for a in assembled.adapters}

    authority = make_authority(adapters=assembled)
    policy = make_constitution_policy()
    authority.issue(policy)
    resolution = authority.resolve(policy.metadata, as_of=T_MID, tenant=TENANT)
    assert resolution.status is PolicyResolutionStatus.RESOLVED


def test_register_works_on_an_empty_registry_too():
    assembled = register_agent_constitution_policy_family(AdapterRegistry())
    assert len(assembled.adapters) == 1


def test_register_requires_a_real_registry():
    with pytest.raises(AgentConstitutionFieldError):
        register_agent_constitution_policy_family([ADAPTER])


def test_registering_twice_is_refused_by_the_core_s_own_duplicate_id_check():
    """The guard adds to the core's refusal; it does not replace it."""

    once = register_agent_constitution_policy_family(AdapterRegistry())
    with pytest.raises(PolicyAuthorityRequestError):
        register_agent_constitution_policy_family(once)


# --------------------------------------------------------------------------- #
# The guard itself, over assembled registries
# --------------------------------------------------------------------------- #


def test_the_guard_passes_when_this_family_answers_exactly_once():
    assert_agent_constitution_family_registration(AdapterRegistry([ADAPTER]))


def test_the_guard_passes_alongside_every_other_registered_family():
    """The realistic composition: UVI, strategy permission, and this family."""

    from ugence_agentic_proposer_strategy_permission_policy import (
        StrategyPermissionPolicyFamilyAdapter,
    )

    assembled = AdapterRegistry(
        [
            StrategyPermissionPolicyFamilyAdapter(),
            *default_uvi_adapters().adapters,
            ADAPTER,
        ]
    )
    assert_agent_constitution_family_registration(assembled)


def test_the_guard_refuses_a_registry_with_no_constitution_adapter():
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        assert_agent_constitution_family_registration(default_uvi_adapters())


def test_the_guard_refuses_two_adapters_answering_for_one_family():
    """The exact gap `ACC-S1-Q3` names: distinct ids, one family value."""

    colliding = AdapterRegistry([ADAPTER, _ImpostorRecognizingAdapter()])
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        assert_agent_constitution_family_registration(colliding)


def test_the_guard_refuses_an_impostor_even_without_the_genuine_adapter():
    """One answering adapter is not enough: it must be this family's own."""

    alone = AdapterRegistry([_ImpostorRecognizingAdapter()])
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        assert_agent_constitution_family_registration(alone)


def test_the_guard_refuses_an_adapter_advertising_this_family_s_value():
    advertising = AdapterRegistry([ADAPTER, _ImpostorAdvertisingAdapter()])
    with pytest.raises(AgentConstitutionFamilyCollisionError):
        assert_agent_constitution_family_registration(advertising)


def test_the_guard_requires_a_real_registry():
    with pytest.raises(AgentConstitutionFieldError):
        assert_agent_constitution_family_registration([ADAPTER])


def test_the_guard_is_side_effect_free():
    """Asserting registers nothing, issues nothing and mutates nothing."""

    registry = AdapterRegistry([ADAPTER])
    before = tuple(registry.adapters)
    assert_agent_constitution_family_registration(registry)
    assert tuple(registry.adapters) == before


# --------------------------------------------------------------------------- #
# The pinned-value collision test — the §3 value against the repository
# --------------------------------------------------------------------------- #


def test_the_ratified_family_value_collides_with_no_registered_family():
    """Compared against the real registered constants, imported never copied."""

    from ugence_agentic_proposer_strategy_permission_policy import (
        STRATEGY_PERMISSION_POLICY_FAMILY,
    )
    from ugence_cloud_scaling_capacity_bounds_policy import (
        CAPACITY_BOUNDS_POLICY_FAMILY,
    )
    from ugence_uvi_policy_contracts.api import PolicyFamily as UviPolicyFamily

    known = {STRATEGY_PERMISSION_POLICY_FAMILY, CAPACITY_BOUNDS_POLICY_FAMILY}
    known |= {member.value for member in UviPolicyFamily}

    assert AGENT_CONSTITUTION_POLICY_FAMILY == "agent_governance.agent_constitution"
    assert len(known) == 7, sorted(known)
    assert AGENT_CONSTITUTION_POLICY_FAMILY not in known


def test_the_ratified_adapter_id_collides_with_no_registered_adapter_id():
    from ugence_agentic_proposer_strategy_permission_policy import (
        StrategyPermissionPolicyFamilyAdapter,
    )
    from ugence_cloud_scaling_capacity_bounds_policy import (
        CapacityBoundsPolicyFamilyAdapter,
    )

    registered = {a.adapter_id for a in default_uvi_adapters().adapters}
    registered.add(StrategyPermissionPolicyFamilyAdapter().adapter_id)
    registered.add(CapacityBoundsPolicyFamilyAdapter().adapter_id)

    assert AGENT_CONSTITUTION_ADAPTER_ID == "ugence.agent-constitution/v1"
    assert AGENT_CONSTITUTION_ADAPTER_ID not in registered
