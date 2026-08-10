"""Canonical Execution State tests.

Covers the required contract (section 18): determinism, per-field sensitivity, proposal
linkage, no duplicated action identity, governance-lineage fidelity, checkpoint round
trip, legacy-checkpoint compatibility, tampering, recovery safety, event anchoring,
immutability, agent-lineage neutrality, and the authority boundary.
"""
from __future__ import annotations

import dataclasses

import pytest

from ugence_agent_runtime.api import (
    AgentRuntimeConfig,
    CanonicalExecutionState,
    ExecutionLineage,
    TaskDefinition,
    WorkflowDefinition,
    create_runtime,
    execution_state,
    recover_runtime,
    register_provider,
)
from ugence_agent_runtime.governance.interfaces import (
    GovernanceDisposition,
    GovernanceEvaluation,
    GovernanceHook,
)
from ugence_agent_runtime.models.execution_state import STATE_VERSION
from ugence_agent_runtime.models.proposal import TransitionProposal
from ugence_agent_runtime.models.task import TaskStatus
from ugence_agent_runtime.models.workflow import WorkflowStatus
from ugence_agent_runtime.persistence.checkpoints import Checkpoint
from ugence_agent_runtime.persistence.in_memory import InMemoryRuntimeStateStore
from ugence_agent_runtime.persistence.recovery import recover_instance
from ugence_agent_runtime.runtime.errors import ExecutionStateError, RecoveryError

from art_fakes import DispositionHook, RecordingProvider


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _clear_hook():
    class Hook(GovernanceHook):
        def __init__(self):
            self.last = None

        def evaluate(self, proposal, evaluation_time):
            self.last = proposal
            return GovernanceEvaluation(
                disposition=GovernanceDisposition.CLEAR,
                proposal_fingerprint=proposal.fingerprint,
                evaluation_reference="ref-1",
                correlation_reference=proposal.correlation_id,
            )

    return Hook()


def _run_clear(*, lineage=None, provider=None):
    hook = _clear_hook()
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    provider = provider or RecordingProvider("p")
    register_provider(rt, provider)
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p", arguments={"a": 1}),),
    )
    inst = rt.start_workflow(wf, lineage=lineage)
    return rt, inst, hook, provider


def _sample_state(**over):
    base = dict(
        runtime_id="agent-runtime",
        runtime_version="0.1.2",
        workflow_id="wf",
        instance_id="inst-1",
        task_id="t",
        correlation_id="corr-1",
        causation_id="cause-1",
        parent_workflow_ref="pw",
        parent_task_ref="pt",
        assigned_agent_ref="agent-x",
        agent_team_plan_ref="plan-x",
        assignment_digest="adig",
        authority_scope_ref="scope-x",
        workflow_status="RUNNING",
        task_status="RUNNING",
        attempt=1,
        provider_id="p",
        operation="op",
        idempotency_key="inst-1:t",
        proposal_version="1",
        proposal_fingerprint="fp-abc",
        governance_disposition="CLEAR",
        evaluation_reference="ev-1",
        authorization_reference="auth-1",
        clearance_reference="clr-1",
        valid_until=123.0,
        input_artifact_refs=("in-1",),
        output_artifact_refs=("out-1",),
        evidence_refs=("ev-a",),
        execution_reference="exec-1",
        result_digest="res-1",
    )
    base.update(over)
    return CanonicalExecutionState(**base).sealed()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_determinism_same_semantic_state_same_digest():
    a = _sample_state()
    b = _sample_state()
    assert a.state_digest == b.state_digest
    assert a.compute_digest() == b.compute_digest()
    assert a.is_intact() and b.is_intact()


def test_determinism_independent_of_ref_sequence_type():
    # Supplying artifact refs as a list vs a tuple yields the same canonical identity.
    a = _sample_state(input_artifact_refs=["in-1", "in-2"])
    b = _sample_state(input_artifact_refs=("in-1", "in-2"))
    assert a.state_digest == b.state_digest


def test_digest_excludes_state_digest_field():
    s = _sample_state()
    # Recomputing over the payload (which omits state_digest) reproduces the digest.
    assert s.state_digest == s.compute_digest()
    assert "state_digest" not in s.canonical_payload()


