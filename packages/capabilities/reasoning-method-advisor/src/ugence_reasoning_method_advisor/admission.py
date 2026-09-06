"""Slice 3 — product entry as a separate, digest-bound admission record.

The slice 2 request and advisory are **unchanged, field for field**: every
historical digest — including a preregistered pilot manifest that embeds an
advisory — still verifies. Product entry is a new record,
``ReasoningMethodAdvisoryAdmission``, that cites the advisory by digest, the
engine-produced ``ReadinessComparisonResult`` it was granted on by digest, and
the fit assessments that admit it by theirs. The advisory stays
``COMPARISON_EVIDENCE_ABSENT`` / ``RESEARCH_ONLY``; the admission is what is
``COMPARISON_EVIDENCE_PRESENT`` / ``ADVISORY_INPUT``.

``admit`` takes the **result**, never a bare bundle of assessments. The result
contract binds every assessment to one engine identity and one request digest
(``ASSESSOR_ENGINE_MISMATCH``), and ``admit`` refuses a result that names any
engine but the comparison engine. A hand-assembled tuple of assessments cannot
be admitted at all. That closes provenance *structurally*: what it does not
close is a forged result. Under SCR-1
(``ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING``) the composition root verifies
the engine's signature over the result through the Trusted Evidence Authority's
anchors — outside this package, which imports neither the engine nor the
authority — and hands ``admit`` the outcome as a typed fact,
``VerifiedResultSignature``. With ``require_signature=True`` an unsigned result
is refused; a record whose digest is not this result's is refused; a record
naming another signer is unbound. The admission cites the verification record
by ``result_signature_receipt_digest``. The trade-off is stated, not hidden: the
advisor trusts the composition root's verification, and an auditor re-verifies
from the cited digest outside the advisor. ``ComparisonEvidence`` stays as the
internal shape the coverage rule reads.

Evidence never creates a qualifier. ``admit`` reads the advisory's qualifying
set as the rule set produced it and asks one question per method: is there a
sufficient fit assessment, for exactly this method reference and this task
class, in the presented evidence? All covered — admitted. Any covered method
with an ``INSUFFICIENT_QUALITY`` assessment — refused as contradicted. Less
than all covered, or no qualifier at all — refused as research-only. There is
no third outcome and no downgrade: an admission either exists or was refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import FrozenSet, List, Optional, Tuple

from ugence_reasoning_method_governance.api import (
    COMPARISON_RESULT_SCHEMA_VERSION,
    EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT,
    USAGE_SCOPE_ADVISORY_INPUT,
    ContractError,
    ContractErrorCode,
    FitOutcome,
    ReadinessComparisonResult,
    ReasoningMethodCatalogRef,
    ReasoningMethodFitAssessment,
    ReasoningMethodRef,
)

from ._canon import digest_of, require_digest, require_nonblank, require_str_tuple, require_tzaware, settle_digest
from .contracts import (
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryRequest,
    RuleSetRef,
    _NoScalarLabels,
    validate_against_request,
)
from .errors import AdvisorError, AdvisorErrorCode
from .version import __version__

ADMISSION_SCHEMA_VERSION = "reasoning_method.advisory_admission.v3"
ADMITTER_IDENTITY = "ugence-reasoning-method-advisor"
#: The comparison engine's identity, mirrored by literal: this package never imports
#: ``ugence_readiness_comparison`` (``tests/test_profiles.py::test_p8``), so it can
#: neither run a comparison nor read one it was not handed. A result naming any other
#: engine is refused as unbound.
COMPARISON_ENGINE_IDENTITY = "ugence-readiness-comparison"

#: The fit outcomes that count as comparison evidence *for* a method.
#: INSUFFICIENT_QUALITY is evidence against it; COMPARISON_EVIDENCE_ABSENT is none.
SUFFICIENT_FIT_OUTCOMES: FrozenSet[FitOutcome] = frozenset({FitOutcome.SUFFICIENT_PARETO_EFFICIENT, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED})


@dataclass(frozen=True)
class VerifiedResultSignature(_NoScalarLabels):
    """The typed fact a composition root hands ``admit`` after verifying the engine's
    signature over a ``ReadinessComparisonResult`` (SCR-1).

    This package does not verify signatures and does not import the package that
    does. It checks the record against the result it was given: ``result_digest``
    must be the result's own, and ``signer_identity`` must be the comparison
    engine's. ``verification_receipt_digest`` is the verifier's record digest in this
    package's bare-hex grammar (the attestation package spells it ``sha256:<hex>``;
    the composition root drops the prefix, as the bridge adds it back for the
    proposer). An auditor re-verifies from that digest, outside this package.
    """

    result_digest: str
    signer_identity: str
    signer_key_id: str
    verification_receipt_digest: str
    verifier_identity: str
    verified_at: datetime

    def __post_init__(self) -> None:
        require_digest(self.result_digest, "VerifiedResultSignature.result_digest")
        require_nonblank(self.signer_identity, "VerifiedResultSignature.signer_identity")
        require_nonblank(self.signer_key_id, "VerifiedResultSignature.signer_key_id")
        require_digest(self.verification_receipt_digest, "VerifiedResultSignature.verification_receipt_digest")
        require_nonblank(self.verifier_identity, "VerifiedResultSignature.verifier_identity")
        require_tzaware(self.verified_at, "VerifiedResultSignature.verified_at")


@dataclass(frozen=True)
class ComparisonEvidence(_NoScalarLabels):
    """Fit assessments a requester presents for one task class over one catalog.

    Presenting is not proving: ``admit`` decides per qualifying method. Every
    assessment must be for ``task_class_digest`` and name a method in ``catalog``,
    and no two may share a digest (``COMPARISON_EVIDENCE_UNBOUND`` otherwise).
    """

    task_class_digest: str
    catalog: ReasoningMethodCatalogRef
    assessments: Tuple[ReasoningMethodFitAssessment, ...]

    def __post_init__(self) -> None:
        require_digest(self.task_class_digest, "ComparisonEvidence.task_class_digest")
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ComparisonEvidence.catalog must be a ReasoningMethodCatalogRef")
        if not isinstance(self.assessments, tuple) or not all(isinstance(a, ReasoningMethodFitAssessment) for a in self.assessments):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ComparisonEvidence.assessments must be a tuple of ReasoningMethodFitAssessment")
        if not self.assessments:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ComparisonEvidence.assessments must be non-empty")
        seen: set = set()
        for a in self.assessments:
            if a.task_class_digest != self.task_class_digest:
                raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"assessment {a.assessment_id} is for another task class")
            if a.method.catalog != self.catalog:
                raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"assessment {a.assessment_id} names a method outside this catalog")
            if a.assessment_digest in seen:
                raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"assessment {a.assessment_id} is presented twice")
            seen.add(a.assessment_digest)

    def digests(self) -> FrozenSet[str]:
        return frozenset(a.assessment_digest for a in self.assessments)


@dataclass(frozen=True)
class ReasoningMethodAdvisoryAdmission(_NoScalarLabels):
    """The record that lets one advisory enter the product as typed input.

    Cites the advisory it admits by digest, restates the qualifying set and the
    primary exactly as the advisory carried them (so a reader need not resolve the
    advisory to see what was admitted), and cites the admitting assessments by
    digest. ``evidence_status`` and ``usage_scope`` are fixed: this record exists
    only in the admitted state. A verified admission proves that the evidence
    covered the rule set's result at ``admitted_at``; it authorizes nothing.
    """

    schema_version: str
    advisory_id: str
    advisory_digest: str
    request_digest: str
    #: The engine-produced ``ReadinessComparisonResult`` this admission was granted on.
    comparison_result_digest: str
    #: The verifier's record for the engine's signature over that result (SCR-1):
    #: ``None`` in the research posture, present whenever a signature was required.
    result_signature_receipt_digest: Optional[str]
    task_class_digest: str
    catalog: ReasoningMethodCatalogRef
    rule_set: RuleSetRef
    qualifying: Tuple[ReasoningMethodRef, ...]
    primary: Optional[ReasoningMethodRef]
    evidence_refs: Tuple[str, ...]
    evidence_status: str
    usage_scope: str
    admitter_identity: str
    admitter_version: str
    admitted_at: datetime
    admission_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodAdvisoryAdmission.schema_version")
        require_nonblank(self.advisory_id, "ReasoningMethodAdvisoryAdmission.advisory_id")
        require_digest(self.advisory_digest, "ReasoningMethodAdvisoryAdmission.advisory_digest")
        require_digest(self.request_digest, "ReasoningMethodAdvisoryAdmission.request_digest")
        require_digest(self.comparison_result_digest, "ReasoningMethodAdvisoryAdmission.comparison_result_digest")
        if self.result_signature_receipt_digest is not None:
            require_digest(self.result_signature_receipt_digest, "ReasoningMethodAdvisoryAdmission.result_signature_receipt_digest")
        require_digest(self.task_class_digest, "ReasoningMethodAdvisoryAdmission.task_class_digest")
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "catalog must be a ReasoningMethodCatalogRef")
        if not isinstance(self.rule_set, RuleSetRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "rule_set must be a RuleSetRef")
        if not isinstance(self.qualifying, tuple) or not all(isinstance(m, ReasoningMethodRef) for m in self.qualifying):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "qualifying must be a tuple of ReasoningMethodRef")
        if not self.qualifying:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "an admission requires at least one qualifying method")
        keys = [m.sort_key for m in self.qualifying]
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "qualifying must be ordered by (method_id, method_version) without repeats")
        if self.primary is not None:
            if not isinstance(self.primary, ReasoningMethodRef) or len(self.qualifying) != 1 or self.primary != self.qualifying[0]:
                raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, "an admission's primary is the sole qualifying method or absent")
        elif len(self.qualifying) == 1:
            raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, "exactly one method qualifies but no primary is set")
        require_str_tuple(self.evidence_refs, "evidence_refs")
        if not self.evidence_refs:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "an admission cites at least one assessment")
        for d in self.evidence_refs:
            require_digest(d, "evidence_refs item")
        if list(self.evidence_refs) != sorted(set(self.evidence_refs)):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "evidence_refs must be sorted and unique")
        if self.evidence_status != EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"evidence_status is fixed at {EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT} on an admission")
        if self.usage_scope != USAGE_SCOPE_ADVISORY_INPUT:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_ADVISORY_INPUT} on an admission")
        require_nonblank(self.admitter_identity, "admitter_identity")
        require_nonblank(self.admitter_version, "admitter_version")
        require_tzaware(self.admitted_at, "admitted_at")
        settle_digest(self, "admission_digest", digest_of(self, exclude=("admission_digest",)))


def _covering_refs(advisory: ReasoningMethodAdvisory, evidence: ComparisonEvidence) -> Tuple[str, ...]:
    """The digests of the assessments that cover every qualifying method, or a refusal."""
    if not advisory.qualifying:
        raise AdvisorError(AdvisorErrorCode.RESEARCH_ONLY_REFUSED_IN_PRODUCT, "no method qualifies; there is nothing to admit")
    refs: List[str] = []
    uncovered: List[str] = []
    for q in advisory.qualifying:
        matching = [a for a in evidence.assessments if a.method == q.method]
        if any(a.outcome is FitOutcome.INSUFFICIENT_QUALITY for a in matching):
            raise AdvisorError(
                AdvisorErrorCode.COMPARISON_EVIDENCE_CONTRADICTED,
                f"{q.method.method_id} qualifies under the rule set but a presented fit assessment finds it INSUFFICIENT_QUALITY for this task class",
            )
        sufficient = [a for a in matching if a.outcome in SUFFICIENT_FIT_OUTCOMES]
        if not sufficient:
            uncovered.append(q.method.method_id)
        refs.extend(a.assessment_digest for a in sufficient)
    if uncovered:
        raise AdvisorError(
            AdvisorErrorCode.RESEARCH_ONLY_REFUSED_IN_PRODUCT,
            "no sufficient comparison evidence for qualifying method(s): " + ", ".join(uncovered),
        )
    return tuple(sorted(set(refs)))


def evidence_from_result(
    result: ReadinessComparisonResult,
    advisory: ReasoningMethodAdvisory,
    *,
    verified: Optional[VerifiedResultSignature] = None,
    require_signature: bool = False,
) -> ComparisonEvidence:
    """The internal evidence bundle an engine result carries for this advisory.

    Refuses (``COMPARISON_EVIDENCE_UNBOUND``) a result naming any engine but the
    comparison engine, a result of another schema version, an empty result, and —
    through ``ComparisonEvidence`` — any assessment for another task class or catalog.

    Signature posture (SCR-1): with ``require_signature`` and no ``verified`` record,
    ``COMPARISON_RESULT_UNSIGNED``. With a record whose ``result_digest`` is not this
    result's, ``COMPARISON_RESULT_SIGNATURE_MISMATCH``. With a record whose signer is
    not the comparison engine, ``COMPARISON_EVIDENCE_UNBOUND``. A record is checked
    whenever one is handed in, required or not.
    """
    if not isinstance(result, ReadinessComparisonResult):
        raise TypeError("admit() takes a ReadinessComparisonResult, never a bare bundle of assessments")
    if not isinstance(require_signature, bool):
        raise TypeError("require_signature must be a bool")
    if advisory.task_class_digest is None:
        raise AdvisorError(AdvisorErrorCode.CLASSIFICATION_INCONSISTENT, "an unclassified advisory can never be admitted")
    if result.engine_identity != COMPARISON_ENGINE_IDENTITY:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"result names engine {result.engine_identity!r}, not the comparison engine")
    if result.schema_version != COMPARISON_RESULT_SCHEMA_VERSION:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"result schema {result.schema_version!r} is not admitted")
    _check_signature(result, verified, require_signature)
    if not result.assessments:
        raise AdvisorError(AdvisorErrorCode.RESEARCH_ONLY_REFUSED_IN_PRODUCT, "the result carries no assessment; there is nothing to admit on")
    return ComparisonEvidence(advisory.task_class_digest, advisory.catalog, tuple(result.assessments))


def _check_signature(result: ReadinessComparisonResult, verified: Optional[VerifiedResultSignature], require_signature: bool) -> None:
    if verified is None:
        if require_signature:
            raise AdvisorError(AdvisorErrorCode.COMPARISON_RESULT_UNSIGNED, "require_signature=True and no VerifiedResultSignature was handed in; an unsigned result admits nothing")
        return
    if not isinstance(verified, VerifiedResultSignature):
        raise TypeError("verified must be a VerifiedResultSignature, the typed fact a composition root constructs after verifying")
    if verified.result_digest != result.result_digest:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_RESULT_SIGNATURE_MISMATCH, "the verified signature covers a different result than the one being admitted")
    if verified.signer_identity != COMPARISON_ENGINE_IDENTITY:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, f"the result was signed by {verified.signer_identity!r}, not the comparison engine")


def admit(
    advisory: ReasoningMethodAdvisory,
    request: ReasoningMethodAdvisoryRequest,
    result: ReadinessComparisonResult,
    *,
    admitted_at: datetime,
    verified: Optional[VerifiedResultSignature] = None,
    require_signature: bool = False,
) -> ReasoningMethodAdvisoryAdmission:
    """Admit ``advisory`` to the product on an engine ``result``, or refuse.

    Binds the advisory to its request first (``validate_against_request``), so an
    advisory cannot be admitted against a request it did not answer. The request
    must be governed: an unclassified advisory is never admitted
    (``CLASSIFICATION_INCONSISTENT``). The result must be the comparison engine's
    and every assessment in it must be for the advisory's own task class and
    catalog (``COMPARISON_EVIDENCE_UNBOUND``). This is the product gate: the
    ``rules.research.v0`` fixture, or any rule set, passes only with sufficient
    evidence for everything it made qualify — never by name — and only evidence
    the engine produced. With ``require_signature=True`` it also passes only with a
    ``VerifiedResultSignature`` for exactly this result (SCR-1); the admission then
    cites the verification record by ``result_signature_receipt_digest``.
    """
    require_tzaware(admitted_at, "admitted_at")
    validate_against_request(advisory, request)
    evidence = evidence_from_result(result, advisory, verified=verified, require_signature=require_signature)
    refs = _covering_refs(advisory, evidence)
    return ReasoningMethodAdvisoryAdmission(
        schema_version=ADMISSION_SCHEMA_VERSION,
        advisory_id=advisory.advisory_id,
        advisory_digest=advisory.advisory_digest,
        request_digest=advisory.request_digest,
        comparison_result_digest=result.result_digest,
        result_signature_receipt_digest=None if verified is None else verified.verification_receipt_digest,
        task_class_digest=advisory.task_class_digest,
        catalog=advisory.catalog,
        rule_set=advisory.rule_set,
        qualifying=tuple(q.method for q in advisory.qualifying),
        primary=advisory.primary,
        evidence_refs=refs,
        evidence_status=EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT,
        usage_scope=USAGE_SCOPE_ADVISORY_INPUT,
        admitter_identity=ADMITTER_IDENTITY,
        admitter_version=__version__,
        admitted_at=admitted_at,
    )


def validate_admission(
    admission: ReasoningMethodAdvisoryAdmission,
    advisory: ReasoningMethodAdvisory,
    result: ReadinessComparisonResult,
    *,
    verified: Optional[VerifiedResultSignature] = None,
    require_signature: bool = False,
) -> None:
    """Replay: the admission must describe exactly this advisory and this result.

    ``DIGEST_MALFORMED`` when the advisory, request or result digests differ, a
    cited assessment is not in the result, or the cited signature record is not the
    one handed in; ``CLASSIFICATION_INCONSISTENT`` when the restated qualifying set
    or primary is not the advisory's; ``COMPARISON_EVIDENCE_UNBOUND`` when the
    result is not the engine's. The signature checks replay exactly as in ``admit``.
    Coverage is then recomputed, so an admission cannot outlive the result it was
    granted on.
    """
    if not isinstance(admission, ReasoningMethodAdvisoryAdmission):
        raise TypeError("validate_admission(admission, advisory, result)")
    if admission.advisory_digest != advisory.advisory_digest or admission.request_digest != advisory.request_digest:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission does not describe this advisory")
    evidence = evidence_from_result(result, advisory, verified=verified, require_signature=require_signature)
    if admission.comparison_result_digest != result.result_digest:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission was not granted on this comparison result")
    expected_receipt = None if verified is None else verified.verification_receipt_digest
    if admission.result_signature_receipt_digest != expected_receipt:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission does not cite the signature verification record handed in")
    if admission.qualifying != tuple(q.method for q in advisory.qualifying) or admission.primary != advisory.primary:
        raise AdvisorError(AdvisorErrorCode.CLASSIFICATION_INCONSISTENT, "admission restates a qualifying set or primary the advisory does not carry")
    unknown = sorted(set(admission.evidence_refs) - evidence.digests())
    if unknown:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission cites assessments not presented: " + ", ".join(unknown))
    if admission.evidence_refs != _covering_refs(advisory, evidence):
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission's evidence refs are not the covering set for this evidence")


__all__ = [
    "ADMISSION_SCHEMA_VERSION",
    "ADMITTER_IDENTITY",
    "COMPARISON_ENGINE_IDENTITY",
    "SUFFICIENT_FIT_OUTCOMES",
    "VerifiedResultSignature",
    "ComparisonEvidence",
    "ReasoningMethodAdvisoryAdmission",
    "evidence_from_result",
    "admit",
    "validate_admission",
]
