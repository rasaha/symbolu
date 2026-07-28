"""
H20 — Governed External Actions & Resource State (example).

Every external side effect crosses its own governed execution boundary.  An
authorized *goal* does not authorize every external action inside it: each
action is proposed as an immutable intent, authority- and policy-checked
(ActionGate), validated against live resource preconditions immediately before
mutation, duplicate-suppressed by a stable idempotency key, and its result is
durably recorded *before* the goal may complete.  An action interrupted after
the adapter ran but before its result was durably recorded becomes UNKNOWN —
never silently replayed — and is resolved by reconciliation.

Runs fully offline with deterministic in-memory / scripted adapters — no API
key, no network, no real cloud, no database.  Deterministic timestamps only.

Scope: H20 adds governed, durable external-action execution with resource
preconditions, durable duplicate suppression, and unknown-outcome
reconciliation.  It is NOT a distributed transaction coordinator, NOT universal
exactly-once execution across arbitrary systems, and does NOT auto-roll-back
irreversible operations.
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
    StaticDecomposer,
    WaitCondition,
    WaitKind,
    InMemoryCheckpointStore,
    HumanParticipant,
    ParticipantRegistry,
    ExternalResourceRef,
    ExternalActionIntent,
    ExternalActionExecutor,
    ExecutionResultCode,
    Reversibility,
    ReconciliationOutcome,
    RuleBasedActionGate,
    AdapterResult,
    InMemoryResourceAdapter,
    ScriptedResourceAdapter,
    ActionApproval,
    ActionAuthorityValidator,
    ActionFaultInjector,
    ActionFaultPoint,
    format_action_trace,
)

REF = ExternalResourceRef("prod-api", resource_type="deployment", provider="mock", sensitivity="high")


def _registry():
    r = CapabilityRegistry()
    r.register(AgentProfile("bot", capabilities=frozenset({"do"}), trust_level=5),
               ScriptedWorker(lambda c, m: WorkerResult(success=True,
                                                        outputs={k: "ok" for k in c.expected_outputs})))
    return r


def _goals():
    return [
        Goal("api", "build api", required_capabilities=frozenset({"do"}), expected_outputs=("api",), priority=1),
        Goal("ui", "build ui", required_capabilities=frozenset({"do"}), expected_outputs=("ui",), priority=2),
        Goal("deploy", "deploy to prod", required_capabilities=frozenset({"do"}),
             dependencies=("api", "ui"), expected_outputs=("release",), priority=3),
    ]


def _wc():
    return WaitCondition("release", "deploy", kind=WaitKind.WAIT_FOR_EVENT,
                         event_type="deploy_done", match=(("env", "prod"),))


def _people():
    return ParticipantRegistry([
        HumanParticipant("lead", "Release Lead", permissions=frozenset({"deploy"}), trust_level=5),
    ])


def _executor(adapter, gate=None, *, store=None, fault=None):
    return ExternalActionExecutor(
        _registry(), store or InMemoryCheckpointStore(), gate or RuleBasedActionGate(),
        default_adapter=adapter,
        authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}),
        participants=_people(), fault=fault)


def _wf(ex):
    return ex.create_workflow("wf", StaticDecomposer().decompose("m", _goals()), WorkingMemory(),
                              run_budget=RunBudget(RunBudgetLimits()), wait_conditions=[_wc()])


def _intent(action_id="a1", *, idem="idem-1", params=(("value", "v2"),), version=5):
    return ExternalActionIntent("a1" if action_id == "a1" else action_id, "wf", "deploy", "bot", "deploy",
                                REF, "set:version", parameters=params, expected_resource_version=version,
                                authority_requirements=frozenset({"deploy"}), idempotency_key=idem,
                                reversibility=Reversibility.COMPENSATABLE)


def _rule(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def scenario_authorized_once():
    _rule("1. Authorized action executes exactly once; result committed before goal")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    ex = _executor(adapter); wf = _wf(ex)
    print(f"  pre-action goals  : api={wf.tree.lookup('api').status} deploy={wf.tree.lookup('deploy').status}")
    print(f"  resource version  : {adapter.read(REF).observed_version}")
    res = ex.execute(wf, _intent(), timestamp=2)
    print(f"  result            : {res.code}   action={res.record.status}")
    print(f"  deploy / workflow : {wf.tree.lookup('deploy').status} / {wf.status}")
    print(f"  resource version  : {adapter.read(REF).observed_version}  (exactly one mutation)")


def scenario_authority_and_gate():
    _rule("2. Authority denial and ActionGate denial both stop before the adapter")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    ex = _executor(adapter, gate=None)
    ex.authority = ActionAuthorityValidator({"bot": frozenset()})   # no execution authority
    wf = _wf(ex)
    r = ex.execute(wf, _intent(), timestamp=2)
    print(f"  authority denial  : {r.code}   resource unchanged v={adapter.read(REF).observed_version}")

    adapter2 = InMemoryResourceAdapter(); adapter2.seed(REF, 5, {})
    ex2 = _executor(adapter2, RuleBasedActionGate(deny_operations=frozenset({"set:version"})))
    wf2 = _wf(ex2)
    r2 = ex2.execute(wf2, _intent(), timestamp=2)
    print(f"  policy (gate) deny: {r2.code}   resource unchanged v={adapter2.read(REF).observed_version}")


def scenario_version_conflict():
    _rule("3. Stale resource version fails closed — never overwrites newer state")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 7, {})   # newer than the intent expects
    ex = _executor(adapter); wf = _wf(ex)
    r = ex.execute(wf, _intent(version=5), timestamp=2)
    print(f"  expected v5, observed v7 → {r.code}")
    print(f"  action status     : {r.record.status}   resource still v={adapter.read(REF).observed_version}")


def scenario_duplicate():
    _rule("4. Duplicate suppression — same idempotency key never re-invokes the adapter")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    ex = _executor(adapter); wf = _wf(ex)
    r1 = ex.execute(wf, _intent(), timestamp=2)
    r2 = ex.execute(wf, _intent(), timestamp=3)
    print(f"  first / second    : {r1.code} / {r2.code}")
    print(f"  resource version  : {adapter.read(REF).observed_version}  (single mutation)")


def scenario_human_review():
    _rule("5. Sensitive action requires human review; approval binds to exact parameters")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    gate = RuleBasedActionGate(review_sensitivities=frozenset({"high"}))
    ex = _executor(adapter, gate); wf = _wf(ex)
    intent = _intent()
    r1 = ex.execute(wf, intent, timestamp=2)
    print(f"  gate outcome      : {r1.code}   resource still v={adapter.read(REF).observed_version}")
    approval = ActionApproval("ap1", "a1", intent.parameter_digest(), "lead", timestamp=3, rationale="ship")
    r2 = ex.submit_action_approval(wf, approval, timestamp=4)
    print(f"  after approval    : {r2.code}   deploy={wf.tree.lookup('deploy').status} wf={wf.status}")
    print(f"  resource version  : {adapter.read(REF).observed_version}")


def scenario_unknown_and_reconcile():
    _rule("6. Interrupted action → UNKNOWN (no replay) → reconciliation resolves it")
    succ = AdapterResult(True, "SUCCEEDED", external_request_ref="req:i1",
                         external_result_ref="res:prod#6", new_version=6, post_state={"version": "v2"})
    adapter = ScriptedResourceAdapter(resources={REF.key: (5, {})}, script={"a1": succ},
                                      reconcile_script={"i1": succ})
    fault = ActionFaultInjector(ActionFaultPoint.AFTER_ADAPTER_BEFORE_RESULT)
    ex = _executor(adapter, fault=fault); wf = _wf(ex)
    r = ex.execute(wf, _intent(idem="i1"), timestamp=2)
    print(f"  interrupted       : {r.code}   action={r.record.status}")
    print(f"  deploy / workflow : {wf.tree.lookup('deploy').status} / {wf.status}  (subtree blocked, not failed)")
    # Re-submitting does NOT replay — it is refused pending reconciliation.
    retry = ex.execute(wf, _intent(idem="i1"), timestamp=3)
    print(f"  blind retry       : {retry.code}  (never auto-replayed)")
    rc = ex.reconciler.reconcile(wf, "a1", timestamp=4)
    print(f"  reconciliation    : {rc.outcome}   action={rc.record.status}")
    print(f"  deploy / workflow : {wf.tree.lookup('deploy').status} / {wf.status}")


def scenario_compensation():
    _rule("7. Compensation is a separate, linked, independently-governed action")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    ex = ExternalActionExecutor(_registry(), InMemoryCheckpointStore(), RuleBasedActionGate(),
                                default_adapter=adapter,
                                authority_validator=ActionAuthorityValidator({"bot": frozenset({"deploy"})}))
    wf = ex.create_workflow("wf", StaticDecomposer().decompose(
        "m", [Goal("act", "flip flag", required_capabilities=frozenset({"do"}),
                   expected_outputs=("x",), priority=1)]),
        WorkingMemory(), run_budget=RunBudget(RunBudgetLimits()))
    orig = ExternalActionIntent("o1", "wf", "act", "bot", "write", REF, "set:flag",
                                parameters=(("value", "on"),), authority_requirements=frozenset({"deploy"}),
                                idempotency_key="io", reversibility=Reversibility.COMPENSATABLE)
    ex.execute(wf, orig, timestamp=2)
    print(f"  original action   : flag={adapter.read(REF).observed_state.get('flag')}")
    comp = ExternalActionIntent("c1", "wf", "act", "bot", "write", REF, "set:flag",
                                parameters=(("value", "off"),), authority_requirements=frozenset({"deploy"}),
                                idempotency_key="ic")
    ex.compensate(wf, "o1", comp, timestamp=3)
    original = ex._load_record(wf, "o1")
    print(f"  compensated       : flag={adapter.read(REF).observed_state.get('flag')}   "
          f"original status={original.status}")
    print(f"  linkage           : original.compensation_references={original.compensation_references}")


def scenario_trace():
    _rule("8. One continuous, reconstructable external-action trace")
    adapter = InMemoryResourceAdapter(); adapter.seed(REF, 5, {})
    ex = _executor(adapter); wf = _wf(ex)
    res = ex.execute(wf, _intent(), timestamp=2)
    print(format_action_trace(res.record))


if __name__ == "__main__":
    scenario_authorized_once()
    scenario_authority_and_gate()
    scenario_version_conflict()
    scenario_duplicate()
    scenario_human_review()
    scenario_unknown_and_reconcile()
    scenario_compensation()
    scenario_trace()
    print("\n" + "=" * 70)
    print("All H20 governed-external-action scenarios ran deterministically (no API key).")
    print("=" * 70)
