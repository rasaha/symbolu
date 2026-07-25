"""Procurement request contracts — domain-specific evidence.

These model a *purchase request* and its constituent evidence. They are
procurement-specific and never seen by the kernel: the governance kernel links
to a *finalized assessment* through the neutral ``LinkedRecordPort`` and never
interprets purchase-request content.

Contracts subclass the kernel's domain-neutral ``DomainModel`` (a frozen,
extra-forbidding pydantic base) — reuse of a neutral utility, not duplication of
a kernel governance contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, model_validator

from decision_governance.api.common import DomainModel, utc_now
from decision_governance.api.errors import DomainValidationError


class Urgency(str, Enum):
    ROUTINE = "ROUTINE"
    EXPEDITED = "EXPEDITED"
    EMERGENCY = "EMERGENCY"


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    WITHDRAWN = "WITHDRAWN"


class SupplierReference(DomainModel):
    """A reference to a known supplier (procurement-specific)."""

    supplier_id: str
    name: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "SupplierReference":
        if not self.supplier_id.strip():
            raise DomainValidationError("supplier_id is required")
        return self


class BudgetReference(DomainModel):
    """A reference to a budget line the purchase draws against."""

    budget_id: str
    available_amount: int = 0  # minor units (e.g. cents); domain-defined

    @model_validator(mode="after")
    def _validate(self) -> "BudgetReference":
        if not self.budget_id.strip():
            raise DomainValidationError("budget_id is required")
        if self.available_amount < 0:
            raise DomainValidationError("available_amount cannot be negative")
        return self


class PurchaseItem(DomainModel):
    """A single line item on a purchase request."""

    description: str
    quantity: int
    unit_cost: int  # minor units

    @model_validator(mode="after")
    def _validate(self) -> "PurchaseItem":
        if not self.description.strip():
            raise DomainValidationError("item description is required")
        if self.quantity <= 0:
            raise DomainValidationError("quantity must be positive")
        if self.unit_cost < 0:
            raise DomainValidationError("unit_cost cannot be negative")
        return self

    @property
    def line_total(self) -> int:
        return self.quantity * self.unit_cost


class PurchaseRequest(DomainModel):
    """A purchase request — the procurement domain's primary evidence record."""

    request_id: str
    tenant_id: str
    requester: str
    supplier: SupplierReference
    items: tuple[PurchaseItem, ...]
    budget: BudgetReference
    justification: str = ""
    urgency: Urgency = Urgency.ROUTINE
    attached_document_ids: tuple[str, ...] = ()
    version: int = 1
    status: RequestStatus = RequestStatus.SUBMITTED
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _validate(self) -> "PurchaseRequest":
        if not self.request_id.strip():
            raise DomainValidationError("request_id is required")
        if not self.tenant_id.strip():
            raise DomainValidationError("tenant_id is required")
        if not self.requester.strip():
            raise DomainValidationError("requester is required")
        if not self.items:
            raise DomainValidationError("a purchase request needs at least one item")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        return self

    @property
    def total_amount(self) -> int:
        return sum(item.line_total for item in self.items)
