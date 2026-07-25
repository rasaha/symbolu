"""Deterministic benchmark CLI (Task 17).

    python -m comparative_governance_benchmark.run \
      --dataset enterprise_pilot_v1 --output build/phase6a-results

Default execution runs all four strategies over all 90 scenarios in normal mode
plus every required failure profile, checks all invariants and fairness controls,
and writes all reports. Repeated runs produce an identical substantive digest.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from .benchmark import run_benchmark
from .reporting.generate import write_all, comparative_report_md
from .reporting import generate as _gen
from .schemas.dataset import load_frozen_dataset
from .schemas.failure import FailureProfile
from .strategies import STRATEGY_ORDER


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="DGM comparative governance benchmark")
    parser.add_argument("--dataset", default="enterprise_pilot_v1",
                        help="frozen dataset identity (only enterprise_pilot_v1 is supported)")
    parser.add_argument("--output", default="build/phase6a-results")
    parser.add_argument("--strategies", default=",".join(STRATEGY_ORDER),
                        help="comma-separated strategy ids")
    parser.add_argument("--domains", default="", help="comma-separated domain filter")
    parser.add_argument("--failure-profile", default="",
                        help="run only this failure profile (default: all)")
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args(argv)

    if args.dataset != "enterprise_pilot_v1":
        print(f"only the frozen enterprise_pilot_v1 dataset is supported (got {args.dataset})",
              file=sys.stderr)
        return 2

    dataset = load_frozen_dataset()
    if args.domains:
        import dataclasses
        keep = set(args.domains.split(","))
        dataset = dataclasses.replace(
            dataset, scenarios=tuple(s for s in dataset.scenarios if s.domain in keep))

    strategy_ids = tuple(s for s in args.strategies.split(",") if s in STRATEGY_ORDER)
    if args.failure_profile:
        profiles = (FailureProfile.NORMAL, FailureProfile[args.failure_profile])
    else:
        profiles = tuple(FailureProfile)

    res = run_benchmark(dataset, strategy_ids=strategy_ids, profiles=profiles, seed=args.seed)
    written = write_all(res, pathlib.Path(args.output))

    from .schemas.safety import UNSAFE_OUTCOMES
    print(f"dataset {res.dataset_identity.version} hash={res.dataset_identity.content_hash[:16]} "
          f"scenarios={res.dataset_identity.scenario_count}")
    for sid in strategy_ids:
        u = sum(1 for j in res.judgements[sid] if j.safety_outcome in UNSAFE_OUTCOMES)
        print(f"  {sid:16} unsafe={u:3}  ops={res.cost[sid]['total_operations']}")
    print(f"fairness   : {'PASS' if res.fairness_passed else 'FAIL'}")
    print(f"invariants : {'PASS' if res.invariants_passed else 'FAIL'}")
    print(f"substantive digest: {res.substantive_digest}")
    print(f"reports written : {len(written)} -> {args.output}")
    for p in written:
        print(f"  - {p.name}")
    return 0 if res.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
