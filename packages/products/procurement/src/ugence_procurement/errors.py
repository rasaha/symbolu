"""Procurement-domain error taxonomy.

Procurement errors derive from the kernel's :class:`GovernanceError` base (via the
``ProcurementError`` alias), so they share one root with kernel governance errors
and never subclass ``ValueError`` — a domain error raised inside a validator
propagates as-is. These are procurement-specific; the neutral governance-chain
error families remain owned by the kernel (``decision_governance.errors``).
"""

from __future__ import annotations

from ugence_decision_authority.api.errors import DomainValidationError, GovernanceError

ProcurementError = GovernanceError


class PurchaseRequestValidationError(ProcurementError):
    """A purchase request failed domain validation."""


class AssessmentNotFinalizedError(ProcurementError):
    """An operation required a finalized policy assessment; none was found."""


class SupplierNotKnownError(ProcurementError):
    """A referenced supplier is not registered in the procurement configuration."""


class BudgetNotKnownError(ProcurementError):
    """A referenced budget is not registered in the procurement configuration."""


__all__ = [
    "ProcurementError",
    "DomainValidationError",
    "PurchaseRequestValidationError",
    "AssessmentNotFinalizedError",
    "SupplierNotKnownError",
    "BudgetNotKnownError",
]
