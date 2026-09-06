#!/usr/bin/env python3
"""Build ``ugence-clearance-export`` and prove the rulings against the *built artifact*.

A source tree can satisfy CE-2 by accident: the repository conftest puts sibling
packages on ``sys.path``, so an import the metadata never declared still resolves.
This script removes that comfort. It builds the wheel and the sdist, installs the
wheel into a clean ``--no-index`` virtual environment with only its one declared
dependency available, and interrogates the *installed* package.

Four proofs (``docs/architecture/ADR_UGENCE_CLEARANCE_EXPORT_SCOPING.md`` §10, §13):

1. **CE-2** — the wheel ships ``ugence_clearance_export`` and nothing else, and its
   metadata declares exactly one dependency: the evaluator package whose frozen
   receipt type CE-1 requires. Not the package that persists receipts.
2. **CE-2, the negative half** — installing without ``ugence-action-clearance``
   *fails at install*. A contracts package that quietly imported a type it never
   declared would pass every source test and break in a deployment.
3. **CE-3, CE-4, CE-7** — from the installed package, each of the three honesty
   enums has exactly one member, and an artifact cannot be built, rebuilt or
   serialized without all three.
4. **CE-5** — the installed port has two reads and no write, and the public surface
   exposes no verb that accepts a receipt.

Run:  python packages/integration/clearance-export/scripts/verify_clearance_export_distribution.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

PACKAGE = pathlib.Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]

#: The one declared dependency, and where it is built from.
DEPENDENCY = "ugence-action-clearance"
DEPENDENCY_SOURCE = REPO / "packages" / "capabilities" / "action-clearance"

_failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {message}")
    if not condition:
        _failures.append(message)


def run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True)


def must(argv: list[str]) -> str:
    result = run(argv)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(argv)}")
    return result.stdout


def wheel_for(wheelhouse: pathlib.Path, distribution: str) -> pathlib.Path:
    prefix = distribution.replace("-", "_") + "-"
    (found,) = [w for w in wheelhouse.glob("*.whl") if w.name.startswith(prefix)]
    return found


def build_all(wheelhouse: pathlib.Path) -> None:
    print(f"\nBuilding into {wheelhouse}")
    for source in (PACKAGE, DEPENDENCY_SOURCE):
        must([sys.executable, "-m", "build", "--outdir", str(wheelhouse), str(source)])
        print(f"  built {source.name}")


def make_venv(root: pathlib.Path) -> pathlib.Path:
    must([sys.executable, "-m", "venv", str(root)])
    return root / "bin" / "python"


def proof_1_the_wheel_and_its_one_dependency(wheelhouse: pathlib.Path) -> None:
    import zipfile

    print("\nCE-2 — the wheel ships the namespace, and declares one dependency")
    wheel = wheel_for(wheelhouse, "ugence-clearance-export")
    names = zipfile.ZipFile(wheel).namelist()
    top = {n.split("/")[0] for n in names}
    check(top == {"ugence_clearance_export", "ugence_clearance_export-0.1.0.dist-info"},
          f"one top-level package plus its metadata (got {sorted(top)})")
    check(not any("/tests/" in n or n.startswith("tests/") for n in names),
          "no test module ships in the distribution")
    check("ugence_clearance_export/py.typed" in names, "py.typed ships")

    metadata = zipfile.ZipFile(wheel).read(
        "ugence_clearance_export-0.1.0.dist-info/METADATA").decode()
    requires = [line.split(":", 1)[1].strip() for line in metadata.splitlines()
                if line.startswith("Requires-Dist:") and "extra ==" not in line]
    check(len(requires) == 1 and requires[0].startswith(DEPENDENCY),
          f"exactly one required dependency, and it is {DEPENDENCY} (got {requires})")
    check(not any("execution-reservation" in r for r in requires),
          "the receipt store is not pulled in through the dependency graph")


def proof_2_a_missing_dependency_fails_at_install(
        wheelhouse: pathlib.Path, workspace: pathlib.Path) -> None:
    print("\nCE-2 — the declared dependency is real: install fails without it")
    partial = workspace / "wheelhouse-partial"
    partial.mkdir()
    withheld = DEPENDENCY.replace("-", "_") + "-"
    for candidate in wheelhouse.glob("*.whl"):
        if not candidate.name.startswith(withheld):
            shutil.copy2(candidate, partial)

    python = make_venv(workspace / "venv-partial")
    result = run([str(python), "-m", "pip", "install", "--no-index",
                  "--find-links", str(partial),
                  str(wheel_for(wheelhouse, "ugence-clearance-export"))])
    check(result.returncode != 0, f"install refuses without {DEPENDENCY}")
    check(DEPENDENCY in (result.stdout + result.stderr),
          "pip names the missing distribution in its refusal")


def proofs_3_and_4_the_installed_package(
        wheelhouse: pathlib.Path, workspace: pathlib.Path) -> None:
    print("\nCE-3, CE-4, CE-7 — the three honesty labels, from the installed package")
    python = make_venv(workspace / "venv-full")
    must([str(python), "-m", "pip", "install", "--no-index",
          "--find-links", str(wheelhouse),
          str(wheel_for(wheelhouse, "ugence-clearance-export"))])

    probe = r'''
import json
from datetime import datetime, timedelta, timezone

import ugence_clearance_export as pkg
from ugence_action_clearance import ClearanceReceiptBody, ClearanceResult, ClearanceStatus

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
body = ClearanceReceiptBody.from_result(ClearanceResult(
    request_id="req-1", authorization_ref="authz-1",
    authorized_action_fingerprint="actfp-1", status=ClearanceStatus.CLEAR,
    reason_codes=("OPERATIONALLY_SAFE",), effective_constraints=(), obligations=(),
    evaluated_at=T0, valid_until=T0 + timedelta(minutes=15),
    policy_refs=("policy:v1",), signal_refs=("sig-1",), request_fingerprint="reqfp-1",
    tenant_id="tenant-alpha", signal_bundle_fingerprint="bundlefp-1"))

artifact = pkg.build_export(
    body,
    identity_assurance=pkg.IdentityAssurance.PRESENTED_UNPROVEN,
    authenticity=pkg.ExportAuthenticity.UNSIGNED,
    data_classification=pkg.ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY)
payload = pkg.artifact_to_dict(artifact)
report = pkg.verify_export(artifact)

omission_refused = {}
for label in ("identity_assurance", "authenticity", "data_classification"):
    without = {k: v for k, v in payload.items() if k != label}
    try:
        pkg.artifact_from_dict(without)
        omission_refused[label] = False
    except pkg.ContractViolation:
        omission_refused[label] = True

try:
    pkg.build_export(body,
                     identity_assurance=pkg.IdentityAssurance.PRESENTED_UNPROVEN,
                     authenticity="SIGNED",
                     data_classification=pkg.ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY)
    softening_refused = False
except pkg.AuthenticityClaimRefused:
    softening_refused = True

print(json.dumps({
    "members": {
        "identity_assurance": [m.value for m in pkg.IdentityAssurance],
        "authenticity": [m.value for m in pkg.ExportAuthenticity],
        "data_classification": [m.value for m in pkg.ExportDataClassification],
    },
    "labels_in_payload": {k: payload.get(k) for k in
                          ("identity_assurance", "authenticity", "data_classification")},
    "omission_refused": omission_refused,
    "softening_refused": softening_refused,
    "integrity_verified": report.integrity_verified,
    "uncheckable": list(report.uncheckable),
    "confers": report.confers,
    "port_surface": sorted(n for n in dir(pkg.ReceivedClearanceSource)
                           if not n.startswith("_")),
    "public_surface": sorted(pkg.__all__),
    "maturity": pkg.MATURITY,
    "enforcement_enabled": pkg.ENFORCEMENT_ENABLED,
}))
'''
    report = json.loads(must([str(python), "-c", probe]).strip().splitlines()[-1])

    check(report["members"]["identity_assurance"] == ["PRESENTED_UNPROVEN"],
          "IdentityAssurance has exactly one member (CE-3)")
    check(report["members"]["authenticity"] == ["UNSIGNED"],
          "ExportAuthenticity has exactly one member (CE-4)")
    check(report["members"]["data_classification"] == ["SYNTHETIC_DEMONSTRATION_ONLY"],
          "ExportDataClassification has exactly one member (CE-7)")
    for label, value in report["labels_in_payload"].items():
        check(value is not None, f"{label} is present on the serialized artifact")
    for label, refused in report["omission_refused"].items():
        check(refused, f"a payload that dropped {label} is refused, not defaulted")
    check(report["softening_refused"], "a softened authenticity claim is refused")
    check(report["integrity_verified"] is True, "the installed verifier verifies")
    check(len(report["uncheckable"]) == 4,
          "verification names all four things it could not check")
    check(report["confers"].startswith("NOTHING"),
          "verification says plainly that it confers nothing")

    print("\nCE-5 — export is a read, from the installed package")
    check(report["port_surface"] == ["list_receipt_ids", "read_receipt"],
          f"the port has two reads and no write (got {report['port_surface']})")
    written = [n for n in report["public_surface"]
               if any(v in n.lower() for v in ("put", "save", "store", "write",
                                               "record", "accept", "persist", "sign"))]
    check(written == [], f"no public verb accepts or stores a receipt (got {written})")
    check(report["maturity"] == "CONTRACTS_ONLY", "maturity is stated as contracts only")
    check(report["enforcement_enabled"] is False, "ENFORCEMENT_ENABLED is False")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="clearance-export-dist-") as tmp:
        workspace = pathlib.Path(tmp)
        wheelhouse = workspace / "wheelhouse"
        wheelhouse.mkdir()
        build_all(wheelhouse)
        proof_1_the_wheel_and_its_one_dependency(wheelhouse)
        proof_2_a_missing_dependency_fails_at_install(wheelhouse, workspace)
        proofs_3_and_4_the_installed_package(wheelhouse, workspace)

    print()
    if _failures:
        print(f"DISTRIBUTION VERIFICATION FAILED — {len(_failures)} check(s):")
        for failure in _failures:
            print(f"  {failure}")
        return 1
    print("DISTRIBUTION VERIFICATION OK — CE-2, CE-3, CE-4, CE-5 and CE-7 hold for the "
          "built artifact, not only for the source tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
