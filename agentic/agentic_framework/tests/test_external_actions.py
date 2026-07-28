"""
Tests for H20 — Governed External Actions & Resource State.

Covers all 18 required scenarios:
 1. Authorized action execution (once).
 2. Unauthorized action denial (no adapter call, no mutation).
 3. ActionGate denial (policy blocks even an otherwise-authorized action).
 4. Approval binding (approval for one parameter set cannot authorize a changed one).
 5. Version conflict (stale expected version fails closed).
 6. Duplicate suppression (same idempotency key does not re-invoke the adapter).
 7. Duplicate suppression after restart.
 8. Unknown outcome (fault after adapter, before durable result → UNKNOWN, no replay).
 9. Reconciliation success (external evidence confirms; continue without re-executing).
10. Reconciliation failure (only the affected subtree follows failure behaviour).
11. Memory continuity (snapshots/results enter H14 with provenance + versions).
12. Assumption effects (durable external observation updates H13).
13. Localized replanning (a conflicted/failed action replans only its subtree).
14. Human review path (ActionGate REQUIRE_HUMAN_REVIEW → H19 approval resumes).
15. Compensation (a separate, linked, independently-authorized governed action).
16. Process-loss recovery at execution boundaries (no duplicate external mutation).
17. Trace reconstruction.
18. Regression — H10–H19 unchanged (separate full-suite run).
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
    HumanParticipant,
    ParticipantRegistry,
    # H13
    PlanAssumption,
    AssumptionState,
    AssumptionRegistry,
    AssumptionDependencyGraph,
    AssumptionContext,
    # H20
    ExternalResourceRef,
    ResourceSnapshot,
    ExternalActionIntent,
    ExternalActionExecutor,
    ExternalActionRecord,
    ActionStatus,
    ExecutionResultCode,
    GateOutcome,
    Reversibility,
    ReconciliationOutcome,
    ActionGateRequest,
    ActionGateDecision,
    ActionGate,
    AllowAllActionGate,
    RuleBasedActionGate,
    AdapterResult,
    InMemoryResourceAdapter,
    ScriptedResourceAdapter,
    ActionApproval,
    ActionAuthorityValidator,
    ActionFaultInjector,
    ActionFaultPoint,
    CompensationPlan,
    format_action_trace,
)

REF = ExternalResourceRef("prod-api", resource_type="deployment", provider="mock", sensitivity="high")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True,
                                                        outputs={k: "ok" for k in c.expected_outputs})))
    return r


def _goals():
    return [
        Goal("api", "api", required_capabilities=frozenset({"do"}), expected_outputs=("api",), priority=1),
        Goal("ui", "ui", required_capabilities=frozenset({"do"}), expected_outputs=("ui",), priority=2),
        Goal("deploy", "deploy", required_capabilities=frozenset({"do"}),
             dependencies=("api", "ui"), expected_outputs=("rel",), priority=3),
    ]


def _wc():
    return WaitCondition("rev", "deploy", kind=WaitKind.WAIT_FOR_EVENT, event_type="act", match=(("e", "p"),))


def _people():
    return ParticipantRegistry([
        HumanParticipant("lead", "Lead", permissions=frozenset({"deploy"}), trust_level=5),
        HumanParticipant("intern", "Intern", permissions=frozenset(), trust_level=1),
    ])


def _executor(adapter, gate=None, *, store=None, auth=None, fault=None):
    return ExternalActionExecutor(
        _registry(), store or InMemoryCheckpointStore(), gate or RuleBasedActionGate(),
        default_adapter=adapter,
        authority_validator=auth or ActionAuthorityValidator({"bot": frozenset({"deploy"})}),
        participants=_people(), fault=fault)


def _wf(ex):
    return ex.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                              run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wc()])


def _intent(action_id="a1", *, idem="idem-1", op="set:version", params=(("value", "v2"),),
            version=5, actor="bot", auth=frozenset({"deploy"}), ref=REF, goal="deploy",
            reversibility=Reversibility.COMPENSATABLE, assumption_effects=()):
    return ExternalActionIntent(
        action_id, "wf", goal, actor, "deploy", ref, op, parameters=params,
        expected_resource_version=version, authority_requirements=auth, idempotency_key=idem,
        reversibility=reversibility, assumption_effects=assumption_effects)


# ---------------------------------------------------------------------------
# 1. Authorized execution
# ---------------------------------------------------------------------------
class TestAuthorizedExecution:
    def test_authorized_action_executes_once(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        wf = _wf(ex)
        assert wf.status == WorkflowStatus.WAITING
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED     # pre-action work done
        res = ex.execute(wf, _intent(), timestamp=2)
        assert res.code == ExecutionResultCode.ACTION_EXECUTED
        assert res.record.status == ActionStatus.SUCCEEDED
        assert wf.tree.lookup("deploy").status == GoalStatus.COMPLETED
        assert wf.status == WorkflowStatus.COMPLETED
        assert adapter.read(REF).observed_version == 6                  # exactly one mutation


# ---------------------------------------------------------------------------
# 2. Unauthorized denial
# ---------------------------------------------------------------------------
class TestUnauthorizedDenial:
    def test_authority_failure_prevents_adapter_and_mutation(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter, auth=ActionAuthorityValidator({"bot": frozenset()}))
        wf = _wf(ex)
        res = ex.execute(wf, _intent(), timestamp=2)
        assert res.code == ExecutionResultCode.AUTHORITY_DENIED
        assert res.record.status == ActionStatus.DENIED
        assert adapter.read(REF).observed_version == 5                  # no mutation
        assert wf.status == WorkflowStatus.WAITING


# ---------------------------------------------------------------------------
# 3. ActionGate denial
# ---------------------------------------------------------------------------
class TestGateDenial:
    def test_policy_denial_blocks_authorized_action(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        gate = RuleBasedActionGate(deny_operations=frozenset({"set:version"}))
        ex = _executor(adapter, gate)
        wf = _wf(ex)
        res = ex.execute(wf, _intent(), timestamp=2)
        assert res.code == ExecutionResultCode.GATE_DENIED
        assert res.record.status == ActionStatus.DENIED
        assert adapter.read(REF).observed_version == 5


# ---------------------------------------------------------------------------
# 4. Approval binding
# ---------------------------------------------------------------------------
class TestApprovalBinding:
    def test_approval_bound_to_exact_parameters(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        gate = RuleBasedActionGate(review_sensitivities=frozenset({"high"}))
        ex = _executor(adapter, gate)
        wf = _wf(ex)
        original = _intent(params=(("value", "v2"),))
        assert ex.execute(wf, original, timestamp=2).code == ExecutionResultCode.REQUIRES_HUMAN_REVIEW
        # An approval bound to a DIFFERENT (materially changed) parameter set is invalid.
        changed = _intent(params=(("value", "v3"),))
        bad = ActionApproval("ap", "a1", changed.parameter_digest(), "lead", timestamp=3)
        res = ex.submit_action_approval(wf, bad, timestamp=3)
        assert res.code == ExecutionResultCode.APPROVAL_BINDING_VIOLATION
        assert adapter.read(REF).observed_version == 5                  # still not executed


# ---------------------------------------------------------------------------
# 5. Version conflict
# ---------------------------------------------------------------------------
class TestVersionConflict:
    def test_stale_version_fails_closed(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 7, {})     # newer than expected
        ex = _executor(adapter)
        wf = _wf(ex)
        res = ex.execute(wf, _intent(version=5), timestamp=2)
        assert res.code == ExecutionResultCode.RESOURCE_VERSION_CONFLICT
        assert res.record.status == ActionStatus.CONFLICTED
        assert adapter.read(REF).observed_version == 7                    # never overwritten

    def test_precondition_failure(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {"locked": True})
        ex = _executor(adapter)
        wf = _wf(ex)
        intent = ExternalActionIntent("a1", "wf", "deploy", "bot", "deploy", REF, "set:version",
                                      parameters=(("value", "v2"),), expected_resource_version=5,
                                      preconditions=(("locked", False),),
                                      authority_requirements=frozenset({"deploy"}), idempotency_key="i")
        res = ex.execute(wf, intent, timestamp=2)
        assert res.code == ExecutionResultCode.PRECONDITION_FAILED
        assert adapter.read(REF).observed_version == 5


# ---------------------------------------------------------------------------
# 6. Duplicate suppression
# ---------------------------------------------------------------------------
class TestDuplicateSuppression:
    def test_same_action_resubmission_suppressed(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        wf = _wf(ex)
        r1 = ex.execute(wf, _intent(), timestamp=2)
        r2 = ex.execute(wf, _intent(), timestamp=3)
        assert r1.code == ExecutionResultCode.ACTION_EXECUTED
        assert r2.code == ExecutionResultCode.DUPLICATE_ACTION_SUPPRESSED
        assert adapter.read(REF).observed_version == 6                    # only one mutation

    def test_distinct_action_same_idempotency_key_suppressed(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        wf = _wf(ex)
        ex.execute(wf, _intent("a1", idem="shared", version=5), timestamp=2)
        r2 = ex.execute(wf, _intent("a2", idem="shared", version=6, params=(("value", "v9"),)), timestamp=3)
        assert r2.code == ExecutionResultCode.DUPLICATE_ACTION_SUPPRESSED
        assert adapter.read(REF).observed_version == 6


# ---------------------------------------------------------------------------
# 7. Duplicate suppression after restart
# ---------------------------------------------------------------------------
class TestDuplicateSuppressionAfterRestart:
    def test_suppressed_across_process_loss(self):
        store = InMemoryCheckpointStore()
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter, store=store)
        wf = _wf(ex)
        ex.execute(wf, _intent(), timestamp=2)
        assert adapter.read(REF).observed_version == 6
        del ex, wf
        # New runtime restores workflow + action records.
        ex2, wf2 = ExternalActionExecutor.restore(
            store, "wf", registry=_registry(), gate=RuleBasedActionGate(), default_adapter=adapter,
            authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}), participants=_people())
        res = ex2.execute(wf2, _intent(), timestamp=5)
        assert res.code == ExecutionResultCode.DUPLICATE_ACTION_SUPPRESSED
        assert adapter.read(REF).observed_version == 6                    # still only one mutation


# ---------------------------------------------------------------------------
# 8. Unknown outcome
# ---------------------------------------------------------------------------
class TestUnknownOutcome:
    def test_fault_after_adapter_before_result_is_unknown(self):
        succ = AdapterResult(True, "SUCCEEDED", external_request_ref="req:i1",
                             external_result_ref="res:x#6", new_version=6)
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})}, script={"a1": succ})
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        ex = _executor(adapter, fault=fault)
        wf = _wf(ex)
        res = ex.execute(wf, _intent(idem="i1"), timestamp=2)
        assert res.code == ExecutionResultCode.UNKNOWN_OUTCOME
        assert res.record.status == ActionStatus.UNKNOWN
        assert wf.tree.lookup("deploy").status == GoalStatus.BLOCKED      # subtree blocked
        assert wf.status == WorkflowStatus.WAITING                        # not completed, not failed

    def test_unknown_is_not_auto_replayed(self):
        succ = AdapterResult(True, "SUCCEEDED", external_request_ref="req:i1", new_version=6)
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})}, script={"a1": succ})
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        ex = _executor(adapter, fault=fault)
        wf = _wf(ex)
        ex.execute(wf, _intent(idem="i1"), timestamp=2)
        # Re-submitting the same UNKNOWN action does not blindly re-run it — it
        # is refused and routed to reconciliation.
        res = ex.execute(wf, _intent(idem="i1"), timestamp=3)
        assert res.code == ExecutionResultCode.UNKNOWN_OUTCOME
        assert res.record.status == ActionStatus.UNKNOWN


# ---------------------------------------------------------------------------
# 9. Reconciliation success
# ---------------------------------------------------------------------------
class TestReconciliationSuccess:
    def test_confirmed_success_continues_without_reexecuting(self):
        succ = AdapterResult(True, "SUCCEEDED", external_request_ref="req:i1",
                             external_result_ref="res:x#6", new_version=6, post_state={"version": "v2"})
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})}, script={"a1": succ},
                                          reconcile_script={"i1": succ})
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        ex = _executor(adapter, fault=fault)
        wf = _wf(ex)
        ex.execute(wf, _intent(idem="i1"), timestamp=2)                   # → UNKNOWN
        rc = ex.reconciler.reconcile(wf, "a1", timestamp=3)
        assert rc.outcome == ReconciliationOutcome.CONFIRMED_SUCCEEDED
        assert rc.record.status == ActionStatus.RECONCILED
        assert wf.tree.lookup("deploy").status == GoalStatus.COMPLETED
        assert wf.status == WorkflowStatus.COMPLETED


# ---------------------------------------------------------------------------
# 10. Reconciliation failure
# ---------------------------------------------------------------------------
class TestReconciliationFailure:
    def test_confirmed_failure_only_affects_subtree(self):
        fail = AdapterResult(False, "FAILED", error="external failure confirmed")
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})},
                                          script={"a1": AdapterResult(True, "SUCCEEDED", new_version=6)},
                                          reconcile_script={"i1": fail})
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        ex = _executor(adapter, fault=fault)
        wf = _wf(ex)
        ex.execute(wf, _intent(idem="i1"), timestamp=2)                   # → UNKNOWN
        rc = ex.reconciler.reconcile(wf, "a1", timestamp=3)
        assert rc.outcome == ReconciliationOutcome.CONFIRMED_FAILED
        assert wf.tree.lookup("deploy").status == GoalStatus.FAILED
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED       # sibling untouched
        assert wf.tree.lookup("ui").status == GoalStatus.COMPLETED

    def test_still_unknown_when_no_evidence(self):
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})},
                                          script={"a1": AdapterResult(True, "SUCCEEDED", new_version=6)})
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
        ex = _executor(adapter, fault=fault)
        wf = _wf(ex)
        ex.execute(wf, _intent(idem="i1"), timestamp=2)
        rc = ex.reconciler.reconcile(wf, "a1", timestamp=3)
        assert rc.outcome == ReconciliationOutcome.STILL_UNKNOWN
        assert wf.tree.lookup("deploy").status == GoalStatus.BLOCKED


# ---------------------------------------------------------------------------
# 11. Memory continuity
# ---------------------------------------------------------------------------
class TestMemoryContinuity:
    def test_result_and_snapshot_enter_memory_with_provenance(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        wf = _wf(ex)
        ex.execute(wf, _intent(), timestamp=2)
        result_rec = wf.memory.peek("action_result:deploy")
        assert result_rec is not None
        assert result_rec.value["status"] == ActionStatus.SUCCEEDED
        # The durable action record is versioned in memory (append-only writes).
        recs = wf.memory.records("__action__:a1")
        assert len(recs) >= 2                                             # PROPOSED … SUCCEEDED
        assert recs[-1].value["intent"]["action_id"] == "a1"


# ---------------------------------------------------------------------------
# 12. Assumption effects
# ---------------------------------------------------------------------------
class TestAssumptionEffects:
    def test_durable_observation_updates_assumption(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        reg = AssumptionRegistry([PlanAssumption("deploy_healthy", "target healthy",
                                                 state=AssumptionState.INVALID)])
        ctx = AssumptionContext(reg, AssumptionDependencyGraph())
        wf = ex.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                                assumption_context=ctx, run_budget=RunBudget(RunBudgetLimits()),
                                wait_conditions=[_wc()])
        assert ctx.registry.get("deploy_healthy").state == AssumptionState.INVALID
        ex.execute(wf, _intent(assumption_effects=(("deploy_healthy", AssumptionState.VALID),)), timestamp=2)
        assert ctx.registry.get("deploy_healthy").state == AssumptionState.VALID


# ---------------------------------------------------------------------------
# 13. Localized replanning
# ---------------------------------------------------------------------------
class TestLocalizedReplanning:
    def test_conflicted_action_replans_only_its_subtree(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 7, {})     # forces conflict
        ex = _executor(adapter)
        wf = _wf(ex)
        res = ex.execute(wf, _intent(version=5), timestamp=2)
        assert res.code == ExecutionResultCode.RESOURCE_VERSION_CONFLICT
        # Replan ONLY the deploy leaf; siblings stay COMPLETED.
        fix = Goal("deploy_v2", "deploy retry", required_capabilities=frozenset({"do"}),
                   expected_outputs=("rel",), priority=3)
        ex.replan_action_goal(wf, "deploy", [fix])
        assert wf.tree.lookup("deploy").status == GoalStatus.ABORTED
        assert wf.tree.lookup("api").status == GoalStatus.COMPLETED
        assert wf.tree.lookup("deploy_v2") is not None


# ---------------------------------------------------------------------------
# 14. Human review path
# ---------------------------------------------------------------------------
class TestHumanReviewPath:
    def test_gate_requires_review_then_approval_resumes(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        gate = RuleBasedActionGate(review_sensitivities=frozenset({"high"}))
        ex = _executor(adapter, gate)
        wf = _wf(ex)
        intent = _intent()
        r1 = ex.execute(wf, intent, timestamp=2)
        assert r1.code == ExecutionResultCode.REQUIRES_HUMAN_REVIEW
        assert adapter.read(REF).observed_version == 5                    # not yet executed
        approval = ActionApproval("ap1", "a1", intent.parameter_digest(), "lead", timestamp=3)
        r2 = ex.submit_action_approval(wf, approval, timestamp=4)
        assert r2.code == ExecutionResultCode.ACTION_EXECUTED
        assert wf.tree.lookup("deploy").status == GoalStatus.COMPLETED
        assert adapter.read(REF).observed_version == 6

    def test_unauthorized_approver_denied(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        gate = RuleBasedActionGate(review_sensitivities=frozenset({"high"}))
        ex = _executor(adapter, gate)
        wf = _wf(ex)
        intent = _intent()
        ex.execute(wf, intent, timestamp=2)
        bad = ActionApproval("ap", "a1", intent.parameter_digest(), "intern", timestamp=3)
        res = ex.submit_action_approval(wf, bad, timestamp=3)
        assert res.code == ExecutionResultCode.AUTHORITY_DENIED
        assert adapter.read(REF).observed_version == 5


# ---------------------------------------------------------------------------
# 15. Compensation
# ---------------------------------------------------------------------------
class TestCompensation:
    def test_compensation_is_separate_linked_governed_action(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = ExternalActionExecutor(_registry(), InMemoryCheckpointStore(), RuleBasedActionGate(),
                                    default_adapter=adapter,
                                    authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}))
        wf = ex.create_workflow("wf", StaticDecomposer().decompose(
            "m", [Goal("act", "act", required_capabilities=frozenset({"do"}), expected_outputs=("x",), priority=1)]),
            WorkingMemory(), run_budget=RunBudget(RunBudgetLimits()))
        orig = ExternalActionIntent("o1", "wf", "act", "bot", "write", REF, "set:flag",
                                    parameters=(("value", "on"),), authority_requirements=frozenset({"deploy"}),
                                    idempotency_key="io", reversibility=Reversibility.COMPENSATABLE)
        assert ex.execute(wf, orig, timestamp=2).code == ExecutionResultCode.ACTION_EXECUTED
        assert adapter.read(REF).observed_state.get("flag") == "on"
        comp = ExternalActionIntent("c1", "wf", "act", "bot", "write", REF, "set:flag",
                                    parameters=(("value", "off"),), authority_requirements=frozenset({"deploy"}),
                                    idempotency_key="ic")
        rc = ex.compensate(wf, "o1", comp, timestamp=3)
        assert rc.code == ExecutionResultCode.ACTION_EXECUTED
        assert adapter.read(REF).observed_state.get("flag") == "off"
        original = ex._load_record(wf, "o1")
        assert "c1" in original.compensation_references                    # linked, not rewritten
        assert original.status == ActionStatus.COMPENSATED
        # Original success transition is preserved in history (append-only).
        assert any(t.to_status == ActionStatus.SUCCEEDED for t in original.lifecycle_history)


# ---------------------------------------------------------------------------
# 16. Process-loss recovery (EXECUTING → UNKNOWN on restore)
# ---------------------------------------------------------------------------
class TestProcessLossRecovery:
    def test_restore_from_executing_yields_unknown_no_duplicate(self):
        store = InMemoryCheckpointStore()
        succ = AdapterResult(True, "SUCCEEDED", external_request_ref="req:i1", new_version=6)
        adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})}, script={"a1": succ})
        # Fault right at the reservation checkpoint boundary — record persists as EXECUTING.
        fault = ActionFaultInjector(ActionFaultPoint.AFTER_IDEMPOTENCY_RESERVATION)
        ex = _executor(adapter, store=store, fault=fault)
        wf = _wf(ex)
        with pytest.raises(ActionFaultInjector.InjectedFault):
            ex.execute(wf, _intent(idem="i1"), timestamp=2)
        del ex, wf
        # Restore: the EXECUTING action becomes UNKNOWN and its goal is blocked.
        ex2, wf2 = ExternalActionExecutor.restore(
            store, "wf", registry=_registry(), gate=RuleBasedActionGate(), default_adapter=adapter,
            authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}), participants=_people())
        rec = ex2._load_record(wf2, "a1")
        assert rec.status == ActionStatus.UNKNOWN
        assert wf2.tree.lookup("deploy").status == GoalStatus.BLOCKED


# ---------------------------------------------------------------------------
# 17. Trace reconstruction
# ---------------------------------------------------------------------------
class TestTraceReconstruction:
    def test_full_lifecycle_trace(self):
        adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
        ex = _executor(adapter)
        wf = _wf(ex)
        res = ex.execute(wf, _intent(), timestamp=2)
        trace = format_action_trace(res.record)
        for token in ["PROPOSED", "VALIDATING", "AUTHORIZED", "READY_TO_EXECUTE",
                      "EXECUTING", "SUCCEEDED", "gate: ALLOW", "idempotency_key=idem-1"]:
            assert token in trace
        # Record round-trips through its durable form.
        rebuilt = ExternalActionRecord.from_dict(res.record.to_dict())
        assert rebuilt.status == ActionStatus.SUCCEEDED
        assert rebuilt.intent.action_id == "a1"


# ---------------------------------------------------------------------------
# Resource identity stability
# ---------------------------------------------------------------------------
class TestResourceIdentity:
    def test_identity_independent_of_mutable_attributes(self):
        a = ExternalResourceRef("r1", provider="p", tenant_id="t", namespace="n",
                                external_version="7", attributes=(("name", "Old"),))
        b = ExternalResourceRef("r1", provider="p", tenant_id="t", namespace="n",
                                external_version="9", attributes=(("name", "New"),))
        assert a.key == b.key                                             # identity is stable
        assert ExternalResourceRef.from_dict(a.to_dict()).key == a.key
