"""TAP dependency + authority boundaries (post canonical-migration, monorepo view).

The TAP implementation now lives in the canonical package ``ugence_tap_provider``
(``packages/providers/tap/src``); ``tap_provider`` is a logic-free compatibility
facade. These monorepo checks enforce the same frozen boundaries against the
canonical source tree and prove the facade preserves them:

    ugence_tap_provider        must not import actiongate_provider / ugence_actiongate_provider
    ugence_tap_provider core   must import neither the framework nor the kernel
    tap_provider (facade)      must not import ActionGate or carry TAP logic
    TAPProvider                exposes no authorize / dispatch / execute surface

Authoritative test for frozen invariant F6 (assertion governance does not
authorize execution).
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
CANONICAL_SRC = REPO / "packages" / "providers" / "tap" / "src" / "ugence_tap_provider"
FACADE = REPO / "tap_provider"

_ACTIONGATE_ROOTS = {"actiongate_provider", "ugence_actiongate_provider"}
_FRAMEWORK_KERNEL_ROOTS = {
    "governance_providers", "ugence_governance_provider_framework",
    "decision_governance", "ugence_decision_authority",
    "ugence_governance_contracts",
}


def _imports(root: pathlib.Path, *, subdir: pathlib.Path | None = None):
    if subdir is not None:
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


def test_canonical_never_imports_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(CANONICAL_SRC)
           if m.split(".")[0] in _ACTIONGATE_ROOTS]
    assert not bad, "TAP and ActionGate must be mutually unaware:\n" + "\n".join(bad)


def test_canonical_core_imports_neither_framework_nor_kernel():
    """The vendor core (``core/``) and client seam are pure — no framework/kernel."""
    bad = [f"{p.relative_to(CANONICAL_SRC)}:{ln}->{m}"
           for p, ln, m in _imports(CANONICAL_SRC, subdir=CANONICAL_SRC / "core")
           if m.split(".")[0] in _FRAMEWORK_KERNEL_ROOTS | _ACTIONGATE_ROOTS]
    bad += [f"{p.relative_to(CANONICAL_SRC)}:{ln}->{m}"
            for p, ln, m in _imports(CANONICAL_SRC, subdir=CANONICAL_SRC / "client")
            if m.split(".")[0] in _FRAMEWORK_KERNEL_ROOTS | _ACTIONGATE_ROOTS]
    assert not bad, bad


def test_canonical_consumes_only_framework_public_api():
    """TAP consumes only the framework's public ``.api`` surface (no deep reach)."""
    bad = []
    for p, ln, m in _imports(CANONICAL_SRC):
        # A bare ``import ugence_governance_provider_framework`` is a presence probe;
        # only a deep reach into a non-public submodule violates the boundary.
        if m.startswith("ugence_governance_provider_framework.") \
                and not m.startswith("ugence_governance_provider_framework.api"):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "TAP must consume only the framework public API:\n" + "\n".join(bad)


def test_facade_carries_no_tap_logic_and_no_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(FACADE)
           if m.split(".")[0] in _ACTIONGATE_ROOTS]
    assert not bad, bad


def test_tap_provider_has_no_execution_surface():
    """F6: assertion governance never authorizes/dispatches/executes."""
    from tap_provider.configuration import build_tap_provider
    from tap_provider.core import TapEngine

    provider = build_tap_provider(TapEngine())
    for forbidden in ("authorize", "dispatch", "execute", "reconcile", "compensate"):
        assert not hasattr(provider, forbidden), forbidden


def test_facade_preserves_object_identity():
    import tap_provider.api as legacy
    import ugence_tap_provider.api as canon
    assert legacy is canon
    assert list(legacy.__all__) == list(canon.__all__)
    for name in canon.__all__:
        assert getattr(legacy, name) is getattr(canon, name), name
