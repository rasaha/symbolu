"""Curated public API of ugence-reasoning-method-advisor (slice 2)."""

from .advisor import ADVISOR_IDENTITY, TraversalOrder, advise
from .contracts import (
    ADVISORY_REQUEST_SCHEMA_VERSION,
    ADVISORY_SCHEMA_VERSION,
    CATALOG_SIDE_PREDICATES,
    EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT,
    FORBIDDEN_ADVISORY_FIELD_NAMES,
    PRIMARY_BASIS_SOLE_QUALIFYING_METHOD,
    RULE_SET_SCHEMA_VERSION,
    SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS,
    SYNTHETIC_NO_SUPPORTING_RULE,
    SYNTHETIC_RULE_IDS,
    AdvisoryClassification,
    AdvisoryEligibility,
    AdvisoryLabel,
    ExcludedMethod,
    NoPrimaryReason,
    Predicate,
    PredicateKind,
    QualifyingMethod,
    QualifyingTradeOff,
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryRequest,
    Rule,
    RuleKind,
    RuleOutcome,
    RuleSet,
    RuleSetRef,
    validate_against_request,
    validate_against_rule_set,
)
from .errors import AdvisorError, AdvisorErrorCode
from .version import __version__

__all__ = [
    "__version__", "ADVISOR_IDENTITY", "TraversalOrder", "advise",
    "ADVISORY_REQUEST_SCHEMA_VERSION", "ADVISORY_SCHEMA_VERSION", "RULE_SET_SCHEMA_VERSION",
    "PRIMARY_BASIS_SOLE_QUALIFYING_METHOD", "EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT",
    "SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS", "SYNTHETIC_NO_SUPPORTING_RULE", "SYNTHETIC_RULE_IDS",
    "FORBIDDEN_ADVISORY_FIELD_NAMES", "CATALOG_SIDE_PREDICATES",
    "RuleKind", "PredicateKind", "AdvisoryLabel", "NoPrimaryReason", "AdvisoryClassification", "AdvisoryEligibility",
    "Predicate", "Rule", "RuleSetRef", "RuleSet", "ReasoningMethodAdvisoryRequest",
    "RuleOutcome", "QualifyingTradeOff", "QualifyingMethod", "ExcludedMethod", "ReasoningMethodAdvisory",
    "validate_against_rule_set", "validate_against_request", "AdvisorError", "AdvisorErrorCode",
]
