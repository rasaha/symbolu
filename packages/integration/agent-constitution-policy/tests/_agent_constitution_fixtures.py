"""Deterministic builders for agent-constitution policies.

Named ``_agent_constitution_fixtures`` rather than ``_fixtures`` so a combined
multi-package pytest run cannot shadow another package's fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ugence_agent_constitution_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_TENANT,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyFamilyAdapter,
    AgentConstitutionPolicyMetadata,
)
from ugence_agentic_proposer import CandidateDisposition, ReviewAction

# Fixed instants — every test time is explicit and timezone-aware.
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

TENANT = "tenant-1"
CONSTITUTION_REF = "ugence.agent-constitution/tenant-1/baseline/v1"

#: Governed role references, in ascending codepoint order.
GOVERNED_ROLE_REFS = (
    "ugence.roles/tenant-1/proposer-reviewer/v1",
    "ugence.roles/tenant-1/reconciler/v1",
)

ADAPTER = AgentConstitutionPolicyFamilyAdapter()

#: A strict subset of each closed vocabulary, sorted — derived, never restated.
DEFAULT_DISPOSITIONS_BOUND = tuple(
    sorted(sorted(member.value for member in CandidateDisposition)[:2])
)
DEFAULT_REVIEW_ACTIONS_BOUND = tuple(
    sorted(sorted(member.value for member in ReviewAction)[:1])
)
DEFAULT_TOOL_SCOPES_BOUND = ("scope.evidence-read", "scope.report-write")

FULL_DISPOSITIONS_BOUND = tuple(sorted(member.value for member in CandidateDisposition))
FULL_REVIEW_ACTIONS_BOUND = tuple(sorted(member.value for member in ReviewAction))


def _metadata(content_digest: str, **overrides) -> AgentConstitutionPolicyMetadata:
    fields = dict(
        policy_id="agent-constitution-baseline",
        version="1.0.0",
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
    governed_role_refs: Optional[tuple] = None,
    dispositions_bound: Optional[tuple] = None,
    review_actions_bound: Optional[tuple] = None,
    tool_scopes_bound: Optional[tuple] = None,
    **meta_overrides,
) -> AgentConstitutionPolicy:
    """Build a constitution whose ``content_digest`` genuinely binds its own body.

    Two passes, exactly as the authority's own fixtures do: the projection
    excludes ``metadata.content_digest``, so digesting a placeholder-carrying
    draft yields exactly the digest the final artifact must declare. No
    fixed-point iteration is involved — the second pass is a construction, not a
    re-computation.
    """

    body = dict(
        agent_constitution_ref=agent_constitution_ref,
        governed_role_refs=(
            GOVERNED_ROLE_REFS if governed_role_refs is None else governed_role_refs
        ),
        permitted_candidate_dispositions_bound=(
            DEFAULT_DISPOSITIONS_BOUND
            if dispositions_bound is None
            else dispositions_bound
        ),
        permitted_review_actions_bound=(
            DEFAULT_REVIEW_ACTIONS_BOUND
            if review_actions_bound is None
            else review_actions_bound
        ),
        permitted_tool_scopes_bound=(
            DEFAULT_TOOL_SCOPES_BOUND if tool_scopes_bound is None else tool_scopes_bound
        ),
    )
    draft = AgentConstitutionPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides), **body
    )
    digest = ADAPTER.describe(draft).body_digest()
    return AgentConstitutionPolicy(metadata=_metadata(digest, **meta_overrides), **body)
