"""Packaging + determinism tests that don't need a built wheel.

The full isolated wheel/sdist install is exercised by
``scripts/verify_policy_workflow_compiler_distribution.py`` and CI. These tests
assert in-tree invariants: canonical import, version metadata, py.typed presence,
maturity honesty, and reproducible logical digest.
"""

from __future__ import annotations

import pathlib

import ugence_policy_workflow_compiler as u


_SRC = pathlib.Path(u.__file__).resolve().parent


def test_canonical_namespace():
    assert u.__version__ == "0.1.0"
    assert u.DISTRIBUTION_NAME == "ugence-policy-workflow-compiler"
    assert u.CANONICAL_NAMESPACE == "ugence_policy_workflow_compiler"


def test_py_typed_present():
    assert (_SRC / "py.typed").exists()


def test_maturity_is_honest():
    info = u.version_info().to_dict()
    assert info["document_extraction_implemented"] is False
    assert info["runtime_deployment_implemented"] is False
    assert info["pilot_validated"] is False
    assert info["production_certified"] is False
    # verification booleans true only because gates pass in this build
    assert info["structured_policy_pack_implemented"] is True
    assert info["deterministic_compilation_verified"] is True
    assert info["procurement_reference_equivalence_verified"] is True


def test_reproducible_logical_digest():
    from ugence_policy_workflow_compiler.api import compile_policy_pack
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )

    pack = build_procurement_policy_pack()
    appr = build_procurement_approval_fixture(pack)
    a = compile_policy_pack(pack, appr)
    b = compile_policy_pack(pack, appr)
    assert a.logical_digest == b.logical_digest
    assert a.logical_digest.startswith("sha256:")


def test_package_and_write_roundtrip(tmp_path):
    from ugence_policy_workflow_compiler.api import compile_policy_pack
    from ugence_policy_workflow_compiler.serialization import package_io
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )

    pack = build_procurement_policy_pack()
    appr = build_procurement_approval_fixture(pack)
    result = compile_policy_pack(pack, appr)
    out = package_io.write_package(result.compiled_package, tmp_path / "pkg")
    files = package_io.read_package_files(out)
    for name in (
        "manifest.json", "policy_pack.json", "workflow_ir.json",
        "capability_manifest.json", "assurance_manifest.json", "coverage_matrix.json",
        "audit_schema.json", "approval_record.json", "validation_report.json",
        "structural_digest.json",
    ):
        assert name in files, name
    assert files["manifest.json"]["structural_digest"] == result.logical_digest
