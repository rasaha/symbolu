"""Deterministic offline traversal of a compiled workflow under a scenario's facts.

**This simulates; it does not execute.** For each node kind the traversal reports
what the graph *requires*, never that the requirement was met:

* an `AUTHORITY_CHECK` observes "this node requires authority A" — never that an
  actor holds it;
* an `APPROVAL_GATE` observes "this node requires approval by role R" — never an
  approval;
* an `ACTION_CLEARANCE_REQUIREMENT` observes that clearance is required — it clears
  nothing;
* an `AUDIT_EMISSION` observes the event types that *would* be emitted.

A scenario's `actor_identities` are stated facts, not credentials, and its
`ExpectedOutcome` is an oracle to compare against, not an authorization this module
issues. Comparing an observation to an oracle yields a test result, and a test
result is not a grant.

Where a node states no evaluable predicate, the traversal records `NOT_EVALUABLE`
and continues rather than inventing a semantics for it. Nothing here reads a clock,
an environment, a file or a socket, and there is no port through which a real
provider could be supplied — that seam is how a simulator becomes a runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..compiler.release import CompiledReleasePackage
from ..compiler.workflow_ir import EdgeKind, NodeKind, WorkflowIR, WorkflowNode
from ..evaluation import evaluate_all, evaluate_any, evaluate_predicate
from ..models.assurance import ReplayCase, TestScenario
from ..models.policy_pack import PolicyPack
from .models import (
    NodeObservation,
    NodeOutcome,
    OracleComparison,
    SimulationRun,
)

#: Node kinds that state a requirement this simulator may never resolve. Each is a
#: point where a runtime would call an authority; here it is only described.
_REQUIREMENT_KINDS = {
    NodeKind.AUTHORITY_CHECK,
    NodeKind.APPROVAL_GATE,
    NodeKind.SEGREGATION_OF_DUTIES_GATE,
    NodeKind.ACTION_CLEARANCE_REQUIREMENT,
    NodeKind.OVERRIDE_GATE,
}

#: The edge to follow for each observed outcome, in preference order. The first
#: kind present on the node is taken; ``NEXT`` is the fallback.
_OUTCOME_EDGES: Dict[NodeOutcome, Tuple[EdgeKind, ...]] = {
    NodeOutcome.SATISFIED: (EdgeKind.ON_PASS, EdgeKind.NEXT),
    NodeOutcome.UNSATISFIED: (EdgeKind.ON_FAIL, EdgeKind.ON_DENY, EdgeKind.NEXT),
    NodeOutcome.MISSING_FACT: (EdgeKind.ON_MISSING, EdgeKind.ON_FAIL, EdgeKind.NEXT),
    # A requirement this simulator may not resolve does not stop the traversal —
    # it makes everything downstream CONDITIONAL on that requirement, which the run
    # states explicitly rather than quietly assuming. Continuing without saying so
    # would be indistinguishable from deciding.
    NodeOutcome.REQUIREMENT_OBSERVED: (EdgeKind.NEXT, EdgeKind.ON_PASS),
    # A node the simulator cannot evaluate has not failed, so the no-objection
    # continuation is taken. This is a stated rule, not a fallback.
    NodeOutcome.NOT_EVALUABLE: (EdgeKind.NEXT, EdgeKind.ON_PASS),
}

#: A traversal step limit. A compiled graph is acyclic by validation, so this only
#: bounds a malformed artifact — it fails closed instead of looping.
_MAX_STEPS = 1000


def _facts_of(scenario) -> Mapping[str, Any]:
    """The scenario's flat fact set. Evidence is merged in under its own keys."""
    facts: Dict[str, Any] = {}
    captured = getattr(scenario, "captured_facts", None)
    facts.update(dict(captured) if captured else dict(getattr(scenario, "initial_facts", {})))
    facts.update(dict(getattr(scenario, "evidence", {}) or {}))
    return facts


def _objects_for(pack: PolicyPack, node: WorkflowNode) -> Tuple[Any, ...]:
    index = pack.object_index()
    return tuple(
        index[object_id] for object_id in node.input_object_ids if object_id in index
    )


