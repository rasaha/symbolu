"""The exchange vocabulary: the authorization binding, the records, and their digests.

Conformance note. This module was written before `SPEC_MODEL_EGRESS_UNIT.md` and
`OWNER_RATIFICATION_MEU_EXCHANGE_TENANCY.md` were ratified on 2026-09-10, and is
now written against them. Where the two differ, the ruling wins.

Five ideas here are load-bearing.

**The MEU verifies an authorization; it never makes one.** ``AuthorizationBinding``
carries what the authorization already decided — the clearance receipt and its
digest, the tenant, the vendor and model that were selected, the policy identity
and the reservation identity. The unit's only job against it is to check that the
target it is about to call is the target that was authorized. Claiming work
confers no authority over what was claimed, so there is no method here that
grants, widens or re-derives any of those fields. D-5 binds at authorization; this
package is downstream of that and stays downstream.

**A refusal is terminal.** A retriable condition is not a refusal; it is a request
that is still ``PENDING``. Every ``RefusalReason`` names a condition re-running
cannot change, and there is no ``OTHER`` member — an escape hatch becomes the one
everybody uses.

**``OUTCOME_UNKNOWN`` is terminal, and its reservation is never released.** It is
recorded when dispatch may already have happened and no result was durably
committed. Retrying would turn "we don't know" into "we did it twice", and a
duplicated billed inference cannot be undone. Neither lease expiry nor content
purging releases the vendor allocation: purging the content does not purge the
obligation.

**An ambiguous dispatch writes a different record, not a half-filled response.**
``DispatchAttempt`` asserts only locally known facts and leaves provider receipt,
acceptance, completion, billing, tokens, cost and even response existence
explicitly ``UNKNOWN``. A partially filled response record would quietly assert
zeros for things nobody measured.

**Consumption is acknowledged, not assumed** — and acknowledgement is a grace, not
a licence. Content is purged at the earlier of one hour after the worker's durable
acknowledgement and 24 hours after that artifact's own creation. A missing
acknowledgement never extends the hard deadline.
"""

from __future__ import annotations

import enum
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping, Optional, Sequence, Tuple
from uuid import UUID

from .canonical import (
    EGRESS_REQUEST_DIGEST_DOMAIN,
    EGRESS_RESULT_DIGEST_DOMAIN,
    canonical_digest,
    minimized_context_digest,
    payload_digest,
)

__all__ = [
    "EXCHANGE_SCHEMA_VERSION",
    "TRUST_LEVEL",
    "ACKNOWLEDGEMENT_GRACE",
    "HARD_RETENTION_DEADLINE",
    "RequestState",
    "ResultOutcome",
    "RefusalReason",
    "ProvenanceKind",
    "TERMINAL_STATES",
    "MinimizedUnit",
    "AuthorizationBinding",
    "DispatchAttempt",
    "EgressRequest",
    "EgressResult",
    "purge_deadline",
]

#: The version of the exchange a request is written under. Bound into the request
#: digest, so a request cannot be reinterpreted under a later schema — which is
#: the whole reason it is a field rather than a deployment fact.
EXCHANGE_SCHEMA_VERSION = "ugence.model-egress-unit/exchange/v1"

#: There is no other value. ``trust`` is not something the MEU computes: D-1 grants
#: the response nothing, so the output arrives as evidence to be verified
#: downstream and is never believed because it arrived.
TRUST_LEVEL = "UNTRUSTED_EVIDENCE"

#: Ratified 2026-09-10. Engineering may shorten neither here; production policy may
#: shorten both, and may lengthen neither without a new owner ruling.
ACKNOWLEDGEMENT_GRACE = timedelta(hours=1)
HARD_RETENTION_DEADLINE = timedelta(hours=24)


class RequestState(str, enum.Enum):
    """Where a request is in the exchange.

    ``PENDING`` and ``LEASED`` are the only non-terminal states. Nothing leaves a
    terminal state; a purge destroys content without changing it.
    """

    PENDING = "PENDING"
    LEASED = "LEASED"
    COMPLETED = "COMPLETED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


TERMINAL_STATES = frozenset({
    RequestState.COMPLETED,
    RequestState.REFUSED,
    RequestState.FAILED,
    RequestState.OUTCOME_UNKNOWN,
})


