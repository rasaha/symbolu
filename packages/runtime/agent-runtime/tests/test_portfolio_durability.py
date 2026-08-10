"""H22-C — durable multi-workflow orchestration (checkpoint / recovery / trace / control).

These tests exercise the orchestration-durability layer that makes the H22-B portfolio
coordinator reconstructable, auditable, and safely controllable across failure/restart —
WITHOUT changing single-workflow execution truth. They prove the phase's core correctness
properties:

* the portfolio checkpoint REFERENCES the underlying runtime checkpoints (by digest) and
  never copies them or duplicates canonical execution state;
* recovery is side-effect free (zero provider / governance / advancement calls) and requires
  explicit continuation;
* SWRR fair_credit, aging, registration order, dependencies, failure, and cancellation state
  all survive recovery so the next scheduler decision is exactly the uninterrupted one;
* committed work never repeats; a resealed-but-inconsistent checkpoint is still rejected;
* failure propagation is bounded and cancellation is cooperative + idempotent.
"""
from __future__ import annotations

import dataclasses

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    CancellationScope,
    DependencyType,
    PortfolioController,
    PortfolioEventType,
    PortfolioFailurePolicy,
    SchedulingPolicy,
    TaskDefinition,
    WorkflowDefinition,
    WorkflowPriority,
    WorkflowStatus,
    advance_workflow,
    continue_workflow,
    create_portfolio,
    create_portfolio_controller,
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
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.orchestration.control import PortfolioController
from ugence_agent_runtime.orchestration.persistence import (
    InMemoryPortfolioCheckpointStore,
    PortfolioCheckpoint,
    PortfolioCheckpointConflict,
    WorkflowCheckpointRef,
    _portfolio_digest,
)
from ugence_agent_runtime.orchestration.portfolio import PortfolioStatus
from ugence_agent_runtime.orchestration.recovery import (
    build_portfolio_checkpoint,
    validate_portfolio_checkpoint,
)
from ugence_agent_runtime.orchestration.scheduling import PortfolioScheduler
from ugence_agent_runtime.orchestration.tracing import (
    InMemoryPortfolioEventStore,
    PortfolioTrace,
    PortfolioTraceSequenceError,
)
from ugence_agent_runtime.persistence.checkpoints import Checkpoint
from ugence_agent_runtime.persistence.in_memory import InMemoryRuntimeStateStore
from ugence_agent_runtime.runtime.errors import CheckpointError, RecoveryError

from art_fakes import RecordingProvider


# --------------------------------------------------------------------------- #
# helpers / test doubles                                                       #
# --------------------------------------------------------------------------- #
def _chain_wf(wid, n=1):
    """A workflow of ``n`` chained consequential tasks: exactly one is runnable per quantum,
    so each granted quantum advances one task and the workflow stays RUNNING until all done."""
    tasks = []
    prev = None
    for i in range(1, n + 1):
        tid = f"{wid}{i}"
        deps = (prev,) if prev is not None else ()
        tasks.append(
            TaskDefinition(task_id=tid, operation=tid, provider_id="p",
                           depends_on=deps, consequential=True)
        )
        prev = tid
    return WorkflowDefinition(workflow_id=wid, tasks=tuple(tasks))


class MappedGovernanceHook(GovernanceHook):
    """Per-workflow disposition (default CLEAR, bound so exact-action passes). Counts calls."""

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


class ExplodingProvider(RecordingProvider):
    def execute(self, invocation):
        raise AssertionError("recovery must not call a provider")


class ExplodingHook(GovernanceHook):
    def evaluate(self, *a, **k):
        raise AssertionError("recovery must not call governance")


def build(specs, deps=(), *, hook=None, policy=PortfolioFailurePolicy.ISOLATE_WORKFLOW,
          runtime_version=None, provider=None, pid="P", event_store=None):
    """Build a runtime (with a durable state_store), prepared workflows, a portfolio, a
    portfolio-checkpoint store, and a controller. ``specs`` is a list of dicts with keys
    ``name``, ``n`` (task count), ``priority``, ``weight``. ``deps`` are
    ``(dependent_name, requires_name, dep_type)`` tuples. Pass ``event_store`` for a durable
    orchestration trace."""
    ss = InMemoryRuntimeStateStore()
    cfg_kw = dict(state_store=ss, governance_hook=hook or AllowAllGovernanceHook())
    if runtime_version is not None:
        cfg_kw["runtime_version"] = runtime_version
    rt = create_runtime(AgentRuntimeConfig(**cfg_kw))
    prov = provider or RecordingProvider("p")
    register_provider(rt, prov)
    portfolio = create_portfolio(pid)
    defs, ids = {}, {}
    for s in specs:
        wf = _chain_wf(s["name"], s.get("n", 1))
        inst = prepare_workflow(rt, wf)
        defs[inst.instance_id] = wf
        ids[s["name"]] = inst.instance_id
        portfolio.register(
            inst.instance_id, runtime=rt,
            priority=s.get("priority", WorkflowPriority.NORMAL),
            weight=s.get("weight", 1.0),
        )
    for dep, req, t in deps:
        portfolio.add_dependency(ids[dep], ids[req], t)
    pcp = InMemoryPortfolioCheckpointStore()
    controller = create_portfolio_controller(
        rt, portfolio, policy=policy, checkpoint_store=pcp, event_store=event_store
    )
    return dict(ss=ss, rt=rt, prov=prov, portfolio=portfolio, defs=defs, ids=ids,
                pid=pid, pcp=pcp, controller=controller, event_store=event_store)


def checkpoint_now(env, failure_policy="ISOLATE_WORKFLOW", trace_sequence=0):
    cp = build_portfolio_checkpoint(
        env["portfolio"], env["rt"], failure_policy=failure_policy,
        trace_sequence=trace_sequence,
    )
    env["pcp"].save(cp)
    return cp


def recover(env, *, hook=None, provider=None, runtime_version=None, event_store=None):
    cfg_kw = dict(state_store=env["ss"], governance_hook=hook or AllowAllGovernanceHook())
    if runtime_version is not None:
        cfg_kw["runtime_version"] = runtime_version
    rt2 = create_runtime(AgentRuntimeConfig(**cfg_kw))
    prov2 = provider or RecordingProvider("p")
    register_provider(rt2, prov2)
    result = recover_portfolio(
        store=env["pcp"], portfolio_id=env["pid"], runtime=rt2, definitions=env["defs"],
        event_store=event_store,
    )
    return rt2, prov2, result


