"""Canonical TAP / ActionGate adapter tests.

Proves the canonical integration boundary:

* **Optionality / laziness** — importing the canonical adapter modules never loads
  the concrete provider; in a clean environment with the audited core + governance
  packages but WITHOUT the providers, importing the adapter modules succeeds and
  the loaders raise :class:`ProviderUnavailable` (verified in a controlled
  subprocess whose import roots exclude the providers).
* **Canonical targeting** — the adapters target the canonical
  ``ugence_tap_provider`` / ``ugence_actiongate_provider`` namespaces (never the
  legacy ``tap_provider`` / ``actiongate_provider`` namespaces).
* **Compatibility identity** — the legacy adapter module paths re-export the
  *same* callables (object identity preserved) and no second implementation exists.
* **Class identity** — when the providers are importable the loaders return the
  canonical provider classes.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

import ugence_ai_hiring.integrations.actiongate_adapter as ag
import ugence_ai_hiring.integrations.actiongate_legacy_adapter as ag_legacy
import ugence_ai_hiring.integrations.tap_adapter as tap
import ugence_ai_hiring.integrations.tap_legacy_adapter as tap_legacy
from ugence_ai_hiring.integrations import LegacyProviderUnavailable, ProviderUnavailable

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


# --- Exception compatibility -------------------------------------------------

def test_provider_unavailable_alias_identity():
    # The neutral name and the retained historical name are the SAME class.
    assert LegacyProviderUnavailable is ProviderUnavailable
    assert issubclass(ProviderUnavailable, ImportError)


# --- Object identity: legacy paths re-export the canonical callables ----------

def test_tap_legacy_paths_reexport_canonical_callables():
    assert tap_legacy.load_tap_provider_cls is tap.load_tap_provider_cls
    assert tap_legacy.build_tap_provider is tap.build_tap_provider
    assert tap_legacy.build_claim_assertion_evaluator is tap.build_claim_assertion_evaluator


def test_actiongate_legacy_paths_reexport_canonical_callables():
    assert ag_legacy.load_actiongate_provider_cls is ag.load_actiongate_provider_cls
    assert ag_legacy.build_actiongate_provider is ag.build_actiongate_provider
    assert (
        ag_legacy.build_action_authorization_integration
        is ag.build_action_authorization_integration
    )


def test_legacy_adapter_modules_contain_no_second_implementation():
    """The legacy module files are thin re-export facades, not implementations."""
    for mod in (tap_legacy, ag_legacy):
        text = pathlib.Path(mod.__file__).read_text()
        assert "def load_" not in text, f"{mod.__name__} redefines a loader"
        assert "def build_" not in text, f"{mod.__name__} redefines a builder"
        assert "import" in text and "adapter import" in text


def test_canonical_adapters_target_canonical_namespaces_only():
    """The canonical adapters reference the canonical namespaces, never the legacy ones."""
    for mod, canon in ((tap, "ugence_tap_provider"), (ag, "ugence_actiongate_provider")):
        text = pathlib.Path(mod.__file__).read_text()
        assert canon in text
        assert "tap_provider.provider" not in text or canon in text
    tap_text = pathlib.Path(tap.__file__).read_text()
    ag_text = pathlib.Path(ag.__file__).read_text()
    # No import of the legacy compatibility namespaces.
    assert "from tap_provider" not in tap_text and "import tap_provider" not in tap_text
    assert "from actiongate_provider" not in ag_text
    assert "import actiongate_provider" not in ag_text


def test_canonical_adapters_contain_no_adjudication_logic():
    for mod in (tap, ag):
        text = pathlib.Path(mod.__file__).read_text()
        assert "def authorize(" not in text
        assert "def evaluate(" not in text


# --- Laziness + fail-closed in a provider-absent subprocess ------------------

def test_canonical_adapter_import_does_not_load_provider(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = (
        "import sys;"
        "import ugence_ai_hiring.integrations.tap_adapter as t;"
        "import ugence_ai_hiring.integrations.actiongate_adapter as a;"
        "leak=[m for m in ('ugence_tap_provider','ugence_actiongate_provider',"
        "'tap_provider','actiongate_provider') if m in sys.modules];"
        "print('LEAK=' + ','.join(leak))"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "LEAK="


def test_canonical_loaders_raise_when_provider_absent(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = _core_only_pythonpath()
    code = (
        "from ugence_ai_hiring.integrations import ProviderUnavailable;"
        "import ugence_ai_hiring.integrations.tap_adapter as t;"
        "import ugence_ai_hiring.integrations.actiongate_adapter as a;"
        "ok=0\n"
        "try:\n t.load_tap_provider_cls()\nexcept ProviderUnavailable:\n ok+=1\n"
        "try:\n a.load_actiongate_provider_cls()\nexcept ProviderUnavailable:\n ok+=1\n"
        "print('RAISED=%d' % ok)"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(tmp_path),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "RAISED=2"


# --- Class identity when the canonical providers are importable ---------------

_HAVE_TAP = importlib.util.find_spec("ugence_tap_provider") is not None
_HAVE_ACTIONGATE = importlib.util.find_spec("ugence_actiongate_provider") is not None


@pytest.mark.skipif(not _HAVE_TAP, reason="ugence_tap_provider not installed")
def test_tap_adapter_loads_canonical_class_and_identity():
    from ugence_governance_provider_framework.api import AssertionGovernanceProvider
    from ugence_tap_provider.provider import TAPProvider

    cls = tap.load_tap_provider_cls()
    assert cls is TAPProvider
    assert issubclass(cls, AssertionGovernanceProvider)
    # Legacy path returns the identical class.
    assert tap_legacy.load_tap_provider_cls() is TAPProvider


@pytest.mark.skipif(not _HAVE_ACTIONGATE, reason="ugence_actiongate_provider not installed")
def test_actiongate_adapter_loads_canonical_class_and_identity():
    from ugence_actiongate_provider.provider import ActionGateProvider
    from ugence_governance_provider_framework.api import ActionGovernanceProvider

    cls = ag.load_actiongate_provider_cls()
    assert cls is ActionGateProvider
    assert issubclass(cls, ActionGovernanceProvider)
    assert ag_legacy.load_actiongate_provider_cls() is ActionGateProvider


@pytest.mark.skipif(
    not (_HAVE_TAP and _HAVE_ACTIONGATE),
    reason="canonical providers not both installed",
)
def test_provider_legacy_facade_identity_holds():
    """The provider packages' own legacy namespace facades preserve class identity."""
    import actiongate_provider.provider as ag_facade
    import tap_provider.provider as tap_facade
    import ugence_actiongate_provider.provider as ag_canon
    import ugence_tap_provider.provider as tap_canon

    assert tap_facade.TAPProvider is tap_canon.TAPProvider
    assert ag_facade.ActionGateProvider is ag_canon.ActionGateProvider
