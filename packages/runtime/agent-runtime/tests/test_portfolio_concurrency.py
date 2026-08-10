"""H22-D — bounded concurrent multi-workflow execution.

These tests exercise the top of the H22 stack: given several *eligible* workflows, which ones may
receive **simultaneous** bounded H22-A quanta without conflicting with each other or exceeding
shared limits? They prove the phase's guarantees WITHOUT the executor ever authorizing a task,
preempting the indivisible governance→exact-action→provider chain, running two quanta for one
workflow at once, weakening H22-C's torn-state contract, or claiming exactly-once/distributed
semantics.

Concurrency is proven with deterministic synchronization primitives (``threading.Barrier`` /
``threading.Event``), never ``sleep`` — a genuine overlap either satisfies a barrier immediately
or the barrier trips on timeout, so there is no timing race in the assertions.
"""
from __future__ import annotations

import threading

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    BudgetRequirement,
    CancellationScope,
    CompensationRegistry,
    CompensationSpec,
    CompensationTrigger,
    ConcurrencyPolicy,
    ConcurrentStepReason,
    ExecutorInfrastructureError,
    PortfolioBudget,
    PortfolioFailurePolicy,
    PortfolioScheduler,
    ResourceClaim,
    ResourceCoordinator,
    ResourceMode,
    TaskDefinition,
    WorkflowDefinition,
    WorkflowPriority,
    WorkflowStatus,
    advance_workflow,
    create_concurrent_executor,
    create_portfolio,
    create_runtime,
    prepare_workflow,
    recover_portfolio,
    register_provider,
)
from ugence_agent_runtime.governance.hooks import AllowAllGovernanceHook
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.providers.interfaces import Provider, ToolResult
from ugence_agent_runtime.orchestration.budgets import BudgetCoordinator, BudgetShortfall
from ugence_agent_runtime.orchestration.concurrency import (
    SynchronousExecutionBackend,
    ThreadPoolExecutionBackend,
)
from ugence_agent_runtime.orchestration.resources import modes_conflict, normalize_claims
from ugence_agent_runtime.persistence.in_memory import InMemoryRuntimeStateStore
from ugence_agent_runtime.orchestration import (
    InMemoryPortfolioCheckpointStore,
    InMemoryPortfolioEventStore,
)

CLEAR = GovernanceDisposition.CLEAR
HOLD = GovernanceDisposition.HOLD
ESCALATE = GovernanceDisposition.ESCALATE
BLOCK = GovernanceDisposition.BLOCK


# --------------------------------------------------------------------------- #
# helpers / thread-safe test doubles                                          #
# --------------------------------------------------------------------------- #
def _task(tid, *, consequential=True, depends_on=(), provider="p"):
    return TaskDefinition(
        task_id=tid, operation=tid, provider_id=provider,
        depends_on=tuple(depends_on), consequential=consequential,
    )


def _wf(workflow_id, *task_ids, chain=False, provider="p"):
    tasks, prev = [], None
    for tid in task_ids:
        deps = (prev,) if (chain and prev is not None) else ()
        tasks.append(_task(tid, depends_on=deps, provider=provider))
        prev = tid
    return WorkflowDefinition(workflow_id=workflow_id, tasks=tuple(tasks))


def _many_task_wf(workflow_id, n, *, provider="p"):
    """A workflow of ``n`` independent consequential tasks — one runs per quantum, so the
    workflow stays eligible for ``n`` served rounds."""
    return _wf(workflow_id, *[f"{workflow_id}t{i}" for i in range(n)], provider=provider)


class ThreadSafeHook(GovernanceHook):
    """Per-workflow disposition hook, safe under concurrent evaluation. CLEAR results bind the
    exact proposal fingerprint so the runtime's exact-action check passes."""

    def __init__(self, default=CLEAR):
        self.default = default
        self.by_workflow = {}
        self._lock = threading.Lock()
        self.evaluations = []

    def set(self, workflow_id, disposition):
        self.by_workflow[workflow_id] = disposition

    def evaluate(self, proposal, evaluation_time) -> GovernanceEvaluation:
        with self._lock:
            self.evaluations.append((proposal.workflow_id, proposal.task_id))
        disp = self.by_workflow.get(proposal.workflow_id, self.default)
        clear = disp is CLEAR
        return GovernanceEvaluation(
            disposition=disp,
            proposal_fingerprint=proposal.fingerprint if clear else None,
            reason_codes=("TEST",),
            evaluation_reference="gov-ref" if clear else None,
            valid_until=None,
            correlation_reference=proposal.correlation_id,
        )


class Probe(Provider):
    """A provider that records peak simultaneous in-flight executions. An optional barrier forces
    exactly ``parties`` executions to overlap (they all pass together) or trips on timeout — a
    deterministic proof of genuine concurrency, with no sleep."""

    def __init__(self, provider_id="p", *, barrier=None):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self._lock = threading.Lock()
        self.current = 0
        self.peak = 0
        self.calls = 0
        self._barrier = barrier

    def execute(self, invocation):
        with self._lock:
            self.current += 1
            self.peak = max(self.peak, self.current)
            self.calls += 1
        try:
            if self._barrier is not None:
                self._barrier.wait(timeout=10)
        finally:
            with self._lock:
                self.current -= 1
        return ToolResult(
            provider_id=self.provider_id, operation=invocation.operation, ok=True,
            output={"op": invocation.operation},
        )


class BoomProvider(Provider):
    """A provider whose execute raises a non-runtime error (simulates a worker infrastructure
    fault inside the quantum, distinct from a governed provider failure)."""

    def __init__(self, provider_id="boom"):
        self.provider_id = provider_id
        self.version = "1.0.0"

    def execute(self, invocation):
        raise RuntimeError("worker infrastructure fault")


class ExplodingBackend:
    """A backend whose run() raises — simulates an executor/thread-pool submission failure."""

    def run(self, thunks):
        raise OSError("cannot submit to executor")


class FaultyAdvanceRuntime:
    """Proxies a real runtime but makes ``advance_workflow`` RAISE for chosen instance ids —
    a genuine H22-D worker/infrastructure fault (distinct from a governed provider failure, which
    the runtime catches and reports as a normal FAILED outcome)."""

    def __init__(self, runtime, fail_ids):
        self._rt = runtime
        self._fail = set(fail_ids)

    def __getattr__(self, name):
        return getattr(self._rt, name)

    def advance_workflow(self, instance_id):
        if instance_id in self._fail:
            raise RuntimeError("advance_workflow infrastructure fault")
        return self._rt.advance_workflow(instance_id)


