"""
P11B Verifier - Structural Verification for Phase-11B Output
==============================================================

This module provides structural verification for Phase-11B rendered output.

Phase-11B Template Patterns:
    - [FAMILY:XXX][VARIANT:YYY] ... - Family and variant prefix
    - Family-VC-N: {data} - Family-prefixed VC slots
    - No [PPV:N] suffix in Phase-11B (PPV is routed via variant)

Verification Rules:
    - Line-by-line structural verification
    - Forbidden vocabulary scan
    - Template shape enforcement (Phase-11B patterns)
    - Length constraints
    - Produces verifier_passed: bool
    - Produces verifier_report_hash

Hard Constraints:
    - MUST be deterministic (same input -> same output)
    - NO ML/NLP imports
    - NO randomness
    - NO time/datetime
    - NO semantic interpretation
    - NO scoring or ranking
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Tuple

from symbolu.mechanical.pipeline.p11b_controller.p11b_templates import P11BRenderResult


# =============================================================================
# Version Constant
# =============================================================================

P11B_VERIFIER_VERSION = "1.0.0"


# =============================================================================
# Forbidden Vocabulary
# =============================================================================

_FORBIDDEN_VOCABULARY: Tuple[str, ...] = (
    # Safety-critical terms
    "ABSOLVING",
    "OVERRIDE",
    "BYPASS",
    "IGNORE_SAFETY",
    "SKIP_VERIFICATION",
    # Generative markers
    "GENERATE_FREE",
    "UNCONSTRAINED",
    "FREE_FORM",
    "UNBOUNDED",
    # System internals
    "__INTERNAL__",
    "__SYSTEM__",
    "__DEBUG__",
    "__ADMIN__",
    # Injection markers
    "<script>",
    "</script>",
    "javascript:",
    "data:text",
)

MAX_LINE_LENGTH = 1000
MAX_OUTPUT_LENGTH = 10000


# =============================================================================
# Phase-11B Template Shape Patterns
# =============================================================================

# Valid Phase-11B template shapes (regex patterns)
_VALID_P11B_SHAPES: Tuple[re.Pattern, ...] = (
    # [FAMILY:XXX][VARIANT:YYY] - standard family/variant prefix
    re.compile(r"^\[FAMILY:[A-Z_]+\]\[VARIANT:[A-Z_]+\].*$"),
    # [FAMILY:XXX][VARIANT:YYY][FALLBACK] - fallback template
    re.compile(r"^\[FAMILY:[A-Z_]+\]\[VARIANT:[A-Z_]+\]\[FALLBACK\].*$"),
    # Any output starting with [FAMILY:
    re.compile(r"^\[FAMILY:[A-Z_]+\].*$"),
    # Also accept [REGIME:xxx] for backwards compatibility
    re.compile(r"^\[REGIME:[a-z]+\].*$"),
)


# =============================================================================
# Verification Dataclasses
# =============================================================================


@dataclass(frozen=True)
class P11BVerificationCheck:
    """
    Result of a single verification check.

    Attributes:
        check_name: Name of the check
        passed: Whether the check passed
        details: Optional details about the check result
    """
    check_name: str
    passed: bool
    details: str = ""


@dataclass(frozen=True)
class P11BVerifierReport:
    """
    Complete verification report for Phase-11B output.

    Attributes:
        passed: Whether ALL checks passed
        checks: Tuple of individual check results
        report_hash: Deterministic hash of the report
    """
    passed: bool
    checks: Tuple[P11BVerificationCheck, ...]
    report_hash: str

    def __post_init__(self) -> None:
        """Validate P11BVerifierReport invariants."""
        if not isinstance(self.passed, bool):
            raise ValueError("P11BVerifierReport.passed must be bool")
        if not isinstance(self.checks, tuple):
            raise ValueError("P11BVerifierReport.checks must be tuple")
        if not isinstance(self.report_hash, str) or len(self.report_hash) != 16:
            raise ValueError("P11BVerifierReport.report_hash must be 16-char hex")


# =============================================================================
# Verification Functions
# =============================================================================


def _check_forbidden_vocabulary(output_text: str) -> P11BVerificationCheck:
    """Check that output does not contain forbidden vocabulary."""
    output_upper = output_text.upper()

    for forbidden in _FORBIDDEN_VOCABULARY:
        if forbidden.upper() in output_upper:
            return P11BVerificationCheck(
                check_name="forbidden_vocabulary",
                passed=False,
                details=f"Contains forbidden term: {forbidden}",
            )

    return P11BVerificationCheck(
        check_name="forbidden_vocabulary",
        passed=True,
        details="No forbidden vocabulary found",
    )


def _check_line_length(output_text: str) -> P11BVerificationCheck:
    """Check that no line exceeds maximum length."""
    lines = output_text.split("\n")

    for i, line in enumerate(lines):
        if len(line) > MAX_LINE_LENGTH:
            return P11BVerificationCheck(
                check_name="line_length",
                passed=False,
                details=f"Line {i+1} exceeds {MAX_LINE_LENGTH} chars",
            )

    return P11BVerificationCheck(
        check_name="line_length",
        passed=True,
        details=f"All lines within {MAX_LINE_LENGTH} chars",
    )


def _check_total_length(output_text: str) -> P11BVerificationCheck:
    """Check that total output length is within limits."""
    if len(output_text) > MAX_OUTPUT_LENGTH:
        return P11BVerificationCheck(
            check_name="total_length",
            passed=False,
            details=f"Output exceeds {MAX_OUTPUT_LENGTH} chars",
        )

    return P11BVerificationCheck(
        check_name="total_length",
        passed=True,
        details=f"Output length {len(output_text)} within limit",
    )


def _check_template_shape(output_text: str) -> P11BVerificationCheck:
    """Check that output matches valid Phase-11B template shapes."""
    # Check first line (primary output line)
    first_line = output_text.split("\n")[0] if output_text else ""

    for pattern in _VALID_P11B_SHAPES:
        if pattern.match(first_line):
            return P11BVerificationCheck(
                check_name="template_shape",
                passed=True,
                details=f"Matches pattern: {pattern.pattern}",
            )

    return P11BVerificationCheck(
        check_name="template_shape",
        passed=False,
        details=f"Output '{first_line[:50]}...' does not match any valid template shape",
    )


def _check_not_empty(output_text: str) -> P11BVerificationCheck:
    """Check that output is not empty."""
    if not output_text or not output_text.strip():
        return P11BVerificationCheck(
            check_name="not_empty",
            passed=False,
            details="Output is empty",
        )

    return P11BVerificationCheck(
        check_name="not_empty",
        passed=True,
        details="Output is not empty",
    )


def _check_no_render_error(output_text: str) -> P11BVerificationCheck:
    """Check that output does not contain render errors."""
    if "[RENDER_ERROR:" in output_text:
        return P11BVerificationCheck(
            check_name="no_render_error",
            passed=False,
            details="Output contains render error",
        )

    return P11BVerificationCheck(
        check_name="no_render_error",
        passed=True,
        details="No render errors",
    )


# =============================================================================
# Main Verification Function
# =============================================================================


def verify_p11b_output(render_result: P11BRenderResult) -> P11BVerifierReport:
    """
    Verify Phase-11B rendered output.

    Runs all verification checks and produces a report.

    Args:
        render_result: The Phase-11B render result to verify.

    Returns:
        P11BVerifierReport with verification results.
    """
    output_text = render_result.output_text
    checks: List[P11BVerificationCheck] = []

    # Run all checks
    checks.append(_check_not_empty(output_text))
    checks.append(_check_forbidden_vocabulary(output_text))
    checks.append(_check_line_length(output_text))
    checks.append(_check_total_length(output_text))
    checks.append(_check_template_shape(output_text))
    checks.append(_check_no_render_error(output_text))

    # Determine overall pass
    all_passed = all(check.passed for check in checks)

    # Compute report hash
    hash_input = f"{all_passed}|{tuple((c.check_name, c.passed) for c in checks)}"
    report_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return P11BVerifierReport(
        passed=all_passed,
        checks=tuple(checks),
        report_hash=report_hash,
    )


# =============================================================================
# Convenience Functions
# =============================================================================


def get_p11b_verifier_version() -> str:
    """Return the verifier version."""
    return P11B_VERIFIER_VERSION


def get_forbidden_vocabulary() -> Tuple[str, ...]:
    """Return the forbidden vocabulary list."""
    return _FORBIDDEN_VOCABULARY


def get_max_line_length() -> int:
    """Return the maximum line length."""
    return MAX_LINE_LENGTH


def get_max_output_length() -> int:
    """Return the maximum output length."""
    return MAX_OUTPUT_LENGTH


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "P11B_VERIFIER_VERSION",
    # Dataclasses
    "P11BVerificationCheck",
    "P11BVerifierReport",
    # Functions
    "verify_p11b_output",
    "get_p11b_verifier_version",
    "get_forbidden_vocabulary",
    "get_max_line_length",
    "get_max_output_length",
]
