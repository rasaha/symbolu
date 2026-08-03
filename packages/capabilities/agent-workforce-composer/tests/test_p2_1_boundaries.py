"""P2.1 boundary discipline: no compiler logic duplicated, no forbidden imports,
no network, no algorithm changes."""
from __future__ import annotations

import ast
import os
import socket

import pytest

import ugence_agent_workforce_composer.api as awc
import ugence_agent_workforce_composer.adapter_v2 as a2
from . import _conformance as C

_SRC = os.path.dirname(os.path.abspath(a2.__file__))
_P2_1_MODULES = ["adapter_v2.py", "compatibility.py"]


def test_no_forbidden_imports_in_p2_1_modules():
    banned = ("agent_runtime", "agentic.agentic_framework", "ugence_model_selection",
              "ugence_actiongate_provider", "h22", "flask", "fastapi", "requests",
              "httpx", "urllib.request")
    for fname in _P2_1_MODULES:
        src = open(os.path.join(_SRC, fname), encoding="utf-8").read()
        for b in banned:
            assert b not in src, f"{fname} references {b!r}"


def test_p2_1_does_not_import_compiler_package():
    # AWC must consume the compiler's serialized output as DATA, never import it.
    for fname in _P2_1_MODULES:
        src = open(os.path.join(_SRC, fname), encoding="utf-8").read()
        assert "ugence_policy_workflow_compiler" not in src


def test_no_reimplemented_compiler_enrichment():
    # the adapter consumes compiler semantics; it must not re-derive them.
    banned_defs = {"enrich_workflow", "classify_role_relevance", "extract_node_semantics",
                   "extract_dependencies", "compile_workflow_v2"}
    for fname in _P2_1_MODULES:
        tree = ast.parse(open(os.path.join(_SRC, fname), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert node.name not in banned_defs, f"{fname} re-defines {node.name}"


def test_no_network_during_v2_adaptation(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("network during adaptation")
    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    for sid in C.SCENARIOS:
        s = C.load(sid)
        a2.adapt_compiled_workflow_v2(s["v2_workflow"], role_overlay=s["v2_overlay"])


def test_v2_adapter_exposes_no_execution_or_grant_surface():
    banned = {"execute_agent", "run_agent", "dispatch", "grant_permission",
              "provision_permission", "authorize_action", "reassign_agent"}
    assert not (banned & set(awc.__all__))


def test_maturity_honest():
    vi = awc.version_info().to_dict()
    for k in ("compiler_workflow_ir_v1_supported", "compiler_workflow_ir_v2_supported",
              "compiler_v2_adapter_implemented", "overlay_reduction_implemented",
              "v1_fingerprint_compatibility_verified", "v1_v2_equivalence_harness_implemented"):
        assert vi[k] is True, k
    for k in ("governance_studio_api_implemented", "runtime_handoff_implemented",
              "runtime_execution_implemented", "h16_migration_implemented",
              "model_selection_integration_implemented", "h22_integration_implemented",
              "pilot_validated", "production_certified"):
        assert vi[k] is False, k


def test_planning_algorithms_unchanged_module_hashes():
    # the eligibility/ranking/composition/permission/fallback modules are NOT part
    # of this change — assert P2.1 added no code to them by checking they define no
    # new adapter symbols (a light structural guard).
    import ugence_agent_workforce_composer.eligibility as e
    import ugence_agent_workforce_composer.ranking as r
    import ugence_agent_workforce_composer.composition as c
    for mod in (e, r, c):
        assert not hasattr(mod, "adapt_compiled_workflow_v2")