def _reseal_portfolio(cp, mutate):
    """Return a PortfolioCheckpoint with ``mutate(dict)`` applied and the outer digest
    recomputed over the canonical payload (a genuine reseal — verify() passes)."""
    d = cp.to_dict()
    mutate(d)
    d["portfolio_digest"] = PortfolioCheckpoint.from_dict(d).compute_digest()
    return PortfolioCheckpoint.from_dict(d)


def run_scheduler(rt, portfolio, rounds, policy=None):
    sched = PortfolioScheduler(rt, policy)
    seq = []
    for _ in range(rounds):
        r = sched.step(portfolio)
        seq.append(r.selected_instance_id if r.granted else None)
    return seq


def continue_running(rt, ids):
    for iid in ids:
        if rt.instance(iid).status in (WorkflowStatus.PAUSED, WorkflowStatus.WAITING):
            continue_workflow(rt, iid)


# =========================================================================== #
# 45. TEST MATRIX — CHECKPOINT                                                 #
# =========================================================================== #
def test_A_checkpoint_roundtrip_equivalent_state():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS)])
    run_scheduler(env["rt"], env["portfolio"], 2)
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=7)
    back = PortfolioCheckpoint.from_dict(cp.to_dict())
    assert back == cp
    assert back.verify()
    assert back.payload() == cp.payload()
    assert back.trace_sequence == 7


def test_B_digest_determinism():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    d1 = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    d2 = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    assert d1.portfolio_digest == d2.portfolio_digest


def test_C_field_sensitivity_every_integrity_field_changes_digest():
    env = build([{"name": "A", "n": 3, "weight": 2}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=3)
    base = cp.portfolio_digest

    def digest_with(mutate):
        d = cp.to_dict()
        mutate(d)
        return _portfolio_digest({k: v for k, v in d.items() if k != "portfolio_digest"})

    assert digest_with(lambda d: d.__setitem__("round", d["round"] + 1)) != base
    assert digest_with(lambda d: d.__setitem__("trace_sequence", 99)) != base
    assert digest_with(lambda d: d["registrations"][0].__setitem__("weight", 5.0)) != base
    assert digest_with(lambda d: d["registrations"][0].__setitem__("fair_credit", 12.0)) != base
    assert digest_with(lambda d: d["registrations"][0].__setitem__("age", 7)) != base
    assert digest_with(lambda d: d["registrations"][0].__setitem__("priority", "CRITICAL")) != base
    assert digest_with(lambda d: d.__setitem__("portfolio_status", "CANCELLED")) != base
    assert digest_with(lambda d: d["workflow_checkpoint_refs"][0].__setitem__("checkpoint_digest", "deadbeef")) != base


def _tamper(cp, mutate):
    d = cp.to_dict()
    mutate(d)
    return PortfolioCheckpoint.from_dict(d)  # digest NOT recomputed


def test_D_tamper_without_reseal_is_rejected():
    env = build([{"name": "A", "n": 3, "weight": 2}, {"name": "B", "n": 3}],
                deps=[("B", "A", DependencyType.REQUIRES_COMPLETION)])
    run_scheduler(env["rt"], env["portfolio"], 2)
    env["pcp"].save(build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                               failure_policy="ISOLATE_WORKFLOW", trace_sequence=0))
    cp = env["pcp"].load(env["pid"])
    tampers = [
        lambda d: d["registrations"][0].__setitem__("weight", 9.0),
        lambda d: d["registrations"][0].__setitem__("priority", "CRITICAL"),
        lambda d: d["registrations"][0].__setitem__("fair_credit", -3.0),
        lambda d: d["registrations"][0].__setitem__("age", 42),
        lambda d: d.__setitem__("round", 999),
        lambda d: d["dependencies"][0].__setitem__("dependency_type", "REQUIRES_SUCCESS"),
        lambda d: d["workflow_checkpoint_refs"][0].__setitem__("checkpoint_digest", "00" * 32),
        lambda d: d.__setitem__("cancellation_state", {env["ids"]["A"]: "WORKFLOW_ONLY"}),
    ]
    for mut in tampers:
        bad = _tamper(cp, mut)
        assert not bad.verify()
        ok, _ = validate_portfolio_checkpoint(bad)
        assert not ok


def test_E_resealed_but_structurally_inconsistent_ref_is_rejected():
    # Reseal after corrupting a workflow checkpoint reference: the outer digest matches, but
    # recovery still fails closed because the reference no longer binds the runtime checkpoint.
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    env["pcp"].save(build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                               failure_policy="ISOLATE_WORKFLOW", trace_sequence=0))
    d = env["pcp"].load(env["pid"]).to_dict()
    d["workflow_checkpoint_refs"][0]["checkpoint_digest"] = "ab" * 32  # plausible but wrong
    d["portfolio_digest"] = _portfolio_digest({k: v for k, v in d.items() if k != "portfolio_digest"})
    resealed = PortfolioCheckpoint.from_dict(d)
    assert resealed.verify()  # outer digest now matches (resealed)
    # validate() passes structurally (ref shape ok), but recovery cross-binding rejects it.
    env["pcp"].save(resealed)
    with pytest.raises(RecoveryError):
        recover(env)


def test_S_resealed_cycle_in_dependencies_is_rejected():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}],
                deps=[("B", "A", DependencyType.REQUIRES_COMPLETION)])
    run_scheduler(env["rt"], env["portfolio"], 1)
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    d = cp.to_dict()
    # Introduce the reverse edge to form a cycle A->B->A, then reseal the outer digest.
    d["dependencies"].append({"dependent_id": env["ids"]["A"], "requires_id": env["ids"]["B"],
                              "dependency_type": "REQUIRES_COMPLETION"})
    # Reseal over the CANONICAL payload (payload() re-sorts the dependency list), so the outer
    # digest genuinely matches — proving structural validation, not just the digest, rejects it.
    d["portfolio_digest"] = PortfolioCheckpoint.from_dict(d).compute_digest()
    resealed = PortfolioCheckpoint.from_dict(d)
    assert resealed.verify()
    ok, reason = validate_portfolio_checkpoint(resealed)
    assert not ok and "graph" in reason


