"""The adapter: a locally validated RFC 9068 access token as proof of who decided.

    THIS ADAPTER VALIDATES A PROOF IT DID NOT ISSUE. IT MINTS NO IDENTITY, ANSWERS
    NO ELIGIBILITY, READS NO CLOCK OF ITS OWN, AND NEVER LOGS, STORES OR RETURNS
    THE TOKEN.

What it decides (IA-1, IA-2, IA-3): the proof is one JWT whose header names a
permitted asymmetric algorithm, an access-token type and a key id; the key is the
issuer's, from the configured JWKS; the signature verifies; ``iss`` and ``aud`` are
the configured ones; the required claims are present and well-typed; and, against
the injected clock, the token has been issued, is not yet expired and, if it says
so, is already valid. Every refusal is an unauthenticated answer carrying a reason
code from ``Refusal`` and nothing else. Only an inability to obtain keys is an
exception, the port's ``IdentityUnavailable``.

What it maps (IA-4): the table in ``ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md``
§3. The tenant and actor-type claim names are configuration with no default. HUMAN
is an exact match of the configured claim against the configured value and is never
inferred from ``sub``, ``client_id``, ``amr`` or ``auth_time``. ``acr`` and ``amr``
are recorded as asserted and nothing here enforces a level. ``authenticated_at`` is
``auth_time`` when present, otherwise the required ``iat``, and the answer records
which.

What it does not decide: subject binding, expiry at the write, tenant policy,
eligibility, replay. Those are the review service's (AI-A) and the directory's.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Optional

import jwt

from ugence_governed_review_service import (
    IDP_AUTHENTICATED,
    ActorKind,
    ApproverIdentity,
    ContractViolation,
    VerifiedClaims,
    subject_reference,
)

from .config import AdapterConfig
from .keys import JwksKeyCache
from .version import MATURITY

__all__ = [
    "ALGORITHMS",
    "ACCESS_TOKEN_TYPES",
    "REQUIRED_CLAIMS",
    "JwtApproverIdentity",
    "JwtApproverIdentityAdapter",
    "Refusal",
]

#: IA-2: the only signature algorithms a proof may name. No HMAC, no ``none``.
ALGORITHMS = ("RS256", "ES256", "EdDSA")

#: IA-1: RFC 9068 §2.1 media types, compared case-insensitively per RFC 7515 §4.1.9.
ACCESS_TOKEN_TYPES = ("at+jwt", "application/at+jwt")

#: Claims a proof must carry to be considered at all.
REQUIRED_CLAIMS = ("iss", "sub", "aud", "exp", "iat")


class Refusal(str, Enum):
    """Why a proof was refused. The complete vocabulary of the unauthenticated answer;
    none of these values can carry any part of the token."""

    PROOF_TOO_LARGE = "PROOF_TOO_LARGE"
    MALFORMED = "MALFORMED"
    ALG_NOT_PERMITTED = "ALG_NOT_PERMITTED"
    TYP_NOT_ACCESS_TOKEN = "TYP_NOT_ACCESS_TOKEN"
    KID_MISSING = "KID_MISSING"
    KEY_UNKNOWN = "KEY_UNKNOWN"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    ISSUER_MISMATCH = "ISSUER_MISMATCH"
    AUDIENCE_MISMATCH = "AUDIENCE_MISMATCH"
    CLAIM_MISSING = "CLAIM_MISSING"
    CLAIM_MALFORMED = "CLAIM_MALFORMED"
    EXPIRED = "EXPIRED"
    ISSUED_IN_FUTURE = "ISSUED_IN_FUTURE"
    NOT_YET_VALID = "NOT_YET_VALID"


@dataclass(frozen=True)
class JwtApproverIdentity(ApproverIdentity):
    """The port's answer plus what this adapter is obliged to record: which claim
    supplied ``authenticated_at`` (IA-4) and, when unauthenticated, why."""

    authenticated_at_source: str = ""
    refusal: str = ""


class JwtApproverIdentityAdapter:
    """``ApproverIdentityPort`` over locally validated access tokens."""

    maturity = MATURITY

    def __init__(self, config: AdapterConfig, *, clock: Callable[[], datetime],
                 keys: Optional[JwksKeyCache] = None) -> None:
        if not isinstance(config, AdapterConfig):
            raise ContractViolation("config must be an AdapterConfig")
        if not callable(clock):
            raise ContractViolation("clock must be callable and return a tz-aware datetime")
        self._config = config
        self._clock = clock
        self._keys = keys if keys is not None else JwksKeyCache(config)

    @property
    def config(self) -> AdapterConfig:
        return self._config

    @property
    def keys(self) -> JwksKeyCache:
        return self._keys

    # -- the port ---------------------------------------------------------------
    def authenticate(self, proof: str) -> JwtApproverIdentity:
        cfg = self._config
        if not isinstance(proof, str) or not proof:
            return _refused(Refusal.MALFORMED)
        if len(proof.encode("utf-8", errors="replace")) > cfg.max_proof_bytes:
            return _refused(Refusal.PROOF_TOO_LARGE)  # before any parse

        try:
            header = jwt.get_unverified_header(proof)
        except jwt.exceptions.PyJWTError:
            return _refused(Refusal.MALFORMED)
        alg = header.get("alg")
        if alg not in ALGORITHMS:
            return _refused(Refusal.ALG_NOT_PERMITTED)
        typ = header.get("typ")
        if not isinstance(typ, str) or typ.lower() not in ACCESS_TOKEN_TYPES:
            return _refused(Refusal.TYP_NOT_ACCESS_TOKEN)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            return _refused(Refusal.KID_MISSING)

        key = self._keys.key_for(kid)  # KeyRetrievalFailed propagates: fail closed
        if key is None:
            return _refused(Refusal.KEY_UNKNOWN)
        if getattr(key, "algorithm_name", None) != alg:
            # The key the issuer published is not for the algorithm the header names.
            return _refused(Refusal.SIGNATURE_INVALID)

        try:
            payload = jwt.decode(
                proof, key.key, algorithms=[alg], audience=cfg.audience, issuer=cfg.issuer,
                options={
                    "verify_signature": True, "verify_iss": True, "verify_aud": True,
                    # Time is the injected clock's, below; never the wall clock's.
                    "verify_exp": False, "verify_nbf": False, "verify_iat": False,
                    "require": list(REQUIRED_CLAIMS),
                },
            )
        except jwt.exceptions.InvalidIssuerError:
            return _refused(Refusal.ISSUER_MISMATCH)
        except jwt.exceptions.InvalidAudienceError:
            return _refused(Refusal.AUDIENCE_MISMATCH)
        except jwt.exceptions.MissingRequiredClaimError:
            return _refused(Refusal.CLAIM_MISSING)
        except jwt.exceptions.InvalidSignatureError:
            return _refused(Refusal.SIGNATURE_INVALID)
        except jwt.exceptions.DecodeError:
            return _refused(Refusal.MALFORMED)
        except jwt.exceptions.InvalidKeyError:
            return _refused(Refusal.SIGNATURE_INVALID)
        except jwt.exceptions.PyJWTError:
            return _refused(Refusal.CLAIM_MALFORMED)
        except (TypeError, ValueError):
            # PyJWT raises these, not its own error, for a key the algorithm cannot use.
            return _refused(Refusal.SIGNATURE_INVALID)
        if not isinstance(payload, Mapping):
            return _refused(Refusal.MALFORMED)

        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ContractViolation("the injected clock must return a tz-aware datetime")
        exp = _instant(payload.get("exp"))
        iat = _instant(payload.get("iat"))
        if exp is None or iat is None:
            return _refused(Refusal.CLAIM_MALFORMED)
        if exp <= now:
            return _refused(Refusal.EXPIRED)
        if iat > now:
            return _refused(Refusal.ISSUED_IN_FUTURE)
        if "nbf" in payload:
            nbf = _instant(payload.get("nbf"))
            if nbf is None:
                return _refused(Refusal.CLAIM_MALFORMED)
            if nbf > now:
                return _refused(Refusal.NOT_YET_VALID)

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            return _refused(Refusal.CLAIM_MALFORMED)

        if "auth_time" in payload:
            authenticated_at, source = _instant(payload.get("auth_time")), "auth_time"
            if authenticated_at is None:
                return _refused(Refusal.CLAIM_MALFORMED)
        else:
            authenticated_at, source = iat, "iat"

        tenants = _tenants(payload, cfg.tenant_claim)
        if tenants is None:
            return _refused(Refusal.CLAIM_MALFORMED)
        acr = payload.get("acr", "")
        if not isinstance(acr, str):
            return _refused(Refusal.CLAIM_MALFORMED)
        amr = payload.get("amr", [])
        if not isinstance(amr, list) or not all(isinstance(m, str) for m in amr):
            return _refused(Refusal.CLAIM_MALFORMED)
        jti = payload.get("jti", "")
        if not isinstance(jti, str):
            return _refused(Refusal.CLAIM_MALFORMED)

        claims = VerifiedClaims(
            issuer=cfg.issuer, subject=subject, audience=cfg.audience,
            authenticated_at=authenticated_at, expires_at=exp,
            tenant_claims=tenants, acr=acr, amr=tuple(amr),
            proof_id_digest=("sha256:" + hashlib.sha256(jti.encode("utf-8")).hexdigest())
            if jti else "",
        )
        return JwtApproverIdentity(
            actor_id=subject_reference(claims), actor_type=_actor_kind(payload, cfg),
            authenticated=True, claims=claims, proof=IDP_AUTHENTICATED,
            authenticated_at_source=source,
        )


# -- helpers ----------------------------------------------------------------------
def _refused(reason: Refusal) -> JwtApproverIdentity:
    return JwtApproverIdentity(actor_id="", actor_type=ActorKind.SYSTEM, authenticated=False,
                               refusal=reason.value)


def _instant(value: Any) -> Optional[datetime]:
    """A NumericDate (RFC 7519 §2) as a tz-aware UTC datetime, or None if malformed."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _tenants(payload: Mapping[str, Any], claim: Optional[str]) -> Optional[tuple]:
    """IA-4: the configured tenant claim, as presented. None means malformed."""

    if claim is None or claim not in payload:
        return ()
    value = payload[claim]
    if isinstance(value, str):
        return (value,) if value.strip() else None
    if isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value):
        return tuple(value)
    return None


def _actor_kind(payload: Mapping[str, Any], cfg: AdapterConfig) -> ActorKind:
    """IA-4: HUMAN iff the configured claim equals the configured value exactly.
    Missing configuration, a missing claim, any other value or any other type is
    SYSTEM. Nothing about ``sub``, ``client_id``, ``amr`` or ``auth_time`` is read."""

    if cfg.actor_type_claim is None:
        return ActorKind.SYSTEM
    value = payload.get(cfg.actor_type_claim)
    if isinstance(value, str) and value == cfg.human_actor_type_value:
        return ActorKind.HUMAN
    return ActorKind.SYSTEM
