"""Ugence Execution Reservation — durable receipts, atomic one-time reservation, and
the ``PRIOR_CONSUMPTION`` signal, as the durable backend of the Decision Authority
execution ledger.

    THIS PACKAGE RESERVES, RECORDS AND REPORTS CONSUMPTION.
    IT NEVER DISPATCHES, OBSERVES AN EXTERNAL SYSTEM, OR MINTS AUTHORITY.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_EXECUTION_RESERVATION_SCOPING.md``.
``CLEAR`` plus ``ACQUIRED`` is still not execution.
"""

from __future__ import annotations

from .consumption import (
    ADAPTER_ID,
    SOURCE_KIND,
    PriorConsumptionSource,
    build_consumption_signal,
    consumption_status_for,
)
from .errors import (
    ContractViolation,
    ExecutionReservationError,
    IllegalTransitionError,
    ProductionModeRefused,
    ReceiptIntegrityError,
    ReceiptNotFoundError,
    ReservationNotFoundError,
    StoreUnavailableError,
)
from .execution_key import EXECUTION_KEY_PREFIX, ExecutionKey
from .memory import InMemoryExecutionReservationStore
from .receipts import (
    ClearanceReceipt,
    ClearanceReceiptRepository,
    PutReceiptResult,
    ReceiptLifecycleEvent,
    ReceiptLifecycleState,
    RevocationResult,
    SupersessionResult,
    derive_lifecycle_state,
    receipt_validity,
    verify_receipt_body,
)
from .reservation import (
    ExecutionReservation,
    ExecutionReservationPort,
    ReconciledOutcome,
    ReservationEvent,
    ReservationResult,
    ReservationState,
    ReserveOnceOutcome,
    classify_head,
    validate_receipt_for_reservation,
)
from .sqlite import SCHEMA_VERSION, SqliteExecutionReservationStore
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED", "SCHEMA_VERSION",
    # key
    "ExecutionKey", "EXECUTION_KEY_PREFIX",
    # receipts (phase E)
    "ClearanceReceipt", "ClearanceReceiptRepository", "ReceiptLifecycleState",
    "ReceiptLifecycleEvent", "PutReceiptResult", "SupersessionResult", "RevocationResult",
    "verify_receipt_body", "receipt_validity", "derive_lifecycle_state",
    # reservation (phase G)
    "ExecutionReservation", "ExecutionReservationPort", "ReservationState", "ReservationResult",
    "ReconciledOutcome", "ReservationEvent", "ReserveOnceOutcome",
    "validate_receipt_for_reservation", "classify_head",
    # consumption signal
    "PriorConsumptionSource", "consumption_status_for", "build_consumption_signal",
    "ADAPTER_ID", "SOURCE_KIND",
    # adapters
    "InMemoryExecutionReservationStore", "SqliteExecutionReservationStore",
    # errors
    "ExecutionReservationError", "ContractViolation", "ReceiptIntegrityError",
    "ReceiptNotFoundError", "ReservationNotFoundError", "IllegalTransitionError",
    "StoreUnavailableError", "ProductionModeRefused",
]
