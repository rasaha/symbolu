"""A′ EXECUTION-READINESS entrypoint — GUARDED. Does NOT execute A′.

A′ is canonically halted (no admissible, licensed, construct-aligned E×Y
dataset; see ``MILESTONE_A_PRIME_EXECUTION_STATUS.md``). This entrypoint makes
the repository *ready*: it reads the A′ config, checks dataset availability +
license, and emits a readiness report with a precise missing-input checklist
and the building-block manifest that will assemble features and run the probe
when data arrives. It never fabricates data and never runs the (gated) A′/B
decision.

States:
  NOT_RUN          — inputs missing (the current, expected state)
  READY_BUT_GATED  — inputs present + license acknowledged; A′/B execution still
                     requires lifting the pre-registered gate (Milestone B), so
                     this entrypoint hands off rather than executing.

    python3 experiments/a_prime/run_a_prime.py [out.md]
"""
from __future__ import annotations

import pathlib
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import config as _cfgmod, repro as _repro  # noqa: E402
from common.report import ReportBuilder  # noqa: E402

# Building blocks already implemented and tested, ready to wire on data arrival.
BUILDING_BLOCKS = [
    "experiments/a_prime/projection.py — A1.4 deterministic E→E′ projection (P)",
    "experiments/common/stats.py — ridge OOF R², shuffle/permutation/percentile nulls, bootstrap CI, BH-FDR",
    "experiments/b0_synthetic_harness/harness_operator.py — operator-aware probe + generic detector",
    "experiments/b0_synthetic_harness/harness.py — bag/bigram baselines + shuffle-null decision",
]


def check_readiness(cfg) -> dict:
    missing = []
    for label, path in [("E ratings table", cfg.e_path),
                        ("semantic observable Y", cfg.y_path),
                        ("phonology baseline features", cfg.phonology_path)]:
        if not path:
            missing.append(f"{label}: path not configured")
        elif not Path(path).exists():
            missing.append(f"{label}: file not found ({path})")
    if not cfg.license_acknowledged:
        missing.append("license / data-use terms not acknowledged (A1.2 criterion 5)")
    status = "NOT_RUN" if missing else "READY_BUT_GATED"
    return {"status": status, "missing": missing, "endpoint": cfg.endpoint}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0]) if argv else (Path(__file__).resolve().parent / "A_PRIME_READINESS.md")
    t0 = time.perf_counter()
    cfg = _cfgmod.load_config(_cfgmod.AprimeConfig, Path(__file__).resolve().parent / "config.json")
    r = check_readiness(cfg)

    rb = ReportBuilder(
        "A_PRIME_READINESS — execution-readiness check (NOT an A′ run)",
        "GUARDED readiness check only. A′ remains canonically halted (no admissible, "
        "licensed, construct-aligned E×Y dataset). No data fabricated, no A′/B decision "
        "executed, no semantics, no PASS/FAIL/⊥ for Symbol-U. Stage A frozen.")
    rb.decision(r["status"])
    rb.section("Missing inputs (checklist)")
    rb.bullets(r["missing"] or ["(none — all configured inputs present)"])
    rb.section("Building blocks ready to wire on data arrival").bullets(BUILDING_BLOCKS)
    rb.section("On READY_BUT_GATED").para(
        "If inputs are present and licensed, A′/B execution still requires lifting the "
        "pre-registered gate per MILESTONE_A_PRIME_PREREGISTRATION(_AMENDMENT_1).md and "
        "the roadmap. This entrypoint hands off; it does not run the gated decision.")
    meta = _repro.collect_metadata(config=asdict(cfg), seed=None,
                                   runtime_s=time.perf_counter() - t0)
    rb.repro_block(meta).footer()
    md = rb.write(out)
    print(md)
    print(f"[written] {out}  status={r['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
