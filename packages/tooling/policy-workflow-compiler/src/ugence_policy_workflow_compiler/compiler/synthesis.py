"""Deterministic workflow synthesis (Stage 3).

Turns an approved :class:`PolicyPack` into a :class:`WorkflowIR`, emitting only the
capabilities the policy requires and preserving authority boundaries. Node ids are
content-addressed and node/edge order is deterministic, so identical approved
input yields an identical IR.

A node's owning capability is taken from the policy object that produced it, and
its disposition is looked up from the capability registry. A pack that declares an
illegal owner (e.g. a decision rule owned by TAP) therefore synthesizes an IR that
fails the authority-boundary check — surfacing as a compile error, never a warning.
"""

from __future__ import annotations

from typing import List, Tuple

from ..models.common import BlockBehavior, CapabilityId
from ..models.policy_pack import PolicyPack
from .capability_registry import CapabilityRegistry, DEFAULT_REGISTRY
from .workflow_ir import (
    EdgeKind,
    NodeKind,
    WorkflowEdge,
    WorkflowIR,
    WorkflowNode,
    make_edge_id,
    make_node_id,
)

# Deterministic stage ordering along the canonical governed chain:
# evidence -> admissibility -> advisory risk -> prohibited -> authority ->
# decision -> segregation -> approval -> exception -> override -> action ->
# clearance -> audit -> terminal.
_STAGE_RANK = {
    NodeKind.EVIDENCE_REQUIREMENT: 10,
    NodeKind.EVIDENCE_ADMISSIBILITY: 20,
    NodeKind.SEQUENCE_RISK_CHECK: 30,
    NodeKind.PROHIBITED_CONDITION: 40,
    NodeKind.AUTHORITY_CHECK: 50,
    NodeKind.DECISION_RULE: 60,
    NodeKind.SEGREGATION_OF_DUTIES_GATE: 70,
    NodeKind.APPROVAL_GATE: 80,
    NodeKind.EXCEPTION_BRANCH: 90,
    NodeKind.OVERRIDE_GATE: 100,
    NodeKind.ACTION_CONSTRAINT: 110,
    NodeKind.ACTION_CLEARANCE_REQUIREMENT: 120,
    NodeKind.AUDIT_EMISSION: 130,
    NodeKind.TERMINAL_OUTCOME: 140,
}

#: Fixed terminal outcome labels the synthesizer always emits.
TERMINAL_LABELS: Tuple[str, ...] = (
    "ADVANCE_AUTHORIZED",
    "BLOCKED",
    "ESCALATED",
    "DENIED",
    "INDETERMINATE",
)


