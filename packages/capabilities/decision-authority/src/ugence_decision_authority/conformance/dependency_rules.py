"""Dependency dimension — the kernel imports nothing from a consuming layer."""
from __future__ import annotations

import ast
import pathlib

from .results import fail, ok

_KERNEL_ROOT = pathlib.Path(__file__).resolve().parents[1]
_FORBIDDEN_ROOTS = ("ai_hiring", "domains", "applications")


def check(fixture, platform, outcome):
    violations = []
    for path in _KERNEL_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            target = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _FORBIDDEN_ROOTS:
                        target = alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                if node.module.split(".")[0] in _FORBIDDEN_ROOTS:
                    target = node.module
            if target:
                violations.append(f"{path.name}:{node.lineno} -> {target}")
    if violations:
        return [fail("dependency_rules", "kernel_is_a_leaf", "; ".join(violations[:5]))]
    return [ok("dependency_rules", "kernel_is_a_leaf")]
