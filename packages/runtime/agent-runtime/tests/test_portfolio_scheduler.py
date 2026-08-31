"""H22-B — deterministic multi-workflow coordination (portfolio + scheduler).

These tests exercise the orchestration layer that decides WHICH prepared workflow receives
the next H22-A execution quantum, and why. They prove the coordination properties the phase
requires — deterministic selection, priority, bounded aging, fairness, dependency
resolution, and governance isolation — WITHOUT the scheduler ever authorizing a task,
resuming a HOLD/ESCALATE, calling a provider directly, or weakening exact-action binding.

The scheduler reaches execution ONLY through ``runtime.advance_workflow`` (the unchanged
H22-A seam), so every consequential quantum still crosses fresh governance below H22-B.
"""
from __future__ import annotations

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    DependencyType,
    PortfolioScheduler,
    PortfolioStepReason,
    SchedulingPolicy,
    TaskDefinition,
    WorkflowDefinition,
    WorkflowEligibility,
    WorkflowPriority,
    WorkflowStatus,
    advance_workflow,
    create_portfolio,
    create_portfolio_scheduler,
    create_runtime,
    prepare_workflow,
    register_provider,
    start_workflow,
)
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.orchestration.dependencies import (
    DependencyGraph,
    DependencyState,
    WorkflowDependency,
)
from ugence_agent_runtime.persistence.in_memory import InMemoryCheckpointStore

from art_fakes import RecordingProvider


# --------------------------------------------------------------------------- #
# helpers / test doubles                                                       #
# --------------------------------------------------------------------------- #
def _task(tid, *, consequential=True, depends_on=()):
    return TaskDefinition(
        task_id=tid, operation=tid, provider_id="p",
        depends_on=tuple(depends_on), consequential=consequential,
    )


def _wf(workflow_id, *task_ids, chain=False):
    """A workflow of one or more tasks; when ``chain`` is set each task depends on the
    previous, so exactly one task is runnable per quantum."""
    tasks = []
    prev = None
    for tid in task_ids:
        deps = (prev,) if (chain and prev is not None) else ()
        tasks.append(_task(tid, depends_on=deps))
        prev = tid
    return WorkflowDefinition(workflow_id=workflow_id, tasks=tuple(tasks))


class CountingProvider(RecordingProvider):
    pass


class MappedGovernanceHook(GovernanceHook):
    """Governance hook returning a per-workflow disposition (default CLEAR, bound).

    Lets one runtime drive several workflows while giving workflow A a HOLD/ESCALATE/BLOCK
    while B/C proceed. CLEAR results bind the exact proposal fingerprint so the runtime's
    exact-action check passes; restrictive dispositions are returned unbound (binding is
    irrelevant to WAIT/PAUSE/STOP)."""

    def __init__(self, default=GovernanceDisposition.CLEAR):
        self.default = default
        self.by_workflow = {}
        self.evaluations = []

    def set(self, workflow_id, disposition):
        self.by_workflow[workflow_id] = disposition

    def evaluate(self, proposal, evaluation_time) -> GovernanceEvaluation:
        self.evaluations.append((proposal.workflow_id, proposal.task_id))
        disp = self.by_workflow.get(proposal.workflow_id, self.default)
        clear = disp is GovernanceDisposition.CLEAR
        return GovernanceEvaluation(
            disposition=disp,
            proposal_fingerprint=proposal.fingerprint if clear else None,
            reason_codes=("TEST",),
            evaluation_reference="gov-ref" if clear else None,
            valid_until=None,
            correlation_reference=proposal.correlation_id,
        )


def _runtime(hook=None, provider=None):
    cfg = AgentRuntimeConfig(governance_hook=hook or AllowAllGovernanceHook())
    rt = create_runtime(cfg)
    register_provider(rt, provider or CountingProvider("p"))
    return rt


def _drive(rt, portfolio, rounds):
    """Step a portfolio ``rounds`` times, returning the list of step results."""
    return [portfolio_scheduler_step(rt, portfolio) for _ in range(rounds)]


def portfolio_scheduler_step(rt, portfolio, policy=None):
    return PortfolioScheduler(rt, policy).step(portfolio)


# --------------------------------------------------------------------------- #
# A. Registration                                                             #
# --------------------------------------------------------------------------- #
def test_register_single_and_multiple_stable_sequence():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    ea = p.register(a.instance_id, runtime=rt)
    eb = p.register(b.instance_id, runtime=rt)
    assert ea.registration_sequence == 0
    assert eb.registration_sequence == 1
    assert p.instance_ids == (a.instance_id, b.instance_id)


