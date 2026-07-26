"""Deterministic pilot entry point (Task 115).

Run:

    python -m enterprise_validation_pilot.run \
      --dataset enterprise_validation_pilot/datasets/enterprise_pilot_v1.json \
      --output build/pilot-results

Loads the versioned dataset, validates the ecosystem manifest, executes the whole
pilot, writes all reports, and exits non-zero if any invariant, failure-injection,
independence, or scenario check fails. Repeated runs against the same code + dataset
produce an identical substantive digest.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from .composition.manifest import validate_manifest
from .pilot import run_pilot
from .reports.generate import write_all
from .schemas.dataset import Dataset

_DEFAULT_DATASET = pathlib.Path(__file__).resolve().parent / "datasets" / "enterprise_pilot_v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DGM enterprise validation pilot")
    parser.add_argument("--dataset", default=str(_DEFAULT_DATASET),
                        help="path to the versioned ground-truth dataset JSON")
    parser.add_argument("--output", default="build/pilot-results",
                        help="directory for machine- and human-readable reports")
    args = parser.parse_args(argv)

    manifest = validate_manifest()
    if not manifest.ok:
        print("MANIFEST INVALID:", [c.component for c in manifest.failures], file=sys.stderr)
        return 2

    dataset = Dataset.from_json(pathlib.Path(args.dataset).read_text())
    results = run_pilot(dataset)
    written = write_all(results, pathlib.Path(args.output))

    print(f"dataset {results.dataset_version} hash={results.dataset_hash[:16]} "
          f"scenarios={len(results.runs)}")
    print(f"scenarios passed : {results.scenarios_passed}/{len(results.runs)}")
    print(f"invariants       : {'PASS' if results.invariants_passed else 'FAIL'}")
    print(f"failure injection: {'FAIL-SAFE' if results.failure_injection_passed else 'FAIL'}")
    print(f"independence     : {'PEERS' if results.independence_passed else 'VIOLATION'}")
    print(f"substantive digest: {results.substantive_digest}")
    print(f"reports written  : {len(written)} -> {args.output}")
    for p in written:
        print(f"  - {p.name}")

    return 0 if results.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
