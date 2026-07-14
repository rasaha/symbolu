"""Shadow evaluation records + classification (Phase 1).

ACP-side shadow logic only: run the deterministic ACP selection over an
``AdaptedSet`` and classify how it relates to the production BCVF choice (whose
id is supplied by the external harness). This module imports NO production code
and NO BCVF — the BCVF replica lives in the eval harness, keeping the ACP core
stdlib-only and production-independent.

Every record carries ``shadow_only=True``. A disagreement is *classified*, never
recorded as an ACP "win" by default.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from .action_selection import LexicographicActionSelector, SelectionOutcome
from .adapters import AdaptedSet
from .envelopes import ActionDecision


class ShadowClass(str, Enum):
    AGREE_ADMISSIBLE = "AGREE_ADMISSIBLE"
    DIFFERENT_BOTH_ADMISSIBLE = "DIFFERENT_BOTH_ADMISSIBLE"
    BCVF_SELECTED_INADMISSIBLE = "BCVF_SELECTED_INADMISSIBLE"
    ACP_NO_SAFE_ACTION = "ACP_NO_SAFE_ACTION"
    ACP_INSUFFICIENT_EVIDENCE = "ACP_INSUFFICIENT_EVIDENCE"
    ADAPTER_UNSUPPORTED = "ADAPTER_UNSUPPORTED"
    SHADOW_ERROR = "SHADOW_ERROR"


@dataclass(frozen=True)
class ShadowRecord:
    call_site: str
    world_state_identity: str
    candidate_identities: Tuple[str, ...]
    bcvf_selected_candidate: Optional[str]
    acp_outcome: str                     # ActionDecision value
    acp_selected_candidate: Optional[str]
    acp_rejected: Tuple[Tuple[str, str], ...]   # (candidate_id, reason_code)
    dispositive_reasons: Tuple[str, ...]
    bcvf_selected_inadmissible: bool
    bcvf_inadmissible_reason: Optional[str]     # reason code for BCVF's pick
    bcvf_inadmissible_kind: Optional[str]       # "REAL_VIOLATION" | "UNEVALUABLE"
    acp_no_safe_action: bool
    both_selected_same: bool
    latency_us: float
    missing_evidence: Tuple[str, ...]
    shadow_class: ShadowClass
    shadow_only: bool = field(default=True)

    def content_dict(self) -> dict:
        """Deterministic content (excludes wall-clock latency)."""
        return {
            "call_site": self.call_site,
            "world_state_identity": self.world_state_identity,
            "candidate_identities": list(self.candidate_identities),
            "bcvf_selected_candidate": self.bcvf_selected_candidate,
            "acp_outcome": self.acp_outcome,
            "acp_selected_candidate": self.acp_selected_candidate,
            "acp_rejected": [list(x) for x in self.acp_rejected],
            "dispositive_reasons": list(self.dispositive_reasons),
            "bcvf_selected_inadmissible": self.bcvf_selected_inadmissible,
            "bcvf_inadmissible_reason": self.bcvf_inadmissible_reason,
            "bcvf_inadmissible_kind": self.bcvf_inadmissible_kind,
            "acp_no_safe_action": self.acp_no_safe_action,
            "both_selected_same": self.both_selected_same,
            "missing_evidence": list(self.missing_evidence),
            "shadow_class": self.shadow_class.value,
            "shadow_only": self.shadow_only,
        }

    def to_dict(self) -> dict:
        d = self.content_dict()
        d["latency_us"] = round(self.latency_us, 3)
        return d


def acp_evaluate(adapted: AdaptedSet, *, tick: int, decision_id: str) -> SelectionOutcome:
    """Run the frozen lexicographic ACP selection over an adapted set."""
    selector = LexicographicActionSelector(adapted.sort_key)
    return selector.select(
        tick=tick, decision_id=decision_id, world_state=adapted.world_state,
        candidates=adapted.candidates, candidate_constraints=adapted.candidate_constraints)


def classify(adapted: AdaptedSet, outcome: SelectionOutcome,
             bcvf_selected_id: Optional[str], *, latency_us: float) -> ShadowRecord:
    """Deterministically classify the ACP-vs-BCVF relationship."""
    trace = outcome.trace
    surviving = set(trace.surviving_candidate_ids)
    rejected = tuple((r.candidate_id, r.reason_code) for r in trace.rejected)
    dispositive = tuple(r.reason_code for r in trace.rejected)
    missing = tuple(sorted({r.reason_code for r in trace.rejected
                            if r.reason_code.startswith("MISSING_")}))

    acp_no_safe = outcome.decision is ActionDecision.NO_SAFE_ACTION
    acp_sel = outcome.selected.candidate_id if outcome.selected else None
    bcvf_inadmissible = (bcvf_selected_id is not None
                         and bcvf_selected_id not in surviving)
    both_same = (acp_sel is not None and acp_sel == bcvf_selected_id)

    # If BCVF's pick is inadmissible, name WHY, and whether it is a real hard
    # violation vs merely unevaluable (no/missing evidence). This separates
    # "BCVF chose something ACP proves unsafe" from "ACP lacks data to judge".
    bcvf_reason: Optional[str] = None
    bcvf_kind: Optional[str] = None
    if bcvf_inadmissible:
        for r in trace.rejected:
            if r.candidate_id == bcvf_selected_id:
                bcvf_reason = r.reason_code
                break
        if bcvf_reason is None or bcvf_reason == "NO_HARD_EVIDENCE" or \
                bcvf_reason.startswith("MISSING_"):
            bcvf_kind = "UNEVALUABLE"
        else:
            bcvf_kind = "REAL_VIOLATION"

    # Classification precedence: a production pick that ACP's hard filter rejects
    # is the headline finding.
    if bcvf_inadmissible:
        cls = ShadowClass.BCVF_SELECTED_INADMISSIBLE
    elif outcome.decision is ActionDecision.REQUEST_MORE_OBSERVATION or (
            acp_no_safe and dispositive and all(
                c.startswith("MISSING_") for c in dispositive)):
        cls = ShadowClass.ACP_INSUFFICIENT_EVIDENCE
    elif acp_no_safe:
        cls = ShadowClass.ACP_NO_SAFE_ACTION
    elif both_same:
        cls = ShadowClass.AGREE_ADMISSIBLE
    else:
        cls = ShadowClass.DIFFERENT_BOTH_ADMISSIBLE

    return ShadowRecord(
        call_site=adapted.call_site,
        world_state_identity=adapted.world_state.version,
        candidate_identities=tuple(c.identity for c in adapted.candidates),
        bcvf_selected_candidate=bcvf_selected_id,
        acp_outcome=outcome.decision.value, acp_selected_candidate=acp_sel,
        acp_rejected=rejected, dispositive_reasons=dispositive,
        bcvf_selected_inadmissible=bcvf_inadmissible,
        bcvf_inadmissible_reason=bcvf_reason, bcvf_inadmissible_kind=bcvf_kind,
        acp_no_safe_action=acp_no_safe,
        both_selected_same=both_same, latency_us=latency_us,
        missing_evidence=missing, shadow_class=cls)
