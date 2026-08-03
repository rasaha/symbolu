"""Procurement application configuration.

Deterministic, offline configuration for the in-memory procurement platform:
spending limits enforced by the budget-authority control plane, plus the
registered suppliers and budgets used for optional request validation. No
external systems, no secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProcurementConfiguration:
    """Tunable limits and registries for a procurement platform instance."""

    #: Purchases at or below this need no extra conditions.
    approval_threshold: int = 1_000_000
    #: Purchases above this are denied outright.
    hard_limit: int = 10_000_000
    #: Suppliers/budgets that are blocked at authorization.
    restricted_suppliers: frozenset[str] = frozenset()
    restricted_budgets: frozenset[str] = frozenset()
    #: Optional registries for domain request validation (None ⇒ skip the check).
    known_suppliers: frozenset[str] | None = None
    known_budgets: frozenset[str] | None = None
    #: Supplier action types that fail transport or time out (for testing paths).
    supplier_transport_failing: frozenset[str] = field(default_factory=frozenset)
    supplier_timing_out: frozenset[str] = field(default_factory=frozenset)


DEFAULT_CONFIGURATION = ProcurementConfiguration()
