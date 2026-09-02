"""§6.2 Neutral research-only lifecycle: five states, closed transitions enforced by
pure operations, one-way lineage, derived revision scope."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple

from ugence_reasoning_method_governance.api import ContractError, ContractErrorCode, FitOutcome, ReadinessComparisonResult, ReasoningMethodRef, USAGE_SCOPE_RESEARCH_ONLY

from .._canon import digest_of, require_digest, require_member, require_nonblank, require_str_tuple, require_tzaware, settle_digest
from ..errors import PilotError, PilotErrorCode
from .manifest import PilotRole, PilotStudyManifest, sorted_roles

PILOT_STATE_SCHEMA_VERSION = "workflow_fit_pilot.state.v1"
APPROVAL_STATUS_NONE = "NONE"


class PilotConfigurationState(str, Enum):
    PROPOSED = "PROPOSED"
    UNDER_TEST = "UNDER_TEST"
    EVALUATED = "EVALUATED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REVISED = "REVISED"


class RevisionScope(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    TASK_CLASS = "TASK_CLASS"
    BENCHMARK_MANIFEST = "BENCHMARK_MANIFEST"
    COMPARISON_PLAN = "COMPARISON_PLAN"
    SUFFICIENCY_RULE = "SUFFICIENCY_RULE"
    ADVICE = "ADVICE"
    EVALUATOR = "EVALUATOR"
    CAPTURE_BOUNDARY = "CAPTURE_BOUNDARY"
    AGGREGATION = "AGGREGATION"


_SCOPE_ORDER = tuple(RevisionScope)


class LifecycleEvent(str, Enum):
    OBSERVATION_VALIDATED = "OBSERVATION_VALIDATED"
    RESULT_ASSESSED = "RESULT_ASSESSED"
    RESULT_INCONCLUSIVE = "RESULT_INCONCLUSIVE"
    SUPERSEDED = "SUPERSEDED"


_ASSESSED = frozenset({FitOutcome.INSUFFICIENT_QUALITY, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED, FitOutcome.SUFFICIENT_PARETO_EFFICIENT})


def comparison_request_id(manifest_digest: str) -> str:
    """The request id the runner gives the engine request for a manifest; results are bound
    to their manifest through it."""
    return f"pilot:{manifest_digest}:comparison"


def derive_revision_scope(predecessor: PilotStudyManifest, successor: PilotStudyManifest) -> Tuple[RevisionScope, ...]:
    """Pure. Every manifest coordinate is covered by some scope."""
    a, b = predecessor, successor
    scopes = set()
    if a.plan.binding != b.plan.binding:
        scopes.add(RevisionScope.CONFIGURATION)
    if a.plan.task_class.task_class_digest != b.plan.task_class.task_class_digest:
        scopes.add(RevisionScope.TASK_CLASS)
    if a.benchmark.benchmark_manifest_digest != b.benchmark.benchmark_manifest_digest:
        scopes.add(RevisionScope.BENCHMARK_MANIFEST)
    ra, rb = a.plan.task_class.comparison_policy.sufficiency, b.plan.task_class.comparison_policy.sufficiency
    if (ra.rule_id, ra.rule_version) != (rb.rule_id, rb.rule_version):
        scopes.add(RevisionScope.SUFFICIENCY_RULE)
    masked = ("baseline", "recommended", "challengers", "catalog", "preregistered_by", "preregistered_at", "plan_id", "schema_version", "usage_scope")
    if any(getattr(a.plan, f) != getattr(b.plan, f) for f in masked):
        scopes.add(RevisionScope.COMPARISON_PLAN)
    if a.advisory_digest != b.advisory_digest or a.rule_set != b.rule_set or a.methods != b.methods:
        scopes.add(RevisionScope.ADVICE)
    if a.evaluator.declaration_digest != b.evaluator.declaration_digest:
        scopes.add(RevisionScope.EVALUATOR)
    if a.capture_boundary != b.capture_boundary:
        scopes.add(RevisionScope.CAPTURE_BOUNDARY)
    if a.resource_aggregation != b.resource_aggregation or a.quality_aggregation != b.quality_aggregation:
        scopes.add(RevisionScope.AGGREGATION)
    if not scopes:
        if a.manifest_digest != b.manifest_digest:
            scopes.add(RevisionScope.COMPARISON_PLAN)  # identity fields only (manifest_id etc.); still a new preregistration
        else:
            raise PilotError(PilotErrorCode.REVISION_WITHOUT_CHANGE, "successor manifest does not differ from the predecessor")
    return tuple(sorted(scopes, key=_SCOPE_ORDER.index))


@dataclass(frozen=True)
class PilotConfigurationStateRecord:
    schema_version: str
    manifest_digest: str
    method: ReasoningMethodRef
    roles: Tuple[PilotRole, ...]
    state: PilotConfigurationState
    fit_outcome: Optional[FitOutcome]
    refusal_codes: Tuple[str, ...]
    result_digest: Optional[str]
    predecessor_state_digest: Optional[str]
    predecessor_manifest_digest: Optional[str]
    successor_manifest_digest: Optional[str]
    revision_scope: Tuple[RevisionScope, ...]
    usage_scope: str
    approval_status: str
    recorded_by: str
    recorded_at: datetime
    state_digest: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != PILOT_STATE_SCHEMA_VERSION:
            raise PilotError(PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED, f"PilotConfigurationStateRecord.schema_version must be {PILOT_STATE_SCHEMA_VERSION}")
        require_digest(self.manifest_digest, "PilotConfigurationStateRecord.manifest_digest")
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "method must be a ReasoningMethodRef")
        if not isinstance(self.roles, tuple) or not self.roles or self.roles != sorted_roles(self.roles):
            raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "roles must be a non-empty member-ordered tuple")
        require_member(self.state, PilotConfigurationState, "state", ContractErrorCode.REF_BLANK_FIELD)
        if self.fit_outcome is not None:
            require_member(self.fit_outcome, FitOutcome, "fit_outcome", ContractErrorCode.REF_BLANK_FIELD)
        require_str_tuple(self.refusal_codes, "refusal_codes")
        for name in ("result_digest", "predecessor_state_digest", "predecessor_manifest_digest", "successor_manifest_digest"):
            v = getattr(self, name)
            if v is not None:
                require_digest(v, name)
        if not isinstance(self.revision_scope, tuple) or not all(isinstance(s, RevisionScope) for s in self.revision_scope) or list(self.revision_scope) != sorted(set(self.revision_scope), key=_SCOPE_ORDER.index):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "revision_scope must be a member-ordered tuple without repeats")
        st = self.state
        if st is PilotConfigurationState.EVALUATED:
            if self.fit_outcome not in _ASSESSED or self.result_digest is None or self.refusal_codes:
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "EVALUATED requires one of the three assessed outcomes, a result digest and no refusal codes")
        elif st is PilotConfigurationState.INCONCLUSIVE:
            if self.fit_outcome not in (None, FitOutcome.COMPARISON_EVIDENCE_ABSENT) or (self.fit_outcome is None and not self.refusal_codes):
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "INCONCLUSIVE carries COMPARISON_EVIDENCE_ABSENT or a refusal code")
        else:
            if self.fit_outcome is not None or self.result_digest is not None or self.refusal_codes:
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"{st.value} carries no outcome, result or refusal")
        if st is PilotConfigurationState.REVISED:
            if self.successor_manifest_digest is None or not self.revision_scope:
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "REVISED names its successor manifest and a non-empty revision scope")
        elif self.successor_manifest_digest is not None:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "only a REVISED record names a successor manifest")
        if st is PilotConfigurationState.PROPOSED:
            if (self.predecessor_manifest_digest is None) != (not self.revision_scope):
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "a successor's PROPOSED record carries the predecessor manifest and the revision scope together")
        elif st is not PilotConfigurationState.REVISED and self.revision_scope:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "only PROPOSED (successor) and REVISED records carry a revision scope")
        if st is not PilotConfigurationState.PROPOSED and self.predecessor_state_digest is None:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"{st.value} must follow a predecessor record")
        if st is not PilotConfigurationState.PROPOSED and self.predecessor_manifest_digest is not None:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "only a PROPOSED record names a predecessor manifest")
        if self.usage_scope != USAGE_SCOPE_RESEARCH_ONLY or self.approval_status != APPROVAL_STATUS_NONE:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "usage_scope and approval_status are constants")
        require_nonblank(self.recorded_by, "recorded_by")
        require_tzaware(self.recorded_at, "recorded_at")
        settle_digest(self, "state_digest", digest_of(self, exclude=("state_digest",)))


def propose(manifest: PilotStudyManifest, method: ReasoningMethodRef, *, recorded_by: str, recorded_at: datetime, predecessor: Optional[PilotConfigurationStateRecord] = None, predecessor_manifest: Optional[PilotStudyManifest] = None) -> PilotConfigurationStateRecord:
    """The only way to produce a PROPOSED record. With a predecessor manifest, carries the
    derived manifest-level revision scope and, when the method existed before, the REVISED
    record's digest."""
    assignment = manifest.assignment(method)
    if assignment is None:
        raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "method is not assigned in the manifest")
    scope: Tuple[RevisionScope, ...] = ()
    pred_state = None
    pred_manifest = None
    if predecessor_manifest is not None:
        scope = derive_revision_scope(predecessor_manifest, manifest)
        pred_manifest = predecessor_manifest.manifest_digest
        if predecessor is not None:
            if predecessor.state is not PilotConfigurationState.REVISED or predecessor.method != method or predecessor.manifest_digest != pred_manifest or predecessor.successor_manifest_digest != manifest.manifest_digest:
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "a successor PROPOSED record follows the same method's REVISED record naming this manifest")
            pred_state = predecessor.state_digest
    elif predecessor is not None:
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "a predecessor record requires the predecessor manifest")
    return PilotConfigurationStateRecord(
        PILOT_STATE_SCHEMA_VERSION, manifest.manifest_digest, method, assignment.roles, PilotConfigurationState.PROPOSED,
        None, (), None, pred_state, pred_manifest, None, scope, USAGE_SCOPE_RESEARCH_ONLY, APPROVAL_STATUS_NONE, recorded_by, recorded_at,
    )


