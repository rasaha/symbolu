"""Transport protection for the exchange's own connections (D-4, spec §4.4, §5.2).

Content crosses the wire between the worker, the unit and the exchange. Row-level
security decides who may read a row; it says nothing about who may observe it in
flight. A production DSN must therefore require a verified TLS session:
``sslmode=verify-full``, which checks both the certificate chain and the host name.
Anything weaker (``require`` verifies nothing about *whom* you are talking to;
``prefer`` and ``disable`` may send plaintext) is refused in production.

Outside production nothing is refused, so the test cluster on loopback keeps working;
the policy is still applied, so the refusal is exercised, not assumed. No DSN, and
nothing derived from one, is ever logged or included in an error message beyond the
``sslmode`` value itself.
"""

from __future__ import annotations

from typing import Callable, Optional

__all__ = ["REQUIRED_SSLMODE", "TransportUnprotected", "sslmode_of", "require_transport_protection",
           "protected_connect"]

REQUIRED_SSLMODE = "verify-full"


class TransportUnprotected(ValueError):
    """A production DSN that would let content travel unverified."""


def sslmode_of(dsn: str) -> Optional[str]:
    """The ``sslmode`` a DSN asks for, in either libpq form, or ``None``.

    No parsing library: ``urllib`` is a network-capable module this package refuses
    to import, and the two shapes are simple enough to read by hand.
    """

    if not isinstance(dsn, str) or not dsn:
        return None
    if "://" in dsn:
        _, _, tail = dsn.partition("://")
        _, question, query = tail.partition("?")
        if not question:
            return None
        for pair in query.split("&"):
            key, eq, value = pair.partition("=")
            if eq and key == "sslmode":
                return value or None
        return None
    for token in dsn.split():
        key, eq, value = token.partition("=")
        if eq and key == "sslmode":
            return value.strip("'\"") or None
    return None


def require_transport_protection(dsn: str, *, production: bool) -> str:
    """The DSN, unchanged, if the posture admits it; else :class:`TransportUnprotected`."""

    if not isinstance(dsn, str) or not dsn.strip():
        raise TransportUnprotected("a DSN is required")
    mode = sslmode_of(dsn)
    if production and mode != REQUIRED_SSLMODE:
        raise TransportUnprotected(
            f"a production DSN must carry sslmode={REQUIRED_SSLMODE} (found "
            f"{mode or 'no sslmode'}): content crosses this connection and an unverified "
            f"session is not an approved transport (spec section 4.4)")
    return dsn


def protected_connect(dsn: str, *, production: bool,
                      connect: Optional[Callable[[str], object]] = None) -> Callable[[], object]:
    """The zero-argument ``connect`` the :class:`Exchange` takes, over a policy-checked DSN.

    ``connect`` defaults to ``psycopg.connect`` and is imported only here, lazily, so
    the check itself needs no driver.
    """

    checked = require_transport_protection(dsn, production=production)
    if connect is None:
        import psycopg  # the only third-party import, and only in this subpackage

        connect = psycopg.connect

    def open_connection():
        return connect(checked)

    return open_connection
