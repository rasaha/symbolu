"""The one read-only Protocol, and the pure selectors over what it returns.

CE-2 allows this package a record type, refusal reasons, pure selectors and **one
read-only Protocol** — the shape seams 5, 8 and 9 proved. The Protocol below is
that one. It is a port and nothing else: this package supplies no implementation,
so nothing here can open a file, hold a connection or reach a network.

Note what the Protocol does **not** have: no ``put``, no ``record``, no ``accept``.
CE-5 rules that export is a read, and §13.3 restates it — no operation may accept a
receipt. A port with a write method would make that a matter of discipline; a port
without one makes it structural.
"""

from __future__ import annotations

from typing import Optional, Protocol, Sequence, runtime_checkable

from ugence_action_clearance import ClearanceReceiptBody

from .errors import ContractViolation

__all__ = [
    "ReceivedClearanceSource",
    "select_for_tenant",
    "select_by_receipt_id",
]


@runtime_checkable
class ReceivedClearanceSource(Protocol):
    """Read access to clearance receipts a deployment already holds.

    Two reads, both by identity, both scoped by tenant. Whoever implements this
    owns the storage; this package never does.
    """

    def read_receipt(
        self, *, tenant_id: str, receipt_id: str
    ) -> Optional[ClearanceReceiptBody]:
        """One receipt, or ``None``. Never raises for an unknown id."""

    def list_receipt_ids(self, *, tenant_id: str) -> Sequence[str]:
        """The receipt ids this source holds for one tenant."""


def select_by_receipt_id(
    receipts: Sequence[ClearanceReceiptBody], receipt_id: str
) -> Optional[ClearanceReceiptBody]:
    """The receipt with this id, or ``None``. Pure."""

    if not isinstance(receipt_id, str) or not receipt_id.strip():
        raise ContractViolation("receipt_id must be a non-empty string")
    wanted = receipt_id.strip()
    for receipt in receipts:
        if receipt.receipt_id == wanted:
            return receipt
    return None


def select_for_tenant(
    receipts: Sequence[ClearanceReceiptBody], tenant_id: str
) -> tuple[ClearanceReceiptBody, ...]:
    """Every receipt bound to this tenant, in the order given. Pure.

    Tenant scoping is a filter here, not a permission: this selects what a caller
    was already handed and grants no access to anything it was not.
    """

    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation("tenant_id must be a non-empty string")
    wanted = tenant_id.strip()
    return tuple(r for r in receipts if r.tenant_id == wanted)