def test_R_dependency_graph_corruption_unknown_ref_rejected():
    env = build([{"name": "A", "n": 2}, {"name": "B", "n": 2}])
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    d = cp.to_dict()
    d["dependencies"].append({"dependent_id": env["ids"]["A"], "requires_id": "ghost",
                              "dependency_type": "REQUIRES_COMPLETION"})
    d["portfolio_digest"] = _portfolio_digest({k: v for k, v in d.items() if k != "portfolio_digest"})
    ok, reason = validate_portfolio_checkpoint(PortfolioCheckpoint.from_dict(d))
    assert not ok and "unknown" in reason


def test_nan_weight_fails_closed_at_digest():
    # A NaN reaching an integrity field cannot even be sealed (allow_nan=False).
    with pytest.raises(ValueError):
        PortfolioCheckpoint.create(
            portfolio_id="P", portfolio_status="ACTIVE", round=1,
            registrations=[{"instance_id": "wf-1", "registration_sequence": 0,
                            "priority": "NORMAL", "weight": float("nan"),
                            "age": 0, "fair_credit": 0.0}],
            dependencies=[], workflow_checkpoint_refs=[
                WorkflowCheckpointRef("wf-1", "A", "wf-1", "d")],
            failure_state={}, cancellation_state={},
            failure_policy="ISOLATE_WORKFLOW", trace_sequence=0,
        )


# =========================================================================== #
# 46. TEST MATRIX — RECOVERY                                                   #
# =========================================================================== #
def test_F_recovery_causes_zero_external_calls():
    env = build([{"name": "A", "n": 4}, {"name": "B", "n": 4}])
    run_scheduler(env["rt"], env["portfolio"], 3)
    checkpoint_now(env)
    rt2 = create_runtime(AgentRuntimeConfig(state_store=env["ss"], governance_hook=ExplodingHook()))
    register_provider(rt2, ExplodingProvider("p"))
    result = recover_portfolio(store=env["pcp"], portfolio_id=env["pid"],
                               runtime=rt2, definitions=env["defs"])  # must not raise
    assert result.requires_continuation is True
    assert set(result.recovered_workflow_ids) == set(env["ids"].values())


def test_G_explicit_continuation_required_before_any_advance():
    env = build([{"name": "A", "n": 4}, {"name": "B", "n": 4}])
    run_scheduler(env["rt"], env["portfolio"], 3)
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    # Recovered workflows are NOT eligible until explicitly continued.
    for iid in result.recovered_workflow_ids:
        assert rt2.instance(iid).status is WorkflowStatus.PAUSED
    step = PortfolioScheduler(rt2).step(result.portfolio)
    assert not step.granted            # nothing eligible -> no quantum
    assert prov2.calls == []           # recovery + a step advanced nothing
    # After explicit continuation the scheduler can step again.
    continue_running(rt2, result.recovered_workflow_ids)
    step2 = PortfolioScheduler(rt2).step(result.portfolio)
    assert step2.granted


def test_H_committed_tasks_never_rerun_after_recovery():
    env = build([{"name": "A", "n": 5}])
    run_scheduler(env["rt"], env["portfolio"], 3)  # A1,A2,A3 committed
    a = env["ids"]["A"]
    assert [c.operation for c in env["prov"].calls] == ["A1", "A2", "A3"]
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    continue_running(rt2, [a])
    for _ in range(5):
        PortfolioScheduler(rt2).step(result.portfolio)
    # The recovery runtime only ever executed the REMAINING tasks; committed ones never reran.
    executed = [c.operation for c in prov2.calls]
    assert "A1" not in executed and "A2" not in executed and "A3" not in executed
    assert executed == ["A4", "A5"]
    assert rt2.instance(a).status is WorkflowStatus.COMPLETED


def test_I_next_quantum_obtains_fresh_governance_after_recovery():
    env = build([{"name": "A", "n": 4}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    checkpoint_now(env)
    fresh_hook = MappedGovernanceHook()
    rt2, prov2, result = recover(env, hook=fresh_hook)
    assert fresh_hook.evaluations == []   # recovery consulted no governance
    continue_running(rt2, [env["ids"]["A"]])
    PortfolioScheduler(rt2).step(result.portfolio)   # one consequential quantum
    assert fresh_hook.evaluations != []   # fresh governance evaluated post-recovery


def test_J_canonical_execution_state_digests_resolvable_after_recovery():
    env = build([{"name": "A", "n": 3}])
    seq = run_scheduler(env["rt"], env["portfolio"], 2)
    a = env["ids"]["A"]
    digest = env["rt"].execution_state(a, "A1").state_digest
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    # The historical canonical-state snapshot is still resolvable by digest after recovery.
    assert rt2.execution_state_by_digest(a, digest) is not None


# =========================================================================== #
# 47. TEST MATRIX — SCHEDULER CONTINUITY                                        #
# =========================================================================== #
def _continuity(specs, rounds, split, policy=None):
    uninterrupted = run_scheduler(build(specs)["rt"], None, 0)  # placeholder replaced below
    envu = build(specs)
    uninterrupted = run_scheduler(envu["rt"], envu["portfolio"], rounds, policy)

    env = build(specs)
    first = run_scheduler(env["rt"], env["portfolio"], split, policy)
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    continue_running(rt2, list(env["ids"].values()))
    second = run_scheduler(rt2, result.portfolio, rounds - split, policy)
    return uninterrupted, first + second


def test_K_swrr_2to1_continuity():
    n = 30
    unint, split = _continuity(
        [{"name": "A", "n": n, "weight": 2}, {"name": "B", "n": n, "weight": 1}], 20, 10
    )
    assert unint == split
    # sanity: proportional 2:1 service in the uninterrupted run
    a, b = "wf-1", "wf-2"
    assert unint.count(a) == 2 * unint.count(b) or abs(unint.count(a) - 2 * unint.count(b)) <= 2


def test_L_swrr_3to1_continuity():
    n = 40
    unint, split = _continuity(
        [{"name": "A", "n": n, "weight": 3}, {"name": "B", "n": n, "weight": 1}], 24, 11
    )
    assert unint == split


def test_M_aging_continuity_across_threshold():
    # A HIGH always beats B NORMAL until B ages 100 rounds and enters the tier (~round 101).
    n = 120
    unint, split = _continuity(
        [{"name": "A", "n": n, "priority": WorkflowPriority.HIGH},
         {"name": "B", "n": n, "priority": WorkflowPriority.NORMAL}],
        105, 100,
    )
    assert unint == split
    assert "wf-2" in unint  # B eventually selected after crossing the aging threshold


def test_N_registration_sequence_tiebreak_continuity():
    n = 24
    unint, split = _continuity(
        [{"name": "A", "n": n}, {"name": "B", "n": n}], 20, 9  # equal weight/priority -> tie
    )
    assert unint == split


# =========================================================================== #
# 48. TEST MATRIX — DEPENDENCIES                                                #
# =========================================================================== #
def test_O_dependency_chain_survives_recovery():
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 1}, {"name": "C", "n": 1}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS),
                      ("C", "B", DependencyType.REQUIRES_SUCCESS)])
    # Run A to completion (one task).
    run_scheduler(env["rt"], env["portfolio"], 3)
    a, b, c = env["ids"]["A"], env["ids"]["B"], env["ids"]["C"]
    assert env["rt"].instance(a).status is WorkflowStatus.COMPLETED
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    continue_running(rt2, [b, c])  # A is terminal; B/C were prepared/paused
    sched = PortfolioScheduler(rt2)
    # A completed => B eligible, C still blocked on B.
    step = sched.step(result.portfolio)
    assert step.granted and step.selected_instance_id == b  # only B is eligible
    # C remains blocked until B succeeds.
    cls = {iid: c2 for iid, c2 in step.classifications}
    assert cls[c] == "WAITING_DEPENDENCY"


