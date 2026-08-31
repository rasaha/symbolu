"""The verification **request** contract — TEV-2's input, not its output.

ADR §30 lists TEV-2 as "the verification authority, trust anchors, key
trust/revocation, signing, independent verification". A verifier needs an input
shape; this is it. It carries what a caller *asks TAP to check against*, and it
carries **no verdict, no status, no verifier identity, no key identifier, no
protocol version and no signature** — every one of which is something only the
act of verification can produce.

The request is an input; the receipt payload is the matching output shape
------------------------------------------------------------------------
TEV-1 also exports :class:`~.receipts.EvidenceVerificationReceiptPayload`, the
structural payload shape ADR §30 and the §32 ledger assign to this milestone
("*shape = TEV-1, service = TEV-2*"). This request and that payload are the two
halves of the same seam: a caller states what TAP should check against, and the
payload states what a verifier declares it found.

**Neither is a verification result.** The payload is caller-constructible, it
carries only *declared* coordinates — outcome, refusal reasons, stage
declarations, verifier/key/protocol identifiers, verification instant — and it
always reports ``STRUCTURAL_UNVERIFIED`` with ``authenticity_verified`` False.
ADR §10 enumerates "an unsigned or untrusted verification object" among the
non-proofs, and §13.3 rules that "a receipt that is unsigned ... is **not** a
receipt", which is exactly why the type is named ``…ReceiptPayload`` and never
``…Receipt``. Signing, signed envelopes, cryptographic verification,
trust-anchor resolution, key validation, key revocation, receipt issuance and
receipt re-verification all remain **TEV-2**.

This request contract itself carries no declared verification coordinates at
all: the verdict-shaped fields live on the payload, not here.

What the request *can* answer, and what it cannot
-------------------------------------------------
:meth:`EvidenceVerificationRequest.structural_scope_mismatches` compares the
evidence's **declared** coordinates against the caller's **expected** ones and
returns the typed refusals for whatever differs, in the ratified reason order.
That is a string-and-digest comparison over two caller-supplied structures. It
is stage-4-shaped but it is **not** ADR §12 stage 4: stage 4 asks whether the
evidence *truly binds* those coordinates, which requires an authentic,
provenance-verified artifact (stages 2-3) before the question is even
meaningful.

Accordingly the method returns **only refusals**. There is no success value: an
empty tuple means "no structural mismatch was detected among the coordinates
compared", and the method's own contract says so. Nothing a caller can build
from this package — including a receipt payload declaring every stage cleared —
establishes authenticity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_exact_type,
    require_identifier,
    require_optional_digest,
)
from .canonical import canonical_bytes, canonical_digest
from .enums import EVIDENCE_TRUST_STAGE_ORDER, EvidenceTrustStage
from .errors import TrustedEvidenceContractError
from .identity import CanonicalEvidenceIdentity
from .reasons import TrustedEvidenceRefusalReason

__all__ = ["EvidenceVerificationRequest"]

_R = TrustedEvidenceRefusalReason

#: The stages a caller may ask TAP to establish. Stage 6 is excluded: ADR §12
#: rules policy sufficiency requirement-relative and assigns it to "the Policy
#: Authority's requirement applied by the consuming evaluation engine — not by
#: TAP". Asking TAP for it is a structural error, not an unfulfilled request.
_REQUESTABLE_STAGES = frozenset(
    s for s in EVIDENCE_TRUST_STAGE_ORDER if s is not EvidenceTrustStage.POLICY_SUFFICIENT
)


@dataclass(frozen=True)
class EvidenceVerificationRequest:
    """What a caller asks a future TAP verifier to check an evidence item against.

    ``as_of`` is a mandatory, timezone-aware, caller-supplied instant with **no
    default** (ADR §22.10 — "explicit caller-supplied evaluation instant ... a
    parameter, not an ambient read"). No code path in this package reads a
    clock.

    ``requested_trust_stages`` is a **set**, not a sequence: the order a caller
    lists stages in carries no meaning, so it is normalized into the ratified
    ADR §12 order and de-duplicated. Two requests differing only in the order
    the caller wrote the stages are therefore the same request and share a
    canonical digest. It must be non-empty, and it must not name
    ``POLICY_SUFFICIENT``.

    The ``expected_*`` coordinates are the caller's assertion of the scope the
    evidence must belong to. Supplying them is not proof of anything; they exist
    so a mismatch is *detectable* (ADR §26.5) rather than assumed away.
    """

    evidence: CanonicalEvidenceIdentity
    expected_content_digest: str
    expected_tenant_id: str
    expected_assessment_context_ref: str
    expected_assessment_context_digest: str
    expected_subject_ref: str
    expected_assessment_purpose_ref: str
    expected_usage_scope_ref: str
    as_of: datetime
    requested_trust_stages: tuple
    expected_assessed_system_binding_ref: str = ""
    expected_assessed_system_binding_digest: str = ""

    def __post_init__(self) -> None:
        require_exact_type(
            self.evidence,
            CanonicalEvidenceIdentity,
            "EvidenceVerificationRequest.evidence",
        )
        require_digest(
            self.expected_content_digest,
            "EvidenceVerificationRequest.expected_content_digest",
        )
        for name in (
            "expected_tenant_id",
            "expected_assessment_context_ref",
            "expected_subject_ref",
            "expected_assessment_purpose_ref",
            "expected_usage_scope_ref",
        ):
            require_identifier(
                getattr(self, name), f"EvidenceVerificationRequest.{name}"
            )
        require_digest(
            self.expected_assessment_context_digest,
            "EvidenceVerificationRequest.expected_assessment_context_digest",
        )
        ref = require_canonical_str(
            self.expected_assessed_system_binding_ref,
            "EvidenceVerificationRequest.expected_assessed_system_binding_ref",
            allow_empty=True,
        )
        digest = require_optional_digest(
            self.expected_assessed_system_binding_digest,
            "EvidenceVerificationRequest.expected_assessed_system_binding_digest",
        )
        if bool(ref) != bool(digest):
            raise TrustedEvidenceContractError(
                "EvidenceVerificationRequest expected_assessed_system_binding_ref "
                "and .expected_assessed_system_binding_digest are co-required: an "
                "expected reference must be digest-bound, and an expected digest "
                "must name the artifact it was computed over"
            )
        require_aware_datetime(self.as_of, "EvidenceVerificationRequest.as_of")
        object.__setattr__(
            self,
            "requested_trust_stages",
            self._normalize_stages(self.requested_trust_stages),
        )

    @staticmethod
    def _normalize_stages(value: object) -> tuple:
        if not isinstance(value, (list, tuple, frozenset, set)):
            raise TrustedEvidenceContractError(
                "EvidenceVerificationRequest.requested_trust_stages must be a "
                f"list, tuple or set of EvidenceTrustStage (got {type(value).__name__})"
            )
        stages = set()
        for index, item in enumerate(value):
            if type(item) is not EvidenceTrustStage:
                raise TrustedEvidenceContractError(
                    "EvidenceVerificationRequest.requested_trust_stages"
                    f"[{index}] must be exactly an EvidenceTrustStage "
                    f"(got {type(item).__name__})"
                )
            if item not in _REQUESTABLE_STAGES:
                raise TrustedEvidenceContractError(
                    f"EvidenceVerificationRequest cannot request {item.value}: "
                    "ADR §12 rules policy sufficiency requirement-relative and "
                    "assigns it to the consuming evaluation engine under a "
                    "Policy Authority requirement, never to TAP"
                )
            stages.add(item)
        if not stages:
            raise TrustedEvidenceContractError(
                "EvidenceVerificationRequest.requested_trust_stages must name at "
                "least one stage; a request that asks for nothing is not a "
                "verification request"
            )
        # Order is semantically irrelevant on input and canonical on storage.
        return tuple(s for s in EVIDENCE_TRUST_STAGE_ORDER if s in stages)

    # ------------------------------------------------------------------ #
    # Structural comparison — refusals only, never a verdict
    # ------------------------------------------------------------------ #
    def structural_scope_mismatches(self) -> tuple:
        """Typed refusals for every declared/expected coordinate that differs.

        Returned in :class:`TrustedEvidenceRefusalReason` declaration order, so
        the sequence is deterministic for identical inputs (ADR §22.13) and a
        digest taken over a refusal set is stable.

        **An empty tuple is not a pass.** It means only that the compared
        coordinates matched. ADR §12 stages 2-6 remain unestablished for every
        object this package can build, ADR §8.1.3 holds that possession is not
        validity, and ADR §10.5 holds that an unsigned verification object
        proves nothing. A caller that treats an empty tuple as verification has
        made exactly the error §10 enumerates.
        """

        scope = self.evidence.scope
        mismatches = []
        if self.evidence.content_digest != self.expected_content_digest:
            mismatches.append(_R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH)
        if scope.tenant_id != self.expected_tenant_id:
            mismatches.append(_R.TRUSTED_EVIDENCE_TENANT_MISMATCH)
        if (
            scope.assessment_context_ref != self.expected_assessment_context_ref
            or scope.assessment_context_digest
            != self.expected_assessment_context_digest
        ):
            mismatches.append(_R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH)
        if scope.subject_ref != self.expected_subject_ref:
            mismatches.append(_R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH)
        if (
            scope.assessed_system_binding_ref
            != self.expected_assessed_system_binding_ref
            or scope.assessed_system_binding_digest
            != self.expected_assessed_system_binding_digest
        ):
            mismatches.append(_R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH)
        if (
            scope.assessment_purpose_ref != self.expected_assessment_purpose_ref
            or scope.usage_scope_ref != self.expected_usage_scope_ref
        ):
            mismatches.append(_R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH)
        order = list(TrustedEvidenceRefusalReason)
        return tuple(sorted(set(mismatches), key=order.index))

    @property
    def unperformed_verification_reason(self) -> TrustedEvidenceRefusalReason:
        """Always ``TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED``.

        A read-only property naming the honest state of every request this
        package can build: a request exists, and no verifier has acted on it. A
        consumer that requires verification refuses on this code (ADR §10, E-8 —
        "when no trusted verifier or trust anchor is configured, the production
        default is **deny**"). It is not settable, and there is no member of
        :class:`TrustedEvidenceRefusalReason` that would represent success.
        """

        return _R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete request."""

        return canonical_digest(self)
