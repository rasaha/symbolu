"""Boundary test (spec §1): neither slice 1 package imports the experimental
reasoning runtime, the contracts package never imports the engine package, and
agent-value-readiness imports neither.

Static AST scan over every module under each package's ``src``. A dynamic
import of a literal module name is read as an import.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[5]
CONTRACTS_SRC = REPO / "packages" / "capabilities" / "reasoning-method-governance" / "src" / "ugence_reasoning_method_governance"
ENGINE_SRC = REPO / "packages" / "capabilities" / "readiness-comparison" / "src" / "ugence_readiness_comparison"
AVR_SRC = REPO / "packages" / "capabilities" / "agent-value-readiness" / "src" / "ugence_agent_value_readiness"

RUNTIME_FORBIDDEN = {"agentic", "agentic_framework", "reasoning_workflows", "adaptive_prompts", "external_actions", "symbolu"}
FORBIDDEN_NAMES = {"WorkflowResult", "WorkflowType", "WorkflowRegistry", "WorkflowSelector"}
CAPABILITY_FORBIDDEN = {"ugence_context_minimization", "ugence_agent_value_readiness", "governed_value", "ugence_policy_authority"}


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, ()
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module, tuple(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in ("import_module", "__import__") and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                yield node.args[0].value, ()


def _violations(src: pathlib.Path, forbidden_modules: set, forbidden_names: set = frozenset()):
    out = []
    for path in sorted(src.rglob("*.py")):
        where = path.relative_to(REPO) if REPO in path.parents else path.name
        for module, names in _imports(path):
            top = module.split(".")[0]
            if top in forbidden_modules:
                out.append(f"{where}: imports {module}")
            for n in names:
                if n in forbidden_names:
                    out.append(f"{where}: imports name {n} from {module}")
    return out


@pytest.mark.parametrize("src", [CONTRACTS_SRC, ENGINE_SRC])
def test_no_runtime_import(src):
    assert src.is_dir()
    assert _violations(src, RUNTIME_FORBIDDEN, FORBIDDEN_NAMES) == []


@pytest.mark.parametrize("src", [CONTRACTS_SRC, ENGINE_SRC])
def test_no_capability_import(src):
    assert _violations(src, CAPABILITY_FORBIDDEN) == []


def test_contracts_never_import_engine():
    assert _violations(CONTRACTS_SRC, {"ugence_readiness_comparison"}) == []


def test_agent_value_readiness_imports_neither():
    assert AVR_SRC.is_dir()
    assert _violations(AVR_SRC, {"ugence_reasoning_method_governance", "ugence_readiness_comparison"}) == []


def test_negative_control_scanner_sees_a_forbidden_import(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from agentic.agentic_framework.reasoning_workflows import WorkflowResult\nimport importlib\nimportlib.import_module('adaptive_prompts')\n")
    found = _violations(tmp_path, RUNTIME_FORBIDDEN, FORBIDDEN_NAMES)
    assert len(found) == 3
