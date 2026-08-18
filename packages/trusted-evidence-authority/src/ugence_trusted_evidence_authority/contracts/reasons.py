"""The typed trusted-evidence refusal vocabulary (ADR §11, E-9, DD-1).

ADR §11 ratifies that every evidence-admission failure condition is fail-closed
and carries a **stable, typed, namespace-scoped** reason code, and records the
exact vocabulary as **DD-1** — "implementation detail; §11 ratifies that codes
must be stable, typed and namespace-scoped, which is the boundary-relevant
part". DD-1 is therefore not an *unresolved* decision that TEV-1 must stop on;
it is a decision the ADR explicitly delegates to this milestone. This module
discharges it for the TEV-1 surface.

Every member is a **refusal**
-----------------------------
There is no success member, and none can be added without changing this type's
name and documentation. In particular ``TRUSTED_EVIDENCE_INDETERMINATE`` is a
refusal, not a pass — ADR §11: "*Indeterminate is a refusal, not a pass. A
verifier that cannot decide has not verified.*" Because the enum is *entirely*
refusals, "no reason code" is the only way to express "nothing was refused", and
that is deliberately **not** a positive verification state either (§10).

Namespace
---------
Every member is prefixed ``TRUSTED_EVIDENCE_``: neutral, capability-scoped, and
free of milestone branding. There are **no aliases and no deprecated spellings**
— ADR §22.11 requires a namespace that is "stable across versions, never reused
for a different meaning", which alias pairs immediately violate.

One vocabulary, extended additively by TEV-2
-------------------------------------------
TEV-1 shipped **nineteen** codes and recorded that several ratified ADR §11
conditions were real but unreachable without a verifier, naming each of them
"**TEV-2.**". TEV-2 exists, so those codes now exist:
``TRUSTED_EVIDENCE_PRODUCER_UNKNOWN`` / ``…_PRODUCER_UNAUTHORIZED`` (§11 row 4),
the key-lifecycle family (§11 row 5) and
``TRUSTED_EVIDENCE_SIGNATURE_INVALID`` (§11 row 6), together with the
envelope, profile, encoding, trust-anchor, protocol and receipt-validity codes
§13.3 requires. They are **appended** in a clearly-marked TEV-2 block, so the
nineteen TEV-1 members keep their exact declaration order and their exact
ordinal positions; :data:`TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS` pins that set
and a test asserts it is the first nineteen members in order.

A separate TEV-2 enum was considered and **rejected**: DD-1 delegates "the exact
typed reason-code vocabulary and namespace strings for evidence verification" in
the singular, and §22.11 requires a namespace "stable across versions, never
reused for a different meaning" — two parallel refusal enums would immediately
be the duplicate, conflicting namespace that rule exists to prevent. No TEV-1
member is renamed, re-valued, re-ordered or removed, and no alias is minted.

What remains deliberately **absent**
------------------------------------
* ``UNIT_MISMATCH`` / ``METRIC_MISMATCH`` (§11 row 13) — a unit or metric is
  mismatched only *against a requirement*, and ADR §12 rules requirement
  sufficiency (stage 6) requirement-relative and never TAP's. It belongs to the
  consuming evaluation engine under a Policy Authority requirement (§18). Not
  TEV-2's, and still not shipped.
* Any benchmark refusal code — BR-1/BR-2 own that vocabulary (§16.3).

**No evidence-supersession code exists.** ADR §28's ratified *evidence*
lifecycle has no supersession arrow; supersession appears only in the
*benchmark* lifecycle (§29) and is itself deferred to DD-4. Inventing an
evidence-supersession reason would ratify a lifecycle the ADR does not have.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "TrustedEvidenceRefusalReason",
    "TRUSTED_EVIDENCE_REFUSAL_REASONS",
    "TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS",
    "TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS",
]


class TrustedEvidenceRefusalReason(str, Enum):
    """Stable typed refusal codes for trusted-evidence admission (ADR §11).

    Declaration order is the **deterministic reason ordering** required by ADR
    §22.13: any routine that reports several refusals sorts them into this
    order, so a digest taken over a result set is stable. Members are grouped
    presence -> structure -> identity -> integrity -> scope -> provenance ->
    time -> lifecycle -> verification-unavailable, which is the order in which
    the ADR §16.2-style ordered checks would encounter them.
    """

    # -- presence ---------------------------------------------------------- #
    #: §11 row 1 — no evidence was supplied where evidence is required.
    TRUSTED_EVIDENCE_MISSING = "TRUSTED_EVIDENCE_MISSING"

    # -- structure --------------------------------------------------------- #
    #: §11 row 2 — the contract does not parse into a well-formed known shape.
    TRUSTED_EVIDENCE_MALFORMED_CONTRACT = "TRUSTED_EVIDENCE_MALFORMED_CONTRACT"
    #: §11 row 12 — the declared schema id/version is not one this stage admits.
    TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED = "TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED"
    #: §22.8 — the declared evidence type is not one this stage admits.
    TRUSTED_EVIDENCE_TYPE_UNSUPPORTED = "TRUSTED_EVIDENCE_TYPE_UNSUPPORTED"

    # -- identity ---------------------------------------------------------- #
    #: §9 — a required identity coordinate is absent or blank.
    TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING = (
        "TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING"
    )

    # -- integrity --------------------------------------------------------- #
    #: §11 row 3 — the declared content digest does not equal the expected one.
    TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH = (
        "TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH"
    )

    # -- scope (§7.1 row 5; replay/swap resistance, §26.5) ------------------ #
    #: §11 row 7 — the evidence binds a different tenant.
    TRUSTED_EVIDENCE_TENANT_MISMATCH = "TRUSTED_EVIDENCE_TENANT_MISMATCH"
    #: §11 row 8 — the evidence binds a different assessment context.
    TRUSTED_EVIDENCE_CONTEXT_MISMATCH = "TRUSTED_EVIDENCE_CONTEXT_MISMATCH"
    #: §11 row 9 — the evidence binds a different subject.
    TRUSTED_EVIDENCE_SUBJECT_MISMATCH = "TRUSTED_EVIDENCE_SUBJECT_MISMATCH"
    #: §11 row 9 — the evidence binds a different assessed-system binding.
    TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH = (
        "TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH"
    )
    #: §7.1 row 5 — the evidence binds a different declared purpose or usage
    #: scope than the one admission was requested for.
    TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH = "TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH"

    # -- provenance -------------------------------------------------------- #
    #: §11 row 11 — the declared chain of custody does not match, or is broken.
    TRUSTED_EVIDENCE_PROVENANCE_MISMATCH = "TRUSTED_EVIDENCE_PROVENANCE_MISMATCH"

    # -- time -------------------------------------------------------------- #
    #: §11 row 10 — the caller's instant precedes the validity interval.
    TRUSTED_EVIDENCE_NOT_YET_VALID = "TRUSTED_EVIDENCE_NOT_YET_VALID"
    #: §11 row 10 — the caller's instant is at or past the validity interval's
    #: exclusive end (half-open ``[valid_from, valid_to)``, ADR §17.9).
    TRUSTED_EVIDENCE_STALE = "TRUSTED_EVIDENCE_STALE"

    # -- lifecycle --------------------------------------------------------- #
    #: §11 row 15 — the evidence is revoked.
    TRUSTED_EVIDENCE_REVOKED = "TRUSTED_EVIDENCE_REVOKED"
    #: §28 — the proposed lifecycle transition is not a ratified arrow.
    TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION = (
        "TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION"
    )

    # -- verification unavailable (never a pass) ---------------------------- #
    #: §10 — a consumer required verification and none was performed. This is
    #: the code for the ordinary TEV-1 situation: contracts exist, no verifier
    #: does. Possession of a structurally valid contract is not verification.
    TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED = (
        "TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED"
    )
    #: §11 row 14 — a verifier was configured but timed out or errored.
    TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE = "TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE"
    #: §11 row 16 — the verifier could not decide. **A refusal, never a pass.**
    TRUSTED_EVIDENCE_INDETERMINATE = "TRUSTED_EVIDENCE_INDETERMINATE"

    # ==================================================================== #
    # TEV-2 additive block — appended, never interleaved
    # ==================================================================== #
    # Every member below is required by a ratified ADR §11 row or §13.3
    # property that TEV-1 could not reach and named as TEV-2's. They are
    # **appended** so the nineteen TEV-1 members keep their exact declaration
    # order and therefore their exact ordinal positions: ADR §22.13's
    # deterministic reason ordering sorts by declaration index, so inserting a
    # member among them would silently re-order a previously-issued refusal
    # sequence. A new namespace was considered and rejected — DD-1 delegates
    # "the exact typed reason-code vocabulary … for evidence verification" in
    # the singular, and a second enum would be exactly the duplicate,
    # conflicting reason namespace §22.11 prohibits.

    # -- envelope structure (§13.3; §11 row 2 applied to the envelope) ------ #
    #: §13.3 — the signed envelope does not parse into the ratified shape.
    TRUSTED_EVIDENCE_ENVELOPE_MALFORMED = "TRUSTED_EVIDENCE_ENVELOPE_MALFORMED"
    #: §13.3 — the envelope's declared payload digest is not the digest of the
    #: payload it carries. The digest is always recomputed, never believed.
    TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH = (
        "TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH"
    )

    # -- cryptographic profile (§13.3, §22.8; DD-9) ------------------------- #
    #: §22.8 — the named signature profile is not the one ratified profile.
    #: There is no negotiation and no fallback, so this is always a refusal.
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED = (
        "TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED"
    )
    #: DD-9 — signature or key material is not in the one canonical encoding
    #: (uppercase hex, a prefix, padding, a wrong length, or non-hex input).
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID = (
        "TRUSTED_EVIDENCE_SIGNATURE_ENCODING_INVALID"
    )

    # -- authority and key coordinates (§9 row 14; §26.5) ------------------- #
    #: §9 row 14 — the artifact names a different signer authority than the
    #: resolved trust anchor belongs to.
    TRUSTED_EVIDENCE_AUTHORITY_MISMATCH = "TRUSTED_EVIDENCE_AUTHORITY_MISMATCH"
    #: §9 row 14 — the artifact names a different key identifier than the one
    #: resolved. An authority name alone is never sufficient (§10.3).
    TRUSTED_EVIDENCE_KEY_ID_MISMATCH = "TRUSTED_EVIDENCE_KEY_ID_MISMATCH"

    # -- trust-anchor resolution (§11 row 5; E-5, E-8; §26.9) --------------- #
    #: §11 row 5 (`KEY_UNKNOWN`) — no trust anchor exists at the exact
    #: coordinate. Resolution is exact-coordinate only; there is no latest(),
    #: no default key, no partial match and no first-key-wins.
    TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING = "TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING"
    #: §26.9 — more than one anchor answers the coordinate. Guessing between
    #: them would be an unsigned authority decision, so it fails closed.
    TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS = (
        "TRUSTED_EVIDENCE_TRUST_ANCHOR_AMBIGUOUS"
    )
    #: E-8 — no trusted verifier or trust anchor is configured at all. "The
    #: production default is **deny**"; this is the code that denial carries.
    TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED = (
        "TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED"
    )
    #: §7.1 row 9 — the resolved anchor is not entitled to the capability the
    #: artifact requires. E-3/§8.1.1: a producing key may never issue receipts.
    TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH = (
        "TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH"
    )

    # -- key lifecycle (§11 row 5; §13.3 key revocation; §17.9) ------------- #
    #: §11 row 5 (`KEY_NOT_YET_VALID`) — evaluated before the key's activation.
    TRUSTED_EVIDENCE_KEY_NOT_YET_VALID = "TRUSTED_EVIDENCE_KEY_NOT_YET_VALID"
    #: §11 row 5 (`KEY_EXPIRED`) — evaluated at or after the key's exclusive
    #: end bound; key validity is half-open `[from, to)` per §17.9.
    TRUSTED_EVIDENCE_KEY_EXPIRED = "TRUSTED_EVIDENCE_KEY_EXPIRED"
    #: §7.1 row 9 — the anchor is administratively disabled. Distinct from
    #: revocation: disabling carries no effective instant and is reversible by
    #: reconfiguration, whereas revocation is dated and terminal.
    TRUSTED_EVIDENCE_KEY_DISABLED = "TRUSTED_EVIDENCE_KEY_DISABLED"
    #: §11 row 5 (`KEY_REVOKED`), §13.3 — the key is revoked as of the
    #: evaluation instant. §26.8 keeps key revocation distinct from evidence
    #: revocation (`TRUSTED_EVIDENCE_REVOKED`) and from policy-version
    #: revocation, which is another authority's concern entirely.
    TRUSTED_EVIDENCE_KEY_REVOKED = "TRUSTED_EVIDENCE_KEY_REVOKED"

    # -- signature (§11 row 6) ---------------------------------------------- #
    #: §11 row 6 — the signature did not verify over the reconstructed signed
    #: input under the resolved key. The single load-bearing cryptographic gate.
    TRUSTED_EVIDENCE_SIGNATURE_INVALID = "TRUSTED_EVIDENCE_SIGNATURE_INVALID"

    # -- producer attribution (§11 row 4; E-3, E-4) ------------------------- #
    #: §11 row 4 (`PRODUCER_UNKNOWN`) — the producing identity is not one the
    #: configured trust boundary knows.
    TRUSTED_EVIDENCE_PRODUCER_UNKNOWN = "TRUSTED_EVIDENCE_PRODUCER_UNKNOWN"
    #: §11 row 4 (`PRODUCER_UNAUTHORIZED`) — the producer is known but is not
    #: authorized for this evidence. E-3: labelling it verified changes nothing.
    TRUSTED_EVIDENCE_PRODUCER_UNAUTHORIZED = "TRUSTED_EVIDENCE_PRODUCER_UNAUTHORIZED"

    # -- verification protocol (§9 row 15; §22.8) --------------------------- #
    #: §22.8 — the named verification protocol is not one this authority runs.
    TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED = "TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED"
    #: §9 row 15 — the protocol is known but the named version is not the one
    #: bound into the signed input. Protocol and version are bound separately
    #: so a version skew is distinguishable from an unknown protocol.
    TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH = (
        "TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH"
    )

    # -- receipt validity (§13.1.6; §17.9) ---------------------------------- #
    #: §13.1.6 — the evaluation instant precedes the receipt's own validity.
    #: Distinct from `TRUSTED_EVIDENCE_NOT_YET_VALID`, which is the *evidence's*
    #: interval; §13.1.6 requires the two never be conflated.
    TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID = "TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID"
    #: §13.1.6 — the evaluation instant is at or past the receipt's exclusive
    #: end bound. Distinct from `TRUSTED_EVIDENCE_STALE`, which is the evidence's.
    TRUSTED_EVIDENCE_RECEIPT_EXPIRED = "TRUSTED_EVIDENCE_RECEIPT_EXPIRED"


#: The nineteen refusal codes ratified and shipped by TEV-1, frozen for
#: backward compatibility.
#:
#: TEV-2 appended members to :class:`TrustedEvidenceRefusalReason`; it changed,
#: removed, renamed and re-ordered **none** of these. The package tests assert
#: this set is exactly the first nineteen members in declaration order, so a
#: later milestone cannot quietly reshuffle the vocabulary a merged receipt was
#: issued under.
TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS: frozenset = frozenset(
    {
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MISSING,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SCHEMA_UNSUPPORTED,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TYPE_UNSUPPORTED,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_IDENTITY_COORDINATE_MISSING,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TENANT_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_CONTEXT_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SUBJECT_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_PROVENANCE_MISMATCH,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_NOT_YET_VALID,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_STALE,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_REVOKED,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_INVALID_LIFECYCLE_TRANSITION,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE,
        TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_INDETERMINATE,
    }
)

#: The refusal codes TEV-2 added, as an immutable set.
#:
#: Every member discharges an ADR §11 row or §13.3 property that TEV-1 named as
#: TEV-2's own. Like every other member of the vocabulary, each is a
#: **refusal**: TEV-2 added no success state, and the enum still has none.
TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS: frozenset = frozenset(
    TrustedEvidenceRefusalReason
) - TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS

#: Every member of :class:`TrustedEvidenceRefusalReason`, as an immutable set.
#:
#: The equality ``TRUSTED_EVIDENCE_REFUSAL_REASONS == set(TrustedEvidenceRefusalReason)``
#: is asserted by the package tests. It is the structural statement that the
#: vocabulary contains **no success state**: there is nothing to add a member to
#: except the refusal set.
TRUSTED_EVIDENCE_REFUSAL_REASONS: frozenset = frozenset(TrustedEvidenceRefusalReason)