def _runtime(hook=None, providers=None, *, store=None, max_concurrent_tasks=8):
    # A permissive runtime ceiling by default so the H22-D ConcurrencyPolicy governs; the C2
    # tests set a low ceiling explicitly to prove min(policy, runtime.max_concurrent_tasks).
    ss = store if store is not None else InMemoryRuntimeStateStore()
    cfg = AgentRuntimeConfig(
        governance_hook=hook or AllowAllGovernanceHook(), state_store=ss,
        max_concurrent_tasks=max_concurrent_tasks,
    )
    rt = create_runtime(cfg)
    for prov in providers or [Probe("p")]:
        register_provider(rt, prov)
    return rt


def _prepare_register(rt, portfolio, definition, **reg):
    inst = prepare_workflow(rt, definition)
    portfolio.register(inst.instance_id, runtime=rt, **reg)
    return inst.instance_id


def _declare_no_claims(ex, *instance_ids):
    """Explicitly declare an empty resource claim set — the application asserting this quantum has
    no shared resource footprint — which (unlike leaving it undeclared) permits concurrency."""
    for iid in instance_ids:
        ex.set_resource_claims(iid, [])


# --------------------------------------------------------------------------- #
# A. bounded max concurrency + C. genuine overlap                             #
# --------------------------------------------------------------------------- #
def test_A_at_most_max_concurrent_quanta_in_flight():
    barrier = threading.Barrier(2)  # exactly 2 must overlap per round
    prov = Probe("p", barrier=barrier)
    rt = _runtime(providers=[prov])
    p = create_portfolio("A")
    for wid in ("W1", "W2", "W3", "W4"):
        _prepare_register(rt, p, _wf(wid, f"{wid}t"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
        backend=ThreadPoolExecutionBackend(),
    )
    _declare_no_claims(ex, *p.instance_ids)  # explicit empty claims -> concurrency permitted
    results = ex.run_concurrent()
    executed = [r for r in results if r.granted]
    assert all(len(r.admitted) <= 2 for r in executed)
    assert prov.peak == 2  # two quanta genuinely overlapped; never three
    assert all(rt.instance(i).status is WorkflowStatus.COMPLETED for i in p.instance_ids)


def test_C_two_independent_workflows_run_concurrently():
    barrier = threading.Barrier(2)
    prov = Probe("p", barrier=barrier)
    rt = _runtime(providers=[prov])
    p = create_portfolio("C")
    _prepare_register(rt, p, _wf("A", "A1"))
    _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
        backend=ThreadPoolExecutionBackend(),
    )
    _declare_no_claims(ex, *p.instance_ids)  # explicit empty claims -> concurrency permitted
    result = ex.step_concurrent()
    # The barrier only releases if BOTH quanta were in flight simultaneously.
    assert result.granted and len(result.admitted) == 2
    assert prov.peak == 2


def test_sequential_backend_never_overlaps():
    prov = Probe("p")  # no barrier
    rt = _runtime(providers=[prov])
    p = create_portfolio("S")
    for wid in ("A", "B", "C"):
        _prepare_register(rt, p, _wf(wid, f"{wid}1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=3),
        backend=SynchronousExecutionBackend(),
    )
    ex.run_concurrent()
    assert prov.peak == 1  # the synchronous backend runs quanta one at a time


# --------------------------------------------------------------------------- #
# B. concurrency=1 equivalence to the H22-B single-quantum scheduler          #
# --------------------------------------------------------------------------- #
def test_B_concurrency_one_matches_single_quantum_scheduler():
    # Two identical setups: one driven by the executor at max_concurrency=1, the other by the
    # plain H22-B scheduler.step loop. Selection order and fairness state must match exactly.
    def build():
        rt = _runtime(providers=[Probe("p")])
        p = create_portfolio("P")
        ids = {}
        ids["A"] = _prepare_register(rt, p, _wf("A", "A1", "A2"), priority=WorkflowPriority.HIGH)
        ids["B"] = _prepare_register(rt, p, _wf("B", "B1", "B2"))
        ids["C"] = _prepare_register(rt, p, _wf("C", "C1"))
        return rt, p, ids

    rt1, p1, _ = build()
    ex = create_concurrent_executor(rt1, p1, policy=ConcurrencyPolicy(max_concurrent_quanta=1))
    exec_order = []
    for r in ex.run_concurrent():
        if r.granted:
            exec_order.extend(r.admitted)

    rt2, p2, _ = build()
    sched = PortfolioScheduler(rt2)
    sched_order = []
    while True:
        res = sched.step(p2)
        if not res.granted:
            break
        sched_order.append(res.selected_instance_id)

    assert exec_order == sched_order
    # Fairness/aging state is identical entry-by-entry.
    for e1, e2 in zip(p1.entries(), p2.entries()):
        assert (e1.fair_credit, e1.age) == (e2.fair_credit, e2.age)


# --------------------------------------------------------------------------- #
# D. same workflow never double in flight  +  F/G determinism                 #
# --------------------------------------------------------------------------- #
def test_D_one_workflow_admitted_at_most_once_per_batch():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("D")
    _prepare_register(rt, p, _wf("A", "A1", "A2", "A3"))  # 3 independent tasks
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=4))
    r = ex.step_concurrent()
    assert r.admitted == tuple(sorted(set(r.admitted)))  # no duplicate id
    assert len(r.admitted) == 1  # only one entry exists → only one quantum, never a double-advance


def test_F_deterministic_admission_same_state_same_batch():
    def plan_once():
        rt = _runtime(providers=[Probe("p")])
        p = create_portfolio("F")
        for wid in ("A", "B", "C", "D"):
            _prepare_register(rt, p, _wf(wid, f"{wid}1"))
        ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
        return ex.step_concurrent().admitted

    assert plan_once() == plan_once() == plan_once()


