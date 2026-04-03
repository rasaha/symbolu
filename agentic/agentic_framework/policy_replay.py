"""
Policy Replay / Simulation Engine — "What would this policy have done?"

Replays historical governance events against selected policy bundles and
compares recorded outcomes vs simulated outcomes.

ARCHITECTURAL POSITION:
    Durable Audit Store (source of truth)
        ↓
    Policy Replay Engine (THIS MODULE)
        ├─ Extract replayable inputs from audit records
        ├─ Reconstruct AuthorizationRequest
        ├─ Evaluate via GovernanceService (decision-only, no mutation)
        ├─ Compare simulated vs recorded outcome
        └─ Produce structured diffs and batch summaries

NON-MUTATION GUARANTEE:
    - GovernanceService never executes actions (decision-only by design)
    - Replay GovernanceService is created WITHOUT an audit_store
    - No audit events are persisted during replay
    - No tools are called, no side effects occur

REPLAY FIDELITY:
    - FULL: All AuthorizationRequest inputs present in request_snapshot
    - PARTIAL: Some inputs missing, conservative defaults used, warnings emitted
    - INSUFFICIENT: Critical fields missing, replay not attempted

DESIGN PRINCIPLES:
    1. Honest about fidelity — never silently fabricate inputs
    2. Structured diffs — machine-readable comparison categories
    3. Batch aggregation — impact summaries across event sets
    4. Reuses runtime governance logic — no duplicated policy engine
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from agentic.agentic_framework.governance_models import (
    APIGovernanceDecision,
    AuthorizationRequest,
)
from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.policy_bundle import (
    PolicyBundle,
    PolicyResolution,
    resolve_effective_policy,
)
from agentic.ledger.governance_audit_store import GovernanceAuditStore

_logger = logging.getLogger(__name__)


# =========================================================================
# Replay Fidelity
# =========================================================================


class ReplayFidelity(Enum):
    """How faithfully the replay can reproduce the original decision."""
    FULL = "full"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


# =========================================================================
# Comparison Categories
# =========================================================================


class OutcomeChange(Enum):
    """How the simulated outcome compares to the recorded outcome."""
    UNCHANGED = "unchanged"
    STRICTER = "stricter"
    LOOSER = "looser"
    NEWLY_BLOCKED = "newly_blocked"
    NEWLY_ALLOWED = "newly_allowed"
    NEWLY_DEFERRED = "newly_deferred"
    ESCALATION_CHANGED = "escalation_changed"
    CONFIDENCE_CHANGED = "confidence_changed"


# Decision severity for comparison (higher = more restrictive)
_DECISION_SEVERITY = {
    "ALLOW": 0,
    "DEFER": 1,
    "DENY": 2,
}

_ESCALATION_SEVERITY = {
    "none": 0,
    "notify": 1,
    "confirm": 2,
    "halt": 3,
}

_EXECUTION_SEVERITY = {
    "full": 0,
    "cautious": 1,
    "confirm": 2,
    "confirm_required": 2,
    "blocked": 3,
}


# =========================================================================
# Replay Models
# =========================================================================


@dataclass(frozen=True)
class ReplayableEvent:
    """Extracted subset of an audit record that can be replayed.

    Contains enough information to reconstruct an AuthorizationRequest
    and compare the result. Fields that were missing from the original
    audit record are marked via `fidelity` and `fidelity_warnings`.
    """
    event_id: str
    timestamp: str
    source_module: str

    # Reconstructed request inputs
    actor_id: str
    action_type: str
    tool_name: str
    agency_level: str
    capabilities: Tuple[str, ...]
    quality_score: float
    coherence_score: float
    internal_consistency: float
    goal_alignment: float
    trajectory_confidence: float
    blocking_factors: Tuple[str, ...]

    # Recorded outcome (what actually happened)
    recorded_decision: str
    recorded_eligible: bool
    recorded_risk_level: str
    recorded_confidence: float
    recorded_execution_mode: str
    recorded_escalation_level: str
    recorded_blocked_reasons: Tuple[str, ...]

    # Original policy metadata (if present)
    original_policy_id: Optional[str] = None
    original_policy_version: Optional[str] = None
    original_policy_fingerprint: Optional[str] = None

    # Fidelity
    fidelity: ReplayFidelity = ReplayFidelity.FULL
    fidelity_warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying a single event under a policy."""
    event_id: str
    replay_timestamp: str

    # Policy used for replay
    replay_policy_id: str
    replay_policy_version: str
    replay_policy_fingerprint: str

    # Simulated outcome
    simulated_decision: str
    simulated_eligible: bool
    simulated_risk_level: str
    simulated_confidence: float
    simulated_execution_mode: str
    simulated_escalation_level: str
    simulated_blocked_reasons: Tuple[str, ...]
    simulated_rationale_codes: Tuple[str, ...]

    # Fidelity carried from extraction
    fidelity: ReplayFidelity
    fidelity_warnings: Tuple[str, ...]

    # Error if replay itself failed
    replay_error: Optional[str] = None


