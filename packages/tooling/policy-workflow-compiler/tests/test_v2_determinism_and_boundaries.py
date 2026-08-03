"""Determinism, ordering independence, and the P2 ownership/leakage boundary."""

from __future__ import annotations

import socket

import pytest

from ugence_policy_workflow_compiler.semantics import (
    compile_workflow_v2,
    enrich_workflow,
    upgrade_workflow_ir,
)
import _v2_helpers as H


# -- determinism ------------------------------------------------------------ #

def test_identical_inputs_identical_fingerprints():
    ir = H.procurement_ir()
    assert enrich_workflow(ir, compiler_version="x").workflow_fingerprint == \
        enrich_workflow(ir, compiler_version="x").workflow_fingerprint


def test_enrichment_adds_no_ordering_sensitivity():
    # The v1 node/edge order is canonical compiler output. Enrichment must add no
    # order sensitivity of its own: reordering the input nodes leaves the enriched
    # SEMANTIC content (node-semantics and dependency fingerprints) invariant, and
    # the enrichment always emits node semantics in canonical (node_id) order.
    ir = H.cybersecurity_success_ir()
    reordered = ir.model_copy(update={"nodes": tuple(reversed(ir.nodes))})
    a = enrich_workflow(ir, compiler_version="x")
    b = enrich_workflow(reordered, compiler_version="x")
    assert {s.fingerprint for s in a.node_semantics} == {s.fingerprint for s in b.node_semantics}
    assert {d.fingerprint for d in a.dependency_semantics} == \
        {d.fingerprint for d in b.dependency_semantics}
    assert [s.node_id for s in a.node_semantics] == sorted(s.node_id for s in a.node_semantics)


def test_replay_upgrade_matches_compile():
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )
    pack = build_procurement_policy_pack()
    appr = build_procurement_approval_fixture(pack)
    v2 = compile_workflow_v2(pack, appr, require_approval=True)
    up = upgrade_workflow_ir(v2.base_ir, compiler_version=v2.compiler_version)
    assert up.workflow_fingerprint == v2.workflow_fingerprint


def test_no_network_during_enrichment(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network access during enrichment")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    for build in H.P3A_SCENARIOS.values():
        enrich_workflow(build(), compiler_version="x")


# -- ownership / leakage boundary ------------------------------------------ #

def test_compiler_never_imports_awc_or_runtime():
    import ugence_policy_workflow_compiler.semantics.extraction as ext
    import ugence_policy_workflow_compiler.semantics.models as mod
    import ugence_policy_workflow_compiler.validation.release_validator as rv
    src = ""
    for m in (ext, mod, rv):
        with open(m.__file__, encoding="utf-8") as fh:
            src += fh.read()
    for banned in ("ugence_agent_workforce_composer", "agent_runtime", "ugence_model_selection",
                   "agentic.agentic_framework", "ugence_actiongate_provider.execute"):
        assert banned not in src, f"P2 module imports/leaks {banned!r}"


def test_no_selection_or_ranking_vocabulary_in_public_api():
    import ugence_policy_workflow_compiler.api as api
    banned = {"eligibility", "rank", "ranking", "compose", "team", "fallback",
              "select_agent", "grant_permission", "authorize_action", "execute"}
    for name in api.__all__:
        low = name.lower()
        assert not any(b in low for b in banned), f"api exports selection/ranking name {name!r}"


def test_v2_carries_no_enterprise_policy_values():
    v2 = enrich_workflow(H.procurement_ir(), compiler_version="x")
    blob = v2.model_dump_json()
    # no provider allowlist, residency, cost/latency ceilings, concentration limits
    for token in ("anthropic", "openai", "provider_concentration", "cost_ceiling",
                  "residency", "maximum_roles_per_agent", "ranking_weight"):
        assert token not in blob