def test_G_backend_choice_does_not_change_admission():
    def run(backend):
        rt = _runtime(providers=[Probe("p")])
        p = create_portfolio("G")
        for wid in ("A", "B", "C", "D", "E"):
            _prepare_register(rt, p, _wf(wid, f"{wid}1"))
        ex = create_concurrent_executor(
            rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2), backend=backend,
        )
        return [r.admitted for r in ex.run_concurrent() if r.granted]

    assert run(SynchronousExecutionBackend()) == run(ThreadPoolExecutionBackend())


# --------------------------------------------------------------------------- #
# E. the H22-A quantum stays atomic (governance precedes provider)            #
# --------------------------------------------------------------------------- #
def test_E_governance_precedes_provider_within_each_quantum():
    hook = ThreadSafeHook()
    rt = _runtime(hook, [Probe("p")])
    p = create_portfolio("E")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
                                    backend=ThreadPoolExecutionBackend())
    ex.step_concurrent()
    kinds = [ev.type for ev in rt.events(a)]
    gov = kinds.index("GOVERNANCE_DISPOSITION_RECEIVED")
    prov = kinds.index("PROVIDER_INVOKED")
    assert gov < prov  # provider is invoked only after governance cleared, inside one quantum


# --------------------------------------------------------------------------- #
# H–O. resource claims: matrix, atomic reservation, leaks, ordering           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "a,b,conflict",
    [
        (ResourceMode.READ, ResourceMode.READ, False),          # H
        (ResourceMode.READ, ResourceMode.WRITE, True),          # I
        (ResourceMode.WRITE, ResourceMode.WRITE, True),         # J
        (ResourceMode.EXCLUSIVE, ResourceMode.READ, True),      # K
        (ResourceMode.EXCLUSIVE, ResourceMode.EXCLUSIVE, True), # K
        (ResourceMode.UNKNOWN, ResourceMode.READ, True),        # fail-closed
        (ResourceMode.UNKNOWN, ResourceMode.UNKNOWN, True),     # fail-closed
    ],
)
def test_HK_conflict_matrix(a, b, conflict):
    assert modes_conflict(a, b) is conflict
    assert modes_conflict(b, a) is conflict


def test_L_multi_resource_reservation_is_all_or_none():
    coord = ResourceCoordinator()
    coord.reserve("holder", [ResourceClaim("R3", ResourceMode.WRITE)])
    ok, conflict = coord.reserve(
        "A",
        [ResourceClaim("R1", ResourceMode.WRITE), ResourceClaim("R2", ResourceMode.READ),
         ResourceClaim("R3", ResourceMode.EXCLUSIVE)],
    )
    assert not ok and conflict.resource_key == "R3"
    # Nothing from A's set was reserved (R1/R2 are free again).
    assert coord.active_claims("A") == ()
    ok2, _ = coord.reserve("A", [ResourceClaim("R1", ResourceMode.WRITE)])
    assert ok2


def test_normalize_claims_escalates_self_conflict():
    norm = normalize_claims([ResourceClaim("R", ResourceMode.READ), ResourceClaim("R", ResourceMode.WRITE)])
    assert norm == (ResourceClaim("R", ResourceMode.WRITE),)


def test_I_write_read_conflict_defers_second_and_keeps_it_eligible():
    # A WRITE customer/123, B WRITE customer/123 -> B deferred; C READ ledger -> admitted.
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("res")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    c = _prepare_register(rt, p, _wf("C", "C1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=3))
    ex.set_resource_claims(a, [ResourceClaim("crm/customer/123", ResourceMode.WRITE)])
    ex.set_resource_claims(b, [ResourceClaim("crm/customer/123", ResourceMode.WRITE)])
    ex.set_resource_claims(c, [ResourceClaim("ledger/report", ResourceMode.READ)])
    r1 = ex.step_concurrent()
    assert set(r1.admitted) == {a, c}
    assert len(r1.deferred_resource) == 1
    dr = r1.deferred_resource[0]
    assert dr["instance_id"] == b and dr["conflicts_with"] == a
    # N: B was deferred, not served — it is still eligible and gets served next round.
    assert ex.resources.is_empty  # reservations released at the batch boundary
    r2 = ex.step_concurrent()
    assert b in r2.admitted


def test_M_no_leaked_resources_across_outcomes():
    hook = ThreadSafeHook()
    hook.set("H", HOLD)
    hook.set("BL", BLOCK)
    rt = _runtime(hook, [Probe("p"), BoomProvider("boom")])
    p = create_portfolio("leak")
    ids = {
        "ok": _prepare_register(rt, p, _wf("OK", "o1")),
        "hold": _prepare_register(rt, p, _wf("H", "h1")),
        "block": _prepare_register(rt, p, _wf("BL", "b1")),
        "boom": _prepare_register(rt, p, _wf("BM", "bm1", provider="boom")),
    }
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=4))
    for k, iid in ids.items():
        ex.set_resource_claims(iid, [ResourceClaim(f"res/{k}", ResourceMode.EXCLUSIVE)])
    ex.step_concurrent()
    # Regardless of success / HOLD / BLOCK / infrastructure exception, no reservation leaks.
    assert ex.resources.is_empty
    assert ex.resources.active_instance_ids() == ()


def test_O_deterministic_conflict_winner_follows_scheduler_order():
    # Two workflows contending for the same WRITE resource: the H22-B fairness winner is admitted,
    # the other deferred — deterministically, by scheduler order (here registration/tie-break).
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("ord")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    ex.set_resource_claims(a, [ResourceClaim("shared", ResourceMode.WRITE)])
    ex.set_resource_claims(b, [ResourceClaim("shared", ResourceMode.WRITE)])
    r = ex.step_concurrent()
    assert r.admitted == (a,)  # A wins by tie-break; B deferred
    assert r.deferred_resource[0]["instance_id"] == b


# --------------------------------------------------------------------------- #
# P–W. shared budget                                                          #
# --------------------------------------------------------------------------- #
def test_P_Q_sufficient_admits_insufficient_defers():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("bud")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
        budget=PortfolioBudget({"cost": 100}),
    )
    _declare_no_claims(ex, a, b)  # isolate the BUDGET deferral from resource coordination
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 70}))
    ex.set_budget_requirement(b, BudgetRequirement({"cost": 70}))
    r = ex.step_concurrent()
    # R/S: 70 + 70 > 100, so only the safe subset (A) is admitted; B is budget-deferred.
    assert r.admitted == (a,)
    assert r.deferred_budget and r.deferred_budget[0]["instance_id"] == b
    assert r.deferred_budget[0]["budget_dimension"] == "cost"


