"""Policy Workflow Compiler (PWC) consumption contract (spec §7, roadmap RA-4A).

``risk_authority`` never compiles policy prose. It *consumes* an activated,
digest-bound :class:`WorkflowIR` through this port. For RA-1..RA-4 the vertical
slice uses manually constructed / curated WorkflowIR (spec §34 MVP); this port
is the seam where a real PWC provider plugs in later without changing any
downstream service.
"""

from __future__ import annotations

from typing import Mapping, Optional, Protocol, runtime_checkable

from ..domain.enums import WorkflowStatus
from ..domain.workflow_ir import WorkflowIR

__all__ = ["WorkflowIRSource", "InMemoryWorkflowIRSource"]


@runtime_checkable
class WorkflowIRSource(Protocol):
    """Resolve an activated WorkflowIR by id and (optionally) version."""

    def get(
        self, workflow_ir_id: str, *, version: Optional[str] = None
    ) -> Optional[WorkflowIR]: ...


class InMemoryWorkflowIRSource:
    """A curated in-memory source of activated WorkflowIRs.

    Only ``ACTIVE`` WorkflowIRs are resolvable — a draft or retired policy is
    never handed to runtime evaluation (spec §7.3).
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], WorkflowIR] = {}
        self._latest: dict[str, WorkflowIR] = {}

    def register(self, workflow: WorkflowIR) -> WorkflowIR:
        if not workflow.digest:
            workflow = workflow.with_digest()
        self._by_key[(workflow.workflow_ir_id, workflow.version)] = workflow
        self._latest[workflow.workflow_ir_id] = workflow
        return workflow

    def get(
        self, workflow_ir_id: str, *, version: Optional[str] = None
    ) -> Optional[WorkflowIR]:
        if version is not None:
            workflow = self._by_key.get((workflow_ir_id, version))
        else:
            workflow = self._latest.get(workflow_ir_id)
        if workflow is None or workflow.status is not WorkflowStatus.ACTIVE:
            return None
        return workflow