def test_registration_is_idempotent_and_identity_immutable():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1"))
    p = create_portfolio("p1")
    first = p.register(a.instance_id, runtime=rt, priority=WorkflowPriority.HIGH, weight=2.0)
    # Re-registering returns the SAME entry unchanged (priority/weight/sequence immutable).
    again = p.register(a.instance_id, runtime=rt, priority=WorkflowPriority.LOW, weight=9.0)
    assert again is first
    assert again.priority is WorkflowPriority.HIGH
    assert again.weight == 2.0
    assert again.registration_sequence == 0
    assert len(p.entries()) == 1


def test_register_unknown_instance_rejected():
    rt = _runtime()
    p = create_portfolio("p1")
    with pytest.raises(ValueError):
        p.register("no-such-instance", runtime=rt)


def test_registration_causes_no_execution():
    provider = CountingProvider("p")
    hook = MappedGovernanceHook()
    rt = _runtime(hook, provider)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    # Merely registering ran nothing.
    assert provider.calls == []
    assert hook.evaluations == []
    assert rt.instance(a.instance_id).task("A1").status is TaskStatus.PENDING


# --------------------------------------------------------------------------- #
# B. Dependency graph structure                                               #
# --------------------------------------------------------------------------- #
def test_linear_chain_depths():
    g = DependencyGraph(
        ["A", "B", "C"],
        [WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS),
         WorkflowDependency("C", "B", DependencyType.REQUIRES_SUCCESS)],
    )
    assert g.depth("A") == 0
    assert g.depth("B") == 1
    assert g.depth("C") == 2


def test_diamond_dependency_depth_is_longest_path():
    # A -> B, A -> C, B -> D, C -> D  (D depends on B and C, both depend on A)
    g = DependencyGraph(
        ["A", "B", "C", "D"],
        [WorkflowDependency("B", "A"), WorkflowDependency("C", "A"),
         WorkflowDependency("D", "B"), WorkflowDependency("D", "C")],
    )
    assert g.depth("A") == 0
    assert g.depth("B") == 1
    assert g.depth("C") == 1
    assert g.depth("D") == 2


def test_self_dependency_rejected():
    with pytest.raises(ValueError):
        DependencyGraph(["A"], [WorkflowDependency("A", "A")])


def test_unknown_workflow_dependency_rejected():
    with pytest.raises(ValueError):
        DependencyGraph(["A"], [WorkflowDependency("A", "ghost")])


def test_direct_cycle_rejected():
    with pytest.raises(ValueError):
        DependencyGraph(
            ["A", "B"],
            [WorkflowDependency("A", "B"), WorkflowDependency("B", "A")],
        )


def test_indirect_cycle_rejected():
    with pytest.raises(ValueError):
        DependencyGraph(
            ["A", "B", "C"],
            [WorkflowDependency("A", "B"), WorkflowDependency("B", "C"),
             WorkflowDependency("C", "A")],
        )


def test_duplicate_edge_is_idempotent_conflicting_type_rejected():
    g = DependencyGraph(
        ["A", "B"],
        [WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS),
         WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS)],
    )
    assert len(g.edges) == 1
    with pytest.raises(ValueError):
        DependencyGraph(
            ["A", "B"],
            [WorkflowDependency("B", "A", DependencyType.REQUIRES_SUCCESS),
             WorkflowDependency("B", "A", DependencyType.REQUIRES_COMPLETION)],
        )


