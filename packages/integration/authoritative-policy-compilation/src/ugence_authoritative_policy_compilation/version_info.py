"""Honest maturity metadata for the composition root.

The gates say what this package does and — as loudly — what it never does. A root
that orchestrates two authorities must never be mistaken for either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .version import __version__

DISTRIBUTION_NAME = "ugence-authoritative-policy-compilation"
PRODUCT_NAME = "Ugence Authoritative Policy Compilation"
CANONICAL_NAMESPACE = "ugence_authoritative_policy_compilation"


@dataclass(frozen=True)
class VersionInfo:
    distribution: str
    distribution_version: str
    product: str
    canonical_namespace: str
    # -- implemented --
    composition_root_implemented: bool
    derived_source_reference_implemented: bool
    body_digest_reverification_implemented: bool
    # -- explicit non-goals, permanent --
    authored_source_reference_accepted: bool
    issues_policy: bool
    revokes_policy: bool
    grants_approval: bool
    holds_key_material: bool
    policy_pack_builder_shipped: bool
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
            "composition_root_implemented": self.composition_root_implemented,
            "derived_source_reference_implemented": (
                self.derived_source_reference_implemented
            ),
            "body_digest_reverification_implemented": (
                self.body_digest_reverification_implemented
            ),
            "authored_source_reference_accepted": self.authored_source_reference_accepted,
            "issues_policy": self.issues_policy,
            "revokes_policy": self.revokes_policy,
            "grants_approval": self.grants_approval,
            "holds_key_material": self.holds_key_material,
            "policy_pack_builder_shipped": self.policy_pack_builder_shipped,
            "runtime_execution_implemented": self.runtime_execution_implemented,
            "pilot_validated": self.pilot_validated,
            "production_certified": self.production_certified,
            "dependencies": dict(self.dependencies),
        }


def version_info() -> VersionInfo:
    """Structured version and maturity metadata."""
    return VersionInfo(
        distribution=DISTRIBUTION_NAME,
        distribution_version=__version__,
        product=PRODUCT_NAME,
        canonical_namespace=CANONICAL_NAMESPACE,
        composition_root_implemented=True,
        derived_source_reference_implemented=True,
        body_digest_reverification_implemented=True,
        # Never: on the authoritative path a reference is derived, never authored.
        authored_source_reference_accepted=False,
        # Never: every authority act belongs to Policy Authority or to a human.
        issues_policy=False,
        revokes_policy=False,
        grants_approval=False,
        holds_key_material=False,
        # Ruling CR-2: families supply their own artifact-to-pack mapping.
        policy_pack_builder_shipped=False,
        runtime_execution_implemented=False,
        pilot_validated=False,
        production_certified=False,
        dependencies={
            "ugence-policy-authority": ">=0.1.0",
            "ugence-policy-workflow-compiler": ">=0.2.0",
        },
    )


__all__ = ["VersionInfo", "version_info", "DISTRIBUTION_NAME", "CANONICAL_NAMESPACE"]