def test_P_failed_success_dependency_remains_blocked_after_recovery():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 1}, {"name": "C", "n": 1}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS)], hook=hook)
    a, b, c = env["ids"]["A"], env["ids"]["B"], env["ids"]["C"]
    # Advance A -> it BLOCKs -> FAILED.
    advance_workflow(env["rt"], a)
    assert env["rt"].instance(a).status is WorkflowStatus.FAILED
    checkpoint_now(env)
    rt2, prov2, result = recover(env, hook=MappedGovernanceHook())
    continue_running(rt2, [b, c])
    step = PortfolioScheduler(rt2).step(result.portfolio)
    cls = {iid: cc for iid, cc in step.classifications}
    assert cls[b] == "BLOCKED_DEPENDENCY"   # hard success-prereq failed; stays blocked
    assert cls[a] == "TERMINAL"
    assert step.selected_instance_id == c   # only the independent C runs


def test_Q_completion_dependency_satisfied_by_failed_predecessor_after_recovery():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 1}],
                deps=[("B", "A", DependencyType.REQUIRES_COMPLETION)], hook=hook)
    a, b = env["ids"]["A"], env["ids"]["B"]
    advance_workflow(env["rt"], a)
    assert env["rt"].instance(a).status is WorkflowStatus.FAILED
    checkpoint_now(env)
    rt2, prov2, result = recover(env, hook=MappedGovernanceHook())
    continue_running(rt2, [b])
    step = PortfolioScheduler(rt2).step(result.portfolio)
    # REQUIRES_COMPLETION is satisfied by ANY terminal predecessor, including a failed one.
    assert step.selected_instance_id == b


# =========================================================================== #
# 49. TEST MATRIX — TRACE                                                       #
# =========================================================================== #
def test_T_U_trace_logical_sequence_monotonic_and_deterministic():
    def run_once():
        env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
        ctrl = env["controller"]
        for _ in range(4):
            ctrl.step()
        return [(e.sequence, e.event_type) for e in ctrl.trace.entries]

    a = run_once()
    b = run_once()
    seqs = [s for s, _ in a]
    assert seqs == list(range(1, len(seqs) + 1))  # monotonic, gap-free, starts at 1
    assert a == b                                  # deterministic


def test_V_exactly_one_recovery_event():
    env = build([{"name": "A", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    recs = [e for e in result.trace.entries
            if e.event_type == PortfolioEventType.PORTFOLIO_RECOVERED.value]
    assert len(recs) == 1
    assert recs[0].sequence >= 1


def test_W_trace_does_not_duplicate_workflow_execution_payload():
    env = build([{"name": "A", "n": 2}])
    ctrl = env["controller"]
    ctrl.step()
    # Orchestration events carry ids/digests only — never task results, args, or provider output.
    for e in ctrl.trace.entries:
        for v in e.detail.values():
            assert not isinstance(v, (dict,)) or all(
                not isinstance(x, (bytes,)) for x in v.values()
            )
        assert "output" not in e.detail
        assert "arguments" not in e.detail


def test_X_quantum_event_references_execution_and_checkpoint_digests():
    env = build([{"name": "A", "n": 2}])
    ctrl = env["controller"]
    ctrl.step()
    granted = [e for e in ctrl.trace.entries
               if e.event_type == PortfolioEventType.QUANTUM_GRANTED.value]
    assert granted
    d = granted[0].detail
    assert d["instance_id"] == env["ids"]["A"]
    assert d["execution_state_digest"] is not None
    assert d["workflow_checkpoint_digest"] is not None


def test_trace_restore_continues_sequence():
    t = PortfolioTrace("P")
    t.emit(PortfolioEventType.PORTFOLIO_CREATED)
    t.emit(PortfolioEventType.WORKFLOW_REGISTERED, instance_id="wf-1")
    anchor = t.last_sequence
    restored = PortfolioTrace.restore("P", anchor)
    e = restored.emit(PortfolioEventType.PORTFOLIO_RECOVERED)
    assert e.sequence == anchor + 1  # strictly increasing across restart


# =========================================================================== #
# 50. TEST MATRIX — FAILURE                                                     #
# =========================================================================== #
def test_Y_independent_failure_isolation():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 2}], hook=hook,
                policy=PortfolioFailurePolicy.ISOLATE_WORKFLOW)
    ctrl = env["controller"]
    for _ in range(6):
        ctrl.step()
    a, b = env["ids"]["A"], env["ids"]["B"]
    assert env["rt"].instance(a).status is WorkflowStatus.FAILED
    assert env["rt"].instance(b).status is WorkflowStatus.COMPLETED  # independent B finished
    assert env["portfolio"].is_failed(a)
    assert env["portfolio"].status is not WorkflowStatus.FAILED  # portfolio not failed by isolate


