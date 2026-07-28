"""
Human Governance, Interactive Approval & Decision Authority (H19)
================================================================

Makes human participants **first-class governed actors** inside workflow
execution.  Reviews, approvals, overrides, delegations, and escalations become
explicit runtime objects rather than anonymous external events.

```
Workflow → Human Review Task → Assigned Reviewer
        → Approve / Reject / Request Changes / Delegate / Escalate
        → Governed Decision → Resume Workflow
```

The workflow no longer waits for an abstract event — it waits for an
authenticated, authorized, governed **decision**.  H17's wait semantics are
unchanged: H19 creates the review object that ultimately produces the event
that satisfies the H17 wait, delivered through the **unchanged** H18 durable
engine.

This phase introduces **deterministic human governance and interactive decision
authority** for long-lived workflows.  It is **not** enterprise identity
management, authentication, SSO/LDAP, electronic signatures, notifications, UI,
or a legally-binding approval system.  Human interaction is represented through
deterministic runtime APIs only.

H19 composes on public APIs and does not modify H10–H18, ActionGate, TAP, or the
authorization engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

from agentic.agentic_framework.working_memory import WorkingMemory, MemoryWrite
from agentic.agentic_framework.hierarchical_planning import Goal, GoalStatus, GoalTree, MissionPlan
from agentic.agentic_framework.coordination import CapabilityRegistry, AuthorityModel
from agentic.agentic_framework.event_workflows import WaitCondition, WorkflowEvent, WorkflowInstance
from agentic.agentic_framework.workflow_durability import (
    DurableWorkflowEngine, CheckpointStore, EventOutcome,
)

__all__ = [
    "ReviewOutcome",
    "ReviewStatus",
    "ReviewResultCode",
    "HumanParticipant",
    "ParticipantRegistry",
    "HumanDecision",
    "DelegationRecord",
    "EscalationRecord",
    "ReviewTask",
    "HumanAuthorityValidator",
    "ReviewResult",
    "ReviewManager",
    "format_review_trace",
]

#: Reserved WorkingMemory key prefix for durable review state (checkpointed by H18).
REVIEW_KEY_PREFIX = "__review__:"


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class ReviewOutcome:
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    DELEGATED = "DELEGATED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


class ReviewStatus:
    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


_TERMINAL_REVIEW = {ReviewStatus.COMPLETED, ReviewStatus.CANCELLED, ReviewStatus.EXPIRED}


class ReviewResultCode:
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    DELEGATED = "DELEGATED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    DUPLICATE_DECISION_IGNORED = "DUPLICATE_DECISION_IGNORED"
    REVIEW_ALREADY_RESOLVED = "REVIEW_ALREADY_RESOLVED"


# ---------------------------------------------------------------------------
# Human actor model (immutable during execution)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HumanParticipant:
    """An immutable description of a human reviewer's authority envelope."""

    participant_id: str
    display_name: str = ""
    authority_roles: FrozenSet[str] = frozenset()
    permissions: FrozenSet[str] = frozenset()
    trust_level: int = 0
    organizational_unit: str = ""
    delegation_limit: int = 0            # max delegation-chain length this actor may extend
    approval_scope: FrozenSet[str] = frozenset()   # goal ids (empty = any)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "participant_id": self.participant_id, "display_name": self.display_name,
            "authority_roles": sorted(self.authority_roles), "permissions": sorted(self.permissions),
            "trust_level": self.trust_level, "organizational_unit": self.organizational_unit,
            "delegation_limit": self.delegation_limit, "approval_scope": sorted(self.approval_scope),
        }


