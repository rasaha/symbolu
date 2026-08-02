"""The Agent Runtime engine — deterministic coordination of a single workflow.

The engine drives a workflow's tasks in deterministic dependency order. For each
consequential task it consults the neutral governance boundary BEFORE any provider
is invoked, and it obeys the returned disposition without ever broadening it:

    CLEAR    -> run the provider (retry/timeout apply)
    HOLD     -> task WAITING, workflow WAITING (no provider call, no authority)
    BLOCK    -> task FAILED, workflow FAILED (no provider call)
    ESCALATE -> task WAITING, workflow PAUSED (no provider call)

The engine COORDINATES. Governance DECIDES permission. Providers EXECUTE. Recovery
reconstructs state without any external call. Nothing here creates authority,
authors policy, or mints execution clearance.
"""
from __future__ import annotations

from typing import Dict, Optional

from ..config import AgentRuntimeConfig
from ..governance.decisions import RuntimeDirective, directive_for, validate_clearance
from ..governance.interfaces import GovernanceEvaluation
from ..models import events as ev
from ..models.proposal import TransitionProposal, compute_fingerprint
from ..models.results import FailureCategory, RuntimeFailure, RuntimeResult
from ..models.task import TaskInstance, TaskStatus
from ..models.transitions import check_task_transition, check_workflow_transition
from ..models.workflow import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from ..observability.tracing import RunTrace
from ..persistence.checkpoints import Checkpoint
from ..persistence.recovery import RuntimeRecoveryResult, recover_instance
from ..providers.interfaces import ToolInvocation
from .cancellation import CancellationToken
from .errors import AgentRuntimeError
from .execution import execute_with_policy