def test_portfolio_add_dependency_cycle_rejected_no_partial_state():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.add_dependency(b.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
    with pytest.raises(ValueError):
        p.add_dependency(a.instance_id, b.instance_id, DependencyType.REQUIRES_SUCCESS)
    # The rejected edge left no partial state: graph is still the single valid edge.
    assert len(p.dependency_graph().edges) == 1


# --------------------------------------------------------------------------- #
# C/D. Completion vs success dependency semantics                             #
# --------------------------------------------------------------------------- #
def test_completion_dependency_blocks_until_predecessor_terminal():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1", "A2", chain=True))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.add_dependency(b.instance_id, a.instance_id, DependencyType.REQUIRES_COMPLETION)
    sched = create_portfolio_scheduler(rt)

    # B must never be selected until A is terminal (COMPLETED).
    selected_b_before_a_terminal = False
    for _ in range(3):  # A needs A1, A2, finalize
        r = sched.step(p)
        if r.selected_instance_id == b.instance_id:
            selected_b_before_a_terminal = True
    assert rt.instance(a.instance_id).status is WorkflowStatus.COMPLETED
    assert not selected_b_before_a_terminal
    # Now B is eligible.
    r = sched.step(p)
    assert r.selected_instance_id == b.instance_id


def test_success_dependency_blocks_when_predecessor_fails():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)  # A will FAIL on governance BLOCK
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.add_dependency(b.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)

    # Drive A to FAILED first (A is eligible; B is eligible independently too, so drive a
    # few rounds). B requires A SUCCESS, so once A FAILED, B must be BLOCKED_DEPENDENCY.
    for _ in range(4):
        sched.step(p)
    assert rt.instance(a.instance_id).status is WorkflowStatus.FAILED
    cls = dict((e.instance_id, c) for e, c in sched.classify(p))
    assert cls[b.instance_id] is WorkflowEligibility.BLOCKED_DEPENDENCY


def test_completion_dependency_satisfied_even_if_predecessor_failed():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.add_dependency(b.instance_id, a.instance_id, DependencyType.REQUIRES_COMPLETION)
    sched = create_portfolio_scheduler(rt)
    for _ in range(4):
        sched.step(p)
    assert rt.instance(a.instance_id).status is WorkflowStatus.FAILED
    cls = dict((e.instance_id, c) for e, c in sched.classify(p))
    # COMPLETION is permissive: a terminal (even FAILED) predecessor releases the dependent.
    assert cls[b.instance_id] in (
        WorkflowEligibility.ELIGIBLE, WorkflowEligibility.TERMINAL
    )


# --------------------------------------------------------------------------- #
# E. Eligibility mapping from runtime status                                  #
# --------------------------------------------------------------------------- #
def test_eligibility_maps_runtime_states():
    hook = MappedGovernanceHook()
    hook.set("H", GovernanceDisposition.HOLD)
    hook.set("E", GovernanceDisposition.ESCALATE)
    rt = _runtime(hook)
    run = prepare_workflow(rt, _wf("R", "R1"))        # stays RUNNING
    hold = prepare_workflow(rt, _wf("H", "H1"))       # -> WAITING (HOLD)
    esc = prepare_workflow(rt, _wf("E", "E1"))        # -> PAUSED (ESCALATE)
    done = start_workflow(rt, _wf("D", "D1"))         # COMPLETED (terminal)
    p = create_portfolio("p1")
    for inst in (run, hold, esc, done):
        p.register(inst.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    advance_workflow(rt, hold.instance_id)            # trigger HOLD -> WAITING
    advance_workflow(rt, esc.instance_id)             # trigger ESCALATE -> PAUSED
    cls = dict((e.instance_id, c) for e, c in sched.classify(p))
    assert cls[run.instance_id] is WorkflowEligibility.ELIGIBLE
    assert cls[hold.instance_id] is WorkflowEligibility.WAITING_RUNTIME
    assert cls[esc.instance_id] is WorkflowEligibility.PAUSED
    assert cls[done.instance_id] is WorkflowEligibility.TERMINAL


# --------------------------------------------------------------------------- #
# F. Priority                                                                 #
# --------------------------------------------------------------------------- #
def test_higher_priority_selected_first():
    rt = _runtime()
    low = prepare_workflow(rt, _wf("LOW", "l1"))
    high = prepare_workflow(rt, _wf("HIGH", "h1"))
    p = create_portfolio("p1")
    p.register(low.instance_id, runtime=rt, priority=WorkflowPriority.LOW)
    p.register(high.instance_id, runtime=rt, priority=WorkflowPriority.HIGH)
    r = create_portfolio_scheduler(rt).step(p)
    assert r.selected_instance_id == high.instance_id
    assert r.selection_reason.base_priority == "HIGH"


def test_priority_cannot_bypass_dependency():
    rt = _runtime()
    dep = prepare_workflow(rt, _wf("DEP", "d1", "d2", chain=True))  # NORMAL, upstream
    crit = prepare_workflow(rt, _wf("CRIT", "c1"))                  # CRITICAL, but blocked
    p = create_portfolio("p1")
    p.register(dep.instance_id, runtime=rt, priority=WorkflowPriority.NORMAL)
    p.register(crit.instance_id, runtime=rt, priority=WorkflowPriority.CRITICAL)
    # CRITICAL requires DEP success — priority must NOT let it run first.
    p.add_dependency(crit.instance_id, dep.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)
    r = sched.step(p)
    assert r.selected_instance_id == dep.instance_id  # not the CRITICAL, which is blocked


# --------------------------------------------------------------------------- #
# G. Deterministic tie-breaking                                               #
# --------------------------------------------------------------------------- #
def test_equal_workflows_break_ties_by_registration_sequence():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "a1"))
    b = prepare_workflow(rt, _wf("B", "b1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)  # seq 0
    p.register(b.instance_id, runtime=rt)  # seq 1
    r = create_portfolio_scheduler(rt).step(p)
    assert r.selected_instance_id == a.instance_id  # earliest registration wins the tie


# --------------------------------------------------------------------------- #
# H/I. Fairness + aging                                                       #
# --------------------------------------------------------------------------- #
def test_same_priority_workflows_are_not_starved():
    # Two long, equal-priority workflows: neither is drained while the other waits.
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "a1", "a2", "a3", chain=True))
    b = prepare_workflow(rt, _wf("B", "b1", "b2", "b3", chain=True))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    picks = []
    for _ in range(6):
        r = sched.step(p)
        if r.granted:
            picks.append(rt.instance(r.selected_instance_id).workflow_id)
    # Both workflows advanced within the first 6 rounds — no permanent starvation.
    assert "A" in picks and "B" in picks
    # And they alternate deterministically rather than draining one first.
    assert picks[:4] == ["A", "B", "A", "B"]


