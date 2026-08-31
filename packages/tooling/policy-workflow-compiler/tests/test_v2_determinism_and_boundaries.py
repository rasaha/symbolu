"""Determinism, ordering independence, and the P2 ownership/leakage boundary."""

from __future__ import annotations

import ast
import os
import pathlib
import socket
import subprocess
import sys

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

#: Distributions the compiler must never depend on. AWC is listed because the
#: compiler->AWC seam is DATA-ONLY in both directions: AWC mirrors the IR
#: vocabulary by value (see AWC ``contracts.py``) and bans the compiler from its
#: own source (see AWC ``tests/test_boundaries.py``). A core edge either way
#: would close a distribution cycle through AWC's ``compiler-reference`` extra.
_FORBIDDEN_ROOTS = frozenset({
    "ugence_agent_workforce_composer",
    "agent_runtime",
    "agent_runtime_v2",
    "agent_runtime_migration",
    "ugence_model_selection",
    "agentic",
    "ugence_actiongate_provider",
})


def _compiler_src_root() -> pathlib.Path:
    import ugence_policy_workflow_compiler as pkg
    return pathlib.Path(pkg.__file__).resolve().parent


def test_compiler_never_imports_awc_or_runtime():
    """No module in the distribution imports a forbidden root.

    Scoped to the whole package, not a hand-listed few. The earlier version read
    three named files, so a forbidden import added anywhere else -- including in
    ``serialization/``, which every emitted digest flows through -- passed
    unnoticed while this assertion still claimed the compiler never imports AWC.
    """
    offenders = []
    for path in _compiler_src_root().rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            roots = []
            if isinstance(node, ast.Import):
                roots = [n.name.split(".")[0] for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            for root in roots:
                if root in _FORBIDDEN_ROOTS:
                    offenders.append(f"{path.name}: imports {root}")
    assert not offenders, offenders


def test_importing_api_does_not_load_forbidden_modules():
    """The *transitive* check: a static scan cannot see a deferred or aliased
    import, so import the public API clean and inspect ``sys.modules``.

    Runs in an isolated subprocess so a sibling test (e.g. the procurement
    equivalence harness) cannot pollute ``sys.modules`` and mask a real edge.
    """
    code = (
        "import ugence_policy_workflow_compiler.api, sys;"
        "banned=%r;"
        "hit=[b for b in banned if b in sys.modules];"
        "print('HIT:'+','.join(hit)); sys.exit(1 if hit else 0)"
    ) % (sorted(_FORBIDDEN_ROOTS),)
    env = dict(os.environ)
    # Prepend rather than replace: a CI runner may already rely on PYTHONPATH.
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_compiler_src_root().parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    result = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stdout + result.stderr


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
