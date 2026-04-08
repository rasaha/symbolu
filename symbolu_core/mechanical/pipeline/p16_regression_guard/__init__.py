"""
P16 Regression Guard — Input Contract + Regression Guard

A deterministic, non-LLM, non-authoritative layer that:
1. Defines an explicit P16InputContract describing what P16 may read
2. Produces a P16RegressionGuard that snapshots upstream authority objects
3. Enforces strict allow-list of what P16 may write
4. Detects mutations, authority drift, and contract violations

DESIGN PRINCIPLES:
- No external LLM calls
- Deterministic output (same input → same hashes)
- Immutable contracts and snapshots
- Explicit allow-lists for writes
- Fail-fast on violations

USAGE:
    from symbolu_core.mechanical.pipeline.p16_regression_guard import (
        maybe_run_p16_guard_pre,
        maybe_run_p16_guard_post,
    )

    # Before P16 work:
    snapshot, contract = maybe_run_p16_guard_pre(ctx)

    # ... P16 work happens ...

    # After P16 work:
    maybe_run_p16_guard_post(ctx, snapshot)  # Raises on violation
"""

from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_contract_schema import (
    # Version
    P16_VERSION,
    # Enums
    AuthorityScope,
    ViolationType,
    # Dataclasses
    ScopeHash,
    HashSnapshot,
    ContractViolation,
    P16InputContract,
    P16GuardResult,
    # Exception
    P16ContractViolationError,
)

from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_hashing import (
    stable_json,
    stable_hash,
    stable_hash_combine,
    extract_hashable_fields,
    hash_fields,
    validate_hash_unchanged,
    is_serializable,
)

from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_regression_guard import (
    P16RegressionGuard,
)

from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_integration import (
    # Primary integration functions
    maybe_run_p16_guard_pre,
    maybe_run_p16_guard_post,
    is_p16_enabled,
    # Snapshot access
    get_p16_snapshot,
    has_p16_snapshot,
    get_p16_contract,
    get_p16_guard_result,
    # Diagnostic functions
    validate_p16_without_raise,
    get_violations,
    # Testing helpers
    get_guard,
    capture_snapshot_directly,
    assert_unchanged_directly,
    enforce_allowlist_directly,
    # Context manager
    P16GuardContext,
)


__all__ = [
    # Version
    "P16_VERSION",
    # Enums
    "AuthorityScope",
    "ViolationType",
    # Dataclasses
    "ScopeHash",
    "HashSnapshot",
    "ContractViolation",
    "P16InputContract",
    "P16GuardResult",
    # Exception
    "P16ContractViolationError",
    # Hashing
    "stable_json",
    "stable_hash",
    "stable_hash_combine",
    "extract_hashable_fields",
    "hash_fields",
    "validate_hash_unchanged",
    "is_serializable",
    # Guard
    "P16RegressionGuard",
    # Integration
    "maybe_run_p16_guard_pre",
    "maybe_run_p16_guard_post",
    "is_p16_enabled",
    "get_p16_snapshot",
    "has_p16_snapshot",
    "get_p16_contract",
    "get_p16_guard_result",
    "validate_p16_without_raise",
    "get_violations",
    "get_guard",
    "capture_snapshot_directly",
    "assert_unchanged_directly",
    "enforce_allowlist_directly",
    "P16GuardContext",
]
