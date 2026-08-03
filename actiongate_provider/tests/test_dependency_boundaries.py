"""ActionGate dependency + authority boundaries (post canonical-migration, monorepo view).

The ActionGate implementation now lives in the canonical package
``ugence_actiongate_provider`` (``packages/providers/actiongate/src``);
``actiongate_provider`` is a logic-free compatibility facade. These monorepo checks
enforce the same frozen boundaries against the canonical source tree and prove the
facade preserves them:

    ugence_actiongate_provider       must not import tap_provider / ugence_tap_provider
    ugence_actiongate_provider core  must import neither the framework nor the kernel
    actiongate_provider (facade)     must not import TAP or carry ActionGate logic
    kernel / framework               must not import ActionGate
    ActionGateProvider               exposes no dispatch / execute surface (authorize only)

Authoritative test for frozen invariant F7 (action governance does not determine
assertion truth) and the authorization-only boundary.
"""

from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL_SRC = REPO / "packages" / "providers" / "actiongate" / "src" / "ugence_actiongate_provider"
FACADE = REPO / "actiongate_provider"
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "governance_providers"

_TAP_ROOTS = {"tap_provider", "ugence_tap_provider"}
_FRAMEWORK_KERNEL_ROOTS = {
    "governance_providers", "ugence_governance_provider_framework",
    "decision_governance", "ugence_decision_authority",
    "ugence_governance_contracts",
}


def _imports(root: pathlib.Path, *, subdir: pathlib.Path | None = None,
             only_file: pathlib.Path | None = None):
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


def test_kernel_never_imports_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(KERNEL)
           if m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")]
    assert not bad, bad


def test_framework_never_imports_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(FRAMEWORK)
           if m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")]
    assert not bad, bad


def test_canonical_never_imports_tap():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(CANONICAL_SRC)
           if m.split(".")[0] in _TAP_ROOTS]
    assert not bad, "ActionGate and TAP must be mutually unaware:\n" + "\n".join(bad)


def test_canonical_core_imports_neither_framework_nor_kernel():
    """The vendor core (``core.py``) and the client seam are pure."""
    bad = [f"core.py:{ln}->{m}"
           for _p, ln, m in _imports(CANONICAL_SRC, only_file=CANONICAL_SRC / "core.py")
           if m.split(".")[0] in _FRAMEWORK_KERNEL_ROOTS | _TAP_ROOTS]
    bad += [f"client:{ln}->{m}"
            for _p, ln, m in _imports(CANONICAL_SRC,
                                      only_file=CANONICAL_SRC / "client" / "__init__.py")
            if m.split(".")[0] in _FRAMEWORK_KERNEL_ROOTS | _TAP_ROOTS]
    assert not bad, bad


def test_canonical_consumes_only_framework_public_api():
    """ActionGate consumes only the framework's public ``.api`` surface (no deep reach),
    and never imports the kernel directly."""
    bad = []
    for p, ln, m in _imports(CANONICAL_SRC):
        root = m.split(".")[0]
        if m.startswith("ugence_governance_provider_framework.") \
                and not m.startswith("ugence_governance_provider_framework.api"):
            bad.append(f"{p.name}:{ln}->{m}")
        if root in ("decision_governance", "ugence_decision_authority"):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "ActionGate must consume only the framework public API:\n" + "\n".join(bad)


def test_facade_carries_no_actiongate_logic_and_no_tap():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(FACADE)
           if m.split(".")[0] in _TAP_ROOTS]
    assert not bad, bad


def test_actiongate_provider_has_no_execution_surface():
    """F7 / authorization-only: ActionGate authorizes but never dispatches/executes."""
    from actiongate_provider.configuration import build_actiongate_provider
    from actiongate_provider.core import ActionGateEngine

    provider = build_actiongate_provider(ActionGateEngine())
    assert hasattr(provider, "authorize")
    for forbidden in ("dispatch", "execute", "observe", "reconcile", "compensate"):
        assert not hasattr(provider, forbidden), forbidden


def test_facade_preserves_object_identity():
    import actiongate_provider.api as legacy
    import ugence_actiongate_provider.api as canon
    assert legacy is canon
    assert list(legacy.__all__) == list(canon.__all__)
    for name in canon.__all__:
        assert getattr(legacy, name) is getattr(canon, name), name


def test_canonical_imports_standalone_without_cycles():
    code = ("import ugence_actiongate_provider.api, ugence_actiongate_provider.conformance, "
            "ugence_actiongate_provider.configuration; print('ok')")
    env_src = [
        str(REPO / "packages" / "providers" / "actiongate" / "src"),
        str(REPO / "packages" / "governance-provider-framework" / "src"),
        str(REPO / "packages" / "governance-contracts" / "src"),
    ]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(env_src))
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
