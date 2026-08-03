"""Boundary + maturity honesty: the demo layer is presentation/orchestration
only. It performs no network I/O, duplicates no AWC policy logic, and never
presents planning artifacts as grants or executions.
"""
import ast
import os
import socket

import pytest

import ugence_agent_workforce_composer.api as awc
import _loader as L

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")


def test_no_network_access_during_evaluation(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network access attempted during AWC evaluation")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    for sid in L.SCENARIOS:
        L.run_pipeline(L.load_inputs(sid))  # must complete offline


def test_scripts_only_orchestrate_awc_never_reimplement_it():
    """The authoring/generation scripts may import the AWC public API and its
    canonical/fingerprint helpers, but must not import private policy engines
    (eligibility/ranking/composition/permissions/fallback) or define their own."""
    banned_modules = {
        "ugence_agent_workforce_composer.eligibility",
        "ugence_agent_workforce_composer.ranking",
        "ugence_agent_workforce_composer.composition",
        "ugence_agent_workforce_composer.permissions",
        "ugence_agent_workforce_composer.fallback",
        "ugence_agent_workforce_composer.plan",
        "ugence_agent_workforce_composer.adapter",
    }
    banned_defs = {
        "evaluate_agent_eligibility", "rank_eligible_candidates", "compose_agent_team",
        "propose_permission_bound", "build_fallback_plan", "build_agent_team_plan",
        "classify_node",
    }
    for fname in os.listdir(_SCRIPTS):
        if not fname.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(_SCRIPTS, fname), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in banned_modules:
                raise AssertionError(f"{fname} imports private AWC engine {node.module}")
            if isinstance(node, ast.FunctionDef) and node.name in banned_defs:
                raise AssertionError(f"{fname} re-defines AWC engine function {node.name}")


def test_permission_proposals_carry_no_grant_notice():
    for sid in L.SCENARIOS:
        plan = L.run_pipeline(L.load_inputs(sid))["plan"]
        for prop in plan.permission_bound_proposals:
            assert "does not grant" in prop.notice
            assert "execute" in prop.notice


def test_public_api_exposes_no_execution_or_grant_surface():
    banned = {"execute_agent", "run_agent", "dispatch", "grant_permission",
              "assign_permission", "invoke_model", "schedule_workflow",
              "authorize_action", "reassign_agent"}
    assert not (banned & set(awc.__all__))


def test_no_business_action_authorization_in_plans():
    """Governance-owned/authoritative work stays with non-agent dispositions;
    no such node is ever turned into an agent assignment."""
    for sid in L.SCENARIOS:
        out = L.run_pipeline(L.load_inputs(sid))
        role_node_ids = {r.source_node_id for r in out["adaptation"].role_requirements}
        for na in out["adaptation"].non_agent_dispositions:
            assert na.node_id not in role_node_ids