def test_runnable_unselected_workflow_ages_blocked_does_not():
    rt = _runtime()
    hi = prepare_workflow(rt, _wf("HI", "h1", "h2", "h3", "h4", "h5", chain=True))
    lo = prepare_workflow(rt, _wf("LO", "l1", "l2", chain=True))
    dep = prepare_workflow(rt, _wf("DEP", "d1"))
    p = create_portfolio("p1")
    p.register(hi.instance_id, runtime=rt, priority=WorkflowPriority.HIGH)
    p.register(lo.instance_id, runtime=rt, priority=WorkflowPriority.LOW)
    p.register(dep.instance_id, runtime=rt, priority=WorkflowPriority.HIGH)
    # DEP depends on LO success, so it is dependency-blocked and must NOT age.
    p.add_dependency(dep.instance_id, lo.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)
    for _ in range(3):
        sched.step(p)
    # LO is a runnable, unselected LOW workflow (HIGH keeps winning) -> it aged.
    assert p.entry(lo.instance_id).age >= 1
    # DEP is dependency-blocked -> age never accrued.
    assert p.entry(dep.instance_id).age == 0


def test_aging_eventually_lets_lower_priority_run_but_never_reaches_critical():
    rt = _runtime()
    hi = prepare_workflow(rt, _wf("HI", *[f"h{i}" for i in range(30)], chain=True))
    lo = prepare_workflow(rt, _wf("LO", "l1"))
    p = create_portfolio("p1")
    p.register(hi.instance_id, runtime=rt, priority=WorkflowPriority.HIGH)
    p.register(lo.instance_id, runtime=rt, priority=WorkflowPriority.BACKGROUND)
    policy = SchedulingPolicy(aging_cap=500)
    sched = PortfolioScheduler(rt, policy)
    picked_lo = False
    for _ in range(400):
        r = sched.step(p)
        if r.selected_instance_id == lo.instance_id:
            picked_lo = True
            break
    assert picked_lo, "aging failed to rescue a starved BACKGROUND workflow"
    # Even fully aged, a non-critical effective rank never reaches the CRITICAL rank (0).
    assert policy.effective_rank(p.entry(lo.instance_id)) >= 1


def test_critical_class_never_ages():
    rt = _runtime()
    crit = prepare_workflow(rt, _wf("C", "c1"))
    p = create_portfolio("p1")
    e = p.register(crit.instance_id, runtime=rt, priority=WorkflowPriority.CRITICAL)
    e.age = 999  # even with a large age...
    assert SchedulingPolicy().effective_rank(e) == 0  # ...CRITICAL stays absolute


