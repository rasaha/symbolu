"""Assessment completeness service — deterministic, structural only.

Computes whether an assessment is structurally finished under the published
contract. It never considers whether observation values are good or bad. A
supported low value can be COMPLETE; a favourable value with missing required
evidence is INCOMPLETE; a high/critical unresolved conflict is BLOCKED.

Deterministic conflict policy (Phase 3B): HIGH/CRITICAL conflicts block
finalization (they require a later authorized disposition); LOW/MEDIUM conflicts
are recorded and yield COMPLETE_WITH_CONFLICTS.
"""

from __future__ import annotations

from ..assessments.completeness import CompletenessResult
from ..assessments.missing_evidence import MissingEvidenceRecord
from ..assessments.observation import Observation
from ..assessments.evidence_binding import EvidenceBinding
from ..assessments.status import CompletenessStatus
from ..assessments.workspace import AssessmentWorkspace
from ..rubrics.conflicts import Conflict, ConflictSeverity

_BLOCKING_SEVERITIES = frozenset({ConflictSeverity.HIGH, ConflictSeverity.CRITICAL})


class AssessmentCompletenessService:
    def compute(
        self,
        workspace: AssessmentWorkspace,
        *,
        bindings: tuple[EvidenceBinding, ...],
        observations: tuple[Observation, ...],
        missing: tuple[MissingEvidenceRecord, ...],
        conflicts: tuple[Conflict, ...],
    ) -> CompletenessResult:
        obs_by_crit = {o.criterion_id: o for o in observations}
        binding_count: dict[str, int] = {}
        for b in bindings:
            binding_count[b.criterion_id] = binding_count.get(b.criterion_id, 0) + 1

        required = [b for b in workspace.capability_bindings if b.required]
        blocking: list[str] = []
        satisfied = 0
        for b in required:
            crit = b.criterion_id
            ok = crit in obs_by_crit
            if b.evidence_rule.minimum_count > 0 and \
                    binding_count.get(crit, 0) < b.evidence_rule.minimum_count:
                ok = False
            if ok:
                satisfied += 1
            else:
                blocking.append(f"REQUIRED_CRITERION_UNSATISFIED:{crit}")

        blocking_conflicts = [c for c in conflicts if c.severity in _BLOCKING_SEVERITIES]
        for c in blocking_conflicts:
            blocking.append(f"BLOCKING_CONFLICT:{c.conflict_id}")
        non_blocking_conflicts = [c for c in conflicts
                                  if c.severity not in _BLOCKING_SEVERITIES]
        has_uncertainty = any(o.uncertainty is not None for o in observations)

        if not observations and not bindings and not missing:
            status = CompletenessStatus.NOT_STARTED
        elif blocking_conflicts:
            status = CompletenessStatus.BLOCKED
        elif satisfied < len(required):
            status = CompletenessStatus.INCOMPLETE
        elif non_blocking_conflicts:
            status = CompletenessStatus.COMPLETE_WITH_CONFLICTS
        elif has_uncertainty:
            status = CompletenessStatus.COMPLETE_WITH_UNCERTAINTY
        else:
            status = CompletenessStatus.COMPLETE

        return CompletenessResult(
            status=status, required_criteria_total=len(required),
            satisfied_criteria=satisfied, criteria_with_observations=len(obs_by_crit),
            blocking_conditions=tuple(blocking),
            has_uncertainty=has_uncertainty, has_conflicts=bool(conflicts))
