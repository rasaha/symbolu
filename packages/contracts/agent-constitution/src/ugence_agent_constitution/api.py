"""The curated public API of ``ugence_agent_constitution``.

``__all__`` here is the contract. ``tests/packaging/test_public_api.py`` asserts
that ``public_api.json`` matches this list exactly, so the surface cannot grow or
shrink without the change being visible in a reviewed file.

What is deliberately NOT here, because AC-0 does not implement it: any compiler,
any capability registry, any conformance finding or verdict, any signing or key
material, any UI, any LLM assistance, any runtime binding, and any authority
decision.
"""

from __future__ import annotations

from .compatibility import (
    SchemaCompatibility,
    SuccessionCompatibility,
    compare_artifact_versions,
    is_semantic_version,
    parse_semantic_version,
    requires_version_bump,
    schema_compatibility,
    succession_compatibility,
)
from .errors import (
    AgentConstitutionContractError,
    DigestScopeError,
    MalformedVersionError,
    UnknownArtifactKind,
)
from .fingerprint import (
    DIGEST_ALGORITHM,
    DIGEST_PREFIX,
    compute_content_digest,
    digest_scope,
    digests_agree,
    fingerprint,
    fingerprint_sequence,
    fingerprint_text,
    is_well_formed_digest,
)
from .models import (
    AgentConstitution,
    AgentRoleManifest,
    ArtifactKind,
    CapabilityRegistryEntryRef,
    CapabilityRequirement,
    ConformanceSubject,
    ConstitutionRef,
    ContentRef,
    DeveloperImplementationContract,
    FrozenArtifact,
    IssuerIdentity,
    IssuerKind,
    PredecessorRef,
    RequirementObligation,
    SubjectKind,
)
from .serialization.canonical_json import dumps, dumps_pretty, loads, to_canonical_obj
from .validation import (
    ValidationFinding,
    ValidationOutcome,
    ValidationReport,
    combine_outcomes,
    is_ratified_constitution,
    validate_artifact,
    validate_constitution,
)
from .version import (
    AGENT_CONSTITUTION_V1,
    AGENT_ROLE_MANIFEST_V1,
    CONFORMANCE_SUBJECT_V1,
    DEVELOPER_IMPLEMENTATION_CONTRACT_V1,
    DISTRIBUTION_NAME,
    DISTRIBUTION_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    VersionInfo,
    version_info,
)

__all__ = [
    # -- artifacts --
    "AgentConstitution",
    "AgentRoleManifest",
    "ConformanceSubject",
    "DeveloperImplementationContract",
    "CapabilityRequirement",
    "CapabilityRegistryEntryRef",
    "ConstitutionRef",
    "ContentRef",
    "PredecessorRef",
    "IssuerIdentity",
    "FrozenArtifact",
    # -- enums --
    "ArtifactKind",
    "IssuerKind",
    "RequirementObligation",
    "SubjectKind",
    "SchemaCompatibility",
    "SuccessionCompatibility",
    "ValidationOutcome",
    # -- canonical serialization --
    "to_canonical_obj",
    "dumps",
    "dumps_pretty",
    "loads",
    # -- fingerprinting --
    "DIGEST_ALGORITHM",
    "DIGEST_PREFIX",
    "fingerprint",
    "fingerprint_text",
    "fingerprint_sequence",
    "digest_scope",
    "compute_content_digest",
    "is_well_formed_digest",
    "digests_agree",
    # -- validation --
    "ValidationFinding",
    "ValidationReport",
    "combine_outcomes",
    "validate_artifact",
    "validate_constitution",
    "is_ratified_constitution",
    # -- version compatibility --
    "parse_semantic_version",
    "is_semantic_version",
    "compare_artifact_versions",
    "schema_compatibility",
    "succession_compatibility",
    "requires_version_bump",
    # -- errors --
    "AgentConstitutionContractError",
    "UnknownArtifactKind",
    "MalformedVersionError",
    "DigestScopeError",
    # -- distribution metadata --
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "AGENT_ROLE_MANIFEST_V1",
    "AGENT_CONSTITUTION_V1",
    "DEVELOPER_IMPLEMENTATION_CONTRACT_V1",
    "CONFORMANCE_SUBJECT_V1",
    "SUPPORTED_SCHEMA_VERSIONS",
    "VersionInfo",
    "version_info",
]