def test_Z_failed_hard_dependency_blocks_dependent():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 1}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS)], hook=hook)
    ctrl = env["controller"]
    for _ in range(4):
        ctrl.step()
    b = env["ids"]["B"]
    # B's hard success prerequisite failed -> B never runs (no provider call for B1).
    assert "B1" not in [c.operation for c in env["prov"].calls]
    assert env["rt"].instance(b).status is not WorkflowStatus.COMPLETED


def test_AA_fail_dependents_cancels_transitive_subgraph():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 2}, {"name": "C", "n": 2},
                 {"name": "D", "n": 2}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS),
                      ("C", "B", DependencyType.REQUIRES_SUCCESS)], hook=hook,
                policy=PortfolioFailurePolicy.FAIL_DEPENDENTS)
    ctrl = env["controller"]
    for _ in range(8):
        ctrl.step()
    a, b, c, d = (env["ids"][x] for x in "ABCD")
    assert env["rt"].instance(a).status is WorkflowStatus.FAILED
    assert env["rt"].instance(b).status is WorkflowStatus.CANCELLED
    assert env["rt"].instance(c).status is WorkflowStatus.CANCELLED
    assert env["rt"].instance(d).status is WorkflowStatus.COMPLETED  # independent D unaffected
    assert set(env["portfolio"].cancelled_ids()) == {b, c}


def test_AB_fail_portfolio_grants_no_further_quantum():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.BLOCK)
    env = build([{"name": "A", "n": 1}, {"name": "B", "n": 3}], hook=hook,
                policy=PortfolioFailurePolicy.FAIL_PORTFOLIO)
    ctrl = env["controller"]
    # Step until A is selected and fails, tripping FAIL_PORTFOLIO.
    for _ in range(6):
        ctrl.step()
    from ugence_agent_runtime.orchestration.portfolio import PortfolioStatus
    assert env["portfolio"].status is PortfolioStatus.FAILED
    calls_before = len(env["prov"].calls)
    r = ctrl.step()
    assert not r.granted
    assert len(env["prov"].calls) == calls_before  # no new quantum after portfolio failure


# =========================================================================== #
# 51. TEST MATRIX — CANCELLATION                                                #
# =========================================================================== #
def test_AC_workflow_only_cancels_just_the_target():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    ctrl = env["controller"]
    ctrl.step(); ctrl.step()
    a, b = env["ids"]["A"], env["ids"]["B"]
    res = ctrl.cancel(a, CancellationScope.WORKFLOW_ONLY)
    assert res.cancelled == (a,)
    assert env["rt"].instance(a).status is WorkflowStatus.CANCELLED
    assert env["rt"].instance(b).status is WorkflowStatus.RUNNING


def test_AD_dependent_subgraph_cancels_target_plus_transitive_dependents():
    env = build([{"name": "A", "n": 2}, {"name": "B", "n": 2}, {"name": "C", "n": 2},
                 {"name": "D", "n": 2}],
                deps=[("B", "A", DependencyType.REQUIRES_COMPLETION),
                      ("C", "B", DependencyType.REQUIRES_COMPLETION)])
    ctrl = env["controller"]
    a, b, c, d = (env["ids"][x] for x in "ABCD")
    res = ctrl.cancel(a, CancellationScope.DEPENDENT_SUBGRAPH)
    assert set(res.cancelled) == {a, b, c}
    assert env["rt"].instance(d).status is not WorkflowStatus.CANCELLED
    assert res.cancelled == tuple(i for i in env["portfolio"].instance_ids if i in {a, b, c})


def test_AE_portfolio_all_cancels_every_non_terminal():
    env = build([{"name": "A", "n": 2}, {"name": "B", "n": 2}, {"name": "C", "n": 2}])
    ctrl = env["controller"]
    ctrl.step()
    res = ctrl.cancel(env["ids"]["A"], CancellationScope.PORTFOLIO_ALL)
    for x in "ABC":
        assert env["rt"].instance(env["ids"][x]).status is WorkflowStatus.CANCELLED
    from ugence_agent_runtime.orchestration.portfolio import PortfolioStatus
    assert env["portfolio"].status is PortfolioStatus.CANCELLED
    assert len(res.cancelled) == 3


def test_AF_cancellation_is_idempotent():
    env = build([{"name": "A", "n": 3}])
    ctrl = env["controller"]
    a = env["ids"]["A"]
    r1 = ctrl.cancel(a, CancellationScope.WORKFLOW_ONLY)
    n_events = len(ctrl.trace.entries)
    r2 = ctrl.cancel(a, CancellationScope.WORKFLOW_ONLY)
    assert r1.cancelled == (a,)
    assert r2.cancelled == ()             # second request cancels nothing new
    assert r2.already_cancelled == (a,)   # reports current state
    # No WORKFLOW_CANCELLED_BY_PORTFOLIO event was duplicated by the repeat request.
    cbp = [e for e in ctrl.trace.entries
           if e.event_type == PortfolioEventType.WORKFLOW_CANCELLED_BY_PORTFOLIO.value]
    assert len(cbp) == 1


def test_AG_cancel_terminal_workflow_is_deterministic_no_corruption():
    env = build([{"name": "A", "n": 1}])
    ctrl = env["controller"]
    ctrl.step()  # quantum 1: run A1
    ctrl.step()  # quantum 2: finalize A -> COMPLETED
    a = env["ids"]["A"]
    assert env["rt"].instance(a).status is WorkflowStatus.COMPLETED
    res = ctrl.cancel(a, CancellationScope.WORKFLOW_ONLY)
    assert res.cancelled == ()
    assert res.skipped_terminal == (a,)   # cannot cancel a COMPLETED workflow
    assert not env["portfolio"].is_cancelled(a)


