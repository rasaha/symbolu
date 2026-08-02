"""Typed exceptions for Action Clearance.

Exceptions are reserved for **programming errors and malformed contracts** — not
for normal governance/operational outcomes. Expected operational conditions
(authorization expired, mandatory signal missing, target unavailable, conflict,
prior consumption, …) produce a fail-closed :class:`ClearanceResult`, never an
exception.
"""
from __future__ import annotations


class ActionClearanceError(Exception):
    """Base class for every Action Clearance error."""


class ValidationError(ActionClearanceError):
    """A request/model is structurally malformed (missing slot, duplicate id,
    future capture time, prohibited credential/command payload, unknown enum)."""


class FingerprintError(ActionClearanceError):
    """A value cannot be canonicalized/fingerprinted deterministically."""


class UnsupportedVersionError(ActionClearanceError):
    """An unsupported contract/policy version was supplied."""


__all__ = [
    "ActionClearanceError",
    "ValidationError",
    "FingerprintError",
    "UnsupportedVersionError",
]
