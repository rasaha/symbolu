"""Supplier dispatch/outcome vocabulary → kernel outcomes.

The supplier is the *external system* the governance execution phase dispatches
to. Procurement names its supplier outcomes (accepted / rejected / timed out /
unknown); these map onto the kernel's neutral ``BusinessOutcome`` /
``TransportStatus``. The kernel ``ExecutionRecord`` remains authoritative — a
transport acknowledgement is never a business outcome.
"""

from __future__ import annotations

from enum import Enum

from decision_governance.execution import BusinessOutcome, TransportStatus


class SupplierOutcome(str, Enum):
    """The observed business result from a supplier."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


# Supplier business outcome -> neutral kernel business outcome.
SUPPLIER_TO_BUSINESS: dict[SupplierOutcome, BusinessOutcome] = {
    SupplierOutcome.ACCEPTED: BusinessOutcome.SUCCEEDED,
    SupplierOutcome.REJECTED: BusinessOutcome.REJECTED,
    SupplierOutcome.TIMED_OUT: BusinessOutcome.UNKNOWN,
    SupplierOutcome.UNKNOWN: BusinessOutcome.UNKNOWN,
}


def business_outcome_for(outcome: SupplierOutcome) -> BusinessOutcome:
    return SUPPLIER_TO_BUSINESS[outcome]
