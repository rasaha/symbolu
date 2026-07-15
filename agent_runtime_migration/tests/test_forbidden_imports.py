"""Research-isolation + no-duplicate-authority enforcement (AST).

Proves the migration package imports NONE of the legacy runtime, the research-only
signal code, or the duplicate governance authority. If this fails, the migration's
clean-boundary claim is void.
"""
from __future__ import annotations

import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, ".."))

# Forbidden top-level packages entirely.
FORBIDDEN_TOP = {"agentic"}
# Forbidden module basenames anywhere in a dotted path (research + duplicate governance).
FORBIDDEN_NAMES = {
    # research-only signal governance
    "jepa_governance", "cg_tool_dispatcher", "sovereign_bridge", "coherence_tracker",
    "signal_adapters", "signal_config", "shadow_ai", "chitta_vritti", "olm_bridge",
    "request_enrichment", "inference_mistral",
    # duplicate governance authority
    "mcp_gateway", "safety_contract", "governance_service", "governance_adapter",
    "governance_api", "governance_models", "confidence_gate", "approval",
    "approval_workflow", "approval_coverage", "policy_bundle", "policy_replay",
    "domain_policy", "adaptive_policy", "duration_policy",
}


# Evaluation harnesses that DELIBERATELY import the legacy runtime to compare against
# it are not part of the production runtime import path and are excluded from this scan.
_EXCLUDED_DIRS = (f"{os.sep}tests", f"{os.sep}parity")


def _py_files():
    for root, _dirs, files in os.walk(PKG):
        if "__pycache__" in root or any(d in root for d in _EXCLUDED_DIRS):
            continue
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def _module_names(path):
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module


def test_no_forbidden_imports():
    offenders = []
    for path in _py_files():
        for mod in _module_names(path):
            parts = mod.split(".")
            if parts[0] in FORBIDDEN_TOP:
                offenders.append((os.path.relpath(path, PKG), mod))
            if set(parts) & FORBIDDEN_NAMES:
                offenders.append((os.path.relpath(path, PKG), mod))
    assert not offenders, f"forbidden imports in the migration runtime: {offenders}"


def test_production_import_does_not_pull_legacy_or_research():
    # Importing the production package must NOT load any module from the legacy
    # ``agentic`` runtime. Checked in a CLEAN subprocess so it is not contaminated by
    # other tests (e.g. the parity harness) that legitimately import the legacy runtime.
    import subprocess
    import sys
    code = (
        "import sys, agent_runtime_migration\n"
        "leaked=[m for m in sys.modules if m=='agentic' or m.startswith('agentic.')]\n"
        "print('LEAKED:'+','.join(leaked))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=PKG + "/..")
    assert proc.returncode == 0, proc.stderr
    line = [l for l in proc.stdout.splitlines() if l.startswith("LEAKED:")][0]
    leaked = [x for x in line[len("LEAKED:"):].split(",") if x]
    assert not leaked, f"legacy/research modules leaked into sys.modules: {leaked}"
