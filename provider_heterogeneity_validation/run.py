"""Deterministic Phase 6B CLI (Task 16).

    python -m provider_heterogeneity_validation.run \
      --dataset enterprise_pilot_v1 --output build/phase6b-results

Default execution runs all six configurations over all 90 scenarios, the required
failure profiles over a deterministic representative subset, all invariants, and
all reports. Repeated runs produce an identical substantive digest.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from .failure_injection.profiles import FailureProfile, REQUIRED_PROFILES
from .reporting.generate import write_all
from .schemas.config import CONFIG_ORDER
from .validation import run_validation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="DGM provider heterogeneity validation")
    parser.add_argument("--dataset", default="enterprise_pilot_v1")
    parser.add_argument("--output", default="build/phase6b-results")
    parser.add_argument("--configuration", default=",".join(CONFIG_ORDER))
    parser.add_argument("--domains", default="")
    parser.add_argument("--provider-state-profile", default="")
    parser.add_argument("--failure-profile", default="")
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args(argv)

    if args.dataset != "enterprise_pilot_v1":
        print(f"only enterprise_pilot_v1 is supported (got {args.dataset})", file=sys.stderr)
        return 2

    config_ids = tuple(c for c in args.configuration.split(",") if c in CONFIG_ORDER)
    profiles = REQUIRED_PROFILES
    if args.failure_profile:
        profiles = (FailureProfile.NORMAL, FailureProfile[args.failure_profile])

    dataset = None
    if args.domains:
        import dataclasses
        from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
        keep = set(args.domains.split(","))
        base = load_frozen_dataset()
        dataset = dataclasses.replace(
            base, scenarios=tuple(s for s in base.scenarios if s.domain in keep))

    res = run_validation(dataset, config_ids=config_ids, profiles=profiles)
    written = write_all(res, pathlib.Path(args.output))

    print(f"dataset {res.dataset_identity.version} hash={res.dataset_identity.content_hash[:16]}")
    for cid in config_ids:
        c = res.configuration_comparison[cid]
        print(f"  {cid} unsafe={c['unsafe_outcomes']:2} dispatched={c['dispatched']:2} "
              f"false_blocks={c['false_blocks']:2} fallbacks={c['assertion_fallbacks']+c['action_fallbacks']:2}")
    print(f"invariants H1-H20 : {'PASS' if res.invariants_passed else 'FAIL'}")
    print(f"substantive digest: {res.substantive_digest}")
    print(f"reports written   : {len(written)} -> {args.output}")
    for p in written:
        print(f"  - {p.name}")
    return 0 if res.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