def test_T_unused_reservation_released_after_hold():
    hook = ThreadSafeHook()
    hook.set("A", HOLD)  # provider never runs → the reservation must be released, not consumed
    rt = _runtime(hook, [Probe("p")])
    p = create_portfolio("bud2")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
        budget=PortfolioBudget({"cost": 100}),
    )
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 40}))
    ex.step_concurrent()
    assert rt.instance(a).status is WorkflowStatus.WAITING
    assert ex.budget.consumed("cost") == 0.0  # HOLD consumed nothing
    assert not ex.budget.has_active_reservations


def test_S_conservative_settlement_charges_reservation_on_success():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("bud3")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
        budget=PortfolioBudget({"cost": 100}),
    )
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 40}))
    ex.run_concurrent()  # run task quantum + finalization quantum
    assert rt.instance(a).status is WorkflowStatus.COMPLETED
    assert ex.budget.consumed("cost") == 40.0  # conservative: full reservation charged once
    assert not ex.budget.has_active_reservations


def test_V_budget_rejects_nan_inf_negative():
    for bad in (float("nan"), float("inf"), -1.0):
        with pytest.raises(ValueError):
            PortfolioBudget({"cost": bad})
        with pytest.raises(ValueError):
            BudgetRequirement({"cost": bad})


def test_W_exhausted_budget_is_deterministic_no_admission():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("bud4")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
        budget=PortfolioBudget({"cost": 10}),
    )
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 50}))  # never affordable
    r = ex.step_concurrent()
    assert not r.granted
    assert r.reason == ConcurrentStepReason.NO_CONCURRENTLY_ADMISSIBLE_WORKFLOW.value
    assert r.deferred_budget  # structured, not opaque


def test_budget_coordinator_reservation_prevents_overspend():
    coord = BudgetCoordinator(PortfolioBudget({"cost": 100}))
    ok, _ = coord.reserve("A", BudgetRequirement({"cost": 70}))
    assert ok
    ok2, short = coord.reserve("B", BudgetRequirement({"cost": 70}))
    assert not ok2 and isinstance(short, BudgetShortfall)
    assert short.available == 30.0 and short.requested == 70.0


# --------------------------------------------------------------------------- #
# X–AB. fairness integration under concurrency                                #
# --------------------------------------------------------------------------- #
def test_Z_swrr_two_to_one_proportional_under_resource_serialization():
    # A (weight 2) and B (weight 1) both EXCLUSIVE-claim the same resource, so only one runs per
    # round. Over concurrent batches SWRR must serve A twice as often as B — exactly.
    pa, pb = Probe("pa"), Probe("pb")
    rt = _runtime(providers=[pa, pb])
    p = create_portfolio("fair")
    a = _prepare_register(rt, p, _many_task_wf("A", 40, provider="pa"), weight=2.0)
    b = _prepare_register(rt, p, _many_task_wf("B", 40, provider="pb"), weight=1.0)
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    ex.set_resource_claims(a, [ResourceClaim("shared", ResourceMode.EXCLUSIVE)])
    ex.set_resource_claims(b, [ResourceClaim("shared", ResourceMode.EXCLUSIVE)])
    for _ in range(30):
        ex.step_concurrent()
    assert (pa.calls, pb.calls) == (20, 10)  # deterministic 2:1


def test_Y_resource_conflicted_workflow_keeps_starvation_protection():
    # B repeatedly conflicts with a higher-priority A; B must not be charged/aged as served, so
    # the moment A finishes, B is admitted.
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("starve")
    # Equal priority isolates RESOURCE deferral from priority aging.
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    ex.set_resource_claims(a, [ResourceClaim("shared", ResourceMode.WRITE)])
    ex.set_resource_claims(b, [ResourceClaim("shared", ResourceMode.WRITE)])
    r1 = ex.step_concurrent()
    assert r1.admitted == (a,)
    b_entry = p.entry(b)
    # Deferred by resource conflict: B is NOT aged as out-prioritized (age stays 0) and NOT
    # charged as served — its SWRR credit only rose (more owed), preserving starvation protection.
    assert b_entry.age == 0 and b_entry.fair_credit > 0
    # Drive to completion: once A's conflict clears, B is served (never permanently starved).
    ex.run_concurrent()
    assert rt.instance(b).status is WorkflowStatus.COMPLETED


def test_AB_identical_runs_produce_identical_admission_sequences():
    def run():
        rt = _runtime(providers=[Probe("p")])
        p = create_portfolio("det")
        a = _prepare_register(rt, p, _many_task_wf("A", 5), weight=2.0)
        b = _prepare_register(rt, p, _many_task_wf("B", 5), weight=1.0)
        ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1))
        return [r.admitted for r in ex.run_concurrent() if r.granted]

    assert run() == run()


# --------------------------------------------------------------------------- #
# AC–AG. governance under concurrency                                         #
# --------------------------------------------------------------------------- #
def test_AC_AD_AE_governance_dispositions_are_independent_across_the_batch():
    hook = ThreadSafeHook()
    hook.set("H", HOLD)
    hook.set("ES", ESCALATE)
    hook.set("BL", BLOCK)
    rt = _runtime(hook, [Probe("p")])
    p = create_portfolio("gov")
    ids = {
        "clear": _prepare_register(rt, p, _wf("CL", "c1")),
        "hold": _prepare_register(rt, p, _wf("H", "h1")),
        "escalate": _prepare_register(rt, p, _wf("ES", "e1")),
        "block": _prepare_register(rt, p, _wf("BL", "b1")),
    }
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=4),
                                    backend=ThreadPoolExecutionBackend())
    _declare_no_claims(ex, *p.instance_ids)
    ex.run_concurrent()
    assert rt.instance(ids["clear"]).status is WorkflowStatus.COMPLETED
    assert rt.instance(ids["hold"]).status is WorkflowStatus.WAITING     # HOLD
    assert rt.instance(ids["escalate"]).status is WorkflowStatus.PAUSED  # ESCALATE
    assert rt.instance(ids["block"]).status is WorkflowStatus.FAILED     # BLOCK
    # A/C independent of the restrictive ones — B progressed regardless.


