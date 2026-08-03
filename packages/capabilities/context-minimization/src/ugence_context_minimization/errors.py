"""Package-level error taxonomy.

Errors are raised only for *programming/contract* violations the caller can fix
(a missing oracle in oracle mode, an invalid request, an invalid unit identity).
They are NOT raised for oracle failures at runtime — those FAIL CLOSED to the full
context and are reported via reason codes on the result, never as exceptions.
"""

from __future__ import annotations


class ContextMinimizationError(Exception):
    """Base class for all package errors."""


class InvalidRequestError(ContextMinimizationError, ValueError):
    """The minimization request is structurally invalid (bad target, budget,
    evaluation_time, etc.).

    Subclasses :class:`ValueError` so existing ``except ValueError`` callers keep
    working while the error is also identifiable as a package error.
    """


class OracleRequiredError(ContextMinimizationError):
    """Oracle-verified mode was requested without a valid invariance oracle."""


class InvalidUnitError(ContextMinimizationError, ValueError):
    """A context unit has invalid identity or payload the minimizer cannot process
    (bad id, malformed token count, non-scalar metadata value).

    Subclasses :class:`ValueError` for backward compatibility with callers that
    catch ``ValueError`` on model construction.
    """
