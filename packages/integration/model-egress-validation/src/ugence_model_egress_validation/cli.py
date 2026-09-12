"""``python -m ugence_model_egress_validation``: the offline run, and a ``live`` that refuses.

This is the one module that reads a clock and the filesystem. ``offline`` runs the
harness with fake components, checks the records for drift, writes the redacted report
and exits non-zero on any non-conformant offline row or any drift. ``live`` never
executes: no live transport exists in any distribution, and LP-7 ruling 12 keeps the
owner-run verifier from executing until every step-8 designation is supplied and
independently checked. It prints the undesignated values and exits 2.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timezone
from typing import List, Optional

from ugence_model_egress_unit import COMMISSIONING_STATUS, STEP8_OBLIGATION_COUNT, step8_field_counts

from .drift import check_drift, load_records
from .harness import run_offline
from .report import build_report, write_report

__all__ = ["main"]


def _undesignated(designation: dict) -> tuple:
    """(undesignated obligation keys, attestation lines). Obligations are the seventeen of
    ruling 12; the independent check is an attestation, never an eighteenth obligation."""

    step8 = designation.get("step8_required_values", {})
    obligations = step8.get("obligations", {})
    names = [k for k, v in obligations.items() if isinstance(v, str) and v.startswith("UNDESIGNATED")]
    attestation = []
    if step8.get("attestation", {}).get("independently_checked_by") in (None, ""):
        attestation.append("independently_checked_by: not recorded")
    return names, attestation


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ugence_model_egress_validation")
    sub = parser.add_subparsers(dest="command", required=True)
    off = sub.add_parser("offline", help="run the eighteen-row harness over fake components and write a redacted report")
    off.add_argument("--report", required=True, type=pathlib.Path)
    off.add_argument("--now", default=None, help="ISO-8601 instant with offset; defaults to the current UTC time")
    off.add_argument("--records", default=None, type=pathlib.Path, help="directory of the two records (default: beside the unit)")
    live = sub.add_parser("live", help="refuses until every step-8 designation is supplied and independently checked")
    live.add_argument("--records", default=None, type=pathlib.Path)
    args = parser.parse_args(argv)

    records = load_records(args.records)
    if args.command == "live":
        # Refused here, before any custody port, budget, transport or harness is touched.
        missing, attestation = _undesignated(records["designation"])
        counts = step8_field_counts()
        pinned = records["validation"].get("live_synthetic_validation_authorization")
        print(f"live verifier refused: commissioning is {COMMISSIONING_STATUS}; no live transport exists in any distribution; "
              f"the canonical live_synthetic_validation_authorization is {pinned!r} (a typed, consumed authorization is the "
              f"only thing that admits a genuine call, ADR §0.6).")
        print(f"{counts['statement']} (LP-7 ruling 12).")
        print(f"{len(missing)} of {STEP8_OBLIGATION_COUNT} mandatory designation obligations are undesignated:")
        for name in missing:
            print(f"  - {name}")
        print("attestation (not a designation obligation):")
        for line in attestation or ["independently_checked_by: recorded"]:
            print(f"  - {line}")
        print("Supplying and verifying them closes only the infrastructure-designation blocker; the first live synthetic "
              "validation needs the owner's separate explicit authorization.")
        return 2

    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    run = run_offline(now=now)
    report = build_report(run)
    drift = check_drift(records["designation"], records["validation"])
    report["drift"] = drift
    write_report(report, args.report)
    nonconformant = [r["row"] for r in report["rows"] if r["status"] == "OFFLINE_NONCONFORMANT"]
    print(f"offline harness: {report['summary']} -> {args.report}")
    if nonconformant:
        print(f"non-conformant offline rows: {nonconformant}")
    if drift:
        print("drift:")
        for line in drift:
            print(f"  - {line}")
    print(f"infrastructure-dependent rows not executed: {report['infrastructure_dependent_rows_not_executed']}; "
          f"{report['step8']['statement']}, none supplied here")
    return 1 if (nonconformant or drift) else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
