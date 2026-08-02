"""COMPATIBILITY-ONLY. Legacy path for provider metadata/descriptors.

Canonical: ``ugence_governance_contracts.metadata``. Re-exports the SAME objects
(identity preserved); no logic. Removal/review target: governance_providers 0.2.0.
"""
from ugence_governance_contracts.metadata import (  # noqa: F401
    ProviderKind,
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderHealth,
    ProviderDescriptor,
)
