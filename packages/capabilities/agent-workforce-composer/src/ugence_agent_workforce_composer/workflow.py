"""Canonical immutable planning objects derived from a compiled workflow.

These are the *source-derived* products of the compiler adapter: one
:class:`WorkflowRoleRequirement` per AI-agent-eligible node, one
:class:`NonAgentDisposition` per non-agent node, a :class:`WorkflowNodeDisposition`
record for every node (total accounting), and the top-level
:class:`CompilerAdaptationResult`.

Field provenance discipline (Phase 0 §7): fields are labelled *source-derived*
(from the compiler IR), *enterprise-policy-derived* (from an injected overlay), or
*later-phase* (typed but unused optimization constraints — never ranked in P1).
"""
from __future__ import annotations

from typing import Optional, Tuple

from pydantic import Field

from .canonical import AwcModel
from .contracts import AuthorityDisposition, CapabilityOwner, NodeDisposition, NodeKind
from .version import CONTRACT_VERSION


class Provenance(AwcModel):
    """Where a canonical object came from, and whether it is synthetic."""

    source_kind: str  # e.g. "compiler_workflow_ir", "synthetic_fixture"
    synthetic: bool = False
    source_ref: str = ""
    notes: str = ""


class AuthorityContext(AwcModel):
    """The governance/authority envelope a source node carried into planning."""

    owning_capability: CapabilityOwner
    authority_disposition: AuthorityDisposition
    authority_type: str = ""
    public_contract_target: str = ""


class WorkflowRoleRequirement(AwcModel):
    """An immutable AI-agent-eligible workflow role.

    ``AI_AGENT_ELIGIBLE`` source nodes become exactly one of these. An eligible
    result against this role means only that no hard constraint disqualifies an
    agent — never that it is selected, recommended, best, authorized or assigned.
    """

    contract_version: str = CONTRACT_VERSION
    # -- source-derived (from the compiler IR) ---------------------------------
    role_id: str
    workflow_id: str
    workflow_version: int
    source_node_id: str
    source_node_kind: NodeKind
    role_name: str
    role_description: str = ""
    required_capabilities: Tuple[str, ...] = ()
    input_contract_refs: Tuple[str, ...] = ()
    output_contract_refs: Tuple[str, ...] = ()
    authority_context: AuthorityContext
    provenance: Provenance
    source_package_digest: str
    # -- enterprise-policy-derived (from an injected role overlay) -------------
    optional_capabilities: Tuple[str, ...] = ()
    required_tools: Tuple[str, ...] = ()
    prohibited_tools: Tuple[str, ...] = ()
    domain_requirements: Tuple[str, ...] = ()
    data_classification: str = ""
    residency_constraints: Tuple[str, ...] = ()
    provider_constraints: Tuple[str, ...] = ()
    deployment_constraints: Tuple[str, ...] = ()
    required_permissions: Tuple[str, ...] = ()
    prohibited_permissions: Tuple[str, ...] = ()
    authority_ceiling: int = 0
    required_audit_capabilities: Tuple[str, ...] = ()
    required_security_classification: int = 0
    required_evidence_classes: Tuple[str, ...] = ()
    state_requirement: str = ""
    human_review_requirement: bool = False
    # -- later-phase (typed, preserved, NEVER ranked/optimized in P1) ----------
    minimum_quality_constraint: Optional[float] = None
    maximum_latency_constraint: Optional[float] = None
    maximum_cost_constraint: Optional[float] = None
    model_requirement_refs: Tuple[str, ...] = ()
    fallback_policy_ref: str = ""
    evidence_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    # -- content address --------------------------------------------------------
    role_fingerprint: str = ""


class NonAgentDisposition(AwcModel):
    """An immutable disposition for a node not assigned to an AI agent.

    Holds any disposition except ``AI_AGENT_ELIGIBLE``. Every compiler node is
    represented either here or as a :class:`WorkflowRoleRequirement` — never both,
    never neither (total node accounting, invariant I2).
    """

    contract_version: str = CONTRACT_VERSION
    workflow_id: str
    node_id: str
    source_node_kind: NodeKind
    disposition: NodeDisposition
    reason_codes: Tuple[str, ...] = ()
    canonical_owner: str = ""
    authority_context: AuthorityContext
    source_capability: str = ""
    human_review_required: bool = False
    provenance: Provenance
    source_package_digest: str
    fingerprint: str = ""


class WorkflowNodeDisposition(AwcModel):
    """The one-per-node accounting record: which node got which disposition."""

    node_id: str
    source_node_kind: NodeKind
    disposition: NodeDisposition
    reason_codes: Tuple[str, ...] = ()
    role_id: str = ""          # set iff disposition == AI_AGENT_ELIGIBLE
    is_agent_role: bool = False


class AdaptationDiagnostic(AwcModel):
    """A structured diagnostic emitted during adaptation (never a silent drop)."""

    severity: str  # INFO | WARNING | ERROR | FATAL
    code: str
    node_id: str = ""
    message: str = ""


class CompilerAdaptationResult(AwcModel):
    """The complete, deterministic result of adapting one compiled workflow."""

    contract_version: str = CONTRACT_VERSION
    workflow_identity: str
    workflow_version: int
    source_contract_version: str
    source_package_digest: str
    node_dispositions: Tuple[WorkflowNodeDisposition, ...]
    role_requirements: Tuple[WorkflowRoleRequirement, ...]
    non_agent_dispositions: Tuple[NonAgentDisposition, ...]
    diagnostics: Tuple[AdaptationDiagnostic, ...] = ()
    ok: bool = True
    adaptation_fingerprint: str = ""

    # -- total-accounting invariant (I2) ---------------------------------------
    def all_node_ids(self) -> Tuple[str, ...]:
        return tuple(nd.node_id for nd in self.node_dispositions)

    def role_node_ids(self) -> frozenset:
        return frozenset(r.source_node_id for r in self.role_requirements)

    def non_agent_node_ids(self) -> frozenset:
        return frozenset(n.node_id for n in self.non_agent_dispositions)

    def accounting_holds(self) -> bool:
        """True iff role-node-ids ∪ non-agent-node-ids == all-node-ids, disjoint."""
        roles = self.role_node_ids()
        non = self.non_agent_node_ids()
        allids = frozenset(self.all_node_ids())
        return (
            not (roles & non)
            and (roles | non) == allids
            and len(self.node_dispositions) == len(allids)  # no duplicate node ids
        )


__all__ = [
    "Provenance",
    "AuthorityContext",
    "WorkflowRoleRequirement",
    "NonAgentDisposition",
    "WorkflowNodeDisposition",
    "AdaptationDiagnostic",
    "CompilerAdaptationResult",
]
