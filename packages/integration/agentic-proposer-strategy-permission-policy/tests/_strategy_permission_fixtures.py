"""Deterministic builders for strategy-permission policies.

Named ``_strategy_permission_fixtures`` rather than ``_fixtures`` so a combined
multi-package pytest run cannot shadow another package's fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ugence_agentic_proposer import ReasoningStrategy
from ugence_agentic_proposer_strategy_permission_policy import (
    LIFECYCLE_APPROVED_ACTIVE,
    PLACEHOLDER_CONTENT_DIGEST,
    POLICY_SCOPE_TENANT,
    StrategyPermissionPolicy,
    StrategyPermissionPolicyFamilyAdapter,
    StrategyPermissionPolicyMetadata,
)

# Fixed instants — every test time is explicit and timezone-aware.
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

TENANT = "tenant-1"
STRATEGY_POLICY_REF = "ugence.agentic-proposer/strategy-permission/reviewer-role/v1"

ADAPTER = StrategyPermissionPolicyFamilyAdapter()

#: Two of the three ratified spellings, in ascending codepoint order.
DEFAULT_PERMITTED = tuple(
    sorted(
        (
            ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value,
            ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value,
        )
    )
)


def _metadata(content_digest: str, **overrides) -> StrategyPermissionPolicyMetadata:
    fields = dict(
        policy_id="agentic-proposer-strategy-permission",
        version="1.0.0",
        content_digest=content_digest,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
        effective_from=T_FROM,
        effective_to=T_TO,
    )
    fields.update(overrides)
    return StrategyPermissionPolicyMetadata(**fields)


def make_permission_policy(
    *,
    permitted: Optional[tuple] = None,
    strategy_policy_ref: str = STRATEGY_POLICY_REF,
    **meta_overrides,
) -> StrategyPermissionPolicy:
    """Build a policy whose ``content_digest`` genuinely binds its own body.

    Two passes, exactly as the authority's own fixtures do: the projection
    excludes ``metadata.content_digest``, so digesting a placeholder-carrying
    draft yields exactly the digest the final artifact must declare. No
    fixed-point iteration is involved — the second pass is a construction, not a
    re-computation.
    """

    body = DEFAULT_PERMITTED if permitted is None else permitted
    draft = StrategyPermissionPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides),
        strategy_policy_ref=strategy_policy_ref,
        permitted_strategies=body,
    )
    digest = ADAPTER.describe(draft).body_digest()
    return StrategyPermissionPolicy(
        metadata=_metadata(digest, **meta_overrides),
        strategy_policy_ref=strategy_policy_ref,
        permitted_strategies=body,
    )
