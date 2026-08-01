"""COMPATIBILITY-ONLY. Legacy path for the provider error taxonomy.

Canonical: ``ugence_governance_contracts.errors``. Re-exports the SAME objects
(identity preserved); contains no logic. New code should import from the
canonical package. Removal/review target: governance_providers 0.2.0.
"""
from ugence_governance_contracts.errors import (  # noqa: F401
    FailureClass,
    ProviderError,
    ProviderRegistrationError,
    ProviderResolutionError,
    ProviderCompatibilityError,
    ProviderConfigurationError,
    ProviderUnavailableError,
    ProviderTimeoutError,
    ProviderProtocolError,
    ProviderResultValidationError,
    __all__,
)
