"""Typed, fail-closed errors for the pilot operator.

Every operator failure is structured and fails closed. Nothing here enables
execution, GitHub writes, reservation, or a consumption ledger.
"""
from __future__ import annotations

from ..errors import CodeGovernanceError


class PilotOperatorError(CodeGovernanceError):
    """Base for pilot-operator failures."""


class PilotConfigError(PilotOperatorError):
    """A pilot deployment configuration was rejected (fail closed)."""


class PilotLifecycleError(PilotOperatorError):
    """An illegal or unsafe lifecycle transition was attempted."""


class PilotPreflightError(PilotOperatorError):
    """A preflight verification could not complete."""


class CredentialBoundaryError(PilotOperatorError):
    """A credential crossed, or was about to cross, a prohibited boundary."""


class PilotSecurityError(PilotOperatorError):
    """A static or runtime security boundary was violated."""


class KillSwitchActiveError(PilotOperatorError):
    """An operation was refused because the durable kill switch is active."""


class PilotStoppedError(PilotOperatorError):
    """An operation was refused because the pilot is not ACTIVE."""


class ReviewQueueError(PilotOperatorError):
    """A reviewer-queue operation was rejected (e.g. cross-tenant / unknown item)."""


class PilotRecoveryError(PilotOperatorError):
    """Restart recovery could not proceed safely (fail closed)."""


__all__ = [
    "PilotOperatorError", "PilotConfigError", "PilotLifecycleError", "PilotPreflightError",
    "CredentialBoundaryError", "PilotSecurityError", "KillSwitchActiveError",
    "PilotStoppedError", "ReviewQueueError", "PilotRecoveryError",
]
