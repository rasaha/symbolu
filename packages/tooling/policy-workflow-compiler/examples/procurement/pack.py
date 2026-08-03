"""Procurement reference pack — re-export of the shipped in-package builder.

The canonical builder lives in
``ugence_policy_workflow_compiler.reference.procurement`` so the CLI ``demo`` and
the equivalence harness resolve it from the installed wheel. This example module
re-exports it for documentation and standalone example runs.
"""

from __future__ import annotations

from ugence_policy_workflow_compiler.reference.procurement import (
    APPROVAL_THRESHOLD,
    HARD_LIMIT,
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)

__all__ = [
    "build_procurement_policy_pack",
    "build_procurement_approval_fixture",
    "HARD_LIMIT",
    "APPROVAL_THRESHOLD",
]