class ParticipantRegistry:
    """A named registry of human participants (a rebindable runtime dependency)."""

    def __init__(self, participants: Optional[List[HumanParticipant]] = None) -> None:
        self._participants: Dict[str, HumanParticipant] = {}
        for p in participants or []:
            self.register(p)

    def register(self, participant: HumanParticipant) -> "ParticipantRegistry":
        if participant.participant_id in self._participants:
            raise ValueError(f"participant '{participant.participant_id}' already registered")
        self._participants[participant.participant_id] = participant
        return self

    def get(self, participant_id: str) -> Optional[HumanParticipant]:
        return self._participants.get(participant_id)

    def has(self, participant_id: str) -> bool:
        return participant_id in self._participants

    def ids(self) -> List[str]:
        return list(self._participants)


# ---------------------------------------------------------------------------
# Decision / delegation / escalation records (append-only)
# ---------------------------------------------------------------------------
@dataclass
class HumanDecision:
    """A governed human decision.  Append-only once recorded on a task."""

    decision_id: str
    outcome: str
    participant_id: str
    timestamp: float = 0.0
    rationale: str = ""
    evidence: List[str] = field(default_factory=list)
    workflow_id: str = ""
    goal_id: str = ""
    identity_ref: str = ""              # opaque digital-identity reference (not authentication)
    trace_position: int = -1
    target_participant_id: Optional[str] = None   # delegate / escalate target
    memory_writes: List[MemoryWrite] = field(default_factory=list)
    assumption_signals: Dict[str, str] = field(default_factory=dict)
    change_goals: List[Goal] = field(default_factory=list)   # REQUEST_CHANGES replacement goals

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id, "outcome": self.outcome, "participant_id": self.participant_id,
            "timestamp": self.timestamp, "rationale": self.rationale, "evidence": list(self.evidence),
            "workflow_id": self.workflow_id, "goal_id": self.goal_id, "identity_ref": self.identity_ref,
            "trace_position": self.trace_position, "target_participant_id": self.target_participant_id,
            "memory_writes": [w.key for w in self.memory_writes],
            "assumption_signals": dict(self.assumption_signals),
            "change_goals": [g.goal_id for g in self.change_goals],
        }


@dataclass
class DelegationRecord:
    from_participant: str
    to_participant: str
    timestamp: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"from_participant": self.from_participant, "to_participant": self.to_participant,
                "timestamp": self.timestamp, "reason": self.reason}


@dataclass
class EscalationRecord:
    from_participant: str
    to_participant: str
    timestamp: float = 0.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"from_participant": self.from_participant, "to_participant": self.to_participant,
                "timestamp": self.timestamp, "reason": self.reason}


# ---------------------------------------------------------------------------
# Review task
# ---------------------------------------------------------------------------
@dataclass
class ReviewTask:
    """An explicit, governed human review of a workflow goal."""

    task_id: str
    workflow_id: str
    goal_id: str
    condition_id: str                    # the H17 wait condition this review satisfies
    assigned_participant: str
    original_participant: str
    required_authority: FrozenSet[str] = frozenset()
    deadline: Optional[float] = None
    priority: int = 0
    status: str = ReviewStatus.ASSIGNED
    review_history: List[Dict[str, Any]] = field(default_factory=list)   # append-only audit
    processed_decision_ids: List[str] = field(default_factory=list)
    delegation_chain: List[DelegationRecord] = field(default_factory=list)
    escalation_chain: List[EscalationRecord] = field(default_factory=list)

    # ----- append-only history -----
    def record(self, kind: str, detail: Dict[str, Any], timestamp: float) -> None:
        self.review_history.append({"kind": kind, "detail": detail, "timestamp": timestamp})

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_REVIEW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id, "workflow_id": self.workflow_id, "goal_id": self.goal_id,
            "condition_id": self.condition_id, "assigned_participant": self.assigned_participant,
            "original_participant": self.original_participant, "required_authority": sorted(self.required_authority),
            "deadline": self.deadline, "priority": self.priority, "status": self.status,
            "review_history": list(self.review_history), "processed_decision_ids": list(self.processed_decision_ids),
            "delegation_chain": [d.to_dict() for d in self.delegation_chain],
            "escalation_chain": [e.to_dict() for e in self.escalation_chain],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewTask":
        t = cls(
            task_id=d["task_id"], workflow_id=d["workflow_id"], goal_id=d["goal_id"],
            condition_id=d["condition_id"], assigned_participant=d["assigned_participant"],
            original_participant=d["original_participant"],
            required_authority=frozenset(d.get("required_authority", [])),
            deadline=d.get("deadline"), priority=d.get("priority", 0), status=d["status"],
            review_history=list(d.get("review_history", [])),
            processed_decision_ids=list(d.get("processed_decision_ids", [])),
        )
        t.delegation_chain = [DelegationRecord(**x) for x in d.get("delegation_chain", [])]
        t.escalation_chain = [EscalationRecord(**x) for x in d.get("escalation_chain", [])]
        return t


