"""The exchange's failure vocabulary, free of any database driver.

These live at the package root rather than beside the store that raises them, and
the reason is not tidiness. ``reconcile.py`` catches :class:`RequestNotClaimable`
at runtime; while that exception was defined in ``postgres/exchange.py``, catching
it meant importing the module that imports ``psycopg`` — so the whole package
required the driver, including the records, the digests and the providers that
have nothing to do with storage.

That was a real defect and CI is what found it: every test passed, because the
boundary test read *direct* imports and the chain
``__init__ → reconcile → postgres.exchange → psycopg`` is three deep. The step
that actually uninstalled the driver and tried to import the package failed on
all three Pythons. A structural test that reasons about imports is not a
substitute for removing the dependency and looking.

An exception is part of what a caller has to understand, not part of how the
store is implemented. Splitting them here is what lets the claim in the README be
true.
"""

from __future__ import annotations

__all__ = [
    "ExchangeError",
    "UnscopableConnection",
    "TenantMismatch",
    "RequestNotClaimable",
    "ResultNotAcknowledgeable",
]


class ExchangeError(RuntimeError):
    """A request or result could not be moved the way the caller asked."""


class UnscopableConnection(ExchangeError):
    """A connection arrived mid-transaction, so tenant identity cannot be scoped.

    ``SET LOCAL`` is scoped to the enclosing **transaction**, not to a savepoint.
    On a connection that already has one open, ``conn.transaction()`` opens a
    savepoint instead, and the tenant identity established inside it survives the
    savepoint's release — staying live for the rest of the outer transaction and
    for whatever the next caller does with it. That is a cross-tenant read no
    policy can catch, because by then the session genuinely *is* that tenant.

    Demonstrated in ``tests/test_rls.py``: on an IDLE connection the identity
    reverts to the empty string and the next read fails closed; on an ``INTRANS``
    one it leaks. So the exchange refuses rather than degrade quietly.
    """


class TenantMismatch(ExchangeError):
    """A row came back carrying a tenant the caller did not ask for.

    Raised by the application-level check. Reaching this means row-level security
    did not do its job, so the transaction is abandoned rather than trusted.
    """


class RequestNotClaimable(ExchangeError):
    """The request is not in a state a result may be recorded against."""


class ResultNotAcknowledgeable(ExchangeError):
    """No unacknowledged result exists for this request."""
