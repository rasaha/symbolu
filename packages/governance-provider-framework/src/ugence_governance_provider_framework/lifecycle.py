"""COMPATIBILITY-ONLY. Legacy path for the provider lifecycle state machine.

Canonical: ``ugence_governance_contracts.lifecycle``. Re-exports the SAME objects
(identity preserved); no logic. Removal/review target: governance_providers 0.2.0.
"""
from ugence_governance_contracts.lifecycle import (  # noqa: F401
    ProviderLifecycleState,
    is_legal_transition,
    assert_transition,
)
