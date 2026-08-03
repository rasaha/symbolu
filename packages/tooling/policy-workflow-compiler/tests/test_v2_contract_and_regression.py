"""Contract-version safety and P1 regression for the additive workflow_ir.v2."""

from __future__ import annotations

import pytest

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import (
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V2,
    compile_workflow_v2,
    enrich_workflow,
)
from ugence_policy_workflow_compiler.version import DISTRIBUTION_VERSION, version_info

# The exact v1 *release* structural digest of the procurement reference. Pinned so
# a change to the v1 emission path (or the distribution version, which feeds the v1
# release digest) is caught immediately. P2 must never move this value.
_PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
# The v1 IR-only digest (WorkflowIR.logical_digest over ordered nodes+edges), which
# v2 embeds as base_ir_digest. Also pinned for regression.
_PINNED_V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"


def _pack():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def test_distribution_version_unchanged_preserves_v1_digest():
    assert DISTRIBUTION_VERSION == "0.1.0"
    pack, appr = _pack()
    result = api.compile_policy_pack(pack, appr)
    assert result.success
    assert result.logical_digest == _PINNED_V1_RELEASE_DIGEST
    assert result.workflow_ir.logical_digest() == _PINNED_V1_IR_DIGEST
    assert result.workflow_ir.ir_version == WORKFLOW_IR_V1


def test_product_version_bumped_to_p2():
    assert version_info().product_version == "0.2.0"


def test_supported_contract_versions():
    assert api.SUPPORTED_WORKFLOW_IR_VERSIONS == (WORKFLOW_IR_V1, WORKFLOW_IR_V2)


def test_v2_is_explicitly_labeled_and_never_mislabeled_as_v1():
    pack, appr = _pack()
    v2 = compile_workflow_v2(pack, appr, require_approval=True)
    assert v2.ir_version == WORKFLOW_IR_V2
    assert v2.contract_version == WORKFLOW_IR_V2
    # the embedded base graph keeps its own v1 label
    assert v2.base_ir.ir_version == WORKFLOW_IR_V1


def test_v2_embeds_byte_stable_v1_graph():
    pack, appr = _pack()
    v2 = compile_workflow_v2(pack, appr, require_approval=True)
    assert v2.base_ir_digest == v2.base_ir.logical_digest()
    assert v2.base_ir_digest == _PINNED_V1_IR_DIGEST


def test_all_p1_public_names_preserved():
    required = {
        "PolicyPack", "WorkflowIR", "WorkflowNode", "WorkflowEdge", "NodeKind", "EdgeKind",
        "GovernedWorkflowCompiler", "CompilationResult", "CompiledReleasePackage",
        "ReleaseManifest", "compile_policy_pack", "PolicyPackValidator", "ValidationReport",
        "Severity", "validate_policy_pack", "CapabilityRegistry", "verify_compiled_package",
        "diff_policy_packs", "version_info", "VersionInfo",
    }
    assert required <= set(api.__all__)


def test_maturity_flags_are_honest():
    vi = version_info().to_dict()
    for k in ("workflow_ir_v2_supported", "semantic_node_enrichment_implemented",
              "capability_requirement_extraction_implemented", "typed_contract_references_implemented",
              "dependency_semantics_implemented", "authority_semantics_implemented",
              "human_review_semantics_implemented", "policy_provenance_implemented",
              "release_validation_implemented", "deterministic_replay_verified"):
        assert vi[k] is True, k
    for k in ("awc_adapter_updated", "agent_eligibility_implemented", "agent_ranking_implemented",
              "team_composition_implemented", "runtime_execution_implemented",
              "action_authorization_implemented", "enterprise_policy_evaluation_implemented",
              "pilot_validated", "production_certified"):
        assert vi[k] is False, k