class AgentRuntime:
    """Coordinates workflow execution against injected providers and governance.

    A single ``AgentRuntime`` may drive several workflow instances. Each instance has
    its own trace, cancellation token, and (optional) persisted checkpoints. The
    engine executes tasks sequentially and deterministically; ``max_concurrent_tasks``
    bounds concurrency (the reference engine never exceeds one in-flight task).
    """

    def __init__(self, config: Optional[AgentRuntimeConfig] = None) -> None:
        self._config = config or AgentRuntimeConfig()
        self._instances: Dict[str, WorkflowInstance] = {}
        self._traces: Dict[str, RunTrace] = {}
        self._tokens: Dict[str, CancellationToken] = {}
        self._failures: Dict[str, list] = {}
        # Runtime-level trace (records RUNTIME_CREATED); no I/O performed here.
        self._runtime_trace = RunTrace(
            instance_id=self._config.runtime_id,
            sink=self._make_sink(self._config.runtime_id),
        )
        self._runtime_trace.emit(ev.RUNTIME_CREATED, runtime_id=self._config.runtime_id)

    def _make_sink(self, instance_id: str):
        """Compose the caller's event sink with the optional event store. Both are
        opt-in; when neither is configured the trace performs no I/O."""
        user_sink = self._config.event_sink
        store = self._config.event_store
        if user_sink is None and store is None:
            return None

        def _sink(event):
            if store is not None:
                store.append(instance_id, event)
            if user_sink is not None:
                user_sink(event)

        return _sink

    # -- accessors ----------------------------------------------------------
    @property
    def config(self) -> AgentRuntimeConfig:
        return self._config

    def instance(self, instance_id: str) -> WorkflowInstance:
        return self._instances[instance_id]

    def trace(self, instance_id: str) -> RunTrace:
        return self._traces[instance_id]

    def events(self, instance_id: str):
        return list(self._traces[instance_id].events)

    # -- public lifecycle ---------------------------------------------------
    def start_workflow(
        self,
        definition: WorkflowDefinition,
        correlation_id: Optional[str] = None,
    ) -> WorkflowInstance:
        instance_id = self._config.id_generator()
        correlation_id = correlation_id or instance_id
        instance = WorkflowInstance.create(instance_id, definition, correlation_id)
        trace = RunTrace(instance_id=instance_id, sink=self._make_sink(instance_id))
        self._instances[instance_id] = instance
        self._traces[instance_id] = trace
        self._tokens[instance_id] = CancellationToken()
        self._failures[instance_id] = []
        trace.emit(ev.WORKFLOW_CREATED, workflow_id=definition.workflow_id, instance_id=instance_id)

        self._set_wf(instance, WorkflowStatus.READY, trace, None)
        self._set_wf(instance, WorkflowStatus.RUNNING, trace, ev.WORKFLOW_STARTED)
        self._checkpoint(instance, trace)
        self._drive(instance, trace)
        return instance

    def resume_workflow(self, instance_id: str) -> WorkflowInstance:
        """Explicitly continue a workflow that is WAITING or PAUSED.

        This is the ONLY way HOLD/ESCALATE work proceeds — the runtime never
        self-resolves a restrictive governance disposition."""
        instance = self._instances[instance_id]
        trace = self._traces[instance_id]
        if instance.status not in (WorkflowStatus.WAITING, WorkflowStatus.PAUSED):
            raise AgentRuntimeError(
                f"workflow {instance_id} is {instance.status.value}; not resumable"
            )
        # Re-arm any WAITING tasks for another evaluation.
        for ti in instance.tasks.values():
            if ti.status is TaskStatus.WAITING:
                self._set_task(instance, ti, TaskStatus.READY, trace, None)
        self._set_wf(instance, WorkflowStatus.RUNNING, trace, ev.WORKFLOW_RESUMED)
        self._drive(instance, trace)
        return instance

    def pause_workflow(self, instance_id: str) -> WorkflowInstance:
        instance = self._instances[instance_id]
        trace = self._traces[instance_id]
        if instance.status is WorkflowStatus.RUNNING:
            self._set_wf(instance, WorkflowStatus.PAUSED, trace, ev.WORKFLOW_PAUSED,
                         reason="explicit_pause")
            self._checkpoint(instance, trace)
        return instance

    def cancel_workflow(self, instance_id: str) -> WorkflowInstance:
        instance = self._instances[instance_id]
        trace = self._traces[instance_id]
        self._tokens[instance_id].cancel()
        if instance.is_terminal:
            return instance
        for ti in instance.tasks.values():
            if not ti.is_terminal:
                self._set_task(instance, ti, TaskStatus.CANCELLED, trace, None)
        self._set_wf(instance, WorkflowStatus.CANCELLED, trace, ev.WORKFLOW_CANCELLED)
        self._checkpoint(instance, trace)
        return instance

    def recover_runtime(
        self,
        instance_id: str,
        definition: WorkflowDefinition,
    ) -> RuntimeRecoveryResult:
        """Reconstruct an instance from persisted state. No provider or governance
        call is made. The recovered instance requires explicit continuation."""
        store = self._config.state_store or self._config.checkpoint_store
        if store is None:
            raise AgentRuntimeError("no state_store/checkpoint_store configured for recovery")
        checkpoint = (
            store.load(instance_id)
            if hasattr(store, "load")
            else store.latest(instance_id)
        )
        result = recover_instance(
            checkpoint,
            definition,
            self._config.runtime_id,
            self._config.runtime_version,
        )
        instance = result.instance
        trace = RunTrace(instance_id=instance_id, sink=self._make_sink(instance_id))
        self._instances[instance_id] = instance
        self._traces[instance_id] = trace
        self._tokens[instance_id] = CancellationToken()
        self._failures[instance_id] = []
        trace.emit(
            ev.RECOVERY_PERFORMED,
            instance_id=instance_id,
            resumed_from_status=result.resumed_from_status,
            requires_continuation=result.requires_continuation,
            config_mismatch=result.config_mismatch,
        )
        return result

    def result(self, instance_id: str) -> RuntimeResult:
        instance = self._instances[instance_id]
        completed = tuple(
            tid for tid, ti in instance.tasks.items() if ti.status is TaskStatus.COMPLETED
        )
        return RuntimeResult(
            instance_id=instance_id,
            workflow_id=instance.workflow_id,
            status=instance.status.value,
            completed_tasks=completed,
            failures=tuple(self._failures.get(instance_id, ())),
        )

    # -- drive loop ---------------------------------------------------------
    def _drive(self, instance: WorkflowInstance, trace: RunTrace) -> None:
        token = self._tokens[instance.instance_id]
        while instance.status is WorkflowStatus.RUNNING:
            if token.cancelled:
                self.cancel_workflow(instance.instance_id)
                return
            task = instance.ready_task()
            if task is None:
                self._finalize(instance, trace)
                return
            self._run_task(instance, task, trace)

    def _finalize(self, instance: WorkflowInstance, trace: RunTrace) -> None:
        remaining = instance.remaining_tasks()
        if not remaining:
            self._set_wf(instance, WorkflowStatus.COMPLETED, trace, ev.WORKFLOW_COMPLETED)
            self._checkpoint(instance, trace)
            return
        # Non-terminal tasks remain but none is currently runnable (all WAITING).
        if all(ti.status is TaskStatus.WAITING for ti in remaining):
            self._set_wf(instance, WorkflowStatus.WAITING, trace, ev.WORKFLOW_WAITING)
            self._checkpoint(instance, trace)

    def _build_proposal(self, instance: WorkflowInstance, ti: TaskInstance) -> TransitionProposal:
        d = ti.definition
        return TransitionProposal.build(
            workflow_id=instance.workflow_id,
            instance_id=instance.instance_id,
            task_id=ti.task_id,
            provider_id=d.provider_id or d.operation,
            operation=d.operation,
            arguments=dict(d.arguments),
            idempotency_key=f"{instance.instance_id}:{ti.task_id}",
            correlation_id=instance.correlation_id or instance.instance_id,
        )

    def _run_task(self, instance: WorkflowInstance, ti: TaskInstance, trace: RunTrace) -> None:
        self._set_task(instance, ti, TaskStatus.READY, trace, ev.TASK_READY)
        proposal = self._build_proposal(instance, ti)

        if ti.definition.consequential:
            evaluation = self._evaluate(proposal, ti, trace)
            directive = directive_for(evaluation)
            ti.governance_reference = evaluation.binding_reference() if evaluation else None
        else:
            # Non-consequential task: no governance boundary is crossed.
            evaluation = None
            directive = RuntimeDirective.CONTINUE

        if directive is RuntimeDirective.WAIT:  # HOLD
            self._set_task(instance, ti, TaskStatus.WAITING, trace, ev.TASK_WAITING,
                           disposition="HOLD")
            self._set_wf(instance, WorkflowStatus.WAITING, trace, ev.WORKFLOW_WAITING,
                         reason="governance_hold")
            self._checkpoint(instance, trace)
            return

        if directive is RuntimeDirective.PAUSE:  # ESCALATE
            self._set_task(instance, ti, TaskStatus.WAITING, trace, ev.TASK_WAITING,
                           disposition="ESCALATE")
            self._set_wf(instance, WorkflowStatus.PAUSED, trace, ev.WORKFLOW_PAUSED,
                         reason="governance_escalate")
            self._checkpoint(instance, trace)
            return

        if directive is RuntimeDirective.STOP:  # BLOCK (or fail-closed unknown)
            reasons = evaluation.reason_codes if evaluation else ("GOVERNANCE_STOP",)
            self._fail_task_governance(instance, ti, trace, reasons,
                                       "governance blocked the transition", disposition="BLOCK")
            return

        # CONTINUE (CLEAR): for consequential tasks, the CLEAR must be bound to the
        # EXACT proposal before any provider is invoked. Fail closed otherwise.
        if ti.definition.consequential:
            permitted, reasons = validate_clearance(evaluation, proposal, self._config.clock())
            if not permitted:
                self._fail_task_governance(
                    instance, ti, trace, reasons,
                    "governance CLEAR not bound to the exact proposal (fail closed)",
                    disposition="CLEAR_REJECTED",
                )
                return

        self._set_task(instance, ti, TaskStatus.RUNNING, trace, ev.TASK_STARTED)
        self._execute(instance, ti, proposal, trace)

    def _fail_task_governance(self, instance, ti, trace, reason_codes, message, *, disposition):
        failure = RuntimeFailure(
            category=FailureCategory.GOVERNANCE_BLOCK,
            message=message,
            task_id=ti.task_id,
            reason_codes=tuple(reason_codes),
        )
        self._failures[instance.instance_id].append(failure)
        ti.failure = failure
        self._set_task(instance, ti, TaskStatus.FAILED, trace, ev.TASK_FAILED,
                       disposition=disposition, reason_codes=list(reason_codes))
        self._set_wf(instance, WorkflowStatus.FAILED, trace, ev.WORKFLOW_FAILED,
                     reason="governance_block")
        self._checkpoint(instance, trace)

    def _evaluate(
        self, proposal: TransitionProposal, ti: TaskInstance, trace: RunTrace
    ) -> GovernanceEvaluation:
        trace.emit(ev.GOVERNANCE_EVALUATION_REQUESTED, task_id=ti.task_id,
                   operation=proposal.operation, fingerprint=proposal.fingerprint[:12])
        evaluation = self._config.governance_hook.evaluate(proposal, self._config.clock())
        trace.emit(ev.GOVERNANCE_DISPOSITION_RECEIVED, task_id=ti.task_id,
                   disposition=evaluation.disposition.value,
                   reason_codes=list(evaluation.reason_codes),
                   fingerprint_bound=(evaluation.proposal_fingerprint == proposal.fingerprint))
        return evaluation

    def _execute(self, instance: WorkflowInstance, ti: TaskInstance,
                 proposal: TransitionProposal, trace: RunTrace) -> None:
        d = ti.definition
        # Re-materialize arguments as a FRESH mutable structure only now, after
        # clearance validation — the frozen proposal identity is never handed out.
        invocation = ToolInvocation(
            provider_id=proposal.provider_id,
            operation=proposal.operation,
            arguments=proposal.materialize_arguments(),
            correlation_id=proposal.correlation_id,
            idempotency_key=proposal.idempotency_key,
            timeout=d.timeout if d.timeout is not None else self._config.default_timeout,
        )
        # Exact-action re-check: the invocation must fingerprint-match the proposal
        # governance evaluated — across workflow/instance/task/provider/operation/
        # canonical arguments/idempotency key/correlation id/proposal version. Any
        # drift fails closed (integrity), never executes.
        inv_fp = compute_fingerprint(
            proposal.workflow_id, proposal.instance_id, proposal.task_id,
            invocation.provider_id, invocation.operation, invocation.arguments,
            invocation.idempotency_key, invocation.correlation_id, proposal.proposal_version,
        )
        if inv_fp != proposal.fingerprint:
            self._fail_task_governance(
                instance, ti, trace, ("PROPOSAL_INVOCATION_MISMATCH",),
                "provider invocation does not match the evaluated proposal (fail closed)",
                disposition="INTEGRITY",
            )
            return
        trace.emit(ev.PROVIDER_INVOKED, task_id=ti.task_id, provider_id=invocation.provider_id)
        outcome = execute_with_policy(
            self._config.provider_registry,
            invocation,
            self._config.retry_policy if d.max_attempts <= 1 else self._retry_for(d.max_attempts),
            self._config.clock,
            invocation.timeout,
            ti.task_id,
        )
        ti.attempts = outcome.attempts
        trace.emit(ev.PROVIDER_COMPLETED, task_id=ti.task_id, ok=outcome.ok,
                   attempts=outcome.attempts)

        if outcome.ok:
            ti.result = outcome.result.output if outcome.result else None
            self._set_task(instance, ti, TaskStatus.COMPLETED, trace, ev.TASK_COMPLETED)
            self._checkpoint(instance, trace)
            return

        failure = outcome.failure or RuntimeFailure(
            category=FailureCategory.PROVIDER_ERROR, message="provider failed",
            task_id=ti.task_id,
        )
        # A retriable provider error that exhausted more than one attempt is
        # reclassified as RETRY_EXHAUSTED for a precise, stable taxonomy.
        if failure.category is FailureCategory.PROVIDER_ERROR and outcome.attempts > 1:
            failure = RuntimeFailure(
                category=FailureCategory.RETRY_EXHAUSTED,
                message=failure.message,
                task_id=ti.task_id,
                detail=failure.detail,
            )
        ti.failure = failure
        self._failures[instance.instance_id].append(failure)
        self._set_task(instance, ti, TaskStatus.FAILED, trace, ev.TASK_FAILED,
                       category=failure.category.value)
        self._set_wf(instance, WorkflowStatus.FAILED, trace, ev.WORKFLOW_FAILED,
                     reason=failure.category.value)
        self._checkpoint(instance, trace)

    def _retry_for(self, max_attempts: int):
        from .retry import RetryPolicy
        return RetryPolicy(max_attempts=max_attempts)

    # -- state transition helpers ------------------------------------------
    def _set_task(self, instance, ti, new_status, trace, event_type, **detail):
        check_task_transition(ti.status, new_status)
        ti.status = new_status
        if event_type is not None:
            trace.emit(event_type, task_id=ti.task_id, status=new_status.value, **detail)

    def _set_wf(self, instance, new_status, trace, event_type, reason="", **detail):
        check_workflow_transition(instance.status, new_status)
        instance.status = new_status
        if event_type is not None:
            trace.emit(event_type, instance_id=instance.instance_id,
                       status=new_status.value, reason=reason, **detail)

    def _checkpoint(self, instance: WorkflowInstance, trace: RunTrace) -> None:
        checkpoint = Checkpoint.of(
            instance, self._config.runtime_id, self._config.runtime_version
        )
        if self._config.checkpoint_store is not None:
            self._config.checkpoint_store.put(checkpoint)
        if self._config.state_store is not None:
            self._config.state_store.save(checkpoint)
        trace.emit(ev.CHECKPOINT_COMMITTED, instance_id=instance.instance_id,
                   status=instance.status.value, digest=checkpoint.digest[:12])
