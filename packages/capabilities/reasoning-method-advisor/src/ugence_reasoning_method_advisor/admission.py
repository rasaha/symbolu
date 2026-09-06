"""Slice 3 — product entry as a separate, digest-bound admission record.

The slice 2 request and advisory are **unchanged, field for field**: every
historical digest — including a preregistered pilot manifest that embeds an
advisory — still verifies. Product entry is a new record,
``ReasoningMethodAdvisoryAdmission``, that cites the advisory by digest and
the fit assessments that admit it by theirs. The advisory stays
``COMPARISON_EVIDENCE_ABSENT`` / ``RESEARCH_ONLY``; the admission is what is
``COMPARISON_EVIDENCE_PRESENT`` / ``ADVISORY_INPUT``.

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
    EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT,
    USAGE_SCOPE_ADVISORY_INPUT,
    ContractError,
    ContractErrorCode,
    FitOutcome,
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

ADMISSION_SCHEMA_VERSION = "reasoning_method.advisory_admission.v1"
ADMITTER_IDENTITY = "ugence-reasoning-method-advisor"

#: The fit outcomes that count as comparison evidence *for* a method.
#: INSUFFICIENT_QUALITY is evidence against it; COMPARISON_EVIDENCE_ABSENT is none.
SUFFICIENT_FIT_OUTCOMES: FrozenSet[FitOutcome] = frozenset({FitOutcome.SUFFICIENT_PARETO_EFFICIENT, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED})


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


def admit(
    advisory: ReasoningMethodAdvisory,
    request: ReasoningMethodAdvisoryRequest,
    evidence: ComparisonEvidence,
    *,
    admitted_at: datetime,
) -> ReasoningMethodAdvisoryAdmission:
    """Admit ``advisory`` to the product on ``evidence``, or refuse.

    Binds the advisory to its request first (``validate_against_request``), so an
    advisory cannot be admitted against a request it did not answer. The request
    must be governed: an unclassified advisory is never admitted
    (``CLASSIFICATION_INCONSISTENT``). The evidence must be for the advisory's own
    task class and catalog (``COMPARISON_EVIDENCE_UNBOUND``). This is the product
    gate: the ``rules.research.v0`` fixture, or any rule set, passes only with
    sufficient evidence for everything it made qualify — never by name.
    """
    if not isinstance(evidence, ComparisonEvidence):
        raise TypeError("admit() takes a ComparisonEvidence")
    require_tzaware(admitted_at, "admitted_at")
    validate_against_request(advisory, request)
    if advisory.task_class_digest is None:
        raise AdvisorError(AdvisorErrorCode.CLASSIFICATION_INCONSISTENT, "an unclassified advisory can never be admitted")
    if evidence.task_class_digest != advisory.task_class_digest:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, "evidence is for another task class")
    if evidence.catalog != advisory.catalog:
        raise AdvisorError(AdvisorErrorCode.COMPARISON_EVIDENCE_UNBOUND, "evidence is over another catalog")
    refs = _covering_refs(advisory, evidence)
    return ReasoningMethodAdvisoryAdmission(
        schema_version=ADMISSION_SCHEMA_VERSION,
        advisory_id=advisory.advisory_id,
        advisory_digest=advisory.advisory_digest,
        request_digest=advisory.request_digest,
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


def validate_admission(admission: ReasoningMethodAdvisoryAdmission, advisory: ReasoningMethodAdvisory, evidence: ComparisonEvidence) -> None:
    """Replay: the admission must describe exactly this advisory and cite only this evidence.

    ``DIGEST_MALFORMED`` when the advisory or request digests differ or a cited
    assessment was not presented; ``CLASSIFICATION_INCONSISTENT`` when the
    restated qualifying set or primary is not the advisory's. Coverage is then
    recomputed, so an admission cannot outlive the evidence it was granted on.
    """
    if not isinstance(admission, ReasoningMethodAdvisoryAdmission):
        raise TypeError("validate_admission(admission, advisory, evidence)")
    if admission.advisory_digest != advisory.advisory_digest or admission.request_digest != advisory.request_digest:
        raise ContractError(ContractErrorCode.DIGEST_MALFORMED, "admission does not describe this advisory")
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
    "SUFFICIENT_FIT_OUTCOMES",
    "ComparisonEvidence",
    "ReasoningMethodAdvisoryAdmission",
    "admit",
    "validate_admission",
]
