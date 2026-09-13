"""The provider-credential custody seam: a port, its records, and an inert reference.

    NO CREDENTIAL LIVES HERE. This module holds no secret, reads no environment and
    reaches no secret manager. It is the *shape* a commissioned custody adapter must
    take (D-3, ``OWNER_RATIFICATION_LIVE_MODEL_PROVIDER.md``; ballot LP-2,
    ``ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md``), so that when the owner
    commissions one the unit already refuses everything else.

What the port promises
----------------------
* ``materialize`` answers a :class:`CredentialRequest` with a :class:`CredentialLease`
  or raises :class:`CustodyRefused` with a typed reason. A lease is short-lived and
  names its expiry; a provider that holds one past ``expires_at`` may not use it.
* The secret inside a lease is reachable only through :meth:`CredentialLease.use`,
  which hands it to one consumer callable and returns whatever that callable
  returns. It is not an attribute, it is absent from ``repr``, ``str``, ``==`` and
  ``as_record``, it cannot be pickled, and the audit event never carries it.
* Every materialization, granted or refused, is a :class:`CustodyAuditEvent` of
  identifiers and digests only, for the ledger (see ``ledger_kinds``).
* ``is_production_authoritative`` is the one bit the rest of the unit reads: a
  lease from an adapter that is not production-authoritative can never back a
  result that claims a genuine call. The reference adapter below is never
  production-authoritative and refuses a production posture outright.

  The word describes the **lease's authority under the real custody contract**: the
  credential was materialized by the commissioned custody path (Google Secret Manager,
  the pinned numeric version, the designated workload identity), not by a fake,
  emulator or reference path. It says nothing about the deployment the lease serves:
  a production-authoritative lease is exactly what the first live synthetic validation
  uses *within the non-production commissioning scope* (LP-7), and it authorizes no
  production deployment, which needs its own commissioning record.

What it does not decide
-----------------------
Which secret manager, which account, which rotation policy and who the custody
owner is. Those are the owner's designations (LP-2) and live in
``MEU_LIVE_PROVIDER_DESIGNATION.json``, not in code.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Protocol, TypeVar, runtime_checkable
from uuid import UUID

from .canonical import canonical_digest

__all__ = [
    "CUSTODY_AUDIT_DOMAIN",
    "CUSTODY_REQUEST_DOMAIN",
    "REFERENCE_CUSTODY_MARKER",
    "CustodyRefusal",
    "CustodyRefused",
    "CustodyRefusedInProduction",
    "CredentialRequest",
    "CredentialLease",
    "CustodyAuditEvent",
    "ModelCredentialCustodyPort",
    "ReferenceCustodyAdapter",
    "CustodyIdentity",
    "IDENTITY_KINDS",
    "PRODUCTION_AUTHORITATIVE_IDENTITY_KINDS",
    "is_service_account_resource",
    "is_pinned_secret_version",
    "PinnedSecretVersionCustodyAdapter",
    "materialize_with_audit",
]

CUSTODY_REQUEST_DOMAIN = "ugence.model-egress-unit/custody-request/v1"
CUSTODY_AUDIT_DOMAIN = "ugence.model-egress-unit/custody-audit/v1"

#: What the reference adapter hands a consumer instead of a credential. Loud, not
#: configurable, and refused by any vendor endpoint as a credential.
REFERENCE_CUSTODY_MARKER = "[UGENCE-REFERENCE-CUSTODY — NOT A CREDENTIAL]"

_T = TypeVar("_T")


class CustodyRefusal(str, enum.Enum):
    """Why custody would not hand out a lease. Each is terminal for the request."""

    #: No custody adapter has been commissioned for this deployment (D-3).
    NOT_COMMISSIONED = "custody_not_commissioned"
    #: The request names a profile or vendor this adapter does not hold.
    PROFILE_MISMATCH = "custody_profile_mismatch"
    #: The adapter cannot answer for this tenant.
    TENANT_NOT_SERVED = "custody_tenant_not_served"
    #: A reference adapter was asked to serve a production posture.
    REFERENCE_IN_PRODUCTION = "custody_reference_in_production"
    #: The secret manager did not answer; nothing is inferred from silence.
    CUSTODY_UNAVAILABLE = "custody_unavailable"


class CustodyRefused(RuntimeError):
    """Custody answered no, with a typed reason. Never carries a secret."""

    def __init__(self, reason: CustodyRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason


class CustodyRefusedInProduction(CustodyRefused):
    """A reference custody adapter was asked to serve a production posture."""

    def __init__(self, adapter: str) -> None:
        super().__init__(
            CustodyRefusal.REFERENCE_IN_PRODUCTION,
            f"{adapter} is a reference fixture and holds no credential; it refuses a "
            f"production posture rather than hand out a marker that could be mistaken "
            f"for one")


@dataclass(frozen=True)
class CredentialRequest:
    """What a provider adapter asks custody for. Identifiers only."""

    request_id: UUID
    tenant_id: UUID
    vendor: str
    credential_profile: str
    requested_at: datetime
    purpose: str = "model-egress"

    def __post_init__(self) -> None:
        for name in ("vendor", "credential_profile", "purpose"):
            if not getattr(self, name):
                raise ValueError(f"a credential request is incomplete without {name}")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")

    def digest_body(self) -> dict:
        return {
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "vendor": self.vendor,
            "credential_profile": self.credential_profile,
            "requested_at": self.requested_at,
            "purpose": self.purpose,
        }

    def digest(self) -> str:
        return canonical_digest(CUSTODY_REQUEST_DOMAIN, "CredentialRequest", self.digest_body())


class CredentialLease:
    """A short-lived grant of one credential to one consumer.

    **Not a dataclass, and it has no instance ``__dict__``.** Both are deliberate. The
    adversarial pass of 2026-09-13 found that a secret kept as a dataclass field with
    ``repr=False`` was still returned by ``dataclasses.asdict``, which walks ``fields()``
    and ignores ``repr``; moving it to an ``InitVar`` closed that but left
    ``vars(lease)`` and ``lease.__dict__`` open, and those are routine surfaces, not
    exotic ones — ``vars`` is what a structured logger or a generic JSON encoder reaches
    for. A plain class with ``__slots__`` closes the whole family at once:

    ============================== ==========================================
    Surface                        Result
    ============================== ==========================================
    ``vars(lease)``                ``TypeError`` — there is no ``__dict__``
    ``lease.__dict__``             ``AttributeError``
    ``dataclasses.asdict/astuple`` ``TypeError`` — not a dataclass instance
    ``repr`` / ``str`` / f-string  identifiers only
    ``==`` / ``hash``              identity; neither reads the credential
    ``json.dumps``                 ``TypeError``; with ``default=str``, the repr
    ``pickle`` / ``copy``          refused by ``__reduce__``
    ``as_record()``                identifiers and instants only
    attribute assignment           refused; the lease is immutable after birth
    ============================== ==========================================

    The credential is reachable through :meth:`use` and through nothing else this class
    provides. The honest boundary: code running in this process can still read the slot
    through ``CredentialLease.__slots__`` or ``gc``, and no Python object can prevent
    that. What is closed is every surface that a normal serializer, logger, debugger
    repr or exception renderer touches without being asked to go looking.
    """

    __slots__ = ("lease_id", "custody_authority_id", "credential_profile", "vendor",
                 "tenant_id", "secret_version_ref", "issued_at", "expires_at",
                 "is_production_authoritative", "_held", "_sealed")

    def __init__(self, *, lease_id: str, custody_authority_id: str, credential_profile: str,
                 vendor: str, tenant_id: UUID, secret_version_ref: str, issued_at: datetime,
                 expires_at: datetime, is_production_authoritative: bool,
                 _secret: str = "") -> None:
        if expires_at <= issued_at:
            raise ValueError("a lease must expire after it is issued")
        if not _secret:
            raise ValueError("a lease carries a credential or it is not a lease")
        if issued_at.tzinfo is None or expires_at.tzinfo is None:
            raise ValueError("lease instants must be timezone-aware")
        set_ = object.__setattr__
        set_(self, "lease_id", lease_id)
        set_(self, "custody_authority_id", custody_authority_id)
        set_(self, "credential_profile", credential_profile)
        set_(self, "vendor", vendor)
        set_(self, "tenant_id", tenant_id)
        set_(self, "secret_version_ref", secret_version_ref)
        set_(self, "issued_at", issued_at)
        set_(self, "expires_at", expires_at)
        set_(self, "is_production_authoritative", bool(is_production_authoritative))
        set_(self, "_held", _secret)
        set_(self, "_sealed", True)

    # --- immutable after birth --------------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"a CredentialLease is immutable; {name!r} may not be reassigned")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"a CredentialLease is immutable; {name!r} may not be deleted")

    # --- what it may say --------------------------------------------------------------

    def __repr__(self) -> str:  # never the secret
        return (f"CredentialLease(lease_id={self.lease_id!r}, "
                f"custody_authority_id={self.custody_authority_id!r}, "
                f"credential_profile={self.credential_profile!r}, vendor={self.vendor!r}, "
                f"secret_version_ref={self.secret_version_ref!r}, "
                f"expires_at={self.expires_at.isoformat()!r}, "
                f"is_production_authoritative={self.is_production_authoritative!r})")

    __str__ = __repr__

    def __format__(self, spec: str) -> str:  # f"{lease}" and f"{lease:anything}"
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        """Identity. Two leases never compare by content, so ``==`` never reads the
        credential and a timing difference never reveals one."""

        return self is other

    def __ne__(self, other: object) -> bool:
        return self is not other

    def __hash__(self) -> int:
        return id(self)

    # --- and what it refuses ----------------------------------------------------------

    def __getstate__(self):
        raise TypeError("a CredentialLease is never pickled, copied or serialized")

    __reduce__ = __getstate__
    __reduce_ex__ = lambda self, protocol: CredentialLease.__getstate__(self)  # noqa: E731
    __copy__ = __getstate__
    __deepcopy__ = lambda self, memo: CredentialLease.__getstate__(self)  # noqa: E731

    # --- the contract -----------------------------------------------------------------

    def expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def use(self, consumer: Callable[[str], _T], *, now: datetime) -> _T:
        """Hand the secret to ``consumer`` once and return its result.

        The consumer is the only place the secret is ever visible. It must not
        store it; a provider adapter uses it to build one request and lets it go.
        """

        if self.expired(now):
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE,
                                 f"lease {self.lease_id} expired at {self.expires_at.isoformat()}")
        return consumer(self._held)

    def as_record(self) -> dict:
        """Identifiers and instants only. The secret is not a field of the record."""

        return {
            "lease_id": self.lease_id,
            "custody_authority_id": self.custody_authority_id,
            "credential_profile": self.credential_profile,
            "vendor": self.vendor,
            "tenant_id": str(self.tenant_id),
            "secret_version_ref": self.secret_version_ref,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_production_authoritative": self.is_production_authoritative,
        }


@dataclass(frozen=True)
class CustodyAuditEvent:
    """One materialization, granted or refused, as the ledger records it."""

    request_digest: str
    tenant_id: UUID
    vendor: str
    credential_profile: str
    custody_authority_id: str
    observed_at: datetime
    outcome: str  # "LEASED" | "REFUSED"
    lease_id: Optional[str] = None
    secret_version_ref: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_production_authoritative: Optional[bool] = None
    refusal: Optional[CustodyRefusal] = None

    def __post_init__(self) -> None:
        if self.outcome not in ("LEASED", "REFUSED"):
            raise ValueError("a custody audit event is LEASED or REFUSED")
        if self.outcome == "REFUSED" and self.refusal is None:
            raise ValueError("a refused materialization names its reason")
        if self.outcome == "LEASED" and not self.lease_id:
            raise ValueError("a leased materialization names its lease")

    def as_record(self) -> dict:
        return {
            "kind": "meu.credential_leased" if self.outcome == "LEASED" else "meu.credential_refused",
            "request_digest": self.request_digest,
            "tenant_id": str(self.tenant_id),
            "vendor": self.vendor,
            "credential_profile": self.credential_profile,
            "custody_authority_id": self.custody_authority_id,
            "observed_at": self.observed_at.isoformat(),
            "outcome": self.outcome,
            "lease_id": self.lease_id,
            "secret_version_ref": self.secret_version_ref,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_production_authoritative": self.is_production_authoritative,
            "refusal": self.refusal.value if self.refusal is not None else None,
        }

    def digest(self) -> str:
        return canonical_digest(CUSTODY_AUDIT_DOMAIN, "CustodyAuditEvent", self.as_record())


@runtime_checkable
class ModelCredentialCustodyPort(Protocol):
    """What a commissioned custody adapter implements.

    Mirrors the credential broker's port (``cloud-scaling-credential-broker``):
    an authority id, a profile, the production-authoritative bit, and one method
    that either leases or refuses. ``max_credential_age`` is the rotation policy
    the adapter asserts; a lease never outlives it.
    """

    custody_authority_id: str
    credential_profile: str
    is_production_authoritative: bool
    max_credential_age: timedelta

    def materialize(self, request: CredentialRequest, *, now: datetime,
                    production: bool = False) -> CredentialLease:
        ...


class ReferenceCustodyAdapter:
    """Holds no credential. Leases an inert marker outside production; refuses
    inside it. Exists so the unit's custody path can be exercised end to end."""

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"
    is_production_authoritative = False

    def __init__(self, *, custody_authority_id: str = "ugence-reference-custody",
                 credential_profile: str = "reference-profile",
                 vendor: str = "reference-vendor",
                 lease_ttl: timedelta = timedelta(minutes=5),
                 max_credential_age: timedelta = timedelta(days=1)) -> None:
        self.custody_authority_id = custody_authority_id
        self.credential_profile = credential_profile
        self.vendor = vendor
        self.lease_ttl = lease_ttl
        self.max_credential_age = max_credential_age

    def materialize(self, request: CredentialRequest, *, now: datetime,
                    production: bool = False) -> CredentialLease:
        if production:
            raise CustodyRefusedInProduction(self.custody_authority_id)
        if request.credential_profile != self.credential_profile or request.vendor != self.vendor:
            raise CustodyRefused(
                CustodyRefusal.PROFILE_MISMATCH,
                f"{self.custody_authority_id} holds {self.vendor}/{self.credential_profile}, "
                f"not {request.vendor}/{request.credential_profile}")
        lease_id = canonical_digest(CUSTODY_AUDIT_DOMAIN, "ReferenceLease", {
            "request_digest": request.digest(), "custody_authority_id": self.custody_authority_id,
            "issued_at": now})
        return CredentialLease(
            lease_id=lease_id, custody_authority_id=self.custody_authority_id,
            credential_profile=self.credential_profile, vendor=self.vendor,
            tenant_id=request.tenant_id, secret_version_ref="reference/0",
            issued_at=now, expires_at=now + self.lease_ttl,
            is_production_authoritative=False, _secret=REFERENCE_CUSTODY_MARKER)