def test_AF_fresh_governance_per_consequential_quantum():
    hook = ThreadSafeHook()
    rt = _runtime(hook, [Probe("p")])
    p = create_portfolio("fresh")
    a = _prepare_register(rt, p, _wf("A", "A1", "A2"))  # two consequential quanta
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1))
    ex.run_concurrent()
    # Governance was consulted once per consequential task — never cached/reused across quanta.
    assert len(hook.evaluations) == 2


# --------------------------------------------------------------------------- #
# AH–AO. crash / durability                                                   #
# --------------------------------------------------------------------------- #
def _durable_env():
    ss = InMemoryRuntimeStateStore()
    rt = _runtime(providers=[Probe("p")], store=ss)
    return rt


def test_AH_checkpoint_only_at_stable_boundary_and_reservations_empty():
    rt = _durable_env()
    p = create_portfolio("dur")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
        checkpoint_store=cps, budget=PortfolioBudget({"cost": 100}),
    )
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 25}))
    ex.step_concurrent()
    assert ex.resources.is_empty and not ex.budget.has_active_reservations
    cp = ex.checkpoint()
    assert cp.checkpoint_version == "2"
    assert cp.concurrency_state["budget"]["consumed"]["cost"] == 25.0


def test_AI_checkpoint_refused_with_active_reservation():
    rt = _durable_env()
    p = create_portfolio("dur2")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(rt, p, checkpoint_store=cps)
    ex.resources.reserve(a, [ResourceClaim("R", ResourceMode.WRITE)])  # simulate an in-flight hold
    with pytest.raises(ValueError):
        ex.checkpoint()


def test_U_AN_consumed_budget_persists_across_recovery():
    rt = _durable_env()
    p = create_portfolio("durB")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
        checkpoint_store=cps, budget=PortfolioBudget({"cost": 100}),
    )
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 30}))
    ex.step_concurrent()
    ex.checkpoint()

    rt2 = _runtime(providers=[Probe("p")], store=rt.config.state_store)
    rec = recover_portfolio(
        store=cps, portfolio_id="durB", runtime=rt2,
        definitions={a: _wf("A", "A1")},
    )
    assert rec.concurrency_state["budget"]["consumed"]["cost"] == 30.0
    restored = BudgetCoordinator.restore(rec.concurrency_state["budget"])
    assert restored.consumed("cost") == 30.0 and not restored.has_active_reservations


def test_AJ_torn_state_divergence_is_preserved_under_h22d():
    rt = _durable_env()
    p = create_portfolio("torn")
    a = _prepare_register(rt, p, _wf("A", "A1", "A2"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    checkpoint_store=cps)
    ex.step_concurrent()      # advances A to a checkpointed boundary (still RUNNING)
    ex.checkpoint()           # portfolio cp references the current runtime checkpoint
    advance_workflow(rt, a)   # runtime advances ahead of the portfolio snapshot (crash window)
    rt2 = _runtime(providers=[Probe("p")], store=rt.config.state_store)
    with pytest.raises(Exception) as exc:
        recover_portfolio(store=cps, portfolio_id="torn", runtime=rt2,
                          definitions={a: _wf("A", "A1", "A2")})
    assert "DIVERGENCE" in str(exc.value)


def test_AL_recovery_launches_no_workers():
    rt = _durable_env()
    prov = Probe("p")
    rt = _runtime(providers=[prov], store=rt.config.state_store)
    p = create_portfolio("norun")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    checkpoint_store=cps)
    ex.step_concurrent()
    ex.checkpoint()
    calls_before = prov.calls
    rt2 = _runtime(providers=[Probe("p2")], store=rt.config.state_store)
    rec = recover_portfolio(store=cps, portfolio_id="norun", runtime=rt2,
                            definitions={a: _wf("A", "A1")})
    assert rec.requires_continuation is True
    assert prov.calls == calls_before  # recovery ran no quantum


# --------------------------------------------------------------------------- #
# AP–AT. cancellation                                                         #
# --------------------------------------------------------------------------- #
def test_AP_cancellation_before_batch_prevents_admission():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("cancel")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    ex.cancel(a)
    r = ex.step_concurrent()
    assert a not in r.admitted and b in r.admitted
    assert rt.instance(a).status is WorkflowStatus.CANCELLED


