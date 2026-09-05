"""Typed errors. Every one is a *refusal*; none is ever promoted to a grant."""

from __future__ import annotations


class AuthorityDirectoryError(Exception):
    """Base class for every error this package raises."""


class ContractViolation(AuthorityDirectoryError, ValueError):
    """A caller supplied structurally invalid input (naive datetime, blank id, wrong type)."""


class GrantNotFoundError(AuthorityDirectoryError, LookupError):
    """No grant exists for the given id."""


class GrantAlreadyExistsError(AuthorityDirectoryError):
    """A grant would collide with an existing grant id.

    Raised rather than silently replacing it: a grant is a record of what an
    administrator loaded, and overwriting one would lose that record.
    """


class DelegationRefused(AuthorityDirectoryError):
    """A delegated grant is inadmissible.

    The delegator's own grant is absent or not valid at the same instant, the
    delegated scope is not a subset of the delegator's, the tenant differs, or the
    delegator's grant is itself delegated — delegation stops after one hop.
    """


class RecordIntegrityError(AuthorityDirectoryError, ValueError):
    """A stored grant does not re-derive its own record digest."""


class StoreUnavailableError(AuthorityDirectoryError):
    """The durable store cannot be reached. Callers fail closed."""


class ProductionModeRefused(AuthorityDirectoryError):
    """A reference-grade adapter was asked to run in production mode."""
