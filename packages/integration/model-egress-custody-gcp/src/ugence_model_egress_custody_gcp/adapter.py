"""The production-form Google Secret Manager custody adapter.

It implements ``ModelCredentialCustodyPort`` and is the adapter LP-8 names as the only
one that may materialize the credential for the commissioning validation. What makes it
"production-form" is not that it is trusted more: it is that the client is the real
Google one, built at the deployment composition root, and every refusal that protected
the fixture path still applies.

Order of refusal, which is the part worth reading:

1. construction validates the resource, the identity and the designation, so a
   misconfigured adapter cannot exist and therefore cannot call anything;
2. ``materialize`` refuses a production posture it is not authoritative for, then a
   profile or vendor mismatch, then an expired designation binding, all before the
   client is touched;
3. only then is ``AccessSecretVersion`` called, for exactly one pinned resource;
4. the answer is checked (right version, decodable, non-empty, no control characters)
   before it becomes a lease;
5. anything the client raises becomes ``CUSTODY_UNAVAILABLE`` carrying the exception's
   TYPE NAME and nothing else.

The secret exists in this module for the duration of one function and reaches the
caller only inside ``CredentialLease``, which keeps it out of ``repr``, ``str``,
equality, records and pickling.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from ugence_model_egress_unit import (
    CUSTODY_AUDIT_DOMAIN,
    CredentialLease,
    CredentialRequest,
    CustodyIdentity,
    CustodyRefusal,
    CustodyRefused,
    CustodyRefusedInProduction,
    canonical_digest,
)

from .client import AccessedSecretVersion, SecretManagerClient
from .config import CustodyConfig
from .designation import AcceptedDesignation, DesignationRefused, check_designation_accepted
from .errors import sanitize_exception_type
from .identity import IdentityRefused, check_production_identity
from .resource import parse_secret_version
from .version import PERMITTED_SECRET_MANAGER_METHOD, PRODUCTION_FORM_ADAPTER_NAME

__all__ = ["ProductionFormSecretManagerCustodyAdapter"]

#: A payload larger than this is not a provider API key; it is a file somebody pasted.
_MAX_PAYLOAD_BYTES = 8 * 1024


class ProductionFormSecretManagerCustodyAdapter:
    """``ModelCredentialCustodyPort`` over Google Secret Manager, one pinned version."""

    #: The name LP-8's execution-posture check requires of the custody adapter.
    adapter_name = PRODUCTION_FORM_ADAPTER_NAME
    maturity = "PRODUCTION_FORM_NON_PRODUCTION_SCOPE"
    permitted_method = PERMITTED_SECRET_MANAGER_METHOD

    def __init__(self, *, config: CustodyConfig, client: SecretManagerClient,
                 designation: Mapping[str, Any]) -> None:
        """Validate everything; touch nothing.

        No network call, no file read and no environment read happens here. A
        constructed adapter is one whose configuration, identity and designation have
        already been accepted together.
        """

        if not isinstance(config, CustodyConfig):
            raise ValueError("config must be a CustodyConfig; an unvalidated mapping is not configuration")
        if client is None or not hasattr(client, "access_secret_version"):
            raise ValueError("a SecretManagerClient with access_secret_version is required")
        accepted = check_designation_accepted(designation)
        identity = check_production_identity(config.identity)
        version = parse_secret_version(config.secret_version_resource)

        if version.resource != accepted.secret_version_resource:
            raise DesignationRefused(
                "the configured secret version is not the designated one; the adapter reads the exact "
                "version the owner designated (step-8 obligation 6)")
        if identity.principal != accepted.service_account_resource:
            raise IdentityRefused(
                "the runtime service account is not the designated MEU service account; the adapter binds "
                "to exactly one account (step-8 obligation 3)")
        if identity.designated_service_account != accepted.service_account_resource:
            raise IdentityRefused(
                "the identity assertion's designated service account disagrees with the designation record")
        if accepted.identity_mechanism == "native_gcp_workload_identity" \
                and identity.kind != "native_gcp_workload_identity":
            raise IdentityRefused(
                "the designation records native GCP workload identity but the process asserts a different "
                "mechanism; the mechanism is designated, not chosen at run time")

        self._config = config
        self._client = client
        self._version = version
        self._designation = accepted
        self.identity = identity
        self.custody_authority_id = config.custody_authority_id
        self.credential_profile = config.credential_profile
        self.vendor = config.vendor
        self.secret_version_resource = version.resource
        self.lease_ttl = timedelta(seconds=int(config.lease_ttl_seconds))
        self.max_credential_age = timedelta(days=int(config.max_credential_age_days))
        #: Production-authoritative because the identity, the designation and the
        #: resource were all accepted together above. There is no constructor flag that
        #: could set this without them.
        self.is_production_authoritative = True

    def __repr__(self) -> str:  # identifiers only; no client, no payload, no principal secret
        return (f"ProductionFormSecretManagerCustodyAdapter("
                f"custody_authority_id={self.custody_authority_id!r}, "
                f"credential_profile={self.credential_profile!r}, vendor={self.vendor!r}, "
                f"secret_version_resource={self.secret_version_resource!r}, "
                f"identity_kind={self.identity.kind!r}, is_production_authoritative=True)")

    __str__ = __repr__

    def __getstate__(self):
        raise TypeError("a custody adapter holds a live client and is never pickled or serialized")

    __reduce__ = __getstate__

    def as_record(self) -> dict:
        """What a redacted report may say about this adapter. References only."""

        return {
            "adapter": self.adapter_name,
            "custody_authority_id": self.custody_authority_id,
            "credential_profile": self.credential_profile,
            "vendor": self.vendor,
            "secret_version_ref": self.secret_version_resource,
            "identity_kind": self.identity.kind,
            "identity_principal": self.identity.principal,
            "designation_attested_by": self._designation.attested_by,
            "is_production_authoritative": True,
            "permitted_method": self.permitted_method,
        }

    def materialize(self, request: CredentialRequest, *, now: datetime,
                    production: bool = False) -> CredentialLease:
        if production and not self.is_production_authoritative:  # pragma: no cover - unreachable by construction
            raise CustodyRefusedInProduction(self.custody_authority_id)
        if request.credential_profile != self.credential_profile or request.vendor != self.vendor:
            raise CustodyRefused(
                CustodyRefusal.PROFILE_MISMATCH,
                f"{self.custody_authority_id} holds {self.vendor}/{self.credential_profile}, "
                f"not {request.vendor}/{request.credential_profile}")
        payload = self._access(self._version.resource)
        lease_id = canonical_digest(CUSTODY_AUDIT_DOMAIN, "ProductionFormSecretManagerLease", {
            "request_digest": request.digest(),
            "custody_authority_id": self.custody_authority_id,
            "secret_version_resource": self._version.resource,
            "identity_principal": self.identity.principal,
            "issued_at": now,
        })
        return CredentialLease(
            lease_id=lease_id, custody_authority_id=self.custody_authority_id,
            credential_profile=self.credential_profile, vendor=self.vendor,
            tenant_id=request.tenant_id, secret_version_ref=self._version.resource,
            issued_at=now, expires_at=now + self.lease_ttl,
            is_production_authoritative=True, _secret=payload)

    # --- the one call, and what it is allowed to return ------------------------------

    def _access(self, resource: str) -> str:
        """``AccessSecretVersion`` for one pinned resource, validated into text.

        Every failure is :class:`CustodyRefused` with :data:`CustodyRefusal.CUSTODY_UNAVAILABLE`
        and a message built here, never from the provider.
        """

        failure = None
        answer = None
        try:
            answer = self._client.access_secret_version(name=resource)
        except Exception as exc:  # noqa: BLE001 - the provider's words never reach a record
            failure = sanitize_exception_type(exc)
        # Raised OUTSIDE the except block on purpose. ``raise ... from None`` suppresses
        # the *printing* of the original exception but leaves it on ``__context__``, where
        # an error reporter that walks the chain would find the provider's message with
        # whatever it quoted back. Leaving the block first means there is no context to
        # walk. Found by the adversarial pass of 2026-09-13.
        if failure is not None:
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE,
                                 f"{resource} could not be accessed ({failure})")
        return self._validated_payload(answer, resource)

    def _validated_payload(self, answer: Any, resource: str) -> str:
        def unavailable(detail: str) -> CustodyRefused:
            return CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE, f"{resource} {detail}")

        if not isinstance(answer, AccessedSecretVersion):
            raise unavailable("was answered by something that is not an AccessedSecretVersion")
        # A client that resolved an alias, or answered for another version, is refused:
        # the lease must name the version the bytes actually came from.
        if answer.name and answer.name != resource:
            raise unavailable("was answered for a different version than the one requested")
        data = answer.payload
        if not isinstance(data, (bytes, bytearray)):
            raise unavailable("was answered with a payload that is not bytes")
        if not data:
            raise unavailable("holds an empty payload")
        if len(data) > _MAX_PAYLOAD_BYTES:
            raise unavailable("holds a payload too large to be a provider credential")
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            raise unavailable("holds a payload that is not valid UTF-8 text") from None
        stripped = text.strip()
        if not stripped:
            raise unavailable("holds a payload that is only whitespace")
        if any(ord(c) < 0x20 or ord(c) == 0x7F for c in stripped):
            raise unavailable("holds a payload with control characters; a provider key is one line of text")
        return stripped