def transition(
    predecessor: PilotConfigurationStateRecord,
    event: LifecycleEvent,
    *,
    manifest: PilotStudyManifest,
    successor_manifest: Optional[PilotStudyManifest] = None,
    result: Optional[ReadinessComparisonResult] = None,
    capture_refusal: Optional[str] = None,
    recorded_by: str,
    recorded_at: datetime,
) -> PilotConfigurationStateRecord:
    """Pure. The only way to produce a non-PROPOSED record."""
    if not isinstance(predecessor, PilotConfigurationStateRecord) or not isinstance(manifest, PilotStudyManifest):
        raise TypeError("transition(predecessor, event, *, manifest, ...)")
    if predecessor.manifest_digest != manifest.manifest_digest:
        raise PilotError(PilotErrorCode.MANIFEST_MISMATCH, "predecessor record belongs to another manifest")
    st = predecessor.state
    if st is PilotConfigurationState.REVISED:
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "a REVISED record is terminal")
    common = dict(schema_version=PILOT_STATE_SCHEMA_VERSION, manifest_digest=manifest.manifest_digest, method=predecessor.method, roles=predecessor.roles,
                  predecessor_state_digest=predecessor.state_digest, predecessor_manifest_digest=None, usage_scope=USAGE_SCOPE_RESEARCH_ONLY, approval_status=APPROVAL_STATUS_NONE,
                  recorded_by=recorded_by, recorded_at=recorded_at)
    if event is LifecycleEvent.SUPERSEDED:
        if successor_manifest is None:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "SUPERSEDED requires the successor manifest")
        scope = derive_revision_scope(manifest, successor_manifest)
        return PilotConfigurationStateRecord(state=PilotConfigurationState.REVISED, fit_outcome=None, refusal_codes=(), result_digest=None,
                                             successor_manifest_digest=successor_manifest.manifest_digest, revision_scope=scope, **common)
    if event is LifecycleEvent.OBSERVATION_VALIDATED:
        if st is not PilotConfigurationState.PROPOSED:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"OBSERVATION_VALIDATED is not permitted from {st.value}")
        return PilotConfigurationStateRecord(state=PilotConfigurationState.UNDER_TEST, fit_outcome=None, refusal_codes=(), result_digest=None,
                                             successor_manifest_digest=None, revision_scope=(), **common)
    if st is not PilotConfigurationState.UNDER_TEST and not (st is PilotConfigurationState.PROPOSED and event is LifecycleEvent.RESULT_INCONCLUSIVE and capture_refusal):
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"{event.value} is not permitted from {st.value}")
    if event is LifecycleEvent.RESULT_INCONCLUSIVE and capture_refusal:
        return PilotConfigurationStateRecord(state=PilotConfigurationState.INCONCLUSIVE, fit_outcome=None, refusal_codes=(capture_refusal,), result_digest=None,
                                             successor_manifest_digest=None, revision_scope=(), **common)
    if result is None or not isinstance(result, ReadinessComparisonResult):
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"{event.value} requires the ReadinessComparisonResult")
    outcome = next((a.outcome for a in result.assessments if a.method == predecessor.method), None)
    refusals = tuple(sorted(r.code.value for r in result.refusals if r.method is None or r.method == predecessor.method))
    if event is LifecycleEvent.RESULT_ASSESSED:
        if outcome not in _ASSESSED:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "RESULT_ASSESSED requires one of the three assessed outcomes for this method")
        return PilotConfigurationStateRecord(state=PilotConfigurationState.EVALUATED, fit_outcome=outcome, refusal_codes=(), result_digest=result.result_digest,
                                             successor_manifest_digest=None, revision_scope=(), **common)
    if outcome in _ASSESSED:
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "RESULT_INCONCLUSIVE is not permitted when the method was assessed")
    if outcome is None and not refusals:
        raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "RESULT_INCONCLUSIVE requires COMPARISON_EVIDENCE_ABSENT or a refusal for this method")
    return PilotConfigurationStateRecord(state=PilotConfigurationState.INCONCLUSIVE, fit_outcome=outcome, refusal_codes=refusals, result_digest=result.result_digest,
                                         successor_manifest_digest=None, revision_scope=(), **common)