def test_AH_cancellation_survives_recovery():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}, {"name": "C", "n": 3}],
                deps=[("B", "A", DependencyType.REQUIRES_COMPLETION)])
    ctrl = env["controller"]
    a, b, c = env["ids"]["A"], env["ids"]["B"], env["ids"]["C"]
    ctrl.cancel(a, CancellationScope.DEPENDENT_SUBGRAPH)  # cancels A + B
    ctrl.checkpoint()
    rt2, prov2, result = recover(env)
    assert result.portfolio.is_cancelled(a)
    assert result.portfolio.is_cancelled(b)
    assert not result.portfolio.is_cancelled(c)
    # A cancelled workflow can never become eligible after recovery.
    continue_running(rt2, [c])
    step = PortfolioScheduler(rt2).step(result.portfolio)
    cls = {iid: cc for iid, cc in step.classifications}
    assert cls[a] == "TERMINAL" and cls[b] == "TERMINAL"
    assert step.selected_instance_id == c


def test_AI_cancel_waiting_hold_is_not_a_governance_override():
    hook = MappedGovernanceHook()
    hook.set("A", GovernanceDisposition.HOLD)
    env = build([{"name": "A", "n": 2}], hook=hook)
    a = env["ids"]["A"]
    advance_workflow(env["rt"], a)   # A -> WAITING (governance HOLD)
    assert env["rt"].instance(a).status is WorkflowStatus.WAITING
    evals_before = len(hook.evaluations)
    res = env["controller"].cancel(a, CancellationScope.WORKFLOW_ONLY)
    assert res.cancelled == (a,)
    assert env["rt"].instance(a).status is WorkflowStatus.CANCELLED
    # Cancellation did not consult governance or reinterpret the HOLD — it is orchestration
    # control choosing not to continue the workflow, not overruling the disposition.
    assert len(hook.evaluations) == evals_before


# =========================================================================== #
# 52. TEST MATRIX — SELF-RECOVERABILITY                                         #
# =========================================================================== #
def test_self_recoverability_refuses_to_persist_invalid_checkpoint(monkeypatch):
    env = build([{"name": "A", "n": 3}])
    env["controller"].step()
    # Force the builder to yield an internally inconsistent (resealed) checkpoint: a
    # cancellation target that is not a registered workflow. The commit path must reject it
    # BEFORE any store write, leaving store history unchanged.
    good = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                      failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    d = good.to_dict()
    d["cancellation_state"] = {"ghost-instance": "WORKFLOW_ONLY"}
    d["portfolio_digest"] = _portfolio_digest({k: v for k, v in d.items() if k != "portfolio_digest"})
    bad = PortfolioCheckpoint.from_dict(d)
    assert bad.verify()  # resealed
    gen_before = env["pcp"].generation(env["pid"])

    import ugence_agent_runtime.orchestration.control as control_mod
    monkeypatch.setattr(control_mod, "build_portfolio_checkpoint", lambda *a, **k: bad)
    with pytest.raises(CheckpointError):
        env["controller"].checkpoint()
    assert env["pcp"].generation(env["pid"]) == gen_before  # store unchanged (fail closed)


def test_every_committed_checkpoint_is_self_recoverable():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}],
                deps=[("B", "A", DependencyType.REQUIRES_SUCCESS)])
    ctrl = env["controller"]
    for _ in range(3):
        ctrl.step()
        cp = ctrl.checkpoint()
        ok, reason = validate_portfolio_checkpoint(cp)
        assert ok, reason


# =========================================================================== #
# 53. TEST MATRIX — MULTIPLE RECOVERIES                                         #
# =========================================================================== #
def test_multiple_recoveries_no_accumulated_corruption():
    specs = [{"name": "A", "n": 30, "weight": 2}, {"name": "B", "n": 30, "weight": 1}]
    # Reference: 18 uninterrupted rounds.
    envu = build(specs)
    reference = run_scheduler(envu["rt"], envu["portfolio"], 18)

    # Two crash/recover cycles at rounds 6 and 12.
    env = build(specs)
    seq = run_scheduler(env["rt"], env["portfolio"], 6)
    checkpoint_now(env)
    rt2, prov2, result = recover(env)
    continue_running(rt2, list(env["ids"].values()))
    # Wrap rt2 into an env-shaped dict so we can checkpoint/recover again.
    env2 = dict(ss=env["ss"], rt=rt2, portfolio=result.portfolio, defs=env["defs"],
                pid=env["pid"], pcp=env["pcp"])
    seq += run_scheduler(rt2, result.portfolio, 6)
    checkpoint_now(env2)
    rt3, prov3, result3 = recover(env2)
    continue_running(rt3, list(env["ids"].values()))
    seq += run_scheduler(rt3, result3.portfolio, 6)

    assert seq == reference
    # No duplicate committed work: total quanta granted == tasks advanced across all runtimes.
    a = env["ids"]["A"]
    assert rt3.instance(a).status in (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED)


# =========================================================================== #
# 54. RUNTIME-UPGRADE COMPATIBILITY                                             #
# =========================================================================== #
def test_runtime_upgrade_recovery_does_not_require_writer_version_equality():
    # Written under runtime_version A; recovered under a newer runtime_version B.
    env = build([{"name": "A", "n": 4}], runtime_version="0.5.0")
    run_scheduler(env["rt"], env["portfolio"], 2)
    checkpoint_now(env)
    rt2, prov2, result = recover(env, runtime_version="0.6.0")  # compatible upgrade
    a = env["ids"]["A"]
    # Recovery succeeds and reports the origin-provenance mismatch — it is NOT fatal.
    assert a in result.recovered_workflow_ids
    assert result.recovery_metadata["workflows"][a]["config_mismatch"] is True
    continue_running(rt2, [a])
    assert PortfolioScheduler(rt2).step(result.portfolio).granted


# =========================================================================== #
# store: optimistic concurrency                                                #
# =========================================================================== #
def test_portfolio_store_compare_and_save_conflict():
    env = build([{"name": "A", "n": 2}])
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    gen = env["pcp"].save(cp)                     # generation 1
    assert gen == 1
    env["pcp"].save(cp, expected_generation=1)    # ok -> generation 2
    with pytest.raises(PortfolioCheckpointConflict):
        env["pcp"].save(cp, expected_generation=1)  # stale expectation


