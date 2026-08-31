"""Typed errors for the action-assurance orchestration path.

All derive from :class:`~ugence_ai_hiring.errors.HiringError`. They are the
fail-closed signals of the decision → authorization → assurance → execution
spine: each stops the pipeline before the next side effect can occur.
"""

from __future__ import annotations

from typing import Optional

from ..errors import HiringError


class ActionAssuranceError(HiringError):
    """Base for orchestration-path failures."""


class FailClosedError(ActionAssuranceError):
    """A precondition for building/executing an action was not met (no binding
    decision, not eligible, wrong disposition, missing proposed action)."""


class ContractBindingError(ActionAssuranceError):
    """The supplied contract does not match the case's contract reference."""


class ActionAuthorizationDenied(ActionAssuranceError):
    """The shared ActionGate denied the action. Runtime assurance must not run."""

    def __init__(self, message: str, *, outcome: Optional[object] = None) -> None:
        self.outcome = outcome
        super().__init__(message)


class RuntimeAssuranceNotClear(ActionAssuranceError):
    """Runtime assurance did not clear. No HRIS execution may occur."""

    def __init__(self, message: str, *, outcome: Optional[object] = None) -> None:
        self.outcome = outcome
        super().__init__(message)


class PayloadMutationError(ActionAssuranceError):
    """The action payload changed after it was authorized."""
