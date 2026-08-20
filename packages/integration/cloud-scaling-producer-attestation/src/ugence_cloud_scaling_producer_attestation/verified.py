"""``VerifiedProducerAttestation`` — a verification artifact, and not an authorization.

What it establishes
-------------------
Exactly one thing: that at the injected instant ``verified_as_of_fact``, a configured trust
anchor at the exact coordinate ``(issuer, key_id, Cloud Scaling recommendation-attestation
capability)`` was usable, and its public key verified a signature over a canonical payload
this package **recomputed** from the Phase 5A candidate's own reconciled facts.

Issuer versus producer, stated precisely
----------------------------------------
The anchor is resolved by **issuer**. What the signature establishes is therefore:

    a trusted issuer/key signed an assertion naming this producer.

It does **not** establish that the producer controls the key, and it does not resolve the
producer against a trust anchor of its own — ``producer_id`` is a signed *claim by the
issuer*, not an independently verified identity. The field is named
:attr:`attested_producer_id` so the name says exactly that much and no more. It was
called ``verified_producer_id`` in an earlier revision of this unmerged package; an
independent closure audit found the name asserted more than the check performs, and the
name was corrected rather than kept as an alias.

A trusted issuer may legitimately attest a producer other than itself — Phase 5 ADR §3
ratifies the controller signing its own output, and does not require the two identifiers
to differ. The trust question that answers is "which issuer vouched", not "which producer
proved possession of a key".

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

What the signature covers, and what records the determination's scope
--------------------------------------------------------------------
Two different statements, and reading the first for the second over-claims the guarantee.
:attr:`artifact_digest` covers every field on this class — but that is an *integrity*
digest this package computes, and its job is to stop a field being rewritten after
construction. It is not the producer's signature.

The producer's signature covers exactly the fourteen keys
:func:`~ugence_cloud_scaling_producer_attestation.attestation.
producer_attestation_signing_payload` emits: the schema version and signing purpose, the
producer, issuer and key id, the algorithm, profile and encoding, the issuance instant, and
the five facts the determination is *about* — ``tenant_id``, ``subject_id``,
``subject_type``, ``recommendation_id`` and ``recommendation_digest``.

Every remaining field on this artifact records **the scope of this determination**, not
something the producer asserted: :attr:`candidate_digest` (which candidate it was reached
against), the trust-anchor coordinate, record and capability (which anchor answered),
:attr:`verified_as_of_fact` and the anchor window bounds (when), and the verification
profile and version (under which routine).

:attr:`candidate_digest` is therefore **not signature-covered**, and the consequence is
stated here rather than left to be found: *one genuine attestation verifies against any
candidate that agrees on those five reconciled facts*. Verified against two such candidates
the same attestation yields two artifacts with the same :attr:`attestation_digest`,
different :attr:`candidate_digest` values and different :attr:`artifact_digest` values, and
both read ``VERIFIED``.

What that admits, stated as a rule rather than as a list — an enumeration of dimensions is
what two revisions of this docstring got wrong. The verifier reconciles **exactly those five
facts and directly reconciles no other candidate facts**. Stated as the claim it supports: for
two independently valid objects of exact type ``CapacityAuthorizationCandidate``, the
producer-attestation layer does not independently compare facts outside those five when the
five reconciled values remain equal.

:attr:`candidate_digest` is read **after** verification succeeds, to bind the resulting
artifact to the candidate the determination was reached against. It is neither
producer-signature-covered nor independently reconciled — the verifier never compares it
against anything. ``tests/test_adversarial.py`` A-59 is the load-bearing evidence; A-60 is a
syntactic tripwire whose coverage limits are stated with it. Measured
instances: a different policy binding, a different execution target scope, different permitted
magnitude bounds, a different ``disposition``/``risk_outcome`` within the ALLOW family, and a
different risk decision — all still ``VERIFIED``.

The one thing it does **not** admit is a candidate whose own recommendation differs:
``magnitude_after`` and ``requested_delta`` are functionally determined by the recommendation,
so changing them moves ``recommendation_digest``, which *is* one of the five, and the
verification refuses with ``RECOMMENDATION_DIGEST_MISMATCH``.

That is the ratified scope, not an oversight. The recommendation itself *is* pinned, by id
and by content digest, which is what stops a forged recommendation laundering. What is not
pinned is the authorization envelope the recommendation was later placed into — binding
that would mean signing the Phase 5A candidate, which would mean minting the attestation
after the candidate rather than at the Controller's output boundary, and would make the v2
payload depend on Phase 5A. So a consumer must not read ``VERIFIED`` as saying anything
about the policy binding, the decision or the scope the recommendation was bound into.
ADR §12.1 records the ruling; ``tests/test_adversarial.py`` pins the behaviour.

Why a frozen dataclass is not the boundary
------------------------------------------
Following Phase 4C's ``AuthenticatedRecommendation``: a frozen dataclass stops *accidental*
mutation and stops nothing deliberate. ``object.__new__`` fabricates one with no
``__post_init__``, ``object.__setattr__`` rewrites a frozen field, a subclass diverts every
read through a property, and a duck-typed look-alike never touches this class at all.

So the boundary is made of four things instead:

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
its facts; an artifact carrying identical facts *is* the same determination. Keying on
identity would refuse a faithful in-process copy of a real determination while doing
nothing extra against a forger, and a ``WeakSet`` keyed on value is worse still — ``add``
is a no-op for an equal member, so the recorded reference can die while an equal, live
artifact goes unregistered.

What "a faithful copy still revalidates" does and does not mean
--------------------------------------------------------------
It means an **in-process** copy that preserves object state: ``copy.copy``,
``dataclasses.replace`` with no substitution, or any equal-but-identity-distinct instance
carrying the same fields. Those revalidate, because they carry the same digest *and* the
same construction token object.

It does **not** extend to ``copy.deepcopy`` or to ``pickle``. Both rebuild the token — a
bare ``object()`` sentinel whose whole meaning is its identity — so the copy carries a
*different* token and :func:`require_verified_producer_attestation` refuses it. That is
the correct direction to fail, and it is stated here rather than discovered: an artifact
that has crossed a process boundary is not a determination *this* process reached, and
there is deliberately no deserializer that would let it claim to be one. A consumer that
needs a determination in another process must re-verify there, not ship the artifact.

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
    attested_producer_id: str
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
            "attested_producer_id": self.attested_producer_id,
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