@dataclass(frozen=True)
class ReplayComparison:
    """Structured diff between recorded and simulated outcomes."""
    event_id: str

    # Recorded
    recorded_decision: str
    recorded_eligible: bool
    recorded_confidence: float
    recorded_execution_mode: str
    recorded_escalation_level: str

    # Simulated
    simulated_decision: str
    simulated_eligible: bool
    simulated_confidence: float
    simulated_execution_mode: str
    simulated_escalation_level: str

    # Diff classification
    outcome_changes: Tuple[OutcomeChange, ...]
    decision_shifted: bool
    confidence_delta: float
    eligibility_changed: bool

    # Policy provenance
    original_policy_id: Optional[str]
    replay_policy_id: str

    # Fidelity
    fidelity: ReplayFidelity
    fidelity_warnings: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for structured output."""
        return {
            "event_id": self.event_id,
            "recorded_decision": self.recorded_decision,
            "simulated_decision": self.simulated_decision,
            "decision_shifted": self.decision_shifted,
            "outcome_changes": [c.value for c in self.outcome_changes],
            "confidence_delta": round(self.confidence_delta, 6),
            "eligibility_changed": self.eligibility_changed,
            "recorded_eligible": self.recorded_eligible,
            "simulated_eligible": self.simulated_eligible,
            "recorded_confidence": self.recorded_confidence,
            "simulated_confidence": self.simulated_confidence,
            "recorded_execution_mode": self.recorded_execution_mode,
            "simulated_execution_mode": self.simulated_execution_mode,
            "recorded_escalation_level": self.recorded_escalation_level,
            "simulated_escalation_level": self.simulated_escalation_level,
            "original_policy_id": self.original_policy_id,
            "replay_policy_id": self.replay_policy_id,
            "fidelity": self.fidelity.value,
            "fidelity_warnings": list(self.fidelity_warnings),
        }


@dataclass(frozen=True)
class BatchReplaySummary:
    """Aggregate summary of replaying multiple events."""
    total_events: int
    replayed_count: int
    skipped_count: int
    skip_reasons: Tuple[str, ...]

    # Outcome distribution
    unchanged_count: int
    stricter_count: int
    looser_count: int
    newly_blocked_count: int
    newly_allowed_count: int
    newly_deferred_count: int

    # Fidelity distribution
    full_fidelity_count: int
    partial_fidelity_count: int

    # Policy metadata
    replay_policy_id: str
    replay_policy_version: str
    replay_timestamp: str

    # Per-event comparisons
    comparisons: Tuple[ReplayComparison, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for structured output."""
        return {
            "total_events": self.total_events,
            "replayed_count": self.replayed_count,
            "skipped_count": self.skipped_count,
            "skip_reasons": list(self.skip_reasons),
            "unchanged_count": self.unchanged_count,
            "stricter_count": self.stricter_count,
            "looser_count": self.looser_count,
            "newly_blocked_count": self.newly_blocked_count,
            "newly_allowed_count": self.newly_allowed_count,
            "newly_deferred_count": self.newly_deferred_count,
            "full_fidelity_count": self.full_fidelity_count,
            "partial_fidelity_count": self.partial_fidelity_count,
            "replay_policy_id": self.replay_policy_id,
            "replay_policy_version": self.replay_policy_version,
            "replay_timestamp": self.replay_timestamp,
            "comparisons": [c.to_dict() for c in self.comparisons],
        }


# =========================================================================
# Audit → Replay Extraction
# =========================================================================


_CONSERVATIVE_DEFAULT = 0.5
_REQUIRED_FIELDS = ("actor_id", "action_type")