def test_AR_cancelled_workflow_receives_no_future_quantum():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("cancel2")
    a = _prepare_register(rt, p, _wf("A", "A1", "A2", "A3"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    ex.step_concurrent()      # advances A once
    ex.cancel(a)
    admitted_after = [r.admitted for r in ex.run_concurrent()]
    assert all(a not in adm for adm in admitted_after)


def test_AT_portfolio_all_cancellation_prevents_future_batches():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("cancel3")
    for wid in ("A", "B", "C"):
        _prepare_register(rt, p, _wf(wid, f"{wid}1", f"{wid}2"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=3))
    ex.step_concurrent()
    ex.cancel(p.instance_ids[0], scope=CancellationScope.PORTFOLIO_ALL)
    r = ex.step_concurrent()
    assert not r.granted and r.reason == ConcurrentStepReason.PORTFOLIO_TERMINAL.value


# --------------------------------------------------------------------------- #
# AU–BB. compensation                                                         #
# --------------------------------------------------------------------------- #
def test_AU_AV_AW_failure_registers_exactly_one_compensation_with_lineage():
    hook = ThreadSafeHook()
    hook.set("PAY", BLOCK)  # payment "fails" (governance block) -> compensation intent
    rt = _runtime(hook, [Probe("p")])
    p = create_portfolio("comp")
    pay = _prepare_register(rt, p, _wf("PAY", "charge"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1))
    ex.configure_compensation(pay, "RefundPaymentWorkflow", CompensationTrigger.ON_WORKFLOW_FAILURE)
    ex.step_concurrent()
    ex.step_concurrent()  # a second observation must NOT duplicate the registration
    regs = ex.compensations.registrations()
    assert len(regs) == 1
    reg = regs[0]
    assert reg.compensation_workflow_id == "RefundPaymentWorkflow"
    assert reg.lineage["compensates_instance_id"] == pay
    assert reg.trigger == CompensationTrigger.ON_WORKFLOW_FAILURE.value


def test_AX_AY_AZ_compensation_is_an_ordinary_freshly_governed_workflow():
    # The compensation workflow, when scheduled, is an ordinary H22-D workflow: it crosses fresh
    # governance, obeys resource/budget, and H22-D never calls a compensation provider directly.
    hook = ThreadSafeHook()
    rt = _runtime(hook, [Probe("refund")])
    p = create_portfolio("comp2")
    refund = _prepare_register(rt, p, _wf("RefundPaymentWorkflow", "r1", provider="refund"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget=PortfolioBudget({"cost": 100}))
    ex.set_budget_requirement(refund, BudgetRequirement({"cost": 10}))
    ex.run_concurrent()
    assert rt.instance(refund).status is WorkflowStatus.COMPLETED
    assert hook.evaluations == [("RefundPaymentWorkflow", "r1")]  # fresh governance
    assert ex.budget.consumed("cost") == 10.0  # obeyed the shared budget


def test_BB_recovery_does_not_duplicate_registered_compensation():
    reg = CompensationRegistry()
    spec = CompensationSpec(
        origin_instance_id="wf-1", compensation_workflow_id="Refund",
        trigger=CompensationTrigger.ON_WORKFLOW_FAILURE,
    )
    reg.register(spec)
    restored = CompensationRegistry.restore(reg.registry_state())
    _, created = restored.register(spec)  # replay after recovery
    assert created is False
    assert len(restored.registrations()) == 1


# --------------------------------------------------------------------------- #
# BC–BG. worker / executor infrastructure failure                            #
# --------------------------------------------------------------------------- #
def test_BC_BD_worker_exception_leaks_no_reservation():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("boom")
    a = _prepare_register(rt, p, _wf("A", "a1"))
    faulty = FaultyAdvanceRuntime(rt, {a})  # advance_workflow itself raises for A
    ex = create_concurrent_executor(faulty, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget=PortfolioBudget({"cost": 100}))
    ex.set_resource_claims(a, [ResourceClaim("R", ResourceMode.WRITE)])
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 20}))
    result = ex.step_concurrent()
    out = result.outcomes[0]
    assert out.infrastructure_failure  # captured as an infra fault, not fabricated as success
    assert out.advance_outcome is None
    assert ex.resources.is_empty and not ex.budget.has_active_reservations


def test_BE_executor_submission_failure_fails_closed():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("subfail")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    backend=ExplodingBackend(), budget=PortfolioBudget({"cost": 100}))
    ex.set_resource_claims(a, [ResourceClaim("R", ResourceMode.WRITE)])
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 20}))
    with pytest.raises(ExecutorInfrastructureError):
        ex.step_concurrent()
    # Reservations taken during planning were released on the failure path — no leak, fail closed.
    assert ex.resources.is_empty and not ex.budget.has_active_reservations


def test_BF_one_worker_failure_does_not_fabricate_another_result():
    rt = _runtime(providers=[Probe("ok")])
    p = create_portfolio("mixed")
    ok = _prepare_register(rt, p, _wf("OK", "o1", provider="ok"))
    boom = _prepare_register(rt, p, _wf("BM", "b1", provider="ok"))
    faulty = FaultyAdvanceRuntime(rt, {boom})  # only BM's worker faults
    ex = create_concurrent_executor(faulty, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
                                    backend=ThreadPoolExecutionBackend())
    _declare_no_claims(ex, ok, boom)
    result = ex.step_concurrent()
    by_id = {o.instance_id: o for o in result.outcomes}
    assert by_id[ok].advance_outcome is not None and not by_id[ok].infrastructure_failure
    assert by_id[boom].infrastructure_failure  # BM's fault never fabricated OK's result
    assert rt.instance(ok).instance_id == ok  # OK ran; its task advanced normally
    assert by_id[ok].advance_outcome.task_id == "o1"


# --------------------------------------------------------------------------- #
# BH–BM. audit trace                                                          #
# --------------------------------------------------------------------------- #
def test_BH_BI_batch_planned_and_deferral_reasons_are_structured():
    rt = _runtime(providers=[Probe("p")])
    est = InMemoryPortfolioEventStore()
    p = create_portfolio("audit")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
                                    event_store=est)
    ex.set_resource_claims(a, [ResourceClaim("shared", ResourceMode.WRITE)])
    ex.set_resource_claims(b, [ResourceClaim("shared", ResourceMode.WRITE)])
    ex.step_concurrent()
    kinds = [e.event_type for e in ex.trace.history()]
    assert "CONCURRENT_BATCH_PLANNED" in kinds
    assert "QUANTUM_ADMITTED" in kinds
    assert "QUANTUM_DEFERRED_RESOURCE" in kinds
    deferral = next(e for e in ex.trace.history() if e.event_type == "QUANTUM_DEFERRED_RESOURCE")
    assert deferral.detail.get("resource_key") == "shared"
    assert deferral.detail.get("conflicts_with") == a


def test_BJ_reconciliation_trace_is_admission_ordered_despite_completion_race():
    barrier = threading.Barrier(2)
    prov = Probe("p", barrier=barrier)
    est = InMemoryPortfolioEventStore()
    rt = _runtime(providers=[prov])
    p = create_portfolio("recon")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
                                    backend=ThreadPoolExecutionBackend(), event_store=est)
    _declare_no_claims(ex, a, b)
    r = ex.step_concurrent()
    completed = [e for e in ex.trace.history() if e.event_type == "CONCURRENT_QUANTUM_COMPLETED"]
    order = [e.detail["instance_id"] for e in completed]
    assert order == list(r.admitted)  # admission order, regardless of which finished first


def test_BK_audit_history_survives_recovery():
    rt = _durable_env()
    est = InMemoryPortfolioEventStore()
    p = create_portfolio("survive")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    checkpoint_store=cps, event_store=est)
    ex.step_concurrent()
    ex.checkpoint()
    pre = [e.event_type for e in ex.trace.history()]
    rt2 = _runtime(providers=[Probe("p")], store=rt.config.state_store)
    rec = recover_portfolio(store=cps, portfolio_id="survive", runtime=rt2,
                            definitions={a: _wf("A", "A1")}, event_store=est)
    post = [e.event_type for e in rec.trace.history()]
    assert "CONCURRENT_BATCH_PLANNED" in post  # pre-crash H22-D events preserved
    assert "PORTFOLIO_RECOVERED" in post
    assert len(post) > len(pre)


