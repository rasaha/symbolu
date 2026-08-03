"""Distribution + product version and maturity metadata.

Two version concepts are kept separate:

* :data:`DISTRIBUTION_VERSION` — the independent wheel-packaging lifecycle of the
  ``ugence-policy-workflow-compiler`` distribution.
* :data:`PRODUCT_VERSION` — the Policy Workflow Compiler product/capability marker.

:func:`version_info` reports honest maturity booleans. The three
verification booleans (``structured_policy_pack_implemented``,
``deterministic_compilation_verified``,
``procurement_reference_equivalence_verified``) are only ``True`` because their
gates pass in this build's test suite. Document extraction, runtime deployment,
pilot validation, and production certification are all ``False``.
"""

from __future__ import annotations

import importlib
import importlib.metadata as _md
from dataclasses import dataclass, field
from typing import Dict, Optional

# The distribution (wheel) version is DELIBERATELY held at 0.1.0: it is an input
# to the v1 structural/logical digest (release._logical_payload), so bumping it
# would change every existing workflow_ir.v1 release digest and break P1
# fingerprint stability. P2 is an ADDITIVE contract (workflow_ir.v2) delivered at
# the same distribution version; the product marker below carries the P2 bump.
DISTRIBUTION_VERSION = "0.1.0"
DISTRIBUTION_NAME = "ugence-policy-workflow-compiler"
PRODUCT_NAME = "Ugence Policy Workflow Compiler"
PRODUCT_VERSION = "0.2.0"
CANONICAL_NAMESPACE = "ugence_policy_workflow_compiler"

#: Frozen v1 workflow-IR contract.
WORKFLOW_IR_V1 = "workflow_ir.v1"
#: Additive P2 semantic-enrichment contract.
WORKFLOW_IR_V2 = "workflow_ir.v2"
#: Every workflow-IR contract this build can emit / validate.
SUPPORTED_WORKFLOW_IR_VERSIONS = (WORKFLOW_IR_V1, WORKFLOW_IR_V2)
#: The source policy-pack schema version (unchanged).
POLICY_PACK_SCHEMA_VERSION = "policy_pack.v1"

#: Optional integrations this distribution can probe for at runtime. The core
#: compiler never imports these; the capability registry resolves capability
#: targets from metadata alone. version_info() reports availability only.
_OPTIONAL_INTEGRATIONS = {
    "procurement-reference": "ugence_procurement",
}

_TRACKED_DEPENDENCIES = ("pydantic",)


def _dist_version(name: str) -> Optional[str]:
    try:
        return _md.version(name)
    except Exception:  # pragma: no cover - best effort
        return None


