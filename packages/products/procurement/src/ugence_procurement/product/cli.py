"""Command-line facade for the Ugence Procurement product.

A thin, read-only, offline CLI over the public API. Every subcommand runs
deterministic simulation with in-memory adapters and prints to stdout — no
network, no model SDK, no credentials, no production integration — and stops
before any real supplier effect.

Subcommands:
- ``version`` — print distribution + product version/maturity metadata (JSON or text).
- ``verify``  — assert the packaged product's safety/governance invariants; PASS/FAIL.
- ``demo``    — run the canonical reference demo (happy path + fail-closed) and print it.
- ``report``  — print a structured JSON report of the demo cohort + maturity.

Invoke as ``python -m ugence_procurement <command>`` or
``python -m ugence_procurement.product.cli <command>``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ..version import version_info
from .demo import run_demo
from .version import product_maturity


def _cmd_version(args) -> int:
    info = version_info()
    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
    else:
        print(f"{info.distribution} {info.distribution_version} (distribution) — "
              f"{info.product} product {info.product_version} ({info.stability})")
        print(f"canonical namespace: {info.canonical_namespace}")
        print(f"release classification: {info.release_classification}")
        print(f"evidence maturity: {info.evidence_maturity}")
        print(f"pilot validated: {info.pilot_validated}")
        print(f"production certified: {info.production_certified}")
    return 0


def _cmd_demo(args) -> int:
    result = run_demo()
    if args.json:
        print(json.dumps({"product_version": result.product_version,
                          "cohort": result.summary()}, indent=2))
    else:
        print(f"Ugence Procurement reference demo — product {result.product_version} "
              f"(deterministic, offline; no real purchase order created)")
        for row in result.summary():
            print(f"  {row['scenario']:<32} request={row['request_id']:<20} "
                  f"outcome={row['outcome'] or '-':<22} "
                  f"auth={row['authorization_outcome'] or '-':<26} "
                  f"dispatched={row['dispatched']}")
            print(f"    · {row['note']}")
    return 0


def _cmd_report(args) -> int:
    result = run_demo()
    info = version_info()
    report = {
        "product": info.product,
        "distribution": info.distribution,
        "distribution_version": info.distribution_version,
        "product_version": info.product_version,
        "maturity": product_maturity().to_dict(),
        "cohort": result.summary(),
    }
    print(json.dumps(report, indent=2))
    return 0


def _cmd_verify(args) -> int:
    info = version_info()
    result = run_demo()
    runs = {r.scenario: r for r in result.runs}
    happy = runs.get("happy_path")
    fail_closed = runs.get("fail_closed_restricted_supplier")
    checks = {
        "pilot_not_validated": info.pilot_validated is False,
        "production_not_certified": info.production_certified is False,
        "reference_workflow_verified": info.reference_workflow_verified is True,
        "canonical_namespace_is_ugence_procurement":
            info.canonical_namespace == "ugence_procurement",
        "happy_path_reconciled":
            happy is not None and happy.reconciliation_status == "RECONCILED",
        "happy_path_dispatched": happy is not None and happy.dispatched is True,
        "restricted_supplier_denied":
            fail_closed is not None and fail_closed.authorization_outcome == "DENIED",
        "restricted_supplier_not_dispatched":
            fail_closed is not None and fail_closed.dispatched is False,
    }
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence_procurement",
        description="Ugence Procurement — deterministic, offline reference CLI "
                    "(no production effects).",
    )
    # ``--json`` is accepted after the subcommand (e.g. ``version --json``).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", parents=[common],
                   help="print distribution + product version/maturity metadata")
    sub.add_parser("verify", parents=[common],
                   help="assert product safety/governance invariants")
    sub.add_parser("demo", parents=[common], help="run the canonical reference demo cohort")
    sub.add_parser("report", parents=[common],
                   help="print a structured JSON report of the demo cohort")
    return parser


_DISPATCH = {
    "version": _cmd_version,
    "verify": _cmd_verify,
    "demo": _cmd_demo,
    "report": _cmd_report,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
