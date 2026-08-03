"""Change-impact analysis for a structural diff.

Given the classified object changes, summarize downstream impact: which workflow
nodes and assurance tests are affected, whether approval re-review is required,
and which connector mappings and authority scopes change. Deterministic and
exact — no semantic inference.
"""

from __future__ import annotations

from typing import Dict, Tuple

from ..models.common import ObjectType, PolicyObject

# Object types whose change forces a new approval review.
_APPROVAL_SENSITIVE = frozenset(
    {
        ObjectType.DECISION_RULE,
        ObjectType.AUTHORITY_REQUIREMENT,
        ObjectType.PROHIBITED_CONDITION,
        ObjectType.ACTION_CONSTRAINT,
        ObjectType.OVERRIDE_RULE,
        ObjectType.EXCEPTION_RULE,
        ObjectType.APPROVAL_PATH,
    }
)

# Object types that materialize into workflow nodes.
_NODE_PRODUCING = frozenset(
    {
        ObjectType.REQUIRED_EVIDENCE,
        ObjectType.DECISION_RULE,
        ObjectType.AUTHORITY_REQUIREMENT,
        ObjectType.APPROVAL_PATH,
        ObjectType.PROHIBITED_CONDITION,
        ObjectType.EXCEPTION_RULE,
        ObjectType.OVERRIDE_RULE,
        ObjectType.ACTION_CONSTRAINT,
        ObjectType.SEQUENCE_RISK_PATTERN,
    }
)


def compute_impact(
    added,
    removed,
    changed,
    old_index: Dict[str, PolicyObject],
    new_index: Dict[str, PolicyObject],
):
    from .structural_diff import ImpactSummary

    all_changes = list(added) + list(removed) + list(changed)

    nodes = set()
    tests = set()
    connectors = set()
    authority = set()
    re_review = False

    def type_of(change) -> str:
        return change.object_type

    for change in all_changes:
        otype = type_of(change)
        try:
            ot = ObjectType(otype)
        except ValueError:  # pragma: no cover - defensive
            continue
        if ot in _NODE_PRODUCING:
            nodes.add(change.object_id)
            tests.add(change.object_id)
        if ot is ObjectType.CONNECTOR_MAPPING:
            connectors.add(change.object_id)
        if ot in (ObjectType.AUTHORITY_REQUIREMENT, ObjectType.APPROVAL_PATH):
            authority.add(change.object_id)
        if ot in (ObjectType.TEST_SCENARIO, ObjectType.REPLAY_CASE):
            tests.add(change.object_id)
        if ot in _APPROVAL_SENSITIVE:
            re_review = True

    return ImpactSummary(
        workflow_nodes_affected=tuple(sorted(nodes)),
        assurance_tests_affected=tuple(sorted(tests)),
        approval_re_review_required=re_review,
        connector_mappings_affected=tuple(sorted(connectors)),
        authority_scope_affected=tuple(sorted(authority)),
    )
