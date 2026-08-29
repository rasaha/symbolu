"""The Cloud Scaling **capacity-bounds** policy family and its adapter.

The prerequisite R-8 turned out to rest on: no shipped policy family states a
capacity bound, so before anything can verify a bound it must be possible to
*issue* one. This distribution is that policy family — the shared Policy
Authority's **second**, and the first registered from outside the authority's own
distribution.

What it establishes
-------------------
A ``CapacityBoundsPolicy`` is a declarative, versioned, digest-bound artifact
stating ``max_permitted_magnitude`` and ``max_permitted_delta`` per action type,
optionally narrowed by resource class. Issued and signed through the shared
authority, it is the first thing in the tree a self-asserted candidate maximum
could ever be reconciled against.

What it deliberately does not do
--------------------------------
* **No comparison.** It does not compare a bound against a candidate's
  ``max_permitted_magnitude`` / ``max_permitted_delta``. That reconciliation is a
  later subphase with its own ruling; this package holds no candidate type.
* **No authorization, evaluation, or runtime state.** It reads no clock, calls no
  cloud API, and grants nothing.
* **No signing.** Issuance, signing, registry, resolution and revocation all
  belong to the shared authority. This package supplies an artifact and an
  adapter, nothing else.
* **No action-type reconciliation.** ``action_type`` is a free token; this family
  does not import the Phase 4C/D-4 canonical set, because a leaf policy family
  must not drag the Risk Authority in behind it. Reconciling the two vocabularies
  is recorded as deferred, not silently assumed.

Wiring is the composition root's job: register
:class:`CapacityBoundsPolicyFamilyAdapter` on an ``AdapterRegistry`` alongside
whatever other adapters that root configures.
"""

from __future__ import annotations

from .adapter import CapacityBoundsPolicyFamilyAdapter, capacity_bounds_coordinate
from .errors import (
    CapacityBoundsDuplicateError,
    CapacityBoundsFieldError,
    CapacityBoundsOrderingError,
    CapacityBoundsPolicyError,
    CapacityBoundsRejectionReason,
    rejection_reason_of,
    with_rejection_reason,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    CAPACITY_BOUNDS_ADAPTER_ID,
    CAPACITY_BOUNDS_POLICY_FAMILY,
    CAPACITY_BOUNDS_POLICY_TYPE,
    LIFECYCLE_APPROVED_ACTIVE,
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUPERSEDED,
    LIFECYCLE_WITHDRAWN,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    SUPPORTED_LIFECYCLE_STATES,
    SUPPORTED_POLICY_SCOPES,
)
from .policy import (
    PLACEHOLDER_CONTENT_DIGEST,
    CapacityBound,
    CapacityBoundsPolicy,
    CapacityBoundsPolicyMetadata,
)
from .version import __version__

__all__ = [
    "__version__",
    # Identity
    "CAPACITY_BOUNDS_ADAPTER_ID",
    "CAPACITY_BOUNDS_POLICY_FAMILY",
    "CAPACITY_BOUNDS_POLICY_TYPE",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "SUPPORTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "SUPPORTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
    # Artifact
    "CapacityBound",
    "CapacityBoundsPolicy",
    "CapacityBoundsPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
    # Adapter
    "CapacityBoundsPolicyFamilyAdapter",
    "capacity_bounds_coordinate",
    # Errors
    "CapacityBoundsPolicyError",
    "CapacityBoundsFieldError",
    "CapacityBoundsOrderingError",
    "CapacityBoundsDuplicateError",
    "CapacityBoundsRejectionReason",
    "rejection_reason_of",
    "with_rejection_reason",
]