def _module_available(module: Optional[str]) -> bool:
    if module is None:
        return False
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class VersionInfo:
    """Structured version + maturity metadata."""

    distribution: str
    distribution_version: str
    product: str
    product_version: str
    canonical_namespace: str
    structured_policy_pack_implemented: bool
    deterministic_compilation_verified: bool
    procurement_reference_equivalence_verified: bool
    document_extraction_implemented: bool
    runtime_deployment_implemented: bool
    pilot_validated: bool
    production_certified: bool
    # -- P2 semantic-enrichment maturity (contract workflow_ir.v2) --
    workflow_ir_v1_supported: bool = True
    workflow_ir_v2_supported: bool = False
    semantic_node_enrichment_implemented: bool = False
    capability_requirement_extraction_implemented: bool = False
    typed_contract_references_implemented: bool = False
    dependency_semantics_implemented: bool = False
    authority_semantics_implemented: bool = False
    human_review_semantics_implemented: bool = False
    policy_provenance_implemented: bool = False
    release_validation_implemented: bool = False
    deterministic_replay_verified: bool = False
    # -- explicit NON-goals (remain false; this package makes no such claim) --
    awc_adapter_updated: bool = False
    agent_eligibility_implemented: bool = False
    agent_ranking_implemented: bool = False
    team_composition_implemented: bool = False
    runtime_execution_implemented: bool = False
    action_authorization_implemented: bool = False
    enterprise_policy_evaluation_implemented: bool = False
    supported_workflow_ir_versions: tuple = ()
    dependency_versions: Dict[str, Optional[str]] = field(default_factory=dict)
    optional_integrations: Dict[str, bool] = field(default_factory=dict)
    build_commit: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product": self.product,
            "product_version": self.product_version,
            "canonical_namespace": self.canonical_namespace,
            "structured_policy_pack_implemented": self.structured_policy_pack_implemented,
            "deterministic_compilation_verified": self.deterministic_compilation_verified,
            "procurement_reference_equivalence_verified": (
                self.procurement_reference_equivalence_verified
            ),
            "document_extraction_implemented": self.document_extraction_implemented,
            "runtime_deployment_implemented": self.runtime_deployment_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "workflow_ir_v1_supported": self.workflow_ir_v1_supported,
            "workflow_ir_v2_supported": self.workflow_ir_v2_supported,
            "semantic_node_enrichment_implemented": self.semantic_node_enrichment_implemented,
            "capability_requirement_extraction_implemented": (
                self.capability_requirement_extraction_implemented
            ),
            "typed_contract_references_implemented": self.typed_contract_references_implemented,
            "dependency_semantics_implemented": self.dependency_semantics_implemented,
            "authority_semantics_implemented": self.authority_semantics_implemented,
            "human_review_semantics_implemented": self.human_review_semantics_implemented,
            "policy_provenance_implemented": self.policy_provenance_implemented,
            "release_validation_implemented": self.release_validation_implemented,
            "deterministic_replay_verified": self.deterministic_replay_verified,
            "awc_adapter_updated": self.awc_adapter_updated,
            "agent_eligibility_implemented": self.agent_eligibility_implemented,
            "agent_ranking_implemented": self.agent_ranking_implemented,
            "team_composition_implemented": self.team_composition_implemented,
            "runtime_execution_implemented": self.runtime_execution_implemented,
            "action_authorization_implemented": self.action_authorization_implemented,
            "enterprise_policy_evaluation_implemented": (
                self.enterprise_policy_evaluation_implemented
            ),
            "supported_workflow_ir_versions": list(self.supported_workflow_ir_versions),
            "dependency_versions": dict(self.dependency_versions),
            "optional_integrations": dict(self.optional_integrations),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + product version and maturity metadata.

    The three verification booleans are ``True`` in this build because the
    corresponding gates pass in the shipped test suite. ``document_extraction``,
    ``runtime_deployment``, ``pilot_validated`` and ``production_certified`` are
    hard-coded ``False`` — this package makes no such claim.
    """
    deps = {name: _dist_version(name) for name in _TRACKED_DEPENDENCIES}
    integrations = {
        name: _module_available(module)
        for name, module in _OPTIONAL_INTEGRATIONS.items()
    }
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=DISTRIBUTION_VERSION,
        product=PRODUCT_NAME,
        product_version=PRODUCT_VERSION,
        canonical_namespace=CANONICAL_NAMESPACE,
        structured_policy_pack_implemented=True,
        deterministic_compilation_verified=True,
        procurement_reference_equivalence_verified=True,
        document_extraction_implemented=False,
        runtime_deployment_implemented=False,
        pilot_validated=False,
        production_certified=False,
        # P2 semantic enrichment: implemented and verified by the shipped suite.
        workflow_ir_v1_supported=True,
        workflow_ir_v2_supported=True,
        semantic_node_enrichment_implemented=True,
        capability_requirement_extraction_implemented=True,
        typed_contract_references_implemented=True,
        dependency_semantics_implemented=True,
        authority_semantics_implemented=True,
        human_review_semantics_implemented=True,
        policy_provenance_implemented=True,
        release_validation_implemented=True,
        deterministic_replay_verified=True,
        # explicit non-goals — never claimed by this package.
        awc_adapter_updated=False,
        agent_eligibility_implemented=False,
        agent_ranking_implemented=False,
        team_composition_implemented=False,
        runtime_execution_implemented=False,
        action_authorization_implemented=False,
        enterprise_policy_evaluation_implemented=False,
        supported_workflow_ir_versions=SUPPORTED_WORKFLOW_IR_VERSIONS,
        dependency_versions=deps,
        optional_integrations=integrations,
        build_commit=None,
    )


__all__ = [
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "WORKFLOW_IR_V1",
    "WORKFLOW_IR_V2",
    "SUPPORTED_WORKFLOW_IR_VERSIONS",
    "POLICY_PACK_SCHEMA_VERSION",
    "VersionInfo",
    "version_info",
]