# ---------------------------------------------------------------------------
# Sensitivity — every identity-bearing field changes the digest
# ---------------------------------------------------------------------------
def test_sensitivity_every_identity_field_changes_digest():
    base = _sample_state()
    changes = {
        "runtime_id": "other",
        "runtime_version": "9.9.9",
        "workflow_id": "wf2",
        "instance_id": "inst-2",
        "task_id": "t2",
        "state_version": "2",
        "correlation_id": "corr-2",
        "causation_id": "cause-2",
        "parent_workflow_ref": "pw2",
        "parent_task_ref": "pt2",
        "assigned_agent_ref": "agent-y",
        "agent_team_plan_ref": "plan-y",
        "assignment_digest": "adig2",
        "authority_scope_ref": "scope-y",
        "workflow_status": "COMPLETED",
        "task_status": "COMPLETED",
        "attempt": 2,
        "provider_id": "p2",
        "operation": "op2",
        "idempotency_key": "k2",
        "proposal_version": "2",
        "proposal_fingerprint": "fp-xyz",
        "governance_disposition": "HOLD",
        "evaluation_reference": "ev-2",
        "authorization_reference": "auth-2",
        "clearance_reference": "clr-2",
        "valid_until": 999.0,
        "input_artifact_refs": ("in-9",),
        "output_artifact_refs": ("out-9",),
        "evidence_refs": ("ev-z",),
        "execution_reference": "exec-2",
        "result_digest": "res-2",
    }
    for field, value in changes.items():
        mutated = dataclasses.replace(base, **{field: value}).sealed()
        assert mutated.state_digest != base.state_digest, field


# ---------------------------------------------------------------------------
# Proposal linkage / no duplicated action identity
# ---------------------------------------------------------------------------
def test_state_references_active_proposal_fingerprint():
    rt, inst, hook, _ = _run_clear()
    assert inst.status is WorkflowStatus.COMPLETED
    state = execution_state(rt, inst.instance_id, "t")
    assert state is not None
    assert state.proposal_fingerprint == hook.last.fingerprint


def test_no_independent_action_payload():
    # Canonical state carries a *reference* (fingerprint), never a second copy of the
    # proposal arguments — there is no `arguments` field to canonicalize independently.
    s = _sample_state()
    keys = set(s.to_dict())
    assert "arguments" not in keys
    field_names = {f.name for f in dataclasses.fields(CanonicalExecutionState)}
    assert "arguments" not in field_names
    # The only action identity present is the proposal fingerprint reference.
    assert s.proposal_fingerprint == "fp-abc"


# ---------------------------------------------------------------------------
# Governance lineage fidelity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "disposition,final_status",
    [
        (GovernanceDisposition.CLEAR, WorkflowStatus.COMPLETED),
        (GovernanceDisposition.HOLD, WorkflowStatus.WAITING),
        (GovernanceDisposition.BLOCK, WorkflowStatus.FAILED),
        (GovernanceDisposition.ESCALATE, WorkflowStatus.PAUSED),
    ],
)
def test_governance_disposition_recorded_accurately(disposition, final_status):
    hook = DispositionHook(disposition)
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    assert inst.status is final_status
    state = execution_state(rt, inst.instance_id, "t")
    assert state.governance_disposition == disposition.value


def test_missing_governance_references_are_not_fabricated():
    # A HOLD with no references must leave the reference fields None (never invented).
    class Hook(GovernanceHook):
        def evaluate(self, proposal, evaluation_time):
            return GovernanceEvaluation(disposition=GovernanceDisposition.HOLD)

    rt = create_runtime(AgentRuntimeConfig(governance_hook=Hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    state = execution_state(rt, inst.instance_id, "t")
    assert state.governance_disposition == "HOLD"
    assert state.evaluation_reference is None
    assert state.authorization_reference is None
    assert state.clearance_reference is None


def test_non_consequential_task_has_no_governance_disposition():
    rt = create_runtime(AgentRuntimeConfig())
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p", consequential=False),),
    )
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.COMPLETED
    state = execution_state(rt, inst.instance_id, "t")
    assert state.governance_disposition is None
    assert state.proposal_fingerprint is not None  # proposal still constructed


# ---------------------------------------------------------------------------
# Checkpoint round trip / legacy compatibility / tampering
# ---------------------------------------------------------------------------
def test_checkpoint_round_trip_preserves_execution_state():
    ss = InMemoryRuntimeStateStore()
    hook = _clear_hook()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hook))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p", arguments={"a": 1}),),
    )
    inst = rt.start_workflow(wf)
    original = execution_state(rt, inst.instance_id, "t")

    rt2 = create_runtime(AgentRuntimeConfig(state_store=ss))
    result = recover_runtime(rt2, inst.instance_id, wf)
    restored = result.execution_states["t"]
    assert restored.is_intact()
    assert restored.state_digest == original.state_digest
    # And it is reachable through the read-only accessor on the recovered runtime.
    assert execution_state(rt2, inst.instance_id, "t").state_digest == original.state_digest


