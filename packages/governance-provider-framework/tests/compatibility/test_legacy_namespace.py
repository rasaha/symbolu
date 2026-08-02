"""Legacy ``governance_providers`` namespace compatibility (identity-preserving).

Consumers that still import from ``governance_providers`` must observe the SAME
objects as the canonical ``ugence_governance_provider_framework`` package — same
classes, same modules, same serialization — so no consumer needs a code change.
"""

from __future__ import annotations

import importlib

import pytest

# Deep-import paths that external consumers rely on (from the baseline import graph).
DEEP_MODULES = [
    "api",
    "registry",
    "resolution",
    "configuration",
    "observability",
    "fingerprint",
    "version",
    "errors",
    "lifecycle",
    "metadata",
    "contracts",
    "contracts.base",
    "contracts.assertion",
    "contracts.action",
    "contracts.execution",
    "conformance",
    "conformance.common",
    "conformance.assertion",
    "conformance.action",
    "conformance.execution",
    "reference",
    "reference.assertion",
    "reference.action",
    "reference.execution",
    "adapters",
    "adapters.action_to_control_plane",
    "adapters.execution_to_external_system",
    "adapters.assertion_integration",
]


@pytest.mark.parametrize("sub", DEEP_MODULES)
def test_legacy_submodule_is_the_same_object_as_canonical(sub):
    legacy = importlib.import_module("governance_providers." + sub)
    canon = importlib.import_module("ugence_governance_provider_framework." + sub)
    assert legacy is canon


def test_top_level_version_identity():
    import governance_providers as gp
    import ugence_governance_provider_framework as canon
    assert gp.__version__ is canon.__version__ == "0.1.0"


def test_public_api_symbols_are_identical_objects():
    import governance_providers.api as legacy_api
    import ugence_governance_provider_framework.api as canon_api
    assert list(legacy_api.__all__) == list(canon_api.__all__)
    for name in canon_api.__all__:
        assert getattr(legacy_api, name) is getattr(canon_api, name), name


def test_contract_shims_resolve_to_the_contracts_leaf():
    """The neutral contracts are single-sourced in ugence_governance_contracts; the
    framework's legacy shims re-export the identical objects (not a second copy)."""
    import ugence_governance_contracts.errors as gce
    import ugence_governance_contracts.metadata as gcm
    from governance_providers.errors import ProviderError
    from governance_providers.metadata import ProviderKind
    assert ProviderError is gce.ProviderError
    assert ProviderKind is gcm.ProviderKind


def test_deep_import_from_statement_still_works():
    # Representative of ai_hiring's legacy deep imports.
    from governance_providers.contracts.action import ActionGovernanceOutcome
    from governance_providers.reference import DeterministicAssertionProvider
    from governance_providers.version import CONTRACT_VERSION
    assert CONTRACT_VERSION == "1.0.0"
    assert DeterministicAssertionProvider().descriptor().provider_id == "deterministic-assertion"
    assert ActionGovernanceOutcome is not None
