"""Distribution version, frozen schema identities, and honest maturity metadata.

Three version concepts are kept apart, because conflating them is how a digest
stops being reproducible:

* :data:`DISTRIBUTION_VERSION` — the wheel-packaging lifecycle of the
  ``ugence-agent-constitution`` distribution. Never enters a digest.
* A **schema version** (``agent_constitution.v1`` and friends) — the frozen
  identity of an artifact *shape*. It is a pinned constant per artifact kind, and
  it does participate in that artifact's digest scope.
* An **artifact version** — the semantic version of one artifact's *content*
  along its own lineage (``1.0.0`` -> ``1.1.0``). Owned by the artifact, bumped by
  its issuer, and checked by :mod:`.compatibility`.

Nothing here reads ambient package metadata, the clock, or the environment.
"""

from __future__ import annotations

import importlib.metadata as _md
from dataclasses import dataclass, field
from typing import Dict, Optional

DISTRIBUTION_VERSION = "0.1.0"
DISTRIBUTION_NAME = "ugence-agent-constitution"
PRODUCT_NAME = "Ugence Agent Constitution"
PRODUCT_VERSION = "0.1.0"
CANONICAL_NAMESPACE = "ugence_agent_constitution"

#: Frozen schema identity of a drafting artifact. Carries no authority.
AGENT_ROLE_MANIFEST_V1 = "agent_role_manifest.v1"
#: Frozen schema identity of a ratified, immutable constitution.
AGENT_CONSTITUTION_V1 = "agent_constitution.v1"
#: Frozen schema identity of a developer implementation contract.
DEVELOPER_IMPLEMENTATION_CONTRACT_V1 = "developer_implementation_contract.v1"
#: Frozen schema identity of a conformance subject. AC-0 evaluates none.
CONFORMANCE_SUBJECT_V1 = "conformance_subject.v1"

#: Every schema identity this build can validate, per artifact kind. A version
#: absent from this mapping is not "probably fine": it is undecidable here, and
#: :mod:`.validation` reports INDETERMINATE for it rather than guessing.
SUPPORTED_SCHEMA_VERSIONS: Dict[str, tuple] = {
    "agent_role_manifest": (AGENT_ROLE_MANIFEST_V1,),
    "agent_constitution": (AGENT_CONSTITUTION_V1,),
    "developer_implementation_contract": (DEVELOPER_IMPLEMENTATION_CONTRACT_V1,),
    "conformance_subject": (CONFORMANCE_SUBJECT_V1,),
}

#: Schema identities this build once accepted and has since retired. Empty in the
#: first release; an entry here is a hard INVALID, not an INDETERMINATE, because a
#: retired shape is known to be wrong rather than merely unrecognized.
RETIRED_SCHEMA_VERSIONS: Dict[str, tuple] = {
    "agent_role_manifest": (),
    "agent_constitution": (),
    "developer_implementation_contract": (),
    "conformance_subject": (),
}

_TRACKED_DEPENDENCIES = ("pydantic",)


def _dist_version(name: str) -> Optional[str]:
    try:
        return _md.version(name)
    except Exception:  # pragma: no cover - best effort
        return None


@dataclass(frozen=True)
class VersionInfo:
    """Structured distribution version and maturity metadata.

    Every ``*_implemented`` boolean that is ``True`` is backed by a gate in this
    build's shipped test suite. Everything AC-0 declared out of scope is hard-coded
    ``False`` and stays that way until the corresponding scope is ratified and
    implemented — these are not aspirational flags.
    """

    distribution: str
    distribution_version: str
    product: str
    product_version: str
    canonical_namespace: str
    # -- AC-0 scope: implemented and gated in this build --
    canonical_serialization_implemented: bool = True
    content_fingerprinting_implemented: bool = True
    schema_validation_implemented: bool = True
    semantic_validation_implemented: bool = True
    version_compatibility_implemented: bool = True
    fail_closed_outcomes_implemented: bool = True
    immutable_artifacts_implemented: bool = True
    # -- explicit NON-goals of AC-0; never claimed by this package --
    compiler_implemented: bool = False
    capability_registry_implemented: bool = False
    conformance_findings_implemented: bool = False
    signing_implemented: bool = False
    ui_implemented: bool = False
    llm_assistance_implemented: bool = False
    runtime_binding_implemented: bool = False
    authority_decision_implemented: bool = False
    pilot_validated: bool = False
    production_certified: bool = False
    supported_schema_versions: Dict[str, tuple] = field(default_factory=dict)
    dependency_versions: Dict[str, Optional[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product": self.product,
            "product_version": self.product_version,
            "canonical_namespace": self.canonical_namespace,
            "canonical_serialization_implemented": self.canonical_serialization_implemented,
            "content_fingerprinting_implemented": self.content_fingerprinting_implemented,
            "schema_validation_implemented": self.schema_validation_implemented,
            "semantic_validation_implemented": self.semantic_validation_implemented,
            "version_compatibility_implemented": self.version_compatibility_implemented,
            "fail_closed_outcomes_implemented": self.fail_closed_outcomes_implemented,
            "immutable_artifacts_implemented": self.immutable_artifacts_implemented,
            "compiler_implemented": self.compiler_implemented,
            "capability_registry_implemented": self.capability_registry_implemented,
            "conformance_findings_implemented": self.conformance_findings_implemented,
            "signing_implemented": self.signing_implemented,
            "ui_implemented": self.ui_implemented,
            "llm_assistance_implemented": self.llm_assistance_implemented,
            "runtime_binding_implemented": self.runtime_binding_implemented,
            "authority_decision_implemented": self.authority_decision_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "supported_schema_versions": {
                k: list(v) for k, v in self.supported_schema_versions.items()
            },
            "dependency_versions": dict(self.dependency_versions),
        }


def version_info() -> VersionInfo:
    """Return structured distribution version and maturity metadata."""
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=DISTRIBUTION_VERSION,
        product=PRODUCT_NAME,
        product_version=PRODUCT_VERSION,
        canonical_namespace=CANONICAL_NAMESPACE,
        supported_schema_versions={
            k: tuple(v) for k, v in SUPPORTED_SCHEMA_VERSIONS.items()
        },
        dependency_versions={n: _dist_version(n) for n in _TRACKED_DEPENDENCIES},
    )


__all__ = [
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "AGENT_ROLE_MANIFEST_V1",
    "AGENT_CONSTITUTION_V1",
    "DEVELOPER_IMPLEMENTATION_CONTRACT_V1",
    "CONFORMANCE_SUBJECT_V1",
    "SUPPORTED_SCHEMA_VERSIONS",
    "RETIRED_SCHEMA_VERSIONS",
    "VersionInfo",
    "version_info",
]
