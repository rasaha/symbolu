#!/usr/bin/env python3
"""Fail when the committed distribution-verifier report has gone stale.

`artifacts/distribution_verifier_report.json` is a checked-in record of a real
verifier run. Nothing previously tied it to the build it describes, so it silently
kept describing the 0.1.0 build after the distribution moved to 0.2.0 (stale wheel
filename, stale public-API count, no v2 steps at all). This guard closes that gap.

It deliberately compares only fields that are stable across machines and runs:

* the verdict, and that every required step is present and passed;
* the distribution version reported by the installed CLI, and the wheel/sdist
  **filenames** (not their hashes);
* the frozen public-API count, against `artifacts/public_api.json`;
* the frozen `workflow_ir.v1` digest semantic identity;
* the v1 logical digest and the v2 workflow fingerprint, cross-checked against the
  values this source tree computes right now.

It deliberately does NOT compare:

* the raw sdist archive SHA — the report itself records
  `sdist_archive_bit_for_bit: false` (only sdist *content* is reproducible), so
  archive-hash equality is not an established invariant and must not gate CI;
* the wheel SHA — reproducible bit-for-bit within a single verifier run, but
  observed to differ between runs (build metadata), so it is not an invariant;
* the embedded pytest timing string, which varies run to run.

Exit 0 when the report is consistent with this source tree; exit 1 with the
specific mismatches otherwise.
"""

from __future__ import annotations

import json
import pathlib
import sys

PKG_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = PKG_ROOT / "artifacts" / "distribution_verifier_report.json"
PUBLIC_API = PKG_ROOT / "artifacts" / "public_api.json"

# Every step the current verifier must have exercised. A report missing any of
# these describes an older verifier and is stale by definition.
REQUIRED_STEPS = (
    "dep_download",
    "distribution_version_0_2_0",
    "wheel_audit",
    "clean_install",
    "isolated_imports",
    "no_repo_path_leak",
    "cli_version",
    "cli_demo",
    "cli_verify",
    "cli_inspect",
    "cli_validate",
    "cli_compile",
    "cli_diff",
    "cli_version_v2_flags",
    "cli_compile_v2",
    "cli_validate_release",
    "cli_inspect_semantics",
    "cli_inspect_dependencies",
    "cli_inspect_provenance",
    "cli_upgrade_v1",
    "cli_compare_contracts",
    "deterministic_digest",
    "procurement_equivalence",
    "deterministic_v2_fingerprint",
    "cli_review_requirements",
    "cli_check_review_refuses",
    "public_api_frozen",
    "offline_no_credentials",
    "installed_test_suite",
)


def _live_digests() -> tuple[str, str]:
    """Recompute the v1 release digest and the v2 workflow fingerprint here."""
    import ugence_policy_workflow_compiler.api as api
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_approval_fixture,
        build_procurement_policy_pack,
    )
    from ugence_policy_workflow_compiler.semantics import compile_workflow_v2

    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    v1 = api.compile_policy_pack(pack, approval)
    v2 = compile_workflow_v2(pack, approval)
    return v1.logical_digest, v2.workflow_fingerprint


def main() -> int:
    from ugence_policy_workflow_compiler.version import (
        DISTRIBUTION_VERSION,
        WORKFLOW_IR_V1,
        digest_compiler_version_for,
    )

    report = json.loads(REPORT.read_text())
    steps = report.get("steps", {})
    problems: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    check(report.get("verdict") == "PASS", f"verdict is {report.get('verdict')!r}, not PASS")

    for name in REQUIRED_STEPS:
        if name not in steps:
            problems.append(f"required step {name!r} missing — report predates the current verifier")
        elif not steps[name].get("passed"):
            problems.append(f"step {name!r} did not pass")

    reported_version = steps.get("cli_version", {}).get("distribution_version")
    check(
        reported_version == DISTRIBUTION_VERSION,
        f"report describes distribution {reported_version!r}, source tree is {DISTRIBUTION_VERSION!r}",
    )

    # Filenames only — never the archive hashes (see module docstring).
    for where, key in (("hashes", "wheel"), ("hashes", "sdist")):
        name = report.get(where, {}).get(key, {}).get("name", "")
        check(
            DISTRIBUTION_VERSION in name,
            f"{key} filename {name!r} does not carry version {DISTRIBUTION_VERSION}",
        )
    for key in ("wheel", "sdist"):
        name = steps.get("distribution_version_0_2_0", {}).get(key, "")
        check(
            DISTRIBUTION_VERSION in name,
            f"distribution_version step {key} {name!r} does not carry version {DISTRIBUTION_VERSION}",
        )

    frozen_count = json.loads(PUBLIC_API.read_text())["count"]
    reported_count = steps.get("public_api_frozen", {}).get("count")
    check(
        reported_count == frozen_count,
        f"report public-API count {reported_count} != frozen artifact count {frozen_count}",
    )

    check(
        digest_compiler_version_for(WORKFLOW_IR_V1) == "0.1.0",
        "workflow_ir.v1 digest semantic identity is no longer frozen at 0.1.0",
    )

    live_v1, live_v2 = _live_digests()
    for step, key, live, label in (
        ("cli_demo", "logical_digest", live_v1, "v1 logical digest"),
        ("deterministic_digest", "digest", live_v1, "v1 deterministic digest"),
        ("cli_compile_v2", "workflow_fingerprint", live_v2, "v2 fingerprint"),
        ("deterministic_v2_fingerprint", "workflow_fingerprint", live_v2, "v2 deterministic fingerprint"),
    ):
        reported = steps.get(step, {}).get(key)
        check(
            reported == live,
            f"{label}: report {reported!r} != freshly computed {live!r}",
        )

    if problems:
        print("Distribution-verifier report is stale or inconsistent:")
        for p in problems:
            print("  -", p)
        print("\nRegenerate it with:")
        print("  python packages/tooling/policy-workflow-compiler/scripts/"
              "verify_policy_workflow_compiler_distribution.py \\")
        print("    > packages/tooling/policy-workflow-compiler/artifacts/"
              "distribution_verifier_report.json")
        return 1

    print(
        f"verifier report fresh: distribution {DISTRIBUTION_VERSION}, "
        f"{frozen_count} public names, {len(REQUIRED_STEPS)} required steps passed, "
        f"v1 {live_v1}, v2 {live_v2}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
