"""Run the Procurement example end to end (deterministic, offline).

    python -m examples.procurement
"""

from __future__ import annotations

import json

from ugence_policy_workflow_compiler.api import (
    GovernedWorkflowCompiler,
    verify_compiled_package,
)

from .pack import build_procurement_approval_fixture, build_procurement_policy_pack


def main() -> int:
    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    result = GovernedWorkflowCompiler().compile(pack, approval)
    if not result.success:
        print(json.dumps({"success": False,
                          "diagnostics": [d.model_dump(mode="python") for d in result.diagnostics]},
                         indent=2))
        return 2
    report = verify_compiled_package(result.compiled_package)
    print(json.dumps({
        "success": True,
        "pack_id": pack.pack_id,
        "logical_digest": result.logical_digest,
        "nodes": len(result.workflow_ir.nodes),
        "edges": len(result.workflow_ir.edges),
        "assurance_tests": result.assurance_manifest.test_count,
        "coverage_complete": result.assurance_manifest.coverage_matrix.complete,
        "verify_passed": report.passed,
    }, indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
