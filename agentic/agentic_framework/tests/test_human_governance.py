"""
Tests for H19 — Human Governance, Interactive Approval & Decision Authority.

Covers the required scenarios and all 10 evidence requirements:
1. Workflow pauses for an assigned reviewer (not an anonymous event).
2. Authorized approval resumes execution.
3. Unauthorized participant rejected before any workflow state change.
4. Request-changes triggers localized subtree replanning; siblings intact.
5. Delegation transfers responsibility while preserving the decision chain.
6. Escalation routes to a higher-authority participant.
7. A workflow checkpointed during review restores and continues.
8. Duplicate decisions ignored after restart.
9. One continuous trace reconstructs the whole governance history.
10. H10–H18 unchanged (full regression — separate).
"""

import pytest

from agentic.agentic_framework import (
    WorkingMemory,
    RunBudget,
    RunBudgetLimits,
    AgentProfile,
    CapabilityRegistry,
    ScriptedWorker,
    WorkerResult,
    Goal,
    GoalStatus,
    StaticDecomposer,
    WaitCondition,
    WaitKind,
    WorkflowStatus,
    InMemoryCheckpointStore,
    # H19
    HumanParticipant,
    ParticipantRegistry,
    HumanDecision,
    ReviewOutcome,
    ReviewStatus,
    ReviewManager,
    ReviewResultCode,
    format_review_trace,
)


def _workers():
    r = CapabilityRegistry()
    r.register(AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True, outputs={k: "ok" for k in c.expected_outputs})))
    return r


def _goals():
    return [
        Goal("api", "api", required_capabilities=frozenset({"do"}), expected_outputs=("api",), priority=1),
        Goal("ui", "ui", required_capabilities=frozenset({"do"}), expected_outputs=("ui",), priority=2),
        Goal("deploy", "deploy", required_capabilities=frozenset({"do"}),
             dependencies=("api", "ui"), expected_outputs=("rel",), priority=3),
    ]


def _gate():
    return WaitCondition("rev", "deploy", kind=WaitKind.WAIT_FOR_APPROVAL, event_type="appr", match=(("e", "p"),))


def _specs():
    return {"rev": {"assigned_participant": "lead", "required_authority": ["appr"], "deadline": 100, "priority": 1}}


def _people():
    return ParticipantRegistry([
        HumanParticipant("lead", "Security Lead", permissions=frozenset({"appr"}), trust_level=5, delegation_limit=1),
        HumanParticipant("peer", "Peer Lead", permissions=frozenset({"appr"}), trust_level=5),
        HumanParticipant("mgr", "Eng Manager", permissions=frozenset({"appr"}), trust_level=9),
        HumanParticipant("intern", "Intern", permissions=frozenset(), trust_level=1),
    ])


def _new(name, mgr):
    return mgr.create_workflow(name, StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                               run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_gate()],
                               review_specs=_specs())


def _decision(did, outcome, pid, **kw):
    return HumanDecision(did, outcome, pid, timestamp=kw.pop("ts", 2), **kw)


# ---------------------------------------------------------------------------
# Pause for an assigned reviewer
# ---------------------------------------------------------------------------
class TestReviewTaskCreation:
    def test_workflow_pauses_for_assigned_reviewer(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        assert wf.status == WorkflowStatus.WAITING
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED   # pre-review work done
        tasks = mgr.tasks_for(wf)
        assert len(tasks) == 1
        t = tasks[0]
        assert t.assigned_participant == "lead"
        assert t.goal_id == "deploy"
        assert t.status == ReviewStatus.ASSIGNED


# ---------------------------------------------------------------------------
# Approval / authority
# ---------------------------------------------------------------------------
class TestApprovalAndAuthority:
    def test_authorized_approval_resumes(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("d1", ReviewOutcome.APPROVED, "lead", rationale="ok"))
        assert res.code == ReviewResultCode.APPROVED
        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.tree.lookup("deploy").status == GoalStatus.COMPLETED
        # The decision is captured in H14 memory.
        assert wf.memory.peek("decision:deploy").value["outcome"] == "APPROVED"

    def test_unauthorized_rejected_before_state_change(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("d0", ReviewOutcome.APPROVED, "intern"))
        assert res.code == ReviewResultCode.AUTHORITY_DENIED
        # No workflow state changed.
        assert wf.status == WorkflowStatus.WAITING
        assert wf.tree.lookup("deploy").status == GoalStatus.BLOCKED

    def test_out_of_scope_participant_denied(self):
        people = ParticipantRegistry([
            HumanParticipant("scoped", "Scoped", permissions=frozenset({"appr"}),
                             approval_scope=frozenset({"some_other_goal"}), trust_level=5),
        ])
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), people)
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("d", ReviewOutcome.APPROVED, "scoped"))
        assert res.code == ReviewResultCode.AUTHORITY_DENIED


