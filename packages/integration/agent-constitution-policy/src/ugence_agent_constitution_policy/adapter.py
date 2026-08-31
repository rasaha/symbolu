"""The Agent Constitution ``PolicyFamilyAdapter``.

The shared Policy Authority ratified that a new policy family is added by
registering a new adapter, with **no core change**. This is that registration,
performed from outside the authority's own distribution: the adapter lives in the
family's package, and the composition root wires it — through
:func:`~ugence_agent_constitution_policy.registration.register_agent_constitution_policy_family`,
which also runs the `ACC-S1-Q3` family-collision guard.

It could not live inside the authority even if that were desirable — the
authority's own packaging suite bars every module under ``ugence_policy_authority``
from importing anything but the standard library, itself and one contracts leaf,
and this family imports the Agentic Proposer's ratified vocabulary.

The canonical projection
------------------------
Mirrors the shipped adapters' discipline exactly, because the discipline is the
authority's:

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

from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    AGENT_CONSTITUTION_ADAPTER_ID,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    AGENT_CONSTITUTION_POLICY_TYPE,
)
from .policy import AgentConstitutionPolicy, AgentConstitutionPolicyMetadata

__all__ = [
    "AgentConstitutionPolicyFamilyAdapter",
    "agent_constitution_coordinate",
]


def agent_constitution_coordinate(metadata: object) -> PolicyCoordinate:
    """Map this family's metadata envelope onto a family-neutral coordinate."""

    if not isinstance(metadata, AgentConstitutionPolicyMetadata):
        raise PolicyAuthorityRequestError(
            "agent_constitution_coordinate requires an AgentConstitutionPolicyMetadata"
        )
    # Re-checked here rather than trusted: the family component is what keeps two
    # families from colliding in the authority's identity space, so the adapter
    # states it rather than reading whatever the envelope happens to report.
    if metadata.policy_family != AGENT_CONSTITUTION_POLICY_FAMILY:
        raise PolicyAuthorityRequestError(
            f"metadata reports policy family {metadata.policy_family!r}, not "
            f"{AGENT_CONSTITUTION_POLICY_FAMILY!r}"
        )
    return PolicyCoordinate(
        policy_family=AGENT_CONSTITUTION_POLICY_FAMILY,
        policy_id=metadata.policy_id,
        version=metadata.version,
        content_digest=metadata.content_digest,
        scope=metadata.scope,
        tenant_id=metadata.tenant_id,
    )


class AgentConstitutionPolicyFamilyAdapter:
    """Registers the Agent Constitution family with the shared authority."""

    @property
    def adapter_id(self) -> str:
        return AGENT_CONSTITUTION_ADAPTER_ID

    @property
    def policy_family(self) -> str:
        """The one family value this adapter answers for.

        Advertised on the adapter so a registration-time guard — this family's
        own (`ACC-S1-Q3`), or a future family's — can compare family values
        across an assembled registry without constructing a foreign artifact.
        """

        return AGENT_CONSTITUTION_POLICY_FAMILY

    # ------------------------------------------------------------------
    # Recognition
    # ------------------------------------------------------------------
    def recognizes(self, artifact: object) -> bool:
        """Exact runtime type match — a subclass is deliberately not recognized."""

        return type(artifact) is AgentConstitutionPolicy

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        if not isinstance(reference, AgentConstitutionPolicyMetadata):
            return None
        return agent_constitution_coordinate(reference)

    # ------------------------------------------------------------------
    # Description
    # ------------------------------------------------------------------
    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        if type(artifact) is not AgentConstitutionPolicy:
            raise UnsupportedPolicyArtifactError(
                f"{type(artifact).__name__!r} is not an AgentConstitutionPolicy"
            )

        metadata = getattr(artifact, "metadata", None)
        if not isinstance(metadata, AgentConstitutionPolicyMetadata):
            raise UnsupportedPolicyArtifactError(
                "AgentConstitutionPolicy must carry an AgentConstitutionPolicyMetadata "
                "envelope"
            )

        projection = self._canonical_projection(artifact)

        return PolicyArtifactDescriptor(
            adapter_id=AGENT_CONSTITUTION_ADAPTER_ID,
            # A constant, not ``type(artifact).__name__``: the value is framed into
            # every body digest, so a class rename must be a deliberate act.
            policy_type=AGENT_CONSTITUTION_POLICY_TYPE,
            coordinate=agent_constitution_coordinate(metadata),
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
            raise UnsupportedPolicyArtifactError(
                "an agent-constitution policy must carry a metadata envelope with a "
                "content_digest declaration"
            )
        body = dict(body)
        body["metadata"] = {k: v for k, v in metadata.items() if k != "content_digest"}
        return body
