"""Control resolution — WorkflowIR rules -> required control set.

Deterministic, prose-free. Resolves which rules apply to a case and unions the
controls those rules require (spec §7.4, §10).
"""

from __future__ import annotations

from typing import Mapping

from ..domain.workflow_ir import WorkflowIR, WorkflowRule

__all__ = ["resolve_required_controls", "applicable_rules"]


def applicable_rules(
    workflow: WorkflowIR, context: Mapping[str, object]
) -> tuple[WorkflowRule, ...]:
    return workflow.applicable_rules(context)


def resolve_required_controls(
    workflow: WorkflowIR, context: Mapping[str, object]
) -> tuple[str, ...]:
    """Return the sorted, de-duplicated union of controls required by applicable rules."""

    required: set[str] = set()
    for rule in workflow.applicable_rules(context):
        required.update(rule.required_controls)
    return tuple(sorted(required))
