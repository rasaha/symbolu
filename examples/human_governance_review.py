"""
H19 — Human Governance, Interactive Approval & Decision Authority (example).

Humans are first-class *governed runtime actors*.  A workflow suspends on a
review-gated wait condition; a named, authority-scoped participant reviews the
goal and issues a governed decision (approve / reject / request-changes /
delegate / escalate).  The decision is validated against the participant's
authority envelope BEFORE any workflow state changes, recorded append-only,
and — for a terminal decision — translated into the H17 event that satisfies
the wait, delivered through the unchanged H18 durable engine.  Review state
lives in H14 working memory, so it is checkpointed and restored for free.

Runs fully offline with scripted workers — no API key, no network, no UI, no
email.  Deterministic timestamps only.

Scope: H19 adds a governed human-decision layer.  It is NOT authentication,
identity management, electronic signatures, or a legally binding approval
system.  `identity_ref` is an opaque, caller-supplied reference — not proof of
identity.
"""

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
    HumanParticipant,
    ParticipantRegistry,
    HumanDecision,
    ReviewOutcome,
    ReviewManager,
    ReviewResultCode,
    format_review_trace,
)


def _registry():
    r = CapabilityRegistry()
    r.register(
        AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
        ScriptedWorker(lambda c, m: WorkerResult(success=True,
                                                 outputs={k: "ok" for k in c.expected_outputs})),
    )
    return r


def _goals():
    # api + ui run before review; deploy is the reviewed, gated goal.
    return [
        Goal("api", "build api", required_capabilities=frozenset({"do"}),
             expected_outputs=("api",), priority=1),
        Goal("ui", "build ui", required_capabilities=frozenset({"do"}),
             expected_outputs=("ui",), priority=2),
        Goal("deploy", "deploy to production", required_capabilities=frozenset({"do"}),
             dependencies=("api", "ui"), expected_outputs=("release",), priority=3),
    ]


def _gate():
    return WaitCondition("release_review", "deploy", kind=WaitKind.WAIT_FOR_APPROVAL,
                         event_type="release_approval", match=(("env", "prod"),))


def _specs():
    return {"release_review": {"assigned_participant": "lead",
                               "required_authority": ["approve_release"],
                               "deadline": 100, "priority": 1}}


def _people():
    return ParticipantRegistry([
        HumanParticipant("lead", "Security Lead",
                         permissions=frozenset({"approve_release"}), trust_level=5,
                         delegation_limit=1),
        HumanParticipant("peer", "Peer Lead",
                         permissions=frozenset({"approve_release"}), trust_level=5),
        HumanParticipant("mgr", "Eng Manager",
                         permissions=frozenset({"approve_release"}), trust_level=9),
        HumanParticipant("intern", "Intern", permissions=frozenset(), trust_level=1),
    ])


def _new(name, mgr):
    return mgr.create_workflow(
        name, StaticDecomposer().decompose("release", _goals()), WorkingMemory(),
        run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_gate()],
        review_specs=_specs())