def extract_replayable_event(
    audit_record: Dict[str, Any],
) -> ReplayableEvent:
    """Convert a durable audit record dict into a ReplayableEvent.

    Handles missing fields gracefully:
    - Required fields (actor_id, action_type): if missing → INSUFFICIENT fidelity
    - Score fields (quality_score, etc.): if missing → use 0.5 default, PARTIAL fidelity
    - Policy metadata: if missing → None, still replayable

    Args:
        audit_record: Dict from GovernanceAuditStore.list_recent() or similar.

    Returns:
        ReplayableEvent with fidelity assessment.
    """
    warnings: List[str] = []
    fidelity = ReplayFidelity.FULL

    snapshot = audit_record.get("request_snapshot", {})
    if isinstance(snapshot, str):
        import json
        try:
            snapshot = json.loads(snapshot)
        except (json.JSONDecodeError, TypeError):
            snapshot = {}

    # Required fields — check both top-level and snapshot
    actor_id = snapshot.get("actor_id") or audit_record.get("actor_id", "")
    action_type = snapshot.get("action_type") or audit_record.get("action_type", "")

    if not actor_id or not action_type:
        return ReplayableEvent(
            event_id=audit_record.get("event_id", "unknown"),
            timestamp=audit_record.get("timestamp", ""),
            source_module=audit_record.get("source_module", ""),
            actor_id=actor_id,
            action_type=action_type,
            tool_name="",
            agency_level="INFORM",
            capabilities=(),
            quality_score=_CONSERVATIVE_DEFAULT,
            coherence_score=_CONSERVATIVE_DEFAULT,
            internal_consistency=_CONSERVATIVE_DEFAULT,
            goal_alignment=_CONSERVATIVE_DEFAULT,
            trajectory_confidence=_CONSERVATIVE_DEFAULT,
            blocking_factors=(),
            recorded_decision=audit_record.get("decision_outcome", "DENY"),
            recorded_eligible=audit_record.get("eligible", False),
            recorded_risk_level=audit_record.get("risk_level", "write"),
            recorded_confidence=audit_record.get("confidence", 0.0),
            recorded_execution_mode=audit_record.get("execution_mode", "blocked"),
            recorded_escalation_level=audit_record.get("escalation_level", "halt"),
            recorded_blocked_reasons=tuple(
                audit_record.get("blocked_reasons", ())
            ),
            fidelity=ReplayFidelity.INSUFFICIENT,
            fidelity_warnings=(
                "Missing required fields: actor_id or action_type",
            ),
        )

    tool_name = snapshot.get("tool_name") or audit_record.get("tool_name", "")
    agency_level = snapshot.get("agency_level", "INFORM")
    capabilities = tuple(snapshot.get("capabilities", ()))

    # Score fields — mark partial if missing
    def _get_score(key: str) -> float:
        nonlocal fidelity
        val = snapshot.get(key)
        if val is None:
            warnings.append(f"Missing {key} in request_snapshot, using default {_CONSERVATIVE_DEFAULT}")
            fidelity = ReplayFidelity.PARTIAL
            return _CONSERVATIVE_DEFAULT
        return float(val)

    quality_score = _get_score("quality_score")
    coherence_score = _get_score("coherence_score")
    internal_consistency = _get_score("internal_consistency")
    goal_alignment = _get_score("goal_alignment")
    trajectory_confidence = _get_score("trajectory_confidence")

    blocking_factors = tuple(snapshot.get("blocking_factors", ()))

    # Policy metadata from original event
    policy_bundle_meta = snapshot.get("policy_bundle")
    original_policy_id = None
    original_policy_version = None
    original_policy_fingerprint = None
    if isinstance(policy_bundle_meta, dict):
        original_policy_id = policy_bundle_meta.get("policy_id")
        original_policy_version = policy_bundle_meta.get("version")
        original_policy_fingerprint = policy_bundle_meta.get("fingerprint")

    return ReplayableEvent(
        event_id=audit_record.get("event_id", "unknown"),
        timestamp=audit_record.get("timestamp", ""),
        source_module=audit_record.get("source_module", ""),
        actor_id=actor_id,
        action_type=action_type,
        tool_name=tool_name,
        agency_level=agency_level,
        capabilities=capabilities,
        quality_score=quality_score,
        coherence_score=coherence_score,
        internal_consistency=internal_consistency,
        goal_alignment=goal_alignment,
        trajectory_confidence=trajectory_confidence,
        blocking_factors=blocking_factors,
        recorded_decision=audit_record.get("decision_outcome", "DENY"),
        recorded_eligible=audit_record.get("eligible", False),
        recorded_risk_level=audit_record.get("risk_level", "write"),
        recorded_confidence=audit_record.get("confidence", 0.0),
        recorded_execution_mode=audit_record.get("execution_mode", "blocked"),
        recorded_escalation_level=audit_record.get("escalation_level", "halt"),
        recorded_blocked_reasons=tuple(
            audit_record.get("blocked_reasons", ())
        ),
        original_policy_id=original_policy_id,
        original_policy_version=original_policy_version,
        original_policy_fingerprint=original_policy_fingerprint,
        fidelity=fidelity,
        fidelity_warnings=tuple(warnings),
    )


