"""Version-decoupling correction: the package release version is 0.2.0, while
every workflow_ir.v1 logical digest continues to commit to the FROZEN legacy
semantic identity 0.1.0. A package-version bump must never perturb a v1 digest.
"""

from __future__ import annotations

import pytest

import ugence_policy_workflow_compiler as u
import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2, enrich_workflow
from ugence_policy_workflow_compiler.version import (
    DISTRIBUTION_VERSION,
    PRODUCT_VERSION,
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION,
    WORKFLOW_IR_V2,
    WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION,
    UnsupportedContractVersion,
    digest_compiler_version_for,
    version_info,
)

# Full live pinned v1 digests (must remain byte-identical after the correction).
V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"


def _pack():
    p = build_procurement_policy_pack()
    return p, build_procurement_approval_fixture(p)


# -- version separation ----------------------------------------------------- #

def test_distribution_version_is_0_2_0():
    assert DISTRIBUTION_VERSION == "0.2.0"
    assert u.__version__ == "0.2.0"


def test_product_version_is_0_2_0():
    assert PRODUCT_VERSION == "0.2.0"
    assert version_info().product_version == "0.2.0"
    assert version_info().distribution_version == "0.2.0"


def test_v1_digest_semantic_identity_frozen_at_0_1_0():
    assert WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION == "0.1.0"
    assert digest_compiler_version_for(WORKFLOW_IR_V1) == "0.1.0"
    vi = version_info().to_dict()
    assert vi["workflow_ir_v1_digest_compiler_version"] == "0.1.0"


def test_v2_digest_semantic_identity_explicit_0_2_0():
    assert WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION == "0.2.0"
    assert digest_compiler_version_for(WORKFLOW_IR_V2) == "0.2.0"
    vi = version_info().to_dict()
    assert vi["workflow_ir_v2_digest_compiler_version"] == "0.2.0"


def test_v1_digest_identity_independent_of_package_version():
    # digest identity is a pinned constant, not the package/distribution version.
    assert digest_compiler_version_for(WORKFLOW_IR_V1) != DISTRIBUTION_VERSION


def test_unknown_contract_digest_fails_closed():
    with pytest.raises(UnsupportedContractVersion):
        digest_compiler_version_for("workflow_ir.v9")


# -- v1 byte-stability ------------------------------------------------------ #

def test_v1_release_digest_byte_identical():
    pack, appr = _pack()
    assert api.compile_policy_pack(pack, appr).logical_digest == V1_RELEASE_DIGEST


def test_v1_ir_digest_byte_identical():
    pack, appr = _pack()
    r = api.compile_policy_pack(pack, appr)
    assert r.workflow_ir.logical_digest() == V1_IR_DIGEST


def test_v1_canonical_serialization_stable():
    from ugence_policy_workflow_compiler.serialization import canonical_json
    pack, appr = _pack()
    r = api.compile_policy_pack(pack, appr)
    # canonical bytes of the v1 IR are a pure function of logical content
    a = canonical_json.dumps(canonical_json.to_canonical_obj(r.workflow_ir))
    b = canonical_json.dumps(canonical_json.to_canonical_obj(r.workflow_ir))
    assert a == b
    # and the release logical payload digest matches the recorded digest
    assert r.compiled_package.recompute_digest() == V1_RELEASE_DIGEST


def test_v1_validation_unchanged():
    pack, appr = _pack()
    r = api.compile_policy_pack(pack, appr)
    assert r.success
    assert api.verify_compiled_package(r.compiled_package).passed


def test_manifest_metadata_reports_distribution_0_2_0():
    # the on-disk manifest metadata honestly reports the building distribution,
    # while the digest stays frozen (metadata is NOT part of the logical digest).
    pack, appr = _pack()
    r = api.compile_policy_pack(pack, appr)
    assert r.compiled_package.manifest.compiler_distribution_version == "0.2.0"
    assert r.compiled_package.manifest.structural_digest == V1_RELEASE_DIGEST


# -- v2 semantic identity --------------------------------------------------- #

def test_v2_fingerprint_uses_v2_semantic_identity():
    pack, appr = _pack()
    v2 = compile_workflow_v2(pack, appr, require_approval=True)
    assert v2.compiler_version == WORKFLOW_IR_V2_DIGEST_COMPILER_VERSION == "0.2.0"
    # v2 provenance carries the v2 semantic identity, not the frozen v1 identity
    assert any(s.provenance.compiler_version == "0.2.0" for s in v2.node_semantics)


def test_v2_fingerprint_deterministic():
    pack, appr = _pack()
    a = compile_workflow_v2(pack, appr, require_approval=True).workflow_fingerprint
    b = compile_workflow_v2(pack, appr, require_approval=True).workflow_fingerprint
    assert a == b


def test_v2_embeds_frozen_v1_base_digest():
    pack, appr = _pack()
    v2 = compile_workflow_v2(pack, appr, require_approval=True)
    assert v2.base_ir_digest == V1_IR_DIGEST  # v1 identity preserved inside v2
