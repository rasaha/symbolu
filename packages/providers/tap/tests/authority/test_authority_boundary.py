"""Assertion-only authority boundary (canonical package).

TAP owns assertion-support evaluation only. It must expose no authorize / dispatch
/ execute / reconcile / compensate surface, must be an ASSERTION_GOVERNANCE
provider (never an action-governance kind), and its core must never reach an
ActionGate module or a kernel action control-plane port.
"""
from __future__ import annotations

import ast
import pathlib
import sys

from ugence_governance_provider_framework.api import ProviderKind
from ugence_tap_provider.configuration import build_tap_provider
from ugence_tap_provider.core import TapEngine
from ugence_tap_provider.provider import TAPProvider

CANON = pathlib.Path(__file__).resolve().parents[2] / "src" / "ugence_tap_provider"


def _module_names():
    for p in CANON.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(), filename=str(p))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield p, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield p, node.module


def test_provider_kind_is_assertion_governance():
    d = build_tap_provider(TapEngine()).descriptor()
    assert d.kind is ProviderKind.ASSERTION_GOVERNANCE
    assert d.kind is not ProviderKind.ACTION_GOVERNANCE


def test_no_authorize_dispatch_execute_surface():
    provider = build_tap_provider(TapEngine())
    for forbidden in ("authorize", "dispatch", "execute", "reconcile", "compensate"):
        assert not hasattr(provider, forbidden), forbidden
    assert not hasattr(TAPProvider, "authorize")


def test_capabilities_are_assertion_only():
    caps = build_tap_provider(TapEngine()).descriptor().capabilities
    assert caps.kind is ProviderKind.ASSERTION_GOVERNANCE
    forbidden = {"authorize", "dispatch", "execute", "reconcile", "compensate"}
    assert not (set(caps.features) & forbidden)


def test_core_never_imports_actiongate():
    bad = [f"{p.name}->{m}" for p, m in _module_names()
           if m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")]
    assert not bad, bad


def test_core_never_imports_action_control_plane_port():
    """TAP never *references* the kernel's action control-plane / external-execution
    ports as code (a docstring may name them to disclaim them — that is not use)."""
    forbidden_symbols = {"ActionControlPlanePort", "ExternalExecutionPort"}
    hits = []
    for p in CANON.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        tree = ast.parse(p.read_text(), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden_symbols:
                hits.append(f"{p.name}:{node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in forbidden_symbols:
                hits.append(f"{p.name}:{node.attr}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                hits += [f"{p.name}:{a.name}" for a in node.names
                         if a.name in forbidden_symbols]
    assert not hits, hits


def test_no_actiongate_module_loaded_by_import():
    # Importing the whole TAP surface must not pull ActionGate into sys.modules.
    import ugence_tap_provider.api  # noqa: F401
    assert not any(m.split(".")[0] in ("actiongate_provider", "ugence_actiongate_provider")
                   for m in list(sys.modules))