def _observe(node: WorkflowNode, pack: PolicyPack, facts: Mapping[str, Any]):
    """What this node's own policy objects say, under these facts."""
    objects = _objects_for(pack, node)
    evaluated = tuple(o.object_id for o in objects)
    requirements: List[str] = []

    if node.kind is NodeKind.TERMINAL_OUTCOME:
        return NodeOutcome.TERMINAL, evaluated, ()

    if node.kind in _REQUIREMENT_KINDS:
        # Observed, never resolved. This is the line between simulating and
        # executing, and it is drawn per node kind rather than per call site.
        for obj in objects:
            requirement = getattr(obj, "required_role", "") or getattr(
                obj, "decision_scope", ""
            )
            if requirement:
                requirements.append(f"{node.kind.value} requires {requirement}")
        if not requirements:
            requirements.append(f"{node.kind.value} states a requirement")
        return NodeOutcome.REQUIREMENT_OBSERVED, evaluated, tuple(requirements)

    if node.kind is NodeKind.EVIDENCE_REQUIREMENT:
        for obj in objects:
            fact_key = getattr(obj, "fact_key", "")
            if fact_key and fact_key not in facts:
                return NodeOutcome.MISSING_FACT, evaluated, ()
        return NodeOutcome.SATISFIED, evaluated, ()

    if node.kind is NodeKind.PROHIBITED_CONDITION:
        for obj in objects:
            conditions = getattr(obj, "conditions", ())
            if conditions and evaluate_any(conditions, facts):
                # A prohibition that trips blocks: it is the unsatisfied path.
                return NodeOutcome.UNSATISFIED, evaluated, ()
        return NodeOutcome.SATISFIED, evaluated, ()

    if node.kind is NodeKind.ACTION_CONSTRAINT:
        # Only the numeric bound kinds are modelled. A constraint this simulator
        # does not model is NOT_EVALUABLE, never a failure: treating "I cannot
        # evaluate this" as "this failed" would deny every workflow that uses a
        # membership or once-only constraint, which is a fabricated answer dressed
        # as a conservative one.
        evaluable = False
        for obj in objects:
            if getattr(obj, "kind", None) is None or obj.kind.value not in (
                "NUMERIC_RANGE", "HARD_LIMIT"
            ):
                continue
            evaluable = True
            parameter = getattr(obj, "parameter", "")
            maximum = getattr(obj, "max_value", None)
            minimum = getattr(obj, "min_value", None)
            if not parameter or parameter not in facts:
                return NodeOutcome.MISSING_FACT, evaluated, ()
            value = facts[parameter]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return NodeOutcome.MISSING_FACT, evaluated, ()
            if maximum is not None and value > maximum:
                return NodeOutcome.UNSATISFIED, evaluated, ()
            if minimum is not None and value < minimum:
                return NodeOutcome.UNSATISFIED, evaluated, ()
        return (
            NodeOutcome.SATISFIED if evaluable else NodeOutcome.NOT_EVALUABLE,
            evaluated,
            (),
        )

    # Every remaining kind that states declarative conditions is evaluated through
    # the one shared evaluator — there is no second interpretation of a predicate.
    conditioned = [o for o in objects if getattr(o, "conditions", ())]
    if conditioned:
        for obj in conditioned:
            for predicate in obj.conditions:
                if predicate.fact_key not in facts and predicate.comparator.value not in (
                    "IS_EMPTY", "NON_EMPTY"
                ):
                    return NodeOutcome.MISSING_FACT, evaluated, ()
        satisfied = all(evaluate_all(o.conditions, facts) for o in conditioned)
        return (
            NodeOutcome.SATISFIED if satisfied else NodeOutcome.UNSATISFIED,
            evaluated,
            (),
        )

    return NodeOutcome.NOT_EVALUABLE, evaluated, ()


def _entry_node(ir: WorkflowIR) -> Optional[WorkflowNode]:
    """The node no edge targets. Deterministic: nodes are canonically ordered."""
    targeted = {e.target_id for e in ir.edges}
    for node in ir.nodes:
        if node.node_id not in targeted:
            return node
    return ir.nodes[0] if ir.nodes else None


