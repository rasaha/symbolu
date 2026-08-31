"""The capacity-bounds ``PolicyFamilyAdapter`` — the authority's second family.

The shared Policy Authority ratified that a second policy family is added by
registering a second adapter, with **no core change**. This is that registration,
performed from outside the authority's own distribution: the adapter lives in the
family's package, and the composition root wires it.

The canonical projection
------------------------
Mirrors the UVI adapter's discipline exactly, because the discipline is the
authority's, not UVI's:

* the whole artifact is projected canonically, then **exactly one declared
  path** — ``metadata.content_digest`` — is **removed** from the mapping;
* removal is by path, not by name, so a ``content_digest`` appearing anywhere
  else in the artifact would remain bound;
* the field is removed, never blanked, so no sentinel participates in the digest
  and setting the declaration to the computed result cannot change the result;
* the artifact has no signature field, so the projection is structurally
  incapable of depending on a signature.

Recognition is an **exact runtime type** test rather than ``isinstance``: a
subclass could add fields this family never validates, and issuing it under the
parent's identity would bind a digest over content nothing checked.
"""

from __future__ import annotations

from typing import Any, Optional

from ugence_policy_authority.api import (
    PolicyArtifactDescriptor,
    PolicyAuthorityRequestError,
    PolicyCoordinate,
    UnsupportedPolicyArtifactError,
    to_canonical_obj,
)

from .errors import (
    CapacityBoundsRejectionReason as Reason,
    with_rejection_reason,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    CAPACITY_BOUNDS_ADAPTER_ID,
    CAPACITY_BOUNDS_POLICY_FAMILY,
    CAPACITY_BOUNDS_POLICY_TYPE,
)
from .policy import CapacityBoundsPolicy, CapacityBoundsPolicyMetadata

__all__ = [
    "CapacityBoundsPolicyFamilyAdapter",
    "capacity_bounds_coordinate",
]


def capacity_bounds_coordinate(metadata: object) -> PolicyCoordinate:
    """Map this family's metadata envelope onto a family-neutral coordinate."""

    if not isinstance(metadata, CapacityBoundsPolicyMetadata):
        raise with_rejection_reason(
            PolicyAuthorityRequestError(
                "capacity_bounds_coordinate requires a CapacityBoundsPolicyMetadata"
            ),
            Reason.COORDINATE_INPUT_TYPE_MISMATCH,
        )
    return PolicyCoordinate(
        policy_family=CAPACITY_BOUNDS_POLICY_FAMILY,
        policy_id=metadata.policy_id,
        version=metadata.version,
        content_digest=metadata.content_digest,
        scope=metadata.scope,
        tenant_id=metadata.tenant_id,
    )


class CapacityBoundsPolicyFamilyAdapter:
    """Registers the Cloud Scaling capacity-bounds family with the shared authority."""

    @property
    def adapter_id(self) -> str:
        return CAPACITY_BOUNDS_ADAPTER_ID

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------
    def recognizes(self, artifact: object) -> bool:
        """Exact runtime type match — a subclass is deliberately not recognized."""

        return type(artifact) is CapacityBoundsPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, CapacityBoundsPolicyMetadata):
            return None
        return capacity_bounds_coordinate(reference)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------
    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if type(artifact) is not CapacityBoundsPolicy:
            raise with_rejection_reason(
                UnsupportedPolicyArtifactError(
                    f"{type(artifact).__name__!r} is not a CapacityBoundsPolicy"
                ),
                Reason.ARTIFACT_TYPE_MISMATCH,
            )

        metadata = getattr(artifact, "metadata", None)
        if not isinstance(metadata, CapacityBoundsPolicyMetadata):
            raise with_rejection_reason(
                UnsupportedPolicyArtifactError(
                    "CapacityBoundsPolicy must carry a CapacityBoundsPolicyMetadata envelope"
                ),
                Reason.METADATA_ENVELOPE_MISSING,
            )

        projection = self._canonical_projection(artifact)

        return PolicyArtifactDescriptor(
            adapter_id=CAPACITY_BOUNDS_ADAPTER_ID,
            # A constant, not ``type(artifact).__name__``: the value is framed into
            # every body digest, so a class rename must be a deliberate act.
            policy_type=CAPACITY_BOUNDS_POLICY_TYPE,
            coordinate=capacity_bounds_coordinate(metadata),
            declared_content_digest=metadata.content_digest,
            canonical_projection=projection,
            lifecycle_label=metadata.lifecycle_state,
            lifecycle_is_active=(metadata.lifecycle_state == ACTIVE_LIFECYCLE_STATE),
            supersedes_ref=metadata.supersedes_ref,
            effective_from=metadata.effective_from,
            effective_to=metadata.effective_to,
        )

    # ------------------------------------------------------------------
    # Canonical projection
    # ------------------------------------------------------------------
    @staticmethod
    def _canonical_projection(artifact: Any) -> dict:
        """Project the artifact, removing exactly ``metadata.content_digest``.

        Canonicalization itself — NFC enforcement, naive-datetime rejection,
        ``float`` rejection, UTC normalization — happens inside
        :func:`to_canonical_obj`, so a malformed artifact is refused here rather
        than silently digested.
        """

        body = to_canonical_obj(artifact, path="$")
        metadata = body.get("metadata") if isinstance(body, dict) else None
        if not isinstance(metadata, dict) or "content_digest" not in metadata:
            raise with_rejection_reason(
                UnsupportedPolicyArtifactError(
                    "a capacity-bounds policy must carry a metadata envelope with a "
                    "content_digest declaration"
                ),
                Reason.PROJECTION_DIGEST_DECLARATION_MISSING,
            )
        body = dict(body)
        body["metadata"] = {k: v for k, v in metadata.items() if k != "content_digest"}
        return body
