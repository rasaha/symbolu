"""Command-line interface.

    ugence-policy-workflow-compiler version
    ugence-policy-workflow-compiler validate <pack.json>
    ugence-policy-workflow-compiler compile  <pack.json> --approval <approval.json> [--out DIR]
    ugence-policy-workflow-compiler verify   <compiled-package-dir>
    ugence-policy-workflow-compiler diff     <old-pack.json> <new-pack.json>
    ugence-policy-workflow-compiler inspect  <compiled-package-dir>
    ugence-policy-workflow-compiler demo     procurement [--out DIR]

Also runnable as ``python -m ugence_policy_workflow_compiler``. The demo is
deterministic, offline, and credential-free.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Optional

from .api import (
    SUPPORTED_WORKFLOW_IR_VERSIONS,
    WORKFLOW_IR_V1,
    WORKFLOW_IR_V2,
    GovernedWorkflowCompiler,
    HumanApprovalRecord,
    PolicyPack,
    WorkflowIR,
    WorkflowIRv2,
    compile_workflow_v2,
    diff_policy_packs,
    enrich_workflow,
    upgrade_workflow_ir,
    validate_compiled_release,
    validate_policy_pack,
    verify_compiled_package,
    version_info,
)
from .serialization import canonical_json, package_io


def _load_pack(path: str) -> PolicyPack:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return PolicyPack.model_validate(canonical_json.loads(text))


def _load_v1_ir(path: str) -> WorkflowIR:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return WorkflowIR.model_validate(canonical_json.loads(text))


def _load_v2(path: str) -> WorkflowIRv2:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return WorkflowIRv2.model_validate(canonical_json.loads(text))


def _load_approval(path: str) -> HumanApprovalRecord:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    return HumanApprovalRecord.model_validate(canonical_json.loads(text))


def _print(obj) -> None:
    print(canonical_json.dumps_pretty(obj), end="")


def cmd_version(_args) -> int:
    _print(version_info().to_dict())
    return 0


def cmd_validate(args) -> int:
    pack = _load_pack(args.pack)
    report = validate_policy_pack(pack)
    _print({"ok": report.ok, "counts": report.counts(),
            "diagnostics": [d.model_dump(mode="python") for d in report.diagnostics]})
    return 0 if report.ok else 2


def cmd_compile(args) -> int:
    contract = getattr(args, "contract", WORKFLOW_IR_V1)
    if contract not in SUPPORTED_WORKFLOW_IR_VERSIONS:
        _print({"error": f"unsupported contract {contract!r}",
                "supported": list(SUPPORTED_WORKFLOW_IR_VERSIONS)})
        return 2
    pack = _load_pack(args.pack)
    approval = _load_approval(args.approval) if args.approval else None
    result = GovernedWorkflowCompiler().compile(
        pack, approval, require_approval=not args.no_approval
    )
    if not result.success:
        _print({"success": False, "contract": contract,
                "diagnostics": [d.model_dump(mode="python") for d in result.diagnostics]})
        return 2
    if contract == WORKFLOW_IR_V2:
        v2 = enrich_workflow(result.workflow_ir, pack, compiler_version=version_info().distribution_version)
        if args.out:
            pathlib.Path(args.out).write_text(
                canonical_json.dumps_pretty(v2.model_dump(mode="python")), encoding="utf-8")
        _print({
            "success": True, "contract": WORKFLOW_IR_V2,
            "workflow_fingerprint": v2.workflow_fingerprint,
            "base_ir_digest": v2.base_ir_digest,
            "nodes": len(v2.base_ir.nodes),
            "node_semantics": len(v2.node_semantics),
            "dependency_semantics": len(v2.dependency_semantics),
            "written_to": args.out or None,
        })
        return 0
    if args.out:
        package_io.write_package(result.compiled_package, args.out)
    _print({
        "success": True, "contract": WORKFLOW_IR_V1,
        "logical_digest": result.logical_digest,
        "nodes": len(result.workflow_ir.nodes),
        "edges": len(result.workflow_ir.edges),
        "assurance_tests": result.assurance_manifest.test_count,
        "coverage_complete": result.assurance_manifest.coverage_matrix.complete,
        "written_to": args.out or None,
    })
    return 0


def cmd_validate_release(args) -> int:
    v2 = _load_v2(args.file)
    result = validate_compiled_release(v2)
    _print({"state": result.state.value, "ok": result.ok,
            "structural_ok": result.structural_ok, "semantic_ok": result.semantic_ok,
            "authority_ok": result.authority_ok, "contract_ok": result.contract_ok,
            "dependency_ok": result.dependency_ok, "provenance_ok": result.provenance_ok,
            "digest_ok": result.digest_ok,
            "diagnostics": [d.model_dump(mode="python") for d in result.diagnostics]})
    return 0 if result.ok else 2


def cmd_inspect_semantics(args) -> int:
    v2 = _load_v2(args.file)
    _print({
        "policy_pack_id": v2.policy_pack_id,
        "contract_version": v2.ir_version,
        "node_semantics": [
            {"node_id": s.node_id, "node_kind": s.node_kind,
             "role_relevance": s.role_relevance.value,
             "semantic_purpose": s.semantic_purpose,
             "authority_disposition": s.authority_disposition,
             "canonical_capability_owner": s.canonical_capability_owner,
             "required_capabilities": [c.capability_id for c in s.required_capability_refs],
             "human_review": s.human_review_requirement.review_kind}
            for s in v2.node_semantics],
        "capability_reference_manifest": list(v2.capability_reference_manifest),
    })
    return 0


def cmd_inspect_dependencies(args) -> int:
    v2 = _load_v2(args.file)
    _print({
        "policy_pack_id": v2.policy_pack_id,
        "dependencies": [
            {"edge_id": d.edge_id, "source": d.source_node_id, "target": d.target_node_id,
             "dependency_kind": d.dependency_kind.value, "condition_ref": d.condition_ref}
            for d in v2.dependency_semantics],
    })
    return 0


def cmd_inspect_provenance(args) -> int:
    v2 = _load_v2(args.file)
    _print({
        "policy_pack_id": v2.policy_pack_id,
        "provenance_manifest": list(v2.provenance_manifest),
        "node_provenance": [
            {"node_id": s.node_id, "derivation_class": s.provenance.derivation_class.value,
             "compiler_rule": s.provenance.compiler_rule,
             "source_object_ids": list(s.provenance.source_object_ids)}
            for s in v2.node_semantics],
    })
    return 0


def cmd_compare_contracts(args) -> int:
    v1 = _load_v1_ir(args.v1_file)
    v2 = _load_v2(args.v2_file)
    _print({
        "v1_ir_version": v1.ir_version,
        "v2_ir_version": v2.ir_version,
        "v1_logical_digest": v1.logical_digest(),
        "v2_base_ir_digest": v2.base_ir_digest,
        "base_graphs_match": v1.logical_digest() == v2.base_ir_digest,
        "v2_adds": {
            "node_semantics": len(v2.node_semantics),
            "dependency_semantics": len(v2.dependency_semantics),
            "semantic_features": [f.name.value for f in v2.semantic_features if f.present],
        },
    })
    return 0


def cmd_upgrade_v1(args) -> int:
    v1 = _load_v1_ir(args.file)
    v2 = upgrade_workflow_ir(v1, compiler_version=version_info().distribution_version)
    if args.out:
        pathlib.Path(args.out).write_text(
            canonical_json.dumps_pretty(v2.model_dump(mode="python")), encoding="utf-8")
    _print({
        "upgraded": True, "from": v1.ir_version, "to": v2.ir_version,
        "base_ir_digest": v2.base_ir_digest, "workflow_fingerprint": v2.workflow_fingerprint,
        "node_semantics": len(v2.node_semantics),
        "note": "semantics absent from v1 are marked unresolved/not-applicable; none are invented",
        "written_to": args.out or None,
    })
    return 0


def cmd_verify(args) -> int:
    package = _read_compiled_package(args.package)
    if package is None:
        _print({"error": f"could not load compiled package from {args.package}"})
        return 2
    report = verify_compiled_package(package)
    _print({"passed": report.passed,
            "checks": [c.model_dump(mode="python") for c in report.checks]})
    return 0 if report.passed else 2


def cmd_diff(args) -> int:
    old = _load_pack(args.old)
    new = _load_pack(args.new)
    d = diff_policy_packs(old, new)
    _print(d.model_dump(mode="python"))
    return 0


def cmd_inspect(args) -> int:
    files = package_io.read_package_files(args.package)
    manifest = files.get("manifest.json", {})
    ir = files.get("workflow_ir.json", {})
    assurance = files.get("assurance_manifest.json", {})
    caps = files.get("capability_manifest.json", {})
    _print({
        "policy_pack_id": manifest.get("policy_pack_id"),
        "structural_digest": manifest.get("structural_digest"),
        "node_count": len(ir.get("nodes", [])),
        "edge_count": len(ir.get("edges", [])),
        "referenced_capabilities": caps.get("referenced_capabilities", []),
        "assurance_test_count": len(assurance.get("scenarios", []))
        + len(assurance.get("replay_cases", [])),
        "files": sorted(files.keys()),
    })
    return 0


def cmd_demo(args) -> int:
    if args.domain != "procurement":
        _print({"error": f"unknown demo domain '{args.domain}'"})
        return 2
    from .reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )

    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    result = GovernedWorkflowCompiler().compile(pack, approval)
    if not result.success:
        _print({"success": False,
                "diagnostics": [d.model_dump(mode="python") for d in result.diagnostics]})
        return 2
    if args.out:
        package_io.write_package(result.compiled_package, args.out)
    report = verify_compiled_package(result.compiled_package)
    _print({
        "success": True,
        "pack_id": pack.pack_id,
        "logical_digest": result.logical_digest,
        "nodes": len(result.workflow_ir.nodes),
        "edges": len(result.workflow_ir.edges),
        "assurance_tests": result.assurance_manifest.test_count,
        "coverage_complete": result.assurance_manifest.coverage_matrix.complete,
        "verify_passed": report.passed,
        "written_to": args.out or None,
    })
    return 0 if report.passed else 2


def _read_compiled_package(directory: str):
    """Reconstruct a CompiledReleasePackage from an on-disk package directory."""
    from .compiler.release import (
        CapabilityManifest,
        CompiledReleasePackage,
        ReleaseManifest,
    )
    from .models.assurance import AssuranceManifest, CoverageMatrix
    from .models.audit import AuditSchema
    from .models.policy_pack import PolicyPack as _PP
    from .compiler.workflow_ir import WorkflowIR
    from .validation.errors import ValidationReport
    from .models.approvals import HumanApprovalRecord as _HAR

    files = package_io.read_package_files(directory)
    if "manifest.json" not in files:
        return None
    try:
        approval_data = files.get("approval_record.json") or None
        approval = _HAR.model_validate(approval_data) if approval_data else None
        sd = files.get("structural_digest.json", {})
        return CompiledReleasePackage(
            manifest=ReleaseManifest.model_validate(files["manifest.json"]),
            policy_pack=_PP.model_validate(files["policy_pack.json"]),
            workflow_ir=WorkflowIR.model_validate(files["workflow_ir.json"]),
            capability_manifest=CapabilityManifest.model_validate(files["capability_manifest.json"]),
            assurance_manifest=AssuranceManifest.model_validate(files["assurance_manifest.json"]),
            coverage_matrix=CoverageMatrix.model_validate(files["coverage_matrix.json"]),
            audit_schema=AuditSchema.model_validate(files["audit_schema.json"]),
            approval_record=approval,
            validation_report=ValidationReport.model_validate(files["validation_report.json"]),
            structural_digest=sd.get("structural_digest", ""),
            release_metadata=sd.get("release_metadata", {}),
        )
    except Exception:  # pragma: no cover - defensive
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence-policy-workflow-compiler",
        description="Compile a reviewed structured governance policy pack into a "
        "deterministic governed-workflow artifact and assurance package.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print version and maturity metadata").set_defaults(
        func=cmd_version
    )

    p_validate = sub.add_parser("validate", help="validate a policy pack")
    p_validate.add_argument("pack")
    p_validate.set_defaults(func=cmd_validate)

    p_compile = sub.add_parser("compile", help="compile an approved policy pack")
    p_compile.add_argument("pack")
    p_compile.add_argument("--approval", default=None, help="approval record JSON")
    p_compile.add_argument("--out", default=None,
                           help="write compiled package to DIR (v1) or v2 JSON to FILE")
    p_compile.add_argument("--contract", default=WORKFLOW_IR_V1,
                           choices=list(SUPPORTED_WORKFLOW_IR_VERSIONS),
                           help="target workflow-IR contract (default workflow_ir.v1)")
    p_compile.add_argument("--no-approval", action="store_true",
                           help="skip the approval gate (preview only)")
    p_compile.set_defaults(func=cmd_compile)

    p_valrel = sub.add_parser("validate-release",
                              help="validate an enriched workflow_ir.v2 release JSON")
    p_valrel.add_argument("file")
    p_valrel.set_defaults(func=cmd_validate_release)

    p_isem = sub.add_parser("inspect-semantics", help="inspect v2 node semantics")
    p_isem.add_argument("file")
    p_isem.set_defaults(func=cmd_inspect_semantics)

    p_idep = sub.add_parser("inspect-dependencies", help="inspect v2 dependency semantics")
    p_idep.add_argument("file")
    p_idep.set_defaults(func=cmd_inspect_dependencies)

    p_iprov = sub.add_parser("inspect-provenance", help="inspect v2 policy provenance")
    p_iprov.add_argument("file")
    p_iprov.set_defaults(func=cmd_inspect_provenance)

    p_cmp = sub.add_parser("compare-contracts",
                           help="compare a v1 IR JSON and a v2 release JSON")
    p_cmp.add_argument("v1_file")
    p_cmp.add_argument("v2_file")
    p_cmp.set_defaults(func=cmd_compare_contracts)

    p_up = sub.add_parser("upgrade-v1",
                          help="deterministic, non-destructive v1->v2 enrichment "
                               "(preserves all v1 information; derived/deferred/"
                               "unresolved semantics are labeled, never invented)")
    p_up.add_argument("file")
    p_up.add_argument("--out", default=None, help="write v2 JSON to FILE")
    p_up.set_defaults(func=cmd_upgrade_v1)

    p_verify = sub.add_parser("verify", help="verify a compiled package directory")
    p_verify.add_argument("package")
    p_verify.set_defaults(func=cmd_verify)

    p_diff = sub.add_parser("diff", help="structural diff of two packs")
    p_diff.add_argument("old")
    p_diff.add_argument("new")
    p_diff.set_defaults(func=cmd_diff)

    p_inspect = sub.add_parser("inspect", help="inspect a compiled package directory")
    p_inspect.add_argument("package")
    p_inspect.set_defaults(func=cmd_inspect)

    p_demo = sub.add_parser("demo", help="run the offline Procurement demo")
    p_demo.add_argument("domain", choices=["procurement"])
    p_demo.add_argument("--out", default=None, help="write compiled package to DIR")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
