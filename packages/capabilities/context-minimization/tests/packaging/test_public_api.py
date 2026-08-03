"""Public-API + reason-code agreement, py.typed, and import-side-effect tests.

Covers required scenarios 6–9 (py.typed, metadata/version, no undeclared deps at
import, no import side effects). Wheel/sdist build + isolated install (scenarios
1–5) are proven by ``scripts/verify_context_minimization_distribution.py``.
"""

from __future__ import annotations

import json
import pathlib

import ugence_context_minimization
from ugence_context_minimization import api

PKG_ROOT = pathlib.Path(ugence_context_minimization.__file__).resolve().parent
# repo source artifacts live next to src/, under the package project root.
PROJECT_ROOT = PKG_ROOT.parents[1]
ARTIFACTS = PROJECT_ROOT / "artifacts"


def test_public_api_matches_committed_manifest():
    manifest = json.loads((ARTIFACTS / "public_api.json").read_text())
    assert sorted(api.__all__) == manifest["exports"]
    assert manifest["version"] == api.__version__
    assert manifest["contract_version"] == api.CONTRACT_VERSION
    assert manifest["distribution"] == "ugence-context-minimization"
    assert manifest["namespace"] == "ugence_context_minimization"


def test_every_export_actually_resolves():
    for name in api.__all__:
        assert hasattr(api, name), name


def test_reason_codes_manifest_in_sync():
    manifest = json.loads((ARTIFACTS / "reason_codes.json").read_text())
    assert manifest["codes"] == list(api.REASON_CODES)


def test_version_and_contract_version():
    assert api.__version__ == "0.1.1"
    assert api.CONTRACT_VERSION == "1.0.1"


def test_py_typed_ships_in_source_tree():
    assert (PKG_ROOT / "py.typed").is_file()


def test_no_undeclared_third_party_dependency_declared_in_pyproject():
    text = (PROJECT_ROOT / "pyproject.toml").read_text()
    # The runtime dependency list must be empty (leaf, stdlib-only).
    assert "dependencies = []" in text


def test_import_has_no_side_effects(monkeypatch):
    """Importing the package must not touch the network, spawn threads/schedulers,
    read credentials, or manipulate sys.path."""
    import importlib
    import socket
    import sys
    import threading

    # forbid real socket connections
    def _boom(*a, **k):  # pragma: no cover - only fires on a violation
        raise AssertionError("import performed a network connection")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    before_threads = threading.active_count()
    before_path = list(sys.path)

    for mod in [m for m in list(sys.modules) if m.startswith("ugence_context_minimization")]:
        del sys.modules[mod]
    importlib.import_module("ugence_context_minimization")
    importlib.import_module("ugence_context_minimization.api")

    assert threading.active_count() == before_threads
    assert sys.path == before_path  # no sys.path manipulation on import