def _event_to_request(event: ReplayableEvent) -> AuthorizationRequest:
    """Reconstruct an AuthorizationRequest from a ReplayableEvent."""
    return AuthorizationRequest(
        actor_id=event.actor_id,
        action_type=event.action_type,
        tool_name=event.tool_name or None,
        agency_level=event.agency_level,
        capabilities=list(event.capabilities),
        quality_score=event.quality_score,
        coherence_score=event.coherence_score,
        internal_consistency=event.internal_consistency,
        goal_alignment=event.goal_alignment,
        trajectory_confidence=event.trajectory_confidence,
        blocking_factors=list(event.blocking_factors),
    )


# =========================================================================
# Comparison Logic
# =========================================================================


def _classify_outcome_changes(
    recorded_decision: str,
    simulated_decision: str,
    recorded_escalation: str,
    simulated_escalation: str,
    recorded_confidence: float,
    simulated_confidence: float,
) -> List[OutcomeChange]:
    """Classify all outcome changes between recorded and simulated."""
    changes: List[OutcomeChange] = []

    rec_sev = _DECISION_SEVERITY.get(recorded_decision, 1)
    sim_sev = _DECISION_SEVERITY.get(simulated_decision, 1)

    if rec_sev == sim_sev:
        # Decision itself unchanged — but other fields may differ
        pass
    elif sim_sev > rec_sev:
        changes.append(OutcomeChange.STRICTER)
    else:
        changes.append(OutcomeChange.LOOSER)

    # Specific newly-X categories
    if simulated_decision == "DENY" and recorded_decision != "DENY":
        changes.append(OutcomeChange.NEWLY_BLOCKED)
    if simulated_decision == "ALLOW" and recorded_decision != "ALLOW":
        changes.append(OutcomeChange.NEWLY_ALLOWED)
    if simulated_decision == "DEFER" and recorded_decision != "DEFER":
        changes.append(OutcomeChange.NEWLY_DEFERRED)

    # Escalation change
    rec_esc = _ESCALATION_SEVERITY.get(recorded_escalation, 0)
    sim_esc = _ESCALATION_SEVERITY.get(simulated_escalation, 0)
    if rec_esc != sim_esc:
        changes.append(OutcomeChange.ESCALATION_CHANGED)

    # Confidence change (>= 0.05 threshold for significance)
    if abs(simulated_confidence - recorded_confidence) >= 0.05:
        changes.append(OutcomeChange.CONFIDENCE_CHANGED)

    if not changes:
        changes.append(OutcomeChange.UNCHANGED)

    return changes


def compare_outcomes(
    event: ReplayableEvent,
    result: ReplayResult,
) -> ReplayComparison:
    """Build a structured comparison between recorded and simulated outcomes."""
    changes = _classify_outcome_changes(
        recorded_decision=event.recorded_decision,
        simulated_decision=result.simulated_decision,
        recorded_escalation=event.recorded_escalation_level,
        simulated_escalation=result.simulated_escalation_level,
        recorded_confidence=event.recorded_confidence,
        simulated_confidence=result.simulated_confidence,
    )

    return ReplayComparison(
        event_id=event.event_id,
        recorded_decision=event.recorded_decision,
        recorded_eligible=event.recorded_eligible,
        recorded_confidence=event.recorded_confidence,
        recorded_execution_mode=event.recorded_execution_mode,
        recorded_escalation_level=event.recorded_escalation_level,
        simulated_decision=result.simulated_decision,
        simulated_eligible=result.simulated_eligible,
        simulated_confidence=result.simulated_confidence,
        simulated_execution_mode=result.simulated_execution_mode,
        simulated_escalation_level=result.simulated_escalation_level,
        outcome_changes=tuple(changes),
        decision_shifted=(event.recorded_decision != result.simulated_decision),
        confidence_delta=result.simulated_confidence - event.recorded_confidence,
        eligibility_changed=(event.recorded_eligible != result.simulated_eligible),
        original_policy_id=event.original_policy_id,
        replay_policy_id=result.replay_policy_id,
        fidelity=result.fidelity,
        fidelity_warnings=result.fidelity_warnings,
    )


