"""``VerifiedPolicyAuthenticity`` — a verification artifact, and not an authorization.

What it establishes
-------------------
Exactly one thing: that at the injected instant :attr:`resolved_as_of_fact`, under the
policy trust configuration identified by :attr:`trust_configuration_digest`, the complete
policy coordinate this artifact names resolved to a **non-historical** ``RESOLVED``
answer — meaning the Policy Authority found a record under that exact coordinate, the
stored artifact still re-derived it and still canonicalized, the declared and signed body
digests both equalled the recomputed one, the issuance signature verified under a key of the
named authority that was un-revoked, in-window, tenant-permitted and entitled to
``ISSUE_POLICY``, external approval evidence held, the lifecycle was active, the instant fell
inside the effective period, and no verified revocation applied.

"Is valid now", not "was validly issued"
-----------------------------------------
D-5B0B-5 rules that authenticity here means *is valid now*, judged at an injected ``as_of``.
The same record yields different answers at different instants with nothing else varying, so
an artifact that did not carry its instant would be meaningless. :attr:`resolved_as_of_fact`
is that instant, and it is named ``…_fact`` because this package read no clock to obtain it.

**Whose clock supplied it is not settled** — ADR residual R-2, left open and explicitly
authorized to remain open for this implementation. The consequence, stated rather than
buried: an authenticity determination reached at an attacker-chosen ``as_of`` can resolve a
policy that is revoked, expired or not yet effective *now*. Binding ``as_of`` to a trusted
time source is 5B-2's envelope-issuance work. Until then, a consumer must treat
:attr:`resolved_as_of_fact` as an **unvalidated input**, not as a verified fact about time.

A historical answer can never appear here
------------------------------------------
:attr:`historical` is a derived property that hard-returns ``False``, and the verifier
refuses a historical resolution at admission rather than carrying it forward labelled. The
Policy Authority's own type already draws the distinction —
``PolicyResolution.implies_current_validity`` is ``False`` for every historical answer — and
an authorization asserts that limits apply to an action about to be taken, which a statement
about the past cannot support.

What it does not establish
--------------------------
Everything else.

* **Not authorization.** :attr:`grants_authority` is a derived property that hard-returns
  ``False``. There is no envelope, no ActionGate result, no credential and no execution
  permission here, and no field for a later commit to flip. The Policy Authority performs no
  caller authorization at all: :attr:`expected_reference_tenant_id` records the tenant the
  *reference* declared, never the caller's right to it.
* **Not bound to a recommendation, a scope or a candidate.** This is the direct successor to
  5B-0A's A-59 residual, and ADR residual R-4. :attr:`candidate_digest_fact` records *which
  candidate the determination accompanied*, if the caller supplied one. It is **never
  reconciled against anything** — the verifier does not compare it, and cannot: D-5B0B-3
  measured that Phase 5A's ``PolicyTargetBindingReference`` carries three of the coordinate's
  six components and that its fourth, ``policy_artifact_digest``, is format-incompatible with
  every Policy Authority digest, so a Phase 5A binding **cannot name a coordinate**. The
  consequence, stated as a rule: *one genuine policy proof verifies alongside any candidate
  whatsoever*, including one whose policy binding names a different policy entirely. Binding
  the two is 5B-1's decision-scope repair. ``tests/test_adversarial.py`` pins this.
* **Not the bounds the candidate carries.** Whether ``max_permitted_magnitude`` and
  ``max_permitted_delta`` on a candidate are the bounds this policy states is bound-extraction
  work, not authenticity work, and is out of scope. What this artifact gives a consumer who
  later extracts bounds is :attr:`policy_body_digest`: the framed digest of the exact body
  that was verified. Extract against that body, and the extraction is bound to a verified
  artifact; extract against anything else, and it is not.
* **Not the policy body itself.** A verified artifact is fully digest-covered, so it carries
  no arbitrary object. The resolved artifact reaches a consumer through
  :attr:`~.verification.PolicyAuthenticityResult.resolution`, the Policy Authority's own
  ``PolicyResolution``, which the result carries alongside this one.

Two digest namespaces on one class
-----------------------------------
Every digest field here is a bare 64-hex Policy Authority digest — except
:attr:`candidate_digest_fact`, which is a ``sha256:``-prefixed Phase 5A digest. Each is
validated by its own predicate at construction and the two are never interchanged. See
:mod:`.canonical`.

Why a frozen dataclass is not the boundary
------------------------------------------
Following Phase 4C's ``AuthenticatedRecommendation`` and 5B-0A's
``VerifiedProducerAttestation``: a frozen dataclass stops *accidental* mutation and stops
nothing deliberate. ``object.__new__`` fabricates one with no ``__post_init__``,
``object.__setattr__`` rewrites a frozen field, a subclass diverts every read through a
property, and a duck-typed look-alike never touches this class at all. So the boundary is
made of four things instead: a package-private construction token, a self-digest recomputed
at construction, a provenance registry of every determination this process actually reached,
and revalidation at every consumption boundary through
:func:`require_verified_policy_authenticity`.

What that does **not** close, stated plainly: in-process code that reaches into a private
module attribute can add to the registry, exactly as it can read the token off a genuine
artifact. No Python-level mechanism prevents that. What is closed is every route that does
not require reaching into this module's privates.

The registry holds **digests, not object identities**, so a faithful in-process copy of a
real determination still revalidates, while a forgery naming a determination this process
never reached does not. It does not extend across a process boundary: ``deepcopy`` and
``pickle`` rebuild the token sentinel, so the copy is refused. That is the correct direction
to fail — an artifact that crossed a process boundary is not a determination *this* process
reached — and there is deliberately no deserializer, no ``from_dict`` and no ``to_json``,
because a serialized verification artifact would be a forgeable one.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Optional

from ugence_policy_authority.api import PolicyCoordinate

from .canonical import (
    framed_digest,
    require_phase5a_digest,
    require_policy_digest,
)
from .errors import VerifiedPolicyArtifactIntegrityError as _IntegrityError
from .identifiers import (
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHORITY_CANONICALIZATION_VERSION,
    POLICY_AUTHORITY_PROTOCOL_ID,
    POLICY_TRUST_ANCHOR_OWNER,
    SUPPORTED_SIGNATURE_ALGORITHMS,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .outcomes import PolicyAuthenticityOutcome

__all__ = [
    "VerifiedPolicyAuthenticity",
    "require_verified_policy_authenticity",
]

#: The private construction token. Not exported, not in ``__all__``, not reachable from the
#: curated API. Holding it is what distinguishes an artifact the verifier minted from one a
#: caller assembled.
_VERIFICATION_TOKEN = object()

#: Provenance registry: the ``artifact_digest`` of every determination the authoritative
#: routine has reached in this process. See this module's docstring.
_MINTED_DIGESTS: set = set()


def _record_minted(artifact: "VerifiedPolicyAuthenticity") -> "VerifiedPolicyAuthenticity":
    """Record a determination as reached. Called only by the authoritative routine."""

    _MINTED_DIGESTS.add(artifact.artifact_digest)
    return artifact


@dataclass(frozen=True)
class VerifiedPolicyAuthenticity:
    """The exact-typed, immutable, **non-authoritative** result of a successful verification."""

    # --- the complete coordinate: all six components, none omitted ----------------------
    policy_family: str
    policy_id: str
    policy_version: str
    policy_content_digest: str
    policy_scope: str
    policy_tenant_id: str
    # --- the content binding the signature covers (D-5B0B-2) ----------------------------
    policy_body_digest: str
    # --- who issued it, and under which key ---------------------------------------------
    issuing_authority_id: str
    key_id: str
    signature_alg: str
    record_id: str
    adapter_id: str
    policy_type: str
    # --- what was asked, and under which trust ------------------------------------------
    expected_reference_tenant_id: str
    trust_configuration_digest: str
    policy_trust_anchor_owner: str
    authority_protocol_id: str
    authority_canonicalization_version: str
    # --- validity facts, carried from the inputs; no clock was read ---------------------
    policy_issued_at_fact: datetime
    resolved_as_of_fact: datetime
    # --- scope of the determination; recorded, never reconciled (R-4) -------------------
    candidate_digest_fact: Optional[str]
    # --- how it was verified --------------------------------------------------------------
    verification_profile: str
    verification_profile_version: str
    # --- self ------------------------------------------------------------------------------
    artifact_digest: str
    construction_token: object = None

    def __post_init__(self) -> None:
        if self.construction_token is not _VERIFICATION_TOKEN:
            raise _IntegrityError(
                "VerifiedPolicyAuthenticity cannot be constructed directly. It is minted "
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
                f"verification_profile_version must be exactly {VERIFICATION_PROFILE_VERSION!r}"
            )
        if self.policy_trust_anchor_owner != POLICY_TRUST_ANCHOR_OWNER:
            raise _IntegrityError(
                "policy_trust_anchor_owner must name the ratified owner of the policy trust "
                f"anchor ({POLICY_TRUST_ANCHOR_OWNER!r}); D-5B0B-4 option (a)"
            )
        if self.authority_protocol_id != POLICY_AUTHORITY_PROTOCOL_ID:
            raise _IntegrityError(
                "authority_protocol_id must name the Policy Authority protocol this routine "
                f"was written against ({POLICY_AUTHORITY_PROTOCOL_ID!r})"
            )
        if self.authority_canonicalization_version != POLICY_AUTHORITY_CANONICALIZATION_VERSION:
            raise _IntegrityError(
                "authority_canonicalization_version must name the canonicalization the "
                "verified digests were computed under"
            )
        if self.signature_alg not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise _IntegrityError(
                f"signature_alg {self.signature_alg!r} is outside the closed admitted set"
            )
        # Two digest namespaces, each checked by its own predicate; never interchanged.
        for name in (
            "policy_content_digest",
            "policy_body_digest",
            "trust_configuration_digest",
            "artifact_digest",
        ):
            require_policy_digest(name, getattr(self, name))
        if self.candidate_digest_fact is not None:
            require_phase5a_digest("candidate_digest_fact", self.candidate_digest_fact)
        # The R-3 gate, re-asserted on the artifact itself: the coordinate's content digest
        # IS the body digest the signature covered. The verifier checks it before minting;
        # checking it here too means a mutated artifact cannot present a coordinate that
        # names a different body than the one that was verified.
        if self.policy_content_digest != self.policy_body_digest:
            raise _IntegrityError(
                "policy_content_digest must equal policy_body_digest: the Policy Authority "
                "enforces this at issuance but does not re-enforce it at resolution (ADR "
                "residual R-3), so this boundary refuses an artifact where they differ"
            )
        expected = framed_digest(
            domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN, body=self.digest_payload()
        )
        if self.artifact_digest != expected:
            raise _IntegrityError(
                "artifact_digest does not equal the digest of the bound facts"
            )

    # -- derived, never stored ------------------------------------------------------------ #

    @property
    def outcome(self) -> PolicyAuthenticityOutcome:
        """Always ``VERIFIED``. A read-only property, so it cannot be set."""

        return PolicyAuthenticityOutcome.VERIFIED

    @property
    def grants_authority(self) -> bool:
        """Always ``False``. Derived, and with no branch that returns ``True``.

        Policy authenticity is not authorization. This property exists so the statement is
        executable rather than merely written down.
        """

        return False

    @property
    def historical(self) -> bool:
        """Always ``False``. A historical resolution is refused at admission (D-5B0B-1)."""

        return False

    @property
    def implies_current_validity(self) -> bool:
        """Always ``True`` — *at* :attr:`resolved_as_of_fact`, and only there.

        Mirrors ``PolicyResolution.implies_current_validity``. It says the answer is a
        statement about the present rather than the past; it does **not** say that the
        instant it was judged at is honest. See R-2 in this module's docstring.
        """

        return True

    @property
    def policy_coordinate(self) -> PolicyCoordinate:
        """Rebuild the Policy Authority coordinate this determination is about.

        Derived on every read from the six bound components, so it cannot drift from them,
        and typed as the authority's own coordinate so a consumer never re-assembles one by
        hand from loose strings.
        """

        return PolicyCoordinate(
            policy_family=self.policy_family,
            policy_id=self.policy_id,
            version=self.policy_version,
            content_digest=self.policy_content_digest,
            scope=self.policy_scope,
            tenant_id=self.policy_tenant_id,
        )

    # -- canonical form --------------------------------------------------------------------- #

    def digest_payload(self) -> dict:
        """Every bound fact, and nothing derived except the two framed refusals.

        ``artifact_digest`` and ``construction_token`` are excluded — a digest cannot cover
        itself, and a process-local sentinel is not canonicalizable. Every other field is
        present, so a field rewritten after construction moves the digest.
        """

        return {
            "policy_family": self.policy_family,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_content_digest": self.policy_content_digest,
            "policy_scope": self.policy_scope,
            "policy_tenant_id": self.policy_tenant_id,
            "policy_body_digest": self.policy_body_digest,
            "issuing_authority_id": self.issuing_authority_id,
            "key_id": self.key_id,
            "signature_alg": self.signature_alg,
            "record_id": self.record_id,
            "adapter_id": self.adapter_id,
            "policy_type": self.policy_type,
            "expected_reference_tenant_id": self.expected_reference_tenant_id,
            "trust_configuration_digest": self.trust_configuration_digest,
            "policy_trust_anchor_owner": self.policy_trust_anchor_owner,
            "authority_protocol_id": self.authority_protocol_id,
            "authority_canonicalization_version": self.authority_canonicalization_version,
            "policy_issued_at_fact": self.policy_issued_at_fact,
            "resolved_as_of_fact": self.resolved_as_of_fact,
            "candidate_digest_fact": self.candidate_digest_fact,
            "verification_profile": self.verification_profile,
            "verification_profile_version": self.verification_profile_version,
            # Framed in deliberately: the digest commits to the facts that this artifact
            # establishes policy authenticity, grants nothing, and is not historical.
            "outcome": self.outcome.value,
            "grants_authority": self.grants_authority,
            "historical": self.historical,
        }

    def digest(self) -> str:
        """Recompute this artifact's canonical digest from its current field values."""

        return framed_digest(
            domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN, body=self.digest_payload()
        )

    def __repr__(self) -> str:
        return (
            "VerifiedPolicyAuthenticity(policy="
            f"{self.policy_family}/{self.policy_id}@{self.policy_version}, "
            f"tenant={self.policy_tenant_id!r}, issuer={self.issuing_authority_id!r}, "
            "grants_authority=False)"
        )


def require_verified_policy_authenticity(
    value: Any, name: str = "verified_policy_authenticity"
) -> VerifiedPolicyAuthenticity:
    """Revalidate a verification artifact at a consumption boundary. Refuse anything else.

    Call this **every** time one of these crosses a boundary, not once at the point of
    minting. Five independent checks, each closing a different fabrication route:

    #. exact type — a subclass with a diverting property, and a duck-typed look-alike, both
       fail here;
    #. every declared field is actually present — an ``object.__new__`` fabrication has no
       instance state at all and fails here;
    #. the construction token — an artifact assembled without the verifier fails here;
    #. registry membership — an artifact assembled *with* a borrowed token, read off a
       genuine one, names a determination this process never reached and fails here;
    #. the self-digest, recomputed — a field rewritten with ``object.__setattr__`` after
       construction fails here.
    """

    if type(value) is not VerifiedPolicyAuthenticity:
        raise _IntegrityError(
            f"{name} must be exactly VerifiedPolicyAuthenticity (got "
            f"{type(value).__name__}); a subclass, a duck-typed look-alike and a fabricated "
            "instance are refused, not adapted"
        )
    for field in fields(VerifiedPolicyAuthenticity):
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
