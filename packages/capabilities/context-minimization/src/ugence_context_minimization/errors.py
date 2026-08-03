"""Package-level error taxonomy.

Errors are raised only for *programming/contract* violations the caller can fix
(a missing oracle in oracle mode, an invalid request, an invalid unit identity).
They are NOT raised for oracle failures at runtime — those FAIL CLOSED to the full
context and are reported via reason codes on the result, never as exceptions.
"""

from __future__ import annotations


class ContextMinimizationError(Exception):
    """Base class for all package errors."""


class InvalidRequestError(ContextMinimizationError):
    """The minimization request is structurally invalid (bad target, budget, etc.)."""


class OracleRequiredError(ContextMinimizationError):
    """Oracle-verified mode was requested without a valid invariance oracle."""


class InvalidUnitError(ContextMinimizationError):
    """A context unit has invalid identity or payload the minimizer cannot process."""
