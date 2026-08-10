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
    execution_state_by_digest,
    recover_runtime,
    register_provider,
    resume_workflow,
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

    # A genuine v1 checkpoint carries a valid extension digest.
    saved = ss.load(inst.instance_id)
    assert saved.checkpoint_version == "1"
    assert saved.verify() and saved.verify_extension()

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

    # Simulate a pre-canonical-state serialized checkpoint: drop all the new keys entirely.
    d = cp.to_dict()
    for k in (
        "checkpoint_version", "execution_states", "execution_state_journal",
        "workflow_lineage", "task_lineage", "extension_digest",
    ):
        d.pop(k, None)
    legacy = Checkpoint.from_dict(d)
    assert legacy.checkpoint_version == "0"
    assert not legacy.has_extension_data()
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


def test_lineage_source_tampering_fails_recovery():
    # The reviewer's scenario: tamper ONLY the persisted lineage source. The base digest
    # excludes it and the snapshots/journal are untouched — so both older checks pass — but
    # the extension digest must catch it, or a resumed run would attribute a forged agent.
    ss = InMemoryRuntimeStateStore()
    hold = DispositionHook(GovernanceDisposition.HOLD)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hold))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(
        wf, task_lineage={"t": ExecutionLineage(assigned_agent_ref="risk-agent-7",
                                                evidence_refs=["EV-44"])}
    )
    cp = ss.load(inst.instance_id)
    assert cp.verify() and cp.verify_extension()

    tl = dict(cp.task_lineage)
    tl["t"] = {**tl["t"], "assigned_agent_ref": "execution-agent-9", "evidence_refs": ["EV-99"]}
    tampered = dataclasses.replace(cp, task_lineage=tl)
    assert tampered.verify()                       # base digest unaffected (the old gap)
    assert tampered.validate_execution_states()[0]  # snapshots/journal untouched (the old gap)
    assert not tampered.verify_extension()          # NEW: extension digest catches it
    with pytest.raises(RecoveryError):
        recover_instance(tampered, wf, cp.runtime_id, cp.runtime_version)


def test_journal_omission_caught_even_when_extension_resealed():
    # An adversary who can recompute the extension digest still cannot omit a journal entry
    # that a latest snapshot points to — the latest<->journal consistency check catches it.
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)

    latest_digest = cp.execution_states["t"]["state_digest"]
    journal = {k: v for k, v in cp.execution_state_journal.items() if k != latest_digest}
    stripped = dataclasses.replace(cp, execution_state_journal=journal)
    resealed = dataclasses.replace(stripped, extension_digest=stripped.compute_extension_digest())
    assert resealed.verify_extension()  # digest re-sealed, so it passes
    ok, reason = resealed.validate_execution_states()
    assert not ok and "journal" in reason.lower()
    with pytest.raises(RecoveryError):
        recover_instance(resealed, wf, cp.runtime_id, cp.runtime_version)


def test_runtime_upgrade_mixed_version_journal_recovers():
    # Origin provenance across an upgrade must not make a checkpoint unrecoverable:
    #   vA writes states → recover under vB (config_mismatch) → resume under vB → the new
    #   checkpoint carries a mixed-version journal (vA + vB) → it must still recover under vB.
    ss = InMemoryRuntimeStateStore()
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(
            TaskDefinition(task_id="a", operation="op", provider_id="p"),
            TaskDefinition(task_id="b", operation="op", provider_id="p", depends_on=("a",)),
        ),
    )
    # vA: task 'a' clears and completes; task 'b' is HOLD, so the workflow is WAITING.
    class Gate(GovernanceHook):
        def __init__(self):
            self.hold = {"b"}
        def evaluate(self, proposal, evaluation_time):
            if proposal.task_id in self.hold:
                return GovernanceEvaluation(disposition=GovernanceDisposition.HOLD)
            return GovernanceEvaluation(
                disposition=GovernanceDisposition.CLEAR,
                proposal_fingerprint=proposal.fingerprint,
                evaluation_reference="ref",
                correlation_reference=proposal.correlation_id,
            )

    gate_a = Gate()
    rt_a = create_runtime(AgentRuntimeConfig(state_store=ss, runtime_version="0.2.0", governance_hook=gate_a))
    register_provider(rt_a, RecordingProvider("p"))
    inst = rt_a.start_workflow(wf)
    assert inst.status is WorkflowStatus.WAITING
    state_a = execution_state(rt_a, inst.instance_id, "a")
    assert state_a.runtime_version == "0.2.0"

    # vB: recover (runtime version differs -> config_mismatch), release the HOLD, resume.
    gate_b = Gate()
    gate_b.hold = set()
    rt_b = create_runtime(AgentRuntimeConfig(state_store=ss, runtime_version="0.2.1", governance_hook=gate_b))
    register_provider(rt_b, RecordingProvider("p"))
    result = recover_runtime(rt_b, inst.instance_id, wf)
    assert result.config_mismatch is True
    resume_workflow(rt_b, inst.instance_id)
    assert rt_b.instance(inst.instance_id).status is WorkflowStatus.COMPLETED

    # The freshly written checkpoint carries a mixed-version journal.
    cp = ss.load(inst.instance_id)
    assert cp.runtime_version == "0.2.1"
    journal_versions = {
        CanonicalExecutionState.from_dict(s).runtime_version
        for s in cp.execution_state_journal.values()
    }
    assert journal_versions == {"0.2.0", "0.2.1"}, journal_versions
    # It must validate and recover cleanly under vB despite the older-origin states.
    assert cp.verify() and cp.verify_extension()
    assert cp.validate_execution_states()[0]
    rt_c = create_runtime(AgentRuntimeConfig(state_store=ss, runtime_version="0.2.1"))
    result2 = recover_runtime(rt_c, inst.instance_id, wf)
    assert result2.instance.status is WorkflowStatus.COMPLETED


