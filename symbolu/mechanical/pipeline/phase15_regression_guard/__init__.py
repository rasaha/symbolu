"""
DEPRECATED: phase15_regression_guard has been renamed to p15_authority_guard.

This module is a backward-compatibility shim that re-exports all symbols
from the new location. Please update your imports to use:

    from symbolu.mechanical.pipeline.p15_authority_guard import (
        P15AuthoritySnapshot,
        P15RegressionViolation,
        P15RegressionViolationError,
        ViolationType,
        P15RegressionGuard,
        capture_p15_snapshot,
        enforce_p15_regression_guard,
        get_p15_snapshot,
        has_p15_snapshot,
    )

This shim will be maintained for backward compatibility but the canonical
location is now symbolu.mechanical.pipeline.p15_authority_guard.
"""

import warnings

# Issue a deprecation warning on import
warnings.warn(
    "phase15_regression_guard is deprecated and has been renamed to p15_authority_guard. "
    "Please update your imports to use 'from symbolu.mechanical.pipeline.p15_authority_guard import ...'",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from symbolu.mechanical.pipeline.p15_authority_guard import (
    # Schema
    P15AuthoritySnapshot,
    P15RegressionViolation,
    P15RegressionViolationError,
    ViolationType,
    # Guard
    P15RegressionGuard,
    # Integration
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
