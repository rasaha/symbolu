"""ADR §0.6: the typed, immutable, consumable live-synthetic-validation authorization,
and the six-condition gate that admits one genuine call against it.

Authority never lives in a constant. It lives in the owner's typed
:class:`LiveSyntheticValidationAuthorization` record, whose digest the owner pins into
the canonical commissioning record (``MEU_LIVE_VALIDATION.json`` →
``live_synthetic_validation_authorization``; ``NOT_GIVEN`` until then), and in the
durable ledger that consumes each attempt before dispatch. :func:`admit_genuine_call`
is the only way to obtain a :class:`GenuineCallAdmission`, and it holds:

1. G1 from the canonical commissioning record: the status admits a genuine call;
2. the typed authorization is present, well-formed, and is the one the record pins;
3. every scope field matches the proposed request and the current step-8 designations;
4. the authorization is within its validity window and not revoked;
5. its nonce has not been replayed (ledger);
6. the durable ledger proves remaining call and budget capacity — and then consumes
   the attempt, before dispatch. An ambiguous dispatch keeps the consumption.

A non-empty string, a boolean, an owner's name or an altered release constant never
satisfies any of these. Nothing here opens a network connection or reads a clock.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Protocol, Tuple
from uuid import UUID

from .canonical import canonical_digest
from .egress_policy import OPENAI_RESPONSES
from .infrastructure import PLACEHOLDER_MARKERS, looks_like_a_credential
from .limits import COMMISSIONING_LIMITS, is_pinned_snapshot
from .records import EgressRequest, GenuineCallAdmission

__all__ = [
    "AUTHORIZATION_SCHEMA",
    "AUTHORIZATION_DIGEST_DOMAIN",
    "DESIGNATION_RECORD_DIGEST_DOMAIN",
    "NOT_GIVEN",
    "AuthorizationRefusal",
    "AuthorizationRefused",
    "LiveSyntheticValidationAuthorization",
    "ScopeExpectation",
    "CommissioningRecordView",
    "designation_record_digest",
    "AuthorizationLedger",
    "InMemoryAuthorizationLedger",
    "check_live_authorization",
    "admit_genuine_call",
]

AUTHORIZATION_SCHEMA = "model-egress-unit.live-synthetic-validation-authorization.v1"
AUTHORIZATION_DIGEST_DOMAIN = "ugence.model-egress-unit/live-synthetic-validation-authorization/v1"
DESIGNATION_RECORD_DIGEST_DOMAIN = "ugence.model-egress-unit/step8-designation-record/v1"
NOT_GIVEN = "NOT_GIVEN"
_ENVIRONMENT = "NON_PRODUCTION"
_HEX = set("0123456789abcdef")


class AuthorizationRefusal(str, Enum):
    NOT_GIVEN = "authorization_not_given"
    MALFORMED = "authorization_malformed"
    NOT_CANONICAL = "authorization_not_the_one_the_commissioning_record_pins"
    REVOKED = "authorization_revoked"
    NOT_YET_VALID = "authorization_not_yet_valid"
    EXPIRED = "authorization_expired"
    OWNER_MISMATCH = "authorizing_owner_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    DESIGNATION_DRIFT = "step8_designation_record_drift"
    PLAN_MISMATCH = "validation_plan_mismatch"
    REQUEST_NOT_AUTHORIZED = "request_digest_not_authorized"
    LIMITS_EXCEED_RULING = "authorization_limits_exceed_ruling"
    REQUEST_EXCEEDS_AUTHORIZATION = "request_exceeds_authorized_limits"
    STATUS_NOT_ADMITTING = "commissioning_status_does_not_admit_a_genuine_call"
    NONCE_REPLAYED = "authorization_nonce_replayed"
    CALLS_EXHAUSTED = "authorized_calls_exhausted"
    ALREADY_CONSUMED = "request_already_consumed"
    CAPACITY_EXHAUSTED = "durable_capacity_exhausted"


class AuthorizationRefused(RuntimeError):
    def __init__(self, reason: AuthorizationRefusal, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _clean(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, f"{name} is required")
    if looks_like_a_credential(value):
        raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, f"{name} carries a credential shape")
    lowered = value.lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in lowered and name != "endpoint":
            raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, f"{name} carries the placeholder token {marker!r}")
    return value


@dataclass(frozen=True)
class LiveSyntheticValidationAuthorization:
    """The owner's typed authorization of the first live synthetic validation sequence.

    Immutable (frozen; edits do not change the digest the record pins, so an edited
    copy is ``NOT_CANONICAL``) and consumable (each call is consumed durably by the
    ledger; ``max_calls`` bounds the sequence). Every field is bound into the digest.
    """

    authorization_id: str
    nonce: str
    authorizing_owner: str
    authority_reference: str
    issued_at: datetime
    expires_at: datetime
    environment: str
    openai_organization_id: str
    openai_project_id: str
    openai_service_account_id: str
    provider: str
    model: str
    endpoint: str
    designation_record_digest: str
    validation_plan_digest: str
    authorized_request_digests: Tuple[str, ...]
    synthetic_non_sensitive_only: bool
    max_calls: int
    max_input_tokens: int
    max_output_tokens: int
    budget_usd_cents: int
    concurrency: int
    max_retries: int
    schema: str = AUTHORIZATION_SCHEMA

    def __post_init__(self) -> None:
        R = AuthorizationRefusal
        if self.schema != AUTHORIZATION_SCHEMA:
            raise AuthorizationRefused(R.MALFORMED, "schema")
        for name in ("authorization_id", "nonce", "authorizing_owner", "authority_reference", "environment",
                     "openai_organization_id", "openai_project_id", "openai_service_account_id",
                     "provider", "model", "endpoint"):
            _clean(name, getattr(self, name))
        if len(self.nonce) < 16:
            raise AuthorizationRefused(R.MALFORMED, "nonce is at least 16 characters and never reused")
        for name in ("issued_at", "expires_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise AuthorizationRefused(R.MALFORMED, f"{name} must be a timezone-aware instant")
        if self.expires_at <= self.issued_at:
            raise AuthorizationRefused(R.MALFORMED, "expires_at must follow issued_at")
        if self.environment != _ENVIRONMENT:
            raise AuthorizationRefused(R.ENVIRONMENT_MISMATCH, f"environment must be {_ENVIRONMENT}")
        if self.provider != "openai":
            raise AuthorizationRefused(R.SCOPE_MISMATCH, "provider is openai")
        if not is_pinned_snapshot(self.model):
            raise AuthorizationRefused(R.SCOPE_MISMATCH, "model must be a pinned snapshot")
        if OPENAI_RESPONSES.check(self.endpoint) is not None:
            raise AuthorizationRefused(R.SCOPE_MISMATCH, "endpoint is exactly the designated destination")
        for name in ("designation_record_digest", "validation_plan_digest"):
            if not _is_digest(getattr(self, name)):
                raise AuthorizationRefused(R.MALFORMED, f"{name} must be a 64-hex digest")
        digests = tuple(self.authorized_request_digests) if isinstance(self.authorized_request_digests, (list, tuple)) else None
        if not digests or not all(_is_digest(d) for d in digests) or len(set(digests)) != len(digests):
            raise AuthorizationRefused(R.MALFORMED, "authorized_request_digests is a non-empty set of distinct 64-hex digests")
        object.__setattr__(self, "authorized_request_digests", digests)
        if self.synthetic_non_sensitive_only is not True:
            raise AuthorizationRefused(R.MALFORMED, "synthetic_non_sensitive_only must be exactly true")
        for name in ("max_calls", "max_input_tokens", "max_output_tokens", "budget_usd_cents", "concurrency", "max_retries"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise AuthorizationRefused(R.MALFORMED, f"{name} must be a non-negative integer")
        L = COMMISSIONING_LIMITS
        if not (1 <= self.max_calls <= L.max_genuine_calls):
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"max_calls must be 1..{L.max_genuine_calls}")
        if len(digests) > self.max_calls:
            raise AuthorizationRefused(R.MALFORMED, "more request digests than max_calls")
        if self.max_input_tokens < 1 or self.max_input_tokens > L.max_input_tokens:
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"max_input_tokens must be 1..{L.max_input_tokens}")
        if self.max_output_tokens < 1 or self.max_output_tokens > L.max_output_tokens:
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"max_output_tokens must be 1..{L.max_output_tokens}")
        if self.budget_usd_cents < 1 or self.budget_usd_cents > L.budget_usd_cents:
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"budget_usd_cents must be 1..{L.budget_usd_cents}")
        if self.concurrency != L.concurrency:
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"concurrency is {L.concurrency}")
        if self.max_retries > L.max_retries:
            raise AuthorizationRefused(R.LIMITS_EXCEED_RULING, f"max_retries is at most {L.max_retries}")

    def digest_body(self) -> Dict[str, Any]:
        body = {}
        for f in fields(self):
            value = getattr(self, f.name)
            body[f.name] = list(value) if isinstance(value, tuple) else value
        return body

    def digest(self) -> str:
        return canonical_digest(AUTHORIZATION_DIGEST_DOMAIN, "LiveSyntheticValidationAuthorization", self.digest_body())

    def as_record(self) -> Dict[str, Any]:
        out = self.digest_body()
        out["issued_at"] = self.issued_at.isoformat()
        out["expires_at"] = self.expires_at.isoformat()
        out["digest"] = self.digest()
        return out

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "LiveSyntheticValidationAuthorization":
        """Strict: every field required, no unknown key, instants ISO-8601 with offset."""

        if not isinstance(record, Mapping):
            raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, "a record is a mapping")
        names = {f.name for f in fields(cls)}
        given = set(record) - {"digest"}
        if given != names:
            missing, extra = sorted(names - given), sorted(given - names)
            raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, f"missing {missing}, unknown {extra}")
        kwargs = dict(record)
        kwargs.pop("digest", None)
        for name in ("issued_at", "expires_at"):
            value = kwargs[name]
            if isinstance(value, str):
                try:
                    kwargs[name] = datetime.fromisoformat(value)
                except ValueError:
                    raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, f"{name} is not ISO-8601")
        kwargs["authorized_request_digests"] = tuple(kwargs["authorized_request_digests"]) if isinstance(
            kwargs["authorized_request_digests"], (list, tuple)) else kwargs["authorized_request_digests"]
        auth = cls(**kwargs)
        if "digest" in record and record["digest"] != auth.digest():
            raise AuthorizationRefused(AuthorizationRefusal.MALFORMED, "the record's digest does not match its content")
        return auth


@dataclass(frozen=True)
class ScopeExpectation:
    """What the current step-8 designations and the ruling say the scope must be.
    Every value comes from the designation record; an ``UNDESIGNATED`` value can match
    nothing, which is the intended failure while step 8 is open."""

    openai_organization_id: str
    openai_project_id: str
    openai_service_account_id: str
    provider: str = "openai"
    model: str = ""
    endpoint: str = OPENAI_RESPONSES.url
    environment: str = _ENVIRONMENT


def designation_record_digest(designation: Mapping[str, Any]) -> str:
    """The exact digest of the step-8 designation record (the whole
    ``MEU_LIVE_PROVIDER_DESIGNATION.json`` content, canonically serialized)."""

    return canonical_digest(DESIGNATION_RECORD_DIGEST_DOMAIN, "MEU_LIVE_PROVIDER_DESIGNATION", dict(designation))


@dataclass(frozen=True)
class CommissioningRecordView:
    """G1's source and the authorization's canonical binding, read from the two records
    beside the unit — never from a constant."""

    status: str
    authorization_digest: str            # NOT_GIVEN or the pinned digest
    revoked_digests: Tuple[str, ...]
    authorizing_owner: str
    designation_digest: str

    @classmethod
    def from_records(cls, validation: Mapping[str, Any], designation: Mapping[str, Any]) -> "CommissioningRecordView":
        pinned = validation.get("live_synthetic_validation_authorization", NOT_GIVEN)
        if pinned != NOT_GIVEN and not _is_digest(pinned):
            raise AuthorizationRefused(AuthorizationRefusal.MALFORMED,
                                       "live_synthetic_validation_authorization is NOT_GIVEN or a 64-hex digest")
        return cls(
            status=str(validation.get("meu_live_status", "")),
            authorization_digest=pinned,
            revoked_digests=tuple(validation.get("revoked_authorization_digests", ()) or ()),
            authorizing_owner=str(validation.get("authorizing_owner", "")),
            designation_digest=designation_record_digest(designation),
        )


class AuthorizationLedger(Protocol):
    """The durable side: nonce replay, per-authorization consumption, and the budget
    capacity of LP-5's reservation ledger. The PostgreSQL implementation is
    ``postgres.ExchangeAuthorizationLedger``; the in-memory one below is a fixture."""

    NON_PRODUCTION: bool

    def capacity(self, *, tenant_id: UUID) -> Tuple[int, int]:
        """(calls remaining, cents remaining) under LP-5 for this tenant."""

    def consume(self, authorization: LiveSyntheticValidationAuthorization, *, tenant_id: UUID,
                request_id: UUID, request_digest: str, estimated_cents: int, now: datetime) -> Tuple[str, int]:
        """Consume one attempt durably, before dispatch: (consumption id, call number), or
        :class:`AuthorizationRefused` with NONCE_REPLAYED, CALLS_EXHAUSTED, ALREADY_CONSUMED,
        EXPIRED or CAPACITY_EXHAUSTED. Nothing is ever given back."""


class InMemoryAuthorizationLedger:
    """FIXTURE ONLY. The same rules as the durable ledger, in a dict; a restart forgets
    it, which is exactly why it never backs a genuine validation call."""

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self) -> None:
        self._nonces: Dict[str, str] = {}                 # nonce -> authorization digest
        self._calls: Dict[str, int] = {}                  # authorization digest -> consumed
        self._consumed: Dict[Tuple[str, str], str] = {}   # (digest, request digest) -> consumption id
        self._budget: Dict[str, Tuple[int, int]] = {}     # tenant -> (calls, cents) reserved
        self.consumptions: list = []

    def capacity(self, *, tenant_id: UUID) -> Tuple[int, int]:
        calls, cents = self._budget.get(str(tenant_id), (0, 0))
        return COMMISSIONING_LIMITS.max_genuine_calls - calls, COMMISSIONING_LIMITS.budget_usd_cents - cents

    def consume(self, authorization, *, tenant_id, request_id, request_digest, estimated_cents, now):
        R = AuthorizationRefusal
        digest = authorization.digest()
        held = self._nonces.get(authorization.nonce)
        if held is not None and held != digest:
            raise AuthorizationRefused(R.NONCE_REPLAYED, "this nonce already backs a different authorization")
        if now >= authorization.expires_at:
            raise AuthorizationRefused(R.EXPIRED)
        if (digest, request_digest) in self._consumed:
            raise AuthorizationRefused(R.ALREADY_CONSUMED, "this request was already consumed under this authorization")
        if self._calls.get(digest, 0) >= authorization.max_calls:
            raise AuthorizationRefused(R.CALLS_EXHAUSTED, f"{authorization.max_calls} authorized calls consumed")
        calls_left, cents_left = self.capacity(tenant_id=tenant_id)
        if calls_left < 1 or cents_left < estimated_cents:
            raise AuthorizationRefused(R.CAPACITY_EXHAUSTED, "the durable reservation ledger has no remaining capacity")
        self._nonces[authorization.nonce] = digest
        self._calls[digest] = self._calls.get(digest, 0) + 1
        consumption_id = f"mem-{len(self.consumptions) + 1:04d}"
        self._consumed[(digest, request_digest)] = consumption_id
        calls, cents = self._budget.get(str(tenant_id), (0, 0))
        self._budget[str(tenant_id)] = (calls + 1, cents + estimated_cents)
        self.consumptions.append({"consumption_id": consumption_id, "authorization_digest": digest,
                                  "request_id": str(request_id), "request_digest": request_digest,
                                  "consumed_at": now.isoformat(), "call_number": self._calls[digest]})
        return consumption_id, self._calls[digest]


def check_live_authorization(authorization: Any, *, record: CommissioningRecordView, request: EgressRequest,
                             expected: ScopeExpectation, plan_digest: str, now: datetime) -> None:
    """Conditions 1 to 4 of ADR §0.6, in order, or :class:`AuthorizationRefused`. Pure."""

    R = AuthorizationRefusal
    from .version import GENUINE_CALL_ADMITTING_STATUSES
    if record.status not in GENUINE_CALL_ADMITTING_STATUSES:
        raise AuthorizationRefused(R.STATUS_NOT_ADMITTING, f"meu_live_status is {record.status!r}")
    if record.authorization_digest == NOT_GIVEN or authorization is None:
        raise AuthorizationRefused(R.NOT_GIVEN, "the commissioning record pins no authorization")
    if not isinstance(authorization, LiveSyntheticValidationAuthorization):
        raise AuthorizationRefused(R.MALFORMED, f"a {type(authorization).__name__} is not a typed authorization")
    digest = authorization.digest()
    if digest != record.authorization_digest:
        raise AuthorizationRefused(R.NOT_CANONICAL, "the authorization is not the one the commissioning record pins")
    if digest in record.revoked_digests:
        raise AuthorizationRefused(R.REVOKED)
    if authorization.authorizing_owner != record.authorizing_owner or not record.authorizing_owner:
        raise AuthorizationRefused(R.OWNER_MISMATCH)
    if authorization.environment != expected.environment or expected.environment != _ENVIRONMENT:
        raise AuthorizationRefused(R.ENVIRONMENT_MISMATCH)
    for name in ("openai_organization_id", "openai_project_id", "openai_service_account_id", "provider", "endpoint"):
        if getattr(authorization, name) != getattr(expected, name):
            raise AuthorizationRefused(R.SCOPE_MISMATCH, name)
    if authorization.model != expected.model:
        raise AuthorizationRefused(R.SCOPE_MISMATCH, "model")
    auth_binding = request.authorization
    if auth_binding.authorized_vendor != authorization.provider or auth_binding.authorized_model != authorization.model:
        raise AuthorizationRefused(R.SCOPE_MISMATCH, "the request's binding names another vendor or model")
    if authorization.designation_record_digest != record.designation_digest:
        raise AuthorizationRefused(R.DESIGNATION_DRIFT, "the step-8 designation record changed since the authorization was issued")
    if authorization.validation_plan_digest != plan_digest:
        raise AuthorizationRefused(R.PLAN_MISMATCH)
    if request.minimized_context is None or not request.content_matches_digest():
        raise AuthorizationRefused(R.REQUEST_NOT_AUTHORIZED, "the request's content no longer hashes to its digest")
    request_digest = request.digest()
    if request_digest not in authorization.authorized_request_digests:
        raise AuthorizationRefused(R.REQUEST_NOT_AUTHORIZED)
    tokens = sum(u.token_count for u in (request.minimized_context or ()))
    out = request.parameters.get("max_output_tokens")
    if tokens > authorization.max_input_tokens or not isinstance(out, int) or out > authorization.max_output_tokens:
        raise AuthorizationRefused(R.REQUEST_EXCEEDS_AUTHORIZATION)
    if now < authorization.issued_at:
        raise AuthorizationRefused(R.NOT_YET_VALID)
    if now >= authorization.expires_at:
        raise AuthorizationRefused(R.EXPIRED)


def admit_genuine_call(authorization: Any, *, record: CommissioningRecordView, request: EgressRequest,
                       expected: ScopeExpectation, plan_digest: str, now: datetime,
                       ledger: AuthorizationLedger, estimated_cents: int) -> GenuineCallAdmission:
    """All six conditions, then the durable consumption, then the admission receipt."""

    check_live_authorization(authorization, record=record, request=request, expected=expected,
                             plan_digest=plan_digest, now=now)
    calls_left, cents_left = ledger.capacity(tenant_id=request.tenant_id)
    if calls_left < 1 or cents_left < estimated_cents:
        raise AuthorizationRefused(AuthorizationRefusal.CAPACITY_EXHAUSTED,
                                   f"{calls_left} calls and {cents_left} cents remain in the durable ledger")
    request_digest = request.digest()
    consumption_id, call_number = ledger.consume(
        authorization, tenant_id=request.tenant_id, request_id=request.request_id,
        request_digest=request_digest, estimated_cents=estimated_cents, now=now)
    return GenuineCallAdmission.issue(
        authorization_digest=authorization.digest(), nonce=authorization.nonce, request_id=request.request_id,
        request_digest=request_digest, consumption_id=str(consumption_id), consumed_at=now, call_number=call_number)