def _rule(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def scenario_authorized_approval():
    _rule("1. Workflow pauses for a NAMED reviewer; authorized approval resumes")
    mgr = ReviewManager(_registry(), InMemoryCheckpointStore(), _people())
    wf = _new("wf1", mgr)
    task = mgr.tasks_for(wf)[0]
    print(f"  status            : {wf.status}   (not an anonymous wait)")
    print(f"  api / ui          : {wf.tree.lookup('api').status} / "
          f"{wf.tree.lookup('ui').status}   (pre-review work done)")
    print(f"  review assigned to: {task.assigned_participant}  for goal '{task.goal_id}'")

    res = mgr.submit_decision(wf, task.task_id,
                              HumanDecision("d1", ReviewOutcome.APPROVED, "lead",
                                            timestamp=2, rationale="ship it"))
    print(f"  decision          : {res.code}")
    print(f"  workflow          : {wf.status}   deploy={wf.tree.lookup('deploy').status}")
    print(f"  captured in memory: {wf.memory.peek('decision:deploy').value}")


def scenario_unauthorized_denied():
    _rule("2. Unauthorized participant denied BEFORE any workflow state change")
    mgr = ReviewManager(_registry(), InMemoryCheckpointStore(), _people())
    wf = _new("wf2", mgr)
    task = mgr.tasks_for(wf)[0]
    res = mgr.submit_decision(wf, task.task_id,
                              HumanDecision("d1", ReviewOutcome.APPROVED, "intern",
                                            timestamp=2, rationale="looks fine"))
    print(f"  intern decision   : {res.code}  ({res.reason})")
    print(f"  workflow unchanged: {wf.status}   deploy={wf.tree.lookup('deploy').status}")
    # The rightful reviewer can still act afterwards.
    res2 = mgr.submit_decision(wf, task.task_id,
                               HumanDecision("d2", ReviewOutcome.APPROVED, "lead", timestamp=3))
    print(f"  lead decision     : {res2.code}   workflow={wf.status}")


def scenario_request_changes():
    _rule("3. Request-changes → localized subtree replanning (siblings intact)")
    mgr = ReviewManager(_registry(), InMemoryCheckpointStore(), _people())
    wf = _new("wf3", mgr)
    task = mgr.tasks_for(wf)[0]
    fix = Goal("deploy_fixed", "deploy with rollback plan",
               required_capabilities=frozenset({"do"}), expected_outputs=("release",), priority=3)
    res = mgr.submit_decision(wf, task.task_id,
                              HumanDecision("d1", ReviewOutcome.REQUEST_CHANGES, "lead",
                                            timestamp=2, rationale="add rollback plan",
                                            change_goals=[fix]))
    print(f"  decision          : {res.code}")
    print(f"  original 'deploy'  : {wf.tree.lookup('deploy').status}   (aborted/replaced)")
    print(f"  new 'deploy_fixed' : {wf.tree.lookup('deploy_fixed').status}")
    print(f"  sibling 'api'      : {wf.tree.lookup('api').status}   (untouched)")
    print(f"  workflow           : {wf.status}")


def scenario_delegation_escalation():
    _rule("4. Delegation preserves the chain; escalation routes to higher authority")
    mgr = ReviewManager(_registry(), InMemoryCheckpointStore(), _people())
    wf = _new("wf4", mgr)
    task = mgr.tasks_for(wf)[0]

    # lead delegates to an equally-authorized peer (within delegation_limit=1).
    d = mgr.submit_decision(wf, task.task_id,
                            HumanDecision("d1", ReviewOutcome.DELEGATED, "lead", timestamp=2,
                                          target_participant_id="peer", rationale="I'm out today"))
    t = mgr.tasks_for(wf)[0]
    print(f"  delegate          : {d.code}   now assigned to '{t.assigned_participant}'")
    print(f"  delegation chain  : {[(r.from_participant, r.to_participant) for r in t.delegation_chain]}")

    # peer escalates to the manager (strictly higher trust_level).
    e = mgr.submit_decision(wf, task.task_id,
                            HumanDecision("d2", ReviewOutcome.ESCALATED, "peer", timestamp=3,
                                          target_participant_id="mgr", rationale="needs VP sign-off"))
    t = mgr.tasks_for(wf)[0]
    print(f"  escalate          : {e.code}   now assigned to '{t.assigned_participant}'")

    # manager approves; workflow completes.
    a = mgr.submit_decision(wf, task.task_id,
                            HumanDecision("d3", ReviewOutcome.APPROVED, "mgr", timestamp=4,
                                          rationale="approved"))
    print(f"  manager approval  : {a.code}   workflow={wf.status}")


def scenario_recovery_and_idempotency():
    _rule("5. Checkpoint during review → restore → resume; duplicate ignored")
    store = InMemoryCheckpointStore()
    registry, people = _registry(), _people()
    mgr = ReviewManager(registry, store, people)
    wf = _new("wf5", mgr)
    print(f"  before crash      : {wf.status}, {len(mgr.tasks_for(wf))} pending review(s)")

    # Process is destroyed; a brand-new manager + workflow are restored from disk.
    del mgr, wf
    mgr2, wf2 = ReviewManager.restore(store, "wf5", registry=registry, participants=people)
    task = mgr2.tasks_for(wf2)[0]
    print(f"  after restore     : {wf2.status}, review for '{task.goal_id}' "
          f"assigned to '{task.assigned_participant}'")

    res = mgr2.submit_decision(wf2, task.task_id,
                               HumanDecision("apX", ReviewOutcome.APPROVED, "lead", timestamp=5))
    print(f"  approve post-restore: {res.code}   workflow={wf2.status}")

    dup = mgr2.submit_decision(wf2, task.task_id,
                               HumanDecision("apX", ReviewOutcome.APPROVED, "lead", timestamp=6))
    print(f"  same decision again : {dup.code}   (no double-effect; workflow={wf2.status})")


def scenario_audit_trace():
    _rule("6. One continuous, reconstructable governance trace")
    mgr = ReviewManager(_registry(), InMemoryCheckpointStore(), _people())
    wf = _new("wf6", mgr)
    task = mgr.tasks_for(wf)[0]
    mgr.submit_decision(wf, task.task_id,
                        HumanDecision("d1", ReviewOutcome.DELEGATED, "lead", timestamp=2,
                                      target_participant_id="peer", rationale="cover for me"))
    mgr.submit_decision(wf, task.task_id,
                        HumanDecision("d2", ReviewOutcome.APPROVED, "peer", timestamp=3,
                                      rationale="approved"))
    print(format_review_trace(mgr.tasks_for(wf)[0]))


if __name__ == "__main__":
    scenario_authorized_approval()
    scenario_unauthorized_denied()
    scenario_request_changes()
    scenario_delegation_escalation()
    scenario_recovery_and_idempotency()
    scenario_audit_trace()
    print("\n" + "=" * 68)
    print("All H19 human-governance scenarios ran deterministically (no API key).")
    print("=" * 68)
