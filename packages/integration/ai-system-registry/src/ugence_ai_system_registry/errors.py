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
