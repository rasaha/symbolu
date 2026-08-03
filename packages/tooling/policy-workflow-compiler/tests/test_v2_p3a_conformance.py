"""P3A requirements conformance.

For each merged Governance Studio P3A scenario shape, the compiler P2 layer must
express the compiler-owned semantics the P3A ownership matrix identifies — without
guessing — while emitting NO agent-selection, ranking, composition, or enterprise
deployment policy (those remain enterprise-overlay / AWC / runtime concerns).
"""

from __future__ import annotations

import pytest

from ugence_policy_workflow_compiler.semantics import (
    RoleRelevance,
    enrich_workflow,
)
from ugence_policy_workflow_compiler.validation.release_validator import (
    ReleaseValidationState,
    validate_compiled_release,
)
import _v2_helpers as H

# P3A COMPILER_VS_OVERLAY_OWNERSHIP.md: fields the compiler should own/emit.
_COMPILER_OWNED_PRESENT = (
    "node_id", "node_kind", "semantic_purpose", "role_relevance",
    "authority_disposition", "canonical_capability_owner",
    "human_review_requirement", "provenance",
)
# Fields that must NOT appear in compiler output (enterprise overlay / AWC / runtime).
_FORBIDDEN_ON_NODE_SEMANTICS = (
    "provider_constraints", "residency_constraints", "deployment_constraints",
    "required_security_classification", "maximum_cost_constraint",
    "maximum_latency_constraint", "minimum_quality_constraint",
    "eligibility", "ranking", "score", "team", "fallback", "permission_grant",
)


@pytest.mark.parametrize("sid", list(H.P3A_SCENARIOS))
def test_scenario_enriches_and_validates(sid):
    ir = H.P3A_SCENARIOS[sid]()
    v2 = enrich_workflow(ir, compiler_version="test")
    assert validate_compiled_release(v2).state is ReleaseValidationState.VALID
    assert len(v2.node_semantics) == len(ir.nodes)


@pytest.mark.parametrize("sid", list(H.P3A_SCENARIOS))
def test_scenario_has_all_compiler_owned_semantics(sid):
    v2 = enrich_workflow(H.P3A_SCENARIOS[sid](), compiler_version="test")
    for s in v2.node_semantics:
        for field in _COMPILER_OWNED_PRESENT:
            assert getattr(s, field) is not None


@pytest.mark.parametrize("sid", list(H.P3A_SCENARIOS))
def test_scenario_omits_enterprise_and_awc_fields(sid):
    v2 = enrich_workflow(H.P3A_SCENARIOS[sid](), compiler_version="test")
    fields = set(type(v2.node_semantics[0]).model_fields)
    for forbidden in _FORBIDDEN_ON_NODE_SEMANTICS:
        assert forbidden not in fields, f"compiler node semantics must not carry {forbidden!r}"


def test_procurement_agent_roles_and_authority_split():
    v2 = enrich_workflow(H.procurement_ir(), compiler_version="test")
    rel = {}
    for s in v2.node_semantics:
        rel.setdefault(s.role_relevance, 0)
        rel[s.role_relevance] += 1
    # three advisory agent-eligible evidence roles; approval is human authority;
    # purchase authorization is governance-owned.
    assert rel.get(RoleRelevance.ADVISORY_AGENT_ELIGIBLE) == 3
    assert rel.get(RoleRelevance.HUMAN_AUTHORITY, 0) >= 1
    assert rel.get(RoleRelevance.GOVERNANCE_OWNED, 0) >= 1


def test_infeasible_scenario_is_still_compiler_valid():
    # 'no feasible team' is an AWC planning outcome, not a compiler concern: the
    # compiler enriches the graph identically and the release is VALID.
    v2 = enrich_workflow(H.cybersecurity_no_feasible_team_ir(), compiler_version="test")
    assert validate_compiled_release(v2).state is ReleaseValidationState.VALID
    agents = [s for s in v2.node_semantics
              if s.role_relevance is RoleRelevance.ADVISORY_AGENT_ELIGIBLE]
    assert len(agents) == 2  # threat analysis + incident correlation
