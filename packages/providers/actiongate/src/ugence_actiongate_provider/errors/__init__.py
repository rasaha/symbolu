"""Error translation — ActionGate native failures → framework provider errors.

No ActionGate exception may cross the provider boundary. This maps each native
failure to a classified framework ``ProviderError`` (which the control-plane
adapter then normalizes to a fail-safe ``INDETERMINATE`` authorization).
"""

from __future__ import annotations

from governance_providers.api import (
    ProviderConfigurationError,
    ProviderError,
    ProviderResultValidationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from ..core import (
    ActionGateConfigError,
    ActionGateError,
    ActionGateMalformedResponse,
    ActionGateTimeout,
    ActionGateUnavailable,
)

_MAP = {
    ActionGateConfigError: ProviderConfigurationError,
    ActionGateTimeout: ProviderTimeoutError,
    ActionGateMalformedResponse: ProviderResultValidationError,
    ActionGateUnavailable: ProviderUnavailableError,
}


def translate_error(exc: Exception) -> ProviderError:
    """Translate any ActionGate/native exception into a classified provider error."""
    for native, provider in _MAP.items():
        if isinstance(exc, native):
            return provider(f"actiongate: {exc}")
    if isinstance(exc, ActionGateError):
        # An unknown native failure → generic ProviderError (adapter → INDETERMINATE).
        return ProviderError(f"actiongate: {exc}")
    # A truly unexpected exception is still not allowed to leak as-is.
    return ProviderError(f"actiongate-unexpected: {type(exc).__name__}: {exc}")


__all__ = ["translate_error"]
