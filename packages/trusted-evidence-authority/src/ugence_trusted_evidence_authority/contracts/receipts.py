"""The structural evidence-verification receipt **payload** (ADR §13, §30, §32).

ADR §30 assigns "receipt shape (§13)" to **TEV-1**, and the §32 status ledger is
explicit: *"Signed, immutable TAP verification receipt (§13) … shape = TEV-1,
service = TEV-2."* This module is that shape.

Payload, not receipt
--------------------
The type is named :class:`EvidenceVerificationReceiptPayload`, not
``EvidenceVerificationReceipt``, because ADR §13.3 rules that "a receipt that is
unsigned, or whose signature does not verify against a configured trust anchor,
is **not** a receipt. There is no 'trusted but unsigned' state." Nothing here is
signed, so nothing here is a receipt. What exists is the **canonical content a
TEV-2 signer will sign and a TEV-2 verifier will check** — and §13.3 requires
exactly that content, its canonicalization version and its domain tag to be
"unambiguous, versioned, and **fixed before signing exists**". Defining it now is
not premature; it is the precondition.

Anyone can construct one
------------------------
This is stated plainly rather than hedged. A payload is caller-constructible, and
every verification coordinate it carries — the outcome, the cleared stages, the
verifier authority, the key identifier, the protocol version, the reason codes —
is a **declaration written by whoever built the object**. None of it is checked,
and none of it can be, because checking requires trust anchors, keys and
signature verification that this milestone does not have (E-8, TEV-2).

The contract is honest about that at every turn:

* every declared field is named ``declared_*`` or reads as a claim, never a fact;
* :class:`~..enums.DeclaredVerificationOutcome` members carry a ``DECLARED_``
  prefix;
* :attr:`~EvidenceVerificationReceiptPayload.structural_status` is a permanently
  ``STRUCTURAL_UNVERIFIED`` **property**, not a field;
* :attr:`~EvidenceVerificationReceiptPayload.authenticity_verified` is
  permanently ``False``;
* ``CRYPTOGRAPHICALLY_AUTHENTIC`` is in
  :attr:`~EvidenceVerificationReceiptPayload.unestablished_trust_stages` no
  matter what :attr:`declared_cleared_stages` says.

**Declared** and **established** are two different words for two different
things, and this module never lets them merge. ADR §10.2's forbidden artifact is
"a lifecycle label … carried on the artifact itself"; a declared outcome is the
same species, and is treated the same way.

No signature field
------------------
None, not even optional, not even a placeholder. §13.3 separates the concerns:
"signature fields never participate in the content digest, but the digest is
bound **through** the signed payload". TEV-1 owns the payload and its canonical
bytes; TEV-2 owns the signature, the envelope that carries it, the key trust and
the revocation check. An optional or placeholder signature field would create the
"trusted but unsigned" state §13.3 prohibits, and would invite a caller to fill
it with anything.

Stages 1-5 only
---------------
ADR §12: "a receipt therefore records stages 1-5 and **never asserts stage 6
globally**". Policy sufficiency is requirement-relative, owned by the consuming
evaluation engine under a Policy Authority requirement. A payload naming
``POLICY_SUFFICIENT`` in either stage list is refused.

Two validity intervals, never conflated
---------------------------------------
§13.1.6: "the receipt's own validity is distinct from the evidence's effective
period, and **both are carried**". They are separate field pairs, both half-open
``[from, to)`` per §17.9, and both participate in the digest. A caller reading
one for the other is reading a different fact.

Authorizes nothing
------------------
§13.2: a receipt never authorizes deployment, never authorizes runtime action,
never proves economic value, never proves causal attribution, and never silently
converts reported evidence into verified truth. A payload — which is strictly
weaker than a receipt — authorizes strictly less than that, which is nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ._validation import (
    require_aware_datetime,
    require_digest,
    require_exact_type,
    require_identifier,
    require_optional_aware_datetime,
    require_strictly_before,
)
from .canonical import canonical_bytes, canonical_digest
from .enums import (
    EVIDENCE_TRUST_STAGE_ORDER,
    RECEIPT_REPORTABLE_TRUST_STAGES,
    DeclaredVerificationOutcome,
    EvidenceStructuralStatus,
    EvidenceTrustStage,
)
from .errors import TrustedEvidenceContractError
from .identity import EvidenceSchemaRef, EvidenceScopeBinding
from .reasons import TrustedEvidenceRefusalReason

__all__ = ["EvidenceVerificationReceiptPayload"]

_REPORTABLE = frozenset(RECEIPT_REPORTABLE_TRUST_STAGES)


def _normalize_members(value: object, name: str, member_type: type, order: tuple) -> tuple:
    """Normalize a caller-supplied *set* of enum members into ratified order.

    The order a caller lists these in carries no meaning — a set of cleared
    stages is a set — so it is normalized and de-duplicated. Two payloads
    differing only in the order the caller wrote them are the same payload and
    share canonical bytes (ADR §22.2, §22.13).
    """

    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TrustedEvidenceContractError(
            f"{name} must be a list, tuple or set of {member_type.__name__} "
            f"(got {type(value).__name__})"
        )
    members = set()
    for index, item in enumerate(value):
        if type(item) is not member_type:
            raise TrustedEvidenceContractError(
                f"{name}[{index}] must be exactly a {member_type.__name__} "
                f"(got {type(item).__name__}); a lookalike carrying a matching "
                "value is refused because the vocabulary is closed"
            )
        members.add(item)
    return tuple(m for m in order if m in members)


@dataclass(frozen=True)
class EvidenceVerificationReceiptPayload:
    """The canonical content of an evidence-verification receipt (ADR §13).

    Immutable, deterministic, canonicalizable and digest-bound — and **not** a
    receipt, because nothing signed it. Read the module docstring before
    treating any field as established.

    Field groups, mapped to the ADR
    -------------------------------
    ============================================  ==========================
    ``receipt_id``, ``schema``                    §13.1.1 receipt identity/version
    ``source_evidence_identity_digest``           §13.1.2 bind the source evidence
    ``evidence_content_digest``                   §9 row 3, §13.1.2
    ``verification_request_digest``               §13.1.1 what was asked
    ``scope``                                     §13.1.3 tenant/context/subject/system/purpose/scope
    ``verified_at``                               §9 row 6, §13.1.5
    ``verifier_authority_id``, ``verifier_key_id``  §9 row 14, §13.1.4
    ``verification_protocol_id``/``_version``     §9 row 15
    ``declared_outcome``, ``declared_refusal_reasons``  §9 row 16
    ``declared_cleared_stages``,
    ``declared_unattempted_stages``               §13.1.1, §12 stages 1-5
    ``evidence_valid_from``/``_to``               §9 row 17, §13.1.6
    ``receipt_valid_from``/``_to``                §13.1.6, distinct from evidence
    ============================================  ==========================

    The canonicalization version and the receipt domain tag (§13.3) are bound by
    the canonical **frame** rather than carried as fields, exactly as for every
    other contract in this package — so they cannot be edited by a caller, and a
    receipt digest can never be mistaken for an evidence-identity digest.

    ``verifier_key_id`` is an **opaque coordinate**. No key format, algorithm
    identifier, curve, encoding or trust-anchor semantics is specified or
    implied — those are TEV-2's, and inventing them here would fix constants the
    ADR has not ratified.
    """

    receipt_id: str
    schema: EvidenceSchemaRef
    source_evidence_identity_digest: str
    evidence_content_digest: str
    verification_request_digest: str
    scope: EvidenceScopeBinding
    verified_at: datetime
    verifier_authority_id: str
    verifier_key_id: str
    verification_protocol_id: str
    verification_protocol_version: str
    declared_outcome: DeclaredVerificationOutcome
    declared_cleared_stages: tuple
    declared_unattempted_stages: tuple
    declared_refusal_reasons: tuple
    evidence_valid_from: Optional[datetime] = None
    evidence_valid_to: Optional[datetime] = None
    receipt_valid_from: Optional[datetime] = None
    receipt_valid_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "verifier_authority_id",
            "verifier_key_id",
            "verification_protocol_id",
            "verification_protocol_version",
        ):
            require_identifier(
                getattr(self, name), f"EvidenceVerificationReceiptPayload.{name}"
            )
        for name in (
            "source_evidence_identity_digest",
            "evidence_content_digest",
            "verification_request_digest",
        ):
            require_digest(
                getattr(self, name), f"EvidenceVerificationReceiptPayload.{name}"
            )
        require_exact_type(
            self.schema,
            EvidenceSchemaRef,
            "EvidenceVerificationReceiptPayload.schema",
        )
        require_exact_type(
            self.scope,
            EvidenceScopeBinding,
            "EvidenceVerificationReceiptPayload.scope",
        )
        require_exact_type(
            self.declared_outcome,
            DeclaredVerificationOutcome,
            "EvidenceVerificationReceiptPayload.declared_outcome",
        )
        require_aware_datetime(
            self.verified_at, "EvidenceVerificationReceiptPayload.verified_at"
        )

        cleared = _normalize_members(
            self.declared_cleared_stages,
            "EvidenceVerificationReceiptPayload.declared_cleared_stages",
            EvidenceTrustStage,
            EVIDENCE_TRUST_STAGE_ORDER,
        )
        unattempted = _normalize_members(
            self.declared_unattempted_stages,
            "EvidenceVerificationReceiptPayload.declared_unattempted_stages",
            EvidenceTrustStage,
            EVIDENCE_TRUST_STAGE_ORDER,
        )
        reasons = _normalize_members(
            self.declared_refusal_reasons,
            "EvidenceVerificationReceiptPayload.declared_refusal_reasons",
            TrustedEvidenceRefusalReason,
            tuple(TrustedEvidenceRefusalReason),
        )

        for label, stages in (
            ("declared_cleared_stages", cleared),
            ("declared_unattempted_stages", unattempted),
        ):
            outside = [s.value for s in stages if s not in _REPORTABLE]
            if outside:
                raise TrustedEvidenceContractError(
                    f"EvidenceVerificationReceiptPayload.{label} may not name "
                    f"{', '.join(outside)}: ADR §12 rules that a receipt records "
                    "stages 1-5 and never asserts stage 6 globally, because "
                    "policy sufficiency is requirement-relative and belongs to "
                    "the consuming evaluation engine"
                )
        overlap = sorted(s.value for s in set(cleared) & set(unattempted))
        if overlap:
            raise TrustedEvidenceContractError(
                "EvidenceVerificationReceiptPayload declares "
                f"{', '.join(overlap)} both cleared and not attempted; a stage "
                "cannot be simultaneously established and untried"
            )

        admitted = self.declared_outcome is DeclaredVerificationOutcome.DECLARED_ADMITTED
        if admitted:
            if not cleared:
                raise TrustedEvidenceContractError(
                    "EvidenceVerificationReceiptPayload declares "
                    "DECLARED_ADMITTED but names no cleared stage; an admission "
                    "that clears nothing describes no verification"
                )
            if reasons:
                raise TrustedEvidenceContractError(
                    "EvidenceVerificationReceiptPayload declares "
                    "DECLARED_ADMITTED and also carries refusal reasons "
                    f"({', '.join(r.value for r in reasons)}); every member of "
                    "the vocabulary is a refusal, so an admission carries none"
                )
        else:
            if not reasons:
                raise TrustedEvidenceContractError(
                    f"EvidenceVerificationReceiptPayload declares "
                    f"{self.declared_outcome.value} but carries no reason code; "
                    "ADR §11 requires every fail-closed condition to carry a "
                    "stable typed reason"
                )
        if (
            self.declared_outcome is DeclaredVerificationOutcome.DECLARED_INDETERMINATE
            and TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_INDETERMINATE not in reasons
        ):
            raise TrustedEvidenceContractError(
                "EvidenceVerificationReceiptPayload declares "
                "DECLARED_INDETERMINATE but does not carry "
                "TRUSTED_EVIDENCE_INDETERMINATE; ADR §11 makes an undecidable "
                "verification a refusal that must name itself as one"
            )

        object.__setattr__(self, "declared_cleared_stages", cleared)
        object.__setattr__(self, "declared_unattempted_stages", unattempted)
        object.__setattr__(self, "declared_refusal_reasons", reasons)

        for name in (
            "evidence_valid_from",
            "evidence_valid_to",
            "receipt_valid_from",
            "receipt_valid_to",
        ):
            require_optional_aware_datetime(
                getattr(self, name), f"EvidenceVerificationReceiptPayload.{name}"
            )
        for start, end, label in (
            ("evidence_valid_from", "evidence_valid_to", "evidence"),
            ("receipt_valid_from", "receipt_valid_to", "receipt"),
        ):
            lower, upper = getattr(self, start), getattr(self, end)
            if lower is not None and upper is not None:
                require_strictly_before(
                    lower,
                    upper,
                    f"EvidenceVerificationReceiptPayload.{start}",
                    f"EvidenceVerificationReceiptPayload.{end}",
                    f"the {label} validity interval is half-open [{start}, {end}) "
                    "per ADR §17.9",
                )

    # ------------------------------------------------------------------ #
    # Honest, non-settable status — the same discipline as ADR §14.5
    # ------------------------------------------------------------------ #
    @property
    def structural_status(self) -> EvidenceStructuralStatus:
        """Always ``STRUCTURAL_UNVERIFIED``, whatever the payload declares.

        A read-only property, not a field: no constructor argument, assignment
        or subclass hook raises it. Raising it requires TEV-2's signed envelope,
        trust anchors and signature verification.
        """

        return EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED

    @property
    def authenticity_verified(self) -> bool:
        """Always ``False`` — constructing a payload attests nothing.

        In particular this stays ``False`` for a payload declaring
        ``DECLARED_ADMITTED`` with every reportable stage cleared and an
        authoritative-sounding verifier name. That combination is the exact
        artifact ADR §10 enumerates as a non-proof.
        """

        return False

    @property
    def established_trust_stages(self) -> tuple:
        """The ADR §12 stages this payload actually establishes.

        Exactly ``(STRUCTURALLY_CONSTRUCTIBLE,)``. Note the contrast with
        :attr:`declared_cleared_stages`, which is whatever the caller wrote.
        """

        return (EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,)

    @property
    def unestablished_trust_stages(self) -> tuple:
        """The stages that remain unestablished — always the other five.

        ``CRYPTOGRAPHICALLY_AUTHENTIC`` is always present here, regardless of
        :attr:`declared_cleared_stages`: no signature has been verified, so
        §12 stage 2 has not been reached however emphatically the payload says
        otherwise.
        """

        established = set(self.established_trust_stages)
        return tuple(s for s in EVIDENCE_TRUST_STAGE_ORDER if s not in established)

    @property
    def declared_unestablished_stages(self) -> tuple:
        """Reportable stages the payload does **not** claim to have cleared.

        Derived from :attr:`declared_cleared_stages`, so it covers stages that
        were attempted and failed as well as stages never attempted. Still a
        statement *the payload makes*, not an independent finding.
        """

        cleared = set(self.declared_cleared_stages)
        return tuple(s for s in RECEIPT_REPORTABLE_TRUST_STAGES if s not in cleared)

    @property
    def envelope_verification_reason(self) -> TrustedEvidenceRefusalReason:
        """Always ``TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED``.

        The honest state of every payload this package can build: no signed
        envelope exists and none was verified. A consumer that requires
        verification refuses on this code — ADR E-8, "when no trusted verifier or
        trust anchor is configured, the production default is **deny**".
        """

        return TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED

    @property
    def declares_admission(self) -> bool:
        """Whether the payload's declared outcome is ``DECLARED_ADMITTED``.

        Reports what the payload **says**, and is named to make that
        unmistakable. It is not a verification result and must never be used as
        an admission decision — ADR §10.1 forbids consumers from treating any
        caller-settable boolean as proof, and this one is derived directly from
        caller-written content.
        """

        return self.declared_outcome is DeclaredVerificationOutcome.DECLARED_ADMITTED

    def receipt_is_valid_at(self, instant: datetime) -> bool:
        """Half-open ``[receipt_valid_from, receipt_valid_to)`` membership.

        The **receipt's** own validity, never the evidence's — see
        :meth:`evidence_is_valid_at`. ``instant`` is an explicit caller input;
        the system clock is never read (ADR §22.9, §22.10).
        """

        require_aware_datetime(
            instant, "EvidenceVerificationReceiptPayload.receipt_is_valid_at.instant"
        )
        return _within(instant, self.receipt_valid_from, self.receipt_valid_to)

    def evidence_is_valid_at(self, instant: datetime) -> bool:
        """Half-open ``[evidence_valid_from, evidence_valid_to)`` membership.

        The **evidence's** declared validity as recorded by this payload, which
        §13.1.6 keeps distinct from the receipt's own. A payload may be within
        its own validity while the evidence it attests is not, and the two
        questions must never be answered with one another's bounds.
        """

        require_aware_datetime(
            instant, "EvidenceVerificationReceiptPayload.evidence_is_valid_at.instant"
        )
        return _within(instant, self.evidence_valid_from, self.evidence_valid_to)

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over.

        Framed under the receipt domain tag, so these bytes can never collide
        with an evidence-identity, schema, scope, observation, provenance,
        applicability, claim or verification-request encoding (ADR §26.6).
        """

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete payload.

        This is the content a TEV-2 signer will sign. It is an identity
        fingerprint over caller-written content — not a signature, and not proof
        that any of that content is true.
        """

        return canonical_digest(self)


def _within(instant: datetime, lower: Optional[datetime], upper: Optional[datetime]) -> bool:
    if lower is not None and instant < lower:
        return False
    if upper is not None and instant >= upper:
        return False
    return True
