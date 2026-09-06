"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class VendorDependencyError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(VendorDependencyError, ValueError):
    """A caller supplied structurally invalid or mismatched input.

    A naive datetime, a blank reference, a wrong type, a look-alike binding or
    label, a chosen rather than derived id, or a tenant that disagrees with the
    binding's tenant.
    """


class DeclarationSupersessionError(VendorDependencyError, ValueError):
    """A superseding declaration is inadmissible.

    It names no predecessor, crosses a tenant, concerns a different vendor, or
    re-declares exactly what the predecessor already declared — an unchanged
    declaration has nothing to supersede.
    """


class DeclarationStorageError(VendorDependencyError, RuntimeError):
    """The durable declarations file could not be opened, read or written (FD-13.2)."""


class DeclarationProductionModeError(DeclarationStorageError):
    """A non-durable location (in memory, a URI) was refused in production mode."""


class DuplicateDeclarationError(VendorDependencyError, ValueError):
    """A declaration with this derived id is already recorded; records are never edited."""


class CrossTenantRefused(VendorDependencyError, ValueError):
    """A read or write named a tenant other than the one this file is bound to."""
