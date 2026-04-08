"""
Generative Containment Constraint (GCC) - C-1 Safety Module
============================================================

This module implements hard safety constraints ensuring Phases 1b-9
and Ontological Router R1 are permanently non-expressive.

The system is provably incapable of:
    - Free-form text generation
    - Semantic interpretation
    - Probabilistic or weighted selection
    - Accidental language assembly

All constraints are fail-closed and auditable.

Hard Invariants:
    - NO free-form string literals (>32 chars)
    - NO f-strings in constrained modules
    - NO regex/tokenizer/NLP imports
    - NO ML/generation libraries
    - ALL outputs must be non-expressive types only

Exports:
    - assert_non_expressive: Runtime guard for output validation
    - GCCViolationError: Exception for GCC violations
    - NonExpressiveValue: Type alias for valid return types
"""

from agentic.safety.gcc_runtime_guard import (
    assert_non_expressive,
    GCCViolationError,
    is_non_expressive,
    NonExpressiveValue,
    GCC_INVARIANTS,
)

from agentic.safety.gcc_ledger_invariant import (
    assert_ledger_entry_valid,
    LedgerInvariantViolation,
    ALLOWED_LEDGER_FIELDS,
)

__all__ = [
    # Runtime guard
    "assert_non_expressive",
    "GCCViolationError",
    "is_non_expressive",
    "NonExpressiveValue",
    "GCC_INVARIANTS",
    # Ledger invariant
    "assert_ledger_entry_valid",
    "LedgerInvariantViolation",
    "ALLOWED_LEDGER_FIELDS",
]
