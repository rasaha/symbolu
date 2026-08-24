"""Leaf-boundary proof: ugence-jcs depends on the standard library and nothing else.

The extraction is only sound if the canonicalizer stayed authority-neutral and
dependency-free. These tests statically scan the package's own source, then load
the public API in an isolated subprocess to prove no forbidden module is imported
at runtime either.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "ugence_jcs"
STDLIB = set(getattr(sys, "stdlib_module_names", set()))

#: The clean-room independence boundary the extraction must preserve, plus the
#: authority capabilities a canonicalization substrate must never reach.
FORBIDDEN = {
    "action_gate_ref", "cer_v0_1", "cer_v0_2", "cer_v0_3", "symbolu_robotics",
    "ugence_decision_authority", "ugence_actiongate_provider",
    "ugence_action_clearance", "ugence_agent_runtime", "agentic",
    "control_plane", "cloud_controller",
    "requests", "httpx", "openai", "anthropic",
}


def _sources():
    return sorted(SRC.rglob("*.py"))


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], 0
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            yield (mod.split(".")[0] if mod else ""), node.level


def test_sources_import_only_stdlib():
    offenders = []
    for path in _sources():
        for top, level in _imports(path):
            if level > 0 or not top or top == "ugence_jcs":
                continue
            if top not in STDLIB:
                offenders.append((path.name, top))
    assert not offenders, f"non-stdlib import in ugence_jcs: {offenders}"


def test_sources_import_nothing_forbidden():
    offenders = []
    for path in _sources():
        for top, level in _imports(path):
            if level == 0 and top in FORBIDDEN:
                offenders.append((path.name, top))
    assert not offenders, f"forbidden import in ugence_jcs: {offenders}"


def test_isolated_import_loads_no_forbidden_module():
    probe = (
        "import sys, json\n"
        "import ugence_jcs\n"
        "ugence_jcs.canonical_bytes({'a': '1'})\n"
        "print(json.dumps(sorted(m.split('.')[0] for m in sys.modules)))\n"
    )
    res = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         cwd=str(SRC.parent), check=True)
    import json
    loaded = set(json.loads(res.stdout.strip().splitlines()[-1]))
    assert not (loaded & FORBIDDEN), f"forbidden module loaded: {sorted(loaded & FORBIDDEN)}"


def test_package_declares_no_runtime_dependencies():
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert "dependencies = []" in pyproject


def test_package_defines_no_authority_vocabulary():
    """A canonicalization substrate emits no decision, authorization or clearance term."""
    reserved = ("AUTHORIZED", "DENIED", "CLEARANCE", "ALLOW", "BLOCK",
                "INDETERMINATE", "APPROVE")
    for path in _sources():
        body = path.read_text(encoding="utf-8")
        for term in reserved:
            assert term not in body, f"{path.name} mentions reserved term {term!r}"