class ResultOutcome(str, enum.Enum):
    """What the unit found out. Four outcomes, none of them an exception.

    ``FAILED`` is a call that demonstrably did not produce a result.
    ``OUTCOME_UNKNOWN`` is a call that may or may not have happened. Collapsing
    the two would let a schema record "it failed" for something nobody knows the
    outcome of, which is a lie the ledger would carry forever.
    """

    ANSWERED = "ANSWERED"
    REFUSED = "REFUSED"
    FAILED = "FAILED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


class ProvenanceKind(str, enum.Enum):
    """Which shape of provenance a result carries.

    ``DISPATCH_ATTEMPT`` is a distinct record type, not a response record with
    empty fields — see :class:`DispatchAttempt`.
    """

    RESPONSE = "RESPONSE"
    DISPATCH_ATTEMPT = "DISPATCH_ATTEMPT"


class RefusalReason(str, enum.Enum):
    """Terminal refusals. Each names a condition re-running cannot change."""

    MODEL_NOT_AVAILABLE = "model_not_available"
    PURPOSE_NOT_PERMITTED = "purpose_not_permitted"
    CONTENT_EXCEEDS_CEILING = "content_exceeds_ceiling"
    ALREADY_TERMINAL = "already_terminal"
    LIVE_EGRESS_NOT_AVAILABLE = "live_egress_not_available"
    #: The target the unit was about to call is not the target the authorization
    #: named. Terminal: the unit may not broaden or reinterpret a binding.
    TARGET_NOT_AUTHORIZED = "target_not_authorized"
    #: The stored content no longer hashes to the digest the request was written
    #: with. Terminal: a substituted prompt is a different logical action.
    CONTENT_DIGEST_MISMATCH = "content_digest_mismatch"
    #: The request's own expiry has passed, independently of any lease.
    REQUEST_NOT_VALID = "request_not_valid"
    #: No provider credential has been commissioned in this deployment.
    CREDENTIAL_NOT_COMMISSIONED = "credential_not_commissioned"
    #: A row belonging to another tenant. Never disclosed as such to a caller —
    #: cross-tenant reads are indistinguishable from unknown — but named
    #: internally so the refusal is not a generic database error.
    TENANT_SCOPE_REFUSED = "tenant_scope_refused"
    #: LP-5: outside the commissioning limits bound into the request (tokens,
    #: streaming, store, tools, background). Terminal for the request as written.
    REQUEST_LIMIT_EXCEEDED = "request_limit_exceeded"
    #: LP-5: the call count, budget or concurrency reservation would be exceeded.
    #: Non-compensatory: nothing refunds it.
    COMMISSIONING_BUDGET_EXHAUSTED = "commissioning_budget_exhausted"
    #: LP-3: the authorized model is a floating alias, not a dated snapshot.
    MODEL_NOT_PINNED = "model_not_pinned"
    #: LP-1, LP-3: a URL other than the one designated destination.
    DESTINATION_NOT_PERMITTED = "destination_not_permitted"


@dataclass(frozen=True)
class MinimizedUnit:
    """One unit Context Minimization admitted, in the order the run fixed.

    ``token_count`` is the unit's declared size. It is metering, not content: it
    survives a purge, so a tombstone can still say how much was sent without
    saying what.
    """

    unit_id: str
    text: str
    token_count: int

    def __post_init__(self) -> None:
        if not self.unit_id:
            raise ValueError("a minimized unit must carry an identifier")
        if self.token_count < 0:
            raise ValueError("token_count cannot be negative")