def _next_edge(ir: WorkflowIR, node_id: str, outcome: NodeOutcome):
    outgoing = sorted(
        (e for e in ir.edges if e.source_id == node_id), key=lambda e: (e.order, e.edge_id)
    )
    for kind in _OUTCOME_EDGES.get(outcome, (EdgeKind.NEXT,)):
        for edge in outgoing:
            if edge.kind is kind:
                return edge
    # No edge matches the observed outcome. Taking an arbitrary one would
    # manufacture a path the graph does not state, so the traversal stops instead
    # and the run reports itself INCOMPLETE.
    return None


def simulate(
    package: CompiledReleasePackage, scenario
) -> SimulationRun:
    """Traverse a compiled release under one scenario's facts. Offline and total.

    Ruling P3C-1: the result is evidence. Nothing consumes it to gate compilation,
    and no field of it could grant, approve or clear anything.
    """
    ir = package.workflow_ir
    pack = package.policy_pack
    facts = _facts_of(scenario)
    by_id = {n.node_id: n for n in ir.nodes}

    trace: List[NodeObservation] = []
    reason_codes: List[str] = []
    audit_events: List[str] = []
    conditional_on: List[str] = []
    visited: set = set()

    node = _entry_node(ir)
    steps = 0
    terminal_state = ""
    while node is not None and steps < _MAX_STEPS:
        steps += 1
        if node.node_id in visited:
            break
        visited.add(node.node_id)

        outcome, evaluated, requirements = _observe(node, pack, facts)
        described = tuple(node.audit_requirements)
        for event in described:
            if event not in audit_events:
                audit_events.append(event)
        for requirement in requirements:
            if requirement not in reason_codes:
                reason_codes.append(requirement)
            if requirement not in conditional_on:
                conditional_on.append(requirement)

        if outcome is NodeOutcome.TERMINAL:
            terminal_state = node.output_contract or node.label or node.node_id
            trace.append(NodeObservation(
                node_id=node.node_id, node_kind=node.kind.value, outcome=outcome,
                evaluated_object_ids=evaluated, described_audit_events=described))
            break

        edge = _next_edge(ir, node.node_id, outcome)
        trace.append(NodeObservation(
            node_id=node.node_id, node_kind=node.kind.value, outcome=outcome,
            evaluated_object_ids=evaluated, observed_requirements=requirements,
            described_audit_events=described,
            followed_edge_kind=edge.kind.value if edge else "",
            next_node_id=edge.target_id if edge else ""))
        if outcome is NodeOutcome.UNSATISFIED and node.failure_behavior.value == "BLOCK":
            if not edge:
                terminal_state = "BLOCKED"
                break
        node = by_id.get(edge.target_id) if edge else None

    if not terminal_state:
        terminal_state = "BLOCKED" if trace and trace[-1].outcome in (
            NodeOutcome.UNSATISFIED, NodeOutcome.MISSING_FACT
        ) else "INCOMPLETE"

    expected = getattr(scenario, "expected_outcome", None)
    oracle = OracleComparison(
        expected_terminal_state=getattr(expected, "terminal_state", "") or "",
        observed_terminal_state=terminal_state,
        expected_reason_codes=tuple(getattr(expected, "reason_codes", ()) or ()),
        observed_reason_codes=tuple(reason_codes),
        expected_audit_events=tuple(getattr(expected, "audit_events", ()) or ()),
        described_audit_events=tuple(audit_events),
    )

    run = SimulationRun(
        release_digest=package.structural_digest,
        policy_pack_id=pack.pack_id,
        scenario_id=getattr(scenario, "object_id", ""),
        trace=tuple(trace),
        terminal_state=terminal_state,
        reason_codes=tuple(reason_codes),
        described_audit_events=tuple(audit_events),
        unreached_node_ids=tuple(sorted(set(by_id) - visited)),
        conditional_on_requirements=tuple(conditional_on),
        oracle=oracle,
    )
    return run.model_copy(update={"run_digest": run.logical_digest()})


def simulate_all(package: CompiledReleasePackage) -> Tuple[SimulationRun, ...]:
    """Simulate every scenario and replay case the release's assurance carries."""
    assurance = package.assurance_manifest
    cases = tuple(assurance.scenarios) + tuple(assurance.replay_cases)
    return tuple(simulate(package, case) for case in cases)


__all__ = ["simulate", "simulate_all"]
