"""Deterministic role dependency + interface graph over AI-agent-eligible roles.

Dependencies are derived ONLY from typed input/output contracts on the P1
`WorkflowRoleRequirement`s (an upstream role's produced output contract consumed by
a downstream role's required input contract), P1 role source-node identities, and an
optional explicit enterprise composition overlay. No LLM inference; no workflow
semantics invented from node names. Unsupported/illegal references fail closed.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from .canonical import AwcModel
from .fingerprint import stamp_fingerprint
from .version import COMPOSITION_CONTRACT_VERSION
from .workflow import Provenance, WorkflowRoleRequirement


class RoleInterfaceRequirement(AwcModel):
    role_id: str
    required_input_contracts: Tuple[str, ...] = ()
    produced_output_contracts: Tuple[str, ...] = ()


class RoleDependency(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    upstream_role_id: str
    downstream_role_id: str
    edge_kind: str = "DATA_CONTRACT"
    required_output_contract: str
    required_input_contract: str
    ordering_semantics: str = "upstream_before_downstream"
    data_classification: str = ""
    authority_context: str = ""
    provenance: Provenance
    dependency_fingerprint: str = ""


class RoleDependencyGraph(AwcModel):
    composition_contract_version: str = COMPOSITION_CONTRACT_VERSION
    roles: Tuple[str, ...] = ()
    interface_requirements: Tuple[RoleInterfaceRequirement, ...] = ()
    dependencies: Tuple[RoleDependency, ...] = ()
    has_cycle: bool = False
    diagnostics: Tuple[str, ...] = ()
    graph_fingerprint: str = ""

    def edges_for(self, role_id: str) -> Tuple[RoleDependency, ...]:
        return tuple(d for d in self.dependencies
                     if d.upstream_role_id == role_id or d.downstream_role_id == role_id)


def _detect_cycle(role_ids: List[str], deps: List[RoleDependency]) -> bool:
    adj: Dict[str, List[str]] = {r: [] for r in role_ids}
    for d in deps:
        adj.setdefault(d.upstream_role_id, []).append(d.downstream_role_id)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {r: WHITE for r in role_ids}

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in adj.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                return True
            if color.get(nxt, WHITE) == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[r] == WHITE and visit(r) for r in role_ids)


def build_role_dependency_graph(
    roles: Tuple[WorkflowRoleRequirement, ...],
    overlay: Optional[Mapping[str, Mapping]] = None,
) -> RoleDependencyGraph:
    """Build the deterministic dependency graph from typed I/O contracts (+ overlay)."""
    roles = tuple(sorted(roles, key=lambda r: r.role_id))
    role_ids = [r.role_id for r in roles]
    by_id = {r.role_id: r for r in roles}
    diagnostics: List[str] = []

    interfaces = tuple(
        RoleInterfaceRequirement(role_id=r.role_id,
                                 required_input_contracts=r.input_contract_refs,
                                 produced_output_contracts=r.output_contract_refs)
        for r in roles)

    deps: List[RoleDependency] = []
    for up in roles:
        for down in roles:
            if up.role_id == down.role_id:
                continue
            shared = set(up.output_contract_refs) & set(down.input_contract_refs)
            for contract in sorted(shared):
                d = RoleDependency(
                    upstream_role_id=up.role_id, downstream_role_id=down.role_id,
                    required_output_contract=contract, required_input_contract=contract,
                    data_classification=down.data_classification,
                    authority_context=down.authority_context.owning_capability.value,
                    provenance=Provenance(source_kind="p1_role_contracts", synthetic=up.provenance.synthetic,
                                          source_ref=f"{up.role_id}->{down.role_id}:{contract}"))
                deps.append(stamp_fingerprint(d, "dependency_fingerprint"))

    # explicit overlay edges (data-only), validated against known roles
    for edge in (overlay or {}).get("dependencies", []) if overlay else []:
        u, dn = edge.get("upstream_role_id"), edge.get("downstream_role_id")
        if u not in by_id or dn not in by_id:
            diagnostics.append(f"overlay dependency references unknown role: {u!r}->{dn!r}")
            continue
        contract = str(edge.get("contract", ""))
        d = RoleDependency(
            upstream_role_id=u, downstream_role_id=dn, edge_kind="OVERLAY",
            required_output_contract=contract, required_input_contract=contract,
            provenance=Provenance(source_kind="composition_overlay", synthetic=True,
                                  source_ref=f"{u}->{dn}"))
        deps.append(stamp_fingerprint(d, "dependency_fingerprint"))

    deps.sort(key=lambda d: (d.upstream_role_id, d.downstream_role_id,
                             d.required_output_contract))
    has_cycle = _detect_cycle(role_ids, deps)
    if has_cycle:
        diagnostics.append("data-contract dependency cycle detected among AI-agent roles")

    graph = RoleDependencyGraph(
        roles=tuple(role_ids), interface_requirements=interfaces,
        dependencies=tuple(deps), has_cycle=has_cycle, diagnostics=tuple(diagnostics))
    return stamp_fingerprint(graph, "graph_fingerprint")


__all__ = [
    "RoleInterfaceRequirement",
    "RoleDependency",
    "RoleDependencyGraph",
    "build_role_dependency_graph",
]