# ---------------------------------------------------------------------------
# Rejection / request changes
# ---------------------------------------------------------------------------
class TestRejectionAndChanges:
    def test_rejection_follows_deterministic_path(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("d", ReviewOutcome.REJECTED, "lead", rationale="unsafe"))
        assert res.code == ReviewResultCode.REJECTED
        assert wf.tree.lookup("deploy").status == GoalStatus.FAILED
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED   # sibling preserved
        assert wf.status == WorkflowStatus.FAILED

    def test_request_changes_localized_replan(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        changes = [Goal("deploy_fixed", "deploy fixed", required_capabilities=frozenset({"do"}), expected_outputs=("rel",))]
        res = mgr.submit_decision(wf, tid, _decision("d", ReviewOutcome.REQUEST_CHANGES, "lead",
                                                     rationale="fix config", change_goals=changes))
        assert res.code == ReviewResultCode.REQUEST_CHANGES
        # Only the reviewed leaf's subtree changed; siblings intact; mission completes.
        assert wf.tree.lookup("deploy").status == GoalStatus.ABORTED
        assert wf.tree.lookup("deploy_fixed").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("ui").status == GoalStatus.COMPLETED
        assert wf.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# Delegation
# ---------------------------------------------------------------------------
class TestDelegation:
    def test_delegation_records_chain_and_preserves_authority(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("dg", ReviewOutcome.DELEGATED, "lead",
                                                     target_participant_id="peer", rationale="you take it"))
        assert res.code == ReviewResultCode.DELEGATED
        task = mgr._load_task(wf, tid)
        assert task.assigned_participant == "peer"
        assert task.original_participant == "lead"
        assert [(d.from_participant, d.to_participant) for d in task.delegation_chain] == [("lead", "peer")]
        # The delegate (authorized) can now approve.
        res2 = mgr.submit_decision(wf, tid, _decision("ap", ReviewOutcome.APPROVED, "peer", ts=3))
        assert res2.code == ReviewResultCode.APPROVED and wf.status == WorkflowStatus.COMPLETED

    def test_delegation_to_unauthorized_denied(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("dg", ReviewOutcome.DELEGATED, "lead",
                                                     target_participant_id="intern"))
        assert res.code == ReviewResultCode.AUTHORITY_DENIED

    def test_delegation_limit_prevents_uncontrolled_chains(self):
        # 'lead' has delegation_limit=1; a second delegation would exceed it.
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        mgr.submit_decision(wf, tid, _decision("dg1", ReviewOutcome.DELEGATED, "lead", target_participant_id="peer"))
        # 'peer' has delegation_limit=0 → cannot delegate further.
        res = mgr.submit_decision(wf, tid, _decision("dg2", ReviewOutcome.DELEGATED, "peer",
                                                     target_participant_id="mgr", ts=3))
        assert res.code == ReviewResultCode.AUTHORITY_DENIED


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------
class TestEscalation:
    def test_escalation_to_higher_authority(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("e1", ReviewOutcome.ESCALATED, "lead",
                                                     target_participant_id="mgr", rationale="need sign-off"))
        assert res.code == ReviewResultCode.ESCALATED
        task = mgr._load_task(wf, tid)
        assert task.assigned_participant == "mgr"
        assert [(e.from_participant, e.to_participant) for e in task.escalation_chain] == [("lead", "mgr")]
        assert mgr.submit_decision(wf, tid, _decision("e2", ReviewOutcome.APPROVED, "mgr", ts=3)).code == ReviewResultCode.APPROVED
        assert wf.status == WorkflowStatus.COMPLETED

    def test_escalation_to_lower_authority_denied(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        res = mgr.submit_decision(wf, tid, _decision("e", ReviewOutcome.ESCALATED, "lead",
                                                     target_participant_id="intern"))
        assert res.code == ReviewResultCode.AUTHORITY_DENIED


# ---------------------------------------------------------------------------
# Checkpoint recovery + duplicate decisions
# ---------------------------------------------------------------------------
class TestRecoveryAndIdempotency:
    def test_pending_review_survives_restart(self):
        store = InMemoryCheckpointStore()
        mgr = ReviewManager(_workers(), store, _people())
        _new("cr", mgr)
        del mgr  # destroy runtime
        mgr2, wf2 = ReviewManager.restore(store, "cr", registry=_workers(), participants=_people())
        tasks = mgr2.tasks_for(wf2)
        assert wf2.status == WorkflowStatus.WAITING
        assert len(tasks) == 1 and tasks[0].status == ReviewStatus.ASSIGNED
        res = mgr2.submit_decision(wf2, tasks[0].task_id, _decision("rec", ReviewOutcome.APPROVED, "lead", ts=5))
        assert res.code == ReviewResultCode.APPROVED and wf2.status == WorkflowStatus.COMPLETED

    def test_duplicate_decision_ignored(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        mgr.submit_decision(wf, tid, _decision("d1", ReviewOutcome.APPROVED, "lead"))
        # Same decision again → the review is resolved / duplicate.
        res = mgr.submit_decision(wf, tid, _decision("d1", ReviewOutcome.APPROVED, "lead", ts=3))
        assert res.code in (ReviewResultCode.DUPLICATE_DECISION_IGNORED, ReviewResultCode.REVIEW_ALREADY_RESOLVED)

    def test_duplicate_decision_ignored_across_restart(self):
        store = InMemoryCheckpointStore()
        mgr = ReviewManager(_workers(), store, _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        # Delegate (non-terminal) so the task stays IN_REVIEW/ASSIGNED and its
        # processed decision id is persisted; then restart and re-deliver it.
        mgr.submit_decision(wf, tid, _decision("dupe", ReviewOutcome.DELEGATED, "lead", target_participant_id="peer"))
        del mgr, wf
        mgr2, wf2 = ReviewManager.restore(store, "wf", registry=_workers(), participants=_people())
        res = mgr2.submit_decision(wf2, tid, _decision("dupe", ReviewOutcome.DELEGATED, "lead",
                                                       target_participant_id="mgr", ts=9))
        assert res.code == ReviewResultCode.DUPLICATE_DECISION_IGNORED


# ---------------------------------------------------------------------------
# Trace / audit reconstruction
# ---------------------------------------------------------------------------
class TestAudit:
    def test_full_governance_history_reconstructs(self):
        mgr = ReviewManager(_workers(), InMemoryCheckpointStore(), _people())
        wf = _new("wf", mgr)
        tid = mgr.tasks_for(wf)[0].task_id
        mgr.submit_decision(wf, tid, _decision("e", ReviewOutcome.ESCALATED, "lead", target_participant_id="mgr"))
        mgr.submit_decision(wf, tid, _decision("a", ReviewOutcome.APPROVED, "mgr", ts=3))
        task = mgr._load_task(wf, tid)
        kinds = [h["kind"] for h in task.review_history]
        assert kinds[0] == "CREATED"
        assert "DECISION" in kinds
        assert task.escalation_chain  # escalation preserved
        # The workflow trace weaves review events into one lifecycle.
        wf_kinds = [e.kind for e in wf.trace.entries]
        assert "REVIEW_TASK_CREATED" in wf_kinds and "REVIEW_DECISION" in wf_kinds
        assert wf_kinds[-1] in ("COMPLETED", "CHECKPOINTED")
        assert "Review" in format_review_trace(task)
