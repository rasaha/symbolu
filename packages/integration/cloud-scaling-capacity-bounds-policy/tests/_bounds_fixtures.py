"""Deterministic builders for capacity-bounds policies.

Named ``_bounds_fixtures`` rather than ``_fixtures`` so a combined multi-package
pytest run cannot shadow another package's fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from ugence_cloud_scaling_capacity_bounds_policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    CapacityBound,
    CapacityBoundsPolicy,
    CapacityBoundsPolicyFamilyAdapter,
    CapacityBoundsPolicyMetadata,
    LIFECYCLE_APPROVED_ACTIVE,
    POLICY_SCOPE_TENANT,
)

# Fixed instants — every test time is explicit and timezone-aware.
T_BEFORE = datetime(2025, 6, 1, tzinfo=timezone.utc)
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

TENANT = "tenant-1"

ADAPTER = CapacityBoundsPolicyFamilyAdapter()

DEFAULT_BOUNDS = (
    CapacityBound(
        action_type="cloud_scaling.scale_out",
        max_permitted_magnitude=100,
        max_permitted_delta=25,
    ),
    CapacityBound(
        action_type="cloud_scaling.scale_out",
        max_permitted_magnitude=40,
        max_permitted_delta=10,
        resource_class="gpu",
    ),
)


def _metadata(content_digest: str, **overrides) -> CapacityBoundsPolicyMetadata:
    fields = dict(
        policy_id="cloud-scaling-capacity-bounds",
        version="1.0.0",
        content_digest=content_digest,
        scope=POLICY_SCOPE_TENANT,
        lifecycle_state=LIFECYCLE_APPROVED_ACTIVE,
        tenant_id=TENANT,
        effective_from=T_FROM,
        effective_to=T_TO,
    )
    fields.update(overrides)
    return CapacityBoundsPolicyMetadata(**fields)


def make_bounds_policy(
    *, bounds: Optional[tuple] = None, **meta_overrides
) -> CapacityBoundsPolicy:
    """Build a policy whose ``content_digest`` genuinely binds its own body.

    Two passes, exactly as the UVI fixtures do: the projection excludes
    ``metadata.content_digest``, so digesting a placeholder-carrying draft yields
    exactly the digest the final artifact must declare. No fixed-point iteration
    is involved — the second pass is a construction, not a re-computation.
    """

    body = bounds if bounds is not None else DEFAULT_BOUNDS
    draft = CapacityBoundsPolicy(
        metadata=_metadata(PLACEHOLDER_CONTENT_DIGEST, **meta_overrides), bounds=body
    )
    digest = ADAPTER.describe(draft).body_digest()
    return CapacityBoundsPolicy(
        metadata=_metadata(digest, **meta_overrides), bounds=body
    )
