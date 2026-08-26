"""Legacy ``actiongate_provider`` facade — object identity + behavior parity.

The facade re-exports the identical objects from ``ugence_actiongate_provider`` and
carries no logic of its own; canonical and legacy imports authorize identically.
"""
from __future__ import annotations

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest)


def test_api_module_and_symbols_are_identical_objects():
    import actiongate_provider.api as legacy
    import ugence_actiongate_provider.api as canon
    assert legacy is canon
    assert list(legacy.__all__) == list(canon.__all__)
    for name in canon.__all__:
        assert getattr(legacy, name) is getattr(canon, name), name


def test_deep_submodule_imports_preserve_identity():
    pairs = [
        ("actiongate_provider.core", "ugence_actiongate_provider.core"),
        ("actiongate_provider.provider", "ugence_actiongate_provider.provider"),
        ("actiongate_provider.mapping.result", "ugence_actiongate_provider.mapping.result"),
        ("actiongate_provider.mapping.constraints", "ugence_actiongate_provider.mapping.constraints"),
        ("actiongate_provider.errors", "ugence_actiongate_provider.errors"),
        ("actiongate_provider.observability", "ugence_actiongate_provider.observability"),
    ]
    import importlib
    for legacy_name, canon_name in pairs:
        assert importlib.import_module(legacy_name) is importlib.import_module(canon_name), legacy_name


def test_legacy_top_level_reexports_version_info():
    import actiongate_provider
    import ugence_actiongate_provider
    assert actiongate_provider.__version__ == ugence_actiongate_provider.__version__ == "0.2.0"
    assert actiongate_provider.version_info is ugence_actiongate_provider.version_info


def test_canonical_and_legacy_authorize_identically():
    from actiongate_provider.configuration import build_actiongate_provider as legacy_build
    from ugence_actiongate_provider.configuration import build_actiongate_provider as canon_build
    lp = legacy_build(); lp.initialize()
    cp = canon_build(); cp.initialize()
    lr = lp.authorize(ActionGovernanceRequest("OK"))
    cr = cp.authorize(ActionGovernanceRequest("OK"))
    assert lr.outcome is cr.outcome is ActionGovernanceOutcome.AUTHORIZED
    assert lr.fingerprint == cr.fingerprint
