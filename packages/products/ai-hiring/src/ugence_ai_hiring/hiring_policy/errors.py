"""Typed errors for the hiring policy / compiler layer.

All derive from :class:`~ugence_ai_hiring.errors.HiringError` (the kernel
``GovernanceError``), so callers can catch them alongside every other hiring
domain error, and so a compile failure raised inside a pydantic validator
propagates as-is rather than being wrapped.
"""

from __future__ import annotations

from ..errors import HiringError


class PolicyCompilationError(HiringError):
    """A Hiring Policy failed to compile.

    Carries the full list of rejection reasons so the author sees every problem
    at once rather than one-at-a-time.
    """

    def __init__(self, reasons: list[str]):
        self.reasons = list(reasons)
        joined = "; ".join(self.reasons)
        super().__init__(f"hiring policy failed to compile: {joined}")


class SignatureError(HiringError):
    """An IR signature could not be produced or verified."""


class ContractProjectionError(HiringError):
    """A Hiring Decision Contract could not be projected from an IR."""