@dataclass(frozen=True)
class AuthorizationBinding:
    """What the authorization decided, carried so the unit can verify it.

    The MEU **verifies**; it does not decide. There is deliberately no constructor
    here that derives a vendor, resolves a model alias or mints a reservation:
    every field arrives already decided by Model Authority under D-5's
    ``BIND_AT_AUTHORIZATION``, and this package is downstream of that.
    """

    clearance_ref: str
    clearance_digest: str
    tenant_id: UUID
    authorized_vendor: str
    authorized_model: str
    policy_id: str
    reservation_id: str

    def __post_init__(self) -> None:
        missing = [
            name for name in (
                "clearance_ref", "clearance_digest", "authorized_vendor",
                "authorized_model", "policy_id", "reservation_id")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                f"an authorization binding is incomplete without {missing}: an "
                f"unbound field is a target nobody authorized")

    def authorizes(self, *, vendor: str, model: str, tenant_id: UUID) -> bool:
        """Whether this binding authorizes exactly this target, for this tenant.

        Exact equality on every component. There is no family match, no alias
        resolution and no prefix rule: an authorization for one model does not
        authorize its successor, and D-5 reserved capacity against *this* pair.
        """

        return (
            vendor == self.authorized_vendor
            and model == self.authorized_model
            and tenant_id == self.tenant_id
        )

    def digest_body(self) -> dict:
        return {
            "clearance_ref": self.clearance_ref,
            "clearance_digest": self.clearance_digest,
            "tenant_id": str(self.tenant_id),
            "authorized_vendor": self.authorized_vendor,
            "authorized_model": self.authorized_model,
            "policy_id": self.policy_id,
            "reservation_id": self.reservation_id,
        }


@dataclass(frozen=True)
class DispatchAttempt:
    """Locally known facts about a dispatch whose outcome is unknown.

    Every provider-side fact is ``UNKNOWN`` and stays ``UNKNOWN`` unless something
    independent evidences it. That is the point of the type: a response record
    with empty fields would assert zero tokens and zero cost for a call that may
    have consumed both.
    """

    #: Explicitly unknown, always, for every provider-side fact.
    UNKNOWN = "UNKNOWN"

    adapter_id: str
    dispatch_observed_at: Optional[datetime]
    detected_at: datetime
    reason: str

    def as_record(self) -> dict:
        """The durable shape. The ``UNKNOWN``s are written, not omitted.

        Omitting them would let a reader infer absence from silence; writing them
        makes the ignorance explicit and survives into the tombstone, where it is
        what keeps a purged ``OUTCOME_UNKNOWN`` reconcilable.
        """

        return {
            "kind": ProvenanceKind.DISPATCH_ATTEMPT.value,
            "adapter_id": self.adapter_id,
            "genuine_call": False,
            "dispatch_observed_at": (
                self.dispatch_observed_at.isoformat()
                if self.dispatch_observed_at is not None else self.UNKNOWN),
            "detected_at": self.detected_at.isoformat(),
            "reason": self.reason,
            "provider_receipt": self.UNKNOWN,
            "provider_acceptance": self.UNKNOWN,
            "provider_completion": self.UNKNOWN,
            "billed": self.UNKNOWN,
            "token_usage": self.UNKNOWN,
            "cost": self.UNKNOWN,
            "response_exists": self.UNKNOWN,
        }


def purge_deadline(
    *, content_created_at: datetime, acknowledged_at: Optional[datetime]
) -> datetime:
    """When this artifact's content must be gone. Earlier of the two clocks.

    The hard deadline is not conditional: **absence of an acknowledgement never
    extends content past 24 hours.** A worker that never acknowledges does not
    thereby keep a prompt alive; it only loses the earlier purge it would have got
    by acknowledging.

    Each content-bearing artifact is governed independently, so a request's
    context and its response each carry their own creation instant and are purged
    on their own clock rather than waiting on the exchange as a unit.
    """

    hard = content_created_at + HARD_RETENTION_DEADLINE
    if acknowledged_at is None:
        return hard
    return min(acknowledged_at + ACKNOWLEDGEMENT_GRACE, hard)


