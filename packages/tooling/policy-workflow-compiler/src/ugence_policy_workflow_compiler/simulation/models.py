"""What a simulation run records. Data only — nothing here can carry an effect.

Ruling P3C-1: a run is **evidence, not a gate**. Nothing in this module is consumed
by compilation, and no field could be: there is no grant, no approval record, no
clearance and no token anywhere in these types. A simulator that could return one
would already be a runtime.

Ruling P3C-2: a contradicted oracle is an :class:`OracleComparison` **on the run**,
because a disagreement is a property of one run against one scenario, not of the
release — the same release may satisfy one scenario and contradict another.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Tuple

from ..models.common import CompilerModel
from ..serialization import hashing


class NodeOutcome(str, Enum):
    """What the traversal observed at a node. None of these is a decision."""

    #: Every predicate the node's policy objects state held.
    SATISFIED = "SATISFIED"
    #: At least one stated predicate did not hold.
    UNSATISFIED = "UNSATISFIED"
    #: A fact the node needs is absent, so the node blocks rather than proceeds.
    MISSING_FACT = "MISSING_FACT"
    #: The node states a requirement this simulator may not resolve — an authority,
    #: an approval, a clearance. Observed and reported, never decided.
    REQUIREMENT_OBSERVED = "REQUIREMENT_OBSERVED"
    #: The node carries no evaluable policy predicate; traversal continues.
    NOT_EVALUABLE = "NOT_EVALUABLE"
    #: A terminal node; traversal stops here.
    TERMINAL = "TERMINAL"


class NodeObservation(CompilerModel):
    """One node, as the traversal saw it under a scenario's facts."""

    node_id: str
    node_kind: str
    outcome: NodeOutcome
    #: Policy-object ids whose predicates were evaluated at this node.
    evaluated_object_ids: Tuple[str, ...] = ()
    #: Requirements the node states — "requires authority X", "requires approval by
    #: role R". Descriptions of what the graph demands, never grants of it.
    observed_requirements: Tuple[str, ...] = ()
    #: Audit event types the node declares it would emit. Described, not emitted.
    described_audit_events: Tuple[str, ...] = ()
    #: The edge kind followed out of this node, empty at a terminal.
    followed_edge_kind: str = ""
    next_node_id: str = ""


class OracleComparison(CompilerModel):
    """The scenario's expectation set beside what the run observed (P3C-2)."""

    expected_terminal_state: str = ""
    observed_terminal_state: str = ""
    expected_reason_codes: Tuple[str, ...] = ()
    observed_reason_codes: Tuple[str, ...] = ()
    expected_audit_events: Tuple[str, ...] = ()
    described_audit_events: Tuple[str, ...] = ()

    @property
    def agrees(self) -> bool:
        """Whether the observation matches the oracle in every compared field."""
        return (
            self.expected_terminal_state == self.observed_terminal_state
            and set(self.expected_reason_codes) <= set(self.observed_reason_codes)
            and set(self.expected_audit_events) <= set(self.described_audit_events)
        )


class SimulationRun(CompilerModel):
    """One scenario exercised against one compiled release, offline.

    ``run_digest`` is a pure function of the release digest, the scenario and the
    trace, so replay is digest equality.
    """

    release_digest: str
    policy_pack_id: str
    scenario_id: str
    trace: Tuple[NodeObservation, ...] = ()
    terminal_state: str = ""
    reason_codes: Tuple[str, ...] = ()
    described_audit_events: Tuple[str, ...] = ()
    unreached_node_ids: Tuple[str, ...] = ()
    #: Requirements the traversal continued past without resolving — authorities,
    #: approvals, clearances. The terminal state below is the outcome **if** these
    #: are met; the simulator does not claim they were. Stating them is what keeps
    #: a conditional continuation from reading as a decision.
    conditional_on_requirements: Tuple[str, ...] = ()
    oracle: OracleComparison = OracleComparison()
    run_digest: str = ""

    def logical_digest(self) -> str:
        """Content digest over everything the run observed, excluding the slot."""
        return hashing.digest(
            {
                "release_digest": self.release_digest,
                "policy_pack_id": self.policy_pack_id,
                "scenario_id": self.scenario_id,
                "trace": list(self.trace),
                "terminal_state": self.terminal_state,
                "reason_codes": list(self.reason_codes),
                "described_audit_events": list(self.described_audit_events),
                "unreached_node_ids": list(self.unreached_node_ids),
                "conditional_on_requirements": list(self.conditional_on_requirements),
                "oracle": self.oracle,
            }
        )


__all__ = ["NodeOutcome", "NodeObservation", "OracleComparison", "SimulationRun"]
