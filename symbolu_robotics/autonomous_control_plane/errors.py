"""ACP error hierarchy.

Every ACP failure is a typed, loud error. Nothing in ACP silently degrades to a
permissive default: a construction or validation failure raises, and the
decision layer prefers ``NO_SAFE_ACTION`` / ``REQUEST_MORE_OBSERVATION`` over
guessing (see ``ACP_INTERFACE_CONTRACTS.md``).

This module has no dependencies beyond the standard library.
"""
from __future__ import annotations


class ACPError(Exception):
    """Base class for every Autonomous Control Plane error."""


class SchemaValidationError(ACPError):
    """A canonical envelope was constructed with invalid or missing fields."""


class NonFiniteValueError(SchemaValidationError):
    """A NaN / +Inf / -Inf value reached a field that must be finite.

    Raised loudly rather than allowing an ambiguous value into an identity or a
    safety-relevant margin.
    """


class IdentityError(ACPError):
    """A value could not be canonicalized into a deterministic identity."""


class IllegalTransitionError(ACPError):
    """An attempted failure-state transition is not in the legal table."""


class AuthorizationError(ACPError):
    """Base class for control-authorization failures."""


class StaleAuthorizationError(AuthorizationError):
    """The world/constraint state changed since the authorization was minted.

    A commit-time revalidation found the bound world-state version or
    constraint-set version no longer matches the current one.
    """


class AuthorizationBindingError(AuthorizationError):
    """An authorization does not bind the action/decision it was presented with."""


class ConfigurationError(ACPError):
    """A required evaluator/component was missing or misconfigured.

    ACP fails closed on configuration errors: a missing evaluator must never be
    read as "no constraints, therefore authorize."
    """