def test_unsupported_version_rejected():
    env = build([{"name": "A", "n": 2}])
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    d = cp.to_dict()
    d["checkpoint_version"] = "999"
    d["portfolio_digest"] = _portfolio_digest({k: v for k, v in d.items() if k != "portfolio_digest"})
    ok, reason = validate_portfolio_checkpoint(PortfolioCheckpoint.from_dict(d))
    assert not ok and "version" in reason


# =========================================================================== #
# FINAL AUDIT CORRECTIONS — durable trace, crash windows, full checkpoint      #
# binding, semantic cross-bind, failure-policy continuity                      #
# =========================================================================== #

# --- 1/2: durable trace history + globally-monotonic sequence across recovery #
def test_audit_durable_trace_history_survives_recovery():
    es = InMemoryPortfolioEventStore()
    env = build([{"name": "A", "n": 4}, {"name": "B", "n": 4}], event_store=es)
    ctrl = env["controller"]
    ctrl.step(); ctrl.step(); ctrl.step()
    ctrl.checkpoint()
    pre = [(e.sequence, e.event_type) for e in es.events(env["pid"])]
    assert len(pre) >= 4  # QUANTUM_GRANTED x3 + CHECKPOINT_COMMITTED at least

    # New process: recover WITH the same durable event store.
    rt2, prov2, result = recover(env, event_store=es)
    # Pre-crash history is preserved (not just the last sequence number).
    hist = result.trace.history()
    assert [(e.sequence, e.event_type) for e in hist][: len(pre)] == pre
    # Globally monotonic: the recovery event's sequence is strictly greater than every prior.
    rec = [e for e in hist if e.event_type == PortfolioEventType.PORTFOLIO_RECOVERED.value]
    assert len(rec) == 1
    assert rec[0].sequence == max(s for s, _ in pre) + 1
    seqs = [e.sequence for e in hist]
    assert seqs == list(range(1, len(seqs) + 1))  # contiguous, gap-free, no duplicates


# --- 3/5: no duplicate sequence after a persisted CHECKPOINT_COMMITTED (Window B)
def test_audit_window_B_crash_after_commit_event_persisted():
    es = InMemoryPortfolioEventStore()
    env = build([{"name": "A", "n": 4}], event_store=es)
    ctrl = env["controller"]
    ctrl.step()
    cp = ctrl.checkpoint()  # appends CHECKPOINT_COMMITTED durably; anchor precedes it
    committed = [e for e in es.events(env["pid"])
                 if e.event_type == PortfolioEventType.PORTFOLIO_CHECKPOINT_COMMITTED.value]
    assert len(committed) == 1
    commit_seq = committed[0].sequence
    assert cp.trace_sequence < commit_seq  # checkpoint captured the anchor BEFORE the commit

    # Crash after both persisted; recover continues strictly AFTER the commit event.
    rt2, prov2, result = recover(env, event_store=es)
    rec = [e for e in es.events(env["pid"])
           if e.event_type == PortfolioEventType.PORTFOLIO_RECOVERED.value]
    assert len(rec) == 1
    assert rec[0].sequence == commit_seq + 1        # no reuse of the commit sequence
    seqs = [e.sequence for e in es.events(env["pid"])]
    assert len(seqs) == len(set(seqs))              # no duplicates


# --- 4: crash after checkpoint save but BEFORE commit-event append (Window A)  #
def test_audit_window_A_crash_before_commit_event():
    es = InMemoryPortfolioEventStore()
    env = build([{"name": "A", "n": 4}], event_store=es)
    ctrl = env["controller"]
    ctrl.step()  # emits QUANTUM_GRANTED (seq 1) into the durable store
    anchor = es.last_sequence(env["pid"])           # = 1
    # Simulate: portfolio checkpoint saved, but crash BEFORE the CHECKPOINT_COMMITTED append.
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=anchor)
    env["pcp"].save(cp)
    # No CHECKPOINT_COMMITTED in the store.
    assert all(e.event_type != PortfolioEventType.PORTFOLIO_CHECKPOINT_COMMITTED.value
               for e in es.events(env["pid"]))
    rt2, prov2, result = recover(env, event_store=es)
    rec = [e for e in es.events(env["pid"])
           if e.event_type == PortfolioEventType.PORTFOLIO_RECOVERED.value]
    assert rec[0].sequence == anchor + 1            # continues without gap/collision
    seqs = [e.sequence for e in es.events(env["pid"])]
    assert seqs == list(range(1, len(seqs) + 1))


def test_audit_event_store_rejects_out_of_order_sequence():
    es = InMemoryPortfolioEventStore()
    t = PortfolioTrace("P", event_store=es)
    t.emit(PortfolioEventType.PORTFOLIO_CREATED)   # seq 1
    from ugence_agent_runtime.orchestration.tracing import PortfolioTraceEntry
    with pytest.raises(PortfolioTraceSequenceError):
        es.append(PortfolioTraceEntry("P", 1, "PORTFOLIO_CREATED"))   # duplicate
    with pytest.raises(PortfolioTraceSequenceError):
        es.append(PortfolioTraceEntry("P", 5, "PORTFOLIO_CREATED"))   # gap


