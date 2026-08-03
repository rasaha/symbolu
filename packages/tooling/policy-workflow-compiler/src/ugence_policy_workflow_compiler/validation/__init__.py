"""Deterministic validation engine."""

from __future__ import annotations

from .authority_boundaries import BoundaryViolation, check_ir, check_node
from .coverage import (
    COVERAGE_REQUIRED_TYPES,
    build_coverage_matrix,
    check_coverage,
    required_coverage_ids,
)
from .errors import Severity, ValidationDiagnostic, ValidationReport
from .validator import PolicyPackValidator, validate_policy_pack

__all__ = [
    "Severity",
    "ValidationDiagnostic",
    "ValidationReport",
    "PolicyPackValidator",
    "validate_policy_pack",
    "BoundaryViolation",
    "check_ir",
    "check_node",
    "COVERAGE_REQUIRED_TYPES",
    "required_coverage_ids",
    "build_coverage_matrix",
    "check_coverage",
]