# --------------------------------------------------------------------------- #
# J. Determinism                                                              #
# --------------------------------------------------------------------------- #
def test_two_identical_portfolios_produce_identical_selection_sequences():
    def run():
        rt = _runtime()
        a = prepare_workflow(rt, _wf("A", "a1", "a2", chain=True))
        b = prepare_workflow(rt, _wf("B", "b1", "b2", chain=True))
        c = prepare_workflow(rt, _wf("C", "c1"))
        p = create_portfolio("p1")
        p.register(a.instance_id, runtime=rt, priority=WorkflowPriority.HIGH)
        p.register(b.instance_id, runtime=rt, priority=WorkflowPriority.NORMAL)
        p.register(c.instance_id, runtime=rt, priority=WorkflowPriority.NORMAL)
        p.add_dependency(c.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
        sched = create_portfolio_scheduler(rt)
        seq = []
        for _ in range(12):
            r = sched.step(p)
            seq.append((rt.instance(r.selected_instance_id).workflow_id
                        if r.selected_instance_id else None, r.reason))
        return seq

    assert run() == run()


# --------------------------------------------------------------------------- #
# K. Bounded A/B interleaving (not draining)                                  #
# --------------------------------------------------------------------------- #
def test_scheduler_interleaves_rather_than_draining():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1", "A2", chain=True))
    b = prepare_workflow(rt, _wf("B", "B1", "B2", chain=True))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    order = []
    for _ in range(4):
        r = sched.step(p)
        order.append(rt.instance(r.selected_instance_id).workflow_id)
    assert order == ["A", "B", "A", "B"]  # interleaved, not A,A,...,B,B


# --------------------------------------------------------------------------- #
# L. Governance HOLD isolation                                                #
# --------------------------------------------------------------------------- #
def test_hold_isolates_one_workflow_others_continue_no_self_resume():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.HOLD)
    provider = CountingProvider("p")
    rt = _runtime(hook, provider)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1", "B2", chain=True))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    for _ in range(6):
        sched.step(p)
    # A hit a HOLD and stays WAITING; the scheduler never resumed it.
    assert rt.instance(a.instance_id).status is WorkflowStatus.WAITING
    # B ran to completion regardless.
    assert rt.instance(b.instance_id).status is WorkflowStatus.COMPLETED
    # A's held task never invoked its provider.
    assert all(c.operation != "A1" for c in provider.calls)
    cls = dict((e.instance_id, c) for e, c in sched.classify(p))
    assert cls[a.instance_id] is WorkflowEligibility.WAITING_RUNTIME


# --------------------------------------------------------------------------- #
# M. Governance ESCALATE isolation                                            #
# --------------------------------------------------------------------------- #
def test_escalate_isolates_one_workflow_others_continue_no_self_resume():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.ESCALATE)
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    for _ in range(5):
        sched.step(p)
    assert rt.instance(a.instance_id).status is WorkflowStatus.PAUSED  # never self-resumed
    assert rt.instance(b.instance_id).status is WorkflowStatus.COMPLETED


# --------------------------------------------------------------------------- #
# N. Governance BLOCK — dependent blocked, independent continues              #
# --------------------------------------------------------------------------- #
def test_block_fails_workflow_dependent_blocked_independent_continues():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))     # independent
    c = prepare_workflow(rt, _wf("C", "C1"))     # requires A success
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.register(c.instance_id, runtime=rt)
    p.add_dependency(c.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)
    results = sched.run(p, max_rounds=20)
    assert rt.instance(a.instance_id).status is WorkflowStatus.FAILED
    assert rt.instance(b.instance_id).status is WorkflowStatus.COMPLETED
    # C never ran; it stays blocked by A's failed success-requirement.
    assert rt.instance(c.instance_id).status is WorkflowStatus.RUNNING
    cls = dict((e.instance_id, cl) for e, cl in sched.classify(p))
    assert cls[c.instance_id] is WorkflowEligibility.BLOCKED_DEPENDENCY
    # A is terminal and is never selected again.
    a_selected_after_fail = [
        r for r in results
        if r.selected_instance_id == a.instance_id and r.round > 2
    ]
    # (A may be selected at most once — the quantum that fails it.)
    assert len(a_selected_after_fail) <= 1


