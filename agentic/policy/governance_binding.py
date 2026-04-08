"""
Governance Binding — Dormant facade for P53 external policy binding.

STATUS: DORMANT (Policy P0-cleanup, 2026-04)

    This facade has ZERO runtime consumers anywhere in the codebase.
    Every real consumer of P53 types (P54 audit trace, P55 execution
    boundary, agentic_framework.governance_models) imports directly
    from ``symbolu_core.mechanical.pipeline.p53_policy_binding`` or
    ``symbolu.mechanical.pipeline.p53_policy_binding``.

    This module is retained on disk as a reserved import path for
    future use. It is deliberately excluded from the ``agentic.policy``
    public API (``__init__.py`` / ``__all__``).

    Do NOT add logic here.
    Do NOT import from here in new code.
    Use the canonical P53 source directly:
        ``from symbolu_core.mechanical.pipeline.p53_policy_binding...``

    This facade will either be promoted to active status (if the
    external governance API needs a clean agentic-layer import surface)
    or deleted entirely in a future cleanup phase.

Re-exports P53 policy binding from symbolu_core.mechanical.pipeline.
P53 binds external governance decisions (ALLOW/DENY/DEFER) into the
pipeline without interpretation — "a plug, not a judge."
"""

# Facade status marker — checked by tests and audit tooling.
# Values: "dormant" (zero consumers, kept for reference) |
#         "provisional" (pre-cleanup) | "active" (real consumers)
_FACADE_STATUS = "dormant"

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
