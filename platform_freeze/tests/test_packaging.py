"""Freeze-tooling packaging + out-of-band guarantees (Task 16)."""
from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
BUILD = REPO / "packaging" / "dgm-platform-freeze-tooling"


def test_symlink_points_to_canonical():
    link = BUILD / "platform_freeze"
    assert link.is_symlink()
    assert link.resolve() == (REPO / "platform_freeze").resolve()


def test_distribution_metadata():
    from platform_freeze.version import __version__
    assert __version__ == "0.1.0"
    text = (BUILD / "pyproject.toml").read_text()
    assert 'name = "dgm-platform-freeze-tooling"' in text
    assert 'attr = "platform_freeze.version.__version__"' in text
    assert 'include = ["platform_freeze*"]' in text
    assert "platform_freeze.tests" in text


def test_tooling_is_out_of_band():
    # the frozen platform packages must never import the freeze tooling
    import ast
    for pkg in ("decision_governance", "governance_providers", "actiongate_provider",
                "tap_provider"):
        for p in (REPO / pkg).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            for node in ast.walk(ast.parse(p.read_text())):
                if isinstance(node, ast.Import):
                    assert all(a.name.split(".")[0] != "platform_freeze" for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert node.module.split(".")[0] != "platform_freeze", p