# ---------------------------------------------------------------------------
# Human authority validation (reuses the H16 subset-check pattern)
# ---------------------------------------------------------------------------
@dataclass
class AuthorityVerdict:
    ok: bool
    reason: str = ""


class HumanAuthorityValidator:
    """Deterministic human authority checks.

    Mirrors the H16 :class:`AuthorityModel` subset-check discipline: a
    participant may act only within granted authority, evaluated in a fixed
    order so denials are deterministic.
    """

    def can_decide(self, participant: HumanParticipant, task: ReviewTask) -> AuthorityVerdict:
        if participant is None:
            return AuthorityVerdict(False, "unknown participant")
        missing = task.required_authority - participant.permissions
        if missing:
            return AuthorityVerdict(False, f"missing authority: {sorted(missing)}")
        if participant.approval_scope and task.goal_id not in participant.approval_scope:
            return AuthorityVerdict(False, f"goal '{task.goal_id}' outside approval scope")
        return AuthorityVerdict(True)

    def can_delegate(self, participant: HumanParticipant, target: Optional[HumanParticipant],
                     task: ReviewTask) -> AuthorityVerdict:
        base = self.can_decide(participant, task)
        if not base.ok:
            return base
        if target is None:
            return AuthorityVerdict(False, "unknown delegation target")
        # Delegation must remain within authority: the delegate must also be
        # authorized for the task.
        if task.required_authority - target.permissions:
            return AuthorityVerdict(False, "delegate lacks required authority")
        # No uncontrolled delegation chains: bounded by the delegator's limit.
        if len(task.delegation_chain) >= max(participant.delegation_limit, 0):
            return AuthorityVerdict(False, "delegation limit exceeded")
        return AuthorityVerdict(True)

    def can_escalate(self, participant: HumanParticipant, target: Optional[HumanParticipant],
                     task: ReviewTask) -> AuthorityVerdict:
        if participant is None:
            return AuthorityVerdict(False, "unknown participant")
        if target is None:
            return AuthorityVerdict(False, "unknown escalation target")
        # Escalation routes to strictly-or-equal higher authority.
        if target.trust_level < participant.trust_level:
            return AuthorityVerdict(False, "escalation target has lower authority")
        if task.required_authority - target.permissions:
            return AuthorityVerdict(False, "escalation target lacks required authority")
        return AuthorityVerdict(True)


# ---------------------------------------------------------------------------
# Review result
# ---------------------------------------------------------------------------
@dataclass
class ReviewResult:
    code: str
    task: Optional[ReviewTask] = None
    reason: str = ""
    event_outcome: Optional[str] = None   # underlying H18 event outcome, if any

    @property
    def ok(self) -> bool:
        return self.code not in (ReviewResultCode.AUTHORITY_DENIED,
                                 ReviewResultCode.DUPLICATE_DECISION_IGNORED,
                                 ReviewResultCode.REVIEW_ALREADY_RESOLVED)


