"""The agent constitution — the ratified, immutable, versioned artifact.

A constitution is what a manifest becomes *after* someone with standing ratified
it. It is content-addressed, carries its own lineage, and cannot be edited: a
change produces a successor with a new artifact version, a new digest, and a
reference back to what it replaced.

What this artifact does NOT do, in AC-0 or in any reading of it:

* It does not make an authority decision. It *records* that an issuer claims to
  have ratified content. Whether that issuer had standing is not decided here.
* It is not signed. ``issuer`` is an unverified claim of provenance; the digest
  attests to content identity only.
* It does not bind anything at runtime. Nothing in this package resolves a
  capability, admits an agent, or authorizes an action.
"""

from __future__ import annotations

from typing import ClassVar, Optional, Tuple

from ..version import AGENT_CONSTITUTION_V1
from .capability import CapabilityRequirement
from .common import FrozenArtifact, IssuerIdentity, PredecessorRef


class AgentConstitution(FrozenArtifact):
    """A ratified, immutable, versioned agent constitution."""

    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset] = frozenset({"content_digest"})

    #: Frozen identity of the artifact *shape*. In digest scope: a constitution
    #: read under a different schema is a different artifact.
    schema_version: str = AGENT_CONSTITUTION_V1
    #: Stable lineage identity. Constant across every version of this constitution.
    constitution_id: str
    #: Semantic version of this artifact's content along its lineage.
    artifact_version: str
    #: The version this one replaces, or ``None`` for the first in a lineage.
    predecessor: Optional[PredecessorRef] = None
    #: Who claims to have ratified this. Unverified.
    issuer: IssuerIdentity
    #: The draft this was ratified from, pinned by identity and digest.
    source_manifest_id: str
    source_manifest_digest: str
    #: The manifest's author. Compared against the issuer to refuse self-ratification.
    source_manifest_author_id: str
    role_name: str
    role_summary: str
    capability_requirements: Tuple[CapabilityRequirement, ...] = ()
    prohibited_actions: Tuple[str, ...] = ()
    #: Caller-supplied ISO-8601 instant of ratification. This package never reads a
    #: clock; the value is data, in digest scope like any other field.
    ratified_at: str
    #: Canonical content digest over every field except itself.
    content_digest: str = ""

    #: Permanently ``True`` — the type *is* the ratified state. Nothing sets this.
    is_ratified: ClassVar[bool] = True
    #: Permanently ``False``. A constitution states rules; it confers no power to
    #: decide anything. Authority decisions are out of AC-0 scope entirely.
    makes_authority_decision: ClassVar[bool] = False
    #: Permanently ``False``. AC-0 ships no signing.
    is_signed: ClassVar[bool] = False

    def with_content_digest(self) -> "AgentConstitution":
        """Return this constitution with ``content_digest`` set to its recomputed value."""
        from ..fingerprint import compute_content_digest

        return self.model_copy(update={"content_digest": compute_content_digest(self)})

    def as_ref(self) -> "PredecessorRef":
        """Return a pinned reference to this exact version, usable as a predecessor."""
        return PredecessorRef(
            constitution_id=self.constitution_id,
            artifact_version=self.artifact_version,
            content_digest=self.content_digest,
        )

    def succeeds(self, other: "AgentConstitution") -> bool:
        """True when this artifact's predecessor reference pins ``other`` exactly."""
        return (
            self.predecessor is not None
            and self.predecessor.constitution_id == other.constitution_id
            and self.predecessor.artifact_version == other.artifact_version
            and self.predecessor.content_digest == other.content_digest
        )

    @property
    def is_lineage_root(self) -> bool:
        """True for the first constitution in a lineage."""
        return self.predecessor is None

    @property
    def requirement_ids(self) -> Tuple[str, ...]:
        """Declared requirement identifiers, in declaration order (duplicates kept)."""
        return tuple(r.requirement_id for r in self.capability_requirements)


__all__ = ["AgentConstitution"]
