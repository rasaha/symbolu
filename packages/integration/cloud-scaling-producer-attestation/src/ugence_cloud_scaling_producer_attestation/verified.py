"""``VerifiedProducerAttestation`` — a verification artifact, and not an authorization.

What it establishes
-------------------
Exactly one thing: that at the injected instant ``verified_as_of_fact``, a configured trust
anchor at the exact coordinate ``(issuer, key_id, producer-attestation capability)`` was
usable, and its public key verified a signature over a canonical payload this package
**recomputed** from the Phase 5A candidate's own reconciled facts. Producer authenticity.

What it does not establish
--------------------------
Everything else. It does not mean the action is *authorized*, *executable*, *admitted*,
*credential-eligible* or *permitted*. It carries no envelope, no envelope request, no
ActionGate result, no credential, no execution permission and no autonomy grant. Those
words do not appear as fields because the concepts do not exist in this package, so there
is nothing for a later commit to flip. :attr:`grants_authority` is a derived property that
hard-returns ``False``; it is not canonical, takes no part in the digest, and no branch can
return ``True``.

Policy authenticity in particular remains **unestablished**. A verified producer
attestation says who produced the recommendation. It says nothing about whether the policy
binding the candidate carries is genuine, in force, or issued by an authority anyone
trusts. That is Phase 5B-0B's, and it is not implemented here.

Why a frozen dataclass is not the boundary
------------------------------------------
Following Phase 4C's ``AuthenticatedRecommendation``: a frozen dataclass stops *accidental*
mutation and stops nothing deliberate. ``object.__new__`` fabricates one with no
``__post_init__``, ``object.__setattr__`` rewrites a frozen field, a subclass diverts every
read through a property, and a duck-typed look-alike never touches this class at all.

So the boundary is made of three things instead:

#. **A package-private construction token.** The only route to an instance is the
   authoritative verification routine, which holds it. Direct construction raises.
#. **A self-digest.** :attr:`artifact_digest` is recomputed at construction over every
   bound fact. A field rewritten afterwards no longer matches it.
#. **A provenance registry.** Every determination the verification routine reaches is
   recorded by its :attr:`artifact_digest` in a module-private set. Membership cannot be
   obtained by assembling an object, only by going through the routine.
#. **Revalidation at consumption.** :func:`require_verified_producer_attestation` re-checks
   the exact type, field presence, the token, registry membership and the digest at every
   boundary that consumes one. A consumer that skips it is trusting an object's shape,
   which is what this class exists to say is not enough.

Why the registry, given the token
---------------------------------
The token is the ratified construction guard, and it is kept. On its own, though, it makes
*possession of one genuine artifact* equivalent to the capability to mint arbitrary ones:
the token is a field, so ``getattr(genuine, "construction_token")`` hands it over, and a
forger who also recomputes :attr:`artifact_digest` produces something the token and digest
checks both accept. The registry closes that specific escalation: a determination this
process never reached has a digest this process never recorded.

It records **digests, not object identities**, and that is deliberate. A determination is
its facts; an artifact carrying identical facts *is* the same determination, whether it was
copied, passed through a queue or rebuilt. Keying on identity would refuse a faithful copy
of a real determination while doing nothing extra against a forger, and a ``WeakSet`` keyed
on value is worse still — ``add`` is a no-op for an equal member, so the recorded reference
can die while an equal, live artifact goes unregistered.

The set grows by one 71-byte digest per **distinct** determination reached, and never
otherwise; repeat verifications of the same candidate add nothing. A process that verifies
unboundedly many distinct recommendations should hold the boundary somewhere with its own
lifecycle rather than relying on a library-local set, and this is said here so that choice
is made deliberately.

What it does **not** close, stated plainly rather than over-claimed: in-process code that
reaches into a private module attribute can add to the registry, exactly as it can import
the token. No Python-level mechanism prevents that, and the Trusted Evidence Authority
documents the same residual for its own signing boundary. What is closed is every route
that does not require reaching into this module's privates.

There is deliberately **no** ``from_dict`` and no deserializer: a serialized verification
artifact would be a forgeable verification artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any

from .canonical import canonical_digest, require_canonical_digest
from .errors import VerifiedArtifactIntegrityError as _IntegrityError
from .identifiers import VERIFICATION_PROFILE, VERIFICATION_PROFILE_VERSION
from .outcomes import ProducerAuthenticityOutcome

__all__ = [
    "VerifiedProducerAttestation",
    "require_verified_producer_attestation",
]

#: The private construction token. Not exported, not in ``__all__``, not reachable from the
#: curated API. Holding it is what distinguishes an artifact the verifier minted from one a
#: caller assembled.
_VERIFICATION_TOKEN = object()

#: Provenance registry: the ``artifact_digest`` of every determination the authoritative
#: routine has reached in this process. Not exported and not reachable from the curated API.
#: See this module's docstring for why it holds digests rather than object identities, and
#: for its growth characteristic.
_MINTED_DIGESTS: set = set()


def _record_minted(artifact: "VerifiedProducerAttestation") -> "VerifiedProducerAttestation":
    """Record a determination as reached. Called only by the authoritative routine."""

    _MINTED_DIGESTS.add(artifact.artifact_digest)
    return artifact


@dataclass(frozen=True)
class VerifiedProducerAttestation:
    """The exact-typed, immutable, **non-authoritative** result of a successful verification."""

    # --- what was verified, bound to the candidate it was verified against -------------
    candidate_digest: str
    recommendation_id: str
    recommendation_digest: str
    tenant_id: str
    subject_id: str
    subject_type: str
    # --- what verified it ---------------------------------------------------------------
    attestation_digest: str
    verified_producer_id: str
    verified_issuer: str
    verified_key_id: str
    trust_anchor_coordinate_digest: str
    trust_anchor_record_digest: str
    trust_anchor_capability: str
    signature_profile: str
    signature_encoding: str
    # --- validity facts, carried from the inputs; no clock was read --------------------
    attestation_issued_at_fact: datetime
    verified_as_of_fact: datetime
    anchor_effective_from_fact: "datetime | None"
    anchor_effective_to_fact: "datetime | None"
    # --- how it was verified ------------------------------------------------------------
    verification_profile: str
    verification_profile_version: str
    # --- self ----------------------------------------------------------------------------
    artifact_digest: str
    construction_token: object = None

    def __post_init__(self) -> None:
        if self.construction_token is not _VERIFICATION_TOKEN:
            raise _IntegrityError(
                "VerifiedProducerAttestation cannot be constructed directly. It is minted "
                "only by the authoritative verification routine, and only after every gate "
                "has succeeded — there is no supported route from caller-chosen facts to a "
                "verification artifact."
            )
        if self.verification_profile != VERIFICATION_PROFILE:
            raise _IntegrityError(
                f"verification_profile must be exactly {VERIFICATION_PROFILE!r}"
            )
        if self.verification_profile_version != VERIFICATION_PROFILE_VERSION:
            raise _IntegrityError(
                "verification_profile_version must be exactly "
                f"{VERIFICATION_PROFILE_VERSION!r}"
            )
        for name in (
            "candidate_digest",
            "recommendation_digest",
            "attestation_digest",
            "trust_anchor_coordinate_digest",
            "trust_anchor_record_digest",
            "artifact_digest",
        ):
            require_canonical_digest(name, getattr(self, name))
        expected = canonical_digest(self.digest_payload())
        if self.artifact_digest != expected:
            raise _IntegrityError(
                "artifact_digest does not equal the digest of the bound facts"
            )

    # -- derived, never stored ----------------------------------------------------------- #

    @property
    def outcome(self) -> ProducerAuthenticityOutcome:
        """Always ``VERIFIED``. A read-only property, so it cannot be set.

        ``object.__setattr__(artifact, "outcome", ...)`` — the usual frozen-dataclass
        bypass — raises against this data descriptor, and a doctored instance dictionary
        never shadows it. There is no field here for a caller to supply.
        """

        return ProducerAuthenticityOutcome.VERIFIED

    @property
    def grants_authority(self) -> bool:
        """Always ``False``. Derived, non-canonical, and with no branch that returns ``True``.

        Producer authenticity is not authorization. This property exists so the statement
        is executable rather than merely written down.
        """

        return False

    # -- canonical form ------------------------------------------------------------------- #

    def digest_payload(self) -> dict[str, Any]:
        """Every bound fact, and nothing derived. The bytes :attr:`artifact_digest` covers.

        ``artifact_digest`` and ``construction_token`` are excluded — a digest cannot cover
        itself, and a process-local sentinel is not canonicalizable. Every other field is
        present, so a field rewritten after construction moves the digest.
        """

        return {
            "candidate_digest": self.candidate_digest,
            "recommendation_id": self.recommendation_id,
            "recommendation_digest": self.recommendation_digest,
            "tenant_id": self.tenant_id,
            "subject_id": self.subject_id,
            "subject_type": self.subject_type,
            "attestation_digest": self.attestation_digest,
            "verified_producer_id": self.verified_producer_id,
            "verified_issuer": self.verified_issuer,
            "verified_key_id": self.verified_key_id,
            "trust_anchor_coordinate_digest": self.trust_anchor_coordinate_digest,
            "trust_anchor_record_digest": self.trust_anchor_record_digest,
            "trust_anchor_capability": self.trust_anchor_capability,
            "signature_profile": self.signature_profile,
            "signature_encoding": self.signature_encoding,
            "attestation_issued_at_fact": self.attestation_issued_at_fact,
            "verified_as_of_fact": self.verified_as_of_fact,
            "anchor_effective_from_fact": self.anchor_effective_from_fact,
            "anchor_effective_to_fact": self.anchor_effective_to_fact,
            "verification_profile": self.verification_profile,
            "verification_profile_version": self.verification_profile_version,
            # Framed in deliberately: the digest commits to the fact that this artifact
            # establishes producer authenticity and grants nothing.
            "outcome": self.outcome.value,
            "grants_authority": self.grants_authority,
        }

    def digest(self) -> str:
        """Recompute this artifact's canonical digest from its current field values."""

        return canonical_digest(self.digest_payload())

    def __repr__(self) -> str:
        return (
            "VerifiedProducerAttestation(issuer="
            f"{self.verified_issuer!r}, key={self.verified_key_id!r}, "
            f"recommendation={self.recommendation_id!r}, grants_authority=False)"
        )