# --------------------------------------------------------------------------- #
# O. Exact-action invariant preserved through the scheduler                   #
# --------------------------------------------------------------------------- #
def test_scheduling_cannot_weaken_exact_action_binding():
    class UnboundClearHook(GovernanceHook):
        """Returns CLEAR without binding the exact proposal — must fail closed."""
        def __init__(self):
            self.evaluations = []
        def evaluate(self, proposal, evaluation_time):
            self.evaluations.append(proposal.task_id)
            return GovernanceEvaluation(
                disposition=GovernanceDisposition.CLEAR,
                proposal_fingerprint=None,        # NOT bound
                reason_codes=("TEST",),
                evaluation_reference=None,
                valid_until=None,
            )

    provider = CountingProvider("p")
    rt = _runtime(UnboundClearHook(), provider)
    a = prepare_workflow(rt, _wf("A", "A1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    r = create_portfolio_scheduler(rt).step(p)
    # The scheduler granted the quantum, but the seam failed the workflow closed.
    assert rt.instance(a.instance_id).status is WorkflowStatus.FAILED
    assert provider.calls == []                   # provider never invoked on an unbound CLEAR
    assert r.advance_outcome.stop_reason == "WORKFLOW_FAILED"


# --------------------------------------------------------------------------- #
# P/Q. Canonical execution state + checkpoint through a granted quantum       #
# --------------------------------------------------------------------------- #
def test_granted_quantum_produces_resolvable_execution_state_and_recoverable_checkpoint():
    cs = InMemoryCheckpointStore()
    cfg = AgentRuntimeConfig(
        governance_hook=AllowAllGovernanceHook(), checkpoint_store=cs
    )
    rt = create_runtime(cfg)
    register_provider(rt, CountingProvider("p"))
    a = prepare_workflow(rt, _wf("A", "A1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    r = create_portfolio_scheduler(rt).step(p)
    # Canonical execution-state digest from the quantum is resolvable in the runtime journal.
    assert r.advance_outcome.execution_state_digest is not None
    resolved = rt.execution_state_by_digest(
        a.instance_id, r.advance_outcome.execution_state_digest
    )
    assert resolved is not None
    # Every emitted checkpoint remains self-recoverable (unchanged H22-A guarantee).
    for cp in cs.history(a.instance_id):
        assert cp.verify()
        ok, reason = cp.validate_execution_states()
        assert ok, reason


# --------------------------------------------------------------------------- #
# R/S. No direct provider call; classification triggers no execution          #
# --------------------------------------------------------------------------- #
def test_classification_invokes_no_provider_and_no_governance():
    provider = CountingProvider("p")
    hook = MappedGovernanceHook()
    rt = _runtime(hook, provider)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    # Classifying many times performs zero execution.
    for _ in range(5):
        sched.classify(p)
    assert provider.calls == []
    assert hook.evaluations == []


def test_one_step_grants_exactly_one_quantum_of_provider_work():
    provider = CountingProvider("p")
    rt = _runtime(AllowAllGovernanceHook(), provider)
    a = prepare_workflow(rt, _wf("A", "A1", "A2", "A3", chain=True))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    sched.step(p)
    assert len(provider.calls) == 1  # exactly one task ran — the scheduler did not drain A


# --------------------------------------------------------------------------- #
# T. Quiescent / terminal / empty portfolio stop reasons                      #
# --------------------------------------------------------------------------- #
def test_empty_portfolio_returns_empty_reason():
    rt = _runtime()
    p = create_portfolio("p1")
    r = create_portfolio_scheduler(rt).step(p)
    assert r.reason == PortfolioStepReason.EMPTY_PORTFOLIO.value


def test_all_terminal_portfolio_completes():
    rt = _runtime()
    a = start_workflow(rt, _wf("A", "A1"))  # already COMPLETED
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    r = create_portfolio_scheduler(rt).step(p)
    assert r.reason == PortfolioStepReason.ALL_TERMINAL.value
    assert p.status.value == "COMPLETED"


def test_all_waiting_or_paused_is_quiescent_not_complete():
    hook = MappedGovernanceHook(default=GovernanceDisposition.HOLD)
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    # Drive both to WAITING (HOLD), then step: no eligible workflow, but NOT complete.
    for _ in range(6):
        r = sched.step(p)
    assert r.reason == PortfolioStepReason.NO_ELIGIBLE_WORKFLOW.value
    assert p.status.value == "ACTIVE"  # quiescent, governance WAITING is not completion


def test_run_is_bounded_and_does_not_spin_on_quiescent_portfolio():
    hook = MappedGovernanceHook(default=GovernanceDisposition.HOLD)
    rt = _runtime(hook)
    a = prepare_workflow(rt, _wf("A", "A1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    results = create_portfolio_scheduler(rt).run(p, max_rounds=50)
    # It stops as soon as no quantum can be granted, well under the bound.
    assert results[-1].reason == PortfolioStepReason.NO_ELIGIBLE_WORKFLOW.value
    assert len(results) <= 3


# --------------------------------------------------------------------------- #
# §26. Agent-Teams-style shared task-graph scenario                           #
# --------------------------------------------------------------------------- #
def test_agent_teams_delivery_graph_release_chain():
    """Architecture -> Backend -> Tests: each stage releases the next on success."""
    rt = _runtime()
    arch = prepare_workflow(rt, _wf("architecture", "design"))
    backend = prepare_workflow(rt, _wf("backend", "build"))
    tests = prepare_workflow(rt, _wf("tests", "verify"))
    p = create_portfolio("delivery")
    p.register(arch.instance_id, runtime=rt)
    p.register(backend.instance_id, runtime=rt)
    p.register(tests.instance_id, runtime=rt)
    p.add_dependency(backend.instance_id, arch.instance_id, DependencyType.REQUIRES_SUCCESS)
    p.add_dependency(tests.instance_id, backend.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)

    granted_order = []
    results = sched.run(p, max_rounds=30)
    for r in results:
        if r.granted:
            granted_order.append(rt.instance(r.selected_instance_id).workflow_id)

    # The first granted workflow must be architecture (the only initially-eligible one).
    assert granted_order[0] == "architecture"
    # Backend never precedes architecture; tests never precede backend.
    assert granted_order.index("backend") > granted_order.index("architecture")
    assert granted_order.index("tests") > granted_order.index("backend")
    assert rt.instance(tests.instance_id).status is WorkflowStatus.COMPLETED
    assert p.status.value == "COMPLETED"


# --------------------------------------------------------------------------- #
# Weighted fairness (SWRR) — unequal weights                                  #
# --------------------------------------------------------------------------- #
def _weighted_run(weight_a, weight_b, rounds, tasks=80):
    """Two equal-priority workflows of unequal weight, both long enough to stay eligible
    for the whole window. Returns (count_a, count_b, order_string)."""
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", *[f"a{i}" for i in range(tasks)], chain=True))
    b = prepare_workflow(rt, _wf("B", *[f"b{i}" for i in range(tasks)], chain=True))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt, weight=weight_a)
    p.register(b.instance_id, runtime=rt, weight=weight_b)
    sched = create_portfolio_scheduler(rt)
    order = []
    for _ in range(rounds):
        r = sched.step(p)
        if r.granted:
            order.append(rt.instance(r.selected_instance_id).workflow_id)
    return order.count("A"), order.count("B"), "".join(order)


def test_weighted_fairness_2to1_proportional_service():
    ca, cb, order = _weighted_run(2, 1, rounds=12)
    # SWRR gives exactly proportional service over a whole number of periods.
    assert (ca, cb) == (8, 4)
    assert ca == 2 * cb
    # ...and it is SMOOTH, not bursty: the heavier workflow never monopolizes — the lighter
    # one is served at least every few rounds (no starvation of the positive weight).
    assert "BBB" not in order and order.count("B") > 0
    assert max(_max_run(order)) <= 2  # no run of the same workflow longer than 2


def test_weighted_fairness_3to1_proportional_service():
    ca, cb, order = _weighted_run(3, 1, rounds=12)
    assert (ca, cb) == (9, 3)
    assert ca == 3 * cb
    assert order.count("B") > 0  # weight-1 workflow is not starved by the weight-3 one


def test_weighted_fairness_no_permanent_starvation_over_long_horizon():
    # The exact defect the audit flagged: A(weight=2), B(weight=1). B must NOT starve.
    ca, cb, order = _weighted_run(2, 1, rounds=60)
    assert cb > 0
    assert ca == 2 * cb                 # still exactly 2:1 over the long horizon
    # B is served regularly throughout — not just once. Check the second half too.
    assert order[30:].count("B") > 0


def test_weighted_fairness_is_deterministic():
    assert _weighted_run(3, 1, rounds=15) == _weighted_run(3, 1, rounds=15)
    assert _weighted_run(5, 2, rounds=21) == _weighted_run(5, 2, rounds=21)


def _max_run(s):
    """Lengths of maximal same-character runs in a string (helper for smoothness checks)."""
    runs, cur, prev = [], 0, None
    for ch in s:
        if ch == prev:
            cur += 1
        else:
            if prev is not None:
                runs.append(cur)
            cur, prev = 1, ch
    if prev is not None:
        runs.append(cur)
    return runs or [0]


def test_non_finite_and_non_positive_weights_rejected():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1"))
    p = create_portfolio("p1")
    for i, bad in enumerate((float("nan"), float("inf"), float("-inf"), 0, -1.0)):
        with pytest.raises(ValueError):
            # A distinct, unregistered id each time; weight is validated fail-closed.
            p.register(f"unregistered-{i}", runtime=None, weight=bad)
    # A real registration with a good weight still works.
    e = p.register(a.instance_id, runtime=rt, weight=2.0)
    assert e.weight == 2.0


# --------------------------------------------------------------------------- #
# Portfolio lifecycle — topology frozen once scheduling begins                #
# --------------------------------------------------------------------------- #
def test_topology_frozen_after_first_scheduling_round():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1", "A2", chain=True))
    b = prepare_workflow(rt, _wf("B", "B1"))
    c = prepare_workflow(rt, _wf("C", "C1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    assert p.status.value == "CREATED"
    sched.step(p)                                  # scheduling begins -> ACTIVE + frozen
    assert p.status.value == "ACTIVE"
    # A NEW registration is now rejected (topology frozen).
    with pytest.raises(ValueError):
        p.register(c.instance_id, runtime=rt)
    # A new dependency is rejected too.
    with pytest.raises(ValueError):
        p.add_dependency(b.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
    # Re-registering an EXISTING id is still an idempotent no-op (not a topology change).
    assert p.register(a.instance_id) is p.entry(a.instance_id)
    # The un-registerable C never entered the schedule.
    assert not p.is_registered(c.instance_id)


def test_topology_frozen_after_completion_no_zombie_registration():
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "A1"))
    b = prepare_workflow(rt, _wf("B", "B1"))
    p = create_portfolio("p1")
    p.register(a.instance_id, runtime=rt)
    sched = create_portfolio_scheduler(rt)
    sched.run(p, max_rounds=10)
    assert p.status.value == "COMPLETED"
    # The audit's zombie case: a COMPLETED portfolio must not accept a new workflow it would
    # then run while still reporting COMPLETED.
    with pytest.raises(ValueError):
        p.register(b.instance_id, runtime=rt)
    assert p.status.value == "COMPLETED"
    assert not p.is_registered(b.instance_id)


def test_empty_portfolio_step_leaves_it_created_and_mutable():
    rt = _runtime()
    p = create_portfolio("p1")
    r = create_portfolio_scheduler(rt).step(p)
    assert r.reason == PortfolioStepReason.EMPTY_PORTFOLIO.value
    # Stepping an empty portfolio must NOT flip it to a misleading ACTIVE — it stays CREATED
    # and therefore still mutable.
    assert p.status.value == "CREATED"
    a = prepare_workflow(rt, _wf("A", "A1"))
    p.register(a.instance_id, runtime=rt)          # still permitted
    r2 = create_portfolio_scheduler(rt).step(p)
    assert r2.reason == PortfolioStepReason.QUANTUM_GRANTED.value
    assert p.status.value == "ACTIVE"


def test_agent_teams_independent_plus_dependent_interleaves_then_releases():
    """A and B independent; C depends on A. A/B interleave; A's success releases C."""
    rt = _runtime()
    a = prepare_workflow(rt, _wf("A", "a1", "a2", chain=True))
    b = prepare_workflow(rt, _wf("B", "b1", "b2", chain=True))
    c = prepare_workflow(rt, _wf("C", "c1"))
    p = create_portfolio("delivery")
    p.register(a.instance_id, runtime=rt)
    p.register(b.instance_id, runtime=rt)
    p.register(c.instance_id, runtime=rt)
    p.add_dependency(c.instance_id, a.instance_id, DependencyType.REQUIRES_SUCCESS)
    sched = create_portfolio_scheduler(rt)

    # Initially only A and B are eligible; C is blocked.
    cls0 = dict((e.instance_id, cl) for e, cl in sched.classify(p))
    assert cls0[a.instance_id] is WorkflowEligibility.ELIGIBLE
    assert cls0[b.instance_id] is WorkflowEligibility.ELIGIBLE
    assert cls0[c.instance_id] is WorkflowEligibility.WAITING_DEPENDENCY

    order = []
    for _ in range(10):
        r = sched.step(p)
        if r.granted:
            order.append(rt.instance(r.selected_instance_id).workflow_id)
    # A and B interleaved before C ran, and C ran only after A completed.
    assert order.index("C") > order.index("A")
    assert "B" in order[:order.index("C")]
    assert rt.instance(a.instance_id).status is WorkflowStatus.COMPLETED
    assert rt.instance(c.instance_id).status is WorkflowStatus.COMPLETED