def test_every_emitted_checkpoint_is_self_recoverable():
    # Every checkpoint the runtime writes must pass its own recovery validator.
    saved = []

    class CapturingStore(InMemoryRuntimeStateStore):
        def save(self, checkpoint):
            saved.append(checkpoint)
            super().save(checkpoint)

    ss = CapturingStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(
            TaskDefinition(task_id="a", operation="op", provider_id="p"),
            TaskDefinition(task_id="b", operation="op", provider_id="p", depends_on=("a",)),
        ),
    )
    rt.start_workflow(wf)
    assert saved  # several checkpoints were written across the run
    for cp in saved:
        assert cp.verify() and cp.verify_extension()
        assert cp.validate_execution_states()[0]


def test_unknown_checkpoint_version_fails_recovery():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)
    bumped = dataclasses.replace(cp, checkpoint_version="2")
    with pytest.raises(RecoveryError):
        recover_instance(bumped, wf, cp.runtime_id, cp.runtime_version)


def test_malformed_task_lineage_key_fails_closed():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(
        wf, task_lineage={"t": ExecutionLineage(assigned_agent_ref="a")}
    )
    cp = ss.load(inst.instance_id)
    # A persisted lineage entry for a task the workflow does not contain must fail closed,
    # not be silently ignored.
    tl = dict(cp.task_lineage)
    tl["ghost"] = {"assigned_agent_ref": "x"}
    stripped = dataclasses.replace(cp, task_lineage=tl)
    resealed = dataclasses.replace(stripped, extension_digest=stripped.compute_extension_digest())
    ok, reason = resealed.validate_execution_states()
    assert not ok and "ghost" in reason


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


def test_unsupported_state_version_fails_closed():
    with pytest.raises(ExecutionStateError):
        CanonicalExecutionState(state_version="2")


def test_non_finite_valid_until_fails_closed():
    with pytest.raises(ExecutionStateError):
        CanonicalExecutionState(valid_until=float("nan"))
    with pytest.raises(ExecutionStateError):
        CanonicalExecutionState(valid_until=float("inf"))


# ---------------------------------------------------------------------------
# Task-specific lineage (multi-agent) — correction 1
# ---------------------------------------------------------------------------
def test_task_specific_lineage_overrides_workflow_common():
    rt = create_runtime(AgentRuntimeConfig(governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(
            TaskDefinition(task_id="t1", operation="op", provider_id="p"),
            TaskDefinition(task_id="t2", operation="op", provider_id="p"),
        ),
    )
    wf_lineage = ExecutionLineage(agent_team_plan_ref="PLAN-1", parent_workflow_ref="root")
    task_lineage = {
        "t1": ExecutionLineage(assigned_agent_ref="research", input_artifact_refs=["doc-r"]),
        "t2": ExecutionLineage(assigned_agent_ref="risk", input_artifact_refs=["doc-k"]),
    }
    inst = rt.start_workflow(wf, lineage=wf_lineage, task_lineage=task_lineage)
    assert inst.status is WorkflowStatus.COMPLETED
    s1 = execution_state(rt, inst.instance_id, "t1")
    s2 = execution_state(rt, inst.instance_id, "t2")
    # Task-specific fields are attributed per task — not smeared across siblings.
    assert s1.assigned_agent_ref == "research"
    assert s2.assigned_agent_ref == "risk"
    assert s1.input_artifact_refs == ("doc-r",)
    assert s2.input_artifact_refs == ("doc-k",)
    # Workflow-common fields are inherited by both.
    assert s1.agent_team_plan_ref == s2.agent_team_plan_ref == "PLAN-1"
    assert s1.parent_workflow_ref == s2.parent_workflow_ref == "root"
    assert s1.state_digest != s2.state_digest


def test_unknown_task_lineage_key_rejected():
    rt = create_runtime(AgentRuntimeConfig(governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    with pytest.raises(ValueError):
        rt.start_workflow(wf, task_lineage={"nope": ExecutionLineage(assigned_agent_ref="x")})


# ---------------------------------------------------------------------------
# Lineage continuity across recovery — correction 2
# ---------------------------------------------------------------------------
def test_recovery_preserves_lineage_for_future_snapshots():
    ss = InMemoryRuntimeStateStore()
    hold = DispositionHook(GovernanceDisposition.HOLD)
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=hold))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    task_lineage = {
        "t": ExecutionLineage(
            assigned_agent_ref="risk-agent-7",
            agent_team_plan_ref="PLAN-88",
            evidence_refs=["EV-44"],
        )
    }
    inst = rt.start_workflow(wf, task_lineage=task_lineage)
    assert inst.status is WorkflowStatus.WAITING
    before = execution_state(rt, inst.instance_id, "t")
    assert before.assigned_agent_ref == "risk-agent-7"

    # Recover in a fresh runtime, then resume with CLEAR. The NEW snapshot built after
    # recovery must keep the same lineage refs — continuity is not lost across the crash.
    clear = DispositionHook(GovernanceDisposition.CLEAR)
    rt2 = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=clear))
    register_provider(rt2, RecordingProvider("p"))
    result = recover_runtime(rt2, inst.instance_id, wf)
    assert result.requires_continuation
    resume_workflow(rt2, inst.instance_id)
    after = execution_state(rt2, inst.instance_id, "t")
    assert after.task_status == "COMPLETED"
    assert after.assigned_agent_ref == "risk-agent-7"
    assert after.agent_team_plan_ref == "PLAN-88"
    assert after.evidence_refs == ("EV-44",)