# =========================================================================
# Policy Replay Engine
# =========================================================================


class PolicyReplayEngine:
    """Replays historical governance events against policy bundles.

    NON-MUTATION GUARANTEE:
        - Creates GovernanceService WITHOUT audit_store (no persistence)
        - GovernanceService is decision-only by design
        - No tools are called, no side effects occur

    Usage::

        engine = PolicyReplayEngine()
        store = GovernanceAuditStore("governance_audit.db")
        records = store.list_recent(limit=50)

        # Replay under a different policy
        resolution = resolve_effective_policy(strict_policy)
        summary = engine.replay_batch(records, resolution)

        print(summary.newly_blocked_count)
        for comp in summary.comparisons:
            if comp.decision_shifted:
                print(comp.to_dict())
    """

    def replay_event(
        self,
        audit_record: Dict[str, Any],
        policy_resolution: PolicyResolution,
    ) -> Tuple[ReplayResult, ReplayComparison]:
        """Replay a single audit record under a policy.

        Args:
            audit_record: Dict from GovernanceAuditStore query.
            policy_resolution: Resolved policy to evaluate against.

        Returns:
            (ReplayResult, ReplayComparison) tuple.
        """
        event = extract_replayable_event(audit_record)

        if event.fidelity == ReplayFidelity.INSUFFICIENT:
            result = ReplayResult(
                event_id=event.event_id,
                replay_timestamp=datetime.now(timezone.utc).isoformat(),
                replay_policy_id=policy_resolution.effective_policy.metadata.policy_id,
                replay_policy_version=policy_resolution.effective_policy.metadata.version,
                replay_policy_fingerprint=policy_resolution.effective_policy.metadata.fingerprint(),
                simulated_decision="DENY",
                simulated_eligible=False,
                simulated_risk_level="write",
                simulated_confidence=0.0,
                simulated_execution_mode="blocked",
                simulated_escalation_level="halt",
                simulated_blocked_reasons=("REPLAY_INSUFFICIENT_DATA",),
                simulated_rationale_codes=("REPLAY_INSUFFICIENT_DATA",),
                fidelity=ReplayFidelity.INSUFFICIENT,
                fidelity_warnings=event.fidelity_warnings,
                replay_error="Insufficient data for replay",
            )
            comparison = compare_outcomes(event, result)
            return result, comparison

        # Reconstruct AuthorizationRequest
        request = _event_to_request(event)

        # Create a GovernanceService WITHOUT audit_store (non-mutation)
        service = GovernanceService(policy_resolution=policy_resolution)

        try:
            response = service.authorize(request)

            result = ReplayResult(
                event_id=event.event_id,
                replay_timestamp=datetime.now(timezone.utc).isoformat(),
                replay_policy_id=policy_resolution.effective_policy.metadata.policy_id,
                replay_policy_version=policy_resolution.effective_policy.metadata.version,
                replay_policy_fingerprint=policy_resolution.effective_policy.metadata.fingerprint(),
                simulated_decision=response.governance_decision.value,
                simulated_eligible=response.eligible,
                simulated_risk_level=response.risk_level.value,
                simulated_confidence=response.confidence_score,
                simulated_execution_mode=response.execution_mode.value,
                simulated_escalation_level=response.escalation_level.value,
                simulated_blocked_reasons=tuple(response.blocked_reasons),
                simulated_rationale_codes=tuple(response.rationale_codes),
                fidelity=event.fidelity,
                fidelity_warnings=event.fidelity_warnings,
            )
        except Exception as exc:
            _logger.error(
                "Replay error for event %s: %s", event.event_id, exc,
                exc_info=True,
            )
            result = ReplayResult(
                event_id=event.event_id,
                replay_timestamp=datetime.now(timezone.utc).isoformat(),
                replay_policy_id=policy_resolution.effective_policy.metadata.policy_id,
                replay_policy_version=policy_resolution.effective_policy.metadata.version,
                replay_policy_fingerprint=policy_resolution.effective_policy.metadata.fingerprint(),
                simulated_decision="DENY",
                simulated_eligible=False,
                simulated_risk_level="write",
                simulated_confidence=0.0,
                simulated_execution_mode="blocked",
                simulated_escalation_level="halt",
                simulated_blocked_reasons=(f"REPLAY_ERROR:{type(exc).__name__}",),
                simulated_rationale_codes=(f"REPLAY_ERROR:{type(exc).__name__}",),
                fidelity=event.fidelity,
                fidelity_warnings=event.fidelity_warnings,
                replay_error=f"{type(exc).__name__}: {exc}",
            )

        comparison = compare_outcomes(event, result)
        return result, comparison

    def replay_batch(
        self,
        audit_records: Sequence[Dict[str, Any]],
        policy_resolution: PolicyResolution,
    ) -> BatchReplaySummary:
        """Replay multiple audit records and produce an aggregate summary.

        Args:
            audit_records: Sequence of dicts from GovernanceAuditStore.
            policy_resolution: Resolved policy to evaluate against.

        Returns:
            BatchReplaySummary with per-event comparisons and counts.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        comparisons: List[ReplayComparison] = []
        skip_reasons: List[str] = []
        skipped = 0

        for record in audit_records:
            event = extract_replayable_event(record)
            if event.fidelity == ReplayFidelity.INSUFFICIENT:
                skipped += 1
                skip_reasons.append(
                    f"{event.event_id}: {'; '.join(event.fidelity_warnings)}"
                )
                continue

            _, comparison = self.replay_event(record, policy_resolution)
            comparisons.append(comparison)

        # Aggregate counts
        unchanged = sum(
            1 for c in comparisons
            if OutcomeChange.UNCHANGED in c.outcome_changes
        )
        stricter = sum(
            1 for c in comparisons
            if OutcomeChange.STRICTER in c.outcome_changes
        )
        looser = sum(
            1 for c in comparisons
            if OutcomeChange.LOOSER in c.outcome_changes
        )
        newly_blocked = sum(
            1 for c in comparisons
            if OutcomeChange.NEWLY_BLOCKED in c.outcome_changes
        )
        newly_allowed = sum(
            1 for c in comparisons
            if OutcomeChange.NEWLY_ALLOWED in c.outcome_changes
        )
        newly_deferred = sum(
            1 for c in comparisons
            if OutcomeChange.NEWLY_DEFERRED in c.outcome_changes
        )
        full_fidelity = sum(
            1 for c in comparisons if c.fidelity == ReplayFidelity.FULL
        )
        partial_fidelity = sum(
            1 for c in comparisons if c.fidelity == ReplayFidelity.PARTIAL
        )

        return BatchReplaySummary(
            total_events=len(audit_records),
            replayed_count=len(comparisons),
            skipped_count=skipped,
            skip_reasons=tuple(skip_reasons),
            unchanged_count=unchanged,
            stricter_count=stricter,
            looser_count=looser,
            newly_blocked_count=newly_blocked,
            newly_allowed_count=newly_allowed,
            newly_deferred_count=newly_deferred,
            full_fidelity_count=full_fidelity,
            partial_fidelity_count=partial_fidelity,
            replay_policy_id=policy_resolution.effective_policy.metadata.policy_id,
            replay_policy_version=policy_resolution.effective_policy.metadata.version,
            replay_timestamp=timestamp,
            comparisons=tuple(comparisons),
        )

    def replay_batch_compare(
        self,
        audit_records: Sequence[Dict[str, Any]],
        policy_a: PolicyResolution,
        policy_b: PolicyResolution,
    ) -> Tuple[BatchReplaySummary, BatchReplaySummary]:
        """Replay the same events under two policies for side-by-side comparison.

        Returns:
            (summary_a, summary_b) — one BatchReplaySummary per policy.
        """
        summary_a = self.replay_batch(audit_records, policy_a)
        summary_b = self.replay_batch(audit_records, policy_b)
        return summary_a, summary_b


# =========================================================================
# Convenience: load from audit store and replay
# =========================================================================


def replay_recent_events(
    store: GovernanceAuditStore,
    policy_resolution: PolicyResolution,
    limit: int = 100,
) -> BatchReplaySummary:
    """Load recent audit records and replay under a policy.

    Convenience function that combines store query + batch replay.
    """
    records = store.list_recent(limit=limit)
    engine = PolicyReplayEngine()
    return engine.replay_batch(records, policy_resolution)


def replay_events_by_decision(
    store: GovernanceAuditStore,
    decision_outcome: str,
    policy_resolution: PolicyResolution,
    limit: int = 100,
) -> BatchReplaySummary:
    """Load audit records by decision outcome and replay under a policy."""
    records = store.list_by_decision(decision_outcome, limit=limit)
    engine = PolicyReplayEngine()
    return engine.replay_batch(records, policy_resolution)
