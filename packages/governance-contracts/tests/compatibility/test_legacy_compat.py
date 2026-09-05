"""C4 — legacy ``governance_providers`` ↔ canonical identity.

Every neutral contract symbol imported from the legacy ``governance_providers``
paths must be the SAME object as the canonical ``ugence_governance_contracts``
symbol, so pre-migration imports keep working and no `isinstance`/singleton
identity breaks across the boundary.
"""

from __future__ import annotations

import pytest

import ugence_governance_contracts as canon

# Legacy modules that are now re-export shims.
import governance_providers.errors as gp_errors
import governance_providers.lifecycle as gp_lifecycle
import governance_providers.metadata as gp_metadata
import governance_providers.contracts as gp_contracts
import governance_providers.contracts.base as gp_base
import governance_providers.contracts.action as gp_action
import governance_providers.contracts.assertion as gp_assertion
import governance_providers.contracts.execution as gp_execution
import governance_providers.api as gp_api

_NEUTRAL = [
    "FailureClass", "ProviderError", "ProviderRegistrationError",
    "ProviderResolutionError", "ProviderCompatibilityError",
    "ProviderConfigurationError", "ProviderUnavailableError",
    "ProviderTimeoutError", "ProviderProtocolError", "ProviderResultValidationError",
    "ProviderLifecycleState",
    "ProviderKind", "ProviderCapabilities", "ProviderCompatibility",
    "ProviderDescriptor", "ProviderHealth",
    "Provider", "BaseProvider",
    "AssertionGovernanceProvider", "AssertionGovernanceRequest",
    "AssertionGovernanceResult", "AssertionCoverage",
    "ActionGovernanceProvider", "ActionGovernanceRequest",
    "ActionGovernanceResult", "ActionGovernanceOutcome",
    "ExternalExecutionProvider", "ExecutionDispatchRequest",
    "ExecutionDispatchResult", "ExecutionObservation", "ExecutionBusinessOutcome",
]


@pytest.mark.parametrize("name", _NEUTRAL)
def test_legacy_api_symbol_is_canonical_object(name):
    assert getattr(gp_api, name) is getattr(canon, name), name


def test_legacy_module_shims_preserve_identity():
    assert gp_errors.FailureClass is canon.FailureClass
    assert gp_lifecycle.ProviderLifecycleState is canon.ProviderLifecycleState
    assert gp_metadata.ProviderKind is canon.ProviderKind
    assert gp_contracts.Provider is canon.Provider
    assert gp_base.BaseProvider is canon.BaseProvider
    assert gp_action.ActionGovernanceRequest is canon.ActionGovernanceRequest
    assert gp_assertion.AssertionGovernanceResult is canon.AssertionGovernanceResult
    assert gp_execution.ExecutionObservation is canon.ExecutionObservation


def test_contract_version_and_versions_preserved():
    # CONTRACT_VERSION (the provider contract surface) is unchanged by GV-2E-a,
    # unchanged again by the M-3R.3 neutral assessed-system identity family, and
    # unchanged once more by the G4 neutral audit reference; only the package
    # __version__ advances (additive neutral contract families).
    assert gp_api.CONTRACT_VERSION == canon.CONTRACT_VERSION == "1.0.0"
    assert canon.__version__ == "0.6.0"


def test_isinstance_works_across_boundary():
    # An object built from the canonical Request satisfies the legacy protocol
    # class because they are the same object.
    req = gp_api.ActionGovernanceRequest(action_type="x")
    assert isinstance(req, canon.ActionGovernanceRequest)
