"""Shared base, enums and reference tokens for agent-constitution artifacts.

Every artifact in this package is a **frozen** pydantic model with ``extra``
forbidden. Frozen is not decoration: an artifact that can be mutated in place
after its digest is computed is an artifact whose digest means nothing. Drafting
still needs to be possible, so the drafting artifact offers copy-on-write
revision instead of mutation — see :class:`~.manifest.AgentRoleManifest`.

``extra="forbid"`` matters for the same reason. A payload carrying a field this
build does not know about is not a payload this build can digest faithfully: the
unknown field would be dropped, and the digest would attest to less than the
author wrote. Refusing is the fail-closed answer.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class ArtifactKind(str, Enum):
    """The closed set of artifact kinds AC-0 defines."""

    AGENT_ROLE_MANIFEST = "agent_role_manifest"
    AGENT_CONSTITUTION = "agent_constitution"
    DEVELOPER_IMPLEMENTATION_CONTRACT = "developer_implementation_contract"
    CONFORMANCE_SUBJECT = "conformance_subject"


class RequirementObligation(str, Enum):
    """How strongly a capability requirement binds the implementation.

    ``CONDITIONAL`` is the only value that admits a condition, and it *requires*
    one: a conditional obligation with no stated condition is not a weaker rule,
    it is an unreadable one.
    """

    MANDATORY = "MANDATORY"
    CONDITIONAL = "CONDITIONAL"
    PROHIBITED = "PROHIBITED"


class IssuerKind(str, Enum):
    """What sort of identity ratified a constitution.

    This records *who claims to have issued* the artifact. It is descriptive
    provenance, not proof: AC-0 ships no signing, so nothing here is verified, and
    no value of this enum confers authority on its holder.
    """

    HUMAN_OWNER = "HUMAN_OWNER"
    OWNER_BODY = "OWNER_BODY"
    DELEGATED_REVIEWER = "DELEGATED_REVIEWER"


class SubjectKind(str, Enum):
    """What a conformance subject points at."""

    AGENT_IMPLEMENTATION = "AGENT_IMPLEMENTATION"
    DEVELOPER_ARTIFACT = "DEVELOPER_ARTIFACT"
    DEPLOYMENT_CANDIDATE = "DEPLOYMENT_CANDIDATE"


class FrozenArtifact(BaseModel):
    """Base for every artifact: frozen, extra-forbidden, digest-scope aware."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=False,
        validate_default=True,
    )

    #: Top-level fields excluded from this artifact's own content digest.
    #: Overridden by digest-bearing artifacts to exclude the digest field itself.
    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset] = frozenset()

    def canonical_obj(self) -> Any:
        """Return this artifact as canonical, JSON-native Python objects."""
        from ..serialization.canonical_json import to_canonical_obj

        return to_canonical_obj(self)

    def canonical_json(self) -> str:
        """Return this artifact's canonical JSON encoding."""
        from ..serialization.canonical_json import dumps

        return dumps(self)


class ContentRef(FrozenArtifact):
    """An opaque, co-required reference to content this package does not own.

    Identifier and digest travel together on purpose. An identifier alone names a
    thing without pinning which version of it was meant; a digest alone pins
    content without saying what it is. Requiring both is what makes a reference
    checkable by a later consumer that *does* hold the target.
    """

    ref_id: str
    content_digest: str


class CapabilityRegistryEntryRef(FrozenArtifact):
    """A reference to one entry in an external capability registry.

    AC-0 owns **no** registry and resolves nothing. This is a pinned, opaque token:
    a namespace, an entry identifier, the entry version that was meant, and the
    digest of that entry's content. A consumer that holds the registry can check
    the token; this package can only check that it is well-formed and internally
    consistent.

    The type is deliberately named ``CapabilityRegistryEntryRef`` and not
    ``CapabilityRegistry``/``CapabilityDefinition``/``CapabilityManifest`` — those
    names belong to other packages and mean other things.
    """

    registry_namespace: str
    entry_id: str
    entry_version: str
    entry_digest: str

    @property
    def token(self) -> str:
        """A stable, human-readable rendering of the pinned token."""
        return f"{self.registry_namespace}/{self.entry_id}@{self.entry_version}"


class ConstitutionRef(FrozenArtifact):
    """A pinned reference to one ratified constitution.

    Carries lineage identity, the artifact version meant, and that version's
    content digest. A downstream artifact that references a constitution without
    a digest would silently follow the lineage wherever it went; pinning the digest
    means a successor constitution invalidates the reference instead of quietly
    redefining it.
    """

    constitution_id: str
    artifact_version: str
    content_digest: str


class PredecessorRef(ConstitutionRef):
    """The immediately preceding constitution in a lineage.

    Structurally a :class:`ConstitutionRef`; kept a distinct type because the rules
    that apply to it are different — a predecessor must share the successor's
    lineage identity, must be strictly older, and must not carry the successor's
    own digest. See :mod:`..compatibility`.
    """


class IssuerIdentity(FrozenArtifact):
    """Who ratified a constitution, as claimed by the artifact.

    Unverified by construction. AC-0 ships no signing and makes no authority
    decision, so this records a claim of provenance and nothing more. The one rule
    this package does enforce about it is structural and lives in semantic
    validation: an issuer may not be the author of the manifest being ratified.
    """

    issuer_id: str
    issuer_display_name: str
    issuer_kind: IssuerKind


__all__ = [
    "ArtifactKind",
    "RequirementObligation",
    "IssuerKind",
    "SubjectKind",
    "FrozenArtifact",
    "ContentRef",
    "CapabilityRegistryEntryRef",
    "ConstitutionRef",
    "PredecessorRef",
    "IssuerIdentity",
]
