"""Strict, deterministic validation of an enriched ``workflow_ir.v2`` release.

Validates structural, semantic, authority, contract, dependency, provenance and
digest integrity. An authority-boundary failure or a digest mismatch can never be
downgraded to ``VALID_WITH_WARNINGS``.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..models.common import CompilerModel
from ..semantics.contracts import (
    RoleRelevance,
    SUPPORTED_WORKFLOW_IR_VERSIONS,
    WORKFLOW_IR_V2,
)
from ..semantics.models import SemanticDiagnostic, WorkflowIRv2


class ReleaseValidationState(str, Enum):
    VALID = "VALID"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    INVALID = "INVALID"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


class ReleaseValidationCode(str, Enum):
    UNKNOWN_CONTRACT_VERSION = "UNKNOWN_CONTRACT_VERSION"
    UNSUPPORTED_NODE_KIND = "UNSUPPORTED_NODE_KIND"
    UNSUPPORTED_EDGE_KIND = "UNSUPPORTED_EDGE_KIND"
    MISSING_NODE_SEMANTICS = "MISSING_NODE_SEMANTICS"
    MISSING_AUTHORITY_DISPOSITION = "MISSING_AUTHORITY_DISPOSITION"
    CONFLICTING_AUTHORITY_DISPOSITION = "CONFLICTING_AUTHORITY_DISPOSITION"
    MISSING_CAPABILITY_REQUIREMENT = "MISSING_CAPABILITY_REQUIREMENT"
    UNKNOWN_CAPABILITY_REF = "UNKNOWN_CAPABILITY_REF"
    DUPLICATE_CAPABILITY_REQUIREMENT = "DUPLICATE_CAPABILITY_REQUIREMENT"
    MISSING_INPUT_CONTRACT = "MISSING_INPUT_CONTRACT"
    MISSING_OUTPUT_CONTRACT = "MISSING_OUTPUT_CONTRACT"
    UNRESOLVED_CONTRACT_REF = "UNRESOLVED_CONTRACT_REF"
    CONTRACT_VERSION_MISMATCH = "CONTRACT_VERSION_MISMATCH"
    DANGLING_EDGE = "DANGLING_EDGE"
    INVALID_DEPENDENCY = "INVALID_DEPENDENCY"
    UNSUPPORTED_CYCLE = "UNSUPPORTED_CYCLE"
    BROKEN_PROVENANCE = "BROKEN_PROVENANCE"
    CONFLICTING_POLICY_SOURCE = "CONFLICTING_POLICY_SOURCE"
    INCOMPLETE_ROLE_SEMANTICS = "INCOMPLETE_ROLE_SEMANTICS"
    AI_ELIGIBLE_ON_AUTHORITATIVE_NODE = "AI_ELIGIBLE_ON_AUTHORITATIVE_NODE"
    DUPLICATE_NODE_ID = "DUPLICATE_NODE_ID"
    DUPLICATE_EDGE_ID = "DUPLICATE_EDGE_ID"
    BASE_DIGEST_MISMATCH = "BASE_DIGEST_MISMATCH"
    WORKFLOW_FINGERPRINT_MISMATCH = "WORKFLOW_FINGERPRINT_MISMATCH"


# Severity values mirror the P1 validation vocabulary.
_INFO, _WARNING, _ERROR, _FATAL = "INFO", "WARNING", "ERROR", "FATAL"
_BLOCKING = {"REVIEW_REQUIRED", _ERROR, _FATAL}
#: Codes that indicate an authority-boundary or digest-integrity failure — these
#: can never be reduced to warnings.
_INTEGRITY_CODES = {
    ReleaseValidationCode.BASE_DIGEST_MISMATCH.value,
    ReleaseValidationCode.WORKFLOW_FINGERPRINT_MISMATCH.value,
}
_AUTHORITY_CODES = {
    ReleaseValidationCode.AI_ELIGIBLE_ON_AUTHORITATIVE_NODE.value,
    ReleaseValidationCode.CONFLICTING_AUTHORITY_DISPOSITION.value,
    ReleaseValidationCode.MISSING_AUTHORITY_DISPOSITION.value,
}


class ReleaseValidationResult(CompilerModel):
    state: ReleaseValidationState
    contract_version: str = WORKFLOW_IR_V2
    workflow_identity: str = ""
    structural_ok: bool = True
    semantic_ok: bool = True
    authority_ok: bool = True
    contract_ok: bool = True
    dependency_ok: bool = True
    provenance_ok: bool = True
    digest_ok: bool = True
    diagnostics: Tuple[SemanticDiagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state in (ReleaseValidationState.VALID,
                              ReleaseValidationState.VALID_WITH_WARNINGS)


class CompiledReleaseValidator:
    """Offline, deterministic validator for a ``workflow_ir.v2`` artifact."""

    def validate(self, ir_v2: WorkflowIRv2) -> ReleaseValidationResult:
        wid = f"{ir_v2.policy_pack_id}@{ir_v2.policy_pack_version}"
        diags: List[SemanticDiagnostic] = []

        def add(code: ReleaseValidationCode, severity: str, message: str,
                node_id: str = "", edge_id: str = "") -> None:
            diags.append(SemanticDiagnostic(
                code=code.value, severity=severity, message=message,
                workflow_identity=wid, node_id=node_id, edge_id=edge_id,
                contract_version=ir_v2.contract_version))

        # -- version --
        version_ok = ir_v2.ir_version in SUPPORTED_WORKFLOW_IR_VERSIONS
        if not version_ok:
            add(ReleaseValidationCode.UNKNOWN_CONTRACT_VERSION, _FATAL,
                f"unsupported contract version {ir_v2.ir_version!r}")
            return ReleaseValidationResult(
                state=ReleaseValidationState.UNSUPPORTED_VERSION, workflow_identity=wid,
                structural_ok=False, diagnostics=tuple(diags),
                contract_version=ir_v2.contract_version)

        base = ir_v2.base_ir
        nodes = base.nodes
        by_id = {n.node_id: n for n in nodes}
        sem_by_id: Dict[str, object] = {s.node_id: s for s in ir_v2.node_semantics}

        # -- structural integrity --
        structural_ok = True
        seen_nodes: set = set()
        for n in nodes:
            if n.node_id in seen_nodes:
                add(ReleaseValidationCode.DUPLICATE_NODE_ID, _ERROR,
                    "duplicate node id", node_id=n.node_id)
                structural_ok = False
            seen_nodes.add(n.node_id)
        seen_edges: set = set()
        for e in base.edges:
            if e.edge_id in seen_edges:
                add(ReleaseValidationCode.DUPLICATE_EDGE_ID, _ERROR,
                    "duplicate edge id", edge_id=e.edge_id)
                structural_ok = False
            seen_edges.add(e.edge_id)
            if e.source_id not in by_id or e.target_id not in by_id:
                add(ReleaseValidationCode.DANGLING_EDGE, _ERROR,
                    "edge endpoint does not resolve to a node", edge_id=e.edge_id)
                structural_ok = False

        # -- semantic + authority integrity --
        semantic_ok = True
        authority_ok = True
        for n in nodes:
            sem = sem_by_id.get(n.node_id)
            if sem is None:
                add(ReleaseValidationCode.MISSING_NODE_SEMANTICS, _ERROR,
                    "node has no semantics", node_id=n.node_id)
                semantic_ok = False
                continue
            if not sem.authority_disposition:
                add(ReleaseValidationCode.MISSING_AUTHORITY_DISPOSITION, _ERROR,
                    "node semantics missing authority disposition", node_id=n.node_id)
                authority_ok = False
            if sem.authority_disposition != n.disposition.value:
                add(ReleaseValidationCode.CONFLICTING_AUTHORITY_DISPOSITION, _ERROR,
                    "semantics authority disposition disagrees with the v1 node",
                    node_id=n.node_id)
                authority_ok = False
            # fail closed: an authoritative node may never be agent-eligible.
            if (n.disposition.value == "AUTHORITATIVE"
                    and sem.role_relevance is RoleRelevance.ADVISORY_AGENT_ELIGIBLE):
                add(ReleaseValidationCode.AI_ELIGIBLE_ON_AUTHORITATIVE_NODE, _FATAL,
                    "authoritative node classified as advisory-agent-eligible",
                    node_id=n.node_id)
                authority_ok = False
            # duplicate capability requirements
            cap_ids = [c.capability_id for c in sem.required_capability_refs]
            if len(cap_ids) != len(set(cap_ids)):
                add(ReleaseValidationCode.DUPLICATE_CAPABILITY_REQUIREMENT, _ERROR,
                    "duplicate capability requirement", node_id=n.node_id)
                semantic_ok = False

        # -- contract integrity --
        contract_ok = True
        for sem in ir_v2.node_semantics:
            for req in sem.required_input_contract_refs:
                if not req.contract_ref.contract_id:
                    add(ReleaseValidationCode.UNRESOLVED_CONTRACT_REF, _ERROR,
                        "input contract ref has no contract id", node_id=sem.node_id)
                    contract_ok = False
                if req.producer_node_id and req.producer_node_id not in by_id:
                    add(ReleaseValidationCode.MISSING_INPUT_CONTRACT, _ERROR,
                        "input producer node does not resolve", node_id=sem.node_id)
                    contract_ok = False
            for out in sem.produced_output_contract_refs:
                if not out.contract_ref.contract_id:
                    add(ReleaseValidationCode.UNRESOLVED_CONTRACT_REF, _ERROR,
                        "output contract ref has no contract id", node_id=sem.node_id)
                    contract_ok = False
                for consumer in out.consumer_node_ids:
                    if consumer not in by_id:
                        add(ReleaseValidationCode.MISSING_OUTPUT_CONTRACT, _ERROR,
                            "output consumer node does not resolve", node_id=sem.node_id)
                        contract_ok = False

        # -- dependency integrity --
        dependency_ok = True
        for dep in ir_v2.dependency_semantics:
            if dep.source_node_id not in by_id or dep.target_node_id not in by_id:
                add(ReleaseValidationCode.INVALID_DEPENDENCY, _ERROR,
                    "dependency endpoint does not resolve", edge_id=dep.edge_id)
                dependency_ok = False

        # -- provenance integrity --
        provenance_ok = True
        for sem in ir_v2.node_semantics:
            p = sem.provenance
            if not p.compiler_rule or not p.derivation_class:
                add(ReleaseValidationCode.BROKEN_PROVENANCE, _ERROR,
                    "node provenance missing rule/derivation", node_id=sem.node_id)
                provenance_ok = False
            if p.source_policy_id and p.source_policy_id != ir_v2.policy_pack_id:
                add(ReleaseValidationCode.CONFLICTING_POLICY_SOURCE, _ERROR,
                    "node provenance policy id disagrees with the release",
                    node_id=sem.node_id)
                provenance_ok = False

        # -- digest integrity --
        digest_ok = True
        if ir_v2.base_ir_digest != base.logical_digest():
            add(ReleaseValidationCode.BASE_DIGEST_MISMATCH, _FATAL,
                "recorded base_ir_digest does not match the embedded v1 graph")
            digest_ok = False
        expected_fp = ir_v2.logical_digest()
        if ir_v2.workflow_fingerprint and ir_v2.workflow_fingerprint != expected_fp:
            add(ReleaseValidationCode.WORKFLOW_FINGERPRINT_MISMATCH, _FATAL,
                "recorded workflow_fingerprint does not match recomputation")
            digest_ok = False

        # -- state resolution --
        codes = {d.code for d in diags if d.severity in _BLOCKING}
        state = self._state(diags, codes)
        return ReleaseValidationResult(
            state=state, workflow_identity=wid, contract_version=ir_v2.contract_version,
            structural_ok=structural_ok, semantic_ok=semantic_ok, authority_ok=authority_ok,
            contract_ok=contract_ok, dependency_ok=dependency_ok,
            provenance_ok=provenance_ok, digest_ok=digest_ok, diagnostics=tuple(diags))

    @staticmethod
    def _state(diags: List[SemanticDiagnostic], blocking_codes: set) -> ReleaseValidationState:
        if blocking_codes & _INTEGRITY_CODES:
            return ReleaseValidationState.INTEGRITY_FAILURE
        if blocking_codes:  # any other blocking failure (incl. authority) => INVALID
            return ReleaseValidationState.INVALID
        if any(d.severity == _WARNING for d in diags):
            return ReleaseValidationState.VALID_WITH_WARNINGS
        return ReleaseValidationState.VALID


def validate_compiled_release(ir_v2: WorkflowIRv2) -> ReleaseValidationResult:
    """Convenience wrapper around :class:`CompiledReleaseValidator`."""
    return CompiledReleaseValidator().validate(ir_v2)


__all__ = [
    "ReleaseValidationState",
    "ReleaseValidationCode",
    "ReleaseValidationResult",
    "CompiledReleaseValidator",
    "validate_compiled_release",
]
