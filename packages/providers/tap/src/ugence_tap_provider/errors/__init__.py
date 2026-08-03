"""Error translation — TAP native failures → framework provider errors.

No TAP exception may cross the provider boundary. This maps each native failure
to a classified framework ``ProviderError``. The provider then either raises it
(when a caller performs its own normalization) or, in the default fail-safe mode,
converts it to an ``INDETERMINATE`` result. In no case does infrastructure
failure become SUPPORTED.

    invalid configuration        → ProviderConfigurationError
    protocol / version mismatch  → ProviderProtocolError
    engine unavailable           → ProviderUnavailableError
    evaluation deadline exceeded → ProviderTimeoutError
    malformed native result      → ProviderResultValidationError
    unexpected native failure    → ProviderError
"""

from __future__ import annotations

from governance_providers.api import (
    ProviderConfigurationError,
    ProviderError,
    ProviderProtocolError,
    ProviderResultValidationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from ..core import (
    TapConfigError,
    TapError,
    TapMalformedResult,
    TapProtocolError,
    TapTimeout,
    TapUnavailable,
)

_MAP = {
    TapConfigError: ProviderConfigurationError,
    TapProtocolError: ProviderProtocolError,
    TapTimeout: ProviderTimeoutError,
    TapMalformedResult: ProviderResultValidationError,
    TapUnavailable: ProviderUnavailableError,
}


def translate_error(exc: Exception) -> ProviderError:
    """Translate any TAP/native exception into a classified provider error."""
    for native, provider in _MAP.items():
        if isinstance(exc, native):
            return provider(f"tap: {exc}")
    if isinstance(exc, TapError):
        # An unknown native failure → generic ProviderError (fail-safe: INDETERMINATE).
        return ProviderError(f"tap: {exc}")
    # A truly unexpected exception is still not allowed to leak as-is.
    return ProviderError(f"tap-unexpected: {type(exc).__name__}: {exc}")


__all__ = ["translate_error"]
