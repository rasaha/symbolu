"""Dependency semantics, authority/human-review semantics, and provenance."""

from __future__ import annotations

from ugence_policy_workflow_compiler.semantics import (
    DependencyKind,
    DerivationClass,
    RoleRelevance,
    enrich_workflow,
)
import _v2_helpers as H


def _v2(ir):
    return enrich_workflow(ir, compiler_version="test")


# -- dependencies ----------------------------------------------------------- #

def test_dependency_kinds_present_and_typed():
    v2 = _v2(H.procurement_ir())
    kinds = {d.dependency_kind for d in v2.dependency_semantics}
    assert DependencyKind.DATA_DEPENDENCY in kinds
    assert DependencyKind.AUTHORITY_DEPENDENCY in kinds  # edge into the approval gate
    assert DependencyKind.GOVERNANCE_DEPENDENCY in kinds  # edge into the action constraint


def test_dependency_endpoints_all_resolve():
    v2 = _v2(H.cybersecurity_success_ir())
    ids = {n.node_id for n in v2.base_ir.nodes}
    for d in v2.dependency_semantics:
        assert d.source_node_id in ids and d.target_node_id in ids


def test_dependency_ordering_is_stable():
    a = _v2(H.procurement_ir()).dependency_semantics
    b = _v2(H.procurement_ir()).dependency_semantics
    assert [d.edge_id for d in a] == [d.edge_id for d in b]


def test_data_dependency_carries_contract_refs():
    v2 = _v2(H.procurement_ir())
    data_deps = [d for d in v2.dependency_semantics
                 if d.dependency_kind is DependencyKind.DATA_DEPENDENCY]
    assert data_deps
    assert all(d.output_contract_refs for d in data_deps)


# -- authority / human review ---------------------------------------------- #

def test_authority_disposition_matches_v1_node():
    v2 = _v2(H.procurement_ir())
    by_id = {n.node_id: n for n in v2.base_ir.nodes}
    for s in v2.node_semantics:
        assert s.authority_disposition == by_id[s.node_id].disposition.value


def test_human_authority_requirement_flagged():
    v2 = _v2(H.procurement_ir())
    approval = next(s for s in v2.node_semantics
                    if s.role_relevance is RoleRelevance.HUMAN_AUTHORITY)
    assert approval.human_authority_requirement is True
    assert approval.human_review_requirement.required is True
    assert approval.human_review_requirement.review_kind == "human_authority"


def test_governance_owned_nodes_carry_boundary_refs():
    v2 = _v2(H.procurement_ir())
    gov = [s for s in v2.node_semantics if s.role_relevance is RoleRelevance.GOVERNANCE_OWNED]
    assert gov
    # at least the approval/action nodes with a public contract target expose a boundary ref
    assert any(s.governance_boundary_refs for s in v2.node_semantics
               if s.role_relevance in (RoleRelevance.HUMAN_AUTHORITY, RoleRelevance.GOVERNANCE_OWNED))


def test_agent_eligible_node_has_no_human_review():
    v2 = _v2(H.customer_support_ir())
    agents = [s for s in v2.node_semantics
              if s.role_relevance is RoleRelevance.ADVISORY_AGENT_ELIGIBLE]
    assert agents
    for s in agents:
        assert s.human_authority_requirement is False
        assert s.human_review_requirement.review_kind == "none"


# -- provenance ------------------------------------------------------------- #

def test_every_semantic_value_has_provenance():
    v2 = _v2(H.procurement_ir())
    for s in v2.node_semantics:
        assert s.provenance.compiler_rule
        assert s.provenance.derivation_class
        assert s.provenance.source_policy_id == v2.policy_pack_id
    for d in v2.dependency_semantics:
        assert d.provenance.derivation_class is DerivationClass.DERIVED_FROM_EDGE


def test_provenance_source_object_ids_trace_to_inputs():
    v2 = _v2(H.procurement_ir())
    by_id = {n.node_id: n for n in v2.base_ir.nodes}
    for s in v2.node_semantics:
        assert tuple(s.provenance.source_object_ids) == tuple(by_id[s.node_id].input_object_ids)


def test_provenance_is_ordering_independent():
    # reversing node order in the v1 graph must not change the enriched fingerprint,
    # because enrichment canonicalizes.
    ir = H.procurement_ir()
    reversed_ir = ir.model_copy(update={"nodes": tuple(reversed(ir.nodes))})
    a = _v2(ir)
    b = _v2(reversed_ir)
    # node-semantics set (by fingerprint) is identical regardless of input order
    assert {s.fingerprint for s in a.node_semantics} == {s.fingerprint for s in b.node_semantics}