# =========================================================================== #
# Independent-audit corrections C1–C5                                          #
# =========================================================================== #
from ugence_agent_runtime.orchestration.budgets import BudgetEstimateExceeded
from ugence_agent_runtime.api import create_concurrent_executor_from_recovery
from ugence_agent_runtime.runtime.errors import ProviderExecutionError


class FailProvider(Provider):
    """Provider that always raises a retriable provider error (a provider that RAN and failed)."""

    def __init__(self, provider_id="fail"):
        self.provider_id = provider_id
        self.version = "1.0.0"
        self.calls = 0

    def execute(self, invocation):
        self.calls += 1
        raise ProviderExecutionError("provider failed", retriable=False)


def _hook(disp, *, bind=True):
    class _H(GovernanceHook):
        def __init__(self): self.calls = 0
        def evaluate(self, p, t):
            self.calls += 1
            clear = disp is CLEAR
            return GovernanceEvaluation(
                disposition=disp,
                proposal_fingerprint=(p.fingerprint if (clear and bind) else None),
                reason_codes=("X",),
                evaluation_reference=("r" if (clear and bind) else None),
                valid_until=None, correlation_reference=p.correlation_id)
    return _H()


# --- C5: settlement is driven by authoritative provider-execution evidence --- #
@pytest.mark.parametrize(
    "disp,bind,provider,expected_consumed",
    [
        (CLEAR, True, "probe", 40.0),   # CLEAR + provider success -> charge
        (CLEAR, True, "fail", 40.0),    # CLEAR + provider ran then failed -> charge
        (HOLD, True, "probe", 0.0),     # HOLD (no provider) -> release
        (ESCALATE, True, "probe", 0.0), # ESCALATE (no provider) -> release
        (BLOCK, True, "probe", 0.0),    # BLOCK (no provider) -> release
        (CLEAR, False, "probe", 0.0),   # CLEAR but unbound -> exact-action reject before provider -> release
    ],
)
def test_C5_settlement_follows_provider_execution_evidence(disp, bind, provider, expected_consumed):
    hook = _hook(disp, bind=bind)
    prov = Probe("probe") if provider == "probe" else FailProvider("fail")
    rt = _runtime(hook, [prov])
    p = create_portfolio("c5")
    a = _prepare_register(rt, p, _wf("A", "A1", provider=provider))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget=PortfolioBudget({"cost": 100}))
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 40}))
    ex.step_concurrent()
    assert ex.budget.consumed("cost") == expected_consumed
    assert not ex.budget.has_active_reservations


def test_C5_infrastructure_fault_releases_budget():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("c5inf")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    faulty = FaultyAdvanceRuntime(rt, {a})
    ex = create_concurrent_executor(faulty, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget=PortfolioBudget({"cost": 100}))
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 40}))
    ex.step_concurrent()
    assert ex.budget.consumed("cost") == 0.0 and not ex.budget.has_active_reservations


def test_C5_settle_overrun_fails_closed_without_clamping():
    bc = BudgetCoordinator(PortfolioBudget({"cost": 100}))
    bc.reserve("A", BudgetRequirement({"cost": 40}))
    with pytest.raises(BudgetEstimateExceeded):
        bc.settle("A", actual={"cost": 50})          # measured > reserved -> fail closed
    # Ledger untouched: reservation intact, nothing consumed (no silent clamp to 40).
    assert bc.reserved("cost") == 40.0 and bc.consumed("cost") == 0.0
    s = bc.settle("A", actual={"cost": 30})           # honest actual <= reserved
    assert s.charged["cost"] == 30.0 and s.released["cost"] == 10.0
    assert bc.consumed("cost") == 30.0 and bc.reserved("cost") == 0.0


# --- C4: undeclared vs explicitly-empty requirements ------------------------ #
def test_C4_undeclared_resource_serializes_but_explicit_empty_permits_concurrency():
    # Undeclared: conservatively serialized (only one admitted, the other fail-closed).
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("c4r")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    r = ex.step_concurrent()
    assert len(r.admitted) == 1
    assert r.deferred_resource and r.deferred_resource[0]["reason"] == "RESOURCE_REQUIREMENT_UNAVAILABLE"

    # Explicit empty declaration: application asserts no shared footprint -> concurrency allowed.
    rt2 = _runtime(providers=[Probe("p")])
    p2 = create_portfolio("c4r2")
    a2 = _prepare_register(rt2, p2, _wf("A", "A1"))
    b2 = _prepare_register(rt2, p2, _wf("B", "B1"))
    ex2 = create_concurrent_executor(rt2, p2, policy=ConcurrencyPolicy(max_concurrent_quanta=2))
    _declare_no_claims(ex2, a2, b2)
    r2 = ex2.step_concurrent()
    assert set(r2.admitted) == {a2, b2}


def test_C4_undeclared_budget_fails_closed_when_limits_configured():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("c4b")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget=PortfolioBudget({"cost": 100}))
    _declare_no_claims(ex, a)  # isolate: resources fine, budget requirement UNDECLARED
    r = ex.step_concurrent()
    assert not r.granted
    assert r.deferred_budget and r.deferred_budget[0]["reason"] == "BUDGET_REQUIREMENT_UNAVAILABLE"

    # Explicit empty budget requirement = declared zero -> admitted.
    ex.set_budget_requirement(a, BudgetRequirement({}))
    assert ex.step_concurrent().granted


def test_C4_undeclared_budget_harmless_without_limits():
    rt = _runtime(providers=[Probe("p")])
    p = create_portfolio("c4b2")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1))
    _declare_no_claims(ex, a)  # no budget configured at all -> undeclared requirement is fine
    assert ex.step_concurrent().granted


# --- C3: admission planning is exception-safe (all-or-none, fail closed) ----- #
def test_C3_claims_resolver_exception_fails_closed_no_leak_no_fairness_mutation():
    prov = Probe("p")
    rt = _runtime(providers=[prov])
    p = create_portfolio("c3")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    b = _prepare_register(rt, p, _wf("B", "B1"))

    def resolver(iid):
        if iid == b:
            raise RuntimeError("resolver blew up on candidate B")
        return []

    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
                                    claims_resolver=resolver, budget=PortfolioBudget({"cost": 100}))
    with pytest.raises(ExecutorInfrastructureError):
        ex.step_concurrent()
    # Fail closed: no reservation left behind, no worker launched...
    assert ex.resources.is_empty and not ex.budget.has_active_reservations
    assert prov.calls == 0
    # ...and no H22-B fairness/service state was committed (all entries pristine).
    for e in p.entries():
        assert e.fair_credit == 0.0 and e.age == 0