_PERMITTED = {
    (PilotConfigurationState.PROPOSED, PilotConfigurationState.UNDER_TEST),
    (PilotConfigurationState.PROPOSED, PilotConfigurationState.INCONCLUSIVE),
    (PilotConfigurationState.UNDER_TEST, PilotConfigurationState.EVALUATED),
    (PilotConfigurationState.UNDER_TEST, PilotConfigurationState.INCONCLUSIVE),
    (PilotConfigurationState.PROPOSED, PilotConfigurationState.REVISED),
    (PilotConfigurationState.UNDER_TEST, PilotConfigurationState.REVISED),
    (PilotConfigurationState.EVALUATED, PilotConfigurationState.REVISED),
    (PilotConfigurationState.INCONCLUSIVE, PilotConfigurationState.REVISED),
}


def validate_lineage(records: Iterable[PilotConfigurationStateRecord], manifests: Iterable[PilotStudyManifest], results: Iterable[ReadinessComparisonResult] = ()) -> None:
    """Replays every chain and refuses a record no permitted transition produces, a
    revision scope that differs from the derivation, an incomplete supersession, or an
    EVALUATED / INCONCLUSIVE record whose named engine result is not supplied or does not
    give this method the recorded outcome and refusals. A state can therefore not be
    reached by hand-building a record around a fabricated result digest."""
    recs = list(records)
    by_digest: Dict[str, PilotConfigurationStateRecord] = {r.state_digest: r for r in recs}
    mans: Dict[str, PilotStudyManifest] = {m.manifest_digest: m for m in manifests}
    ress: Dict[str, ReadinessComparisonResult] = {x.result_digest: x for x in results}
    for r in recs:
        if r.manifest_digest not in mans:
            raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, "record names an unsupplied manifest")
        if r.result_digest is not None:
            res = ress.get(r.result_digest)
            if res is None:
                raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, f"{r.state.value} record names an unsupplied engine result")
            man = mans[r.manifest_digest]
            # The result must be THIS manifest's: the runner names the manifest in the request id, and
            # every assessment carries the task class and binding the manifest preregistered.
            if res.request_id != comparison_request_id(man.manifest_digest):
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "engine result does not belong to this manifest")
            for a in res.assessments:
                if a.task_class_digest != man.plan.task_class.task_class_digest or a.binding_digest != man.plan.binding.binding_digest:
                    raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "engine result assesses another task class or binding")
            outcome = next((a.outcome for a in res.assessments if a.method == r.method), None)
            refusals = tuple(sorted(x.code.value for x in res.refusals if x.method is None or x.method == r.method))
            if r.state is PilotConfigurationState.EVALUATED and outcome != r.fit_outcome:
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "EVALUATED outcome differs from the engine result for this method")
            if r.state is PilotConfigurationState.INCONCLUSIVE and (outcome != r.fit_outcome or refusals != r.refusal_codes):
                raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "INCONCLUSIVE outcome or refusals differ from the engine result for this method")
        elif r.state is PilotConfigurationState.EVALUATED:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, "EVALUATED requires an engine result")
        if r.state is PilotConfigurationState.PROPOSED:
            if r.predecessor_manifest_digest is not None:
                pm = mans.get(r.predecessor_manifest_digest)
                if pm is None:
                    raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, "successor PROPOSED names an unsupplied predecessor manifest")
                if r.revision_scope != derive_revision_scope(pm, mans[r.manifest_digest]):
                    raise PilotError(PilotErrorCode.REVISION_SCOPE_MISMATCH, "PROPOSED revision scope differs from the derivation")
                if r.predecessor_state_digest is not None:
                    p = by_digest.get(r.predecessor_state_digest)
                    if p is None or p.state is not PilotConfigurationState.REVISED or p.method != r.method or p.successor_manifest_digest != r.manifest_digest:
                        raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, "successor PROPOSED must follow the same method's REVISED record")
            continue
        p = by_digest.get(r.predecessor_state_digest or "")
        if p is None or p.method != r.method or p.manifest_digest != r.manifest_digest or (p.state, r.state) not in _PERMITTED:
            raise PilotError(PilotErrorCode.STATE_TRANSITION_INVALID, f"no permitted transition produces this {r.state.value} record")
        if r.state is PilotConfigurationState.REVISED:
            sm = mans.get(r.successor_manifest_digest or "")
            if sm is None:
                raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, "REVISED names an unsupplied successor manifest")
            if r.revision_scope != derive_revision_scope(mans[r.manifest_digest], sm):
                raise PilotError(PilotErrorCode.REVISION_SCOPE_MISMATCH, "REVISED revision scope differs from the derivation")
    # Supersession completeness: every predecessor method REVISED, every successor method PROPOSED.
    revised = [r for r in recs if r.state is PilotConfigurationState.REVISED]
    for r in revised:
        pm, sm = mans[r.manifest_digest], mans[r.successor_manifest_digest]
        for a in pm.methods:
            if not any(x.state is PilotConfigurationState.REVISED and x.manifest_digest == pm.manifest_digest and x.method == a.method and x.successor_manifest_digest == sm.manifest_digest for x in recs):
                raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, f"predecessor method {a.method.method_id} has no REVISED record")
        for a in sm.methods:
            if not any(x.state is PilotConfigurationState.PROPOSED and x.manifest_digest == sm.manifest_digest and x.method == a.method and x.predecessor_manifest_digest == pm.manifest_digest for x in recs):
                raise PilotError(PilotErrorCode.LINEAGE_INCOMPLETE, f"successor method {a.method.method_id} has no PROPOSED record")


__all__ = [
    "PILOT_STATE_SCHEMA_VERSION", "APPROVAL_STATUS_NONE", "PilotConfigurationState", "RevisionScope", "LifecycleEvent",
    "comparison_request_id", "derive_revision_scope", "PilotConfigurationStateRecord", "propose", "transition", "validate_lineage",
]