# ---------------------------------------------------------------------------
# Checkpoint <-> execution-state cross-binding — correction 3
# ---------------------------------------------------------------------------
def test_cross_binding_rejects_relabelled_state():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)

    # The state's own digest is intact, but it is filed under the wrong task key.
    states = dict(cp.execution_states)
    states["WRONG"] = states.pop("t")
    tampered = dataclasses.replace(cp, execution_states=states)
    ok, reason = tampered.validate_execution_states()
    assert not ok and reason is not None
    with pytest.raises(RecoveryError):
        recover_instance(tampered, wf, cp.runtime_id, cp.runtime_version)


def test_cross_binding_rejects_foreign_instance_state():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)

    # A snapshot whose OWN digest is valid but which belongs to a different instance must
    # be rejected — something digest-only verification would miss.
    foreign = _sample_state(
        instance_id="OTHER-INSTANCE", task_id="t", workflow_id="wf",
        runtime_id=cp.runtime_id, runtime_version=cp.runtime_version,
        correlation_id=cp.correlation_id,
    )
    assert foreign.is_intact()  # internally consistent
    tampered = dataclasses.replace(cp, execution_states={"t": foreign.to_dict()})
    ok, _ = tampered.validate_execution_states()
    assert not ok


def test_cross_binding_rejects_unsupported_version_with_precise_reason():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    cp = ss.load(inst.instance_id)
    snap = dict(cp.execution_states["t"])
    snap["state_version"] = "99"
    tampered = dataclasses.replace(cp, execution_states={"t": snap})
    ok, reason = tampered.validate_execution_states()
    assert not ok
    assert "state_version" in reason


# ---------------------------------------------------------------------------
# Historical state digests resolvable — correction 4
# ---------------------------------------------------------------------------
def test_historical_state_digests_resolvable():
    rt, inst, _, _ = _run_clear()
    events = rt.events(inst.instance_id)
    anchored = [
        e.detail["execution_state_digest"]
        for e in events
        if e.detail.get("execution_state_digest") is not None
    ]
    assert len(set(anchored)) >= 3  # several distinct trajectory points, not just the last
    for dig in anchored:
        s = execution_state_by_digest(rt, inst.instance_id, dig)
        assert s is not None and s.state_digest == dig
    # The latest-only accessor still returns just the final snapshot.
    assert execution_state(rt, inst.instance_id, "t").state_digest == anchored[-1]


def test_journal_restored_after_recovery():
    ss = InMemoryRuntimeStateStore()
    rt = create_runtime(AgentRuntimeConfig(state_store=ss, governance_hook=_clear_hook()))
    register_provider(rt, RecordingProvider("p"))
    wf = WorkflowDefinition(
        workflow_id="wf",
        tasks=(TaskDefinition(task_id="t", operation="op", provider_id="p"),),
    )
    inst = rt.start_workflow(wf)
    anchored = [
        e.detail["execution_state_digest"]
        for e in rt.events(inst.instance_id)
        if e.detail.get("execution_state_digest") is not None
    ]
    rt2 = create_runtime(AgentRuntimeConfig(state_store=ss))
    recover_runtime(rt2, inst.instance_id, wf)
    for dig in set(anchored):
        assert execution_state_by_digest(rt2, inst.instance_id, dig) is not None
