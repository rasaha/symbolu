"""Command-line facade for the AI Hiring product (H6 §11).

A thin, read-only CLI over the public API. It performs no production effect; every
subcommand runs deterministic simulation and prints to stdout.

Subcommands:
- ``version`` — print product/platform version metadata (JSON or text).
- ``demo``    — run the canonical safe demo and print the cohort summary.
- ``report``  — run the demo and print the sample accountability report
                (``--no-redact`` to show un-redacted identifiers).
- ``verify``  — assert the safety invariants (deterministic mode, no production
                adapter) and print PASS/FAIL.

Invoke as ``python -m ugence_ai_hiring.product`` or ``python -m ugence_ai_hiring.product.cli``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .composition import build_demo_platform
from .config import ExecutionMode
from .demo import run_demo
from .version import version_info


def _cmd_version(args) -> int:
    info = version_info()
    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
    else:
        print(f"AI Hiring product {info.product_version} "
              f"(platform {info.platform_baseline}, {info.stability})")
        print(f"production certified: {info.production_certified}")
    return 0


def _cmd_demo(args) -> int:
    result = run_demo()
    if args.json:
        print(json.dumps({"product_version": result.product_version,
                          "cohort": result.summary()}, indent=2))
    else:
        print(f"Canonical demo — product {result.product_version} "
              f"(deterministic simulation)")
        for row in result.summary():
            print(f"  {row['case_id']:<14} stage={row['reached_stage']:<16} "
                  f"rec={row['recommendation_status'] or '-':<24} "
                  f"decision={row['decision_outcome'] or '-':<8} "
                  f"auth={row['authorization_outcome'] or '-':<8} "
                  f"proposal={row['proposal_status'] or '-':<24} "
                  f"recon={row['reconciliation_outcome'] or '-'}")
    return 0


def _cmd_report(args) -> int:
    from .accountability import build_accountability_report

    product = build_demo_platform()
    result = run_demo(product)
    proposal_id = None
    for r in result.runs:
        if r.action_proposal_id and r.reconciliation_outcome == "MATCHED":
            proposal_id = r.action_proposal_id
            break
    if proposal_id is None:
        print("no reconciled action in demo cohort", file=sys.stderr)
        return 1
    report = build_accountability_report(product, proposal_id, redact=not args.no_redact)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, default=str))
    else:
        print(report.render_text())
    return 0


def _cmd_verify(args) -> int:
    product = build_demo_platform()
    checks = {
        "execution_mode_is_deterministic":
            product.config.execution_mode is ExecutionMode.DETERMINISTIC_SIMULATION,
        "production_not_certified": version_info().production_certified is False,
    }
    # a demo run must complete without a production external effect
    result = run_demo(product)
    checks["demo_ran"] = len(result.runs) == 5
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence_ai_hiring.product",
        description="AI Hiring product — deterministic-simulation CLI (no production effects).",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print product/platform version metadata")
    sub.add_parser("demo", help="run the canonical safe demo")
    rep = sub.add_parser("report", help="print a sample accountability report")
    rep.add_argument("--no-redact", action="store_true",
                     help="show un-redacted subject/actor identifiers")
    sub.add_parser("verify", help="assert product safety invariants")
    return parser


_DISPATCH = {
    "version": _cmd_version,
    "demo": _cmd_demo,
    "report": _cmd_report,
    "verify": _cmd_verify,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
