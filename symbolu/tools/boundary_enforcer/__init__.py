"""
Boundary Enforcer: Static analysis tools for Core/Observer boundary enforcement.

This package provides:
- boundary_rules: Definitions of authoritative and observer module roots
- scan_imports: Static import scanner for violation detection
"""

from .boundary_rules import (
    AUTHORITATIVE_MODULE_ROOTS,
    OBSERVER_MODULE_ROOTS,
    ALLOWED_SINK_PATTERNS,
    BoundaryRule,
    get_boundary_rules,
)
from .scan_imports import (
    ImportScanner,
    scan_for_violations,
    generate_boundary_report,
)

__all__ = [
    "AUTHORITATIVE_MODULE_ROOTS",
    "OBSERVER_MODULE_ROOTS",
    "ALLOWED_SINK_PATTERNS",
    "BoundaryRule",
    "get_boundary_rules",
    "ImportScanner",
    "scan_for_violations",
    "generate_boundary_report",
]
