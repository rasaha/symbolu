"""Shared P2 test helpers."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.adapter import adapt_compiled_workflow
from ugence_agent_workforce_composer.eligibility import evaluate_registry_for_role

NOW = fixtures.LOGICAL_TIME


def adaptation(name="procurement"):
    return adapt_compiled_workflow(fixtures.WORKFLOWS[name](), role_overlay=fixtures.role_overlay())


def role_report(name, node_id, *, enterprise=None, eligibility=None):
    adapt = adaptation(name)
    role = next(r for r in adapt.role_requirements if r.source_node_id == node_id)
    snap = fixtures.registry_snapshot()
    rep = evaluate_registry_for_role(role, snap, enterprise or fixtures.enterprise_policy(),
                                     eligibility or fixtures.eligibility_policy(), NOW)
    return role, rep, snap


def default_policies():
    return dict(
        enterprise=fixtures.enterprise_policy(),
        eligibility=fixtures.eligibility_policy(),
        ranking=fixtures.ranking_policy(),
        composition=fixtures.team_composition_policy(),
        permission=fixtures.permission_policy(),
        fallback=fixtures.fallback_policy(),
    )
