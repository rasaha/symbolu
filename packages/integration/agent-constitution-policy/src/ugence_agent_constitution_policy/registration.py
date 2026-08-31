"""The `ACC-S1-Q3` registration-time family-collision guard.

`[V]` The shared authority's existing collision surface is exactly one check:
the adapter registry refuses a duplicate ``adapter_id`` at registration. Nothing
in the core refuses two adapters, under distinct ids, claiming the same
``policy_family`` value — recognition is by artifact type, and two families
colliding in the coordinate identity space would surface only
coordinate-by-coordinate, as conflicts, after issuance.

`ACC-S1-Q3` ruled that this family ships the stronger guard **at its own
boundary, with no authority change**: the helper that registers this family
asserts, over the assembled registry, that exactly one adapter answers for the
Agent Constitution family value and that the value differs from every family
value any other registered adapter advertises. A core-level uniqueness guard for
all families is a raised Policy Authority milestone, not built here.

How "answers for" is measured
-----------------------------
The registry routes through exactly two seams — ``recognizes`` on artifacts and
``coordinate_for`` on references — and a family value reaches the identity space
only through the coordinates an adapter emits. The guard therefore probes both
seams with a deterministic representative of this family (never issued, never
signed) and requires exactly one adapter to answer on each, that adapter to be
this family's own by id, and the emitted coordinate to carry exactly the
ratified family value. Adapters that *advertise* a ``policy_family`` string —
this family's adapter does — are additionally compared by value, so a foreign
adapter claiming this family's value is refused even if it recognizes nothing.

The guard is deterministic and side-effect free: it issues nothing, signs
nothing and registers nothing beyond the one adapter the register helper
appends.
"""

from __future__ import annotations

from ugence_agentic_proposer import CandidateDisposition, ReviewAction
from ugence_policy_authority.api import AdapterRegistry

from .adapter import AgentConstitutionPolicyFamilyAdapter
from .errors import AgentConstitutionFamilyCollisionError, AgentConstitutionFieldError
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    AGENT_CONSTITUTION_ADAPTER_ID,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    POLICY_SCOPE_GLOBAL,
)
from .policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyMetadata,
)

__all__ = [
    "register_agent_constitution_policy_family",
    "assert_agent_constitution_family_registration",
]


def _probe_policy() -> AgentConstitutionPolicy:
    """A deterministic, never-issued representative of this family.

    Exists only to ask every registered adapter the two routing questions. Its
    digest is the declared placeholder — the probe is never described, issued or
    signed, so no fixed point and no clock is involved. The closed-vocabulary
    bounds are derived from the imported enums, never restated.
    """

    metadata = AgentConstitutionPolicyMetadata(
        policy_id="agent-constitution-registration-probe",
        version="0.0.0",
        content_digest=PLACEHOLDER_CONTENT_DIGEST,
        scope=POLICY_SCOPE_GLOBAL,
        lifecycle_state=ACTIVE_LIFECYCLE_STATE,
    )
    return AgentConstitutionPolicy(
        metadata=metadata,
        agent_constitution_ref="ugence.agent-constitution/registration-probe/v0",
        governed_role_refs=("ugence.agent-constitution/registration-probe/role/v0",),
        permitted_candidate_dispositions_bound=tuple(
            sorted(member.value for member in CandidateDisposition)
        ),
        permitted_review_actions_bound=tuple(
            sorted(member.value for member in ReviewAction)
        ),
        permitted_tool_scopes_bound=(),
    )


def assert_agent_constitution_family_registration(registry: AdapterRegistry) -> None:
    """Assert that exactly one adapter answers for this family across ``registry``.

    Raises :class:`AgentConstitutionFamilyCollisionError` if no adapter answers,
    if more than one does, if the answering adapter is not this family's own, if
    the coordinate it emits carries any other family value, or if any other
    registered adapter advertises this family's ratified value.
    """

    if not isinstance(registry, AdapterRegistry):
        raise AgentConstitutionFieldError(
            "assert_agent_constitution_family_registration requires an AdapterRegistry"
        )

    probe = _probe_policy()

    recognizing = [
        adapter for adapter in registry.adapters if bool(adapter.recognizes(probe))
    ]
    mapping = []
    for adapter in registry.adapters:
        coordinate = adapter.coordinate_for(probe.metadata)
        if coordinate is not None:
            mapping.append((adapter, coordinate))

    if not recognizing and not mapping:
        raise AgentConstitutionFamilyCollisionError(
            "no registered adapter answers for the agent-constitution family; "
            "register AgentConstitutionPolicyFamilyAdapter before asserting"
        )
    if len(recognizing) != 1:
        raise AgentConstitutionFamilyCollisionError(
            f"exactly one registered adapter must recognize this family's artifact; "
            f"{len(recognizing)} do: "
            f"{sorted(adapter.adapter_id for adapter in recognizing)}"
        )
    if len(mapping) != 1:
        raise AgentConstitutionFamilyCollisionError(
            f"exactly one registered adapter must map this family's reference onto a "
            f"coordinate; {len(mapping)} do: "
            f"{sorted(adapter.adapter_id for adapter, _ in mapping)}"
        )

    answering = recognizing[0]
    mapper, coordinate = mapping[0]
    if mapper is not answering:
        raise AgentConstitutionFamilyCollisionError(
            f"two different adapters answer for this family: "
            f"{answering.adapter_id!r} recognizes the artifact and "
            f"{mapper.adapter_id!r} maps the reference"
        )
    if answering.adapter_id != AGENT_CONSTITUTION_ADAPTER_ID:
        raise AgentConstitutionFamilyCollisionError(
            f"the adapter answering for this family is {answering.adapter_id!r}, not "
            f"{AGENT_CONSTITUTION_ADAPTER_ID!r}"
        )
    if coordinate.policy_family != AGENT_CONSTITUTION_POLICY_FAMILY:
        raise AgentConstitutionFamilyCollisionError(
            f"the emitted coordinate carries policy family "
            f"{coordinate.policy_family!r}, not "
            f"{AGENT_CONSTITUTION_POLICY_FAMILY!r}"
        )
    if getattr(answering, "policy_family", None) != AGENT_CONSTITUTION_POLICY_FAMILY:
        raise AgentConstitutionFamilyCollisionError(
            "the answering adapter does not advertise this family's ratified value"
        )

    for adapter in registry.adapters:
        if adapter is answering:
            continue
        advertised = getattr(adapter, "policy_family", None)
        if isinstance(advertised, str) and advertised == AGENT_CONSTITUTION_POLICY_FAMILY:
            raise AgentConstitutionFamilyCollisionError(
                f"adapter {adapter.adapter_id!r} advertises this family's value "
                f"{AGENT_CONSTITUTION_POLICY_FAMILY!r} under a different adapter id"
            )


def register_agent_constitution_policy_family(
    registry: AdapterRegistry,
) -> AdapterRegistry:
    """Append this family's adapter to ``registry`` and run the collision guard.

    Returns a new registry — the authority's registries are immutable — whose
    assembled adapter set has been asserted to answer for the Agent Constitution
    family exactly once. The core's own duplicate-``adapter_id`` refusal still
    applies first, unchanged.
    """

    if not isinstance(registry, AdapterRegistry):
        raise AgentConstitutionFieldError(
            "register_agent_constitution_policy_family requires an AdapterRegistry"
        )
    assembled = registry.with_adapter(AgentConstitutionPolicyFamilyAdapter())
    assert_agent_constitution_family_registration(assembled)
    return assembled
