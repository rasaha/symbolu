"""
P15 Authority Guard — Authority Preservation Layer

Phase: P15 (Authority Guard)
Authority: HIGH
observer_only: False
Determinism: yes

This module enforces the architectural invariant that no phase >= 16 may
modify, reinterpret, escalate, or override any decision produced by PO1-P15.

P15 is the LAST authority-bearing phase. All subsequent phases are READ-ONLY
with respect to:
- Intent inference
- Regime selection
- Discourse act resolution
- Response posture
- Allowed action contracts
- Blocked state

This guard is:
- Structural: enforced by code, not configuration
- Deterministic: same input -> same violations
- Non-bypassable: violations raise exceptions, not warnings

Design Principles:
- Immutable snapshots capture P15 authority decisions
- No hidden state
- No LLM usage
- No heuristics
- No learning
- No auto-correction

The guard exists to STOP the system, not to FIX it.

NOTE: This module was renamed from phase15_regression_guard to p15_authority_guard
to eliminate naming confusion with p15_interaction (the actual P15 phase).
A backward-compatibility shim exists at the old path.
"""

from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_regression_schema import (
    P15AuthoritySnapshot,
    P15RegressionViolation,
    P15RegressionViolationError,
    ViolationType,
)
from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_regression_guard import (
    P15RegressionGuard,
)
from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_integration import (
    capture_p15_snapshot,
    enforce_p15_regression_guard,
    get_p15_snapshot,
    has_p15_snapshot,
)


__all__ = [
    # Schema
    "P15AuthoritySnapshot",
    "P15RegressionViolation",
    "P15RegressionViolationError",
    "ViolationType",
    # Guard
    "P15RegressionGuard",
    # Integration
    "capture_p15_snapshot",
    "enforce_p15_regression_guard",
    "get_p15_snapshot",
    "has_p15_snapshot",
]
