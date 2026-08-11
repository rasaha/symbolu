"""Safe non-compensatory effect aggregation (spec §6/D-C, §13, §17 — closes M-1).

This is the RA-8 security kernel. Decision Authority's internal ``_compare`` keys
the primary-outcome verdict off ``latest = records[-1]`` (confirmed live, spec §0
row 13 / ADR M-1), so a later favorable record can mask an earlier **material
unfavorable** one. DA stays reusable by non-RA products; **RA-8 owns the safe
aggregation** as a composition rule over the *full* record set, applied *before*
trusting any single-record verdict — closing the favorable-mask hole at the RA-8
boundary with no DA change (spec §6 "M-1 closure").

Ratified invariant (spec §6, §28 I10):

    A material unfavorable effect record MUST NOT be masked by a later favorable
    record for the same governed execution unless an explicit finality/version
    supersession relation proves the earlier record was only a non-final state.

Supersession is **explicit and narrow** (spec §6/D-C, §13): a later record
supersedes an earlier one ONLY when they share the same effect identity (same
non-empty ``external_result_id``) and the later one is a ``FINAL`` update of a
prior ``NON_FINAL``/``UNKNOWN`` state (``PARTIAL → FINAL``). A ``FINAL`` unfavorable
record can **never** be superseded by a later favorable record of a *different*
effect identity. **No last-writer-wins** (spec §17).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from ugence_decision_authority.execution.execution_record import ExecutionRecord
from ugence_decision_authority.execution.status import BusinessOutcome, Finality

from .contracts import EffectFinality, EffectReasonCode, EffectReconciliationOutcome

__all__ = [
    "AggregateAssessment",
    "safe_aggregate",
    "UNFAVORABLE_OUTCOMES",
]

#: Observed business outcomes that are materially unfavorable (spec §6, §27).
UNFAVORABLE_OUTCOMES = frozenset(
    {
        BusinessOutcome.FAILED,
        BusinessOutcome.REJECTED,
        BusinessOutcome.CANCELLED_EXTERNALLY,
    }
)


@dataclass(frozen=True)
class AggregateAssessment:
    """The safe-aggregated neutral verdict over the full record set (spec §6, §14)."""

    outcome: EffectReconciliationOutcome
    finality: EffectFinality
    reason_codes: Tuple[EffectReasonCode, ...] = ()
    reasons: Tuple[str, ...] = ()
    dominant_record_ids: Tuple[str, ...] = ()
    compensation_recommended: bool = False


def _param_mismatch(record: ExecutionRecord, expected: Mapping[str, str]) -> bool:
    """A SUCCEEDED record whose observed params contradict the authorized ones (§6)."""

    observed = dict(record.observed_parameters or {})
    for key, value in expected.items():
        if key in observed and observed[key] != value:
            return True
    return False


def _is_wellformed(record: object) -> bool:
    """Exact type checks so a malformed record can never influence the verdict (§29)."""

    return (
        isinstance(record, ExecutionRecord)
        and isinstance(record.business_outcome, BusinessOutcome)
        and isinstance(record.finality, Finality)
    )


def safe_aggregate(
    records: Sequence[ExecutionRecord],
    *,
    expected_parameters: Optional[Mapping[str, str]] = None,
) -> AggregateAssessment:
    """Aggregate the full record set non-compensatorily (spec §6/D-C — closes M-1).

    Never returns ``MATCHED`` unless every settled effect identity is favorable and
    nothing material contradicts it. A malformed record set, or one with no settled
    favorable evidence, resolves to ``UNKNOWN`` / ``MISMATCH`` / ``CONFLICTED`` — never
    ``MATCHED`` by default (spec §14, §27, §29).
    """

    expected = dict(expected_parameters or {})

    wellformed = [r for r in records if _is_wellformed(r)]
    if not records:
        return AggregateAssessment(
            EffectReconciliationOutcome.UNKNOWN,
            EffectFinality.PENDING,
            reason_codes=(EffectReasonCode.NO_OBSERVATION,),
            reasons=("no observed execution records",),
        )
    if not wellformed:
        return AggregateAssessment(
            EffectReconciliationOutcome.UNKNOWN,
            EffectFinality.PENDING,
            reason_codes=(EffectReasonCode.RECONCILIATION_ERROR,),
            reasons=("no well-formed execution records",),
        )

    # ------------------------------------------------------------------ #
    # 1. Collapse each effect identity to its settled representative,
    #    applying the ONLY legitimate supersession: PARTIAL → FINAL of the
    #    SAME identity (spec §6/§13). Records with no external_result_id
    #    cannot be grouped by identity and each stand alone (never superseded).
    # ------------------------------------------------------------------ #
    by_identity: Dict[str, List[ExecutionRecord]] = {}
    standalone: List[ExecutionRecord] = []
    for r in wellformed:
        if r.external_result_id:
            by_identity.setdefault(r.external_result_id, []).append(r)
        else:
            standalone.append(r)

    effective: List[ExecutionRecord] = list(standalone)
    identity_conflict_ids: List[str] = []
    for result_id, group in by_identity.items():
        finals = [r for r in group if r.finality is Finality.FINAL]
        if not finals:
            # Still open for this identity: keep the non-final members (pending/partial).
            effective.extend(group)
            continue
        # A single identity cannot be both favorable-final and unfavorable-final:
        # that is a same-identity conflict (contradicting FINAL observers, §17).
        fav = [r for r in finals if _favorable_final(r, expected)]
        unfav = [r for r in finals if _unfavorable_final(r, expected)]
        if fav and unfav:
            identity_conflict_ids.append(result_id)
        # Represent the settled identity by its FINAL records only; the superseded
        # non-final members of the same identity are legitimately dropped (§6/§13).
        effective.extend(finals)

    # ------------------------------------------------------------------ #
    # 2. Duplicate real effect: >1 distinct SUCCESS-like external_result_id, or any
    #    record the source itself flagged DUPLICATE (reuse the DA rule, spec §6/§16).
    # ------------------------------------------------------------------ #
    success_like_ids = {
        r.external_result_id
        for r in effective
        if r.external_result_id
        and r.business_outcome
        in (BusinessOutcome.SUCCEEDED, BusinessOutcome.PARTIALLY_SUCCEEDED)
    }
    any_duplicate = any(r.business_outcome is BusinessOutcome.DUPLICATE for r in effective)
    if any_duplicate or len(success_like_ids) > 1:
        return AggregateAssessment(
            EffectReconciliationOutcome.MANUAL_REVIEW,
            EffectFinality.FINAL,
            reason_codes=(EffectReasonCode.DUPLICATE_EFFECT,),
            reasons=("duplicate distinct real effects for one authorized attempt",),
            dominant_record_ids=tuple(
                sorted(r.execution_record_id for r in effective if r.external_result_id)
            ),
            compensation_recommended=True,
        )

    # ------------------------------------------------------------------ #
    # 3. Non-compensatory dominance over the effective (non-superseded) set.
    # ------------------------------------------------------------------ #
    unfavorable_final = [r for r in effective if _unfavorable_final(r, expected)]
    favorable_final = [r for r in effective if _favorable_final(r, expected)]
    # A partial effect within policy (params match) is PARTIAL regardless of finality
    # — a settled partial is still "not the full authorized effect", never a mismatch
    # merely because it is incomplete (spec §13). A partial whose params contradict
    # the authorized action is unfavorable (handled above), not partial.
    partial = [
        r
        for r in effective
        if r.business_outcome is BusinessOutcome.PARTIALLY_SUCCEEDED
        and not _unfavorable_final(r, expected)
    ]
    pending = [r for r in effective if _is_pending(r)]

    # 3a. Conflicting trusted observers — favorable AND unfavorable settled evidence
    #     for the same governed execution. Favorable never silently masks
    #     unfavorable; resolution needs explicit semantics, never last-writer-wins
    #     (spec §6, §17). This is the direct M-1 closure for FAILED↔SUCCEEDED.
    if identity_conflict_ids or (unfavorable_final and favorable_final):
        return AggregateAssessment(
            EffectReconciliationOutcome.CONFLICTED,
            EffectFinality.FINAL,
            reason_codes=(
                EffectReasonCode.CONFLICTING_OBSERVERS,
                EffectReasonCode.FAVORABLE_MASK_BLOCKED,
            ),
            reasons=(
                "conflicting final effect observations; a later favorable record "
                "cannot mask an earlier material unfavorable one (M-1 closure)",
            ),
            dominant_record_ids=tuple(
                sorted(r.execution_record_id for r in unfavorable_final + favorable_final)
            ),
            compensation_recommended=True,
        )

    # 3b. A material unfavorable FINAL effect dominates any non-final favorable one.
    if unfavorable_final:
        codes = _unfavorable_reason_codes(unfavorable_final, expected)
        return AggregateAssessment(
            EffectReconciliationOutcome.MISMATCH,
            EffectFinality.FINAL,
            reason_codes=codes,
            reasons=("a material unfavorable final effect was observed",),
            dominant_record_ids=tuple(sorted(r.execution_record_id for r in unfavorable_final)),
            compensation_recommended=True,
        )

    # 3c. Favorable and fully settled with nothing still converging → MATCHED.
    if favorable_final and not pending and not partial:
        return AggregateAssessment(
            EffectReconciliationOutcome.MATCHED,
            EffectFinality.FINAL,
            reasons=("all settled effects match the authorized action",),
            dominant_record_ids=tuple(sorted(r.execution_record_id for r in favorable_final)),
        )

    # 3d. A legitimate partial effect within policy (not final yet) — never a mismatch
    #     merely because it is not settled (spec §11/§13). No signal yet (spec §7).
    if partial or (favorable_final and pending):
        return AggregateAssessment(
            EffectReconciliationOutcome.PARTIAL,
            EffectFinality.PARTIAL,
            reason_codes=(EffectReasonCode.NON_FINAL_PENDING,),
            reasons=("effect is partial / still converging; not yet final",),
            dominant_record_ids=tuple(
                sorted(r.execution_record_id for r in partial + favorable_final)
            ),
        )

    # 3e. Otherwise finality is not yet settled (pending / unknown) → UNKNOWN,
    #     never MATCHED, never a fabricated failure (spec §13, §27).
    reason_code = (
        EffectReasonCode.FINALITY_UNKNOWN if pending else EffectReasonCode.NO_OBSERVATION
    )
    return AggregateAssessment(
        EffectReconciliationOutcome.UNKNOWN,
        EffectFinality.PENDING,
        reason_codes=(reason_code,),
        reasons=("no settled favorable effect; finality not yet determined",),
    )


# --- record classification helpers -------------------------------------------
def _favorable_final(record: ExecutionRecord, expected: Mapping[str, str]) -> bool:
    return (
        record.finality is Finality.FINAL
        and record.business_outcome is BusinessOutcome.SUCCEEDED
        and not _param_mismatch(record, expected)
    )


def _unfavorable_final(record: ExecutionRecord, expected: Mapping[str, str]) -> bool:
    if record.finality is not Finality.FINAL:
        return False
    if record.business_outcome in UNFAVORABLE_OUTCOMES:
        return True
    # A settled "success" (or settled partial) whose observed parameters contradict
    # the authorized ones is a material mismatch, not a favorable/acceptable effect
    # (spec §6, §13 unacceptable-partial, §14 PARAM_MISMATCH).
    if (
        record.business_outcome
        in (BusinessOutcome.SUCCEEDED, BusinessOutcome.PARTIALLY_SUCCEEDED)
        and _param_mismatch(record, expected)
    ):
        return True
    return False


def _is_pending(record: ExecutionRecord) -> bool:
    if record.finality is Finality.FINAL:
        return False
    if record.business_outcome is BusinessOutcome.PARTIALLY_SUCCEEDED:
        return False  # counted as partial, not pending
    return True


def _unfavorable_reason_codes(
    records: Sequence[ExecutionRecord], expected: Mapping[str, str]
) -> Tuple[EffectReasonCode, ...]:
    codes: List[EffectReasonCode] = []
    for r in records:
        if r.business_outcome is BusinessOutcome.FAILED:
            codes.append(EffectReasonCode.OUTCOME_FAILED)
        elif r.business_outcome is BusinessOutcome.REJECTED:
            codes.append(EffectReasonCode.OUTCOME_REJECTED)
        elif r.business_outcome is BusinessOutcome.CANCELLED_EXTERNALLY:
            codes.append(EffectReasonCode.OUTCOME_CANCELLED)
        elif r.business_outcome is BusinessOutcome.SUCCEEDED and _param_mismatch(r, expected):
            codes.append(EffectReasonCode.PARAMETER_MISMATCH)
    # Deterministic, de-duplicated order.
    seen: Dict[EffectReasonCode, None] = {}
    for c in codes:
        seen.setdefault(c, None)
    return tuple(seen.keys()) or (EffectReasonCode.OUTCOME_FAILED,)
