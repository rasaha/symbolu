"""Typed errors for the Provider Framework (application layer)."""

from __future__ import annotations


class ProviderError(Exception):
    """Base class for all provider-framework errors."""


class ProviderNotFoundError(ProviderError):
    """No registered provider matched the requested name/kind/capability."""


class ProviderConflictError(ProviderError):
    """A provider with the same name is already registered."""


class IncompatibleProviderVersionError(ProviderError):
    """A provider targets a kernel major version this framework does not support."""


class ProviderCapabilityError(ProviderError):
    """A provider was asked for a capability it does not declare."""


class ProviderResolutionError(ProviderError):
    """A provider-selection configuration could not be resolved."""


class ProviderLifecycleError(ProviderError):
    """A provider lifecycle operation (start/stop) failed or was misordered."""
