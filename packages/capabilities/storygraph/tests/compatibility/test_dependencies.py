"""S7 — dependency compliance (no prohibited cross-capability imports).

AST-scans every module in ``ugence_storygraph`` and asserts it imports only the
Python standard library and itself — never ActionGate, ACP, Decision Governance,
Agent Runtime, console/API, product, or research packages, and no third-party
runtime dependency. This is the machine guard that StoryGraph stays a leaf
capability (its advisory results flow through public contracts, not authority
imports).
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_storygraph

PKG_ROOT = pathlib.Path(ugence_storygraph.__file__).resolve().parent
SELF = "ugence_storygraph"

# Explicitly prohibited capability / product / research / console roots.
PROHIBITED_ROOTS = {
    "action_gate", "action_gateway", "action_gate_reference", "actiongate_provider",
    "acp", "autonomous_control_plane", "symbolu_robotics",
    "decision_governance", "governance_providers", "cer_v0_1", "cer_v0_2", "cer_v0_3",
    "agent_runtime_migration", "agentic", "agent_runtime_v2",
    "ugence_console_api", "tap_provider", "assertion_governance",
    "experiments", "model_selection_pilot", "hybrid_handover", "symbolu_training",
    "cyber_security", "composite_threat_detector",
    # third-party runtime deps StoryGraph must not acquire
    "pydantic", "numpy", "torch", "pandas", "fastapi", "requests",
}

_STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def _iter_module_files():
    for p in PKG_ROOT.rglob("*.py"):
        yield p


def _top_level_imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — internal, fine
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_prohibited_imports_anywhere():
    offenders = {}
    for path in _iter_module_files():
        bad = _top_level_imports(path) & PROHIBITED_ROOTS
        if bad:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, f"prohibited imports found: {offenders}"


def test_only_stdlib_and_self_imports():
    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for path in _iter_module_files():
        for root in _top_level_imports(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    # Fail loudly if any non-stdlib, non-self absolute import appears.
    assert not strays, f"unexpected non-stdlib/self imports: {strays}"
