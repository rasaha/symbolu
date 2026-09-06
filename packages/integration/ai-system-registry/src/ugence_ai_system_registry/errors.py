"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class AiSystemRegistryError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(AiSystemRegistryError, ValueError):
    """A caller supplied structurally invalid input (naive datetime, blank id, wrong type)."""


class RegistrationSupersessionError(AiSystemRegistryError, ValueError):
    """A superseding registration is inadmissible.

    It names no predecessor, crosses a tenant, or binds the *same* system identity —
    a changed system is registered afresh, and an unchanged one never needs to be.
    """


class RegistryStorageError(AiSystemRegistryError, RuntimeError):
    """The durable registry could not be opened, read or written (FD-9.2)."""


class RegistryProductionModeError(RegistryStorageError):
    """A non-durable location (in memory, a URI) was refused in production mode."""


class DuplicateRegistrationError(AiSystemRegistryError, ValueError):
    """A registration with this derived id is already recorded; records are never edited."""


class CrossTenantRefused(AiSystemRegistryError, ValueError):
    """A read or write named a tenant other than the one this registry is bound to."""