@dataclass(frozen=True)
class EgressRequest:
    """One authorized request for a model exchange, as the worker wrote it.

    ``minimized_context`` is the purgeable artifact; ``content_digest`` is its
    fingerprint and outlives it. Everything else is immutable identity, and all of
    it is bound into ``request_digest``.
    """

    request_id: UUID
    tenant_id: UUID
    correlation_id: UUID
    submitted_at: datetime
    not_valid_after: datetime
    authorization: AuthorizationBinding
    minimized_context: Optional[Tuple[MinimizedUnit, ...]]
    content_digest: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    exchange_schema_version: str = EXCHANGE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        request_id: UUID,
        tenant_id: UUID,
        correlation_id: UUID,
        submitted_at: datetime,
        not_valid_after: datetime,
        authorization: AuthorizationBinding,
        minimized_context: Sequence[MinimizedUnit],
        parameters: Optional[Mapping[str, object]] = None,
    ) -> "EgressRequest":
        """Build a request, digesting its ordered context once at the boundary."""

        if authorization.tenant_id != tenant_id:
            raise ValueError(
                f"the authorization binds tenant {authorization.tenant_id} but the "
                f"request is for {tenant_id}; a request may not be attributed to a "
                f"tenant its clearance did not name")
        units = tuple(minimized_context)
        return cls(
            request_id=request_id,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            submitted_at=submitted_at,
            not_valid_after=not_valid_after,
            authorization=authorization,
            minimized_context=units,
            content_digest=minimized_context_digest(units),
            parameters=dict(parameters or {}),
        )

    def content_matches_digest(self) -> bool:
        """Whether the surviving content still hashes to its recorded digest.

        Answers ``True`` for a purged request: there is no content to disagree
        with the digest, and a tombstone is not a mismatch. Callers that need to
        distinguish the two ask ``minimized_context is None`` first.
        """

        if self.minimized_context is None:
            return True
        return minimized_context_digest(self.minimized_context) == self.content_digest

    def digest_body(self) -> dict:
        """Every immutable field that identifies this request.

        Content enters by digest, not inline — see :mod:`.canonical`. Mutable
        lease, claim, attempt and processing timestamps are excluded because they
        are not part of what was authorized; ``submitted_at`` is included because
        a creation instant never changes.
        """

        return {
            "exchange_schema_version": self.exchange_schema_version,
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "correlation_id": str(self.correlation_id),
            "submitted_at": self.submitted_at,
            "not_valid_after": self.not_valid_after,
            "authorization": self.authorization.digest_body(),
            "content_digest": self.content_digest,
            "parameters": dict(self.parameters),
        }

    def digest(self) -> str:
        """The request digest. Recomputable from a purged tombstone."""

        return canonical_digest(
            EGRESS_REQUEST_DIGEST_DOMAIN, "EgressRequest", self.digest_body())


#: Domain of the admission token below. An admission is a fingerprint of a durable
#: consumption, never an authorization by itself.
ADMISSION_DIGEST_DOMAIN = "ugence.model-egress-unit/genuine-call-admission/v1"


@dataclass(frozen=True)
class GenuineCallAdmission:
    """The receipt of one durable consumption of a live-validation authorization,
    issued by :func:`ugence_model_egress_unit.authorization.admit_genuine_call` after
    the six conditions of ADR §0.6 held and the ledger consumed the attempt.

    It names the authorization (by digest and nonce), the one request it admits (by
    id and digest), the consumption row and the call number. ``verify`` re-derives the
    digest; a token whose fields were edited fails it. It is what a genuine
    ``EgressResult`` must carry, and the database requires the same consumption row
    (migration 3) — a token is never enough on its own.
    """

    authorization_digest: str
    nonce: str
    request_id: UUID
    request_digest: str
    consumption_id: str
    consumed_at: datetime
    call_number: int
    admission_digest: str

    @staticmethod
    def _digest_of(body: dict) -> str:
        return canonical_digest(ADMISSION_DIGEST_DOMAIN, "GenuineCallAdmission", body)

    def _body(self) -> dict:
        return {"authorization_digest": self.authorization_digest, "nonce": self.nonce,
                "request_id": str(self.request_id), "request_digest": self.request_digest,
                "consumption_id": self.consumption_id, "consumed_at": self.consumed_at,
                "call_number": self.call_number}

    @classmethod
    def issue(cls, *, authorization_digest: str, nonce: str, request_id: UUID, request_digest: str,
              consumption_id: str, consumed_at: datetime, call_number: int) -> "GenuineCallAdmission":
        draft = cls(authorization_digest=authorization_digest, nonce=nonce, request_id=request_id,
                    request_digest=request_digest, consumption_id=consumption_id, consumed_at=consumed_at,
                    call_number=call_number, admission_digest="0" * 64)
        return dataclasses.replace(draft, admission_digest=cls._digest_of(draft._body()))

    def verify(self) -> bool:
        try:
            return (isinstance(self.consumption_id, str) and bool(self.consumption_id)
                    and 1 <= int(self.call_number) <= 10
                    and self.admission_digest == self._digest_of(self._body()))
        except Exception:  # noqa: BLE001 — a malformed token verifies false, never raises
            return False

    def as_record(self) -> dict:
        body = self._body()
        body["consumed_at"] = self.consumed_at.isoformat()
        body["admission_digest"] = self.admission_digest
        return body


