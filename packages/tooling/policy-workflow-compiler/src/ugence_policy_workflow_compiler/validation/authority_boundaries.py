"""Authority-boundary enforcement over the workflow IR.

The compiler may wire capabilities together but must never emit a graph in which
one module self-authorizes another's decision. This module encodes the allowed
(node-kind -> owning-capability, disposition) table and reports violations. It is
used both by the validator (as a pre-synthesis object check) and by the compiler
(as a post-synthesis IR check). A violation is a compile error, not a warning.

Concretely it rejects graphs where:
  * TAP becomes a decision authority;
  * StoryGraph becomes a binding decision maker;
  * Decision Authority performs exact-action authorization;
  * ActionGate / Action Clearance make the business decision;
  * an orchestrator grants authority;
  * an advisory node is marked authoritative.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..models.common import AuthorityDisposition, CapabilityId
from ..compiler.workflow_ir import NodeKind, WorkflowIR, WorkflowNode

#: node kind -> (required owning capability, required disposition)
_NODE_AUTHORITY_TABLE: Dict[NodeKind, Tuple[CapabilityId, AuthorityDisposition]] = {
    NodeKind.EVIDENCE_REQUIREMENT: (CapabilityId.COMPILER, AuthorityDisposition.ADVISORY),
    NodeKind.EVIDENCE_ADMISSIBILITY: (CapabilityId.TAP, AuthorityDisposition.ADVISORY),
    NodeKind.DECISION_RULE: (CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.AUTHORITY_CHECK: (CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.APPROVAL_GATE: (CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.SEGREGATION_OF_DUTIES_GATE: (
        CapabilityId.DECISION_AUTHORITY,
        AuthorityDisposition.AUTHORITATIVE,
    ),
    NodeKind.PROHIBITED_CONDITION: (
        CapabilityId.DECISION_AUTHORITY,
        AuthorityDisposition.AUTHORITATIVE,
    ),
    NodeKind.EXCEPTION_BRANCH: (CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.OVERRIDE_GATE: (CapabilityId.DECISION_AUTHORITY, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.ACTION_CONSTRAINT: (CapabilityId.ACTION_GATE, AuthorityDisposition.AUTHORITATIVE),
    NodeKind.SEQUENCE_RISK_CHECK: (CapabilityId.STORYGRAPH, AuthorityDisposition.ADVISORY),
    NodeKind.ACTION_CLEARANCE_REQUIREMENT: (
        CapabilityId.ACTION_CLEARANCE,
        AuthorityDisposition.AUTHORITATIVE,
    ),
    NodeKind.AUDIT_EMISSION: (CapabilityId.COMPILER, AuthorityDisposition.ADVISORY),
    NodeKind.TERMINAL_OUTCOME: (CapabilityId.COMPILER, AuthorityDisposition.ADVISORY),
}


class BoundaryViolation:
    """A single authority-boundary violation."""

    __slots__ = ("node_id", "kind", "message")

    def __init__(self, node_id: str, kind: str, message: str) -> None:
        self.node_id = node_id
        self.kind = kind
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"BoundaryViolation({self.node_id!r}, {self.message!r})"


def check_node(node: WorkflowNode) -> List[BoundaryViolation]:
    """Return authority-boundary violations for a single node."""
    expected = _NODE_AUTHORITY_TABLE.get(node.kind)
    if expected is None:  # pragma: no cover - all kinds are in the table
        return [
            BoundaryViolation(
                node.node_id, node.kind.value, f"unknown node kind {node.kind.value}"
            )
        ]
    exp_capability, exp_disposition = expected
    violations: List[BoundaryViolation] = []
    if node.owning_capability is not exp_capability:
        violations.append(
            BoundaryViolation(
                node.node_id,
                node.kind.value,
                f"{node.kind.value} must be owned by {exp_capability.value}, "
                f"not {node.owning_capability.value}",
            )
        )
    if node.disposition is not exp_disposition:
        violations.append(
            BoundaryViolation(
                node.node_id,
                node.kind.value,
                f"{node.kind.value} must be {exp_disposition.value}, "
                f"not {node.disposition.value}",
            )
        )
    return violations


def check_ir(ir: WorkflowIR) -> List[BoundaryViolation]:
    """Return all authority-boundary violations across an IR."""
    violations: List[BoundaryViolation] = []
    for node in ir.nodes:
        violations.extend(check_node(node))
    return violations


def expected_owner(kind: NodeKind) -> Tuple[CapabilityId, AuthorityDisposition]:
    """The required (capability, disposition) for a node kind."""
    return _NODE_AUTHORITY_TABLE[kind]