def materialize_with_audit(
    port: Any,
    request: CredentialRequest,
    *,
    now: datetime,
    production: bool = False,
    sink: Optional[Callable[[CustodyAuditEvent], None]] = None,
) -> tuple:
    """Ask ``port`` for a lease and record the outcome either way.

    Returns ``(lease_or_None, event)``. A port that raises anything but
    :class:`CustodyRefused` is recorded as ``CUSTODY_UNAVAILABLE`` and the exception
    is not propagated with its message, which might carry what the manager said.
    ``sink`` receives the event; ``None`` means the caller records it itself.
    """

    authority = str(getattr(port, "custody_authority_id", "unknown-custody"))
    lease: Optional[CredentialLease] = None
    refusal: Optional[CustodyRefusal] = None
    try:
        lease = port.materialize(request, now=now, production=production)
        if not isinstance(lease, CredentialLease):
            lease = None
            refusal = CustodyRefusal.CUSTODY_UNAVAILABLE
        elif lease.expires_at - lease.issued_at > getattr(port, "max_credential_age", timedelta.max):
            lease = None
            refusal = CustodyRefusal.CUSTODY_UNAVAILABLE
    except CustodyRefused as exc:
        refusal = exc.reason
    except Exception:  # noqa: BLE001 - the manager's words never reach the record
        refusal = CustodyRefusal.CUSTODY_UNAVAILABLE
    if lease is not None:
        event = CustodyAuditEvent(
            request_digest=request.digest(), tenant_id=request.tenant_id, vendor=request.vendor,
            credential_profile=request.credential_profile, custody_authority_id=authority,
            observed_at=now, outcome="LEASED", lease_id=lease.lease_id,
            secret_version_ref=lease.secret_version_ref, expires_at=lease.expires_at,
            is_production_authoritative=lease.is_production_authoritative)
    else:
        event = CustodyAuditEvent(
            request_digest=request.digest(), tenant_id=request.tenant_id, vendor=request.vendor,
            credential_profile=request.credential_profile, custody_authority_id=authority,
            observed_at=now, outcome="REFUSED", refusal=refusal)
    if sink is not None:
        sink(event)
    return lease, event


