"""The change-effect ``PolicyFamilyAdapter``.

A new policy family is added by registering a new adapter, with no core change. This is
that registration, performed from outside the authority's own distribution.

    THE ADAPTER DESCRIBES AND PROJECTS. IT NEVER RESOLVES, ISSUES, APPROVES, SIGNS,
    VERIFIES A SIGNATURE, OR DECIDES ANYTHING ABOUT A CHANGE.

Resolution remains ``resolve_policy`` under configured trust, in the authority, and this
package neither calls it nor imports it. The two duties performed here are exactly the
two the repository precedent already authorizes: contract-shape recognition, and the
canonical projection.

The canonical projection mirrors the shipped adapters' discipline, because the discipline
is the authority's:

* the whole artifact is projected canonically, then **exactly one declared path** —
  ``metadata.content_digest`` — is **removed** from the mapping;
* removal is by path, not by name, so a ``content_digest`` appearing anywhere else in the
  artifact would remain bound;
* the field is removed, never blanked, so no sentinel participates in the digest;
* the artifact has no signature field, so the projection is structurally incapable of
  depending on a signature.

**Atomicity.** All three members — the protected-registry list, the delegation table and
the mapping coordinate — are inside the projection, so the body digest covers all three
together. Changing any one of them changes the digest, and a changed digest is a
different artifact version. That is what "atomically versioned" means here, and it is a
property of the projection rather than a promise in prose.
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

from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    CHANGE_EFFECT_ADAPTER_ID,
    CHANGE_EFFECT_POLICY_FAMILY,
    CHANGE_EFFECT_POLICY_TYPE,
)
from .policy import ChangeEffectClassificationPolicy, ChangeEffectPolicyMetadata

__all__ = [
    "ChangeEffectPolicyFamilyAdapter",
    "change_effect_coordinate",
]


def change_effect_coordinate(metadata: object) -> PolicyCoordinate:
    """Map this family's metadata envelope onto a family-neutral coordinate."""

    if not isinstance(metadata, ChangeEffectPolicyMetadata):
        raise PolicyAuthorityRequestError(
            "change_effect_coordinate requires a ChangeEffectPolicyMetadata"
        )
    # Re-checked rather than trusted: the family component is what keeps two families from
    # colliding in the authority's identity space, so the adapter states it rather than
    # reading whatever the envelope happens to report.
    if metadata.policy_family != CHANGE_EFFECT_POLICY_FAMILY:
        raise PolicyAuthorityRequestError(
            f"metadata reports policy family {metadata.policy_family!r}, not "
            f"{CHANGE_EFFECT_POLICY_FAMILY!r}"
        )
    return PolicyCoordinate(
        policy_family=CHANGE_EFFECT_POLICY_FAMILY,
        policy_id=metadata.policy_id,
        version=metadata.version,
        content_digest=metadata.content_digest,
        scope=metadata.scope,
        tenant_id=metadata.tenant_id,
    )


class ChangeEffectPolicyFamilyAdapter:
    """Registers the change-effect family with the shared authority."""

    @property
    def adapter_id(self) -> str:
        return CHANGE_EFFECT_ADAPTER_ID

    def recognizes(self, artifact: object) -> bool:
        """Exact runtime type match — a subclass is deliberately not recognized.

        A subclass could add fields this family never validates, and issuing it under the
        parent's identity would bind a digest over content nothing checked.
        """

        return type(artifact) is ChangeEffectClassificationPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, ChangeEffectPolicyMetadata):
            return None
        return change_effect_coordinate(reference)

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if type(artifact) is not ChangeEffectClassificationPolicy:
            raise UnsupportedPolicyArtifactError(
                f"{type(artifact).__name__!r} is not a ChangeEffectClassificationPolicy"
            )
        metadata = getattr(artifact, "metadata", None)
        if not isinstance(metadata, ChangeEffectPolicyMetadata):
            raise UnsupportedPolicyArtifactError(
                "ChangeEffectClassificationPolicy must carry a ChangeEffectPolicyMetadata "
                "envelope"
            )
        return PolicyArtifactDescriptor(
            adapter_id=CHANGE_EFFECT_ADAPTER_ID,
            policy_type=CHANGE_EFFECT_POLICY_TYPE,
            coordinate=change_effect_coordinate(metadata),
            declared_content_digest=metadata.content_digest,
            canonical_projection=self._canonical_projection(artifact),
            lifecycle_label=metadata.lifecycle_state,
            lifecycle_is_active=(metadata.lifecycle_state == ACTIVE_LIFECYCLE_STATE),
            supersedes_ref=metadata.supersedes_ref,
            effective_from=metadata.effective_from,
            effective_to=metadata.effective_to,
        )

    @staticmethod
    def _canonical_projection(artifact: Any) -> dict:
        """Project the artifact, removing exactly ``metadata.content_digest``.

        Canonicalization itself — NFC enforcement, naive-datetime rejection, ``float``
        rejection, UTC normalization — happens inside :func:`to_canonical_obj`, so a
        malformed artifact is refused here rather than silently digested.
        """

        body = to_canonical_obj(artifact, path="$")
        metadata = body.get("metadata") if isinstance(body, dict) else None
        if not isinstance(metadata, dict) or "content_digest" not in metadata:
            raise UnsupportedPolicyArtifactError(
                "the canonical projection must contain metadata.content_digest to remove"
            )
        metadata.pop("content_digest")
        return body