def require_verified_producer_attestation(
    value: object, name: str = "verified_producer_attestation"
) -> VerifiedProducerAttestation:
    """Revalidate a verification artifact at a consumption boundary. Refuse anything else.

    Call this **every** time one of these crosses a boundary, not once at the point of
    minting. Five independent checks, each closing a different fabrication route:

    #. exact type — a subclass with a diverting property, and a duck-typed look-alike,
       both fail here;
    #. every declared field is actually present — an ``object.__new__`` fabrication has no
       instance state at all and fails here;
    #. the construction token — an artifact assembled without the verifier fails here;
    #. registry membership — an artifact assembled *with* a borrowed token, read off a
       genuine one, names a determination this process never reached and fails here;
    #. the self-digest, recomputed — a field rewritten with ``object.__setattr__`` after
       construction fails here.
    """

    if type(value) is not VerifiedProducerAttestation:
        raise _IntegrityError(
            f"{name} must be exactly VerifiedProducerAttestation (got "
            f"{type(value).__name__}); a subclass, a duck-typed look-alike and a "
            "fabricated instance are refused, not adapted"
        )
    for field in fields(VerifiedProducerAttestation):
        try:
            getattr(value, field.name)
        except AttributeError:
            raise _IntegrityError(
                f"{name} is missing the field {field.name!r}; it was fabricated without "
                "running the verification routine"
            ) from None
    if value.construction_token is not _VERIFICATION_TOKEN:
        raise _IntegrityError(
            f"{name} does not carry the package construction token; it was assembled "
            "outside the authoritative verification routine"
        )
    if value.artifact_digest not in _MINTED_DIGESTS:
        raise _IntegrityError(
            f"{name} names a determination this process never reached. It carries the "
            "construction token, so it was assembled by something holding it — but the "
            "authoritative verification routine never produced this determination. "
            "Possession of a genuine artifact is not authority to mint another one."
        )
    if value.artifact_digest != value.digest():
        raise _IntegrityError(
            f"{name} was mutated after construction: its recomputed digest does not equal "
            "the digest bound at verification time"
        )
    return value
