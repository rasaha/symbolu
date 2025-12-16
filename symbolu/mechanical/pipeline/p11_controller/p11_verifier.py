"""
P11 Verifier - Structural Verification for Phase-11 Output
============================================================

This module provides structural verification for Phase-11 rendered output.

Verification Rules:
    - Line-by-line structural verification
    - Forbidden vocabulary scan
    - Template shape enforcement
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
from typing import Dict, List, Tuple

from symbolu.mechanical.pipeline.p11_controller.p11_templates import TemplateRenderResult


# =============================================================================
# Version Constant
# =============================================================================

VERIFIER_VERSION = "1.0.0"


# =============================================================================
# Forbidden Vocabulary
# =============================================================================

# Words/phrases that MUST NOT appear in Phase-11 output
# This is a safety boundary - generative output must not contain these
_FORBIDDEN_VOCABULARY: Tuple[str, ...] = (
    # Safety-critical terms
    "ABSOLVING",
    "OVERRIDE",
    "BYPASS",
    "IGNORE_SAFETY",
    "SKIP_VERIFICATION",
    # Generative markers (should not leak)
    "GENERATE_FREE",
    "UNCONSTRAINED",
    "FREE_FORM",
    "UNBOUNDED",
    # System internals (should not leak)
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

# Maximum allowed line length
MAX_LINE_LENGTH = 1000

# Maximum allowed total output length
MAX_OUTPUT_LENGTH = 10000


# =============================================================================
# Template Shape Patterns
# =============================================================================

# Valid template shapes (regex patterns)
_VALID_TEMPLATE_SHAPES: Tuple[re.Pattern, ...] = (
    re.compile(r"^\[REGIME:[a-z]+\].*$"),  # Standard regime prefix
)


# =============================================================================
# Verification Report
# =============================================================================


@dataclass(frozen=True)
class VerificationCheck:
    """
    Single verification check result.

    Attributes:
        check_name: Name of the check
        passed: Whether the check passed
        details: Additional details about the check
    """
    check_name: str
    passed: bool
    details: str = ""


@dataclass(frozen=True)
class VerifierReport:
    """
    Complete verification report for Phase-11 output.

    Attributes:
        checks: List of individual check results
        passed: Overall pass/fail status
        report_hash: Deterministic hash of the report
        forbidden_words_found: List of any forbidden words detected
        structural_violations: List of structural violations
    """
    checks: Tuple[VerificationCheck, ...]
    passed: bool
    report_hash: str
    forbidden_words_found: Tuple[str, ...] = field(default=())
    structural_violations: Tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        """Validate VerifierReport invariants."""
        if not isinstance(self.checks, tuple):
            raise ValueError(
                f"VerifierReport.checks must be tuple, "
                f"got {type(self.checks).__name__}"
            )
        if not isinstance(self.passed, bool):
            raise ValueError(
                f"VerifierReport.passed must be bool, "
                f"got {type(self.passed).__name__}"
            )
        if not isinstance(self.report_hash, str) or len(self.report_hash) != 16:
            raise ValueError(
                "VerifierReport.report_hash must be 16-char hex string"
            )

    def get_failed_checks(self) -> Tuple[VerificationCheck, ...]:
        """Get all checks that failed."""
        return tuple(c for c in self.checks if not c.passed)

    def get_passed_checks(self) -> Tuple[VerificationCheck, ...]:
        """Get all checks that passed."""
        return tuple(c for c in self.checks if c.passed)


# =============================================================================
# Individual Verification Checks
# =============================================================================


def _check_forbidden_vocabulary(output_text: str) -> Tuple[bool, List[str]]:
    """
    Scan for forbidden vocabulary in output.

    Args:
        output_text: The text to scan.

    Returns:
        Tuple of (passed, list of forbidden words found).
    """
    found_forbidden: List[str] = []
    output_upper = output_text.upper()

    for forbidden in _FORBIDDEN_VOCABULARY:
        if forbidden.upper() in output_upper:
            found_forbidden.append(forbidden)

    return len(found_forbidden) == 0, found_forbidden


def _check_line_length(output_text: str) -> Tuple[bool, List[str]]:
    """
    Check that no line exceeds maximum length.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, list of violations).
    """
    violations: List[str] = []
    lines = output_text.split("\n")

    for i, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE_LENGTH:
            violations.append(f"Line {i}: {len(line)} chars (max {MAX_LINE_LENGTH})")

    return len(violations) == 0, violations


def _check_total_length(output_text: str) -> Tuple[bool, str]:
    """
    Check that total output does not exceed maximum length.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, details).
    """
    length = len(output_text)
    if length > MAX_OUTPUT_LENGTH:
        return False, f"Output length {length} exceeds max {MAX_OUTPUT_LENGTH}"
    return True, f"Output length {length} within limit"


def _check_template_shape(output_text: str) -> Tuple[bool, str]:
    """
    Verify output matches approved template shapes.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, details).
    """
    # Check first line matches a valid template shape
    first_line = output_text.split("\n")[0] if output_text else ""

    for pattern in _VALID_TEMPLATE_SHAPES:
        if pattern.match(first_line):
            return True, f"Matches template shape: {pattern.pattern}"

    return False, f"First line does not match any approved template shape"


def _check_no_null_bytes(output_text: str) -> Tuple[bool, str]:
    """
    Check for null bytes or control characters.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, details).
    """
    if "\x00" in output_text:
        return False, "Contains null bytes"

    # Check for other dangerous control characters
    dangerous_chars = ["\x01", "\x02", "\x03", "\x04", "\x05", "\x06", "\x07"]
    for char in dangerous_chars:
        if char in output_text:
            return False, f"Contains control character: {repr(char)}"

    return True, "No null bytes or dangerous control characters"


def _check_balanced_brackets(output_text: str) -> Tuple[bool, str]:
    """
    Check for balanced brackets in output.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, details).
    """
    stack: List[str] = []
    bracket_pairs = {"[": "]", "{": "}", "(": ")"}

    for char in output_text:
        if char in bracket_pairs:
            stack.append(char)
        elif char in bracket_pairs.values():
            if not stack:
                return False, f"Unbalanced closing bracket: {char}"
            expected_close = bracket_pairs[stack.pop()]
            if char != expected_close:
                return False, f"Mismatched brackets: expected {expected_close}, got {char}"

    if stack:
        return False, f"Unclosed brackets: {stack}"

    return True, "All brackets balanced"


def _check_regime_prefix(output_text: str) -> Tuple[bool, str]:
    """
    Check that output has a valid regime prefix.

    Args:
        output_text: The text to check.

    Returns:
        Tuple of (passed, details).
    """
    if not output_text.startswith("[REGIME:"):
        return False, "Output must start with [REGIME:...]"

    # Extract regime from prefix
    match = re.match(r"^\[REGIME:([a-z]+)\]", output_text)
    if not match:
        return False, "Invalid regime prefix format"

    regime = match.group(1)
    valid_regimes = {"neutral", "soft", "flat", "restrained"}
    if regime not in valid_regimes:
        return False, f"Unknown regime: {regime}. Valid: {valid_regimes}"

    return True, f"Valid regime prefix: {regime}"


# =============================================================================
# Main Verification Function
# =============================================================================


def verify_output(render_result: TemplateRenderResult) -> VerifierReport:
    """
    Perform full structural verification on rendered output.

    This function:
        - Line-by-line structural verification
        - Forbidden vocabulary scan
        - Template shape enforcement
        - Produces verifier_passed: bool
        - Produces verifier_report_hash

    Args:
        render_result: The template render result to verify.

    Returns:
        VerifierReport with full verification results.
    """
    output_text = render_result.output_text
    checks: List[VerificationCheck] = []
    all_forbidden_found: List[str] = []
    all_structural_violations: List[str] = []

    # Check 1: Forbidden vocabulary
    vocab_passed, forbidden_found = _check_forbidden_vocabulary(output_text)
    checks.append(VerificationCheck(
        check_name="forbidden_vocabulary",
        passed=vocab_passed,
        details=f"Found: {forbidden_found}" if forbidden_found else "No forbidden words"
    ))
    all_forbidden_found.extend(forbidden_found)

    # Check 2: Line length
    line_passed, line_violations = _check_line_length(output_text)
    checks.append(VerificationCheck(
        check_name="line_length",
        passed=line_passed,
        details="; ".join(line_violations) if line_violations else "All lines within limit"
    ))
    all_structural_violations.extend(line_violations)

    # Check 3: Total length
    total_passed, total_details = _check_total_length(output_text)
    checks.append(VerificationCheck(
        check_name="total_length",
        passed=total_passed,
        details=total_details
    ))
    if not total_passed:
        all_structural_violations.append(total_details)

    # Check 4: Template shape
    shape_passed, shape_details = _check_template_shape(output_text)
    checks.append(VerificationCheck(
        check_name="template_shape",
        passed=shape_passed,
        details=shape_details
    ))
    if not shape_passed:
        all_structural_violations.append(shape_details)

    # Check 5: No null bytes
    null_passed, null_details = _check_no_null_bytes(output_text)
    checks.append(VerificationCheck(
        check_name="no_null_bytes",
        passed=null_passed,
        details=null_details
    ))
    if not null_passed:
        all_structural_violations.append(null_details)

    # Check 6: Balanced brackets
    bracket_passed, bracket_details = _check_balanced_brackets(output_text)
    checks.append(VerificationCheck(
        check_name="balanced_brackets",
        passed=bracket_passed,
        details=bracket_details
    ))
    if not bracket_passed:
        all_structural_violations.append(bracket_details)

    # Check 7: Regime prefix
    regime_passed, regime_details = _check_regime_prefix(output_text)
    checks.append(VerificationCheck(
        check_name="regime_prefix",
        passed=regime_passed,
        details=regime_details
    ))
    if not regime_passed:
        all_structural_violations.append(regime_details)

    # Overall pass/fail
    overall_passed = all(c.passed for c in checks)

    # Compute deterministic report hash
    hash_input = "|".join([
        f"{c.check_name}:{c.passed}:{c.details}"
        for c in checks
    ])
    report_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return VerifierReport(
        checks=tuple(checks),
        passed=overall_passed,
        report_hash=report_hash,
        forbidden_words_found=tuple(all_forbidden_found),
        structural_violations=tuple(all_structural_violations),
    )


# =============================================================================
# Verifier Metadata
# =============================================================================


def get_verifier_version() -> str:
    """Return the verifier version."""
    return VERIFIER_VERSION


def get_forbidden_vocabulary_count() -> int:
    """Return the count of forbidden vocabulary terms."""
    return len(_FORBIDDEN_VOCABULARY)


def get_max_line_length() -> int:
    """Return the maximum allowed line length."""
    return MAX_LINE_LENGTH


def get_max_output_length() -> int:
    """Return the maximum allowed output length."""
    return MAX_OUTPUT_LENGTH


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "VERIFIER_VERSION",
    # Dataclasses
    "VerificationCheck",
    "VerifierReport",
    # Functions
    "verify_output",
    "get_verifier_version",
    "get_forbidden_vocabulary_count",
    "get_max_line_length",
    "get_max_output_length",
]
