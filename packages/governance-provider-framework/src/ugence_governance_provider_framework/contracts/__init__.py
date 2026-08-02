"""COMPATIBILITY-ONLY. Legacy path for the provider contracts.

Canonical: ``ugence_governance_contracts.contracts``. Re-exports the SAME objects
(identity preserved); no logic. Removal/review target: governance_providers 0.2.0.
"""
from ugence_governance_contracts.contracts import (  # noqa: F401
    Provider, BaseProvider,
    AssertionGovernanceProvider, AssertionGovernanceRequest,
    AssertionGovernanceResult, AssertionCoverage,
    ActionGovernanceProvider, ActionGovernanceRequest,
    ActionGovernanceResult, ActionGovernanceOutcome,
    ExternalExecutionProvider, ExecutionDispatchRequest,
    ExecutionDispatchResult, ExecutionObservation, ExecutionBusinessOutcome,
    __all__,
)
