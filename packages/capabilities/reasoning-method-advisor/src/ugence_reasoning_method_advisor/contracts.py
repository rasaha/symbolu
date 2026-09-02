"""Slice 2 contracts (specification §2–§4).

Digests reuse the slice 1 canonicalization helpers so an advisory's payload
discipline is identical to the governance contracts': enums by value,
datetimes as RFC 3339 UTC, integers never present, tuples in declared order,
``ugence_jcs`` SHA-256 with no prefix.

No contract here can hold a number, and no advisory type may declare a field
whose name reads as a score, rank, weight, priority, probability, confidence,
cost, latency or resource label: such a declaration is refused at class
definition (slice 1's ``SCALAR_LABEL_FIELD_PRESENT`` pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import FrozenSet, Optional, Tuple

from ugence_reasoning_method_governance.api import (
    COMPLEXITY_SIGNAL_TOKENS,
    USAGE_SCOPE_RESEARCH_ONLY,
    ConsequenceClass,
    ContractError,
    ContractErrorCode,
    ImplementationStatus,
    ReasoningMethodCatalog,
    ReasoningMethodCatalogRef,
    ReasoningMethodEntry,
    ReasoningMethodRef,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
)
from ugence_reasoning_method_governance.contracts._util import (
    digest_of,
    require_digest,
    require_member,
    require_nonblank,
    require_str_tuple,
    require_tzaware,
    settle_digest,
)

from .errors import AdvisorError, AdvisorErrorCode

ADVISORY_REQUEST_SCHEMA_VERSION = "reasoning_method.advisory_request.v1"
ADVISORY_SCHEMA_VERSION = "reasoning_method.advisory.v1"
RULE_SET_SCHEMA_VERSION = "reasoning_method.rule_set.v1"
PRIMARY_BASIS_SOLE_QUALIFYING_METHOD = "SOLE_QUALIFYING_METHOD"
EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"

# Synthetic outcomes the evaluator emits for methods no rule reached. Their
# rule_version is the rule set's version, which validate_against_rule_set checks.
SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS = "INADMISSIBLE_IMPLEMENTATION_STATUS"
SYNTHETIC_NO_SUPPORTING_RULE = "NO_SUPPORTING_RULE"
SYNTHETIC_RULE_IDS: FrozenSet[str] = frozenset({SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS, SYNTHETIC_NO_SUPPORTING_RULE})

# Field names no advisory type may declare (slice 1 pattern, widened for advice).
FORBIDDEN_ADVISORY_FIELD_NAMES: FrozenSet[str] = frozenset(
    {
        "score", "scores", "rank", "ranking", "weight", "weights", "priority", "probability",
        "confidence", "likelihood", "cost", "cost_class", "cost_label", "latency", "latency_class",
        "latency_label", "resource_level", "resource_label", "resource_class", "preference",
        "preferred", "expected_quality", "predicted_quality", "outcome_prediction",
    }
)


class _NoScalarLabels:
    """Mixin: refuse subclasses that declare a forbidden field name."""

    def __init_subclass__(cls, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init_subclass__(**kwargs)
        declared = set(getattr(cls, "__annotations__", {}))
        bad = sorted(declared & FORBIDDEN_ADVISORY_FIELD_NAMES)
        if bad:
            raise ContractError(ContractErrorCode.SCALAR_LABEL_FIELD_PRESENT, f"{cls.__name__} declares {', '.join(bad)}")


# --------------------------------------------------------------------------- enums
class RuleKind(str, Enum):
    SUPPORT = "SUPPORT"
    EXCLUDE = "EXCLUDE"


class PredicateKind(str, Enum):
    STRUCTURAL_TOKEN_PRESENT = "STRUCTURAL_TOKEN_PRESENT"
    CONSEQUENCE_CLASS_IN = "CONSEQUENCE_CLASS_IN"
    REVERSIBILITY_IN = "REVERSIBILITY_IN"
    REQUIREMENT_REF_PRESENT = "REQUIREMENT_REF_PRESENT"
    IMPLEMENTATION_STATUS_IN = "IMPLEMENTATION_STATUS_IN"


CATALOG_SIDE_PREDICATES = frozenset({PredicateKind.IMPLEMENTATION_STATUS_IN})


class AdvisoryLabel(str, Enum):
    RULE_DERIVED = "RULE_DERIVED"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"


class NoPrimaryReason(str, Enum):
    NO_QUALIFYING_METHOD = "NO_QUALIFYING_METHOD"
    MULTIPLE_QUALIFYING_METHODS = "MULTIPLE_QUALIFYING_METHODS"


class AdvisoryClassification(str, Enum):
    GOVERNED_TASK_CLASS = "GOVERNED_TASK_CLASS"
    UNCLASSIFIED_EXPLORATORY = "UNCLASSIFIED_EXPLORATORY"


class AdvisoryEligibility(str, Enum):
    JOINABLE_BY_TASK_CLASS_DIGEST = "JOINABLE_BY_TASK_CLASS_DIGEST"
    INELIGIBLE_UNCLASSIFIED = "INELIGIBLE_UNCLASSIFIED"


# --------------------------------------------------------------------------- rules
_VALUE_VOCAB = {
    PredicateKind.CONSEQUENCE_CLASS_IN: frozenset(m.value for m in ConsequenceClass),
    PredicateKind.REVERSIBILITY_IN: frozenset(m.value for m in TaskReversibility),
    PredicateKind.IMPLEMENTATION_STATUS_IN: frozenset(m.value for m in ImplementationStatus),
}


@dataclass(frozen=True)
class Predicate(_NoScalarLabels):
    kind: PredicateKind
    values: Tuple[str, ...]

    def __post_init__(self) -> None:
        require_member(self.kind, PredicateKind, "Predicate.kind", ContractErrorCode.REF_BLANK_FIELD)
        require_str_tuple(self.values, "Predicate.values")
        if not self.values:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "Predicate.values must be non-empty")
        if self.kind is PredicateKind.STRUCTURAL_TOKEN_PRESENT:
            unknown = sorted(set(self.values) - COMPLEXITY_SIGNAL_TOKENS)
            if unknown:
                raise ContractError(ContractErrorCode.SIGNAL_TOKEN_UNKNOWN, f"unknown signal token(s): {', '.join(unknown)}")
        vocab = _VALUE_VOCAB.get(self.kind)
        if vocab is not None:
            unknown = sorted(set(self.values) - vocab)
            if unknown:
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{self.kind.value} value(s) outside vocabulary: {', '.join(unknown)}")

    @property
    def is_catalog_side(self) -> bool:
        return self.kind in CATALOG_SIDE_PREDICATES

    def match_profile(self, profile: TaskProfile) -> Optional[Tuple[str, ...]]:
        """Matched profile coordinates (sorted), or None when the predicate does not match."""
        if self.kind is PredicateKind.STRUCTURAL_TOKEN_PRESENT:
            hit = sorted(set(self.values) & set(profile.structural_characteristics))
            return tuple(hit) or None
        if self.kind is PredicateKind.CONSEQUENCE_CLASS_IN:
            return (profile.consequence_class.value,) if profile.consequence_class.value in self.values else None
        if self.kind is PredicateKind.REVERSIBILITY_IN:
            return (profile.reversibility.value,) if profile.reversibility.value in self.values else None
        if self.kind is PredicateKind.REQUIREMENT_REF_PRESENT:
            refs = set(profile.evidence_requirement_refs) | set(profile.tool_requirement_refs)
            hit = sorted(set(self.values) & refs)
            return tuple(hit) or None
        return None

    def match_entry(self, entry: ReasoningMethodEntry) -> Optional[Tuple[str, ...]]:
        if self.kind is PredicateKind.IMPLEMENTATION_STATUS_IN:
            status = entry.implementation_status.value
            return (status,) if status in self.values else None
        return None


@dataclass(frozen=True)
class Rule(_NoScalarLabels):
    rule_id: str
    rule_version: str
    kind: RuleKind
    predicate: Predicate
    method_ids: Tuple[str, ...]
    rationale_ref: str
    rationale_statement: str

    def __post_init__(self) -> None:
        require_nonblank(self.rule_id, "Rule.rule_id")
        require_nonblank(self.rule_version, "Rule.rule_version")
        require_member(self.kind, RuleKind, "Rule.kind", ContractErrorCode.REF_BLANK_FIELD)
        if not isinstance(self.predicate, Predicate):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "Rule.predicate must be a Predicate")
        require_str_tuple(self.method_ids, "Rule.method_ids")
        if not self.method_ids or len(set(self.method_ids)) != len(self.method_ids):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "Rule.method_ids must be non-empty and unique")
        require_nonblank(self.rationale_ref, "Rule.rationale_ref")
        require_nonblank(self.rationale_statement, "Rule.rationale_statement")


@dataclass(frozen=True)
class RuleSetRef(_NoScalarLabels):
    rule_set_id: str
    rule_set_version: str
    rule_set_digest: str

    def __post_init__(self) -> None:
        require_nonblank(self.rule_set_id, "RuleSetRef.rule_set_id")
        require_nonblank(self.rule_set_version, "RuleSetRef.rule_set_version")
        require_digest(self.rule_set_digest, "RuleSetRef.rule_set_digest")


@dataclass(frozen=True)
class RuleSet(_NoScalarLabels):
    schema_version: str
    rule_set_id: str
    rule_set_version: str
    admissibility: Predicate
    rules: Tuple[Rule, ...]
    provenance_ref: str
    issuer_identity: str
    issued_at: datetime
    rule_set_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "RuleSet.schema_version")
        require_nonblank(self.rule_set_id, "RuleSet.rule_set_id")
        require_nonblank(self.rule_set_version, "RuleSet.rule_set_version")
        if not isinstance(self.admissibility, Predicate) or not self.admissibility.is_catalog_side:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "RuleSet.admissibility must be a catalog-side Predicate (IMPLEMENTATION_STATUS_IN)")
        if not isinstance(self.rules, tuple) or not all(isinstance(r, Rule) for r in self.rules):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "RuleSet.rules must be a tuple of Rule")
        ids = [r.rule_id for r in self.rules]
        if len(set(ids)) != len(ids):
            raise AdvisorError(AdvisorErrorCode.RULE_DUPLICATE_ID, "rule_id values must be unique")
        # Canonical-input rule: ascending rule_id by Unicode code point. Serialization only; never priority.
        if ids != sorted(ids):
            raise AdvisorError(AdvisorErrorCode.RULE_SET_UNSORTED, "RuleSet.rules must be supplied in ascending rule_id order (code point)")
        require_nonblank(self.provenance_ref, "RuleSet.provenance_ref")
        require_nonblank(self.issuer_identity, "RuleSet.issuer_identity")
        require_tzaware(self.issued_at, "RuleSet.issued_at")
        settle_digest(self, "rule_set_digest", digest_of(self, exclude=("rule_set_digest",)))

    def ref(self) -> RuleSetRef:
        return RuleSetRef(self.rule_set_id, self.rule_set_version, self.rule_set_digest)

    def version_of(self, rule_id: str) -> Optional[str]:
        if rule_id in SYNTHETIC_RULE_IDS:
            return self.rule_set_version
        for r in self.rules:
            if r.rule_id == rule_id:
                return r.rule_version
        return None


# --------------------------------------------------------------------------- request
@dataclass(frozen=True)
class ReasoningMethodAdvisoryRequest(_NoScalarLabels):
    schema_version: str
    request_id: str
    profile: TaskProfile
    task_class: Optional[TaskClassIdentity]
    catalog: ReasoningMethodCatalog
    rule_set: RuleSet
    requester_identity: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodAdvisoryRequest.schema_version")
        require_nonblank(self.request_id, "ReasoningMethodAdvisoryRequest.request_id")
        if not isinstance(self.profile, TaskProfile):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "profile must be a TaskProfile")
        if self.task_class is not None:
            if not isinstance(self.task_class, TaskClassIdentity):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "task_class must be a TaskClassIdentity or None")
            missing = sorted(set(self.profile.structural_characteristics) - set(self.task_class.structural_characteristics))
            if missing:
                raise AdvisorError(AdvisorErrorCode.PROFILE_CLASS_MISMATCH, f"task class lacks profile token(s): {', '.join(missing)}")
        if not isinstance(self.catalog, ReasoningMethodCatalog):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "catalog must be a ReasoningMethodCatalog")
        if not isinstance(self.rule_set, RuleSet):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "rule_set must be a RuleSet")
        if not isinstance(self.requester_identity, str):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "requester_identity must be a string")

    def canonical_digest(self) -> str:
        return digest_of(self)


# --------------------------------------------------------------------------- advisory
@dataclass(frozen=True)
class RuleOutcome(_NoScalarLabels):
    rule_id: str
    rule_version: str
    rule_kind: RuleKind
    matched_tokens: Tuple[str, ...]
    rationale_ref: str
    rationale_statement: str

    def __post_init__(self) -> None:
        require_nonblank(self.rule_id, "RuleOutcome.rule_id")
        require_nonblank(self.rule_version, "RuleOutcome.rule_version")
        require_member(self.rule_kind, RuleKind, "RuleOutcome.rule_kind", ContractErrorCode.REF_BLANK_FIELD)
        require_str_tuple(self.matched_tokens, "RuleOutcome.matched_tokens")
        if list(self.matched_tokens) != sorted(self.matched_tokens):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "RuleOutcome.matched_tokens must be sorted")
        require_nonblank(self.rationale_ref, "RuleOutcome.rationale_ref")
        require_nonblank(self.rationale_statement, "RuleOutcome.rationale_statement")


def _outcomes(value: object, name: str, minimum: int) -> None:
    if not isinstance(value, tuple) or not all(isinstance(o, RuleOutcome) for o in value):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a tuple of RuleOutcome")
    if len(value) < minimum:
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must carry at least {minimum} reason(s)")
    ids = [o.rule_id for o in value]
    if ids != sorted(ids):
        raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be ordered by rule_id")


@dataclass(frozen=True)
class QualifyingTradeOff(_NoScalarLabels):
    method: ReasoningMethodRef
    distinguishing_reasons: Tuple[RuleOutcome, ...]
    distinguishing_requirement_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualifyingTradeOff.method must be a ReasoningMethodRef")
        _outcomes(self.distinguishing_reasons, "QualifyingTradeOff.distinguishing_reasons", 0)
        require_str_tuple(self.distinguishing_requirement_refs, "QualifyingTradeOff.distinguishing_requirement_refs")
        if list(self.distinguishing_requirement_refs) != sorted(self.distinguishing_requirement_refs):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "distinguishing_requirement_refs must be sorted")


@dataclass(frozen=True)
class QualifyingMethod(_NoScalarLabels):
    method: ReasoningMethodRef
    label: AdvisoryLabel
    inclusion_reasons: Tuple[RuleOutcome, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualifyingMethod.method must be a ReasoningMethodRef")
        require_member(self.label, AdvisoryLabel, "QualifyingMethod.label", ContractErrorCode.REF_BLANK_FIELD)
        _outcomes(self.inclusion_reasons, "QualifyingMethod.inclusion_reasons", 1)


@dataclass(frozen=True)
class ExcludedMethod(_NoScalarLabels):
    method: ReasoningMethodRef
    label: AdvisoryLabel
    exclusion_reasons: Tuple[RuleOutcome, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "ExcludedMethod.method must be a ReasoningMethodRef")
        require_member(self.label, AdvisoryLabel, "ExcludedMethod.label", ContractErrorCode.REF_BLANK_FIELD)
        _outcomes(self.exclusion_reasons, "ExcludedMethod.exclusion_reasons", 1)


@dataclass(frozen=True)
class ReasoningMethodAdvisory(_NoScalarLabels):
    schema_version: str
    advisory_id: str
    request_digest: str
    profile_digest: str
    task_class_digest: Optional[str]
    catalog: ReasoningMethodCatalogRef
    rule_set: RuleSetRef
    classification: AdvisoryClassification
    eligibility: AdvisoryEligibility
    qualifying: Tuple[QualifyingMethod, ...]
    excluded: Tuple[ExcludedMethod, ...]
    trade_offs: Tuple[QualifyingTradeOff, ...]
    primary: Optional[ReasoningMethodRef]
    primary_basis: Optional[str]
    no_primary_reason: Optional[NoPrimaryReason]
    evidence_status: str
    usage_scope: str
    advisor_identity: str
    advisor_version: str
    advised_at: datetime
    advisory_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "ReasoningMethodAdvisory.schema_version")
        require_nonblank(self.advisory_id, "ReasoningMethodAdvisory.advisory_id")
        require_digest(self.request_digest, "ReasoningMethodAdvisory.request_digest")
        require_digest(self.profile_digest, "ReasoningMethodAdvisory.profile_digest")
        if self.task_class_digest is not None:
            require_digest(self.task_class_digest, "ReasoningMethodAdvisory.task_class_digest")
        if not isinstance(self.catalog, ReasoningMethodCatalogRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "catalog must be a ReasoningMethodCatalogRef")
        if not isinstance(self.rule_set, RuleSetRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "rule_set must be a RuleSetRef")
        require_member(self.classification, AdvisoryClassification, "classification", ContractErrorCode.REF_BLANK_FIELD)
        require_member(self.eligibility, AdvisoryEligibility, "eligibility", ContractErrorCode.REF_BLANK_FIELD)
        # Unclassified-request restriction (owner ruling, binding).
        governed = self.task_class_digest is not None
        if governed != (self.classification is AdvisoryClassification.GOVERNED_TASK_CLASS):
            raise AdvisorError(AdvisorErrorCode.CLASSIFICATION_INCONSISTENT, "classification must be GOVERNED_TASK_CLASS iff a task_class_digest is present")
        expected_elig = AdvisoryEligibility.JOINABLE_BY_TASK_CLASS_DIGEST if governed else AdvisoryEligibility.INELIGIBLE_UNCLASSIFIED
        if self.eligibility is not expected_elig:
            raise AdvisorError(AdvisorErrorCode.CLASSIFICATION_INCONSISTENT, f"eligibility must be {expected_elig.value} for this classification")
        for name, cls in (("qualifying", QualifyingMethod), ("excluded", ExcludedMethod), ("trade_offs", QualifyingTradeOff)):
            v = getattr(self, name)
            if not isinstance(v, tuple) or not all(isinstance(x, cls) for x in v):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be a tuple of {cls.__name__}")
            keys = [x.method.sort_key for x in v]
            if keys != sorted(keys) or len(set(keys)) != len(keys):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"{name} must be ordered by (method_id, method_version) without repeats")
        if {q.method for q in self.qualifying} & {e.method for e in self.excluded}:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "a method cannot be both qualifying and excluded")
        if any(q.label is not AdvisoryLabel.RULE_DERIVED for q in self.qualifying) or any(e.label is not AdvisoryLabel.RULE_DERIVED for e in self.excluded):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "every slice 2 inclusion and exclusion is RULE_DERIVED")
        n = len(self.qualifying)
        # Primary iff exactly one method qualifies (no-forced-winner rule).
        if self.primary is not None:
            if n != 1 or self.primary != self.qualifying[0].method or self.primary_basis != PRIMARY_BASIS_SOLE_QUALIFYING_METHOD or self.no_primary_reason is not None:
                raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, "primary may be set only when exactly one method qualifies, with basis SOLE_QUALIFYING_METHOD and no no_primary_reason")
        else:
            if n == 1:
                raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, "exactly one method qualifies but no primary is set")
            if self.primary_basis is not None:
                raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, "primary_basis without a primary")
            expected = NoPrimaryReason.NO_QUALIFYING_METHOD if n == 0 else NoPrimaryReason.MULTIPLE_QUALIFYING_METHODS
            if self.no_primary_reason is not expected:
                raise AdvisorError(AdvisorErrorCode.PRIMARY_WITHOUT_SOLE_QUALIFIER, f"no_primary_reason must be {expected.value}")
        # Trade-off cardinality.
        if n <= 1:
            if self.trade_offs:
                raise AdvisorError(AdvisorErrorCode.TRADE_OFF_CARDINALITY, "trade_offs must be empty when zero or one method qualifies")
        else:
            if [t.method for t in self.trade_offs] != [q.method for q in self.qualifying]:
                raise AdvisorError(AdvisorErrorCode.TRADE_OFF_CARDINALITY, "exactly one trade-off per qualifying method, in qualifying order, and none for an excluded method")
        if self.evidence_status != EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"evidence_status is fixed at {EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT} in slice 2")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"usage_scope is fixed at {USAGE_SCOPE_RESEARCH_ONLY} in slice 2")
        require_nonblank(self.advisor_identity, "advisor_identity")
        require_nonblank(self.advisor_version, "advisor_version")
        require_tzaware(self.advised_at, "advised_at")
        settle_digest(self, "advisory_digest", digest_of(self, exclude=("advisory_digest",)))


def validate_against_rule_set(advisory: ReasoningMethodAdvisory, rule_set: RuleSet) -> None:
    """Every RuleOutcome.rule_version must equal the admitted rule's version.

    Synthetic outcomes carry the rule set's version. Raises
    RULE_OUTCOME_VERSION_MISMATCH otherwise; also refuses an advisory that
    names a different rule set.
    """
    if advisory.rule_set != rule_set.ref():
        raise AdvisorError(AdvisorErrorCode.RULE_OUTCOME_VERSION_MISMATCH, "advisory names a different rule set")
    outcomes = [o for q in advisory.qualifying for o in q.inclusion_reasons]
    outcomes += [o for e in advisory.excluded for o in e.exclusion_reasons]
    outcomes += [o for t in advisory.trade_offs for o in t.distinguishing_reasons]
    for o in outcomes:
        expected = rule_set.version_of(o.rule_id)
        if expected is None or o.rule_version != expected:
            raise AdvisorError(AdvisorErrorCode.RULE_OUTCOME_VERSION_MISMATCH, f"outcome {o.rule_id} carries version {o.rule_version!r}; admitted rule set has {expected!r}")


__all__ = [
    "ADVISORY_REQUEST_SCHEMA_VERSION", "ADVISORY_SCHEMA_VERSION", "RULE_SET_SCHEMA_VERSION",
    "PRIMARY_BASIS_SOLE_QUALIFYING_METHOD", "EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT",
    "SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS", "SYNTHETIC_NO_SUPPORTING_RULE", "SYNTHETIC_RULE_IDS",
    "FORBIDDEN_ADVISORY_FIELD_NAMES", "CATALOG_SIDE_PREDICATES",
    "RuleKind", "PredicateKind", "AdvisoryLabel", "NoPrimaryReason", "AdvisoryClassification", "AdvisoryEligibility",
    "Predicate", "Rule", "RuleSetRef", "RuleSet", "ReasoningMethodAdvisoryRequest",
    "RuleOutcome", "QualifyingTradeOff", "QualifyingMethod", "ExcludedMethod", "ReasoningMethodAdvisory",
    "validate_against_rule_set",
]
