"""The broker port (ADR 5X, D-1): custody stays behind it, as with TEV's signer port.

A :class:`CredentialBrokerPort` names the authority it speaks for and the one profile it
issues, declares whether it is production-authoritative, and materializes exactly one
package-minted :class:`CredentialRequest` into a :class:`CredentialGrant`. It is never
handed a caller-chosen request. A KMS-, STS- or vault-backed broker implements the same
port and drops in without touching a caller; nothing in this repository ever holds the
provider secret it exchanges.

:class:`ReferenceCredentialBroker` returns an inert handle for conformance and declares
``is_production_authoritative = False``, so the production seam refuses it at construction.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ugence_governance_contracts.api import Validity

from .grant import CredentialGrant, GrantDisposition, derive_grant_id
from .identifiers import CREDENTIAL_PROFILE
from .request import CredentialRequest

__all__ = ["CredentialBrokerPort", "ReferenceCredentialBroker", "REFERENCE_BROKER_AUTHORITY_ID"]

REFERENCE_BROKER_AUTHORITY_ID = "ugence.reference-credential-broker"


@runtime_checkable
class CredentialBrokerPort(Protocol):
    @property
    def broker_authority_id(self) -> str: ...

    @property
    def credential_profile(self) -> str: ...

    @property
    def is_production_authoritative(self) -> bool: ...

    def materialize(self, request: CredentialRequest) -> CredentialGrant: ...


class ReferenceCredentialBroker:
    """Inert conformance broker: a handle that opens nothing. Never production."""

    is_production_authoritative = False

    @property
    def broker_authority_id(self) -> str:
        return REFERENCE_BROKER_AUTHORITY_ID

    @property
    def credential_profile(self) -> str:
        return CREDENTIAL_PROFILE

    def materialize(self, request: CredentialRequest) -> CredentialGrant:
        if type(request) is not CredentialRequest:
            raise TypeError("materialize requires a package-minted CredentialRequest")
        return CredentialGrant(
            grant_id=derive_grant_id(request.request_digest),
            tenant_id=request.tenant_id,
            request_digest=request.request_digest,
            handle_ref="inert:" + request.request_digest.split(":", 1)[1][:32],
            role=request.role,
            validity=Validity(issued_at=request.issued_at, expires_at=request.not_after),
            broker_authority_id=self.broker_authority_id,
            credential_profile=self.credential_profile,
            disposition=GrantDisposition.MATERIALIZED,
        )
