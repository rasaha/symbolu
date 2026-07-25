"""Phase 5H — TAP dependency rules (enforced).

    decision_governance   must not import governance_providers / *_provider
    governance_providers   must not import actiongate_provider / tap_provider
    actiongate_provider    must not import tap_provider
    tap_provider           must not import actiongate_provider; public APIs only
    TAP core               must import neither DGM nor governance_providers
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "governance_providers"
ACTIONGATE = REPO / "actiongate_provider"
TAP = REPO / "tap_provider"


def _imports(root: pathlib.Path, *, only_file: pathlib.Path | None = None,
             subdir: pathlib.Path | None = None):
    if only_file is not None:
        files = [only_file]
    elif subdir is not None:
        files = [p for p in subdir.rglob("*.py") if "__pycache__" not in p.parts]
    else:
        files = [p for p in root.rglob("*.py")
                 if "__pycache__" not in p.parts and "tests" not in p.parts]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_kernel_never_imports_tap():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(KERNEL)
           if m.split(".")[0] == "tap_provider"]
    assert not bad, bad


def test_framework_never_imports_tap():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(FRAMEWORK)
           if m.split(".")[0] == "tap_provider"]
    assert not bad, bad


def test_actiongate_never_imports_tap():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(ACTIONGATE)
           if m.split(".")[0] == "tap_provider"]
    assert not bad, bad


def test_tap_never_imports_actiongate():
    # The TAP *package* source (excluding tests) must never import ActionGate.
    # The application-layer peer-composition fixture in test_end_to_end.py may
    # import both to prove they coexist as mutually-unaware peers.
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(TAP)
           if m.split(".")[0] == "actiongate_provider"]
    assert not bad, "TAP and ActionGate must be mutually unaware:\n" + "\n".join(bad)


def test_tap_imports_only_public_apis():
    bad = []
    for p, ln, m in _imports(TAP):
        root = m.split(".")[0]
        if root == "decision_governance" and not m.startswith("decision_governance.api") \
                and not m.startswith("decision_governance.errors"):
            bad.append(f"{p.name}:{ln}->{m}")
        if root == "governance_providers" and not (
                m.startswith("governance_providers.api")
                or m.startswith("governance_providers.conformance")):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "TAP must consume only public APIs:\n" + "\n".join(bad)


def test_tap_core_imports_neither_dgm_nor_framework():
    """The vendor core (core/) is pure."""
    bad = [f"{_p.name}:{ln}->{m}"
           for _p, ln, m in _imports(TAP, subdir=TAP / "core")
           if m.split(".")[0] in ("decision_governance", "governance_providers",
                                   "actiongate_provider")]
    assert not bad, bad
    # the client seam is core-only too
    client = TAP / "client" / "__init__.py"
    bad_client = [f"{ln}->{m}" for _p, ln, m in _imports(TAP, only_file=client)
                  if m.split(".")[0] in ("decision_governance", "governance_providers",
                                         "actiongate_provider")]
    assert not bad_client, bad_client


def test_tap_imports_standalone_without_cycles():
    code = ("import tap_provider.api, tap_provider.conformance, "
            "tap_provider.configuration; print('ok')")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=str(REPO))
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
