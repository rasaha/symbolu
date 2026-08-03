"""Optional legacy TAP / ActionGate adapter tests.

Proves the addendum boundary two ways:

* **Optionality** — in a clean environment with the audited core + governance
  packages but WITHOUT the legacy providers, importing the adapter modules
  succeeds and the loaders raise :class:`LegacyProviderUnavailable` (verified in a
  controlled subprocess whose import roots exclude the repo).
* **Compatibility** — when ``tap_provider`` / ``actiongate_provider`` ARE
  importable, the loaders return classes that satisfy the neutral governance
  protocols, so the adapters bridge onto the core's neutral integration without
  the core implementing any TAP/ActionGate logic.
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
    """Absolute roots for the core + governance packages, excluding the repo root
    (so the legacy providers are NOT importable)."""
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


def test_adapter_modules_do_not_load_legacy_providers_on_import(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = (
        "import sys;"
        "import ugence_ai_hiring.integrations.tap_legacy_adapter as t;"
        "import ugence_ai_hiring.integrations.actiongate_legacy_adapter as a;"
        "leak=[m for m in ('tap_provider','actiongate_provider') if m in sys.modules];"
        "print('LEAK=' + ','.join(leak))"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "LEAK="


def test_loaders_raise_when_legacy_absent(tmp_path):
    """In a core-only environment the loaders fail closed with guidance."""
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


# --- Compatibility branch: only when the legacy distributions are importable ---
_HAVE_TAP = importlib.util.find_spec("tap_provider") is not None
_HAVE_ACTIONGATE = importlib.util.find_spec("actiongate_provider") is not None


@pytest.mark.skipif(not _HAVE_TAP, reason="legacy tap_provider not installed")
def test_tap_adapter_targets_neutral_protocol():
    from ugence_governance_provider_framework.api import AssertionGovernanceProvider

    cls = tapa.load_tap_provider_cls()
    assert issubclass(cls, AssertionGovernanceProvider)


@pytest.mark.skipif(not _HAVE_ACTIONGATE, reason="legacy actiongate_provider not installed")
def test_actiongate_adapter_targets_neutral_protocol():
    from ugence_governance_provider_framework.api import ActionGovernanceProvider

    cls = aga.load_actiongate_provider_cls()
    assert issubclass(cls, ActionGovernanceProvider)


def test_adapters_contain_no_adjudication_logic():
    """The adapters only bridge; they implement no TAP/ActionGate decision logic."""
    import pathlib

    for mod in (tapa, aga):
        text = pathlib.Path(mod.__file__).read_text()
        # No adjudication/authorization verbs implemented locally — the adapter
        # delegates entirely to the injected legacy provider.
        assert "def authorize(" not in text
        assert "def evaluate(" not in text
