"""
P12 - Acoustic-Prosodic Consistency Validator Pipeline Integration Module

Provides a thin shim for integrating P12 (Acoustic-Prosodic Consistency Validator)
into the Symbol-U pipeline. Called immediately after P11, before any downstream
speech realization.

P12 is an AUDIT-ONLY phase. It does NOT modify behavior.

Usage in orchestrator:
    from .p12_consistency.p12_integration import maybe_run_p12

    # After P11 stage
    maybe_run_p12(ctx)
    # ctx.p12_consistency is now set (or None if insufficient data)

Authority Model:
    - P12 consumes all upstream phase outputs (read-only)
    - P12 cannot mutate any upstream output
    - P12 cannot block, redirect, alter regime, or alter discourse
    - P12 produces P12ConsistencyReport (read-only, non-actuating)
    - Violations are reported upward, never corrected

CRITICAL: P12 is audit-only. It observes, validates, and reports
without modifying any data.

ARCHITECTURAL PRINCIPLE:
    P12 is not an intelligence layer.
    It is a truth-preserving audit layer that ensures Symbol-U
    never sounds more certain, forceful, or authoritative
    than it is allowed to be.
"""

from typing import Any, List, Optional

from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
    P12ConsistencyReport,
    P12Violation,
    P12Warning,
    ViolationSeverity,
    ViolationType,
)
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_validator import (
    P12ConsistencyValidator,
)


# Singleton P12 validator instance
_p12_validator: Optional[P12ConsistencyValidator] = None


def get_p12_validator() -> P12ConsistencyValidator:
    """Get or create the singleton P12 consistency validator instance."""
    global _p12_validator
    if _p12_validator is None:
        _p12_validator = P12ConsistencyValidator()
    return _p12_validator


def maybe_run_p12(ctx: Any) -> Any:
    """
    Run P12 consistency validation on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P12 requires P10 to be present for validation.

    IMPORTANT: This function attaches the result to ctx.p12_consistency.
    It returns the context unchanged (for chaining).

    CRITICAL: P12 is audit-only. It cannot block, redirect, alter regime,
    or alter discourse. It only observes, validates, and reports.

    Rules:
    - If ctx.p12_consistency already exists -> return ctx unchanged
    - If P10 is not available -> set ctx.p12_consistency = None
    - Attach P12ConsistencyReport to ctx.p12_consistency
    - Must not alter upstream behavior
    - Never raises - returns None on any error

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        The same context object (for chaining).
    """
    # Rule 1: If P12 already ran, don't run again
    if hasattr(ctx, 'p12_consistency') and ctx.p12_consistency is not None:
        return ctx

    # Run P12 validator
    try:
        validator = get_p12_validator()
        report = validator.validate(ctx)

        # Attach to context (may be None if insufficient data)
        ctx.p12_consistency = report
    except Exception:
        # Fail-closed: on any error, set to None
        ctx.p12_consistency = None

    return ctx


def run_p12_directly(ctx: Any) -> Optional[P12ConsistencyReport]:
    """
    Run P12 directly with explicit context.

    Useful for testing or standalone consistency validation.

    CRITICAL: The report is observational only. It cannot
    modify behavior or correct violations.

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        P12ConsistencyReport with validation results, or None if insufficient data.
    """
    validator = get_p12_validator()
    return validator.validate(ctx)


def get_p12_consistency_report(ctx: Any) -> Optional[P12ConsistencyReport]:
    """
    Get the P12 consistency report from context.

    Args:
        ctx: Pipeline context.

    Returns:
        P12ConsistencyReport or None if not available.
    """
    if not hasattr(ctx, 'p12_consistency'):
        return None
    return ctx.p12_consistency


def is_consistent(ctx: Any) -> bool:
    """
    Check if the pipeline context is consistent (no violations).

    Args:
        ctx: Pipeline context.

    Returns:
        True if consistent, False otherwise.
        Returns True (conservative) if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return True  # Conservative: assume consistent if not validated
    return report.is_consistent


def has_violations(ctx: Any) -> bool:
    """
    Check if any violations were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if violations detected, False otherwise.
        Returns False if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return False
    return report.has_violations()


