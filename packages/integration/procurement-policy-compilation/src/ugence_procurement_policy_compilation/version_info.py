"""Honest maturity metadata for the Procurement pack builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .version import __version__

DISTRIBUTION_NAME = "ugence-procurement-policy-compilation"
PRODUCT_NAME = "Ugence Procurement Policy Compilation"
CANONICAL_NAMESPACE = "ugence_procurement_policy_compilation"


@dataclass(frozen=True)
class VersionInfo:
    distribution: str
    distribution_version: str
    product: str
    canonical_namespace: str
    # -- implemented --
    procurement_pack_builder_implemented: bool
    deterministic_mapping_verified: bool
    source_declared_semantics_supported: bool
    # -- explicit non-goals --
    authors_authoritative_source: bool
    depends_on_policy_authority: bool
    infers_undeclared_policy: bool
    runtime_execution_implemented: bool
    pilot_validated: bool
    production_certified: bool
    dependencies: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "distribution": self.distribution,
            "distribution_version": self.distribution_version,
            "product": self.product,
            "canonical_namespace": self.canonical_namespace,
            "procurement_pack_builder_implemented": (
                self.procurement_pack_builder_implemented
            ),
            "deterministic_mapping_verified": self.deterministic_mapping_verified,
            "source_declared_semantics_supported": (
                self.source_declared_semantics_supported
            ),
            "authors_authoritative_source": self.authors_authoritative_source,
            "depends_on_policy_authority": self.depends_on_policy_authority,
            "infers_undeclared_policy": self.infers_undeclared_policy,
            "runtime_execution_implemented": self.runtime_execution_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "dependencies": dict(self.dependencies),
        }


def version_info() -> VersionInfo:
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=__version__,
        product=PRODUCT_NAME,
        canonical_namespace=CANONICAL_NAMESPACE,
        procurement_pack_builder_implemented=True,
        deterministic_mapping_verified=True,
        source_declared_semantics_supported=True,
        # Never: the composition root derives that reference from a resolution.
        authors_authoritative_source=False,
        # Never: this builder maps a typed artifact, not a resolution.
        depends_on_policy_authority=False,
        # Never: where the artifact is silent, the pack is silent.
        infers_undeclared_policy=False,
        runtime_execution_implemented=False,
        pilot_validated=False,
        production_certified=False,
        dependencies={"ugence-policy-workflow-compiler": ">=0.2.0"},
    )


__all__ = ["VersionInfo", "version_info", "DISTRIBUTION_NAME", "CANONICAL_NAMESPACE"]
