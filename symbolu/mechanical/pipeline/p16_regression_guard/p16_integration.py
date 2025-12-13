"""
P16 Regression Guard — Integration Module

This module provides the integration functions for using the P16 Regression Guard
within the pipeline:

- maybe_run_p16_guard_pre(ctx): Capture snapshot before P16 work
- maybe_run_p16_guard_post(ctx, snapshot): Verify invariants after P16 work
- is_p16_enabled(ctx): Check if P16 guard is enabled

Usage in pipeline:
    # Before P16 work:
    snapshot, contract = maybe_run_p16_guard_pre(ctx)

    # ... P16 work happens ...

    # After P16 work:
    maybe_run_p16_guard_post(ctx, snapshot)  # Raises on violation

DESIGN PRINCIPLES:
- Guard is DEFAULT ON for tests
- Snapshot captured ONCE before P16 work
- Violations raise P16ContractViolationError (deterministic, non-bypassable)
- No auto-correction, no silent failure
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from symbolu.mechanical.pipeline.p16_regression_guard.p16_contract_schema import (
    ContractViolation,
    HashSnapshot,
    P16ContractViolationError,
    P16GuardResult,
    P16InputContract,
)
from symbolu.mechanical.pipeline.p16_regression_guard.p16_regression_guard import (
    P16RegressionGuard,
)


# ============================================================================
# MODULE-LEVEL GUARD INSTANCE
# ============================================================================


# Single, stateless guard instance for use throughout the pipeline
_guard = P16RegressionGuard()

# Default contract
_default_contract = P16InputContract()


# ============================================================================
# CONFIGURATION
# ============================================================================


# Attribute name used to store the snapshot on the context
_SNAPSHOT_ATTR = "_p16_snapshot"
_CONTRACT_ATTR = "_p16_contract"
_GUARD_RESULT_ATTR = "p16_guard_result"

# Configuration flag (can be overridden per-context)
_P16_ENABLED_DEFAULT = True


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def is_p16_enabled(ctx: Any) -> bool:
    """
    Check if P16 guard is enabled for this context.

    The guard can be disabled per-context by setting ctx._p16_disabled = True.
    By default, the guard is ENABLED.

    Args:
        ctx: The PipelineContext

    Returns:
        True if guard is enabled, False otherwise
    """
    # Check for explicit disable flag
    if getattr(ctx, "_p16_disabled", False):
        return False

    # Check for environment-based disable
    if getattr(ctx, "_p16_enabled", None) is False:
        return False

    return _P16_ENABLED_DEFAULT


def maybe_run_p16_guard_pre(
    ctx: Any,
    contract: Optional[P16InputContract] = None,
) -> Tuple[Optional[HashSnapshot], P16InputContract]:
    """
    Capture the P16 snapshot before P16 work begins.

    This function MUST be called before any P16 work is performed.
    The snapshot is stored as an attribute on the context object.

    Args:
        ctx: The PipelineContext (after P15 has completed)
        contract: Optional custom contract (defaults to P16InputContract())

    Returns:
        Tuple of (snapshot, contract). Snapshot is None if guard is disabled.

    Side Effects:
        Adds _p16_snapshot and _p16_contract attributes to ctx
    """
    if contract is None:
        contract = _default_contract

    # Check if guard is enabled
    if not is_p16_enabled(ctx):
        return (None, contract)

    # Capture the snapshot
    snapshot = _guard.snapshot(ctx, contract)

    # Store on context
    setattr(ctx, _SNAPSHOT_ATTR, snapshot)
    setattr(ctx, _CONTRACT_ATTR, contract)

    return (snapshot, contract)


def maybe_run_p16_guard_post(
    ctx: Any,
    snapshot: Optional[HashSnapshot] = None,
    contract: Optional[P16InputContract] = None,
) -> Optional[P16GuardResult]:
    """
    Validate the P16 regression guard after P16 work completes.

    This function MUST be called after P16 work is performed.
    If any violations are detected, it raises P16ContractViolationError.

    Args:
        ctx: The PipelineContext after P16 work
        snapshot: Optional snapshot (defaults to stored snapshot on ctx)
        contract: Optional contract (defaults to stored contract on ctx)

    Returns:
        P16GuardResult if validation was performed, None if guard disabled

    Raises:
        P16ContractViolationError: If any violations are detected
        RuntimeError: If snapshot was not captured (missing snapshot)
    """
    # Check if guard is enabled
    if not is_p16_enabled(ctx):
        return None

    # Get snapshot (from args or context)
    if snapshot is None:
        snapshot = get_p16_snapshot(ctx)

    if snapshot is None:
        raise RuntimeError(
            "P16 snapshot not found. "
            "maybe_run_p16_guard_pre() must be called before P16 work."
        )

    # Get contract (from args or context)
    if contract is None:
        contract = getattr(ctx, _CONTRACT_ATTR, _default_contract)

    # Validate
    result = _guard.validate(ctx, snapshot, contract)

    # Store result on context
    setattr(ctx, _GUARD_RESULT_ATTR, result)

    # If violations, raise deterministic exception
    if not result.passed:
        raise P16ContractViolationError(
            violations=list(result.violations),
        )

    return result


# ============================================================================
# SNAPSHOT ACCESS FUNCTIONS
# ============================================================================


def get_p16_snapshot(ctx: Any) -> Optional[HashSnapshot]:
    """
    Get the P16 snapshot from the context.

    Args:
        ctx: The PipelineContext

    Returns:
        The HashSnapshot if it exists, None otherwise
    """
    return getattr(ctx, _SNAPSHOT_ATTR, None)


def has_p16_snapshot(ctx: Any) -> bool:
    """
    Check if the context has a P16 snapshot.

    Args:
        ctx: The PipelineContext

    Returns:
        True if snapshot exists, False otherwise
    """
    return get_p16_snapshot(ctx) is not None


def get_p16_contract(ctx: Any) -> P16InputContract:
    """
    Get the P16 contract from the context.

    Args:
        ctx: The PipelineContext

    Returns:
        The P16InputContract (stored or default)
    """
    return getattr(ctx, _CONTRACT_ATTR, _default_contract)


def get_p16_guard_result(ctx: Any) -> Optional[P16GuardResult]:
    """
    Get the P16 guard result from the context.

    Args:
        ctx: The PipelineContext

    Returns:
        The P16GuardResult if validation was performed, None otherwise
    """
    return getattr(ctx, _GUARD_RESULT_ATTR, None)


# ============================================================================
# DIAGNOSTIC FUNCTIONS
# ============================================================================


def validate_p16_without_raise(
    ctx: Any,
    snapshot: Optional[HashSnapshot] = None,
    contract: Optional[P16InputContract] = None,
) -> Optional[P16GuardResult]:
    """
    Validate the P16 regression guard without raising an exception.

    This is useful for testing and diagnostic purposes where you want
    to inspect violations without halting execution.

    Args:
        ctx: The PipelineContext
        snapshot: Optional snapshot (defaults to stored snapshot on ctx)
        contract: Optional contract (defaults to stored contract on ctx)

    Returns:
        P16GuardResult with all violations, or None if guard disabled
    """
    if not is_p16_enabled(ctx):
        return None

    if snapshot is None:
        snapshot = get_p16_snapshot(ctx)

    if snapshot is None:
        return None

    if contract is None:
        contract = getattr(ctx, _CONTRACT_ATTR, _default_contract)

    return _guard.validate(ctx, snapshot, contract)


def get_violations(ctx: Any) -> List[ContractViolation]:
    """
    Get violations from the stored P16 guard result.

    Args:
        ctx: The PipelineContext

    Returns:
        List of violations, or empty list if no result
    """
    result = get_p16_guard_result(ctx)
    if result is None:
        return []
    return list(result.violations)


# ============================================================================
# DIRECT GUARD ACCESS (FOR TESTING)
# ============================================================================


def get_guard() -> P16RegressionGuard:
    """
    Get the module-level guard instance.

    Primarily for testing purposes.

    Returns:
        The P16RegressionGuard instance
    """
    return _guard


def capture_snapshot_directly(
    ctx: Any,
    contract: Optional[P16InputContract] = None,
) -> HashSnapshot:
    """
    Capture a snapshot without storing it on the context.

    Primarily for testing purposes.

    Args:
        ctx: The PipelineContext
        contract: Optional contract

    Returns:
        HashSnapshot
    """
    if contract is None:
        contract = _default_contract
    return _guard.snapshot(ctx, contract)


def assert_unchanged_directly(
    ctx: Any,
    snapshot: HashSnapshot,
    contract: Optional[P16InputContract] = None,
) -> List[ContractViolation]:
    """
    Assert unchanged directly without raising an exception.

    Primarily for testing purposes.

    Args:
        ctx: The PipelineContext
        snapshot: The HashSnapshot
        contract: Optional contract

    Returns:
        List of ContractViolation objects
    """
    if contract is None:
        contract = _default_contract
    return _guard.assert_unchanged(ctx, snapshot, contract)


def enforce_allowlist_directly(
    ctx: Any,
    written_paths: set,
    contract: Optional[P16InputContract] = None,
    debug_before: Any = None,
    metrics_before: Any = None,
) -> List[ContractViolation]:
    """
    Enforce allowlist directly.

    Primarily for testing purposes.

    Args:
        ctx: The PipelineContext
        written_paths: Set of paths that were written to
        contract: Optional contract
        debug_before: Debug state before
        metrics_before: Metrics state before

    Returns:
        List of ContractViolation objects
    """
    if contract is None:
        contract = _default_contract
    return _guard.enforce_allowlist(
        ctx, written_paths, contract, debug_before, metrics_before
    )


# ============================================================================
# CONTEXT MANAGER (OPTIONAL PATTERN)
# ============================================================================


class P16GuardContext:
    """
    Context manager for P16 guard operations.

    Usage:
        with P16GuardContext(ctx) as guard_ctx:
            # P16 work here
            pass
        # Validation happens automatically on exit
    """

    def __init__(
        self,
        ctx: Any,
        contract: Optional[P16InputContract] = None,
    ) -> None:
        """Initialize context manager."""
        self.ctx = ctx
        self.contract = contract or _default_contract
        self.snapshot: Optional[HashSnapshot] = None
        self.result: Optional[P16GuardResult] = None

    def __enter__(self) -> "P16GuardContext":
        """Enter context: capture snapshot."""
        self.snapshot, self.contract = maybe_run_p16_guard_pre(
            self.ctx, self.contract
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Exit context: validate."""
        # Don't validate if an exception already occurred
        if exc_type is not None:
            return False

        self.result = maybe_run_p16_guard_post(
            self.ctx, self.snapshot, self.contract
        )
        return False


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Primary integration functions
    "maybe_run_p16_guard_pre",
    "maybe_run_p16_guard_post",
    "is_p16_enabled",
    # Snapshot access
    "get_p16_snapshot",
    "has_p16_snapshot",
    "get_p16_contract",
    "get_p16_guard_result",
    # Diagnostic functions
    "validate_p16_without_raise",
    "get_violations",
    # Testing helpers
    "get_guard",
    "capture_snapshot_directly",
    "assert_unchanged_directly",
    "enforce_allowlist_directly",
    # Context manager
    "P16GuardContext",
]
