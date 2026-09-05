"""The approver identity port and the proof shape (AI-A, rulings ID-2 to ID-5).

    THIS MODULE MINTS NO IDENTITY. It defines the seam through which a proof the
    service did not issue is presented, the verified-claims shape a real adapter
    returns, and the deterministic reference the service records instead of the
    proof itself.

Three concerns stay separate (``ADR_UGENCE_APPROVER_IDENTITY_SCOPING.md``):
authentication (who this is, answered by the identity provider behind the port and
carried as ``authentication_reference``), eligibility (what this principal may decide,
answered by the directory and carried as ``decided_authority_reference``), and decision
recording (what was decided, written by the ledger). Nothing here answers more than the
first, and the first is only *relayed*: the adapter behind the port proves, this module
shapes and references.

**ID-3.** ``ApproverIdentityPort`` is service-local. It is structurally compatible
with Decision Authority's identity seam, ``authenticate(...) -> (actor_id, actor_type,
authenticated)``, and adds the verified claims the ledger needs, so one real adapter
can serve both; it imports nothing from Decision Authority. Promotion to
governance-contracts waits on a second real consumer and a separate ruling.

**ID-2.** ``decided_by`` is the issuer-qualified subject, encoded unambiguously
(``subject_reference``). ``authentication_reference`` is a digest over the verified
claims and never over the proof: issuer, subject, audience, tenant claims,
authentication time, validity, ``acr``, ``amr`` and, when the issuer supplied one, a
digest of the proof id. Recomputing it from the same claims yields the same reference;
altering any claim changes it.

**ID-4.** Tenant claims are carried as presented: none, one, or several. The service
decides what each means under its explicit tenant mode.

**ID-5.** ``acr`` and ``amr`` are recorded as presented and empty when the issuer
asserted none; nothing here invents an assurance level or imposes a threshold.

The only implementation in this package is ``StaticApproverIdentityAdapter``, a
fixture map from opaque proof strings to claims. It proves nothing: every identity it
returns is labelled ``PRESENTED_UNPROVEN``, and a service constructed in production
mode refuses it. A real adapter is AI-C and lives in its own package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping, Optional, Protocol, runtime_checkable
from urllib.parse import quote

from .errors import ContractViolation, GovernedReviewServiceError

__all__ = [
    "IDENTITY_PROOF_LABELS",
    "IDP_AUTHENTICATED",
    "PRESENTED_UNPROVEN",
    "PROOF_HEADER",
    "ActorKind",
    "ApproverIdentity",
    "ApproverIdentityPort",
    "IdentityUnavailable",
    "RecordedAssurance",
    "StaticApproverIdentityAdapter",
    "TenantMode",
    "VerifiedClaims",
    "authentication_reference",
    "subject_reference",
]

#: The two labels a decision may carry for its approver (ADR §6). The package-level
#: ``IDENTITY_PROOF`` stays ``PRESENTED_UNPROVEN`` until AI-C exists.
PRESENTED_UNPROVEN = "PRESENTED_UNPROVEN"
IDP_AUTHENTICATED = "IDP_AUTHENTICATED"
IDENTITY_PROOF_LABELS = frozenset({PRESENTED_UNPROVEN, IDP_AUTHENTICATED})

#: The one header a relay may carry the opaque, audience-bound proof in (ID-1). The
#: service reads it, hands it to the port and never echoes, logs or stores it.
PROOF_HEADER = "X-Ugence-Approver-Proof"

_REFERENCE_PREFIX = "authn:sha256:"


class ActorKind(str, Enum):
    """Who the proof says is acting. The same three-way split as Decision Authority's
    ``ActorType``, redeclared here so the service imports nothing from it (ID-3)."""

    HUMAN = "HUMAN"
    AI = "AI"
    SYSTEM = "SYSTEM"


class TenantMode(str, Enum):
    """ID-4. ``SINGLE_TENANT``: a missing tenant claim falls back to the configured
    tenant and the outcome names the fallback. ``MULTI_TENANT``: the claim is the only
    source; missing, ambiguous or mismatched is refused."""

    SINGLE_TENANT = "SINGLE_TENANT"
    MULTI_TENANT = "MULTI_TENANT"


class IdentityUnavailable(GovernedReviewServiceError):
    """The adapter could not reach its issuer or could not verify the proof. The
    service fails closed on it (row 7)."""


@dataclass(frozen=True)
class VerifiedClaims:
    """What a real adapter verified about one proof. Never the proof itself.

    ``tenant_claims`` is every tenant the issuer asserted, in order: empty when none,
    one normally, several when the proof is ambiguous. ``acr`` is empty and ``amr`` is
    empty when the issuer asserted none; neither is ever filled in here.
    ``proof_id_digest`` is optional (an issuer may omit a proof id) and, when present,
    must already be a digest, never the id.
    """

    issuer: str
    subject: str
    audience: str
    authenticated_at: datetime
    expires_at: datetime
    tenant_claims: tuple[str, ...] = ()
    acr: str = ""
    amr: tuple[str, ...] = ()
    proof_id_digest: str = ""

    def __post_init__(self) -> None:
        for name in ("issuer", "subject", "audience"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"VerifiedClaims.{name} must be a non-empty string")
        for name in ("authenticated_at", "expires_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ContractViolation(f"VerifiedClaims.{name} must be a tz-aware datetime")
        object.__setattr__(self, "tenant_claims", tuple(str(t) for t in self.tenant_claims))
        object.__setattr__(self, "amr", tuple(str(m) for m in self.amr))
        if any(not t.strip() for t in self.tenant_claims):
            raise ContractViolation("VerifiedClaims.tenant_claims must not contain empty entries")
        if self.proof_id_digest and not self.proof_id_digest.startswith("sha256:"):
            raise ContractViolation("VerifiedClaims.proof_id_digest must be a sha256: digest, "
                                    "never the proof id itself")

    def canonical(self) -> dict:
        """The exact material ``authentication_reference`` digests, in a fixed shape."""

        return {
            "issuer": self.issuer,
            "subject": self.subject,
            "audience": self.audience,
            "tenant_claims": list(self.tenant_claims),
            "authenticated_at": self.authenticated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "acr": self.acr,
            "amr": list(self.amr),
            "proof_id_digest": self.proof_id_digest,
        }


@dataclass(frozen=True)
class ApproverIdentity:
    """What the port answers. The first three fields are the shape Decision Authority's
    seam returns; ``claims`` and ``proof`` are what this path adds.

    ``proof`` is the label the adapter is entitled to put on the answer: a real
    adapter says ``IDP_AUTHENTICATED``; the static adapter says ``PRESENTED_UNPROVEN``
    because it verified nothing. An unauthenticated answer carries no claims.
    """

    actor_id: str
    actor_type: ActorKind
    authenticated: bool
    claims: Optional[VerifiedClaims] = None
    proof: str = PRESENTED_UNPROVEN

    def __post_init__(self) -> None:
        if not isinstance(self.actor_type, ActorKind):
            raise ContractViolation("ApproverIdentity.actor_type must be an ActorKind")
        if self.proof not in IDENTITY_PROOF_LABELS:
            raise ContractViolation(f"ApproverIdentity.proof must be one of "
                                    f"{sorted(IDENTITY_PROOF_LABELS)}, not {self.proof!r}")
        if self.authenticated and self.claims is None:
            raise ContractViolation("an authenticated ApproverIdentity must carry its claims")
        if self.authenticated and self.claims is not None \
                and self.actor_id != subject_reference(self.claims):
            raise ContractViolation("ApproverIdentity.actor_id must be the issuer-qualified "
                                    "subject of its claims (ID-2)")


@runtime_checkable
class ApproverIdentityPort(Protocol):
    """The seam a proof is presented through (ID-3).

    ``authenticate`` receives the opaque proof exactly as the relay forwarded it and
    answers with an ``ApproverIdentity``. It raises ``IdentityUnavailable`` when it
    cannot reach its issuer or verify the proof; the service fails closed on that. It
    never receives the presented approver, the approval or the decision: binding those
    to the proof is the service's rule, not the adapter's.
    """

    def authenticate(self, proof: str) -> ApproverIdentity: ...


def subject_reference(claims: VerifiedClaims) -> str:
    """ID-2: the issuer-qualified subject, encoded so no two (issuer, subject) pairs
    collide. Both halves are percent-encoded with no safe characters, so the separator
    cannot occur inside either."""

    return f"{quote(claims.issuer, safe='')}|{quote(claims.subject, safe='')}"


def authentication_reference(claims: VerifiedClaims) -> str:
    """ID-2: a deterministic, digest-bound reference to the verified claims.

    The digest is over the canonical JSON of ``VerifiedClaims.canonical()``: sorted
    keys, no whitespace, UTF-8. It binds issuer, subject, audience, tenant claims,
    authentication time, validity, ``acr``, ``amr`` and the optional proof-id digest.
    The proof itself is never an input.
    """

    material = json.dumps(claims.canonical(), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
    return _REFERENCE_PREFIX + hashlib.sha256(material).hexdigest()


class StaticApproverIdentityAdapter:
    """A fixture map from opaque proof strings to identities. NOT FOR PRODUCTION.

    It verifies nothing: it looks the proof up. Every identity it returns is labelled
    ``PRESENTED_UNPROVEN`` whatever the caller registered, and ``ReviewService``
    refuses it in production mode. It exists so the binding, tenant, expiry and
    fail-closed rules can be proven at unit level before a real adapter (AI-C) exists.

    ``unavailable`` names proofs the adapter answers with ``IdentityUnavailable``, to
    stand in for an unreachable issuer (row 7).
    """

    NON_PRODUCTION = True
    maturity = "FIXTURE_ONLY"

    def __init__(self, identities: Optional[Mapping[str, ApproverIdentity]] = None, *,
                 unavailable: tuple[str, ...] = ()) -> None:
        self._identities: dict[str, ApproverIdentity] = {}
        for proof, identity in (identities or {}).items():
            self.register(proof, identity)
        self._unavailable = frozenset(unavailable)

    def register(self, proof: str, identity: ApproverIdentity) -> ApproverIdentity:
        if not isinstance(proof, str) or not proof:
            raise ContractViolation("a proof must be a non-empty string")
        if not isinstance(identity, ApproverIdentity):
            raise ContractViolation("identity must be an ApproverIdentity")
        # Whatever was registered, this adapter has proven nothing.
        labelled = ApproverIdentity(identity.actor_id, identity.actor_type,
                                    identity.authenticated, identity.claims,
                                    proof=PRESENTED_UNPROVEN)
        self._identities[proof] = labelled
        return labelled

    def register_human(self, proof: str, claims: VerifiedClaims) -> ApproverIdentity:
        return self.register(proof, ApproverIdentity(subject_reference(claims),
                                                     ActorKind.HUMAN, True, claims))

    def register_actor(self, proof: str, claims: VerifiedClaims,
                       kind: ActorKind) -> ApproverIdentity:
        return self.register(proof, ApproverIdentity(subject_reference(claims), kind, True,
                                                     claims))

    def authenticate(self, proof: str) -> ApproverIdentity:
        if proof in self._unavailable:
            raise IdentityUnavailable("the fixture issuer is configured as unreachable")
        identity = self._identities.get(proof)
        if identity is None:
            # Unknown proofs are unauthenticated, never a human: the same rule as
            # Decision Authority's static provider.
            return ApproverIdentity(actor_id="", actor_type=ActorKind.SYSTEM,
                                    authenticated=False)
        return identity


@dataclass(frozen=True)
class RecordedAssurance:
    """ID-5: what the issuer asserted about how the subject authenticated, recorded as
    presented and enforced nowhere in this release."""

    acr: str = ""
    amr: tuple[str, ...] = ()
    threshold_enforced: bool = False
    policy_reference: str = ""

    def to_dict(self) -> dict:
        return {"acr": self.acr, "amr": list(self.amr),
                "threshold_enforced": self.threshold_enforced,
                "policy_reference": self.policy_reference}
