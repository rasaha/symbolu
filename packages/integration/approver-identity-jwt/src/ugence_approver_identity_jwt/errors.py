"""Typed errors. A refusal of a proof is an unauthenticated answer, never an
exception; exceptions are for the adapter being unable to answer at all (the port's
``IdentityUnavailable``) and for contract violations at the seams."""

from __future__ import annotations

from ugence_governed_review_service import ContractViolation, IdentityUnavailable


class KeyRetrievalFailed(IdentityUnavailable):
    """The JWKS could not be fetched or parsed. The service fails closed on it (row 7).

    The message names the kind of failure and never the response body, the token or
    any header value.
    """


class AdapterConfigurationError(ContractViolation):
    """The composition root supplied configuration the adapter refuses to run with."""