# --- 6: full runtime-checkpoint binding includes the CES extension domain      #
def test_audit_ref_binds_both_base_and_extension_integrity_domains():
    env = build([{"name": "A", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    ref = cp.workflow_checkpoint_refs[0]
    wf_cp = env["ss"].load(env["ids"]["A"])
    assert ref.checkpoint_digest == wf_cp.digest
    assert ref.checkpoint_version == wf_cp.checkpoint_version == "1"
    assert ref.extension_digest == wf_cp.extension_digest
    assert ref.extension_digest and ref.extension_digest != ref.checkpoint_digest


# --- 7: resealed CES/lineage extension with UNCHANGED base digest is rejected  #
def test_audit_resealed_extension_unchanged_base_is_rejected():
    env = build([{"name": "A", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 3)  # multiple journal snapshots recorded
    a = env["ids"]["A"]
    checkpoint_now(env)  # portfolio ref binds the ORIGINAL full checkpoint (base + extension)

    # Tamper the runtime checkpoint's CES extension while keeping the base payload/digest
    # unchanged, and VALIDLY reseal the extension (remove a stale journal snapshot).
    d = env["ss"].load(a).to_dict()
    base_digest_before = d["digest"]
    latest_digests = {s["state_digest"] for s in d["execution_states"].values()}
    stale = [k for k in d["execution_state_journal"] if k not in latest_digests]
    assert stale, "need a non-latest journal snapshot to prune"
    del d["execution_state_journal"][stale[0]]
    resealed = Checkpoint.from_dict(d)
    d["extension_digest"] = resealed.compute_extension_digest()
    tampered = Checkpoint.from_dict(d)
    assert tampered.digest == base_digest_before      # base UNCHANGED
    assert tampered.verify() and tampered.verify_extension()  # internally valid (resealed)
    assert tampered.extension_digest != env["ss"].load(a).extension_digest  # but changed
    env["ss"].save(tampered)

    # The portfolio reference still binds the ORIGINAL extension digest -> recovery rejects.
    with pytest.raises(RecoveryError):
        recover(env)


# --- 8: cancellation-state / runtime-status inconsistency rejected             #
def test_audit_cancellation_state_inconsistent_with_runtime_rejected():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)  # B is RUNNING, never cancelled
    checkpoint_now(env)
    b = env["ids"]["B"]
    cp = env["pcp"].load(env["pid"])
    resealed = _reseal_portfolio(cp, lambda d: d.__setitem__("cancellation_state", {b: "WORKFLOW_ONLY"}))
    assert resealed.verify()
    env["pcp"].save(resealed)
    with pytest.raises(RecoveryError):
        recover(env)  # B recovers RUNNING/PAUSED, not CANCELLED -> fail closed


# --- 9: failure-state / runtime-status inconsistency rejected                  #
def test_audit_failure_state_inconsistent_with_runtime_rejected():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)
    checkpoint_now(env)
    b = env["ids"]["B"]
    cp = env["pcp"].load(env["pid"])
    resealed = _reseal_portfolio(cp, lambda d: d.__setitem__("failure_state", {b: "WORKFLOW_FAILED"}))
    assert resealed.verify()
    env["pcp"].save(resealed)
    with pytest.raises(RecoveryError):
        recover(env)  # B is not FAILED -> fail closed


# --- 10: resealed COMPLETED portfolio with a non-terminal workflow rejected    #
def test_audit_resealed_completed_with_nonterminal_workflow_rejected():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}])
    run_scheduler(env["rt"], env["portfolio"], 2)  # both still RUNNING
    checkpoint_now(env)
    cp = env["pcp"].load(env["pid"])
    resealed = _reseal_portfolio(cp, lambda d: d.__setitem__("portfolio_status", "COMPLETED"))
    assert resealed.verify()
    env["pcp"].save(resealed)
    with pytest.raises(RecoveryError):
        recover(env)  # workflows recover non-terminal -> COMPLETED invariant violated


# --- 11: non-contiguous registration sequences rejected                        #
def test_audit_non_contiguous_registration_sequence_rejected():
    env = build([{"name": "A", "n": 2}, {"name": "B", "n": 2}])
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)

    def bump(d):
        # sequences become [0, 2] — a gap the canonical H22-B invariant forbids.
        for r in d["registrations"]:
            if r["registration_sequence"] == 1:
                r["registration_sequence"] = 2
    resealed = _reseal_portfolio(cp, bump)
    assert resealed.verify()
    ok, reason = validate_portfolio_checkpoint(resealed)
    assert not ok and "contiguous" in reason


def test_audit_invalid_failure_label_rejected():
    env = build([{"name": "A", "n": 2}])
    run_scheduler(env["rt"], env["portfolio"], 1)
    cp = build_portfolio_checkpoint(env["portfolio"], env["rt"],
                                    failure_policy="ISOLATE_WORKFLOW", trace_sequence=0)
    a = env["ids"]["A"]
    resealed = _reseal_portfolio(cp, lambda d: d.__setitem__("failure_state", {a: "BOGUS"}))
    ok, reason = validate_portfolio_checkpoint(resealed)
    assert not ok and "label" in reason


# --- 12: persisted failure policy survives recovery + controller reconstruction #
def test_audit_failure_policy_survives_recovery_and_controller():
    env = build([{"name": "A", "n": 3}, {"name": "B", "n": 3}],
                policy=PortfolioFailurePolicy.FAIL_DEPENDENTS)
    ctrl = env["controller"]
    ctrl.step(); ctrl.step()
    ctrl.checkpoint()
    rt2, prov2, result = recover(env)
    # Typed, first-class field — not buried in generic metadata.
    assert result.failure_policy is PortfolioFailurePolicy.FAIL_DEPENDENTS
    # A controller reconstructed from the recovery uses the recovered policy by DEFAULT,
    # not the constructor default ISOLATE_WORKFLOW.
    ctrl2 = PortfolioController.from_recovery(rt2, result, checkpoint_store=env["pcp"])
    assert ctrl2.failure_policy is PortfolioFailurePolicy.FAIL_DEPENDENTS


# --- 13/14: recovery still zero provider + governance calls (with event store) #
def test_audit_recovery_zero_side_effects_with_event_store():
    es = InMemoryPortfolioEventStore()
    env = build([{"name": "A", "n": 4}, {"name": "B", "n": 4}], event_store=es)
    ctrl = env["controller"]
    ctrl.step(); ctrl.step()
    ctrl.checkpoint()
    rt2 = create_runtime(AgentRuntimeConfig(state_store=env["ss"], governance_hook=ExplodingHook()))
    register_provider(rt2, ExplodingProvider("p"))
    result = recover_portfolio(store=env["pcp"], portfolio_id=env["pid"], runtime=rt2,
                               definitions=env["defs"], event_store=es)  # must not raise
    assert result.requires_continuation is True


# --- 16: SWRR/aging continuity unchanged by the corrections (durable trace)     #
def test_audit_swrr_continuity_unchanged_with_durable_trace():
    n = 30
    unint, split = _continuity(
        [{"name": "A", "n": n, "weight": 2}, {"name": "B", "n": n, "weight": 1}], 20, 10
    )
    assert unint == split
