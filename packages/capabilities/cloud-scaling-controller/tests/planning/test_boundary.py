"""Phase-3 advisory/shadow-boundary + import-safety tests.

Phase 3 recommends; it never executes, authorizes, or verifies an effect, and it imports no
Risk Authority (Phase 4), ActionGate/provider execution (Phase 5), or effect-verification
(Phase 6) package. It performs no network / subprocess / credential / LLM activity and adds
no runtime dependency.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_cloud_scaling_controller
from ugence_cloud_scaling_controller import planning
from ugence_cloud_scaling_controller.planning import (
    CapacityActionRecommendation,
    RecommendationAbstention,
    recommend_capacity_action,
)
import ph_helpers as H

_PLANNING_DIR = pathlib.Path(planning.__file__).parent
_PLANNING_FILES = sorted(_PLANNING_DIR.rglob("*.py"))

FORBIDDEN_IMPORT_ROOTS = {
    "boto3", "botocore", "azure", "kubernetes", "requests", "prometheus_client",
    "opentelemetry", "yaml", "fastapi", "uvicorn", "flask", "socket", "http",
    "urllib", "subprocess", "threading", "multiprocessing",
    "risk_authority", "actiongate", "governance_studio", "decision_governance",
    "agent_runtime", "hybrid_llm", "control_plane", "cloud_scaling_operations",
}


def test_planning_has_no_forbidden_top_level_imports():
    offenders = []
    for p in _PLANNING_FILES:
        tree = ast.parse(p.read_text())
        for node in tree.body:  # module top-level only
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in FORBIDDEN_IMPORT_ROOTS:
                    offenders.append(f"{p.name}: {m}")
    assert not offenders, f"forbidden imports in planning: {offenders}"


def test_planning_mentions_no_risk_authority_or_actiongate_symbols():
    for p in _PLANNING_FILES:
        text = p.read_text()
        for banned in ("RiskAuthority", "ActionGate", "ExecutionReceipt", "approve", "actuate"):
            # allow the words inside docstrings that explicitly disclaim them ("no ActionGate")
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    seg = ast.get_source_segment(text, node) or ""
                    assert banned not in seg, f"{p.name} imports {banned}"


def test_recommendation_is_advisory_only():
    app, db = H.subject("app"), H.subject("db")
    out = recommend_capacity_action(
        H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0, topology=H.topology(subj=app, dependency=db))
    assert isinstance(out, CapacityActionRecommendation)
    assert out.advisory_only is True and out.shadow_only is True
    assert out.actuation_performed is False
    assert out.authorization_performed is False
    assert out.effect_verified is False
    assert out.authority_class == "ADVISORY"
    assert out.execution_capability == "NONE"


def test_abstention_is_advisory_only():
    app = H.subject()
    out = recommend_capacity_action(
        None, H.replicas_state(H.at(180), 6, subj=app), H.cost_book(subj=app), H.constraints(),
        H.policy(), recommendation_time=H.at(190), validity_seconds=600.0)
    assert isinstance(out, RecommendationAbstention)
    assert out.advisory_only is True and out.shadow_only is True
    assert out.actuation_performed is False


def test_recommendation_cannot_claim_execution():
    app, db = H.subject("app"), H.subject("db")
    out = recommend_capacity_action(
        H.build_forecast_evidence(8, subj=app), H.replicas_state(H.at(180), 6, subj=app),
        H.cost_book(subj=app, dependency=db), H.constraints(max_capacity=50), H.policy(),
        recommendation_time=H.at(190), validity_seconds=600.0, topology=H.topology(subj=app, dependency=db))
    import dataclasses
    for banned in ("actuation_performed", "authorization_performed", "effect_verified"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(out, banned, True)


def test_top_level_exports_present():
    for name in ("recommend_capacity_action", "CapacityActionRecommendation",
                 "RecommendationAbstention", "DependencyTopology", "CostBook",
                 "OperatingConstraints", "RecommendationPolicy"):
        assert hasattr(ugence_cloud_scaling_controller, name)
        assert name in ugence_cloud_scaling_controller.__all__