def has_critical_violations(ctx: Any) -> bool:
    """
    Check if any CRITICAL violations were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if CRITICAL violations detected, False otherwise.
        Returns False if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return False
    return report.has_critical_violations()


def has_major_violations(ctx: Any) -> bool:
    """
    Check if any MAJOR violations were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if MAJOR violations detected, False otherwise.
        Returns False if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return False
    return report.has_major_violations()


def has_warnings(ctx: Any) -> bool:
    """
    Check if any warnings were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if warnings detected, False otherwise.
        Returns False if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return False
    return report.has_warnings()


def get_violations(ctx: Any) -> List[P12Violation]:
    """
    Get all violations from the consistency report.

    Args:
        ctx: Pipeline context.

    Returns:
        List of violations, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return list(report.violations)


def get_critical_violations(ctx: Any) -> List[P12Violation]:
    """
    Get all CRITICAL violations from the consistency report.

    Args:
        ctx: Pipeline context.

    Returns:
        List of CRITICAL violations, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return report.get_critical_violations()


def get_major_violations(ctx: Any) -> List[P12Violation]:
    """
    Get all MAJOR violations from the consistency report.

    Args:
        ctx: Pipeline context.

    Returns:
        List of MAJOR violations, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return report.get_major_violations()


def get_warnings(ctx: Any) -> List[P12Warning]:
    """
    Get all warnings from the consistency report.

    Args:
        ctx: Pipeline context.

    Returns:
        List of warnings, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return list(report.warnings)


def get_violations_by_type(ctx: Any, violation_type: ViolationType) -> List[P12Violation]:
    """
    Get violations filtered by type.

    Args:
        ctx: Pipeline context.
        violation_type: The type of violations to filter.

    Returns:
        List of violations of the specified type, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return report.get_violations_by_type(violation_type)


def get_violations_by_severity(ctx: Any, severity: ViolationSeverity) -> List[P12Violation]:
    """
    Get violations filtered by severity.

    Args:
        ctx: Pipeline context.
        severity: The severity level to filter.

    Returns:
        List of violations of the specified severity, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return report.get_violations_by_severity(severity)


def get_checked_invariants(ctx: Any) -> List[str]:
    """
    Get list of invariants that were checked.

    Args:
        ctx: Pipeline context.

    Returns:
        List of invariant names, or empty list if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return []
    return list(report.checked_invariants)


def get_audit_notes(ctx: Any) -> Optional[dict]:
    """
    Get audit notes from the consistency report.

    Args:
        ctx: Pipeline context.

    Returns:
        Dictionary of audit notes, or None if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return None
    return dict(report.audit_notes)


def violation_count(ctx: Any) -> int:
    """
    Get total number of violations.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of violations, or 0 if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return 0
    return report.violation_count()


def warning_count(ctx: Any) -> int:
    """
    Get total number of warnings.

    Args:
        ctx: Pipeline context.

    Returns:
        Number of warnings, or 0 if P12 hasn't run.
    """
    report = get_p12_consistency_report(ctx)
    if report is None:
        return 0
    return report.warning_count()


__all__ = [
    # Core functions
    "get_p12_validator",
    "maybe_run_p12",
    "run_p12_directly",
    "get_p12_consistency_report",
    # Consistency accessors
    "is_consistent",
    "has_violations",
    "has_critical_violations",
    "has_major_violations",
    "has_warnings",
    # Violation accessors
    "get_violations",
    "get_critical_violations",
    "get_major_violations",
    "get_warnings",
    "get_violations_by_type",
    "get_violations_by_severity",
    # Metadata accessors
    "get_checked_invariants",
    "get_audit_notes",
    # Count accessors
    "violation_count",
    "warning_count",
]
