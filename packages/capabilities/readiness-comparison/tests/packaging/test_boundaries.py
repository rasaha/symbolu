"""The engine package imports no runtime, no capability beyond its declared
contract dependencies, and performs no I/O or clock reads beyond produced_at."""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[5]
SRC = REPO / "packages" / "capabilities" / "readiness-comparison" / "src" / "ugence_readiness_comparison"

ALLOWED_TOP_LEVEL = {
    "ugence_reasoning_method_governance", "ugence_governance_contracts", "ugence_uvi_policy_contracts", "ugence_jcs",
    "datetime", "decimal", "typing", "__future__", "dataclasses", "enum",
}
# Bare-name calls that would mean I/O, a clock, or dynamic code in a pure engine.
# (Attribute calls such as dict.get are not I/O; network access is excluded by the
# import allowlist above.)
FORBIDDEN_CALLS = {"open", "input", "print", "exec", "eval", "compile", "__import__"}


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_only_declared_imports():
    seen = set()
    for path in SRC.rglob("*.py"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Import):
                seen.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                seen.add(node.module.split(".")[0])
    assert seen <= ALLOWED_TOP_LEVEL, seen - ALLOWED_TOP_LEVEL


def test_no_io_calls_in_engine():
    for path in SRC.rglob("*.py"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, f"{path.name} calls {node.func.id}"


def test_static_pyproject_version_matches_package_version():
    import re

    from ugence_readiness_comparison import __version__

    text = (REPO / "packages" / "capabilities" / "readiness-comparison" / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == __version__


def test_single_clock_read_is_produced_at_default_only():
    engine = (SRC / "engine.py").read_text(encoding="utf-8")
    assert engine.count("datetime.now(") == 1