#: LP-2: how the unit proves who it is to the secret manager. A long-lived
#: service-account key is refused at construction, not discouraged in prose.
#:
#: ``native_gcp_workload_identity`` is the identity a Google-hosted runtime carries by
#: attachment — for the commissioning path, the Cloud Run Job's dedicated non-human
#: service account. ``application_default_credentials`` is NOT that: ADC is how a Google
#: client library *finds* some credential, and the thing it finds may be a developer's
#: user credential, a downloaded key or the default compute identity. It is a discovery
#: mechanism, never proof of identity, and it is never production-authoritative
#: (LP-8 identity clarification, 2026-09-13).
IDENTITY_KINDS = ("workload_identity_federation", "native_gcp_workload_identity",
                  "application_default_credentials", "fake_emulator", "service_account_key")

#: The two mechanisms LP-7 ruling 2 designates, and the only two that may back a
#: production-authoritative lease. Both must still name a non-human principal, and the
#: native one must be bound to the exact designated service-account resource.
PRODUCTION_AUTHORITATIVE_IDENTITY_KINDS = ("workload_identity_federation",
                                           "native_gcp_workload_identity")

#: A GCP service-account resource: ``projects/<project>/serviceAccounts/<email>``.
def is_service_account_resource(resource: str) -> bool:
    if not isinstance(resource, str):
        return False
    parts = resource.split("/")
    return (len(parts) == 4 and parts[0] == "projects" and parts[2] == "serviceAccounts"
            and bool(parts[1]) and "@" in parts[3] and parts[3].endswith(".iam.gserviceaccount.com"))


