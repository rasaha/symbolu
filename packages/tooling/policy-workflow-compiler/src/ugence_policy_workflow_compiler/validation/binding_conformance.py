"""PWC-P3B — conformance of emitted bindings against the capability registry.

`workflow_ir.v2` already **emits** declarative capability binding: a
`CapabilityRequirement` per role-relevant node and typed `DataContractRef`s, each
provenance-backed. What it never did was check those emissions against the registry
that defines what each capability actually is. Release validation checked only that
requirements were not duplicated.

P3B is that check, and only that check. It is conformance validation, not a second
emission path: nothing here creates a requirement, changes one, or infers one. It
compares what the compiler emitted with what the registry says, and refuses a
disagreement.

**The boundary is unchanged.** The registry resolves capability targets from
metadata alone; this module reads the same metadata. It imports no provider, calls
nothing, and cannot tell whether a capability is installed — only whether the
workflow's own claims about it are internally coherent.

The authority checks are the reason this phase exists. A binding that lets an
advisory capability own an authoritative node, or marks an authoritative capability
optional, is an authority-boundary failure, and those are never downgraded to
warnings.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..compiler.capability_registry import (
    DEFAULT_REGISTRY,
    CapabilityRegistry,
    UnknownCapabilityError,
)
from ..compiler.workflow_ir import WorkflowNode
from ..semantics.contracts import (
    CapabilityRequirementSource,
    RequirementLevel,
    ResolutionStatus,
)


class BindingConformanceCode:
    """Codes this module raises. Mirrored into `ReleaseValidationCode`."""

    UNKNOWN_CAPABILITY_REF = "UNKNOWN_CAPABILITY_REF"
    ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE = "ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE"
    AUTHORITATIVE_CAPABILITY_MARKED_OPTIONAL = "AUTHORITATIVE_CAPABILITY_MARKED_OPTIONAL"
    MANDATORY_CAPABILITY_MARKED_OPTIONAL = "MANDATORY_CAPABILITY_MARKED_OPTIONAL"
    CAPABILITY_CONTRACT_TARGET_MISMATCH = "CAPABILITY_CONTRACT_TARGET_MISMATCH"
    UNRESOLVED_CAPABILITY_BINDING = "UNRESOLVED_CAPABILITY_BINDING"


#: (code, severity, message, node_id) — severity is the P1 vocabulary.
Finding = Tuple[str, str, str, str]

_ERROR = "ERROR"
_FATAL = "FATAL"


#: Requirement sources that name a **canonical governance capability** — one the
#: registry defines, with an authority disposition to conform to.
_CANONICAL_SOURCES = frozenset({
    CapabilityRequirementSource.CAPABILITY_OWNER_MAPPING,
    CapabilityRequirementSource.EXPLICIT_POLICY,
})

#: Requirement sources that name a **functional** capability instead — what a node
#: does, not who holds authority for it. `EVIDENCE_REQUIREMENT -> evidence_extraction`
#: is the shipped example. These are deliberately not registry capabilities: they
#: describe work, and the registry describes authority. Checking them against the
#: registry would fail every valid artifact, which is precisely the false-failure
#: mode conformance validation must avoid.
_FUNCTIONAL_SOURCES = frozenset({
    CapabilityRequirementSource.NODE_KIND_MAPPING,
    CapabilityRequirementSource.CONTRACT_DERIVATION,
})


def _requirement_findings(
    node: WorkflowNode, requirement, registry: CapabilityRegistry
) -> List[Finding]:
    findings: List[Finding] = []
    node_id = node.node_id

    if requirement.source in _FUNCTIONAL_SOURCES:
        # A functional capability has no registry entry to conform to. The one
        # thing that still holds is resolution: a REQUIRED binding that resolved to
        # nothing cannot be satisfied, whatever kind of capability it names.
        return _resolution_findings(requirement, node_id)

    # 1. A canonical capability must be one the registry defines. An emitted
    #    requirement naming an unknown one is a claim about nothing.
    try:
        definition = registry.get(type(node.owning_capability)(requirement.capability_id))
    except (UnknownCapabilityError, ValueError):
        findings.append((
            BindingConformanceCode.UNKNOWN_CAPABILITY_REF, _ERROR,
            f"capability requirement {requirement.capability_id!r} is not defined in "
            f"the capability registry",
            node_id,
        ))
        return findings

    disposition = definition.disposition.value
    level = requirement.requirement_level

    # 2. An advisory capability may not own an authoritative node. This is the
    #    authority boundary the whole product exists to keep: advice never decides.
    if node.disposition.value == "AUTHORITATIVE" and disposition == "ADVISORY":
        findings.append((
            BindingConformanceCode.ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE, _FATAL,
            f"advisory capability {requirement.capability_id!r} is bound to an "
            f"authoritative node; advice may inform a decision, never make one",
            node_id,
        ))

    # 3. An authoritative capability cannot be optional at an authoritative node:
    #    "the authority may or may not be consulted" is not a governed workflow.
    if (node.disposition.value == "AUTHORITATIVE"
            and disposition == "AUTHORITATIVE"
            and level is RequirementLevel.OPTIONAL):
        findings.append((
            BindingConformanceCode.AUTHORITATIVE_CAPABILITY_MARKED_OPTIONAL, _FATAL,
            f"authoritative capability {requirement.capability_id!r} is bound as "
            f"OPTIONAL at an authoritative node",
            node_id,
        ))

    # 4. A capability the registry marks non-optional may not be emitted OPTIONAL.
    if not definition.optional and level is RequirementLevel.OPTIONAL:
        findings.append((
            BindingConformanceCode.MANDATORY_CAPABILITY_MARKED_OPTIONAL, _ERROR,
            f"capability {requirement.capability_id!r} is not optional in the "
            f"registry but is bound as OPTIONAL",
            node_id,
        ))

    # 5. Where the node names a public contract target, it must be the registry's
    #    for the capability it binds — otherwise the workflow points one way and
    #    the registry another.
    if (node.public_contract_target
            and requirement.capability_id == node.owning_capability.value
            and node.public_contract_target != definition.public_contract):
        findings.append((
            BindingConformanceCode.CAPABILITY_CONTRACT_TARGET_MISMATCH, _ERROR,
            f"node targets {node.public_contract_target!r} but the registry gives "
            f"{definition.public_contract!r} for {requirement.capability_id!r}",
            node_id,
        ))

    # 6. A REQUIRED binding that resolved to nothing is unusable. An unresolved
    #    OPTIONAL binding is honest; an unresolved REQUIRED one is a gap.
    findings.extend(_resolution_findings(requirement, node_id))

    return findings


def _resolution_findings(requirement, node_id: str) -> List[Finding]:
    """The one check that applies to every requirement, canonical or functional."""
    if requirement.requirement_level is not RequirementLevel.REQUIRED:
        return []
    if (requirement.source is CapabilityRequirementSource.UNRESOLVED
            or requirement.resolution is ResolutionStatus.UNKNOWN):
        return [(
            BindingConformanceCode.UNRESOLVED_CAPABILITY_BINDING, _ERROR,
            f"required capability {requirement.capability_id!r} is unresolved; a "
            f"required binding that resolves to nothing cannot be satisfied",
            node_id,
        )]
    return []


def check_binding_conformance(
    ir_v2, registry: Optional[CapabilityRegistry] = None
) -> Tuple[Finding, ...]:
    """Check every emitted capability binding against the registry.

    Deterministic and offline. Returns findings in node order, then in the order the
    requirements were emitted, so the result is a pure function of the artifact.
    """
    registry = registry or DEFAULT_REGISTRY
    by_id: Dict[str, WorkflowNode] = {n.node_id: n for n in ir_v2.base_ir.nodes}
    findings: List[Finding] = []
    for semantics in ir_v2.node_semantics:
        node = by_id.get(semantics.node_id)
        if node is None:
            # A semantics entry with no node is a structural failure the release
            # validator already reports; nothing to check against here.
            continue
        for requirement in (
            tuple(semantics.required_capability_refs)
            + tuple(semantics.optional_capability_refs)
        ):
            findings.extend(_requirement_findings(node, requirement, registry))
    return tuple(findings)


__all__ = ["check_binding_conformance", "BindingConformanceCode"]
