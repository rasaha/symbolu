"""The deterministic governed-workflow intermediate representation.

Nodes and edges are typed and content-addressed: a node's id is derived from its
kind, owning capability, and input object ids, so identical approved input yields
identical node ids. Edges carry a deterministic ordering key. The IR records, per
node, the owning capability, authority type, input object ids, output contract,
failure behavior, audit requirements, the capability public-contract target, and
whether the node is advisory or authoritative.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import Field

from ..models.common import (
    AuthorityDisposition,
    BlockBehavior,
    CapabilityId,
    CompilerModel,
)
from ..serialization import hashing


class NodeKind(str, Enum):
    EVIDENCE_REQUIREMENT = "EVIDENCE_REQUIREMENT"
    EVIDENCE_ADMISSIBILITY = "EVIDENCE_ADMISSIBILITY"
    DECISION_RULE = "DECISION_RULE"
    AUTHORITY_CHECK = "AUTHORITY_CHECK"
    APPROVAL_GATE = "APPROVAL_GATE"
    SEGREGATION_OF_DUTIES_GATE = "SEGREGATION_OF_DUTIES_GATE"
    PROHIBITED_CONDITION = "PROHIBITED_CONDITION"
    EXCEPTION_BRANCH = "EXCEPTION_BRANCH"
    OVERRIDE_GATE = "OVERRIDE_GATE"
    ACTION_CONSTRAINT = "ACTION_CONSTRAINT"
    SEQUENCE_RISK_CHECK = "SEQUENCE_RISK_CHECK"
    ACTION_CLEARANCE_REQUIREMENT = "ACTION_CLEARANCE_REQUIREMENT"
    AUDIT_EMISSION = "AUDIT_EMISSION"
    TERMINAL_OUTCOME = "TERMINAL_OUTCOME"


class EdgeKind(str, Enum):
    NEXT = "NEXT"
    ON_PASS = "ON_PASS"
    ON_FAIL = "ON_FAIL"
    ON_MISSING = "ON_MISSING"
    ON_EXCEPTION = "ON_EXCEPTION"
    ON_OVERRIDE = "ON_OVERRIDE"
    ON_ESCALATE = "ON_ESCALATE"
    ON_DENY = "ON_DENY"
    ON_INDETERMINATE = "ON_INDETERMINATE"


class WorkflowNode(CompilerModel):
    """A single governed-workflow node."""

    node_id: str
    kind: NodeKind
    #: The capability that owns this node's authority function.
    owning_capability: CapabilityId
    #: The authority type the node asserts (declarative label; may be empty for
    #: purely structural nodes).
    authority_type: str = ""
    #: Whether the node is advisory or authoritative.
    disposition: AuthorityDisposition
    #: The capability public-contract module this node targets ("" for structural).
    public_contract_target: str = ""
    #: Policy-object ids that feed this node.
    input_object_ids: Tuple[str, ...] = ()
    #: A declarative description of the node's output contract.
    output_contract: str = ""
    #: What the node does on failure — never proceed by default.
    failure_behavior: BlockBehavior = BlockBehavior.BLOCK
    #: Audit-field names this node must emit.
    audit_requirements: Tuple[str, ...] = ()
    #: A short label of the node's purpose.
    label: str = ""


class WorkflowEdge(CompilerModel):
    """A typed, ordered edge between two nodes."""

    edge_id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    #: Deterministic ordering key within the whole edge list.
    order: int = Field(..., ge=0)


class WorkflowIR(CompilerModel):
    """The full governed-workflow graph for a compiled pack."""

    policy_pack_id: str
    policy_pack_version: int
    ir_version: str = "workflow_ir.v1"
    nodes: Tuple[WorkflowNode, ...] = ()
    edges: Tuple[WorkflowEdge, ...] = ()
    #: Capability ids referenced by at least one node, in deterministic order.
    referenced_capabilities: Tuple[str, ...] = ()

    @property
    def node_kinds(self) -> Tuple[str, ...]:
        seen: list[str] = []
        for n in self.nodes:
            if n.kind.value not in seen:
                seen.append(n.kind.value)
        return tuple(seen)

    def logical_digest(self) -> str:
        """Content digest over the ordered nodes and edges (no timestamps)."""
        return hashing.digest(
            {"nodes": list(self.nodes), "edges": list(self.edges)}
        )


def make_node_id(
    kind: NodeKind, owning_capability: CapabilityId, input_object_ids: Tuple[str, ...]
) -> str:
    """Deterministically derive a node id from its identity-defining fields."""
    key = hashing.digest(
        {
            "kind": kind.value,
            "capability": owning_capability.value,
            "inputs": sorted(input_object_ids),
        }
    )
    # short, stable, human-scannable id
    return f"node_{kind.value.lower()}_{key.split(':', 1)[1][:12]}"


def make_edge_id(kind: EdgeKind, source_id: str, target_id: str) -> str:
    key = hashing.digest(
        {"kind": kind.value, "source": source_id, "target": target_id}
    )
    return f"edge_{key.split(':', 1)[1][:12]}"