def _human_or_default_identity(principal: str) -> Optional[str]:
    """Why ``principal`` is not a dedicated non-human identity, or ``None``."""

    lowered = principal.strip().lower()
    if lowered.startswith("user:") or "@gmail." in lowered or "@googlemail." in lowered:
        return "a user credential is a human identity"
    if "-compute@" in lowered or lowered.endswith("developer.gserviceaccount.com"):
        return "the default compute identity is not the dedicated MEU identity"
    return None


@dataclass(frozen=True)
class CustodyIdentity:
    """How the unit proves who it is, and what that proof is worth.

    ``designated_service_account``, ``designation_attested_by`` and
    ``designation_record_digest`` are the binding and attestation inputs a native GCP
    workload identity needs before it may be production-authoritative. They are
    identifiers and a digest: no credential is a field of this record.
    """

    kind: str
    principal: str
    designated_service_account: str = ""
    designation_attested_by: str = ""
    designation_record_digest: str = ""

    def __post_init__(self) -> None:
        if self.kind not in IDENTITY_KINDS:
            raise ValueError(f"unknown identity kind {self.kind!r}")
        if self.kind == "service_account_key":
            raise ValueError(
                "a long-lived service-account key is itself a credential in the deployment "
                "and is refused (LP-2); use workload identity federation")
        if not self.principal:
            raise ValueError("an identity names its principal")

    def production_authority_refusal(self) -> Optional[str]:
        """Why this identity may not back a production-authoritative lease, or ``None``.

        The message names the rule and never the principal's secret-bearing content,
        because a principal is an identifier and nothing here is a credential.
        """

        if self.kind == "application_default_credentials":
            return ("application default credentials name no identity: ADC is how a client library "
                    "finds a credential, not proof of which one, so it is never production-authoritative; "
                    "assert native_gcp_workload_identity bound to the designated service account, or "
                    "workload identity federation (LP-8 identity clarification)")
        if self.kind not in PRODUCTION_AUTHORITATIVE_IDENTITY_KINDS:
            return (f"a {self.kind} identity is never production-authoritative; only workload identity "
                    f"federation or native GCP workload identity attached to the designated service "
                    f"account may be (LP-2, LP-8)")
        human = _human_or_default_identity(self.principal)
        if human is not None:
            return f"{human}; the MEU runs as a dedicated non-human identity (LP-7 ruling 2)"
        if self.kind == "native_gcp_workload_identity":
            if not is_service_account_resource(self.designated_service_account):
                return ("a native GCP workload identity is production-authoritative only when bound to the "
                        "exact designated service-account resource projects/<project>/serviceAccounts/<email> "
                        "(step-8 obligation 3)")
            if _human_or_default_identity(self.designated_service_account) is not None:
                return "the designated service account is a human or default-compute identity (LP-7 ruling 2)"
            if self.principal.strip() != self.designated_service_account.strip():
                return ("the runtime principal is not the designated service-account resource; a native "
                        "identity binds to exactly one account (step-8 obligation 3)")
            if not self.designation_attested_by.strip():
                return ("the step-8 designation record carries no independent verification; a native identity "
                        "is production-authoritative only under an attested designation (LP-7 ruling 12)")
            if not (len(self.designation_record_digest) == 64
                    and all(c in "0123456789abcdef" for c in self.designation_record_digest)):
                return ("the designation-record digest is absent or malformed; the identity binds to the exact "
                        "designation the owner attested (LP-7 ruling 12)")
        elif not (self.principal.startswith("principal://") or self.principal.startswith("principalSet://")
                  or ".iam.gserviceaccount.com" in self.principal):
            return ("a federated principal is the pool-constrained principal:// binding or the impersonated "
                    "service account (step-8 obligation 5)")
        return None