class WorkflowSynthesizer:
    """Deterministically synthesizes a governed-workflow IR from a policy pack."""

    def __init__(self, registry: CapabilityRegistry = DEFAULT_REGISTRY) -> None:
        self._registry = registry

    def _disposition(self, capability: CapabilityId):
        return self._registry.get(capability).disposition

    def _contract(self, capability: CapabilityId) -> str:
        return self._registry.get(capability).public_contract

    def _make_node(
        self,
        kind: NodeKind,
        owning_capability: CapabilityId,
        input_object_ids: Tuple[str, ...],
        *,
        authority_type: str = "",
        output_contract: str = "",
        failure_behavior: BlockBehavior = BlockBehavior.BLOCK,
        audit_requirements: Tuple[str, ...] = (),
        label: str = "",
    ) -> WorkflowNode:
        return WorkflowNode(
            node_id=make_node_id(kind, owning_capability, input_object_ids),
            kind=kind,
            owning_capability=owning_capability,
            authority_type=authority_type,
            disposition=self._disposition(owning_capability),
            public_contract_target=self._contract(owning_capability),
            input_object_ids=input_object_ids,
            output_contract=output_contract,
            failure_behavior=failure_behavior,
            audit_requirements=audit_requirements,
            label=label,
        )

    def synthesize(self, pack: PolicyPack) -> WorkflowIR:
        nodes: List[WorkflowNode] = []

        # 1. Evidence requirements + admissibility.
        for ev in pack.required_evidence:
            if not ev.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.EVIDENCE_REQUIREMENT,
                    CapabilityId.COMPILER,
                    (ev.object_id,),
                    output_contract=f"evidence_present:{ev.fact_key}",
                    failure_behavior=ev.on_missing,
                    audit_requirements=("evidence_references",),
                    label=f"require:{ev.name}",
                )
            )
            if ev.requires_admissibility_check:
                nodes.append(
                    self._make_node(
                        NodeKind.EVIDENCE_ADMISSIBILITY,
                        ev.admissibility_capability,
                        (ev.object_id,),
                        output_contract="assertion_admissible",
                        failure_behavior=ev.on_missing,
                        audit_requirements=("evidence_references",),
                        label=f"admissible:{ev.name}",
                    )
                )

        # 2. Advisory sequence-risk checks (StoryGraph).
        for pattern in pack.sequence_risk_patterns:
            if not pattern.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.SEQUENCE_RISK_CHECK,
                    pattern.owning_capability,
                    (pattern.object_id,),
                    output_contract="advisory_sequence_risk",
                    failure_behavior=BlockBehavior.ESCALATE,
                    audit_requirements=("reason_codes",),
                    label=f"risk:{pattern.name}",
                )
            )

        # 3. Prohibited conditions (fail-closed block guards).
        for cond in pack.prohibited_conditions:
            if not cond.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.PROHIBITED_CONDITION,
                    cond.owning_capability,
                    (cond.object_id,),
                    output_contract="not_prohibited",
                    failure_behavior=cond.behavior,
                    audit_requirements=("reason_codes", "outcome"),
                    label=f"prohibit:{cond.name}",
                )
            )

        # 4. Authority checks.
        for auth in pack.authority_requirements:
            if not auth.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.AUTHORITY_CHECK,
                    auth.owning_capability,
                    (auth.object_id,),
                    authority_type=auth.authority_type.value,
                    output_contract="authority_satisfied",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("actor_identity", "actor_role", "authority_reference"),
                    label=f"authority:{auth.name}",
                )
            )

        # 5. Decision rules.
        for rule in pack.decision_rules:
            if not rule.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.DECISION_RULE,
                    rule.owning_capability,
                    (rule.object_id,),
                    output_contract=f"decision:{rule.on_satisfied_outcome}",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("decision_reference", "reason_codes"),
                    label=f"decision:{rule.name}",
                )
            )

        # 6. Approval paths (approval gate + optional segregation-of-duties gate).
        for path in pack.approval_paths:
            if not path.enabled:
                continue
            if path.segregation_pairs:
                nodes.append(
                    self._make_node(
                        NodeKind.SEGREGATION_OF_DUTIES_GATE,
                        path.owning_capability,
                        (path.object_id,),
                        output_contract="segregation_satisfied",
                        failure_behavior=BlockBehavior.BLOCK,
                        audit_requirements=("actor_identity", "actor_role"),
                        label=f"sod:{path.name}",
                    )
                )
            nodes.append(
                self._make_node(
                    NodeKind.APPROVAL_GATE,
                    path.owning_capability,
                    (path.object_id,),
                    output_contract="approvals_complete",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("actor_identity", "actor_role", "decision_reference"),
                    label=f"approval:{path.name}",
                )
            )

        # 7. Exception branches.
        for exc in pack.exception_rules:
            if not exc.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.EXCEPTION_BRANCH,
                    exc.owning_capability,
                    (exc.object_id,),
                    output_contract=f"exception:{exc.exception_outcome}",
                    failure_behavior=BlockBehavior.ESCALATE,
                    audit_requirements=("exception_reference", "reason_codes"),
                    label=f"exception:{exc.name}",
                )
            )

        # 8. Override gates.
        for ovr in pack.override_rules:
            if not ovr.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.OVERRIDE_GATE,
                    ovr.owning_capability,
                    (ovr.object_id,),
                    output_contract="override_valid",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("override_reference", "actor_identity", "reason_codes"),
                    label=f"override:{ovr.name}",
                )
            )

        # 9. Action constraints (+ optional commit-time clearance).
        for constraint in pack.action_constraints:
            if not constraint.enabled:
                continue
            nodes.append(
                self._make_node(
                    NodeKind.ACTION_CONSTRAINT,
                    constraint.owning_capability,
                    (constraint.object_id,),
                    output_contract=f"action_authorized:{constraint.action_type}",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("action_reference", "constraint_digest", "reason_codes"),
                    label=f"constraint:{constraint.name}",
                )
            )
            if constraint.requires_clearance:
                nodes.append(
                    self._make_node(
                        NodeKind.ACTION_CLEARANCE_REQUIREMENT,
                        CapabilityId.ACTION_CLEARANCE,
                        (constraint.object_id,),
                        output_contract="action_clear",
                        failure_behavior=BlockBehavior.BLOCK,
                        audit_requirements=("action_reference", "reason_codes"),
                        label=f"clearance:{constraint.name}",
                    )
                )

        # 10. A single audit-emission node bound to all audit requirements/objects.
        audit_inputs = tuple(sorted(o.object_id for o in pack.all_objects()))
        nodes.append(
            self._make_node(
                NodeKind.AUDIT_EMISSION,
                CapabilityId.COMPILER,
                audit_inputs or (pack.pack_id,),
                output_contract="audit_event_emitted",
                failure_behavior=BlockBehavior.BLOCK,
                audit_requirements=("event_digest", "previous_event_digest"),
                label="audit_emission",
            )
        )

        # 11. Terminal outcomes (fixed set).
        for terminal in TERMINAL_LABELS:
            nodes.append(
                self._make_node(
                    NodeKind.TERMINAL_OUTCOME,
                    CapabilityId.COMPILER,
                    (f"{pack.pack_id}:{terminal}",),
                    output_contract=f"terminal:{terminal}",
                    failure_behavior=BlockBehavior.BLOCK,
                    audit_requirements=("outcome",),
                    label=f"terminal:{terminal}",
                )
            )

        nodes = self._dedupe_and_order(nodes)
        edges = self._build_edges(nodes)
        referenced = tuple(
            sorted({n.owning_capability.value for n in nodes})
        )
        return WorkflowIR(
            policy_pack_id=pack.pack_id,
            policy_pack_version=pack.version,
            nodes=tuple(nodes),
            edges=tuple(edges),
            referenced_capabilities=referenced,
        )

    @staticmethod
    def _dedupe_and_order(nodes: List[WorkflowNode]) -> List[WorkflowNode]:
        """Drop duplicate node ids and sort deterministically by (stage, id)."""
        seen = {}
        for node in nodes:
            seen.setdefault(node.node_id, node)
        ordered = sorted(
            seen.values(), key=lambda n: (_STAGE_RANK[n.kind], n.node_id)
        )
        return ordered

    def _build_edges(self, nodes: List[WorkflowNode]) -> List[WorkflowEdge]:
        """Build deterministic spine + branch edges.

        The spine connects consecutive non-terminal, non-audit nodes; each guard
        node also branches to the appropriate terminal outcome. The final spine
        node flows into audit emission, which flows into ADVANCE_AUTHORIZED.
        """
        terminals = {
            n.label.split(":", 1)[1]: n.node_id
            for n in nodes
            if n.kind is NodeKind.TERMINAL_OUTCOME
        }
        audit_node = next(
            (n for n in nodes if n.kind is NodeKind.AUDIT_EMISSION), None
        )
        spine = [
            n
            for n in nodes
            if n.kind not in (NodeKind.TERMINAL_OUTCOME, NodeKind.AUDIT_EMISSION)
        ]

        edges: List[WorkflowEdge] = []

        def add(kind: EdgeKind, src: str, dst: str) -> None:
            edges.append(
                WorkflowEdge(
                    edge_id=make_edge_id(kind, src, dst),
                    kind=kind,
                    source_id=src,
                    target_id=dst,
                    order=len(edges),
                )
            )

        # Spine.
        for i in range(len(spine) - 1):
            add(EdgeKind.ON_PASS, spine[i].node_id, spine[i + 1].node_id)

        # Branch edges per node kind.
        for node in spine:
            self._branch_edges(node, terminals, add)

        # Spine tail -> audit -> ADVANCE_AUTHORIZED.
        if audit_node is not None:
            if spine:
                add(EdgeKind.ON_PASS, spine[-1].node_id, audit_node.node_id)
            add(EdgeKind.ON_PASS, audit_node.node_id, terminals["ADVANCE_AUTHORIZED"])

        return edges

    @staticmethod
    def _branch_edges(node: WorkflowNode, terminals, add) -> None:
        kind = node.kind
        blocked = terminals["BLOCKED"]
        escalated = terminals["ESCALATED"]
        denied = terminals["DENIED"]
        indeterminate = terminals["INDETERMINATE"]
        if kind in (NodeKind.EVIDENCE_REQUIREMENT, NodeKind.EVIDENCE_ADMISSIBILITY):
            target = escalated if node.failure_behavior is BlockBehavior.ESCALATE else blocked
            add(EdgeKind.ON_MISSING, node.node_id, target)
        elif kind is NodeKind.PROHIBITED_CONDITION:
            target = escalated if node.failure_behavior is BlockBehavior.ESCALATE else blocked
            add(EdgeKind.ON_FAIL, node.node_id, target)
        elif kind is NodeKind.SEQUENCE_RISK_CHECK:
            add(EdgeKind.ON_ESCALATE, node.node_id, escalated)
        elif kind in (NodeKind.AUTHORITY_CHECK, NodeKind.SEGREGATION_OF_DUTIES_GATE, NodeKind.APPROVAL_GATE):
            add(EdgeKind.ON_FAIL, node.node_id, denied)
        elif kind is NodeKind.DECISION_RULE:
            add(EdgeKind.ON_FAIL, node.node_id, denied)
        elif kind is NodeKind.EXCEPTION_BRANCH:
            add(EdgeKind.ON_EXCEPTION, node.node_id, escalated)
        elif kind is NodeKind.OVERRIDE_GATE:
            add(EdgeKind.ON_OVERRIDE, node.node_id, denied)
        elif kind is NodeKind.ACTION_CONSTRAINT:
            add(EdgeKind.ON_DENY, node.node_id, denied)
            add(EdgeKind.ON_INDETERMINATE, node.node_id, indeterminate)
        elif kind is NodeKind.ACTION_CLEARANCE_REQUIREMENT:
            add(EdgeKind.ON_DENY, node.node_id, blocked)
