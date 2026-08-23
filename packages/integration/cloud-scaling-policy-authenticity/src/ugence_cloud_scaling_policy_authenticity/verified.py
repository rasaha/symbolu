"""``VerifiedPolicyAuthenticity`` — a verification artifact, and not an authorization.

What it establishes
-------------------
Exactly one thing: that at the injected instant :attr:`resolved_as_of_fact`, through the
resolution port the composition root wired, the complete policy coordinate this artifact
names resolved to a **non-historical** ``RESOLVED`` answer — meaning the Policy Authority found a record under that exact coordinate, the
stored artifact still re-derived it and still canonicalized, the declared and signed body
digests both equalled the recomputed one, the issuance signature verified under a key of the
named authority that was un-revoked, in-window, tenant-permitted and entitled to
``ISSUE_POLICY``, external approval evidence held, the lifecycle was active, the instant fell
inside the effective period, and no verified revocation applied.

Note what that sentence does **not** say. It does not say *which* trust configuration the
resolution ran under: :attr:`trust_configuration_digest` is what the port reported about
itself, which is why it sits in the recorded half. See :meth:`recorded_facts`.

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
* **Not bound to a recommendation.** :attr:`candidate_digest_fact` records which candidate
  the determination accompanied, and since 5B-1 that candidate is **reconciled**: gate 11
  compares its policy coordinate — all six components, the signed body digest and the issuing
  identity — against the resolved policy, and refuses the pair with
  ``CANDIDATE_COORDINATE_MISMATCH`` when they disagree. ``None`` means no candidate
  accompanied the determination; it never means one was carried unchecked.

  What remains open is narrower and is 5B-0A's A-59 residual, not this one: the *producer
  attestation* is bound to the recommendation rather than to the candidate, and this package
  establishes nothing about that binding. Reading a ``VERIFIED`` here as "the recommendation
  this candidate carries is the one a trusted producer signed" is still wrong.
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
    POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
    POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
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
    "VERIFIED_FACT_NAMES",
    "RECORDED_FACT_NAMES",
    "DERIVED_FACT_NAMES",
    "VERIFIED_DIGEST_KEYS",
    "require_partition_agreement",
]

#: The facts a gate actually checked. Ordered as a frozenset because membership, not order,
#: is what the partition asserts; the payload orders them by construction.
VERIFIED_FACT_NAMES: "frozenset[str]" = frozenset(
    {
        "policy_family",
        "policy_id",
        "policy_version",
        "policy_content_digest",
        "policy_scope",
        "policy_tenant_id",
        "policy_body_digest",
        "issuing_authority_id",
        "key_id",
        "signature_alg",
        "record_id",
        "adapter_id",
        "expected_reference_tenant_id",
        "policy_trust_anchor_owner",
        "authority_protocol_id",
        "authority_canonicalization_version",
        "policy_issued_at_fact",
        "verification_profile",
        "verification_profile_version",
        #: Promoted from the recorded half by 5B-1, when gate 11 began reconciling it against
        #: the resolved coordinate. ``None`` means no candidate accompanied the determination;
        #: it never means a candidate was carried unchecked.
        "candidate_digest_fact",
    }
)

#: The facts carried and digest-covered but **never attested** (D-5B0B-7). A member leaves
#: this set only when something starts actually checking it, and doing so moves the artifact
#: digest — which is the point. **Three** members since 5B-1, for three distinct reasons —
#: ``candidate_digest_fact`` left this half when gate 11 began reconciling it, and the artifact
#: digest and the profile version both moved with it, which is exactly what a promotion is
#: supposed to look like:
#:
#: * ``resolved_as_of_fact`` — open residual **R-2**: the instant is injected and unvalidated.
#: * ``policy_type`` — **not signature-covered and never compared.** It is absent from the 21
#:   keys of ``IssuedPolicyRecord.signing_payload()`` (``adapter_id`` is present; this is not),
#:   and ``resolve_policy`` never compares the record's ``policy_type`` against the adapter
#:   descriptor's. A record differing only in this field resolves ``RESOLVED`` and would mint a
#:   ``VERIFIED`` artifact carrying the substituted value. It is transitively committed inside
#:   ``policy_body_digest``, whose frame includes it — but a hash is one-way, and this package
#:   holds no adapter registry with which to re-derive the descriptor, so there is nothing here
#:   to check it against.
#: * ``trust_configuration_digest`` — **self-reported by the resolution port.** The port is the
#:   seam to the authority, so any check this package could make would be the port vouching for
#:   itself: a wrapper delegating to a genuine ``PolicyAuthorityResolutionPort`` while reporting
#:   an arbitrary well-formed digest is indistinguishable from the genuine port at this
#:   boundary. Only the composition root knows which trust configuration it wired.
RECORDED_FACT_NAMES: "frozenset[str]" = frozenset(
    {
        "resolved_as_of_fact",
        "policy_type",
        "trust_configuration_digest",
    }
)

#: Names that enter the **verified half of the digest** but are not constructor fields of
#: :class:`VerifiedPolicyAuthenticity` — derived at mint time and constant on any artifact this
#: package produces (R-7, 5B-2).
#:
#: Before this existed the membership lived in three places: the two sets above, the two literal
#: maps in ``verification.py``, and an unnamed ``derived`` tuple reconciling them. Nothing
#: compared the three, so the only thing catching a divergence was the artifact's own self-digest
#: failing at some later point — a correctness backstop, but one that reports the symptom rather
#: than the edit. :func:`require_partition_agreement` compares them at mint time, so a name added
#: to one place and forgotten in another fails immediately and says which side is short.
DERIVED_FACT_NAMES: "frozenset[str]" = frozenset(
    {
        "outcome",
        "grants_authority",
        "historical",
    }
)

#: Exactly what the verified half of the digest payload must contain. The single canonical
#: statement of that membership.
VERIFIED_DIGEST_KEYS: "frozenset[str]" = VERIFIED_FACT_NAMES | DERIVED_FACT_NAMES


def require_partition_agreement(
    *, verified_map: "dict[str, object]", recorded_map: "dict[str, object]"
) -> None:
    """Refuse to mint when a payload map disagrees with the canonical membership (R-7).

    Raises :class:`VerifiedPolicyArtifactIntegrityError`, this package's ``INVARIANT_VIOLATION``:
    a verifier whose own partition has drifted cannot be trusted to say what it verified, so it
    must not conclude at all.
    """

    for label, actual, expected in (
        ("verified", frozenset(verified_map), VERIFIED_DIGEST_KEYS),
        ("recorded", frozenset(recorded_map), RECORDED_FACT_NAMES),
    ):
        if actual == expected:
            continue
        raise _IntegrityError(
            f"the {label} half of the digest payload does not match the canonical membership "
            f"declared in verified.py: missing {sorted(expected - actual)}, "
            f"unexpected {sorted(actual - expected)}. The payload and the declaration must be "
            "edited together, and this refusal is what makes that unavoidable"
        )

#: The private construction token. Not exported, not in ``__all__``, not reachable from the
#: curated API. Holding it is what distinguishes an artifact the verifier minted from one a
#: caller assembled.
_VERIFICATION_TOKEN = object()

#: Provenance registry: the ``artifact_digest`` of every determination the authoritative
#: routine has reached in this process. See this module's docstring.
_MINTED_DIGESTS: set = set()


def _framed_partition(*, verified_map: dict, recorded_map: dict) -> dict:
    """The two separately framed maps, in the one shape the artifact digest covers.

    Module-level and shared by :meth:`VerifiedPolicyAuthenticity.digest_payload` and the
    minting routine, so the shape cannot drift between the digest that is stamped and the
    digest that is recomputed to check it.
    """

    return {
        "verified": {
            "domain": POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
            "facts": verified_map,
        },
        "recorded": {
            "domain": POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
            "facts": recorded_map,
        },
    }


def _partitioned_digest(*, verified_map: dict, recorded_map: dict) -> str:
    """The artifact digest over both frames. The only routine that stamps one."""

    return framed_digest(
        domain=POLICY_AUTHENTICITY_DIGEST_DOMAIN,
        body=_framed_partition(verified_map=verified_map, recorded_map=recorded_map),
    )


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

    def verified_facts(self) -> dict:
        """The facts a gate actually checked. Every entry was established, not merely carried.

        ``artifact_digest`` and ``construction_token`` are absent — a digest cannot cover
        itself, and a process-local sentinel is not canonicalizable. The two recorded facts
        are absent because they were never attested; see :meth:`recorded_facts`.
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
            "expected_reference_tenant_id": self.expected_reference_tenant_id,
            "policy_trust_anchor_owner": self.policy_trust_anchor_owner,
            "authority_protocol_id": self.authority_protocol_id,
            "authority_canonicalization_version": self.authority_canonicalization_version,
            "policy_issued_at_fact": self.policy_issued_at_fact,
            "verification_profile": self.verification_profile,
            "verification_profile_version": self.verification_profile_version,
            "candidate_digest_fact": self.candidate_digest_fact,
            # Framed in deliberately: the digest commits to the facts that this artifact
            # establishes policy authenticity, grants nothing, and is not historical.
            "outcome": self.outcome.value,
            "grants_authority": self.grants_authority,
            "historical": self.historical,
        }

    def recorded_facts(self) -> dict:
        """Facts carried and digest-covered, but **never attested** (D-5B0B-7).

        Three members since 5B-1, and each is here because nothing established it — see
        :data:`RECORDED_FACT_NAMES` for the reason attached to each. One names an open residual
        (``resolved_as_of_fact``/R-2); ``policy_type`` is neither signature-covered nor
        compared at resolution; ``trust_configuration_digest`` is reported by the resolution
        port about itself. ``candidate_digest_fact`` was the fourth until R-4 closed.

        Being in this map does **not** mean the value is unprotected: it is inside the
        artifact digest, so it cannot be rewritten after the fact. It means nobody checked it.
        A consumer that needs any of these to be *true* must establish it somewhere else.
        """

        return {
            "resolved_as_of_fact": self.resolved_as_of_fact,
            "policy_type": self.policy_type,
            "trust_configuration_digest": self.trust_configuration_digest,
        }

    def digest_payload(self) -> dict:
        """The two separately framed maps the artifact digest covers.

        Each half carries its own domain tag as an ordinary canonical field, so the frame a
        fact sits in is part of what the digest commits to. Promoting a fact from ``recorded``
        to ``verified`` — which is what 5B-1 and 5B-2 do when they close R-4 and R-2 — is
        therefore a visible change to the artifact digest, not a silent relabelling.
        """

        return _framed_partition(
            verified_map=self.verified_facts(), recorded_map=self.recorded_facts()
        )

    def verified_fact(self, name: str):
        """Read one **attested** fact by name. Refuses a recorded one.

        The accessor a consumer reaches for when it wants to act on something this package
        established. Asking it for ``resolved_as_of_fact`` is a category error and is refused
        rather than answered, because the answer would read as attested. Plain attribute access still reaches those fields — this is the surface that
        says which is which, not a lock.
        """

        if name in RECORDED_FACT_NAMES:
            raise _IntegrityError(
                f"{name!r} is a recorded fact, not a verified one: it is carried and "
                "digest-covered but nothing checked it. Read it through recorded_fact(), "
                "which says so at the call site"
            )
        if name not in VERIFIED_FACT_NAMES:
            raise _IntegrityError(
                f"{name!r} is not a fact of a verification artifact"
            )
        return getattr(self, name)

    def recorded_fact(self, name: str):
        """Read one **unverified** recorded fact by name. Refuses a verified one.

        Symmetric on purpose: an attested fact read through this accessor would understate
        what is known, and a caller reading everything through one accessor would learn
        nothing from either.
        """

        if name not in RECORDED_FACT_NAMES:
            raise _IntegrityError(
                f"{name!r} is not a recorded fact; recorded_fact() answers only for "
                f"{sorted(RECORDED_FACT_NAMES)}"
            )
        return getattr(self, name)

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


# --- the partition is total and disjoint, checked at import ------------------------------- #
_PARTITIONED = VERIFIED_FACT_NAMES | RECORDED_FACT_NAMES
_UNPARTITIONABLE = {"artifact_digest", "construction_token"}
_DECLARED = {f.name for f in fields(VerifiedPolicyAuthenticity)} - _UNPARTITIONABLE
if VERIFIED_FACT_NAMES & RECORDED_FACT_NAMES:  # pragma: no cover - import guard
    raise AssertionError(
        "a fact cannot be both verified and recorded: "
        f"{sorted(VERIFIED_FACT_NAMES & RECORDED_FACT_NAMES)}"
    )
if _PARTITIONED != _DECLARED:  # pragma: no cover - import guard
    raise AssertionError(
        "every field of a verification artifact must be classified as verified or recorded; "
        f"unclassified: {sorted(_DECLARED - _PARTITIONED)}; "
        f"named but not declared: {sorted(_PARTITIONED - _DECLARED)}. Adding a field means "
        "deciding whether a gate checked it, which is the decision D-5B0B-7 ratified."
    )
