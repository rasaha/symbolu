"""``advise(request) -> advisory``: the slice 2 evaluator (specification §4).

A pure function of ``(profile, task_class, catalog, rule_set)``. Internal
traversal order over rules, catalog entries and qualifying methods never
affects any output; a test-only ``TraversalOrder`` hook lets the suite prove
it (§7, P11). No I/O, no clock, no numbers: ``advised_at`` is a required,
timezone-aware, caller-supplied instant that enters ``advisory_digest``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple, TypeVar

from ugence_reasoning_method_governance.api import USAGE_SCOPE_RESEARCH_ONLY, ReasoningMethodEntry, ReasoningMethodRef

from ._canon import digest_of, require_tzaware
from .contracts import (
    ADVISORY_SCHEMA_VERSION,
    EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT,
    PRIMARY_BASIS_SOLE_QUALIFYING_METHOD,
    SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS,
    SYNTHETIC_NO_SUPPORTING_RULE,
    AdvisoryClassification,
    AdvisoryEligibility,
    AdvisoryLabel,
    ExcludedMethod,
    NoPrimaryReason,
    QualifyingMethod,
    QualifyingTradeOff,
    ReasoningMethodAdvisory,
    ReasoningMethodAdvisoryRequest,
    RuleKind,
    RuleOutcome,
    validate_against_request,
    validate_against_rule_set,
)
from .errors import AdvisorError, AdvisorErrorCode
from .version import __version__

ADVISOR_IDENTITY = "ugence-reasoning-method-advisor"

T = TypeVar("T")
_Order = Callable[[Sequence[T]], Sequence[T]]


@dataclass(frozen=True)
class TraversalOrder:
    """Test-only hook: permutes the evaluator's internal traversal of rules,
    catalog entries and qualifying methods. Outputs must not change."""

    rules: Optional[_Order] = None
    entries: Optional[_Order] = None
    qualifying: Optional[_Order] = None


def _order(hook: Optional[_Order], seq: Sequence[T]) -> Sequence[T]:
    return list(seq) if hook is None else list(hook(list(seq)))


def advise(
    request: ReasoningMethodAdvisoryRequest,
    *,
    advised_at: datetime,
    _traversal: Optional[TraversalOrder] = None,
) -> ReasoningMethodAdvisory:
    if not isinstance(request, ReasoningMethodAdvisoryRequest):
        raise TypeError("advise() takes a ReasoningMethodAdvisoryRequest")
    require_tzaware(advised_at, "advised_at")
    tr = _traversal or TraversalOrder()
    catalog, rule_set, profile = request.catalog, request.rule_set, request.profile
    entries: Dict[str, ReasoningMethodEntry] = {e.method_id: e for e in catalog.entries}
    catalog_ref = catalog.ref()

    def ref_of(entry: ReasoningMethodEntry) -> ReasoningMethodRef:
        return ReasoningMethodRef(catalog_ref, entry.method_id, entry.method_version)

    # Every rule must name only catalog methods (RULE_METHOD_UNKNOWN), regardless of firing.
    for rule in rule_set.rules:
        for mid in rule.method_ids:
            if mid not in entries:
                raise AdvisorError(AdvisorErrorCode.RULE_METHOD_UNKNOWN, f"rule {rule.rule_id} names method {mid!r} absent from the catalog")

    # 1. Admissible set A and synthetic exclusions for the rest.
    admissible: Dict[str, ReasoningMethodEntry] = {}
    exclusions: Dict[str, List[RuleOutcome]] = {}
    inclusions: Dict[str, List[RuleOutcome]] = {}
    for entry in _order(tr.entries, list(catalog.entries)):
        matched = rule_set.admissibility.match_entry(entry)
        if matched is None:
            exclusions.setdefault(entry.method_id, []).append(
                RuleOutcome(
                    SYNTHETIC_INADMISSIBLE_IMPLEMENTATION_STATUS,
                    rule_set.rule_set_version,
                    RuleKind.EXCLUDE,
                    (entry.implementation_status.value,),
                    f"rule_set:{rule_set.rule_set_id}:{rule_set.rule_set_version}:admissibility",
                    "implementation status does not satisfy the rule set's admissibility gate",
                )
            )
        else:
            admissible[entry.method_id] = entry

    # 2. Rule outcomes over A. Set semantics: order of application is irrelevant.
    for rule in _order(tr.rules, list(rule_set.rules)):
        for mid in rule.method_ids:
            if mid not in admissible:
                continue
            matched = rule.predicate.match_entry(admissible[mid]) if rule.predicate.is_catalog_side else rule.predicate.match_profile(profile)
            if matched is None:
                continue
            outcome = RuleOutcome(rule.rule_id, rule.rule_version, rule.kind, tuple(matched), rule.rationale_ref, rule.rationale_statement)
            (inclusions if rule.kind is RuleKind.SUPPORT else exclusions).setdefault(mid, []).append(outcome)

    # 3. Qualifying set Q and exclusions.
    qualifying_ids: Set[str] = {mid for mid in admissible if mid in inclusions and mid not in exclusions}
    for mid in admissible:
        if mid in qualifying_ids:
            continue
        if mid not in exclusions:
            exclusions[mid] = [
                RuleOutcome(
                    SYNTHETIC_NO_SUPPORTING_RULE,
                    rule_set.rule_set_version,
                    RuleKind.EXCLUDE,
                    (),
                    f"rule_set:{rule_set.rule_set_id}:{rule_set.rule_set_version}",
                    "no SUPPORT rule in the admitted rule set reached this method for this profile",
                )
            ]

    def sorted_outcomes(items: List[RuleOutcome]) -> Tuple[RuleOutcome, ...]:
        return tuple(sorted(items, key=lambda o: o.rule_id))

    qualifying = tuple(
        QualifyingMethod(ref_of(entries[mid]), AdvisoryLabel.RULE_DERIVED, sorted_outcomes(inclusions[mid]))
        for mid in sorted(qualifying_ids, key=lambda m: entries[m].sort_key)
    )
    excluded = tuple(
        ExcludedMethod(ref_of(entries[mid]), AdvisoryLabel.RULE_DERIVED, sorted_outcomes(exclusions[mid]))
        for mid in sorted(exclusions, key=lambda m: entries[m].sort_key)
    )

    # 4. Trade-offs when more than one qualifies: set differences, never preferences.
    trade_offs: Tuple[QualifyingTradeOff, ...] = ()
    if len(qualifying) > 1:
        built: Dict[str, QualifyingTradeOff] = {}
        for q in _order(tr.qualifying, list(qualifying)):
            others = [o for o in qualifying if o.method != q.method]
            other_rule_ids = {r.rule_id for o in others for r in o.inclusion_reasons}
            other_refs = {ref for o in others for ref in entries[o.method.method_id].requirement_refs}
            built[q.method.method_id] = QualifyingTradeOff(
                q.method,
                tuple(r for r in q.inclusion_reasons if r.rule_id not in other_rule_ids),
                tuple(sorted(set(entries[q.method.method_id].requirement_refs) - other_refs)),
            )
        trade_offs = tuple(built[q.method.method_id] for q in qualifying)

    n = len(qualifying)
    primary = qualifying[0].method if n == 1 else None
    governed = request.task_class is not None
    advisory = ReasoningMethodAdvisory(
        schema_version=ADVISORY_SCHEMA_VERSION,
        advisory_id=f"{request.request_id}:advisory",
        request_digest=request.canonical_digest(),
        profile_digest=digest_of(profile),
        task_class_digest=request.task_class.task_class_digest if governed else None,
        catalog=catalog_ref,
        rule_set=rule_set.ref(),
        classification=AdvisoryClassification.GOVERNED_TASK_CLASS if governed else AdvisoryClassification.UNCLASSIFIED_EXPLORATORY,
        eligibility=AdvisoryEligibility.JOINABLE_BY_TASK_CLASS_DIGEST if governed else AdvisoryEligibility.INELIGIBLE_UNCLASSIFIED,
        qualifying=qualifying,
        excluded=excluded,
        trade_offs=trade_offs,
        primary=primary,
        primary_basis=PRIMARY_BASIS_SOLE_QUALIFYING_METHOD if primary is not None else None,
        no_primary_reason=None if primary is not None else (NoPrimaryReason.NO_QUALIFYING_METHOD if n == 0 else NoPrimaryReason.MULTIPLE_QUALIFYING_METHODS),
        evidence_status=EVIDENCE_STATUS_COMPARISON_EVIDENCE_ABSENT,
        usage_scope=USAGE_SCOPE_RESEARCH_ONLY,
        advisor_identity=ADVISOR_IDENTITY,
        advisor_version=__version__,
        advised_at=advised_at,
    )
    validate_against_rule_set(advisory, rule_set)
    validate_against_request(advisory, request)
    return advisory


__all__ = ["ADVISOR_IDENTITY", "TraversalOrder", "advise"]
