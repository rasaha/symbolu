"""Runtime derivation of canonical execution state.

This module is the *only* sanctioned author of :class:`CanonicalExecutionState`
snapshots inside the runtime. It derives a sealed, digest-bearing snapshot from the
runtime's own authoritative objects — configuration, the workflow instance, the task
instance, the immutable transition proposal, and (when available) the governance
evaluation — plus the neutral, typed lineage seam carried on the instance.

Deriving from runtime-owned inputs (rather than accepting arbitrary caller values)
keeps execution truth runtime-owned: a caller cannot claim an authorization, a
clearance, or an execution history by constructing a state — the authority-lineage
fields are copied *verbatim* from what the governance boundary returned, and are None
whenever governance produced nothing. Nothing here decides permission, selects an
agent, or broadens a disposition.
"""
from __future__ import annotations

from typing import Optional

from ..config import AgentRuntimeConfig
from ..governance.interfaces import GovernanceEvaluation
from ..models.execution_state import CanonicalExecutionState, ExecutionLineage
from ..models.proposal import TransitionProposal
from ..models.task import TaskInstance
from ..models.workflow import WorkflowInstance


def build_execution_state(
    config: AgentRuntimeConfig,
    instance: WorkflowInstance,
    task: Optional[TaskInstance] = None,
    proposal: Optional[TransitionProposal] = None,
    evaluation: Optional[GovernanceEvaluation] = None,
) -> CanonicalExecutionState:
    """Derive a sealed :class:`CanonicalExecutionState` for the current trajectory point.

    ``proposal`` supplies the *reference* to action identity (its fingerprint), never a
    re-canonicalized copy of the arguments. ``evaluation`` supplies authority-lineage
    references exactly as governance produced them; when it is ``None`` those references
    remain unavailable and are never fabricated.

    Lineage is the workflow-common lineage on the instance overlaid by the task-specific
    lineage on the task (task fields win when set), so sibling tasks driven by different
    agents are attributed to their own agent/artifacts/causation while still inheriting
    workflow-common references.
    """
    lineage = (instance.lineage or ExecutionLineage()).overlay(
        task.lineage if task is not None else None
    )
    return CanonicalExecutionState(
        runtime_id=config.runtime_id,
        runtime_version=config.runtime_version,
        workflow_id=instance.workflow_id,
        instance_id=instance.instance_id,
        task_id=task.task_id if task is not None else None,
        correlation_id=instance.correlation_id,
        causation_id=lineage.causation_id,
        parent_workflow_ref=lineage.parent_workflow_ref,
        parent_task_ref=lineage.parent_task_ref,
        assigned_agent_ref=lineage.assigned_agent_ref,
        agent_team_plan_ref=lineage.agent_team_plan_ref,
        assignment_digest=lineage.assignment_digest,
        authority_scope_ref=lineage.authority_scope_ref,
        workflow_status=instance.status.value,
        task_status=task.status.value if task is not None else None,
        attempt=task.attempts if task is not None else 0,
        provider_id=proposal.provider_id if proposal is not None else None,
        operation=proposal.operation if proposal is not None else None,
        idempotency_key=proposal.idempotency_key if proposal is not None else None,
        proposal_version=proposal.proposal_version if proposal is not None else None,
        proposal_fingerprint=proposal.fingerprint if proposal is not None else None,
        governance_disposition=(
            evaluation.disposition.value if evaluation is not None else None
        ),
        evaluation_reference=(
            evaluation.evaluation_reference if evaluation is not None else None
        ),
        authorization_reference=(
            evaluation.authorization_reference if evaluation is not None else None
        ),
        clearance_reference=(
            evaluation.clearance_reference if evaluation is not None else None
        ),
        valid_until=evaluation.valid_until if evaluation is not None else None,
        input_artifact_refs=lineage.input_artifact_refs,
        output_artifact_refs=lineage.output_artifact_refs,
        evidence_refs=lineage.evidence_refs,
        # execution_reference / result_digest have no canonical upstream source in the
        # reference engine yet (a future Runtime Assurance / receipt consumer owns them).
        execution_reference=None,
        result_digest=None,
    ).sealed()
