"""
Governance Binding — Facade for P53 external policy binding.

Re-exports P53 policy binding from symbolu_core.mechanical.pipeline.
P53 binds external governance decisions (ALLOW/DENY/DEFER) into the
pipeline without interpretation — "a plug, not a judge."
"""

from symbolu_core.mechanical.pipeline.p53_policy_binding.p53_schema import (
    GovernanceBindingEnvelope,
)
from symbolu_core.mechanical.pipeline.p53_policy_binding.p53_binder import (
    GovernanceResponseValidationError,
    validate_governance_response_structure,
    bind_governance_response,
)

__all__ = [
    "GovernanceBindingEnvelope",
    "GovernanceResponseValidationError",
    "validate_governance_response_structure",
    "bind_governance_response",
]
