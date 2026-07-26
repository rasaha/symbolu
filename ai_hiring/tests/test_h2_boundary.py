"""H2 — architectural boundary tests.

Guards the H2 invariants: recommendations are advisory (no binding decision), AI
holds no decision authority, TAP is reached only through the provider contract, and
the core imports only the frozen public surfaces (no TAP internals, no vendor SDKs).
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from ai_hiring.recommendations.recommendation import HiringRecommendation, RecommendationOutcome
from ai_hiring.recommendations.status import (
    RECOMMENDATION_TERMINAL_STATUSES,
    RecommendationStatus,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

H2_MODULES = [
    "ai_hiring/recommendations/status.py", "ai_hiring/recommendations/claim.py",
    "ai_hiring/recommendations/recommendation.py", "ai_hiring/recommendations/generator.py",
    "ai_hiring/recommendations/tap_integration.py", "ai_hiring/recommendations/review.py",
    "ai_hiring/synthesis/package.py", "ai_hiring/synthesis/minimization.py",
    "ai_hiring/synthesis/service.py",
    "ai_hiring/repositories/recommendation_repositories.py",
    "ai_hiring/services/recommendation_generation_service.py",
    "ai_hiring/services/recommendation_reconstruction_service.py",
    "ai_hiring/api/recommendation_contracts.py",
]


def test_no_binding_decision_status():
    forbidden = {"HIRED", "ACCEPTED", "APPROVED", "OFFERED", "REJECTED_CANDIDATE", "DECIDED", "SELECTED"}
    assert not ({s.value for s in RecommendationStatus} & forbidden)
    assert RECOMMENDATION_TERMINAL_STATUSES == frozenset(
        {RecommendationStatus.REJECTED_BY_REVIEW, RecommendationStatus.SUPERSEDED})


def test_recommendation_is_always_advisory():
    from ai_hiring.errors import DomainValidationError
    with pytest.raises(DomainValidationError):
        HiringRecommendation(
            recommendation_id="r", tenant_id="t", application_id="a", candidate_subject_ref="s",
            requisition_id="q", job_definition_id="jd", job_definition_version=1, rubric_id="rb",
            rubric_version=1, advisory=False)  # advisory must be True


def test_recommendation_outcomes_are_advisory_only():
    # advisory verbs only — never a binding hire/accept
    for o in RecommendationOutcome:
        assert o.value.startswith(("RECOMMEND_", "INSUFFICIENT", "NO_"))


def test_h2_core_imports_only_public_surfaces():
    """H2 modules may import decision_governance and governance_providers only via
    their public `.api`, must not import TAP internals, and must not import vendor SDKs."""
    banned_sdks = ("openai", "anthropic", "mistralai", "langchain", "cohere", "llama_index",
                   "transformers", "torch", "vllm")
    violations = []
    for rel in H2_MODULES:
        tree = ast.parse((REPO / rel).read_text(), filename=rel)
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets.append(node.module)
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for t in targets:
                top = t.split(".")[0]
                if top == "decision_governance" and not t.startswith("decision_governance.api"):
                    violations.append(f"{rel}:{node.lineno} kernel-internal -> {t}")
                if top == "governance_providers" and not t.startswith("governance_providers.api"):
                    violations.append(f"{rel}:{node.lineno} provider-internal -> {t}")
                if top in ("tap_provider", "actiongate_provider"):
                    violations.append(f"{rel}:{node.lineno} provider-impl -> {t}")
                if top in banned_sdks:
                    violations.append(f"{rel}:{node.lineno} vendor-sdk -> {t}")
    assert not violations, "H2 import-boundary violations:\n" + "\n".join(violations)


def test_h2_never_imports_tap_or_actiongate_anywhere():
    for rel in H2_MODULES:
        src = (REPO / rel).read_text()
        assert "tap_provider" not in src, f"{rel} references tap_provider"
        assert "actiongate_provider" not in src, f"{rel} references actiongate_provider"


def test_generation_service_grants_no_decision_authority():
    """The generation service exposes no method that decides/executes a hiring action."""
    from ai_hiring.services.recommendation_generation_service import RecommendationGenerationService
    banned = {"decide", "hire", "reject_candidate", "offer", "execute", "authorize", "advance_candidate"}
    methods = {m for m in dir(RecommendationGenerationService) if not m.startswith("_")}
    assert not (methods & banned), methods & banned
