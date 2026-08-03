"""v1/v2 dispatch, v2 adaptation, overlay reduction, authority preservation."""
from __future__ import annotations

import pytest

import ugence_agent_workforce_composer.api as awc
import ugence_agent_workforce_composer.adapter_v2 as a2
import ugence_agent_workforce_composer.compatibility as compat
from . import _conformance as C


# -- explicit dispatch ------------------------------------------------------ #

def test_dispatch_v1_and_v2_by_declared_contract():
    s = C.load("procurement")
    assert a2.declared_contract_version(s["v1_workflow"]) == "workflow_ir.v1"
    assert a2.declared_contract_version(s["v2_workflow"]) == "workflow_ir.v2"
    v1 = compat.adapt_workflow(s["v1_workflow"], role_overlay=s["v1_overlay"])
    v2 = compat.adapt_workflow(s["v2_workflow"], role_overlay=s["v2_overlay"])
    assert v1.adapter_mode == a2.CompilerAdapterMode.V1_FROZEN.value
    assert v2.adapter_mode == a2.CompilerAdapterMode.V2_SEMANTIC.value


def test_unknown_contract_fails_closed():
    env = compat.adapt_workflow({"ir_version": "workflow_ir.v9"})
    assert not env.ok
    assert env.diagnostics[0].code == a2.AdapterDiagnosticCode.UNSUPPORTED_COMPILER_CONTRACT.value


def test_v2_adapter_rejects_v1_document():
    s = C.load("procurement")
    env = a2.adapt_compiled_workflow_v2(s["v1_workflow"])  # top-level ir_version is v1
    assert not env.ok
    assert env.diagnostics[0].code == a2.AdapterDiagnosticCode.UNSUPPORTED_COMPILER_CONTRACT.value


def test_v1_path_frozen_fingerprint_matches_direct():
    s = C.load("procurement")
    direct = awc.adapt_compiled_workflow(s["v1_workflow"], role_overlay=s["v1_overlay"])
    viaenv = compat.adapt_workflow(s["v1_workflow"], role_overlay=s["v1_overlay"])
    assert viaenv.adaptation_result.adaptation_fingerprint == direct.adaptation_fingerprint


# -- v2 semantic consumption ------------------------------------------------ #

@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_v2_consumes_compiler_semantics(sid):
    s = C.load(sid)
    env = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    assert env.ok
    assert "required_capability_refs" in env.compiler_fields_consumed
    assert "semantic_purpose" in env.compiler_fields_consumed
    for r in env.adaptation_result.role_requirements:
        # role name comes from the compiler (semantic purpose), not the overlay
        assert r.role_name
        assert r.provenance.source_kind == "compiler_workflow_ir_v2"
        assert "compiler_contract=workflow_ir.v2" in r.provenance.notes


def test_v2_dependency_graph_from_compiler_not_reconstructed():
    s = C.load("procurement")
    env = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    g = env.role_dependency_graph
    assert g.dependencies  # built from compiler dependency_semantics
    for d in g.dependencies:
        assert d.provenance.source_kind == "compiler_workflow_ir_v2_dependency"


def test_v2_deterministic():
    s = C.load("procurement")
    a = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    b = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    assert a.adaptation_envelope_fingerprint == b.adaptation_envelope_fingerprint
    assert a.adaptation_result.adaptation_fingerprint == b.adaptation_result.adaptation_fingerprint


# -- overlay reduction ------------------------------------------------------ #

def test_reduce_overlay_removes_only_compiler_emitted_fields():
    s = C.load("procurement")
    reduced, removed = a2.reduce_overlay(s["v1_overlay"])
    # role_name is compiler-emitted -> removed
    assert any("role_name" in v for v in removed.values())
    # enterprise fields retained
    for node, fields in s["v1_overlay"].items():
        for k in fields:
            if k not in ("role_name", "role_description", "human_review_requirement"):
                assert k in reduced[node], f"{k} must be retained"


def test_enterprise_specialist_capability_retained_in_v2():
    # the domain-specialist capability the compiler does NOT emit must survive
    s = C.load("procurement")
    env = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    caps = {c for r in env.adaptation_result.role_requirements for c in r.required_capabilities}
    assert "evidence_extraction" in caps            # compiler functional capability
    assert any(c != "evidence_extraction" for c in caps)  # enterprise specialist retained


# -- authority preservation (monotonic) ------------------------------------ #

def test_overlay_cannot_remove_compiler_human_review():
    # craft a v2 doc where the compiler declares a human-review node that is ALSO
    # agent-eligible (synthetic), and an overlay that tries to remove the review.
    s = C.load("procurement")
    v2 = dict(s["v2_workflow"])
    sems = [dict(x) for x in v2["node_semantics"]]
    target = next(x for x in sems if x["role_relevance"] == "ADVISORY_AGENT_ELIGIBLE")
    hr = dict(target["human_review_requirement"]); hr["required"] = True
    target["human_review_requirement"] = hr
    v2["node_semantics"] = sems
    overlay = {target["node_id"]: {"human_review_requirement": False}}
    env = a2.adapt_compiled_workflow_v2(v2, role_overlay=overlay)
    codes = {d.code for d in env.diagnostics}
    assert a2.AdapterDiagnosticCode.OVERLAY_REMOVES_HUMAN_REVIEW.value in codes
    # fail closed: the review is NOT removed
    role = next(r for r in env.adaptation_result.role_requirements
                if r.source_node_id == target["node_id"])
    assert role.human_review_requirement is True


@pytest.mark.parametrize("sid", C.SCENARIOS)
def test_non_agent_and_authority_nodes_preserved(sid):
    s = C.load(sid)
    v1 = awc.adapt_compiled_workflow(s["v1_workflow"], role_overlay=s["v1_overlay"])
    env = a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])
    a = sorted(d.node_id for d in v1.non_agent_dispositions)
    b = sorted(d.node_id for d in env.adaptation_result.non_agent_dispositions)
    assert a == b  # governance/human/deterministic nodes identical, never agentified