def test_legacy_checkpoint_without_lineage_recovers_unavailable():
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    from ugence_agent_runtime.models.workflow import WorkflowInstance

    inst = WorkflowInstance.create("inst-legacy", wf, correlation_id="corr")
    inst.tasks["t"].status = TaskStatus.COMPLETED
    inst.status = WorkflowStatus.COMPLETED
    cp = Checkpoint.of(inst, "agent-runtime", "0.1.2")  # no execution_states supplied

    # Simulate a pre-canonical-state serialized checkpoint: drop the new keys entirely.
    d = cp.to_dict()
    d.pop("checkpoint_version", None)
    d.pop("execution_states", None)
    legacy = Checkpoint.from_dict(d)
    assert legacy.checkpoint_version == "0"
    assert legacy.verify()  # base digest semantics unchanged
    assert legacy.verify_execution_states()  # vacuously intact

    result = recover_instance(legacy, wf, "agent-runtime", "0.1.2")
    assert result.execution_states == {}  # unavailable, not fabricated
    assert result.instance.status is WorkflowStatus.COMPLETED


def test_tampered_execution_state_fails_closed_on_recovery():
    ss = InMemoryRuntimeStateStore()
    hook = _clear_hook()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hook))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)

    # Tamper a persisted execution-state field without recomputing its state_digest.
    tampered_states = dict(cp.execution_states)
    snap = dict(tampered_states["t"])
    snap["governance_disposition"] = "BLOCK"  # claim a different disposition
    tampered_states["t"] = snap
    tampered = dataclasses.replace(cp, execution_states=tampered_states)

    assert tampered.verify()  # base coordination digest still matches
    assert not tampered.verify_execution_states()  # but lineage integrity fails
    with pytest.raises(RecoveryError):
        recover_instance(tampered, wf, "agent-runtime", "0.1.2")


def test_base_checkpoint_digest_unchanged_by_lineage_addition():
    # The base digest must be identical whether or not execution-state lineage is
    # attached — proving digest semantics of existing checkpoints did not change.
    from ugence_agent_runtime.models.workflow import WorkflowInstance

    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = WorkflowInstance.create("inst-z", wf, correlation_id="corr")
    inst.tasks["t"].status = TaskStatus.COMPLETED
    inst.status = WorkflowStatus.COMPLETED
    without = Checkpoint.of(inst, "agent-runtime", "0.1.2")
    with_lineage = Checkpoint.of(
        inst, "agent-runtime", "0.1.2",
        execution_states={"t": _sample_state(task_id="t")},
    )
    assert without.digest == with_lineage.digest


# ---------------------------------------------------------------------------
# Recovery safety
# ---------------------------------------------------------------------------
def test_recovery_restores_state_without_side_effects():
    ss = InMemoryRuntimeStateStore()

    class ExplodingProvider(RecordingProvider):
        def execute(self, invocation):
            raise AssertionError("recovery must not call a provider")

    class ExplodingHook(GovernanceHook):
        def evaluate(self, *a, **k):
            raise AssertionError("recovery must not call governance")

    hook = DispositionHook(GovernanceDisposition.HOLD)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hook))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    assert inst.status is WorkflowStatus.WAITING

    rt2 = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=ExplodingHook()))
    register_provider(rt2, ExplodingProvider("p"))
    result = recover_runtime(rt2, inst.instance_id, wf)  # must not raise
    assert result.execution_states["t"].is_intact()
    assert result.execution_states["t"].governance_disposition == "HOLD"