# ---------------------------------------------------------------------------
# Review manager (composes the unchanged H18 durable engine)
# ---------------------------------------------------------------------------
class ReviewManager:
    """Governs human review of workflows on top of the H18 durable engine.

    Creates review tasks when a workflow suspends on a review-gated wait
    condition, validates and records governed decisions, and translates a
    terminal decision into the H17 event that satisfies the wait — delivered
    through the unchanged H18 engine.  Review state is stored in H14
    ``WorkingMemory`` so H18 checkpoints and restores it automatically.
    """

    def __init__(self, registry: CapabilityRegistry, store: CheckpointStore,
                 participants: ParticipantRegistry, *,
                 validator: Optional[HumanAuthorityValidator] = None,
                 authority: Optional[AuthorityModel] = None) -> None:
        self.participants = participants
        self.validator = validator or HumanAuthorityValidator()
        self.durable = DurableWorkflowEngine(registry, store, authority=authority)
        self._tasks: Dict[str, ReviewTask] = {}

    # ----- workflow creation with review gates -----
    def create_workflow(self, workflow_id: str, plan: MissionPlan, memory: WorkingMemory, *,
                        assumption_context: Optional[Any] = None, run_budget: Optional[Any] = None,
                        wait_conditions: Optional[List[WaitCondition]] = None,
                        review_specs: Optional[Dict[str, Dict[str, Any]]] = None,
                        created_at: float = 0.0) -> WorkflowInstance:
        wf = self.durable.create_workflow(workflow_id, plan, memory,
                                          assumption_context=assumption_context, run_budget=run_budget,
                                          wait_conditions=wait_conditions, created_at=created_at)
        self._open_reviews(wf, review_specs or {}, timestamp=created_at)
        return wf

    def _open_reviews(self, wf: WorkflowInstance, review_specs: Dict[str, Dict[str, Any]],
                      *, timestamp: float) -> None:
        opened = False
        for wc in wf.waiting_conditions:
            spec = review_specs.get(wc.condition_id)
            if spec is None or self._find_task_for_condition(wf, wc.condition_id) is not None:
                continue
            assignee = spec["assigned_participant"]
            task = ReviewTask(
                task_id=f"review:{wf.workflow_id}:{wc.condition_id}",
                workflow_id=wf.workflow_id, goal_id=wc.goal_id, condition_id=wc.condition_id,
                assigned_participant=assignee, original_participant=assignee,
                required_authority=frozenset(spec.get("required_authority", [])),
                deadline=spec.get("deadline"), priority=spec.get("priority", 0),
                status=ReviewStatus.ASSIGNED,
            )
            task.record("CREATED", {"assignee": assignee, "goal": wc.goal_id}, timestamp)
            self._tasks[task.task_id] = task
            self._persist(wf, task, timestamp=timestamp)
            wf.trace.record("REVIEW_TASK_CREATED", {"task_id": task.task_id, "assignee": assignee,
                                                    "goal": wc.goal_id}, timestamp)
            opened = True
        if opened:
            self.durable.checkpoint(wf, reason="after_review_open")

    # ----- decision submission -----
    def submit_decision(self, wf: WorkflowInstance, task_id: str,
                        decision: HumanDecision) -> ReviewResult:
        task = self._load_task(wf, task_id)
        if task is None:
            return ReviewResult(ReviewResultCode.REVIEW_ALREADY_RESOLVED, reason="no such task")
        if task.is_terminal():
            return ReviewResult(ReviewResultCode.REVIEW_ALREADY_RESOLVED, task=task)
        if decision.decision_id in task.processed_decision_ids:
            wf.trace.record("DUPLICATE_DECISION_IGNORED", {"decision_id": decision.decision_id}, decision.timestamp)
            return ReviewResult(ReviewResultCode.DUPLICATE_DECISION_IGNORED, task=task)

        participant = self.participants.get(decision.participant_id)

        # --- authority validation BEFORE any workflow state change ---
        if decision.outcome == ReviewOutcome.DELEGATED:
            target = self.participants.get(decision.target_participant_id)
            verdict = self.validator.can_delegate(participant, target, task)
        elif decision.outcome == ReviewOutcome.ESCALATED:
            target = self.participants.get(decision.target_participant_id)
            verdict = self.validator.can_escalate(participant, target, task)
        else:
            verdict = self.validator.can_decide(participant, task)
        if not verdict.ok:
            wf.trace.record("REVIEW_AUTHORITY_DENIED", {"participant": decision.participant_id,
                                                        "reason": verdict.reason}, decision.timestamp)
            return ReviewResult(ReviewResultCode.AUTHORITY_DENIED, task=task, reason=verdict.reason)

        # --- record the governed decision (append-only) ---
        task.status = ReviewStatus.IN_REVIEW
        task.processed_decision_ids.append(decision.decision_id)
        task.record("DECISION", decision.to_dict(), decision.timestamp)
        wf.trace.record("REVIEW_DECISION", {"task_id": task_id, "outcome": decision.outcome,
                                            "participant": decision.participant_id}, decision.timestamp)

        outcome = decision.outcome
        if outcome == ReviewOutcome.DELEGATED:
            rec = DelegationRecord(task.assigned_participant, decision.target_participant_id,
                                   decision.timestamp, decision.rationale)
            task.delegation_chain.append(rec)
            task.assigned_participant = decision.target_participant_id
            task.status = ReviewStatus.ASSIGNED
            self._persist(wf, task, timestamp=decision.timestamp)
            self.durable.checkpoint(wf, reason="after_delegation")
            return ReviewResult(ReviewResultCode.DELEGATED, task=task)

        if outcome == ReviewOutcome.ESCALATED:
            rec = EscalationRecord(task.assigned_participant, decision.target_participant_id,
                                   decision.timestamp, decision.rationale)
            task.escalation_chain.append(rec)
            task.assigned_participant = decision.target_participant_id
            task.status = ReviewStatus.ASSIGNED
            self._persist(wf, task, timestamp=decision.timestamp)
            self.durable.checkpoint(wf, reason="after_escalation")
            return ReviewResult(ReviewResultCode.ESCALATED, task=task)

        if outcome == ReviewOutcome.CANCELLED:
            task.status = ReviewStatus.CANCELLED
            self._persist(wf, task, timestamp=decision.timestamp)
            self.durable.checkpoint(wf, reason="after_review_cancel")
            return ReviewResult(ReviewResultCode.CANCELLED, task=task)

        # --- terminal decisions that resolve the H17 wait ---
        task.status = ReviewStatus.COMPLETED
        if outcome == ReviewOutcome.REJECTED:
            # Deterministic rejection: the reviewed goal fails; the wait is then
            # resolved (the goal is already terminal, so it never executes).
            wf.tree.lookup(task.goal_id).transition(
                GoalStatus.FAILED, reason=f"rejected by {decision.participant_id}", timestamp=decision.timestamp)
        elif outcome == ReviewOutcome.REQUEST_CHANGES:
            # H15/H12 localized replanning: replace ONLY the reviewed leaf's
            # subtree with the requested changes; completed siblings are intact.
            wf.tree.replace_leaf(task.goal_id, list(decision.change_goals))
        self._persist(wf, task, timestamp=decision.timestamp)

        # Build the event that satisfies the H17 wait, then deliver via H18.
        event = self._decision_event(wf, task, decision)
        result = self.durable.deliver(wf, event)
        code = {ReviewOutcome.APPROVED: ReviewResultCode.APPROVED,
                ReviewOutcome.REJECTED: ReviewResultCode.REJECTED,
                ReviewOutcome.REQUEST_CHANGES: ReviewResultCode.REQUEST_CHANGES}[outcome]
        return ReviewResult(code, task=task, event_outcome=result.outcome)

    # ----- event construction -----
    def _decision_event(self, wf: WorkflowInstance, task: ReviewTask,
                        decision: HumanDecision) -> WorkflowEvent:
        wc = wf.wait_by_goal.get(task.goal_id)
        writes = list(decision.memory_writes)
        # An approval/decision record is always captured in H14 memory.
        writes.append(MemoryWrite(f"decision:{task.goal_id}",
                                  {"outcome": decision.outcome, "by": decision.participant_id,
                                   "rationale": decision.rationale}, category="governance"))
        payload = dict(wc.match_dict()) if wc is not None else {}
        return WorkflowEvent(
            event_id=decision.decision_id,
            type=wc.event_type if wc is not None else "human_decision",
            payload=payload, timestamp=decision.timestamp, source=f"human:{decision.participant_id}",
            confidence=1.0, memory_writes=writes, assumption_signals=dict(decision.assumption_signals),
        )

    # ----- durable review state (via H14 memory → H18 checkpoint) -----
    def _key(self, task_id: str) -> str:
        return f"{REVIEW_KEY_PREFIX}{task_id}"

    def _persist(self, wf: WorkflowInstance, task: ReviewTask, *, timestamp: float) -> None:
        wf.memory.write(self._key(task.task_id), task.to_dict(), category="review",
                        provenance="review_manager", producing_step="review_manager", timestamp=timestamp)
        self._tasks[task.task_id] = task

    def _load_task(self, wf: WorkflowInstance, task_id: str) -> Optional[ReviewTask]:
        if task_id in self._tasks:
            return self._tasks[task_id]
        rec = wf.memory.peek(self._key(task_id))
        if rec is None:
            return None
        task = ReviewTask.from_dict(rec.value)
        self._tasks[task_id] = task
        return task

    def _find_task_for_condition(self, wf: WorkflowInstance, condition_id: str) -> Optional[ReviewTask]:
        for key in wf.memory.keys():
            if key.startswith(REVIEW_KEY_PREFIX):
                rec = wf.memory.peek(key)
                if rec and rec.value.get("condition_id") == condition_id:
                    return ReviewTask.from_dict(rec.value)
        return None

    def tasks_for(self, wf: WorkflowInstance) -> List[ReviewTask]:
        out = []
        for key in wf.memory.keys():
            if key.startswith(REVIEW_KEY_PREFIX):
                rec = wf.memory.peek(key)
                if rec:
                    out.append(ReviewTask.from_dict(rec.value))
        return out

    # ----- recovery -----
    @classmethod
    def restore(cls, store: CheckpointStore, workflow_id: str, *, registry: CapabilityRegistry,
                participants: ParticipantRegistry, authority: Optional[AuthorityModel] = None
                ) -> Tuple["ReviewManager", WorkflowInstance]:
        """Restore a workflow AND its pending reviews after process loss."""
        manager = cls(registry, store, participants, authority=authority)
        engine, wf = DurableWorkflowEngine.restore(
            store, workflow_id, registry=registry, authority=authority)
        manager.durable = engine
        # Re-hydrate review tasks from the restored WorkingMemory.
        for task in manager.tasks_for(wf):
            manager._tasks[task.task_id] = task
        return manager, wf


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_review_trace(task: ReviewTask) -> str:
    lines = [f"Review {task.task_id}  status={task.status}  goal={task.goal_id}",
             f"assignee={task.assigned_participant} (originally {task.original_participant})",
             "-" * 52]
    for e in task.review_history:
        detail = e["detail"]
        if e["kind"] == "DECISION":
            lines.append(f"  {e['kind']}: {detail.get('outcome')} by {detail.get('participant_id')} "
                         f"— {detail.get('rationale','')}")
        else:
            lines.append(f"  {e['kind']}: {detail}")
    for d in task.delegation_chain:
        lines.append(f"  delegated {d.from_participant} → {d.to_participant}")
    for esc in task.escalation_chain:
        lines.append(f"  escalated {esc.from_participant} → {esc.to_participant}")
    return "\n".join(lines)
