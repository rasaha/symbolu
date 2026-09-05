"""Deterministic builders for the agent-constitution conformance suite.

Named ``_constitution_conformance_fixtures`` rather than ``_fixtures`` so a
combined multi-package pytest run cannot shadow another package's fixtures.

Both sides of the integration are genuine: the authority is the real one — real
``issue_policy``, real Ed25519 signing, the real registry, real
``resolve_policy`` — and the constitution is built through the family package's
own constructors and adapter. Nothing is stubbed except the two boundaries the
authority itself defines as injected, using its own test fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone

from _authority_fixtures import make_authority
from ugence_agent_constitution_conformance import (
    GovernedRoleFacts,
    build_constitution_resolver,
)
from ugence_agent_constitution_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_TENANT,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyFamilyAdapter,
    AgentConstitutionPolicyMetadata,
    agent_constitution_coordinate,
)
from ugence_agentic_proposer import CandidateDisposition, ReviewAction
from ugence_policy_authority.api import AdapterRegistry

# --------------------------------------------------------------------------- #
# Fixed instants — every test time is explicit and timezone-aware.
# --------------------------------------------------------------------------- #
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

TENANT = "tenant-1"
CONSTITUTION_REF = "ugence.agent-constitution/tenant-1/baseline/v1"
ROLE_REF = "ugence.roles/tenant-1/reconciler/v1"
OTHER_GOVERNED_ROLE_REF = "ugence.roles/tenant-1/proposer-reviewer/v1"
POLICY_ID = "agent-constitution-baseline"
POLICY_VERSION = "1.0.0"

ADAPTER = AgentConstitutionPolicyFamilyAdapter()

#: The governed roles, in ascending codepoint order as the artifact requires.
GOVERNED_ROLE_REFS = tuple(sorted((ROLE_REF, OTHER_GOVERNED_ROLE_REF)))

#: The full closed vocabularies, derived from the imported enums, never restated.
ALL_DISPOSITIONS = tuple(sorted(member.value for member in CandidateDisposition))
ALL_REVIEW_ACTIONS = tuple(sorted(member.value for member in ReviewAction))

#: The default signed bounds: a strict subset of each closed vocabulary, plus two
#: tool scopes — so every bound has both an inside and an outside to test.
DISPOSITIONS_BOUND = tuple(sorted(ALL_DISPOSITIONS[:2]))
REVIEW_ACTIONS_BOUND = tuple(sorted(ALL_REVIEW_ACTIONS[:1]))
TOOL_SCOPES_BOUND = ("scope.evidence-read", "scope.report-write")


# --------------------------------------------------------------------------- #
# The constitution artifact
# --------------------------------------------------------------------------- #


def _metadata(content_digest: str, **overrides) -> AgentConstitutionPolicyMetadata:
    fields = dict(
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        content_digest=content_digest,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
        effective_from=T_FROM,
        effective_to=T_TO,
    )
    fields.update(overrides)
    return AgentConstitutionPolicyMetadata(**fields)


def make_constitution_policy(
    *,
    agent_constitution_ref: str = CONSTITUTION_REF,
    governed_role_refs=None,
    dispositions_bound=None,
    review_actions_bound=None,
    tool_scopes_bound=None,
    **meta_overrides,
) -> AgentConstitutionPolicy:
    """Build a constitution whose ``content_digest`` genuinely binds its own body."""

    body = dict(
        agent_constitution_ref=agent_constitution_ref,
        governed_role_refs=(
            GOVERNED_ROLE_REFS if governed_role_refs is None else governed_role_refs
        ),
        permitted_candidate_dispositions_bound=(
            DISPOSITIONS_BOUND if dispositions_bound is None else dispositions_bound
        ),
        permitted_review_actions_bound=(
            REVIEW_ACTIONS_BOUND if review_actions_bound is None else review_actions_bound
        ),
        permitted_tool_scopes_bound=(
            TOOL_SCOPES_BOUND if tool_scopes_bound is None else tool_scopes_bound
        ),
    )
    draft = AgentConstitutionPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides), **body
    )
    digest = ADAPTER.describe(draft).body_digest()
    return AgentConstitutionPolicy(metadata=_metadata(digest, **meta_overrides), **body)


# --------------------------------------------------------------------------- #
# A wired authority, and a resolver pointed at it
# --------------------------------------------------------------------------- #


def make_constitution_authority(*, adapters=None):
    """A real authority whose registry carries the agent-constitution family."""

    return make_authority(
        adapters=adapters if adapters is not None else AdapterRegistry([ADAPTER])
    )


def make_resolver(
    authority,
    *,
    policy=None,
    reference_map=None,
    tenant: str = TENANT,
    role_contract_ref: str = ROLE_REF,
):
    """A resolver whose mapping names exactly the issued constitution's coordinate."""

    if reference_map is None:
        if policy is None:
            raise ValueError("make_resolver needs a policy or an explicit mapping")
        reference_map = {
            (tenant, role_contract_ref): agent_constitution_coordinate(policy.metadata)
        }
    return build_constitution_resolver(
        reference_map=reference_map,
        registry=authority.registry,
        signature_verifier=authority.key_ring,
        approval_verifier=authority.approval,
        adapters=authority.adapters,
    )


def issued_world(*, policy=None, **policy_overrides):
    """Issue a constitution through the real authority and return a resolver for it."""

    policy = (
        policy if policy is not None else make_constitution_policy(**policy_overrides)
    )
    authority = make_constitution_authority()
    record = authority.issue(policy, issued_at=T_MID)
    resolver = make_resolver(authority, policy=policy)
    return authority, policy, record, resolver


# --------------------------------------------------------------------------- #
# Presented role facts
# --------------------------------------------------------------------------- #


def make_facts(
    *,
    tenant_id: str = TENANT,
    role_contract_ref: str = ROLE_REF,
    dispositions=None,
    review_actions=None,
    tool_scopes=None,
) -> GovernedRoleFacts:
    """Facts that conform to the default constitution unless overridden."""

    return GovernedRoleFacts(
        tenant_id=tenant_id,
        role_contract_ref=role_contract_ref,
        declared_candidate_dispositions=(
            DISPOSITIONS_BOUND if dispositions is None else dispositions
        ),
        declared_review_actions=(
            REVIEW_ACTIONS_BOUND if review_actions is None else review_actions
        ),
        declared_tool_scopes=(
            TOOL_SCOPES_BOUND[:1] if tool_scopes is None else tool_scopes
        ),
    )
