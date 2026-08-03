"""Distribution + product version and honest maturity metadata.

Three version concepts are kept separate:

* :data:`DISTRIBUTION_VERSION` — the independent wheel-packaging lifecycle of the
  ``ugence-agent-workforce-composer`` distribution.
* :data:`PRODUCT_VERSION` — the Agent Workforce Composer product/capability marker.
* :data:`CONTRACT_VERSION` — the frozen planning-contract version (``awc.v1``)
  stamped onto every canonical object and eligibility result.

:func:`version_info` reports honest maturity booleans. Only the P1 verification
booleans are ``True``; ranking, team composition, permission assignment, runtime
handoff, H16 migration, live registry, pilot validation and production
certification are all ``False``. This package makes no such claim.
"""
from __future__ import annotations

import importlib
import importlib.metadata as _md
from dataclasses import dataclass, field
from typing import Dict, Optional

__version__ = "0.2.0"

DISTRIBUTION_VERSION = "0.2.0"
DISTRIBUTION_NAME = "ugence-agent-workforce-composer"
PRODUCT_NAME = "Ugence Agent Workforce Composer"
PRODUCT_VERSION = "0.2.0"
CANONICAL_NAMESPACE = "ugence_agent_workforce_composer"

#: The frozen P1 planning-contract version, stamped on P1 canonical objects and
#: results. UNCHANGED in P2 — P1 object fingerprints are stable for identical inputs.
CONTRACT_VERSION = "awc.v1"

#: The additive P2 composition-plan contract version, stamped on ranking,
#: composition, permission-bound, fallback and AgentTeamPlan objects.
COMPOSITION_CONTRACT_VERSION = "awc.composition.v1"

VERSION = __version__

#: Compiler workflow-IR contract version this build's adapter consumes.
SUPPORTED_IR_VERSIONS = ("workflow_ir.v1",)

_TRACKED_DEPENDENCIES = ("pydantic",)

#: Optional integrations this distribution can probe for (never imported by the
#: deterministic core). ``version_info`` reports availability only.
_OPTIONAL_INTEGRATIONS = {
    "compiler-reference": "ugence_policy_workflow_compiler",
}


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
    contract_version: str
    composition_contract_version: str
    supported_ir_versions: tuple
    # -- implemented in P1 --
    canonical_object_model_implemented: bool
    compiler_adapter_implemented: bool
    hard_constraint_eligibility_implemented: bool
    deterministic_replay_verified: bool
    # -- implemented in P2 --
    deterministic_ranking_implemented: bool
    agent_ranking_implemented: bool
    team_composition_implemented: bool
    permission_bound_proposal_implemented: bool
    fallback_planning_implemented: bool
    agent_team_plan_implemented: bool
    # -- explicitly NOT implemented --
    permission_assignment_implemented: bool
    permission_granting_implemented: bool
    runtime_handoff_implemented: bool
    runtime_execution_implemented: bool
    live_availability_implemented: bool
    h16_migration_implemented: bool
    model_selection_integration_implemented: bool
    h22_integration_implemented: bool
    live_registry_implemented: bool
    pilot_validated: bool
    production_certified: bool
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
            "contract_version": self.contract_version,
            "composition_contract_version": self.composition_contract_version,
            "supported_ir_versions": list(self.supported_ir_versions),
            "canonical_object_model_implemented": self.canonical_object_model_implemented,
            "compiler_adapter_implemented": self.compiler_adapter_implemented,
            "hard_constraint_eligibility_implemented": self.hard_constraint_eligibility_implemented,
            "deterministic_replay_verified": self.deterministic_replay_verified,
            "deterministic_ranking_implemented": self.deterministic_ranking_implemented,
            "agent_ranking_implemented": self.agent_ranking_implemented,
            "team_composition_implemented": self.team_composition_implemented,
            "permission_bound_proposal_implemented": self.permission_bound_proposal_implemented,
            "fallback_planning_implemented": self.fallback_planning_implemented,
            "agent_team_plan_implemented": self.agent_team_plan_implemented,
            "permission_assignment_implemented": self.permission_assignment_implemented,
            "permission_granting_implemented": self.permission_granting_implemented,
            "runtime_handoff_implemented": self.runtime_handoff_implemented,
            "runtime_execution_implemented": self.runtime_execution_implemented,
            "live_availability_implemented": self.live_availability_implemented,
            "h16_migration_implemented": self.h16_migration_implemented,
            "model_selection_integration_implemented": self.model_selection_integration_implemented,
            "h22_integration_implemented": self.h22_integration_implemented,
            "live_registry_implemented": self.live_registry_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "dependency_versions": dict(self.dependency_versions),
            "optional_integrations": dict(self.optional_integrations),
            "build_commit": self.build_commit,
        }


def version_info() -> VersionInfo:
    """Return structured distribution + product version and maturity metadata.

    The four P1 booleans are ``True`` because their gates pass in this build's
    shipped test suite. Every later-phase field is hard-coded ``False``.
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
        contract_version=CONTRACT_VERSION,
        composition_contract_version=COMPOSITION_CONTRACT_VERSION,
        supported_ir_versions=SUPPORTED_IR_VERSIONS,
        canonical_object_model_implemented=True,
        compiler_adapter_implemented=True,
        hard_constraint_eligibility_implemented=True,
        deterministic_replay_verified=True,
        # -- implemented in P2 --
        deterministic_ranking_implemented=True,
        agent_ranking_implemented=True,
        team_composition_implemented=True,
        permission_bound_proposal_implemented=True,
        fallback_planning_implemented=True,
        agent_team_plan_implemented=True,
        # -- explicitly NOT implemented --
        permission_assignment_implemented=False,
        permission_granting_implemented=False,
        runtime_handoff_implemented=False,
        runtime_execution_implemented=False,
        live_availability_implemented=False,
        h16_migration_implemented=False,
        model_selection_integration_implemented=False,
        h22_integration_implemented=False,
        live_registry_implemented=False,
        pilot_validated=False,
        production_certified=False,
        dependency_versions=deps,
        optional_integrations=integrations,
        build_commit=None,
    )


__all__ = [
    "__version__",
    "VERSION",
    "DISTRIBUTION_VERSION",
    "DISTRIBUTION_NAME",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "CONTRACT_VERSION",
    "COMPOSITION_CONTRACT_VERSION",
    "SUPPORTED_IR_VERSIONS",
    "VersionInfo",
    "version_info",
]
