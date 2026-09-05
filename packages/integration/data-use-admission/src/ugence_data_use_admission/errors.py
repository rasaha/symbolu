"""Typed errors. Every one is a *refusal*; none is ever promoted to a permission."""

from __future__ import annotations


class DataUseAdmissionError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(DataUseAdmissionError, ValueError):
    """A caller supplied structurally invalid or mismatched input.

    A naive datetime, a blank reference, a wrong type, a look-alike binding or
    label, a chosen rather than derived id, or a tenant that disagrees with the
    binding's tenant.
    """


class DeclarationSupersessionError(DataUseAdmissionError, ValueError):
    """A superseding declaration is inadmissible.

    It names no predecessor, crosses a tenant, concerns different data, or
    re-declares exactly what the predecessor already declared — an unchanged
    declaration has nothing to supersede.
    """