def is_pinned_secret_version(resource: str) -> bool:
    """``projects/<p>/secrets/<s>/versions/<n>`` with a numeric ``<n>``. ``latest`` is
    never pinned (LP-2), and a resource that resolves at execution time is not one a
    record can pin."""

    if not isinstance(resource, str):
        return False
    parts = resource.split("/")
    return (len(parts) == 6 and parts[0] == "projects" and parts[2] == "secrets"
            and parts[4] == "versions" and all(parts[i] for i in (1, 3))
            and parts[5].isdigit())


class PinnedSecretVersionCustodyAdapter:
    """The Google Secret Manager custody adapter's *shape*, over an injected reader.

    LP-6 step 5 authorizes the fake/emulator path only: ``reader`` is whatever returns
    the payload of one pinned secret version, and in this distribution it is always a
    test double. The real client (Secret Manager over workload identity federation)
    is a separate distribution, because this package refuses network imports. What is
    real here and pinned by tests: the resource must be an exact version, never
    ``latest``; the identity may never be a service-account key; the adapter is
    production-authoritative only under workload identity federation and never on the
    fake path; a reader failure is ``CUSTODY_UNAVAILABLE`` without its message; the
    lease names the exact version it came from.
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self, *, custody_authority_id: str, credential_profile: str, vendor: str,
                 secret_version_resource: str, identity: CustodyIdentity,
                 reader: Callable[[str], str], lease_ttl: timedelta = timedelta(minutes=5),
                 max_credential_age: timedelta = timedelta(days=90),
                 production_authoritative: bool = False) -> None:
        if not is_pinned_secret_version(secret_version_resource):
            raise ValueError(
                "the secret version must be pinned as projects/<p>/secrets/<s>/versions/<n>; "
                "'latest' is never resolved during execution (LP-2)")
        if max_credential_age > timedelta(days=90):
            raise ValueError("rotation is at least every 90 days (LP-2)")
        if production_authoritative:
            why = identity.production_authority_refusal()
            if why is not None:
                raise ValueError(why)
        self.custody_authority_id = custody_authority_id
        self.credential_profile = credential_profile
        self.vendor = vendor
        self.secret_version_resource = secret_version_resource
        self.identity = identity
        self.lease_ttl = lease_ttl
        self.max_credential_age = max_credential_age
        self.is_production_authoritative = bool(production_authoritative)
        self._reader = reader

    def materialize(self, request: CredentialRequest, *, now: datetime,
                    production: bool = False) -> CredentialLease:
        if production and not self.is_production_authoritative:
            raise CustodyRefusedInProduction(self.custody_authority_id)
        if request.credential_profile != self.credential_profile or request.vendor != self.vendor:
            raise CustodyRefused(
                CustodyRefusal.PROFILE_MISMATCH,
                f"{self.custody_authority_id} holds {self.vendor}/{self.credential_profile}, "
                f"not {request.vendor}/{request.credential_profile}")
        try:
            payload = self._reader(self.secret_version_resource)
        except Exception:  # noqa: BLE001 - the manager's words never reach a record
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE,
                                 f"{self.secret_version_resource} could not be read") from None
        if not isinstance(payload, str) or not payload.strip():
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE,
                                 f"{self.secret_version_resource} is empty")
        lease_id = canonical_digest(CUSTODY_AUDIT_DOMAIN, "PinnedVersionLease", {
            "request_digest": request.digest(), "custody_authority_id": self.custody_authority_id,
            "secret_version_resource": self.secret_version_resource, "issued_at": now})
        return CredentialLease(
            lease_id=lease_id, custody_authority_id=self.custody_authority_id,
            credential_profile=self.credential_profile, vendor=self.vendor,
            tenant_id=request.tenant_id, secret_version_ref=self.secret_version_resource,
            issued_at=now, expires_at=now + self.lease_ttl,
            is_production_authoritative=self.is_production_authoritative, _secret=payload)
