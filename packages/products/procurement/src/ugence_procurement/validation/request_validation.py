"""Deterministic purchase-request validation (domain business rules).

Structural validation (required fields, positive quantities) is enforced by the
contracts themselves. This validator applies the additional *business* rules a
procurement domain wants checked before a request enters governance: a
non-trivial total and a registered supplier/budget when a registry is supplied.
It raises typed procurement errors.
"""

from __future__ import annotations

from typing import Optional

from ..errors import (
    BudgetNotKnownError,
    PurchaseRequestValidationError,
    SupplierNotKnownError,
)
from ..requests.contracts import PurchaseRequest


class ProcurementRequestValidator:
    """Validates a purchase request against domain business rules."""

    def __init__(
        self,
        *,
        known_suppliers: Optional[frozenset[str]] = None,
        known_budgets: Optional[frozenset[str]] = None,
    ) -> None:
        self._suppliers = known_suppliers
        self._budgets = known_budgets

    def validate(self, request: PurchaseRequest) -> None:
        if request.total_amount <= 0:
            raise PurchaseRequestValidationError(
                f"purchase request '{request.request_id}' has a non-positive total")
        if self._suppliers is not None and request.supplier.supplier_id not in self._suppliers:
            raise SupplierNotKnownError(
                f"supplier '{request.supplier.supplier_id}' is not registered")
        if self._budgets is not None and request.budget.budget_id not in self._budgets:
            raise BudgetNotKnownError(
                f"budget '{request.budget.budget_id}' is not registered")
