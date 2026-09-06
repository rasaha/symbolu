"""PWC-P3B — conformance of emitted bindings against the capability registry.

P3B checks what v2 already emits; it emits nothing itself. Each refusal below is
exercised by perturbing a valid artifact, because a conformance check that never
fires is indistinguishable from one that is not wired up.
"""

from __future__ import annotations

import pytest

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import build_approval_record
from ugence_policy_workflow_compiler.compiler.capability_registry import DEFAULT_REGISTRY
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.semantics.contracts import (
    CapabilityRequirementSource,
    RequirementLevel,
    ResolutionStatus,
)
from ugence_policy_workflow_compiler.validation.binding_conformance import (
    BindingConformanceCode,
    check_binding_conformance,
)
from ugence_policy_workflow_compiler.validation.release_validator import (
    ReleaseValidationState,
)

PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


def _v2():
    pack = build_procurement_policy_pack()
    return compile_workflow_v2(pack, build_procurement_approval_fixture(pack))


def _codes(ir_v2):
    return {finding[0] for finding in check_binding_conformance(ir_v2)}


def _perturb_requirement(ir_v2, node_predicate, **updates):
    """Rebuild the artifact with one node's first requirement altered."""
    semantics = []
    for sem in ir_v2.node_semantics:
        node = next(n for n in ir_v2.base_ir.nodes if n.node_id == sem.node_id)
        if node_predicate(node, sem) and sem.required_capability_refs:
            first = sem.required_capability_refs[0].model_copy(update=updates)
            sem = sem.model_copy(
                update={
                    "required_capability_refs": (first,)
                    + tuple(sem.required_capability_refs[1:])
                }
            )
        semantics.append(sem)
    return ir_v2.model_copy(update={"node_semantics": tuple(semantics)})


def _canonical(node, sem):
    return bool(sem.required_capability_refs) and (
        sem.required_capability_refs[0].source
        is CapabilityRequirementSource.CAPABILITY_OWNER_MAPPING
    )


def _authoritative_canonical(node, sem):
    return _canonical(node, sem) and node.disposition.value == "AUTHORITATIVE"


# -- the reference artifacts conform ------------------------------------------


def test_the_procurement_reference_conforms():
    assert check_binding_conformance(_v2()) == ()


def test_the_ai_hiring_reference_conforms():
    from ugence_policy_workflow_compiler.reference.ai_hiring import (
        build_ai_hiring_policy_pack,
    )

    pack = build_ai_hiring_policy_pack()
    approval = build_approval_record(
        approval_id="approval-1",
        pack=pack,
        reviewer_id="reviewer-1",
        reviewer_role="hiring_manager",
        is_fixture=True,
    )
    assert check_binding_conformance(compile_workflow_v2(pack, approval)) == ()


def test_a_functional_capability_is_not_checked_against_the_registry():
    # `evidence_extraction` is a functional capability, deliberately not a registry
    # entry: the registry describes authority, not work. Checking it there would
    # fail every valid artifact.
    ir_v2 = _v2()
    functional = [
        requirement
        for sem in ir_v2.node_semantics
        for requirement in sem.required_capability_refs
        if requirement.source is CapabilityRequirementSource.NODE_KIND_MAPPING
    ]
    assert functional, "the reference must exercise the functional mapping"
    registry_ids = {d.capability_id.value for d in DEFAULT_REGISTRY.definitions()}
    assert functional[0].capability_id not in registry_ids
    assert check_binding_conformance(ir_v2) == ()


# -- each refusal fires --------------------------------------------------------


def test_an_unknown_canonical_capability_is_refused():
    perturbed = _perturb_requirement(_v2(), _canonical, capability_id="NOT_A_CAPABILITY")
    assert BindingConformanceCode.UNKNOWN_CAPABILITY_REF in _codes(perturbed)


def test_advice_may_never_decide():
    # An advisory capability bound to an authoritative node is the boundary the
    # whole product exists to keep.
    perturbed = _perturb_requirement(
        _v2(), _authoritative_canonical, capability_id="TAP"
    )
    assert (
        BindingConformanceCode.ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE
        in _codes(perturbed)
    )


def test_an_authority_may_not_be_optional():
    perturbed = _perturb_requirement(
        _v2(), _authoritative_canonical, requirement_level=RequirementLevel.OPTIONAL
    )
    codes = _codes(perturbed)
    assert BindingConformanceCode.AUTHORITATIVE_CAPABILITY_MARKED_OPTIONAL in codes


def test_a_mandatory_capability_may_not_be_marked_optional():
    perturbed = _perturb_requirement(
        _v2(), _canonical, requirement_level=RequirementLevel.OPTIONAL
    )
    assert BindingConformanceCode.MANDATORY_CAPABILITY_MARKED_OPTIONAL in _codes(
        perturbed
    )


def test_an_unresolved_required_binding_is_refused():
    perturbed = _perturb_requirement(
        _v2(), _canonical, resolution=ResolutionStatus.UNKNOWN
    )
    assert BindingConformanceCode.UNRESOLVED_CAPABILITY_BINDING in _codes(perturbed)


def test_a_contract_target_that_disagrees_with_the_registry_is_refused():
    ir_v2 = _v2()
    nodes = []
    for node in ir_v2.base_ir.nodes:
        if node.public_contract_target:
            node = node.model_copy(update={"public_contract_target": "some.other.api"})
        nodes.append(node)
    perturbed = ir_v2.model_copy(
        update={"base_ir": ir_v2.base_ir.model_copy(update={"nodes": tuple(nodes)})}
    )
    assert BindingConformanceCode.CAPABILITY_CONTRACT_TARGET_MISMATCH in _codes(
        perturbed
    )


# -- wiring into release validation -------------------------------------------


def test_release_validation_reports_conformance():
    result = api.validate_compiled_release(_v2())
    assert result.state is ReleaseValidationState.VALID
    assert result.binding_ok is True


def test_an_authority_binding_failure_can_never_be_a_warning():
    perturbed = _perturb_requirement(
        _v2(), _authoritative_canonical, capability_id="TAP"
    )
    result = api.validate_compiled_release(perturbed)
    assert result.binding_ok is False
    assert result.state is not ReleaseValidationState.VALID
    assert result.state is not ReleaseValidationState.VALID_WITH_WARNINGS
    offending = [
        d
        for d in result.diagnostics
        if d.code == BindingConformanceCode.ADVISORY_CAPABILITY_ON_AUTHORITATIVE_NODE
    ]
    assert offending and offending[0].severity == "FATAL"


# -- boundary and determinism --------------------------------------------------


def test_conformance_imports_no_provider():
    import pathlib
    import re

    module = (
        pathlib.Path(__file__).resolve().parent.parent
        / "src"
        / "ugence_policy_workflow_compiler"
        / "validation"
        / "binding_conformance.py"
    )
    text = module.read_text()
    assert not re.search(r"import\s+ugence_(tap|decision|actiongate|action_clearance)", text)


def test_conformance_is_deterministic():
    ir_v2 = _v2()
    assert check_binding_conformance(ir_v2) == check_binding_conformance(ir_v2)


def test_p3b_moves_no_digest():
    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    assert api.compile_policy_pack(pack, approval).logical_digest == PINNED_V1_RELEASE_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_maturity_reports_p3b():
    info = api.version_info().to_dict()
    assert info["binding_conformance_validation_implemented"] is True
    # P3B validates; it never binds a provider or executes anything.
    for never in ("runtime_deployment_implemented", "runtime_execution_implemented",
                  "action_authorization_implemented"):
        assert info[never] is False, never
