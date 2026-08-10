"""Ugence Risk Authority — executable governance authority kernel.

An independently packaged module that turns an approved governance decision into
cryptographically bound, scoped, time-bound, revocable runtime authority, and
enforces that authority at the point of action.

This distribution implements the RA-1..RA-4 vertical slice of the architecture
specification (v1.1):

    WorkflowIR -> RiskDecisionCase -> ControlResult -> Decision Authority
        -> signed RiskAuthorizationEnvelope -> Canonical Action
        -> ActionGate -> ALLOW / DENY

TAP + Control Assurance, revocation/epoch propagation, Context Minimization,
Third-Party Gateway, Trajectory Control, ACP and Reconciliation are defined as
contracts and layered incrementally (RA-5..RA-8); the authority spine here is
the kernel they attach to.

``risk_authority`` consumes existing governance components (ActionGate, TAP,
PWC) through the ports in :mod:`risk_authority.integrations` and never imports
their application-specific policy logic directly.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