def test_C3_budget_resolver_exception_fails_closed():
    prov = Probe("p")
    rt = _runtime(providers=[prov])
    p = create_portfolio("c3b")
    a = _prepare_register(rt, p, _wf("A", "A1"))

    def bresolver(iid):
        raise RuntimeError("budget resolver blew up")

    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=1),
                                    budget_resolver=bresolver, budget=PortfolioBudget({"cost": 100}))
    with pytest.raises(ExecutorInfrastructureError):
        ex.step_concurrent()
    assert ex.resources.is_empty and not ex.budget.has_active_reservations and prov.calls == 0


# --- C2: H22-D respects AgentRuntimeConfig.max_concurrent_tasks -------------- #
@pytest.mark.parametrize("runtime_max,policy_max,expected", [(1, 4, 1), (2, 4, 2), (8, 2, 2)])
def test_C2_effective_concurrency_is_min_of_policy_and_runtime(runtime_max, policy_max, expected):
    n = expected * 2  # a multiple of expected so provider-running batches are exactly `expected`
    barrier = threading.Barrier(expected)
    prov = Probe("p", barrier=barrier)
    rt = _runtime(providers=[prov], max_concurrent_tasks=runtime_max)
    p = create_portfolio("c2")
    ids = [_prepare_register(rt, p, _wf(f"W{i}", f"W{i}t")) for i in range(n)]
    ex = create_concurrent_executor(rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=policy_max),
                                    backend=ThreadPoolExecutionBackend())
    _declare_no_claims(ex, *ids)
    assert ex.effective_max_concurrent_quanta == expected
    ex.run_concurrent()
    assert prov.peak == expected  # never exceeds the runtime ceiling
    assert all(len(r.admitted) <= expected for r in ex.run_concurrent() or [])


# --- C1: recovery reconstruction seam --------------------------------------- #
def test_C1_from_recovery_restores_budget_compensation_and_failure_policy():
    ss = InMemoryRuntimeStateStore()
    hook = ThreadSafeHook()
    hook.set("PAY", BLOCK)  # PAY fails -> compensation intent registered
    rt = _runtime(hook, [Probe("p")], store=ss)
    p = create_portfolio("c1")
    a = _prepare_register(rt, p, _wf("A", "A1"))       # CLEAR success -> consumes budget
    pay = _prepare_register(rt, p, _wf("PAY", "charge"))
    cps = InMemoryPortfolioCheckpointStore()
    est = InMemoryPortfolioEventStore()
    ex = create_concurrent_executor(
        rt, p, policy=ConcurrencyPolicy(max_concurrent_quanta=2),
        failure_policy=PortfolioFailurePolicy.FAIL_DEPENDENTS,
        budget=PortfolioBudget({"cost": 100}), checkpoint_store=cps, event_store=est,
    )
    _declare_no_claims(ex, a, pay)
    ex.set_budget_requirement(a, BudgetRequirement({"cost": 70}))
    ex.set_budget_requirement(pay, BudgetRequirement({"cost": 10}))
    ex.configure_compensation(pay, "RefundPaymentWorkflow", CompensationTrigger.ON_WORKFLOW_FAILURE)
    ex.step_concurrent()
    assert ex.budget.consumed("cost") == 70.0          # A charged, PAY (BLOCK) released
    assert len(ex.compensations.registrations()) == 1
    ex.checkpoint()

    # Recover on a fresh runtime, then reconstruct the executor — NO side effects.
    prov2 = Probe("p2")
    rt2 = _runtime(providers=[prov2], store=ss)
    rec = recover_portfolio(
        store=cps, portfolio_id="c1", runtime=rt2, event_store=est,
        definitions={a: _wf("A", "A1"), pay: _wf("PAY", "charge")},
    )
    calls_before = prov2.calls
    ex2 = create_concurrent_executor_from_recovery(
        rt2, rec, policy=ConcurrencyPolicy(max_concurrent_quanta=2), checkpoint_store=cps)
    # Zero side effects during reconstruction.
    assert prov2.calls == calls_before and rec.requires_continuation is True
    # Durable state adopted, not reset.
    assert ex2.budget.consumed("cost") == 70.0
    assert ex2.controller.failure_policy is PortfolioFailurePolicy.FAIL_DEPENDENTS
    regs = ex2.compensations.registrations()
    assert len(regs) == 1 and regs[0].compensation_workflow_id == "RefundPaymentWorkflow"
    # Compensation remains idempotent after reconstruction (no duplicate on replay).
    _, created = ex2.compensations.register(
        CompensationSpec(origin_instance_id=pay, compensation_workflow_id="RefundPaymentWorkflow",
                         trigger=CompensationTrigger.ON_WORKFLOW_FAILURE))
    assert created is False


def test_C1_from_recovery_v1_style_empty_h22d_state_is_safe():
    # A portfolio checkpointed via the plain H22-C controller carries an empty H22-D slice;
    # reconstruction must produce empty-but-valid budget/compensation coordinators.
    from ugence_agent_runtime.api import create_portfolio_controller
    ss = InMemoryRuntimeStateStore()
    rt = _runtime(providers=[Probe("p")], store=ss)
    p = create_portfolio("c1v1")
    a = _prepare_register(rt, p, _wf("A", "A1"))
    cps = InMemoryPortfolioCheckpointStore()
    ctl = create_portfolio_controller(rt, p, checkpoint_store=cps)
    ctl.step()
    ctl.checkpoint()
    rt2 = _runtime(providers=[Probe("p2")], store=ss)
    rec = recover_portfolio(store=cps, portfolio_id="c1v1", runtime=rt2,
                            definitions={a: _wf("A", "A1")})
    ex2 = create_concurrent_executor_from_recovery(rt2, rec)
    assert ex2.budget.consumed("cost") == 0.0
    assert ex2.compensations.registrations() == ()
    assert not ex2.budget.has_active_reservations and ex2.resources.is_empty