@dataclass(frozen=True)
class EgressResult:
    """What came back, or what could not be determined.

    ``trust`` is a constant. ``provenance`` always says whether the call was
    genuine, and in this distribution it never was.
    """

    request_id: UUID
    tenant_id: UUID
    correlation_id: UUID
    recorded_at: datetime
    outcome: ResultOutcome
    adapter_id: str
    provenance: Mapping[str, object]
    payload: Optional[str]
    content_digest: Optional[str]
    refusal_reason: Optional[RefusalReason] = None
    trust: str = TRUST_LEVEL
    #: LP-2b (migration 2). Outside every digest body: which custody lease and
    #: authority a genuine result was produced under. ``None`` for every result in
    #: this distribution, which makes no genuine call.
    custody_lease_id: Optional[str] = None
    custody_authority_id: Optional[str] = None
    #: ADR §0.6 (migration 3). Outside every digest body: the durable consumption of the
    #: live-validation authorization this genuine result ran under. ``None`` for every
    #: result in this distribution, which makes no genuine call.
    admission: Optional[GenuineCallAdmission] = None

    def __post_init__(self) -> None:
        if self.trust != TRUST_LEVEL:
            raise ValueError(
                f"trust is a constant {TRUST_LEVEL!r}; a result that could claim a "
                f"stronger status would be believed because it arrived")
        if self.outcome is ResultOutcome.REFUSED and self.refusal_reason is None:
            raise ValueError(
                "a REFUSED result must name its reason: an unexplained terminal "
                "refusal cannot be acted on by the requester")
        if self.outcome is not ResultOutcome.REFUSED and self.refusal_reason is not None:
            raise ValueError(
                f"a {self.outcome.value} result must not carry a refusal reason")
        if self.outcome is not ResultOutcome.ANSWERED and self.payload is not None:
            raise ValueError(f"a {self.outcome.value} result has no payload to carry")
        genuine = self.provenance.get("genuine_call")
        if genuine is not False:
            # LP-2b and ADR §0.6: the application half of the gate. A genuine result
            # carries the custody lease and authority it ran under, a RESPONSE
            # provenance, and a verified GenuineCallAdmission for THIS request — the
            # receipt of a durable consumption of the owner's typed live-validation
            # authorization, issued by admit_genuine_call after its six conditions held.
            # The release constant is consulted only to fail closed on drift (G1
            # mirror); it is never authority. MET is never required: it is the
            # outcome the validation's evidence feeds, not its input.
            from . import version as _version  # local: version imports nothing

            if genuine is not True:
                raise ValueError("genuine_call is a boolean")
            if not _version.status_admits_genuine_call():
                raise ValueError(
                    f"no result may record a genuine call while commissioning is "
                    f"{_version.COMMISSIONING_STATUS}; a provenance record mistakable for "
                    f"provider evidence is the failure this check exists to prevent")
            if not isinstance(self.admission, GenuineCallAdmission) or not self.admission.verify():
                raise ValueError(
                    "a genuine result carries a verified GenuineCallAdmission: the durable "
                    "consumption of the owner's typed live-validation authorization (ADR §0.6); "
                    "no string, flag, owner name or release constant stands in for it")
            if self.admission.request_id != self.request_id:
                raise ValueError("the admission names a different request than this result")
            if not self.custody_lease_id or not self.custody_authority_id:
                raise ValueError("a genuine result names the custody lease and authority it ran under")
            if self.provenance.get("kind") != ProvenanceKind.RESPONSE.value:
                raise ValueError("only a RESPONSE provenance can record a genuine call")

    @property
    def provenance_kind(self) -> ProvenanceKind:
        return ProvenanceKind(self.provenance["kind"])

    @classmethod
    def answered(cls, *, request_id, tenant_id, correlation_id, recorded_at,
                 adapter_id, payload, model_ref, token_count=None) -> "EgressResult":
        return cls(
            request_id=request_id, tenant_id=tenant_id, correlation_id=correlation_id,
            recorded_at=recorded_at, outcome=ResultOutcome.ANSWERED,
            adapter_id=adapter_id,
            provenance={
                "kind": ProvenanceKind.RESPONSE.value,
                "adapter_id": adapter_id,
                "genuine_call": False,
                "model_ref": model_ref,
                "observed_at": recorded_at.isoformat(),
                "token_count": token_count,
            },
            payload=payload,
            content_digest=payload_digest(payload),
        )

    @classmethod
    def answered_genuine(cls, *, request_id, tenant_id, correlation_id, recorded_at,
                         adapter_id, payload, model_ref, custody_lease_id, custody_authority_id,
                         admission: GenuineCallAdmission, token_count=None) -> "EgressResult":
        """A genuine answer: only constructible with the custody identifiers and a
        verified admission, and refused by ``__post_init__`` unless every gate holds."""

        return cls(
            request_id=request_id, tenant_id=tenant_id, correlation_id=correlation_id,
            recorded_at=recorded_at, outcome=ResultOutcome.ANSWERED,
            adapter_id=adapter_id,
            provenance={
                "kind": ProvenanceKind.RESPONSE.value,
                "adapter_id": adapter_id,
                "genuine_call": True,
                "model_ref": model_ref,
                "observed_at": recorded_at.isoformat(),
                "token_count": token_count,
            },
            payload=payload,
            content_digest=payload_digest(payload),
            custody_lease_id=custody_lease_id, custody_authority_id=custody_authority_id,
            admission=admission,
        )

    @classmethod
    def refused(cls, *, request_id, tenant_id, correlation_id, recorded_at,
                adapter_id, reason, model_ref=None) -> "EgressResult":
        return cls(
            request_id=request_id, tenant_id=tenant_id, correlation_id=correlation_id,
            recorded_at=recorded_at, outcome=ResultOutcome.REFUSED,
            adapter_id=adapter_id,
            provenance={
                "kind": ProvenanceKind.RESPONSE.value,
                "adapter_id": adapter_id,
                "genuine_call": False,
                "model_ref": model_ref,
                "observed_at": recorded_at.isoformat(),
            },
            payload=None, content_digest=None, refusal_reason=reason,
        )

    @classmethod
    def failed(cls, *, request_id, tenant_id, correlation_id, recorded_at,
               adapter_id, model_ref=None) -> "EgressResult":
        """A call that demonstrably did not produce a result.

        Distinct from ``OUTCOME_UNKNOWN``: here the absence of a response is a
        known fact, not an open question.
        """

        return cls(
            request_id=request_id, tenant_id=tenant_id, correlation_id=correlation_id,
            recorded_at=recorded_at, outcome=ResultOutcome.FAILED,
            adapter_id=adapter_id,
            provenance={
                "kind": ProvenanceKind.RESPONSE.value,
                "adapter_id": adapter_id,
                "genuine_call": False,
                "model_ref": model_ref,
                "observed_at": recorded_at.isoformat(),
            },
            payload=None, content_digest=None,
        )

    @classmethod
    def outcome_unknown(cls, *, request_id, tenant_id, correlation_id, recorded_at,
                        attempt: DispatchAttempt) -> "EgressResult":
        """Dispatch may have happened; nothing about the provider side is known.

        Carries a :class:`DispatchAttempt`, which is a different record type from
        a response — not a response with blanks.
        """

        return cls(
            request_id=request_id, tenant_id=tenant_id, correlation_id=correlation_id,
            recorded_at=recorded_at, outcome=ResultOutcome.OUTCOME_UNKNOWN,
            adapter_id=attempt.adapter_id,
            provenance=attempt.as_record(),
            payload=None, content_digest=None,
        )

    def digest_body(self) -> dict:
        return {
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "correlation_id": str(self.correlation_id),
            "recorded_at": self.recorded_at,
            "trust": self.trust,
            "outcome": self.outcome.value,
            "adapter_id": self.adapter_id,
            "provenance": dict(self.provenance),
            "content_digest": self.content_digest,
            "refusal_reason": (
                self.refusal_reason.value if self.refusal_reason is not None else None),
        }

    def digest(self) -> str:
        """The response digest. Binds the payload *and* its provenance.

        What distinguishes *the provider returned this* from *a row was edited
        afterwards*, and what the ledger retains in the payload's place.
        """

        return canonical_digest(
            EGRESS_RESULT_DIGEST_DOMAIN, "EgressResult", self.digest_body())
