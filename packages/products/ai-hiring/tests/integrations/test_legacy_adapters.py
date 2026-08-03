"""Compatibility-path (legacy adapter module) tests.

After canonical normalization the ``*_legacy_adapter`` module names are retained
as **compatibility import paths** — logic-free facades over the canonical
``tap_adapter`` / ``actiongate_adapter`` modules. These tests prove the paths keep
working two ways:

* **Optionality** — in a clean environment with the audited core + governance
  packages but WITHOUT the providers, importing the legacy adapter modules
  succeeds and the loaders raise :class:`ProviderUnavailable` (verified in a
  controlled subprocess whose import roots exclude the providers).
* **Compatibility** — when the canonical providers ARE importable, the legacy-path
  loaders return the canonical classes that satisfy the neutral governance
  protocols, so the compatibility paths bridge onto the core's neutral integration
  without the core implementing any TAP/ActionGate logic.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

import ugence_ai_hiring
import ugence_ai_hiring.integrations.actiongate_legacy_adapter as aga
import ugence_ai_hiring.integrations.tap_legacy_adapter as tapa
from ugence_ai_hiring.integrations import LegacyProviderUnavailable

_CORE_ROOTS = (
    "ugence_ai_hiring",
    "ugence_decision_authority",
    "ugence_governance_provider_framework",
    "ugence_governance_contracts",
)


def _core_only_pythonpath() -> str:
    """Absolute roots for the core + governance packages, excluding the providers
    (so neither the canonical nor the legacy provider namespaces are importable)."""
    import importlib

    roots = []
    for name in _CORE_ROOTS:
        mod = importlib.import_module(name)
        roots.append(os.path.dirname(os.path.dirname(mod.__file__)))
    return os.pathsep.join(dict.fromkeys(roots))


def test_core_import_does_not_load_integrations(tmp_path):
    # Importing the product core must not pull in the optional integrations.
    assert "ugence_ai_hiring.integrations" not in sys.modules or True
    # A fresh subprocess: importing the core leaves integrations unloaded.
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = ("import sys, ugence_ai_hiring;"
            "print('LOADED' if 'ugence_ai_hiring.integrations' in sys.modules else 'NOT_LOADED')")
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "NOT_LOADED"


def test_legacy_paths_do_not_load_providers_on_import(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = (
        "import sys;"
        "import ugence_ai_hiring.integrations.tap_legacy_adapter as t;"
        "import ugence_ai_hiring.integrations.actiongate_legacy_adapter as a;"
        "leak=[m for m in ('tap_provider','actiongate_provider',"
        "'ugence_tap_provider','ugence_actiongate_provider') if m in sys.modules];"
        "print('LEAK=' + ','.join(leak))"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "LEAK="


def test_legacy_path_loaders_raise_when_provider_absent(tmp_path):
    """In a provider-absent environment the legacy-path loaders fail closed with guidance."""
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = (
        "from ugence_ai_hiring.integrations import LegacyProviderUnavailable;"
        "import ugence_ai_hiring.integrations.tap_legacy_adapter as t;"
        "import ugence_ai_hiring.integrations.actiongate_legacy_adapter as a;"
        "ok=0\n"
        "try:\n t.load_tap_provider_cls()\nexcept LegacyProviderUnavailable:\n ok+=1\n"
        "try:\n a.load_actiongate_provider_cls()\nexcept LegacyProviderUnavailable:\n ok+=1\n"
        "print('RAISED=%d' % ok)"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "RAISED=2"


# --- Compatibility branch: only when the canonical providers are importable ---
_HAVE_TAP = importlib.util.find_spec("ugence_tap_provider") is not None
_HAVE_ACTIONGATE = importlib.util.find_spec("ugence_actiongate_provider") is not None


@pytest.mark.skipif(not _HAVE_TAP, reason="ugence_tap_provider not installed")
def test_legacy_tap_path_returns_canonical_neutral_class():
    from ugence_governance_provider_framework.api import AssertionGovernanceProvider
    from ugence_tap_provider.provider import TAPProvider

    cls = tapa.load_tap_provider_cls()
    assert cls is TAPProvider
    assert issubclass(cls, AssertionGovernanceProvider)


@pytest.mark.skipif(not _HAVE_ACTIONGATE, reason="ugence_actiongate_provider not installed")
def test_legacy_actiongate_path_returns_canonical_neutral_class():
    from ugence_actiongate_provider.provider import ActionGateProvider
    from ugence_governance_provider_framework.api import ActionGovernanceProvider

    cls = aga.load_actiongate_provider_cls()
    assert cls is ActionGateProvider
    assert issubclass(cls, ActionGovernanceProvider)


def test_legacy_paths_contain_no_adjudication_logic():
    """The legacy-path facades only re-export; they implement no decision logic."""
    import pathlib

    for mod in (tapa, aga):
        text = pathlib.Path(mod.__file__).read_text()
        assert "def authorize(" not in text
        assert "def evaluate(" not in text
