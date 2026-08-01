"""Provider-framework error taxonomy.

Errors are normalized at adapter boundaries: an arbitrary vendor exception must
never leak into DGM services or domain applications. Each error carries a
:class:`FailureClass` so callers can react (retry / give up / treat as
indeterminate / fix configuration).
"""

from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    RETRYABLE = "RETRYABLE"
    TERMINAL = "TERMINAL"
    INDETERMINATE = "INDETERMINATE"
    CONFIGURATION = "CONFIGURATION"
    COMPATIBILITY = "COMPATIBILITY"


class ProviderError(Exception):
    """Base class for all provider-framework errors."""

    failure_class: FailureClass = FailureClass.TERMINAL


class ProviderRegistrationError(ProviderError):
    failure_class = FailureClass.CONFIGURATION


class ProviderResolutionError(ProviderError):
    failure_class = FailureClass.CONFIGURATION


class ProviderCompatibilityError(ProviderError):
    failure_class = FailureClass.COMPATIBILITY


class ProviderConfigurationError(ProviderError):
    failure_class = FailureClass.CONFIGURATION


class ProviderUnavailableError(ProviderError):
    failure_class = FailureClass.RETRYABLE


class ProviderTimeoutError(ProviderError):
    failure_class = FailureClass.RETRYABLE


class ProviderProtocolError(ProviderError):
    failure_class = FailureClass.TERMINAL


class ProviderResultValidationError(ProviderError):
    failure_class = FailureClass.TERMINAL


__all__ = [
    "FailureClass",
    "ProviderError",
    "ProviderRegistrationError",
    "ProviderResolutionError",
    "ProviderCompatibilityError",
    "ProviderConfigurationError",
    "ProviderUnavailableError",
    "ProviderTimeoutError",
    "ProviderProtocolError",
    "ProviderResultValidationError",
]
