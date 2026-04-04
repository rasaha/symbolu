"""
Governance Binding — Facade for P53 external policy binding.

STATUS: PROVISIONAL (Policy Phase P0)

    This module has ZERO runtime consumers as of Policy Phase P0.
    All P53 consumers (P54 audit trace, P55 execution boundary) import
    directly from symbolu_core.mechanical.pipeline.p53_policy_binding.

    This facade exists as a potential future convenience import path
    for agentic-layer code that needs P53 types. It will be promoted
    to active status when the external governance API needs a clean
    agentic-layer import surface, or deprecated if the decision is
    made to always import P53 types from symbolu_core directly.

    Do not add new logic here. Do not assume this module is active.

Re-exports P53 policy binding from symbolu_core.mechanical.pipeline.
P53 binds external governance decisions (ALLOW/DENY/DEFER) into the
pipeline without interpretation — "a plug, not a judge."
"""

# Facade status marker — checked by tests and audit tooling
_FACADE_STATUS = "provisional"

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
    "_FACADE_STATUS",
]
