"""Phase 5E — kernel dependency rules & import hygiene.

Automatically enforces the architectural boundaries now that two independent
domains depend on the kernel:

* the kernel imports nothing from a consuming layer (``ai_hiring`` / ``domains`` /
  ``applications``);
* the kernel (and its public ``api``) import standalone with no consuming layer
  present — the third-party-consumer condition;
* no circular imports across the kernel's own modules.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

KERNEL_ROOT = pathlib.Path(__file__).resolve().parents[1]
FORBIDDEN_ROOTS = ("ai_hiring", "domains", "applications")


def _kernel_modules():
    for p in KERNEL_ROOT.rglob("*.py"):
        if "__pycache__" in p.parts or "tests" in p.parts:
            continue
        yield p


def test_kernel_never_imports_a_consuming_layer():
    violations = []
    for path in _kernel_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                targets = [node.module]
            for t in targets:
                if t.split(".")[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path.relative_to(KERNEL_ROOT)}:{node.lineno} -> {t}")
    assert not violations, "kernel imports a consuming layer:\n" + "\n".join(violations)


def test_kernel_imports_standalone_as_a_third_party_package():
    code = (
        "import decision_governance, decision_governance.api, "
        "decision_governance.conformance, decision_governance.services, "
        "decision_governance.audit, decision_governance.policy, sys; "
        "leaked=[m for m in sys.modules "
        "if m.split('.')[0] in ('ai_hiring','domains','applications')]; "
        "assert not leaked, leaked; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_all_kernel_modules_import_without_cycles():
    """Import every kernel module fresh in one interpreter — a cycle would raise."""
    modules = sorted(
        ".".join(p.relative_to(KERNEL_ROOT.parent).with_suffix("").parts)
        for p in _kernel_modules()
    )
    # Drop dunder-main-ish and keep importable module paths.
    modules = [m for m in modules if not m.endswith("__init__")]
    code = "import importlib, sys\n"
    code += "mods = " + repr(modules) + "\n"
    code += "[importlib.import_module(m) for m in mods]\n"
    code += "print('imported', len(mods))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "imported" in result.stdout


def test_public_api_is_importable_in_isolation():
    code = (
        "from decision_governance.api import services, contracts, ports, "
        "repositories, vocabulary, audit, identity, policy, errors, common; "
        "print('api-ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "api-ok" in result.stdout