# ---------------------------------------------------------------------------
# Event anchoring
# ---------------------------------------------------------------------------
def test_event_digests_correspond_to_snapshots():
    rt, inst, _, _ = _run_clear()
    final = execution_state(rt, inst.instance_id, "t")
    events = rt.events(inst.instance_id)
    completed = [e for e in events if e.type == "TASK_COMPLETED"]
    assert completed
    assert completed[0].detail["execution_state_digest"] == final.state_digest
    # Every anchored digest is a real 64-char sha256 hex digest.
    for e in events:
        dig = e.detail.get("execution_state_digest")
        if dig is not None:
            assert len(dig) == 64 and int(dig, 16) >= 0


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------
def test_external_mutation_cannot_alter_identity():
    refs = ["in-1", "in-2"]
    lineage = ExecutionLineage(input_artifact_refs=refs)
    state = _sample_state(input_artifact_refs=lineage.input_artifact_refs)
    digest_before = state.state_digest
    refs.append("in-3")  # mutate the caller's original list
    assert state.state_digest == digest_before
    assert state.input_artifact_refs == ("in-1", "in-2")


def test_lineage_supplied_to_workflow_is_snapshot_immune_to_mutation():
    refs = ["doc-1"]
    lineage = ExecutionLineage(input_artifact_refs=refs, assigned_agent_ref="agent-x")
    rt, inst, _, _ = _run_clear(lineage=lineage)
    refs.append("doc-2")
    state = execution_state(rt, inst.instance_id, "t")
    assert state.input_artifact_refs == ("doc-1",)


# ---------------------------------------------------------------------------
# Agent / AWC lineage neutrality
# ---------------------------------------------------------------------------
def test_agent_lineage_carried_but_not_used_for_selection():
    lineage = ExecutionLineage(
        assigned_agent_ref="agent-x",
        agent_team_plan_ref="plan-1",
        authority_scope_ref="scope-1",
    )
    provider = RecordingProvider("p")
    rt, inst, _, _ = _run_clear(lineage=lineage, provider=provider)
    state = execution_state(rt, inst.instance_id, "t")
    # The references are carried verbatim...
    assert state.assigned_agent_ref == "agent-x"
    assert state.agent_team_plan_ref == "plan-1"
    assert state.authority_scope_ref == "scope-1"
    # ...but the runtime still invoked exactly the provider named on the task definition;
    # it did not select, re-rank, or invent an agent from the lineage reference.
    assert len(provider.calls) == 1
    assert provider.calls[0].provider_id == "p"


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------
def test_constructing_state_creates_no_authority():
    # A hand-authored "CLEAR" state with fabricated references is inert: it is not a
    # path to authorize anything. The workflow's disposition still comes from the hook.
    forged = CanonicalExecutionState(
        governance_disposition="CLEAR",
        authorization_reference="forged-auth",
        clearance_reference="forged-clearance",
    ).sealed()
    assert forged.governance_disposition == "CLEAR"  # just a string; inert

    hook = DispositionHook(GovernanceDisposition.HOLD)
    rt = create_runtime(AgentRuntimeConfig(governance_hook=hook))
    provider = RecordingProvider("p")
    register_provider(rt, provider)
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf, lineage=None)
    # HOLD is not converted to CLEAR by any canonical-state construction.
    assert inst.status is WorkflowStatus.WAITING
    assert provider.calls == []
    runtime_state = execution_state(rt, inst.instance_id, "t")
    assert runtime_state.governance_disposition == "HOLD"


def test_no_public_mutation_api_for_execution_state():
    rt, inst, _, _ = _run_clear()
    assert not hasattr(rt, "set_execution_state")
    # The frozen dataclass rejects attribute mutation.
    state = execution_state(rt, inst.instance_id, "t")
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.governance_disposition = "BLOCK"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fail-closed typing
# ---------------------------------------------------------------------------
def test_unsupported_identity_types_fail_closed():
    with pytest.raises(ExecutionStateError):
        CanonicalExecutionState(runtime_id=object())  # type: ignore[arg-type]
    with pytest.raises(ExecutionStateError):
        CanonicalExecutionState(input_artifact_refs=[object()])  # type: ignore[list-item]
    with pytest.raises(ExecutionStateError):
        ExecutionLineage(assigned_agent_ref=123)  # type: ignore[arg-type]


def test_state_version_default():
    assert CanonicalExecutionState().state_version == STATE_VERSION
